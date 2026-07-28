"""
Модуль для распознавания речи (Speech-to-Text, STT) через Groq API.
"""

from groq import Groq
from config import GROQ_API_KEY, STT_MODEL

# Создаём клиент Groq и передаём ему ключ доступа
client = Groq(api_key=GROQ_API_KEY)

def transcribe_audio(file_path: str) -> str:
    """
    Принимает путь к аудиофайлу (ogg, mp3, wav),
    отправляет его в Groq Whisper и возвращает распознанный текст.
    Гарантирует, что на выходе всегда будет строка, даже если библиотека
    вернёт объект Transcription.
    """
    with open(file_path, "rb") as audio:
        result = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=(file_path, audio.read()),   # передаём файл (имя, байты)
            language="ru",
            response_format="text"          # API возвращает просто текст, но типы могут «думать» иначе
        )

    # Обработка типа результата:
    # — если уже строка (что верно для response_format="text"), используем её;
    # — если по какой-то причине объект (например, при обновлении SDK), берём поле .text.
    if isinstance(result, str):
        return result
    return result.text