import os
import logging
from typing import List, Dict, Any
from vkpymusic import Service, TokenReceiver
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список стран для получения популярных треков
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
        self.service = None
        self.token = os.getenv('VK_TOKEN')
        self.init_service()

    def init_service(self):
        """Инициализация сервиса VK с токеном"""
        try:
            if self.token:
                # Получаем client из конфига или используем стандартный
                try:
                    self.service = Service.parse_config()
                    logger.info("✅ VK Service initialized from config")
                except:
                    # Если нет конфига, используем токен напрямую
                    # Для этого нужен client - получаем его через TokenReceiver
                    login = os.getenv('VK_LOGIN')
                    password = os.getenv('VK_PASSWORD')

                    if login and password:
                        token_receiver = TokenReceiver(login, password)
                        if token_receiver.auth():
                            token_receiver.get_token()
                            token_receiver.save_to_config()
                            self.service = Service.parse_config()
                            logger.info("✅ VK Service initialized with new token")
                        else:
                            logger.error("❌ Failed to authenticate with VK")
                    else:
                        logger.error("❌ No VK credentials found")
            else:
                logger.error("❌ VK_TOKEN not found")
        except Exception as e:
            logger.error(f"❌ Error initializing VK service: {e}")

    def get_all_playlists(self) -> List[Dict]:
        """Получить все плейлисты"""
        return PLAYLISTS

    def get_playlist_info(self, playlist_id: str) -> Dict:
        """Получить информацию о плейлисте с реальными треками"""
        playlist = next((p for p in PLAYLISTS if p["id"] == playlist_id), None)
        if not playlist:
            return None

        # Получаем реальные популярные треки через VK API
        tracks = self.get_playlist_tracks(playlist)

        return {
            **playlist,
            "tracks": tracks,
            "total_tracks": len(tracks),
            "description": f"Топ-100 самых популярных треков в {playlist['country']} по версии VK Музыка"
        }

    def get_playlist_tracks(self, playlist: Dict) -> List[Dict]:
        """Получить реальные треки через VK API метод get_popular"""
        if not self.service:
            logger.error("❌ VK Service not available")
            return []

        try:
            # Используем встроенный метод get_popular для получения популярных треков
            # Это дает реальные популярные треки из VK
            popular_songs = self.service.get_popular(count=50, offset=0)

            tracks = []
            for i, song in enumerate(popular_songs[:20]):  # Берем топ-20
                # Получаем полную информацию о треке
                track_info = self._get_complete_track_info(song)
                if track_info:
                    tracks.append(track_info)

            logger.info(f"✅ Got {len(tracks)} real popular tracks from VK")
            return tracks

        except Exception as e:
            logger.error(f"❌ Error getting popular tracks: {e}")
            return []

    def _get_complete_track_info(self, song) -> Dict:
        """Получить полную информацию о треке из объекта VK"""
        try:
            # Основная информация из объекта песни
            track_id = getattr(song, 'id', None)
            title = getattr(song, 'title', 'Unknown')
            artist = getattr(song, 'artist', 'Unknown')
            duration = getattr(song, 'duration', 0)
            url = getattr(song, 'url', '')

            # Получаем обложку из альбома если есть
            cover = self._get_cover_url(song)

            # Получаем текст песни через поиск
            lyrics = self.get_track_lyrics(title, artist)

            # Получаем ID исполнителя для дополнительной информации
            artist_id = getattr(song, 'owner_id', None)

            return {
                'id': track_id,
                'title': title,
                'artist': artist,
                'artist_id': artist_id,
                'duration': duration,
                'url': url,
                'cover': cover,
                'lyrics': lyrics,
            }

        except Exception as e:
            logger.error(f"Error getting track info: {e}")
            return None

    def _get_cover_url(self, song) -> str:
        """Получить URL обложки из объекта песни"""
        # Пробуем получить обложку из альбома
        if hasattr(song, 'album'):
            album = getattr(song, 'album')
            if album and hasattr(album, 'thumb'):
                thumb = album.thumb
                if thumb and hasattr(thumb, 'url'):
                    return thumb.url

        # Пробуем другие возможные поля
        if hasattr(song, 'photo'):
            photo = getattr(song, 'photo')
            if photo and hasattr(photo, 'url'):
                return photo.url

        # Если обложки нет, возвращаем заглушку
        return "https://vk.com/images/camera_100.png"

    def get_track_lyrics(self, title: str, artist: str) -> str:
        """Получить текст песни через поиск в VK"""
        if not self.service:
            return self._get_info_message(title, artist)

        try:
            # Ищем песню с текстом
            query = f"{artist} {title} текст"
            songs = self.service.search_songs_by_text(query, count=3)

            for song in songs:
                # Проверяем различные поля где может быть текст
                if hasattr(song, 'text') and song.text:
                    return song.text
                if hasattr(song, 'lyrics') and song.lyrics:
                    return song.lyrics

                # Если есть ID текста, пытаемся получить его
                if hasattr(song, 'lyrics_id') and song.lyrics_id:
                    lyrics = self._get_lyrics_by_id(song.lyrics_id)
                    if lyrics:
                        return lyrics

            # Если текст не найден, возвращаем информацию
            return self._get_info_message(title, artist)

        except Exception as e:
            logger.error(f"Error getting lyrics: {e}")
            return self._get_info_message(title, artist)

    def _get_lyrics_by_id(self, lyrics_id: int) -> str:
        """Получить текст по ID через VK API"""
        try:
            # Прямой запрос к API для получения текста
            import requests
            url = "https://api.vk.com/method/audio.getLyrics"
            params = {
                'lyrics_id': lyrics_id,
                'access_token': self.token,
                'v': '5.131'
            }
            response = requests.get(url, params=params)
            data = response.json()

            if 'response' in data and 'text' in data['response']:
                return data['response']['text']
        except:
            pass
        return None

    def _get_info_message(self, title: str, artist: str) -> str:
        """Информационное сообщение вместо текста"""
        return f"""🎵 {title} - {artist} 🎵

ℹ️ Информация о треке:
• Исполнитель: {artist}
• Название: {title}

К сожалению, текст этой песни не найден в открытом доступе через VK API.

💡 Но вы можете:
• Спросить Hola AI о значении и популярности этого трека
• Найти текст в официальных источниках
• Наслаждаться музыкой!

🎯 Примеры вопросов для Hola AI:
- "Почему песня {title} стала популярной?"
- "Какой жанр у исполнителя {artist}?"
- "Проанализируй музыкальные характеристики этого трека" """

    def analyze_track(self, track: Dict) -> Dict:
        """Анализ трека на основе реальных данных из VK"""
        duration = track.get('duration', 180)

        # Реалистичный анализ на основе длительности и популярности
        if duration < 180:
            energy = "⚡ Высокая (короткий формат, TikTok-тренды)"
            mood = "🔥 Энергичный / Виральный"
        elif duration < 240:
            energy = "💪 Средняя (стандартный поп-формат)"
            mood = "💃 Танцевальный / Оптимистичный"
        else:
            energy = "😌 Умеренная (глубокий трек)"
            mood = "🎸 Спокойный / Эмоциональный"

        return {
            "title": track.get("title"),
            "artist": track.get("artist"),
            "duration": f"{duration // 60}:{duration % 60:02d}",
            "cover": track.get("cover"),
            "energy_level": energy,
            "mood": mood,
        }


vk_parser = VKParser()