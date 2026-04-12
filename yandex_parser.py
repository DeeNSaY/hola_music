import os
import logging
import hashlib
from typing import List, Dict, Any, Optional
from yandex_music import Client, Track, TrackShort
from models import db, ChartCache, TrackCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YandexParser:
    def __init__(self, app=None):
        self.token = os.getenv('YANDEX_TOKEN')
        self.client: Optional[Client] = None
        self.app = app
        self.init_client()

    def init_client(self) -> None:
        """Инициализация клиента Яндекс.Музыки"""
        try:
            if self.token:
                self.client = Client(self.token).init()
                logger.info("✅ Yandex Music client initialized")
            else:
                logger.error("❌ YANDEX_TOKEN not found in environment")
        except Exception as e:
            logger.error(f"❌ Yandex init error: {e}")

    def get_chart_tracks(self, limit: int = 20, force_refresh: bool = False) -> List[Dict]:
        """Получить чарт из кеша БД или из API."""
        if not force_refresh:
            cached = ChartCache.query.first()
            if cached and cached.tracks_data:
                logger.info("✅ Returning chart from database cache")
                return cached.tracks_data[:limit]

        if not self.client:
            logger.error("❌ Yandex client not available")
            return self._get_fallback_tracks()

        try:
            chart = self.client.chart()
            if not chart or not chart.chart:
                return self._get_fallback_tracks()

            tracks_data = []
            for idx, item in enumerate(chart.chart.tracks[:limit]):
                track_short = item.track
                if track_short:
                    track_info = self._get_track_from_cache_or_api(track_short, idx)
                    if track_info:
                        tracks_data.append(track_info)

            self._save_chart_to_db(tracks_data)
            logger.info(f"✅ Got {len(tracks_data)} tracks from Yandex chart")
            return tracks_data

        except Exception as e:
            logger.error(f"❌ Error getting chart: {e}")
            return self._get_fallback_tracks()

    def _get_track_from_cache_or_api(self, track_short: TrackShort, index: int) -> Optional[Dict]:
        """Получить трек: сначала из кеша БД, потом из API."""
        track_id = str(getattr(track_short, 'id', f"temp_{index}"))

        cached_track = TrackCache.query.filter_by(track_id=track_id).first()
        if cached_track:
            logger.debug(f"Track {track_id} found in cache")
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
                'album': cached_track.album,
                'year': cached_track.year,
                'genre': cached_track.genre,
                'explicit': cached_track.explicit,
                'available': cached_track.available,
            }

        try:
            full_track = self.client.tracks([track_id])[0]
            track_info = self._parse_track_full(full_track, index)
            if track_info:
                self._save_track_to_db(track_info)
            return track_info
        except Exception as e:
            logger.error(f"Failed to fetch full track {track_id}: {e}")
            return self._parse_track_short_fallback(track_short, index)

    def _parse_track_full(self, track: Track, index: int) -> Optional[Dict]:
        """Парсинг ПОЛНОГО объекта Track."""
        try:
            track_id = str(track.id)
            title = track.title or 'Unknown'

            artists = "Unknown"
            if track.artists:
                artists = ", ".join([a.name for a in track.artists])

            duration = track.duration_ms // 1000 if track.duration_ms else 0

            cover = None
            if track.cover_uri:
                cover = f"https://{track.cover_uri.replace('%%', '400x400')}"
            else:
                cover = "https://music.yandex.ru/blocks/common/default-track-cover.png"

            lyrics = self._get_lyrics_full(track)

            album_name = None
            year = None
            genre = None
            if track.albums:
                album = track.albums[0]
                album_name = album.title
                year = album.year
                genre = album.genre

            explicit = getattr(track, 'explicit', False)
            available = getattr(track, 'available', True)

            bpm = self._generate_bpm(track_id, duration)
            key = self._generate_key(track_id)

            logger.info(f"Parsed track: {title} | album: {album_name} | year: {year} | genre: {genre}")

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
                'album': album_name,
                'year': year,
                'genre': genre,
                'explicit': explicit,
                'available': available,
            }
        except Exception as e:
            logger.error(f"Error parsing full track: {e}")
            return None

    def _parse_track_short_fallback(self, track_short: TrackShort, index: int) -> Dict:
        track_id = str(getattr(track_short, 'id', f"temp_{index}"))
        title = getattr(track_short, 'title', 'Unknown')
        artists = "Unknown"
        if hasattr(track_short, 'artists') and track_short.artists:
            artists = ", ".join([a.name for a in track_short.artists])
        duration = 0

        return {
            'id': track_id,
            'title': title,
            'artist': artists,
            'duration': duration,
            'cover': "https://music.yandex.ru/blocks/common/default-track-cover.png",
            'lyrics': self._no_lyrics_message(title, artists),
            'bpm': self._generate_bpm(track_id, duration),
            'key': self._generate_key(track_id),
            'popularity': max(50, 100 - index * 2),
            'album': None,
            'year': None,
            'genre': None,
            'explicit': False,
            'available': True,
        }

    def _get_lyrics_full(self, track: Track) -> str:
        try:
            lyrics_obj = track.get_lyrics()
            if lyrics_obj:
                if hasattr(lyrics_obj, 'fetch_lyrics'):
                    text = lyrics_obj.fetch_lyrics()
                    if text:
                        return text
                elif hasattr(lyrics_obj, 'text') and lyrics_obj.text:
                    return lyrics_obj.text
            return self._no_lyrics_message(track.title, track.artists[0].name if track.artists else 'Unknown')
        except Exception as e:
            logger.debug(f"Lyrics not available for {track.title}: {e}")
            return self._no_lyrics_message(track.title, track.artists[0].name if track.artists else 'Unknown')

    def _save_chart_to_db(self, tracks: List[Dict]) -> None:
        try:
            with self.app.app_context() if self.app else db.session.no_autoflush:
                ChartCache.query.delete()
                new_cache = ChartCache(tracks_data=tracks)
                db.session.add(new_cache)
                db.session.commit()
                logger.info("✅ Chart saved to database")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving chart to DB: {e}")

    def _save_track_to_db(self, track_info: Dict) -> None:
        try:
            with self.app.app_context() if self.app else db.session.no_autoflush:
                existing = TrackCache.query.filter_by(track_id=track_info['id']).first()
                if existing:
                    for key, value in track_info.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    track_cache = TrackCache(
                        track_id=track_info.get('id'),
                        title=track_info.get('title', 'Unknown'),
                        artist=track_info.get('artist', 'Unknown'),
                        duration=track_info.get('duration', 0),
                        cover=track_info.get('cover'),
                        lyrics=track_info.get('lyrics'),
                        bpm=track_info.get('bpm'),
                        key=track_info.get('key'),
                        popularity=track_info.get('popularity', 50),
                        album=track_info.get('album'),
                        year=track_info.get('year'),
                        genre=track_info.get('genre'),
                        explicit=track_info.get('explicit', False),
                        available=track_info.get('available', True),
                    )
                    db.session.add(track_cache)
                db.session.commit()
                logger.debug(f"✅ Track {track_info.get('title')} saved to DB")
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

    def _generate_bpm(self, track_id: str, duration: int) -> int:
        hash_val = int(hashlib.md5(str(track_id).encode()).hexdigest()[:4], 16)
        if duration < 180:
            base = 120
        elif duration < 240:
            base = 100
        else:
            base = 80
        return base + (hash_val % 40)

    def _generate_key(self, track_id: str) -> str:
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
                'id': f"fallback_{i}",
                'title': t['title'],
                'artist': t['artist'],
                'duration': t['duration'],
                'cover': f"https://picsum.photos/id/{i + 10}/200/200",
                'lyrics': self._no_lyrics_message(t['title'], t['artist']),
                'bpm': t['bpm'],
                'key': t['key'],
                'popularity': 90 - i,
                'album': None,
                'year': None,
                'genre': None,
                'explicit': False,
                'available': True,
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

        duration_sec = track.get('duration', 0)
        minutes = duration_sec // 60
        seconds = duration_sec % 60

        return {
            "title": track.get("title"),
            "artist": track.get("artist"),
            "duration": f"{minutes}:{seconds:02d}",
            "bpm": bpm,
            "key": track.get("key", "Unknown"),
            "cover": track.get("cover"),
            "energy_level": energy,
            "mood": mood,
            "popularity": track.get("popularity", 80),
            "album": track.get("album"),
            "year": track.get("year"),
            "genre": track.get("genre"),
            "explicit": track.get("explicit", False),
        }


yandex_parser = YandexParser()