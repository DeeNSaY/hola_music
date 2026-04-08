import os
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class MusicRAGSystem:
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')

    def build_tracks_context(self, tracks: list, limit: int = 10) -> str:
        """Создать контекст из треков для AI"""
        context = "🎵 АКТУАЛЬНЫЙ ЧАРТ ЯНДЕКС МУЗЫКИ (Топ-10):\n\n"
        for i, track in enumerate(tracks[:limit], 1):
            context += f"{i}. {track.get('title')} - {track.get('artist')}\n"
            context += f"   • BPM: {track.get('bpm', 'N/A')}\n"
            context += f"   • Тональность: {track.get('key', 'N/A')}\n"
            context += f"   • Популярность: {track.get('popularity', 'N/A')}/100\n"
            context += f"   • Длительность: {track.get('duration', 0) // 60}:{track.get('duration', 0) % 60:02d}\n"
            if track.get('lyrics') and len(track.get('lyrics')) > 50:
                context += f"   • Текст (начало): {track.get('lyrics')[:200]}...\n"
            context += "\n"
        return context

    def build_full_track_context(self, track: dict) -> str:
        """Создать полный контекст для одного трека"""
        context = f"""🎵 ИНФОРМАЦИЯ О ТРЕКЕ:
    Название: {track.get('title', 'Unknown')}
    Исполнитель: {track.get('artist', 'Unknown')}
    Длительность: {track.get('duration', 0) // 60}:{track.get('duration', 0) % 60:02d}
    BPM: {track.get('bpm', 'N/A')}
    Тональность: {track.get('key', 'N/A')}
    Популярность: {track.get('popularity', 'N/A')}/100
    """
        if track.get('album'):
            context += f"Альбом: {track.get('album')}\n"
        if track.get('year'):
            context += f"Год выпуска: {track.get('year')}\n"
        if track.get('genre'):
            context += f"Жанр: {track.get('genre')}\n"

        context += f"""
    📝 ТЕКСТ ПЕСНИ:
    {track.get('lyrics', 'Текст не найден')[:1000]}

    💡 На основе этих данных ты можешь анализировать трек.
    """
        return context

    def get_ai_response(self, messages: list, tracks_context: str = None, track_context: str = None) -> str:
        """Получить ответ от DeepSeek с RAG контекстом"""
        if not self.api_key:
            return "⚠️ API ключ DeepSeek не настроен."

        # Формируем system prompt с контекстом
        system_prompt = """Ты - Hola AI, эксперт по музыке. Отвечай кратко, по делу, используй эмодзи.

Твои возможности:
- Анализировать почему треки стали популярными
- Объяснять BPM, тональность простым языком
- Сравнивать треки и давать рекомендации

Правила ответов:
- Отвечай на русском
- Будь дружелюбным, но лаконичным (2-4 предложения на основной ответ)
- Используй эмодзи для эмоций
- Если не знаешь - честно скажи
"""

        if tracks_context:
            system_prompt += f"\n\n📊 КОНТЕКСТ ЧАРТА:\n{tracks_context}"
        if track_context:
            system_prompt += f"\n\n📀 КОНТЕКСТ ТРЕКА:\n{track_context}"

        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages[-5:])  # последние 5 сообщений

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": "deepseek-chat",
            "messages": full_messages,
            "temperature": 0.7,
            "max_tokens": 500,  # Ограничиваем для краткости
            "stream": False
        }

        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"AI error: {e}")
            return f"❌ Ошибка: {str(e)[:100]}"


ai_system = MusicRAGSystem()