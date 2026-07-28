"""
Обработчики сообщений Telegram.
Модуль, который связывает всё воедино.
"""

import os
from telegram import Update
from telegram.ext import ContextTypes

# Импортируем наши сервисы
from services.stt import transcribe_audio
from services.analyzer import analyze_brief
from services.image_gen import generate_architecture_image
import utils

# Эта функция будет вызываться каждый раз, когда бот получит сообщение с голосовым и фото
async def handle_voice_and_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает входящее сообщение, которое содержит одновременно голосовое
    и фотографию. Запускает весь конвейер анализа.
    """
    message = update.message   # само сообщение от пользователя

    # Проверка: если нет голосового ИЛИ нет фото — просим прислать оба
    if not message.voice or not message.photo:
        await message.reply_text("Пожалуйста, пришлите одновременно голосовое сообщение и фото схемы.")
        return

    # Отправим сообщение, которое будем менять на каждом этапе — так пользователь видит прогресс
    processing_msg = await message.reply_text("⏳ Получаю файлы...")

    # Переменные для путей к файлам (чтобы потом удалить)
    voice_path = None
    photo_path = None

    try:
        # 1. Получаем файлы из Telegram
        voice_file = await message.voice.get_file()
        # Берём самое большое доступное разрешение фотографии (последний элемент списка photo)
        photo_file = await message.photo[-1].get_file()

        # Скачиваем файлы во временную папку
        voice_path = utils.download_file(context.bot, voice_file.file_id, "voice.ogg")
        photo_path = utils.download_file(context.bot, photo_file.file_id, "schema.jpg")

        # 2. Распознаём речь (аудио → текст)
        await processing_msg.edit_text("🎤 Распознаю речь...")
        brief_text = transcribe_audio(voice_path)
        if not brief_text.strip():
            raise ValueError("Не удалось распознать речь.")  # если тишина или шум

        # 3. Анализируем бриф (текст + фото → отчёт + промпт для картинки)
        await processing_msg.edit_text("🧠 Анализирую бриф и схему...")
        analysis = analyze_brief(brief_text, photo_path)

        # 4. Генерируем диаграмму (если есть описание)
        img_bytes = None
        if analysis["diagram_prompt"]:
            try:
                await processing_msg.edit_text("🖼️ Генерирую диаграмму архитектуры ...")
                img_bytes = generate_architecture_image(analysis["diagram_prompt"])
            except Exception as e:
                # Если не получилось сгенерировать — сообщим, но работу не прерываем
                await message.reply_text(f"⚠️ Не удалось сгенерировать изображение: {e}")

        # 5. Отправляем результат пользователю
        await processing_msg.delete()  # убираем сообщение «обрабатываю»

        # Текстовый отчёт. Telegram ограничивает длину сообщения (4096 символов).
        report_text = analysis["report"]
        if len(report_text) > 4000:
            report_text = report_text[:4000] + "\n... (обрезано)"

        # Отправляем текст (без форматирования Markdown, чтобы не сломать разметку)
        await message.reply_text(report_text)

        # Если картинка сгенерирована — отправляем её
        if img_bytes:
            img_path = utils.save_response_image(img_bytes)
            with open(img_path, "rb") as img:
                await message.reply_photo(img, caption="Диаграмма архитектуры СППР")

    except Exception as e:
        # В случае любой ошибки — удаляем сообщение о статусе и пишем пользователю
        await processing_msg.delete()
        await message.reply_text(f"❌ Ошибка обработки: {str(e)}")

    finally:
        # Очистка временных файлов, чтобы не засорять диск
        for path in [voice_path, photo_path]:
            if path and os.path.exists(path):
                os.remove(path)