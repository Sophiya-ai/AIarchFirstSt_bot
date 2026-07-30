"""
Генерация диаграмм через Kroki API (бесплатно, без ключа).
"""
import requests
import logging
from logger import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)
KROKI_URL = "https://kroki.io/mermaid/png"

def generate_diagram(mermaid_code: str) -> bytes:
    if not mermaid_code.strip():
        raise ValueError("Пустой код Mermaid")
    logger.debug(f"Отправка Mermaid в Kroki, длина: {len(mermaid_code)}")
    response = requests.post(
        KROKI_URL,
        data=mermaid_code.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        timeout=30
    )
    response.raise_for_status()
    logger.info(f"Диаграмма получена от Kroki, размер: {len(response.content)} байт")
    return response.content