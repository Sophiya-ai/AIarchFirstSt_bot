"""
Модуль для генерации изображения архитектурной диаграммы.
Использует бесплатный сервис Pollinations.ai без ключа.
"""

import requests
from config import IMAGE_GEN_URL

def generate_architecture_image(prompt: str) -> bytes:
    """
    Принимает описание на английском языке (промпт).
    Отправляет запрос к Pollinations.ai и возвращает байты готовой картинки.
    """
    if not prompt:
        raise ValueError("Пустое описание для генерации.")  # без промпта нет смысла

    # URL-кодируем текст, чтобы его можно было вставить в URL
    # (например, пробелы превращаются в %20)
    encoded_prompt = requests.utils.quote(prompt)

    # Формируем полный URL: базовый адрес + закодированный промпт + параметры
    # model=flux — модель, которая лучше рисует схемы и текст
    # nologo=true — убирает водяной знак Pollinations (если есть)
    url = f"{IMAGE_GEN_URL}{encoded_prompt}?model=flux&nologo=true"

    # Выполняем GET-запрос и сразу получаем бинарные данные картинки
    response = requests.get(url, timeout=30)  # 30 секунд — максимальное время ожидания
    response.raise_for_status()              # если сервер вернул ошибку (4xx,5xx), вылетит исключение

    return response.content  # возвращаем байты изображения