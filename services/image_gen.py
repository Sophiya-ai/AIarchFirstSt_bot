"""
Модуль для генерации диаграммы архитектуры.
Использует бесплатный сервис Pollinations.ai без ключа.
"""
import logging
import requests
from config import IMAGE_GEN_URL
from logger import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

def generate_architecture_image(prompt: str) -> bytes:
    """
    Принимает описание на английском языке (промпт).
    Отправляет запрос к Pollinations.ai и возвращает байты готовой картинки.
    """
    logger.debug(f"Запрос к Pollinations.ai с промптом: {prompt[:80]}...")

    if not prompt:
        logger.warning("Пустой промпт для генерации")
        raise ValueError("Пустое описание для генерации.")  # без промпта нет смысла

        # URL-кодируем текст, чтобы его можно было вставить в URL
    # (например, пробелы превращаются в %20)
    encoded_prompt = requests.utils.quote(prompt)

    # Параметры: flux-модель, фиксированный seed для одинакового качества,
    # размер 1024x768 (как слайд), без логотипа
    params = {
        "model": "turbo",
        "width": 1024,
        "height": 768,
        "seed": 12345,  # любое число, чтобы стиль был стабильным
        "nologo": "true"
    }
    # Собираем URL вручную, чтобы надёжно передать параметры
    param_str = "&".join(f"{k}={v}" for k, v in params.items())


    # Формируем полный URL: базовый адрес + закодированный промпт + параметры
    # model=flux — модель, которая лучше рисует схемы и текст
    # nologo=true — убирает водяной знак Pollinations (если есть)
    url = f"{IMAGE_GEN_URL}{encoded_prompt}?{param_str}"
    logger.debug(f"URL генерации: {url}")

    try:
        # Выполняем GET-запрос и сразу получаем бинарные данные картинки
        response = requests.get(url, timeout=60)  # 30 секунд — максимальное время ожидания
        response.raise_for_status()              # если сервер вернул ошибку (4xx,5xx), вылетит исключение
        logger.info(f"Изображение успешно загружено, размер: {len(response.content)} байт")
        return response.content  # возвращаем байты изображения
    except requests.exceptions.RequestException as e:
        logger.exception(f"Ошибка при обращении к Pollinations.ai: {str(e)}")
        raise