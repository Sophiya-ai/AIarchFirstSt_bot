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

            # Теперь отделим текст отчёта от описания картинки.
            # В ответе есть специальная секция «Описание диаграммы архитектуры...».
            # Мы вырежем её, чтобы не показывать пользователю, а использовать отдельно.
            lines = full_response.split("\n")
            text_report = []
            diagram_desc = ""
            capture = False  # флаг, который говорит, что мы сейчас читаем описание диаграммы
            for line in lines:
                if line.strip().startswith("**Описание диаграммы архитектуры"):
                    capture = True # началась секция с описанием
                    continue       # эту строку (заголовок) пропускаем
                if capture:
                    diagram_desc += line.strip() + " " # собираем все строки описания в одну
                else:
                    text_report.append(line)

            # Убираем возможные остатки маркера из текста (если он оказался не на отдельной строке)
            report = "\n".join(text_report).replace("**Описание диаграммы архитектуры для генерации изображения:**", "").strip()
            diagram_desc = diagram_desc.strip()
            logger.debug(f"Извлечено описание диаграммы: {diagram_desc[:80]}...")

            return {
                "report": report,                           # чистый текст для пользователя
                "diagram_prompt": diagram_desc.strip()      # промпт для генератора картинок
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