import os
import requests
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class MusicRAGSystem:
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')

    def build_playlist_context(self, playlist_info: Dict) -> str:
        """Создать подробный контекст о плейлисте для AI"""
        if not playlist_info:
            return ""

        context = f"""📀 ИНФОРМАЦИЯ О ПЛЕЙЛИСТЕ:
Название: {playlist_info.get('title', 'Unknown')}
Страна: {playlist_info.get('country', 'Unknown')} {playlist_info.get('icon', '')}
Количество треков: {playlist_info.get('total_tracks', 0)}
Источник: {playlist_info.get('source', 'VK Музыка')}

🎵 ТРЕКИ В ПЛЕЙЛИСТЕ (топ-10):
"""

        for i, track in enumerate(playlist_info.get('tracks', [])[:10], 1):
            context += f"""
{i}. {track.get('title', 'Unknown')} - {track.get('artist', 'Unknown')}
   • BPM: {track.get('bpm', 'Unknown')}
   • Тональность: {track.get('key', 'Unknown')}
   • Популярность: {track.get('popularity', 50)}/100
   • Длительность: {track.get('duration', 0)} сек
"""

        return context

    def build_track_context(self, track: Dict, analysis: Dict, lyrics: str) -> str:
        """Создать контекст о конкретном треке"""
        context = f"""🎤 ИНФОРМАЦИЯ О ТРЕКЕ:
Название: {track.get('title', 'Unknown')}
Исполнитель: {track.get('artist', 'Unknown')}
BPM: {analysis.get('bpm', 'Unknown')}
Тональность: {analysis.get('key', 'Unknown')}
Энергия: {analysis.get('energy_level', 'Unknown')}
Настроение: {analysis.get('mood', 'Unknown')}
Популярность: {analysis.get('popularity', 50)}/100

📝 ТЕКСТ ПЕСНИ (фрагмент):
{lyrics[:500]}...

💡 Анализ: {analysis.get('genre_hint', '')}
"""
        return context

    def get_ai_response(self, messages: List[Dict], context: str = None) -> str:
        """Получить ответ от DeepSeek API с RAG контекстом"""
        if not self.api_key:
            return """⚠️ API ключ DeepSeek не настроен. 

Пожалуйста, добавьте DEEPSEEK_API_KEY в файл .env и перезапустите приложение.

Как получить ключ:
1. Зарегистрируйтесь на platform.deepseek.com
2. Перейдите в раздел API Keys
3. Создайте новый ключ и скопируйте его
4. Вставьте в .env файл"""

        system_prompt = """🌟 Ты - Hola AI, дружелюбный эксперт по музыке!

Твоя задача - помогать пользователям понимать музыку глубже. Отвечай на русском языке.

Что ты можешь:
• Анализировать почему треки стали популярными
• Объяснять музыкальные термины (BPM, тональность) простым языком
• Сравнивать треки и давать рекомендации
• Рассказывать о музыкальных трендах разных стран

Как отвечать:
• Используй эмодзи для эмоциональности 🎵🎸🎹
• Будь дружелюбным и понятным
• Приводи конкретные примеры из музыки
• Если не знаешь - честно признайся

Важно: Отвечай как настоящий музыкальный эксперт, который любит свое дело!"""

        if context:
            system_prompt += f"\n\n📊 КОНТЕКСТ ДЛЯ ОТВЕТА:\n{context}\n\nИспользуй этот контекст для ответа пользователю."

        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages[-10:])  # Последние 10 сообщений для контекста

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",
            "messages": full_messages,
            "temperature": 0.8,
            "max_tokens": 1000,
            "stream": False
        }

        try:
            logger.info("Sending request to DeepSeek API...")
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            ai_message = result['choices'][0]['message']['content']
            logger.info("Successfully received response from DeepSeek")
            return ai_message

        except requests.exceptions.Timeout:
            logger.error("DeepSeek API timeout")
            return "⏰ Нейросеть немного задумалась... Попробуйте спросить еще раз через пару секунд!"

        except requests.exceptions.ConnectionError:
            logger.error("Connection error to DeepSeek API")
            return "🔌 Ошибка подключения к AI серверу. Проверьте интернет соединение."

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return f"❌ Техническая ошибка: {str(e)[:100]}\n\nПожалуйста, попробуйте позже."

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"😅 Произошла неожиданная ошибка. Попробуйте переформулировать вопрос."


ai_system = MusicRAGSystem()