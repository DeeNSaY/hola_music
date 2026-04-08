import os
import logging
from typing import List, Dict, Any
from yandex_music import Client
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YandexParser:
    def __init__(self):
        self.token = os.getenv('YANDEX_TOKEN')
        self.client = None
        self.init_client()

    def init_client(self):
        """Инициализация клиента Яндекс Музыки"""
        try:
            if self.token:
                # Правильный способ авторизации через токен
                # В библиотеке yandex-music токен передаётся напрямую в конструктор Client
                self.client = Client(self.token).init()
                logger.info("✅ Yandex Music client initialized with token")
            else:
                logger.error("❌ YANDEX_TOKEN not found in environment")
                # Пробуем без токена (ограниченный доступ)
                try:
                    self.client = Client().init()
                    logger.warning("⚠️ Yandex client initialized without token (limited access)")
                except Exception as e:
                    logger.error(f"❌ Cannot initialize Yandex client: {e}")
        except Exception as e:
            logger.error(f"❌ Error initializing Yandex client: {e}")

    def get_chart_tracks(self, limit: int = 20) -> List[Dict]:
        """Получить треки из главного чарта Яндекс Музыки"""
        if not self.client:
            logger.error("❌ Yandex client not available")
            return self._get_fallback_tracks()

        try:
            # Правильный метод: chart() а не get_chart()
            chart = self.client.chart()
            if not chart or not hasattr(chart, 'chart') or not chart.chart:
                logger.warning("No chart data, using fallback")
                return self._get_fallback_tracks()

            tracks_data = []
            for idx, item in enumerate(chart.chart.tracks[:limit]):
                track = item.track
                if track:
                    track_info = self._parse_track(track, idx)
                    if track_info:
                        tracks_data.append(track_info)

            logger.info(f"✅ Got {len(tracks_data)} tracks from Yandex chart")
            return tracks_data if tracks_data else self._get_fallback_tracks()

        except Exception as e:
            logger.error(f"❌ Error getting chart: {e}")
            return self._get_fallback_tracks()
    def _parse_track(self, track, index: int) -> Dict:
        """Извлечь всю информацию о треке"""
        try:
            title = getattr(track, 'title', 'Unknown')

            # Получаем имя исполнителя
            artists = "Unknown"
            if hasattr(track, 'artists') and track.artists:
                artists = ", ".join([a.name for a in track.artists])

            duration = getattr(track, 'duration_ms', 0) // 1000 if hasattr(track, 'duration_ms') else 0

            # Обложка
            cover = None
            if hasattr(track, 'cover_uri') and track.cover_uri:
                cover = f"https://{track.cover_uri.replace('%%', '200x200')}"
            else:
                cover = "https://music.yandex.ru/blocks/common/default-track-cover.png"

            # Текст песни
            lyrics = self._get_lyrics(track)

            # Генерация BPM и тональности
            track_id = getattr(track, 'id', f"{title}{artists}")
            bpm = self._generate_bpm(track_id, duration)
            key = self._generate_key(track_id)

            return {
                'id': getattr(track, 'id', index),
                'title': title,
                'artist': artists,
                'duration': duration,
                'cover': cover,
                'lyrics': lyrics,
                'bpm': bpm,
                'key': key,
                'popularity': max(50, 100 - index * 2),
            }
        except Exception as e:
            logger.error(f"Error parsing track: {e}")
            return None

    def _get_lyrics(self, track) -> str:
        """Попытка получить текст песни"""
        try:
            # Пробуем получить текст
            if hasattr(track, 'get_lyrics'):
                lyrics_obj = track.get_lyrics()
                if lyrics_obj and hasattr(lyrics_obj, 'text') and lyrics_obj.text:
                    return lyrics_obj.text

            title = getattr(track, 'title', 'Unknown')
            artists = "Unknown"
            if hasattr(track, 'artists') and track.artists:
                artists = ", ".join([a.name for a in track.artists])

            return self._no_lyrics_message(title, artists)
        except Exception as e:
            logger.debug(f"Lyrics not available: {e}")
            title = getattr(track, 'title', 'Unknown')
            artists = "Unknown"
            if hasattr(track, 'artists') and track.artists:
                artists = ", ".join([a.name for a in track.artists])
            return self._no_lyrics_message(title, artists)

    def _no_lyrics_message(self, title: str, artist: str) -> str:
        return f"""🎵 {title} - {artist} 🎵

📝 Информация о треке:
• Исполнитель: {artist}
• Название: {title}

К сожалению, текст этой песни временно недоступен.

💡 Вы можете:
• Спросить Hola AI о смысле и популярности этой песни
• Найти текст на официальных сайтах

🎯 Примеры вопросов для Hola AI:
• "Почему песня {title} стала популярной?"
• "Какой музыкальный стиль у {artist}?" 
• "Проанализируй этот трек по BPM и тональности"
"""

    def _generate_bpm(self, track_id, duration: int) -> int:
        """Генерирует детерминированный BPM"""
        hash_val = int(hashlib.md5(str(track_id).encode()).hexdigest()[:4], 16)
        if duration < 180:
            base = 120
        elif duration < 240:
            base = 100
        else:
            base = 80
        return base + (hash_val % 40)

    def _generate_key(self, track_id) -> str:
        """Детерминированная тональность"""
        keys = ['C major', 'G major', 'D major', 'A major', 'E major',
                'F major', 'A minor', 'E minor', 'D minor', 'B minor',
                'F# minor', 'C# minor', 'B major', 'C minor']
        hash_val = int(hashlib.md5(str(track_id).encode()).hexdigest()[:4], 16)
        return keys[hash_val % len(keys)]

    def _get_fallback_tracks(self) -> List[Dict]:
        """Запасные треки"""
        fallback = [
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
        for i, t in enumerate(fallback[:10]):
            tracks.append({
                'id': i,
                'title': t['title'],
                'artist': t['artist'],
                'duration': t['duration'],
                'cover': f"https://picsum.photos/id/{i + 10}/200/200",
                'lyrics': self._no_lyrics_message(t['title'], t['artist']),
                'bpm': t['bpm'],
                'key': t['key'],
                'popularity': 90 - i,
            })
        return tracks

    def get_track_analysis(self, track: Dict) -> Dict:
        """Анализ трека"""
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


# Глобальный экземпляр
yandex_parser = YandexParser()