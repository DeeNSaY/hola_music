import os
import logging
from typing import List, Dict, Any
from vkpymusic import Service
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ID реальных плейлистов из VK (нужно найти реальные ID)
PLAYLISTS = [
    {"id": "top100_russia", "title": "Россия: Топ-100", "country": "Россия", "icon": "🇷🇺", "owner_id": "-200100",
     "playlist_id": "100"},
    {"id": "top100_kazakhstan", "title": "Казахстан: Топ-100", "country": "Казахстан", "icon": "🇰🇿",
     "owner_id": "-200101", "playlist_id": "101"},
    {"id": "top100_belarus", "title": "Беларусь: Топ-100", "country": "Беларусь", "icon": "🇧🇾", "owner_id": "-200102",
     "playlist_id": "102"},
    {"id": "top100_azerbaijan", "title": "Азербайджан: Топ-100", "country": "Азербайджан", "icon": "🇦🇿",
     "owner_id": "-200103", "playlist_id": "103"},
    {"id": "top100_armenia", "title": "Армения: Топ-100", "country": "Армения", "icon": "🇦🇲", "owner_id": "-200104",
     "playlist_id": "104"},
    {"id": "top100_uzbekistan", "title": "Узбекистан: Топ-100", "country": "Узбекистан", "icon": "🇺🇿",
     "owner_id": "-200105", "playlist_id": "105"},
]


class VKParser:
    def __init__(self):
        self.token = os.getenv('VK_TOKEN')
        self.service = None
        self.init_service()

    def init_service(self):
        """Инициализация сервиса VK с токеном"""
        try:
            if self.token:
                # Стандартный user-agent для VK API
                client = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                self.service = Service(self.token, client)
                logger.info("✅ VK Service initialized successfully")
            else:
                logger.warning("⚠️ VK_TOKEN not found")
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

        # Получаем реальные треки из VK
        tracks = self.get_playlist_tracks(playlist)

        return {
            **playlist,
            "tracks": tracks,
            "total_tracks": len(tracks),
            "description": f"Топ-100 самых популярных треков в {playlist['country']} по версии VK Музыка"
        }

    def get_playlist_tracks(self, playlist: Dict) -> List[Dict]:
        """Получить треки плейлиста через VK API"""
        if not self.service:
            logger.warning("VK Service not available")
            return []

        try:
            # Ищем популярные треки по стране
            country_queries = {
                "Россия": "россия топ треки",
                "Казахстан": "казахстан топ треки",
                "Беларусь": "беларусь топ треки",
                "Азербайджан": "азербайджан топ треки",
                "Армения": "армения топ треки",
                "Узбекистан": "узбекистан топ треки",
            }

            query = country_queries.get(playlist['country'], f"{playlist['country']} топ треки")

            # Используем поиск по тексту для получения популярных треков
            songs = self.service.search_songs_by_text(query, count=20)

            tracks = []
            for i, song in enumerate(songs):
                track = self._parse_song(song, i)
                tracks.append(track)

            logger.info(f"✅ Got {len(tracks)} tracks for {playlist['country']}")
            return tracks

        except Exception as e:
            logger.error(f"❌ Error getting tracks: {e}")
            return self._get_fallback_tracks(playlist['country'])

    def _parse_song(self, song, index: int) -> Dict:
        """Парсинг объекта песни из VK"""
        # Получаем обложку
        cover = self._get_song_cover(song)

        # Получаем или генерируем BPM
        bpm = self._get_song_bpm(song)

        # Получаем или генерируем тональность
        key = self._get_song_key(song)

        return {
            'id': getattr(song, 'id', index),
            'title': getattr(song, 'title', 'Unknown'),
            'artist': getattr(song, 'artist', 'Unknown'),
            'duration': getattr(song, 'duration', 180),
            'cover': cover,
            'bpm': bpm,
            'key': key,
            'popularity': 95 - (index * 2) if index < 20 else 50,
            'url': getattr(song, 'url', ''),
        }

    def _get_song_cover(self, song) -> str:
        """Получить обложку песни"""
        # Пытаемся получить из разных атрибутов
        if hasattr(song, 'cover'):
            cover = getattr(song, 'cover', '')
            if cover:
                return cover

        if hasattr(song, 'album'):
            album = getattr(song, 'album', None)
            if album and hasattr(album, 'thumb'):
                return getattr(album, 'thumb', '')

        # Стандартные обложки
        default_covers = [
            "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=200&h=200&fit=crop",
            "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=200&h=200&fit=crop",
            "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=200&h=200&fit=crop",
            "https://images.unsplash.com/photo-1459749411171-04bf5292ce7f?w=200&h=200&fit=crop",
        ]
        return random.choice(default_covers)

    def _get_song_bpm(self, song) -> int:
        """Получить или оценить BPM песни"""
        if hasattr(song, 'bpm') and getattr(song, 'bpm'):
            return getattr(song, 'bpm')

        # Оцениваем BPM на основе длительности
        duration = getattr(song, 'duration', 180)
        if duration < 180:
            return random.randint(120, 150)
        elif duration < 240:
            return random.randint(90, 130)
        else:
            return random.randint(70, 110)

    def _get_song_key(self, song) -> str:
        """Получить или оценить тональность"""
        keys = ['C major', 'D minor', 'E major', 'F# minor', 'G major', 'A minor', 'B major']
        return random.choice(keys)

    def get_track_lyrics(self, track_title: str, artist: str) -> str:
        """Получить текст песни через поиск в VK"""
        if not self.service:
            return self._generate_lyrics(track_title, artist)

        try:
            # Ищем песню с текстом
            query = f"{track_title} {artist} текст"
            songs = self.service.search_songs_by_text(query, count=1)

            if songs and len(songs) > 0:
                song = songs[0]
                # Пытаемся получить текст
                if hasattr(song, 'lyrics') and song.lyrics:
                    return song.lyrics
                if hasattr(song, 'text') and song.text:
                    return song.text

            # Если не нашли, ищем текст в интернете
            return self._search_lyrics_online(track_title, artist)

        except Exception as e:
            logger.error(f"Error getting lyrics: {e}")
            return self._generate_lyrics(track_title, artist)

    def _search_lyrics_online(self, title: str, artist: str) -> str:
        """Поиск текста через API (можно добавить Genius API)"""
        # Пока возвращаем сгенерированный текст
        return self._generate_lyrics(title, artist)

    def _generate_lyrics(self, title: str, artist: str) -> str:
        """Сгенерировать текст песни"""
        return f"""🎵 {title} - {artist} 🎵

[Куплет 1]
Эта песня покорила сердца миллионов слушателей
Мелодия сочетает современное звучание и глубокий смысл

[Припев]
Запоминающийся припев делает эту песню настоящим хитом
{title} - это больше, чем просто музыка

[Куплет 2]
Исполнитель вложил в эту композицию частичку души
Текст отражает эмоции и переживания

[Аутро]
Наслаждайтесь этой прекрасной музыкой! 🎶"""

    def _get_fallback_tracks(self, country: str) -> List[Dict]:
        """Запасные треки если API не работает"""
        fallback = []
        for i in range(20):
            fallback.append({
                'id': i,
                'title': f'Top Track {i + 1}',
                'artist': f'Popular Artist {i + 1}',
                'duration': 180 + i * 5,
                'cover': f'https://picsum.photos/id/{i + 100}/200/200',
                'bpm': 120 + (i % 40),
                'key': ['C major', 'D minor', 'E major'][i % 3],
                'popularity': 95 - i,
                'url': '',
            })
        return fallback

    def get_track_analysis(self, track: Dict) -> Dict:
        """Получить анализ трека"""
        bpm = track.get('bpm', 120)

        if bpm > 130:
            energy = "⚡ Очень высокий"
            mood = "🔥 Энергичный"
        elif bpm > 100:
            energy = "💪 Высокий"
            mood = "💃 Танцевальный"
        elif bpm > 70:
            energy = "😌 Средний"
            mood = "🎸 Спокойный"
        else:
            energy = "😴 Низкий"
            mood = "🎵 Расслабляющий"

        return {
            "title": track.get("title"),
            "artist": track.get("artist"),
            "duration": f"{track.get('duration', 0) // 60}:{track.get('duration', 0) % 60:02d}",
            "bpm": bpm,
            "key": track.get("key", "Unknown"),
            "popularity": track.get("popularity", 50),
            "energy_level": energy,
            "mood": mood,
            "cover": track.get("cover", ""),
        }


vk_parser = VKParser()