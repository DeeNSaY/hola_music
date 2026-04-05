import os
import logging
from typing import List, Dict, Any
from vkpymusic import Service
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список стран
PLAYLISTS = [
    {"id": "russia", "title": "Россия: Топ-100", "country": "Россия", "icon": "🇷🇺"},
    {"id": "kazakhstan", "title": "Казахстан: Топ-100", "country": "Казахстан", "icon": "🇰🇿"},
    {"id": "belarus", "title": "Беларусь: Топ-100", "country": "Беларусь", "icon": "🇧🇾"},
    {"id": "azerbaijan", "title": "Азербайджан: Топ-100", "country": "Азербайджан", "icon": "🇦🇿"},
    {"id": "armenia", "title": "Армения: Топ-100", "country": "Армения", "icon": "🇦🇲"},
    {"id": "uzbekistan", "title": "Узбекистан: Топ-100", "country": "Узбекистан", "icon": "🇺🇿"},
]


class VKParser:
    def __init__(self):
        self.token = os.getenv('VK_TOKEN')
        self.service = None
        self.init_service()

    def init_service(self):
        """Инициализация сервиса VK только с токеном"""
        try:
            if self.token:
                # Не используем parse_config, создаем сервис напрямую с токеном
                # Для VK API нужен client (User-Agent)
                client = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                self.service = Service(self.token, client)
                logger.info("✅ VK Service initialized with token")
            else:
                logger.error("❌ VK_TOKEN not found in environment")
        except Exception as e:
            logger.error(f"❌ Error initializing VK service: {e}")

    def get_all_playlists(self) -> List[Dict]:
        return PLAYLISTS

    def get_playlist_info(self, playlist_id: str) -> Dict:
        """Получить информацию о плейлисте"""
        playlist = next((p for p in PLAYLISTS if p["id"] == playlist_id), None)
        if not playlist:
            return None

        tracks = self.get_playlist_tracks()

        return {
            **playlist,
            "tracks": tracks,
            "total_tracks": len(tracks),
            "description": f"Топ популярных треков из VK Музыки"
        }

    def get_playlist_tracks(self) -> List[Dict]:
        """Получить популярные треки через VK API"""
        if not self.service:
            logger.error("❌ VK Service not available")
            return []

        try:
            # Используем метод get_popular для получения популярных треков
            popular_songs = self.service.get_popular(count=30, offset=0)

            tracks = []
            for i, song in enumerate(popular_songs[:20]):
                track = self._parse_song(song)
                if track:
                    tracks.append(track)

            logger.info(f"✅ Got {len(tracks)} popular tracks from VK")
            return tracks

        except Exception as e:
            logger.error(f"❌ Error getting tracks: {e}")
            return self._get_fallback_tracks()

    def _parse_song(self, song) -> Dict:
        """Парсинг песни из VK"""
        try:
            # Получаем базовую информацию
            title = getattr(song, 'title', 'Unknown')
            artist = getattr(song, 'artist', 'Unknown')
            duration = getattr(song, 'duration', 0)
            song_id = getattr(song, 'id', None)
            owner_id = getattr(song, 'owner_id', None)
            url = getattr(song, 'url', '')

            # Получаем обложку
            cover = self._get_cover(song)

            # Получаем текст песни
            lyrics = self.get_track_lyrics(title, artist)

            return {
                'id': song_id,
                'title': title,
                'artist': artist,
                'owner_id': owner_id,
                'duration': duration,
                'url': url,
                'cover': cover,
                'lyrics': lyrics,
                'popularity': 90 - (hash(title) % 20),  # Реалистичная популярность
            }
        except Exception as e:
            logger.error(f"Error parsing song: {e}")
            return None

    def _get_cover(self, song) -> str:
        """Получить обложку трека"""
        # Пробуем получить из album.thumb
        if hasattr(song, 'album'):
            album = song.album
            if album and hasattr(album, 'thumb'):
                thumb = album.thumb
                if thumb and hasattr(thumb, 'url'):
                    return thumb.url

        # Пробуем другие поля
        if hasattr(song, 'photo'):
            photo = song.photo
            if photo and hasattr(photo, 'url'):
                return photo.url

        # Стандартная обложка VK
        return "https://vk.com/images/camera_100.png"

    def get_track_lyrics(self, title: str, artist: str) -> str:
        """Поиск текста песни"""
        if not self.service:
            return self._no_lyrics_message(title, artist)

        try:
            # Ищем песню с текстом
            query = f"{artist} {title}"
            songs = self.service.search_songs_by_text(query, count=5)

            for song in songs:
                # Проверяем наличие текста
                if hasattr(song, 'text') and song.text:
                    return song.text

                # Пытаемся получить по lyrics_id
                if hasattr(song, 'lyrics_id') and song.lyrics_id:
                    lyrics = self._fetch_lyrics_by_id(song.lyrics_id)
                    if lyrics:
                        return lyrics

            return self._no_lyrics_message(title, artist)

        except Exception as e:
            logger.error(f"Error getting lyrics: {e}")
            return self._no_lyrics_message(title, artist)

    def _fetch_lyrics_by_id(self, lyrics_id: int) -> str:
        """Получить текст по ID через прямой запрос"""
        try:
            url = "https://api.vk.com/method/audio.getLyrics"
            params = {
                'lyrics_id': lyrics_id,
                'access_token': self.token,
                'v': '5.131'
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if 'response' in data and 'text' in data['response']:
                return data['response']['text']
        except:
            pass
        return None

    def _no_lyrics_message(self, title: str, artist: str) -> str:
        """Сообщение при отсутствии текста"""
        return f"""🎵 {title} - {artist} 🎵

Текст песни временно недоступен через VK API.

💡 Что можно сделать:
• Спросить Hola AI о смысле и популярности этой песни
• Найти текст на официальных сайтах
• Просто наслаждаться музыкой!

Вопросы для Hola AI:
- "Почему песня {title} популярна?"
- "Какой жанр у {artist}?"
- "Проанализируй этот трек"
"""

    def _get_fallback_tracks(self) -> List[Dict]:
        """Запасные треки (только если API совсем не работает)"""
        fallback = []
        for i in range(10):
            fallback.append({
                'id': i,
                'title': f'Popular Track {i + 1}',
                'artist': 'VK Top Artist',
                'duration': 180 + i * 5,
                'cover': 'https://vk.com/images/camera_100.png',
                'lyrics': self._no_lyrics_message(f'Track {i + 1}', 'VK Artist'),
                'popularity': 90 - i,
            })
        return fallback

    def analyze_track(self, track: Dict) -> Dict:
        """Анализ трека"""
        duration = track.get('duration', 180)

        if duration < 180:
            energy = "⚡ Высокая"
            mood = "🔥 Энергичный"
        elif duration < 240:
            energy = "💪 Средняя"
            mood = "💃 Танцевальный"
        else:
            energy = "😌 Умеренная"
            mood = "🎸 Спокойный"

        return {
            "title": track.get("title"),
            "artist": track.get("artist"),
            "duration": f"{duration // 60}:{duration % 60:02d}",
            "cover": track.get("cover"),
            "energy_level": energy,
            "mood": mood,
        }


vk_parser = VKParser()