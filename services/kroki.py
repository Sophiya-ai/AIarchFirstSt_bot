"""
Генерация диаграмм через Kroki или Mermaid Ink (бесплатно, без ключа).
Сначала пробует Kroki, при ошибке — Mermaid Ink.
"""
import requests
import base64
import zlib
import logging
import time
from logger import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

KROKI_URL = "https://kroki.io/mermaid/png"
MERMAID_INK_URL = "https://mermaid.ink/img/"

def _clean_mermaid(code: str) -> str:
    """Удаляет markdown-обёртки и посторонние строки, оставляя чистый код."""
    # Убираем возможные ```mermaid ... ```
    code = code.strip()
    if code.startswith("```"):
        # Находим первый перенос строки и последний ```
        lines = code.splitlines()
        if len(lines) > 1:
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    # Убираем неразрывные пробелы и табуляции
    code = code.replace("\u00A0", " ")
    return code

def _encode_mermaid_ink(code: str) -> str:
    """Кодирует код Mermaid для Mermaid Ink."""
    compressed = zlib.compress(code.encode("utf-8"), 9)
    encoded = base64.urlsafe_b64encode(compressed).decode("utf-8")
    return encoded

def generate_diagram(mermaid_code: str) -> bytes:
    raw_code = mermaid_code
    clean_code = _clean_mermaid(raw_code)
    logger.debug(f"Очищенный Mermaid-код:\n{clean_code}")

    if not clean_code.strip():
        raise ValueError("Пустой код Mermaid после очистки")

    # ---------- Попытка 1: Kroki (POST) ----------
    for attempt in range(1, 4):
        try:
            logger.debug(f"Kroki попытка {attempt}")
            resp = requests.post(
                KROKI_URL,
                data=clean_code.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                timeout=45  # увеличенный таймаут
            )
            resp.raise_for_status()
            logger.info(f"Диаграмма получена через Kroki, размер: {len(resp.content)} байт")
            return resp.content
        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут Kroki (попытка {attempt})")
        except Exception as e:
            logger.warning(f"Ошибка Kroki: {e}")
        time.sleep(2)

    # ---------- Попытка 2: Mermaid Ink (GET) ----------
    logger.debug("Пробуем Mermaid Ink")
    encoded = _encode_mermaid_ink(clean_code)
    url = f"{MERMAID_INK_URL}{encoded}"
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, timeout=45)
            resp.raise_for_status()
            logger.info(f"Диаграмма получена через Mermaid Ink, размер: {len(resp.content)} байт")
            return resp.content
        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут Mermaid Ink (попытка {attempt})")
        except Exception as e:
            logger.error(f"Ошибка Mermaid Ink: {e}")
        time.sleep(2)

    raise RuntimeError("Не удалось сгенерировать диаграмму ни через Kroki, ни через Mermaid Ink")