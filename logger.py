"""
Настройка логирования для всего проекта.
Логи пишутся одновременно в консоль и в файл bot.log.
Уровень логирования можно менять в переменной LOG_LEVEL.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

# Имя логгера, которое будем использовать во всех модулях
LOGGER_NAME = "spra_bot"

# Уровень логирования: DEBUG — самые подробные записи, INFO — основные события
LOG_LEVEL = logging.DEBUG

# Формат сообщений: [время] [уровень] [модуль] сообщение
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger():
    """
    Создаёт и настраивает логгер. Вызывается один раз при запуске бота.
    Возвращает настроенный объект логгера.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(LOG_LEVEL)

    # Чтобы не добавлять обработчики повторно при перезапуске (например, в интерактивном режиме)
    if logger.handlers:
        return logger

    # Форматтер, общий для всех обработчиков
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Обработчик для вывода в консоль (стандартный поток ошибок)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)          # В консоль только INFO и выше
    console_handler.setFormatter(formatter)

    # Обработчик для записи в файл с ротацией (максимум 5 МБ, храним 3 старых файла)
    file_handler = RotatingFileHandler(
        "bot.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)            # В файл пишем всё, включая DEBUG
    file_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger