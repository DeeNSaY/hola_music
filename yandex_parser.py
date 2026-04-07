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
        """Инициализация клиента Яндекс Музыки по токену"""
        try:
            if self.token:
                self.client = Client.from_token(self.token).init()
                logger.info("✅ Yandex Music client initialized")
            else:
                logger.error("❌ YANDEX_TOKEN not found in environment")
        except Exception as e:
            logger.error(f"❌ Error initializing Yandex client: {e}")

    def get_chart_tracks(self, limit: int = 20) -> List[Dict]:
        """Получить треки из главного чарта Яндекс Музыки"""
        if not self.client:
            logger.error("❌ Yandex client not available")
            return self._get_fallback_tracks()

        try:
            # Получаем чарт (по умолчанию главный)
            chart = self.client.get_chart()
            if not chart or not chart.chart:
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
            return tracks_data

        except Exception as e:
            logger.error(f"❌ Error getting chart: {e}")
            return self._get_fallback_tracks()

    def _parse_track(self, track, index: int) -> Dict:
        """Извлечь всю информацию о треке"""
        try:
            title = track.title
            artists = ", ".join([a.name for a in track.artists]) if track.artists else "Unknown"
            duration = track.duration_ms // 1000 if track.duration_ms else 0

            # Обложка – формируем URL из cover_uri
            cover = None
            if track.cover_uri:
                # Пример: "%%" заменяем на размер (например, 200x200)
                cover = f"https://{track.cover_uri.replace('%%', '200x200')}"
            else:
                cover = "https://music.yandex.ru/blocks/common/default-track-cover.png"

            # Текст песни (если доступен)
            lyrics = self._get_lyrics(track)

            # Генерация BPM и тональности детерминированно (на основе id или названия)
            track_id = track.id or f"{title}{artists}"
            bpm = self._generate_bpm(track_id, duration)
            key = self._generate_key(track_id)

            return {
                'id': track.id,
                'title': title,
                'artist': artists,
                'duration': duration,
                'cover': cover,
                'lyrics': lyrics,
                'bpm': bpm,
                'key': key,
                'popularity': max(50, 100 - index * 2),  # заглушка популярности
            }
        except Exception as e:
            logger.error(f"Error parsing track: {e}")
            return None

    def _get_lyrics(self, track) -> str:
        """Попытка получить текст песни через API Яндекс Музыки"""
        try:
            # У некоторых треков есть текст через get_lyrics()
            lyrics_obj = track.get_lyrics()
            if lyrics_obj and lyrics_obj.text:
                return lyrics_obj.text
            else:
                return self._no_lyrics_message(track.title, ", ".join([a.name for a in track.artists]) if track.artists else "Unknown")
        except Exception as e:
            logger.debug(f"Lyrics not available for {track.title}: {e}")
            return self._no_lyrics_message(track.title, ", ".join([a.name for a in track.artists]) if track.artists else "Unknown")

    def _no_lyrics_message(self, title: str, artist: str) -> str:
        return f"""🎵 {title} - {artist} 🎵

📝 Информация о треке:
• Исполнитель: {artist}
• Название: {title}

К сожалению, текст этой песни временно недоступен через Яндекс Музыку.

💡 Вы можете:
• Спросить Hola AI о смысле и популярности этой песни
• Найти текст на официальных сайтах
• Наслаждаться музыкой!

🎯 Примеры вопросов для Hola AI:
• "Почему песня {title} стала популярной?"
• "Какой музыкальный стиль у {artist}?"
• "Проанализируй этот трек по BPM и тональности"
"""

    def _generate_bpm(self, track_id, duration: int) -> int:
        """Генерирует детерминированный BPM на основе id трека и длительности"""
        # Используем хеш для стабильности
        hash_val = int(hashlib.md5(str(track_id).encode()).hexdigest()[:4], 16)
        # BPM в зависимости от длительности: короткие треки быстрее
        if duration < 180:
            base = 120
        elif duration < 240:
            base = 100
        else:
            base = 80
        bpm = base + (hash_val % 40)  # диапазон ±20
        return bpm

    def _generate_key(self, track_id) -> str:
        """Детерминированная тональность"""
        keys = ['C major', 'G major', 'D major', 'A major', 'E major',
                'F major', 'A minor', 'E minor', 'D minor', 'B minor',
                'F# minor', 'C# minor', 'B major', 'C minor']
        hash_val = int(hashlib.md5(str(track_id).encode()).hexdigest()[:4], 16)
        return keys[hash_val % len(keys)]

    def _get_fallback_tracks(self) -> List[Dict]:
        """Запасные треки на случай недоступности API"""
        fallback = [
            {"title": "Birds of a Feather", "artist": "Billie Eilish", "duration": 210, "bpm": 118, "key": "C major"},
            {"title": "Beautiful Things", "artist": "Benson Boone", "duration": 195, "bpm": 120, "key": "D minor"},
            {"title": "Lose Control", "artist": "Teddy Swims", "duration": 225, "bpm": 85, "key": "E major"},
            {"title": "Espresso", "artist": "Sabrina Carpenter", "duration": 185, "bpm": 128, "key": "C minor"},
            {"title": "Too Sweet", "artist": "Hozier", "duration": 240, "bpm": 92, "key": "A major"},
        ]
        tracks = []
        for i, t in enumerate(fallback):
            tracks.append({
                'id': i,
                'title': t['title'],
                'artist': t['artist'],
                'duration': t['duration'],
                'cover': f"https://picsum.photos/id/{i+10}/200/200",
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