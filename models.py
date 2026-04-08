from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Хеширование паролей: используется werkzeug.security.generate_password_hash
    # Алгоритм: pbkdf2:sha256 (стандарт Flask)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chats = db.relationship('ChatHistory', backref='user', lazy=True, cascade='all, delete-orphan')


class ChatHistory(db.Model):
    __tablename__ = 'chat_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    playlist_context = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ChartCache(db.Model):
    """Кеш чарта в базе данных"""
    __tablename__ = 'chart_cache'

    id = db.Column(db.Integer, primary_key=True)
    tracks_data = db.Column(db.JSON, nullable=False)  # Храним JSON с треками
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrackCache(db.Model):
    """Кеш информации о треках"""
    __tablename__ = 'track_cache'

    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    artist = db.Column(db.String(255), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    cover = db.Column(db.String(500))
    lyrics = db.Column(db.Text)
    bpm = db.Column(db.Integer)
    key = db.Column(db.String(50))
    popularity = db.Column(db.Integer)

    # ✅ НОВЫЕ ПОЛЯ
    album = db.Column(db.String(255))
    year = db.Column(db.Integer)
    genre = db.Column(db.String(128))
    explicit = db.Column(db.Boolean, default=False)
    available = db.Column(db.Boolean, default=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)