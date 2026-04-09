import os
import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hola-secure-key-2025')
database_url = os.getenv('DATABASE_URL', 'sqlite:///hola.db')
if database_url and database_url.startswith('postgres://'):
    # Render использует postgres://, заменяем на postgresql:// и добавляем sslmode
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if 'sslmode' not in database_url:
        database_url += '?sslmode=require'
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, User, ChatHistory, ChartCache, TrackCache

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


from yandex_parser import yandex_parser
from forms import RegistrationForm, LoginForm, ChatForm
from ai_rag import ai_system

# Создание таблиц
with app.app_context():
    db.create_all()
    # Привязываем парсер к app для доступа к БД
    yandex_parser.app = app
    logger.info("✅ Database ready")


@app.context_processor
def utility_processor():
    return dict(now=datetime.now())


# === Кешированный доступ к чарту ===
def get_cached_chart_tracks(limit=20, force_refresh=False):
    """Получить чарт из кеша БД или API"""
    with app.app_context():
        return yandex_parser.get_chart_tracks(limit=limit, force_refresh=force_refresh)


# === Маршруты ===
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/charts')
def charts():
    force = request.args.get('refresh', '0') == '1'
    tracks = get_cached_chart_tracks(limit=100, force_refresh=force)   # было 20, теперь 100
    return render_template('charts.html', tracks=tracks)

@app.route('/track/<int:track_index>')
def track_detail(track_index):
    tracks = get_cached_chart_tracks(limit=100)   # тоже 100
    if track_index >= len(tracks):
        flash('Трек не найден', 'error')
        return redirect(url_for('charts'))

    track = tracks[track_index]
    lyrics = track.get('lyrics', '')
    analysis = yandex_parser.get_track_analysis(track)

    return render_template('track_detail.html',
                           track=track,
                           lyrics=lyrics,
                           analysis=analysis,
                           track_index=track_index)

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
    chat_history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).limit(
        50).all()
    return render_template('profile.html', chat_history=chat_history)


# === API ===
@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    data = request.get_json()
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({'error': 'Введите сообщение'}), 400

    # Сохраняем сообщение пользователя
    user_chat = ChatHistory(user_id=current_user.id, role='user', content=user_message)
    db.session.add(user_chat)
    db.session.commit()

    # Определяем тип вопроса и формируем контекст
    tracks = get_cached_chart_tracks(limit=10)
    tracks_context = ai_system.build_tracks_context(tracks)

    # Проверяем, спрашивают ли о конкретном треке
    track_context = None
    for track in tracks:
        if track.get('title').lower() in user_message.lower() or track.get('artist').lower() in user_message.lower():
            track_context = ai_system.build_full_track_context(track)
            break

    # История диалога
    recent = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.timestamp.desc()).limit(6).all()
    messages = [{'role': c.role, 'content': c.content} for c in reversed(recent)]

    # Ответ AI
    ai_response = ai_system.get_ai_response(messages, tracks_context, track_context)

    ai_chat = ChatHistory(user_id=current_user.id, role='assistant', content=ai_response)
    db.session.add(ai_chat)
    db.session.commit()

    return jsonify({'response': ai_response})


@app.route('/api/refresh-chart', methods=['POST'])
@login_required
def refresh_chart():
    """Принудительное обновление кеша чарта"""
    tracks = get_cached_chart_tracks(limit=20, force_refresh=True)
    return jsonify({'status': 'ok', 'count': len(tracks)})


# === Аутентификация ===
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower()).first()
        if existing:
            flash('Email уже используется', 'error')
            return render_template('register.html', form=form)

        hashed = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user = User(username=form.username.data, email=form.email.data.lower(), password_hash=hashed)
        db.session.add(user)
        db.session.commit()

        flash(f'Добро пожаловать, {user.username}!', 'success')
        login_user(user)
        return redirect(url_for('index'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash(f'С возвращением, {user.username}!', 'success')
            return redirect(url_for('index'))
        flash('Неверный email или пароль', 'error')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта', 'info')
    return redirect(url_for('index'))


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('500.html'), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)