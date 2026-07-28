"""
Точка входа в приложение.
Создаёт и запускает Telegram-бота.
"""

from telegram.ext import ApplicationBuilder, MessageHandler, filters
from config import TELEGRAM_TOKEN
from handlersTG import handle_voice_and_photo

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build() # Строим приложение с токеном бота

    # Фильтр: сообщение должно содержать и голос, и фото
    voice_and_photo_filter = filters.VOICE & filters.PHOTO

    # Регистрируем обработчик: при сообщении с таким фильтром вызываем нашу функцию
    app.add_handler(MessageHandler(voice_and_photo_filter, handle_voice_and_photo))

    print("Бот запущен...")
    app.run_polling()    # Запускаем бесконечный опрос серверов Telegram (polling)

if __name__ == "__main__":
    main()