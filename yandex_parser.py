import os
import logging
import hashlib
from typing import List, Dict, Any
from yandex_music import Client
from models import db, ChartCache, TrackCache
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YandexParser:
    def __init__(self, app=None):
        self.token = os.getenv('YANDEX_TOKEN')
        self.client = None
        self.app = app
        self.init_client()

    def init_client(self):
        try:
            if self.token:
                self.client = Client(self.token).init()
                logger.info("✅ Yandex Music client initialized")
            else:
                logger.error("❌ YANDEX_TOKEN not found")
        except Exception as e:
            logger.error(f"❌ Yandex init error: {e}")

    def get_chart_tracks(self, limit: int = 20, force_refresh: bool = False) -> List[Dict]:
        """Получить чарт из кеша БД или из API"""
        # 1. Пытаемся взять из кеша БД
        if not force_refresh:
            cached = ChartCache.query.first()
            if cached and cached.tracks_data:
                logger.info("✅ Returning chart from database cache")
                return cached.tracks_data[:limit]

        # 2. Если кеша нет или force_refresh=True - идём в API
        if not self.client:
            logger.error("❌ Yandex client not available")
            return self._get_fallback_tracks()

        try:
            chart = self.client.chart()
            if not chart or not chart.chart:
                return self._get_fallback_tracks()

            tracks_data = []
            for idx, item in enumerate(chart.chart.tracks[:limit]):
                track = item.track
                if track:
                    # Пытаемся взять трек из кеша треков
                    track_info = self._get_track_from_cache_or_api(track, idx)
                    if track_info:
                        tracks_data.append(track_info)

            # 3. Сохраняем чарт в БД
            self._save_chart_to_db(tracks_data)

            logger.info(f"✅ Got {len(tracks_data)} tracks from Yandex chart")
            return tracks_data

        except Exception as e:
            logger.error(f"❌ Error getting chart: {e}")
            return self._get_fallback_tracks()

    def _get_track_from_cache_or_api(self, track, index: int) -> Dict:
        """Получить трек: сначала из кеша БД, потом из API"""
        track_id = str(getattr(track, 'id', f"temp_{index}"))

        # Проверяем кеш треков
        cached_track = TrackCache.query.filter_by(track_id=track_id).first()
        if cached_track:
            return {
                'id': cached_track.track_id,
                'title': cached_track.title,
                'artist': cached_track.artist,
                'duration': cached_track.duration,
                'cover': cached_track.cover,
                'lyrics': cached_track.lyrics,
                'bpm': cached_track.bpm,
                'key': cached_track.key,
                'popularity': cached_track.popularity,
            }

        # Нет в кеше - получаем из API
        track_info = self._parse_track_full(track, index)
        if track_info:
            self._save_track_to_db(track_info)
        return track_info

    def _parse_track_full(self, track, index: int) -> Dict:
        """Полная информация о треке (включая текст)"""
        try:
            track_id = str(getattr(track, 'id', f"temp_{index}"))
            title = getattr(track, 'title', 'Unknown')

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

            # ТЕКСТ ПЕСНИ - получаем через API
            lyrics = self._get_lyrics_full(track)

            # Генерация BPM и тональности (Yandex не даёт)
            bpm = self._generate_bpm(track_id, duration)
            key = self._generate_key(track_id)

            return {
                'id': track_id,
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

    def _get_lyrics_full(self, track) -> str:
        """Получение текста песни через Yandex API"""
        try:
            # Пробуем получить текст
            if hasattr(track, 'get_lyrics'):
                lyrics_obj = track.get_lyrics()
                if lyrics_obj and hasattr(lyrics_obj, 'text') and lyrics_obj.text:
                    return lyrics_obj.text

            # Если нет - возвращаем сообщение
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

    def _save_chart_to_db(self, tracks: List[Dict]):
        """Сохранить чарт в базу данных"""
        try:
            # Удаляем старый кеш
            ChartCache.query.delete()
            # Сохраняем новый
            new_cache = ChartCache(tracks_data=tracks)
            db.session.add(new_cache)
            db.session.commit()
            logger.info("✅ Chart saved to database")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving chart to DB: {e}")

    def _save_track_to_db(self, track_info: Dict):
        """Сохранить трек в базу данных"""
        try:
            track_cache = TrackCache(
                track_id=track_info.get('id'),
                title=track_info.get('title', 'Unknown'),
                artist=track_info.get('artist', 'Unknown'),
                duration=track_info.get('duration', 0),
                cover=track_info.get('cover'),
                lyrics=track_info.get('lyrics'),
                bpm=track_info.get('bpm'),
                key=track_info.get('key'),
                popularity=track_info.get('popularity', 50)
            )
            db.session.add(track_cache)
            db.session.commit()
            logger.info(f"✅ Track {track_info.get('title')} saved to database")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving track to DB: {e}")

    def _no_lyrics_message(self, title: str, artist: str) -> str:
        return f"""🎵 {title} - {artist} 🎵

Текст этой песни временно недоступен через Яндекс Музыку.

💡 Спросите Hola AI:
• "Почему песня {title} стала популярной?"
• "Какой стиль у {artist}?" 
• "Проанализируй этот трек"
"""

    def _generate_bpm(self, track_id, duration: int) -> int:
        hash_val = int(hashlib.md5(str(track_id).encode()).hexdigest()[:4], 16)
        if duration < 180:
            base = 120
        elif duration < 240:
            base = 100
        else:
            base = 80
        return base + (hash_val % 40)

    def _generate_key(self, track_id) -> str:
        keys = ['C major', 'G major', 'D major', 'A major', 'E major',
                'F major', 'A minor', 'E minor', 'D minor', 'B minor']
        hash_val = int(hashlib.md5(str(track_id).encode()).hexdigest()[:4], 16)
        return keys[hash_val % len(keys)]

    def _get_fallback_tracks(self) -> List[Dict]:
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
                'cover': f"https://picsum.photos/id/{i + 10}/200/200",
                'lyrics': self._no_lyrics_message(t['title'], t['artist']),
                'bpm': t['bpm'],
                'key': t['key'],
                'popularity': 90 - i,
            })
        return tracks

    def get_track_analysis(self, track: Dict) -> Dict:
        bpm = track.get('bpm', 100)
        if bpm > 120:
            energy = "⚡ Высокая"
            mood = "🔥 Живой"
        elif bpm > 90:
            energy = "💪 Средняя"
            mood = "💃 Оптимистичный"
        else:
            energy = "😌 Низкая"
            mood = "🎵 Спокойный"
        return {
            "title": track.get("title"),
            "artist": track.get("artist"),
            "duration": f"{track.get('duration', 0) // 60}:{track.get('duration', 0) % 60:02d}",
            "bpm": bpm,
            "key": track.get("key", "Unknown"),
            "cover": track.get("cover"),
            "energy_level": energy,
            "mood": mood,
            "popularity": track.get("popularity", 80),
        }


yandex_parser = YandexParser()