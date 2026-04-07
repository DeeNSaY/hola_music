import os
import logging
from typing import List, Dict, Any
from vkpymusic import Service
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список стран с поисковыми запросами для получения ТОП-10 треков
PLAYLISTS = [
    {"id": "russia", "title": "Россия: Топ-10", "country": "Россия", "icon": "🇷🇺", "search_query": "россия топ треки"},
    {"id": "kazakhstan", "title": "Казахстан: Топ-10", "country": "Казахстан", "icon": "🇰🇿",
     "search_query": "казахстан топ треки"},
    {"id": "belarus", "title": "Беларусь: Топ-10", "country": "Беларусь", "icon": "🇧🇾",
     "search_query": "беларусь топ треки"},
    {"id": "azerbaijan", "title": "Азербайджан: Топ-10", "country": "Азербайджан", "icon": "🇦🇿",
     "search_query": "азербайджан топ треки"},
    {"id": "armenia", "title": "Армения: Топ-10", "country": "Армения", "icon": "🇦🇲",
     "search_query": "армения топ треки"},
    {"id": "uzbekistan", "title": "Узбекистан: Топ-10", "country": "Узбекистан", "icon": "🇺🇿",
     "search_query": "узбекистан топ треки"},
]


class VKParser:
    def __init__(self):
        self.token = os.getenv('VK_TOKEN')
        self.service = None
        self.init_service()

    def init_service(self):
        """Инициализация сервиса VK с токеном"""
        try:
            if self.token and self.token != "your_vk_token_here":
                # ВАЖНО: Service(user_agent, token) - именно в таком порядке!
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                self.service = Service(user_agent, self.token)
                logger.info("✅ VK Service initialized with token")

                # Проверяем, работает ли токен
                if self.service.is_token_valid():
                    logger.info("✅ Token is valid")
                else:
                    logger.warning("⚠️ Token validation failed")
            else:
                logger.error("❌ VK_TOKEN not found in environment")
        except Exception as e:
            logger.error(f"❌ Error initializing VK service: {e}")

    def get_all_playlists(self) -> List[Dict]:
        return PLAYLISTS

    def get_playlist_info(self, playlist_id: str) -> Dict:
        """Получить информацию о плейлисте с ТОП-10 треками по стране"""
        playlist = next((p for p in PLAYLISTS if p["id"] == playlist_id), None)
        if not playlist:
            return None

        # Получаем ТОП-10 треков для этой страны
        tracks = self.get_playlist_tracks(playlist)

        return {
            **playlist,
            "tracks": tracks,
            "total_tracks": len(tracks),
            "description": f"Топ-10 популярных треков в {playlist['country']} по версии VK Музыка"
        }

    def get_playlist_tracks(self, playlist: Dict) -> List[Dict]:
        """Получить ТОП-10 треков для конкретной страны через поиск"""
        if not self.service:
            logger.error("❌ VK Service not available")
            return self._get_fallback_tracks(playlist['country'])

        try:
            search_query = playlist.get('search_query', f"{playlist['country']} топ треки")
            logger.info(f"🔍 Searching tracks for {playlist['country']}: '{search_query}'")

            # Используем поиск для получения треков
            songs = self.service.search_songs_by_text(search_query, count=10)

            tracks = []
            for i, song in enumerate(songs):
                track = self._parse_song(song, i)
                if track:
                    tracks.append(track)

            logger.info(f"✅ Got {len(tracks)} tracks for {playlist['country']}")
            return tracks if tracks else self._get_fallback_tracks(playlist['country'])

        except Exception as e:
            logger.error(f"❌ Error getting tracks for {playlist['country']}: {e}")
            return self._get_fallback_tracks(playlist['country'])

    def _parse_song(self, song, index: int) -> Dict:
        """Парсинг песни из VK с полной информацией"""
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

            # Получаем BPM (если есть) или вычисляем приблизительно
            bpm = self._get_bpm(song, duration)

            # Получаем тональность
            key = self._get_key(song, title, artist)

            return {
                'id': song_id,
                'title': title,
                'artist': artist,
                'owner_id': owner_id,
                'duration': duration,
                'url': url,
                'cover': cover,
                'lyrics': lyrics,
                'bpm': bpm,
                'key': key,
                'popularity': 95 - index * 2 if index < 10 else 70,
            }
        except Exception as e:
            logger.error(f"Error parsing song: {e}")
            return None

    def _get_cover(self, song) -> str:
        """Получить обложку трека из VK"""
        # Пробуем получить из album.thumb
        if hasattr(song, 'album'):
            album = song.album
            if album and hasattr(album, 'thumb'):
                thumb = album.thumb
                if thumb and hasattr(thumb, 'url'):
                    return thumb.url

        # Пробуем получить из photo
        if hasattr(song, 'photo'):
            photo = song.photo
            if photo and hasattr(photo, 'url'):
                return photo.url

        # Если нет обложки, возвращаем стандартную
        return "https://vk.com/images/camera_100.png"

    def _get_bpm(self, song, duration: int) -> int:
        """Получить BPM трека"""
        # Если в объекте есть BPM
        if hasattr(song, 'bpm') and song.bpm:
            return song.bpm

        # Приблизительный BPM на основе длительности
        # Короткие песни (2-3 мин) обычно быстрее (120-140 BPM)
        # Длинные песни (4+ мин) обычно медленнее (70-90 BPM)
        if duration < 180:
            return 128  # Typical pop/dance
        elif duration < 240:
            return 110  # Typical rock/pop
        else:
            return 85  # Typical ballad

    def _get_key(self, song, title: str, artist: str) -> str:
        """Получить тональность трека"""
        if hasattr(song, 'key') and song.key:
            return song.key

        # Стандартные тональности для популярной музыки
        keys = ['C major', 'G major', 'D major', 'A major', 'E major',
                'F major', 'A minor', 'E minor', 'D minor', 'B minor']

        # Используем хеш для детерминированного выбора
        import hashlib
        hash_val = int(hashlib.md5(f"{title}{artist}".encode()).hexdigest()[:8], 16)
        return keys[hash_val % len(keys)]

    def get_track_lyrics(self, title: str, artist: str) -> str:
        """Получить текст песни через VK API"""
        if not self.service:
            return self._no_lyrics_message(title, artist)

        try:
            # Ищем песню с текстом
            query = f"{artist} {title} текст"
            songs = self.service.search_songs_by_text(query, count=3)

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
            logger.error(f"Error getting lyrics for {title}: {e}")
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
        except Exception as e:
            logger.error(f"Error fetching lyrics by id: {e}")
        return None

    def _no_lyrics_message(self, title: str, artist: str) -> str:
        """Сообщение при отсутствии текста"""
        return f"""🎵 {title} - {artist} 🎵

📝 Информация о треке:
• Исполнитель: {artist}
• Название: {title}

К сожалению, текст этой песни временно недоступен через VK API.

💡 Вы можете:
• Спросить Hola AI о смысле и популярности этой песни
• Найти текст на официальных сайтах
• Наслаждаться музыкой!

🎯 Примеры вопросов для Hola AI:
• "Почему песня {title} стала популярной?"
• "Какой музыкальный стиль у {artist}?"
• "Проанализируй этот трек по BPM и тональности"
"""

    def _get_fallback_tracks(self, country: str) -> List[Dict]:
        """Запасные треки если API не работает"""
        fallback_tracks = [
            {"title": "Birds of a Feather", "artist": "Billie Eilish", "duration": 210, "bpm": 118, "key": "C major"},
            {"title": "Beautiful Things", "artist": "Benson Boone", "duration": 195, "bpm": 120, "key": "D minor"},
            {"title": "Lose Control", "artist": "Teddy Swims", "duration": 225, "bpm": 85, "key": "E major"},
            {"title": "Espresso", "artist": "Sabrina Carpenter", "duration": 185, "bpm": 128, "key": "C minor"},
            {"title": "Too Sweet", "artist": "Hozier", "duration": 240, "bpm": 92, "key": "A major"},
            {"title": "We Can't Be Friends", "artist": "Ariana Grande", "duration": 215, "bpm": 115, "key": "F major"},
            {"title": "Texas Hold 'Em", "artist": "Beyoncé", "duration": 210, "bpm": 100, "key": "G major"},
            {"title": "Saturn", "artist": "SZA", "duration": 225, "bpm": 80, "key": "D major"},
            {"title": "Yes, And?", "artist": "Ariana Grande", "duration": 205, "bpm": 125, "key": "B minor"},
            {"title": "Greedy", "artist": "Tate McRae", "duration": 185, "bpm": 130, "key": "F# minor"},
        ]

        tracks = []
        for i, track_data in enumerate(fallback_tracks[:10]):
            tracks.append({
                'id': i,
                'title': track_data['title'],
                'artist': track_data['artist'],
                'duration': track_data['duration'],
                'cover': f"https://picsum.photos/id/{i + 10}/200/200",
                'lyrics': self._no_lyrics_message(track_data['title'], track_data['artist']),
                'bpm': track_data['bpm'],
                'key': track_data['key'],
                'popularity': 90 - i,
            })
        return tracks

    def get_track_analysis(self, track: Dict) -> Dict:
        """Анализ трека на основе полученных данных"""
        bpm = track.get('bpm', 100)
        duration = track.get('duration', 180)

        if bpm > 120:
            energy = "⚡ Высокая (энергичный ритм)"
            mood = "🔥 Живой / Танцевальный"
        elif bpm > 90:
            energy = "💪 Средняя (умеренный ритм)"
            mood = "💃 Оптимистичный / Поп"
        else:
            energy = "😌 Низкая (спокойный ритм)"
            mood = "🎵 Расслабляющий / Меланхоличный"

        return {
            "title": track.get("title"),
            "artist": track.get("artist"),
            "duration": f"{duration // 60}:{duration % 60:02d}",
            "bpm": bpm,
            "key": track.get("key", "Unknown"),
            "cover": track.get("cover"),
            "energy_level": energy,
            "mood": mood,
            "popularity": track.get("popularity", 80),
        }


vk_parser = VKParser()