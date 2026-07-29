"""
Точка входа в приложение.
Создаёт и запускает Telegram-бота в диалоговом режиме:
можно отправлять голос и фото по отдельности, в любом порядке.
Если пользователь случайно отправляет оба сразу — корректно обработаем и такой случай.
"""
import json
import logging
# Импортируем нужные классы для создания бота и обработчиков
from telegram.ext import (
    ApplicationBuilder,   # Строитель приложения (основной объект бота)
    CommandHandler,        # Обработчик команд типа /start
    MessageHandler,        # Обработчик обычных сообщений
    filters,                # Фильтры для отбора определённых типов сообщений
    CallbackContext
)
from config import TELEGRAM_TOKEN  # Токен бота из файла .env

# Импортируем наши функции-обработчики из модуля handlers
from handlersTG import (
    start_command,         # Для команды /start
    handle_audio,          # Для голосовых сообщений
    handle_photo,          # Для фото
    combined_handler
)
import utils               # Вспомогательные функции (скачивание файлов)
from logger import setup_logger, LOGGER_NAME   # Импортируем настройки логгера


# Получаем логгер для этого модуля
logger = logging.getLogger(LOGGER_NAME)


async def error_handler(update: object, context: CallbackContext) -> None:
    """
    Глобальный обработчик ошибок.
    Логирует любое необработанное исключение и, если возможно,
    отправляет сообщение пользователю.
    """
    logger.exception("Необработанное исключение при обработке обновления:")
    # Пытаемся извлечь сообщение, чтобы уведомить пользователя
    if update and hasattr(update, 'effective_message') and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Внутренняя ошибка бота. Попробуйте позже или перезапустите сеанс командой /start."
        )


def main():
    """
    Собирает и запускает Telegram-бота.
    """

    # Настраиваем логирование
    setup_logger()

    logger.info("Запуск бота...")

    # Создаём экземпляр приложения и передаём токен.
    # ApplicationBuilder собирает все настройки и создаёт готовое приложение.
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Регистрируем глобальный обработчик ошибок
    app.add_error_handler(error_handler)

    # Регистрируем обработчик команды /start
    app.add_handler(CommandHandler("start", start_command))

    # Обработчик для сообщений, содержащих ТОЛЬКО голосовое (без фото).
    # Фильтр: filters.VOICE & ~filters.PHOTO означает "есть голос И НЕТ фото".
    app.add_handler(MessageHandler(
        (filters.VOICE | filters.AUDIO | filters.Document.AUDIO) & ~filters.PHOTO,
        handle_audio
    ))

    # Обработчик для сообщений, содержащих ТОЛЬКО фото (без голоса).
    app.add_handler(MessageHandler(
        filters.PHOTO & ~(filters.VOICE | filters.AUDIO | filters.Document.AUDIO),
        handle_photo))

    # Обработчик на случай, если в одном сообщении есть и голос, и фото одновременно.
    # Такой фильтр сработает только когда присутствуют оба типа.
    app.add_handler(MessageHandler(
        (filters.VOICE | filters.AUDIO | filters.Document.AUDIO) & filters.PHOTO,
        combined_handler
    ))


    # === ДИАГНОСТИКА: ловим все сообщения, чтобы понять их тип ===
    async def debug_all_messages(update, context):
        msg = update.message
        logger.info(f"ОТЛАДКА: получено сообщение типа: {type(msg).__name__}")
        # Выведем основные атрибуты в лог
        debug_info = {
            "message_id": msg.message_id,
            "from_user": msg.from_user.id if msg.from_user else None,
            "date": msg.date,
            "voice": msg.voice is not None,
            "audio": msg.audio is not None,
            "document": msg.document is not None,
            "photo": msg.photo is not None,
            "text": msg.text if msg.text else None,
        }
        logger.info(f"ОТЛАДКА: детали сообщения: {json.dumps(debug_info, default=str)}")
        # Если есть voice или audio, дополнительно выведем их параметры
        if msg.voice:
            logger.info(f"ОТЛАДКА: voice duration={msg.voice.duration}, mime={msg.voice.mime_type}, file_id={msg.voice.file_id[:20]}...")
        if msg.audio:
            logger.info(f"ОТЛАДКА: audio duration={msg.audio.duration}, mime={msg.audio.mime_type}, file_id={msg.audio.file_id[:20]}...")
    app.add_handler(MessageHandler(~filters.COMMAND, debug_all_messages))
    # === КОНЕЦ ДИАГНОСТИКИ ===


    logger.info("Бот запущен и готов к работе.")
    # Печатаем сообщение в консоль, чтобы видеть, что бот стартовал
    print("Бот запущен в диалоговом режиме...")

    # Запускаем бесконечный опрос серверов Telegram (polling).
    # Этот метод будет работать, пока программа не будет остановлена (Ctrl+C).
    app.run_polling()


# Если файл запущен напрямую (а не импортирован как модуль), вызываем main()
if __name__ == "__main__":
    main()