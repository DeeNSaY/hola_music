from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar_color = db.Column(db.String(7), default='#1DB954')

    # Relationships
    chats = db.relationship('ChatHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    viewed_playlists = db.relationship('UserPlaylistView', backref='user', lazy=True, cascade='all, delete-orphan')


class ChatHistory(db.Model):
    __tablename__ = 'chat_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    playlist_context = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }


class UserPlaylistView(db.Model):
    __tablename__ = 'user_playlist_views'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    playlist_id = db.Column(db.String(255), nullable=False)
    playlist_title = db.Column(db.String(255), nullable=False)
    view_count = db.Column(db.Integer, default=1)
    last_viewed = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)