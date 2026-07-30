"""
Модуль мультимодального анализа брифа.
Использует OpenRouter для вызова модели Gemini Flash,
которая умеет читать картинки и текст одновременно.
"""
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
            text_report = full_response
            logo_prompt = ""
            mermaid_code = ""

            # Разбиваем по маркеру логотипа
            logo_marker = "**Описание логотипа для системы:**"
            mermaid_marker = "**Диаграмма архитектуры в формате Mermaid:**"

            if logo_marker in text_report:
                parts = text_report.split(logo_marker, 1)
                text_report = parts[0].strip()
                rest = parts[1]
                if mermaid_marker in rest:
                    logo_part, mermaid_part = rest.split(mermaid_marker, 1)
                    logo_prompt = logo_part.strip()
                    mermaid_code = mermaid_part.strip()
                else:
                    logo_prompt = rest.strip()
            elif mermaid_marker in text_report:
                parts = text_report.split(mermaid_marker, 1)
                text_report = parts[0].strip()
                mermaid_code = parts[1].strip()

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