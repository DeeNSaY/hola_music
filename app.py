import os
import sys
import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hola-secure-key-2025')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///hola.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, User, ChatHistory, UserPlaylistView
db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Импортируем новый парсер вместо vk_parser
from yandex_parser import yandex_parser
from forms import RegistrationForm, LoginForm, ChatForm
from ai_rag import ai_system

# Создание таблиц
with app.app_context():
    db.create_all()
    logger.info("✅ Database ready")

# Контекстный процессор
@app.context_processor
def utility_processor():
    return dict(now=datetime.now())

# === Маршруты ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/charts')
def charts():
    """Страница чарта – получаем треки из Яндекс Музыки"""
    tracks = yandex_parser.get_chart_tracks(limit=20)
    return render_template('charts.html', tracks=tracks)

@app.route('/track/<int:track_index>')
def track_detail(track_index):
    """Детальная страница трека по индексу в чарте"""
    tracks = yandex_parser.get_chart_tracks(limit=50)  # можно закешировать
    if track_index >= len(tracks):
        flash('Трек не найден', 'error')
        return redirect(url_for('charts'))
    track = tracks[track_index]
    lyrics = track.get('lyrics', '')
    analysis = yandex_parser.get_track_analysis(track)
    return render_template('track_detail.html', track=track, lyrics=lyrics, analysis=analysis, track_index=track_index)

@app.route('/ai-chat')
@login_required
def ai_chat():
    form = ChatForm()
    chat_history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp).all()
    return render_template('ai_chat.html', form=form, chat_history=chat_history)

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/profile')
@login_required
def profile():
    chat_history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).limit(50).all()
    viewed_playlists = []  # можно убрать или оставить для совместимости
    return render_template('profile.html', chat_history=chat_history, viewed_playlists=viewed_playlists)

# === API ===
@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    playlist_context = data.get('playlist_context')
    if not user_message:
        return jsonify({'error': 'Сообщение не может быть пустым'}), 400

    user_chat = ChatHistory(user_id=current_user.id, role='user', content=user_message, playlist_context=playlist_context)
    db.session.add(user_chat)
    db.session.commit()

    context = None
    if playlist_context and playlist_context != 'general':
        # Если нужен контекст чарта, можно передать треки
        tracks = yandex_parser.get_chart_tracks(limit=20)
        context = "Чарт Яндекс Музыки:\n" + "\n".join([f"{i+1}. {t['title']} - {t['artist']} (BPM: {t['bpm']}, тональность: {t['key']})" for i, t in enumerate(tracks[:10]])

    recent_history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).limit(10).all()
    messages = [{'role': chat.role, 'content': chat.content} for chat in reversed(recent_history)]

    ai_response = ai_system.get_ai_response(messages, context)
    ai_chat = ChatHistory(user_id=current_user.id, role='assistant', content=ai_response, playlist_context=playlist_context)
    db.session.add(ai_chat)
    db.session.commit()
    return jsonify({'response': ai_response})

@app.route('/api/playlist/<playlist_id>/ask', methods=['POST'])
@login_required
def ask_about_playlist(playlist_id):
    # Упростим: спрашиваем о чарте
    data = request.get_json()
    question = data.get('question', '')
    tracks = yandex_parser.get_chart_tracks(limit=20)
    context = "Чарт Яндекс Музыки:\n" + "\n".join([f"{i+1}. {t['title']} - {t['artist']} (BPM: {t['bpm']}, тональность: {t['key']})" for i, t in enumerate(tracks[:10]]])
    user_chat = ChatHistory(user_id=current_user.id, role='user', content=f"[Чарт] {question}", playlist_context=playlist_id)
    db.session.add(user_chat)
    db.session.commit()
    ai_response = ai_system.get_ai_response([{'role': 'user', 'content': question}], context)
    ai_chat = ChatHistory(user_id=current_user.id, role='assistant', content=ai_response, playlist_context=playlist_id)
    db.session.add(ai_chat)
    db.session.commit()
    return jsonify({'response': ai_response})

# === Аутентификация ===

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Проверяем существование пользователя
            existing_user = User.query.filter_by(email=form.email.data.lower()).first()
            if existing_user:
                flash('Пользователь с таким email уже существует', 'error')
                return render_template('register.html', form=form)

            existing_username = User.query.filter_by(username=form.username.data).first()
            if existing_username:
                flash('Пользователь с таким именем уже существует', 'error')
                return render_template('register.html', form=form)

            hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
            user = User(
                username=form.username.data,
                email=form.email.data.lower(),
                password_hash=hashed_password
            )
            db.session.add(user)
            db.session.commit()

            flash(f'🎉 Добро пожаловать, {user.username}! Регистрация прошла успешно.', 'success')
            login_user(user)
            return redirect(url_for('index'))

        except Exception as e:
            logger.error(f"Registration error: {e}")
            db.session.rollback()
            flash('Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.', 'error')

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                flash(f'🎵 С возвращением, {user.username}!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Неверный email или пароль', 'error')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Произошла ошибка при входе. Пожалуйста, попробуйте позже.', 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта. Ждем вас снова! 🎵', 'info')
    return redirect(url_for('index'))


# === Обработка ошибок ===

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)