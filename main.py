"""
Точка входа в приложение.
Создаёт и запускает Telegram-бота в диалоговом режиме:
можно отправлять голос и фото по отдельности, в любом порядке.
Если пользователь случайно отправляет оба сразу — корректно обработаем и такой случай.
"""
import logging
# Импортируем нужные классы для создания бота и обработчиков
from telegram.ext import (
    ApplicationBuilder,   # Строитель приложения (основной объект бота)
    CommandHandler,        # Обработчик команд типа /start
    MessageHandler,        # Обработчик обычных сообщений
    filters                # Фильтры для отбора определённых типов сообщений
)
from config import TELEGRAM_TOKEN  # Токен бота из файла .env

# Импортируем наши функции-обработчики из модуля handlers
from handlersTG import (
    start_command,         # Для команды /start
    handle_voice,          # Для голосовых сообщений
    handle_photo,          # Для фото
    KEY_VOICE_PATH,        # Ключи для хранения в контексте
    KEY_PHOTO_PATH,
    run_analysis            # Функция запуска полного анализа
)
import utils               # Вспомогательные функции (скачивание файлов)
from logger import setup_logger, LOGGER_NAME   # Импортируем настройки логгера


# Получаем логгер для этого модуля
logger = logging.getLogger(LOGGER_NAME)

async def combined_handler(update, context):
    """
    Обработчик на случай, если пользователь отправил одним сообщением
    сразу и голосовое, и фотографию.
    Мы вручную сохраняем оба файла и, если всё готово, запускаем анализ.
    """
    logger.debug("Вызван combined_handler (голос + фото в одном сообщении)")
    message = update.message
    voice = message.voice
    photo = message.photo

    # Если в сообщении есть голосовое — скачиваем и запоминаем путь
    if voice:
        voice_file = await voice.get_file()
        voice_path = utils.download_file(context.bot, voice_file.file_id, "voice.ogg")
        context.user_data[KEY_VOICE_PATH] = voice_path
        logger.info(f"Голосовое сохранено в combined: {voice_path}")

    # Если есть фото — скачиваем и запоминаем (наибольшее разрешение)
    if photo:
        photo_file = await photo[-1].get_file()
        photo_path = utils.download_file(context.bot, photo_file.file_id, "schema.jpg")
        context.user_data[KEY_PHOTO_PATH] = photo_path
        logger.info(f"Фото сохранено в combined: {photo_path}")

    # Проверяем, всё ли получено (могло быть, что голос/фото не загрузились)
    if context.user_data.get(KEY_VOICE_PATH) and context.user_data.get(KEY_PHOTO_PATH):
        # Запускаем обработку, передавая пути к обоим файлам
        await run_analysis(update, context,
                           context.user_data[KEY_VOICE_PATH],
                           context.user_data[KEY_PHOTO_PATH])
    else:
        # Что-то пошло не так — просим прислать недостающее
        logger.warning("combined_handler: не все файлы получены")
        await message.reply_text("Пожалуйста, убедитесь, что вы отправили и голосовое, и фото.")


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

    # Регистрируем обработчик команды /start
    app.add_handler(CommandHandler("start", start_command))

    # Обработчик для сообщений, содержащих ТОЛЬКО голосовое (без фото).
    # Фильтр: filters.VOICE & ~filters.PHOTO означает "есть голос И НЕТ фото".
    app.add_handler(MessageHandler(filters.VOICE & ~filters.PHOTO, handle_voice))

    # Обработчик для сообщений, содержащих ТОЛЬКО фото (без голоса).
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.VOICE, handle_photo))

    # Обработчик на случай, если в одном сообщении есть и голос, и фото одновременно.
    # Такой фильтр сработает только когда присутствуют оба типа.
    app.add_handler(MessageHandler(filters.VOICE & filters.PHOTO, combined_handler))

    logger.info("Бот запущен и готов к работе.")
    # Печатаем сообщение в консоль, чтобы видеть, что бот стартовал
    print("Бот запущен в диалоговом режиме...")

    # Запускаем бесконечный опрос серверов Telegram (polling).
    # Этот метод будет работать, пока программа не будет остановлена (Ctrl+C).
    app.run_polling()


# Если файл запущен напрямую (а не импортирован как модуль), вызываем main()
if __name__ == "__main__":
    main()