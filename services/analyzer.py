"""
Модуль мультимодального анализа брифа.
Использует OpenRouter для вызова модели Gemini Flash,
которая умеет читать картинки и текст одновременно.
"""
import re
import time
import logging
from openai import OpenAI, RateLimitError
from config import OPENROUTER_API_KEY, LLM_MODEL, SYSTEM_PROMPT
import utils   # наши вспомогательные функции
from logger import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

# Создаём клиент, указывая базовый URL OpenRouter и наш ключ.
# OpenRouter предоставляет API, совместимый с OpenAI, поэтому используем OpenAI-клиент.
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

MAX_RETRIES = 3          # сколько раз пробовать при rate-limit
RETRY_DELAY = 5          # начальная задержка в секундах (будет расти)


def analyze_brief(brief_text: str, image_path: str) -> dict:
    """
        Главная функция анализа.
            - brief_text — текст, расшифрованный из голосового сообщения.
            - image_path — путь к фотографии схемы.
        Возвращает словарь с ключами:
          - "report" — текст аналитического отчёта,
          - "diagram_prompt" — описание для генерации картинки.
        Логирует факт запроса и основные параметры.
    """
    logger.debug(f"Подготовка запроса к OpenRouter. Длина текста брифа: {len(brief_text)}, изображение: {image_path}")

    # Кодируем изображение в base64 (строка, которую понимает модель)
    img_b64 = utils.encode_file_to_base64(image_path)
    logger.debug("Изображение закодировано в base64")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    # Системное сообщение задаёт поведение всей беседы
                    {"role": "system", "content": SYSTEM_PROMPT},
                    # Пользовательское сообщение содержит текст и картинку
                    {"role": "user", "content": [
                        # Текстовая часть
                        {"type": "text", "text": brief_text},
                        # Изображение в формате data URI (base64)
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]}
                ],
                extra_body={"reasoning": {"enabled": True}},
                temperature=0.2, # низкая температура — ответ более предсказуемый и точный
                max_tokens=2000  # ограничиваем длину ответа
            )

            # Получаем текст ответа
            full_response = response.choices[0].message.content
            logger.info(f"Ответ от OpenRouter получен, длина: {len(full_response)} символов")


            # Теперь отделим текст отчёта от описания картинки и кода Mermaid.
            # В ответе есть специальные секции для них.
            # Мы вырежем их, чтобы не показывать пользователю, а использовать отдельно.
            # Ищем mermaid‑код: он начинается со слова "graph" и типа графа (TD, LR и т.д.)
            mermaid_match = re.search(r'\b(graph\s+[A-Z]{2}[^\n]*)', full_response, re.IGNORECASE)
            if mermaid_match:
                # Берём всё, начиная с graph и до конца ответа (это код диаграммы)
                mermaid_code = full_response[mermaid_match.start():].strip()
                # Удаляем возможный остаток markdown-обёртки, если он есть
                mermaid_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
                before_mermaid = full_response[:mermaid_match.start()].strip()
            else:
                mermaid_code = ""
                before_mermaid = full_response

            # Теперь в before_mermaid ищем описание логотипа по маркеру
            logo_marker = "**Описание логотипа для системы:**"
            if logo_marker in before_mermaid:
                parts = before_mermaid.split(logo_marker, 1)
                text_report = parts[0].strip()
                logo_prompt = parts[1].strip()
            else:
                text_report = before_mermaid
                logo_prompt = ""

            logger.debug(f"Логотип: {logo_prompt[:80] if logo_prompt else 'нет'}")
            logger.debug(f"Mermaid: {mermaid_code[:80] if mermaid_code else 'нет'}")

            return {
                "report": text_report,
                "logo_prompt": logo_prompt,
                "mermaid_code": mermaid_code
            }

        except RateLimitError as e:
            logger.warning(f"Rate limit (попытка {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                logger.info(f"Ожидание {wait} секунд перед повтором...")
                time.sleep(wait)
            else:
                logger.error("Исчерпаны попытки из-за rate-limit")
                raise
        except Exception as e:
            logger.exception("Неожиданная ошибка при запросе к OpenRouter")
            raise