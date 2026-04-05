import os
import sys
import logging
from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime
import re


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hola-secure-key-2025')

# Настройка базы данных - поддержка PostgreSQL
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    # Render.com использует postgres://, но SQLAlchemy требует postgresql://
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    logger.info("Using PostgreSQL database")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hola.db'
    logger.info("Using SQLite database")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Импорт моделей
from models import db, User, ChatHistory, UserPlaylistView

# Инициализация базы данных
db.init_app(app)

# Инициализация Login Manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = '🎵 Пожалуйста, войдите в аккаунт, чтобы использовать Hola AI!'
login_manager.login_message_category = 'info'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Импорт других модулей
from forms import RegistrationForm, LoginForm, ChatForm
from vk_parser import vk_parser, PLAYLISTS
from ai_rag import ai_system

# Создание таблиц базы данных
with app.app_context():
    db.create_all()
    logger.info("✅ Database tables created successfully")


# === Контекстный процессор для всех шаблонов ===
@app.context_processor
def utility_processor():
    return dict(now=datetime.now())


# === Главные маршруты ===

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


@app.route('/charts')
def charts():
    """Страница со всеми чартами"""
    playlists = vk_parser.get_all_playlists()
    return render_template('charts.html', playlists=playlists)


@app.route('/playlist/<playlist_id>')
def playlist_detail(playlist_id):
    """Детальная страница плейлиста"""
    playlist_info = vk_parser.get_playlist_info(playlist_id)
    if not playlist_info:
        flash('Плейлист не найден', 'error')
        return redirect(url_for('charts'))

    # Сохраняем просмотр если пользователь авторизован
    if current_user.is_authenticated:
        try:
            view = UserPlaylistView.query.filter_by(
                user_id=current_user.id,
                playlist_id=playlist_id
            ).first()

            if view:
                view.view_count += 1
                view.last_viewed = datetime.utcnow()
            else:
                view = UserPlaylistView(
                    user_id=current_user.id,
                    playlist_id=playlist_id,
                    playlist_title=playlist_info['title']
                )
                db.session.add(view)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error saving playlist view: {e}")
            db.session.rollback()

    return render_template('playlist_detail.html', playlist=playlist_info)


@app.route('/track/<playlist_id>/<int:track_index>')
def track_detail(playlist_id, track_index):
    """Детальная страница трека"""
    playlist_info = vk_parser.get_playlist_info(playlist_id)
    if not playlist_info or track_index >= len(playlist_info['tracks']):
        flash('Трек не найден', 'error')
        return redirect(url_for('charts'))

    track = playlist_info['tracks'][track_index]
    lyrics = vk_parser.get_track_lyrics(track['title'], track['artist'])
    analysis = vk_parser.get_track_analysis(track)

    return render_template('track_detail.html',
                           track=track,
                           playlist=playlist_info,
                           lyrics=lyrics,
                           analysis=analysis,
                           track_index=track_index)


@app.route('/ai-chat')
@login_required
def ai_chat():
    """Страница чата с AI"""
    form = ChatForm()
    chat_history = ChatHistory.query.filter_by(user_id=current_user.id) \
        .order_by(ChatHistory.timestamp).all()
    return render_template('ai_chat.html', form=form, chat_history=chat_history)


@app.route('/faq')
def faq():
    """FAQ страница"""
    return render_template('faq.html')


@app.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    chat_history = ChatHistory.query.filter_by(user_id=current_user.id) \
        .order_by(ChatHistory.timestamp.desc()) \
        .limit(50).all()

    viewed_playlists = UserPlaylistView.query.filter_by(user_id=current_user.id) \
        .order_by(UserPlaylistView.last_viewed.desc()) \
        .limit(10).all()

    return render_template('profile.html',
                           chat_history=chat_history,
                           viewed_playlists=viewed_playlists)


# === API маршруты ===

@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    """API для общения с AI"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        playlist_context = data.get('playlist_context')

        if not user_message:
            return jsonify({'error': 'Сообщение не может быть пустым'}), 400

        # Сохраняем сообщение пользователя
        user_chat = ChatHistory(
            user_id=current_user.id,
            role='user',
            content=user_message,
            playlist_context=playlist_context
        )
        db.session.add(user_chat)
        db.session.commit()

        # Получаем контекст плейлиста если есть
        context = None
        if playlist_context and playlist_context != 'general':
            playlist_info = vk_parser.get_playlist_info(playlist_context)
            if playlist_info:
                context = ai_system.build_playlist_context(playlist_info)

        # Получаем историю для контекста диалога
        recent_history = ChatHistory.query.filter_by(user_id=current_user.id) \
            .order_by(ChatHistory.timestamp.desc()) \
            .limit(10).all()

        messages = []
        for chat in reversed(recent_history):
            messages.append({
                'role': chat.role,
                'content': chat.content
            })

        # Получаем ответ от AI
        ai_response = ai_system.get_ai_response(messages, context)

        # Сохраняем ответ AI
        ai_chat = ChatHistory(
            user_id=current_user.id,
            role='assistant',
            content=ai_response,
            playlist_context=playlist_context
        )
        db.session.add(ai_chat)
        db.session.commit()

        return jsonify({
            'response': ai_response,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Произошла ошибка при обработке запроса'}), 500


@app.route('/api/playlist/<playlist_id>/ask', methods=['POST'])
@login_required
def ask_about_playlist(playlist_id):
    """Задать вопрос о конкретном плейлисте"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()

        if not question:
            return jsonify({'error': 'Введите вопрос'}), 400

        playlist_info = vk_parser.get_playlist_info(playlist_id)
        if not playlist_info:
            return jsonify({'error': 'Плейлист не найден'}), 404

        context = ai_system.build_playlist_context(playlist_info)

        # Сохраняем вопрос
        user_chat = ChatHistory(
            user_id=current_user.id,
            role='user',
            content=f"[Плейлист: {playlist_info['title']}] {question}",
            playlist_context=playlist_id
        )
        db.session.add(user_chat)
        db.session.commit()

        # Получаем ответ
        messages = [{'role': 'user', 'content': question}]
        ai_response = ai_system.get_ai_response(messages, context)

        # Сохраняем ответ
        ai_chat = ChatHistory(
            user_id=current_user.id,
            role='assistant',
            content=ai_response,
            playlist_context=playlist_id
        )
        db.session.add(ai_chat)
        db.session.commit()

        return jsonify({'response': ai_response})

    except Exception as e:
        logger.error(f"Playlist ask error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Ошибка при обработке вопроса'}), 500


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