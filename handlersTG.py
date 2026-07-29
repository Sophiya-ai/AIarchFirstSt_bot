"""
Обработчики сообщений Telegram-бота.
Реализован диалоговый режим: пользователь может отправить голосовое
сообщение или фотографию в любом порядке. Бот запоминает полученное
и запрашивает недостающее. Когда оба файла (голос + фото) получены,
автоматически запускается полный цикл анализа.
"""
import os
import logging
from telegram import Update                      # Объект с информацией о событии
from telegram.ext import ContextTypes            # Контекст для хранения данных между вызовами

# Импортируем функции из наших сервисов
from services.stt import transcribe_audio        # Распознавание речи
from services.analyzer import analyze_brief      # Анализ брифа (текст + фото)
from services.image_gen import generate_architecture_image  # Генерация картинки
import utils                                     # Вспомогательные функции (скачивание, кодирование и т.д.)
from logger import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

# Ключи для хранения временных путей к файлам в context.user_data.
# Это «переменные», в которых бот помнит, что пользователь уже прислал.
KEY_VOICE_PATH = "voice_path"
KEY_PHOTO_PATH = "photo_path"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start.
    Полностью сбрасывает текущий прогресс (удаляет сохранённые голос и фото)
    и выводит приветственное сообщение.
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.id} вызвал /start")

    # Очищаем словарь user_data, где мы хранили пути к файлам.
    # После этого бот «забывает», что пользователь уже отправлял.
    context.user_data.clear()

    # Отправляем приветствие с инструкцией
    await update.message.reply_text(
        "👋 Привет! Я проанализирую бриф на разработку СППР.\n"
        "Пришли мне голосовое сообщение с описанием задачи и фотографию схемы.\n"
        "Можно отправлять в любом порядке — я подожду."
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Вызывается, когда пользователь присылает голосовое сообщение (без фото).
    Сохраняет аудиофайл, проверяет, есть ли уже фото.
    Если фото уже получено — запускает анализ. Если нет — просит прислать фото.
    """
    message = update.message         # Извлекаем объект сообщения
    voice = message.voice            # Получаем информацию о голосовом файле
    if not voice:
        logger.warning("handle_voice: сообщение без голосового")
        return                       # Если по какой-то причине голоса нет — выходим

    user = update.effective_user
    logger.debug(f"Пользователь {user.id} прислал голосовое")

    # Скачиваем голосовой файл во временную папку.
    # get_file() возвращает объект, через который можно загрузить файл с сервера Telegram.
    voice_file = await voice.get_file()

    # utils.download_file скачивает файл и возвращает путь к нему на диске.
    voice_path = utils.download_file(context.bot, voice_file.file_id, "voice.ogg")
    logger.info(f"Голосовое сохранено: {voice_path}")

    # Сохраняем путь к файлу в «памяти» бота для этого конкретного пользователя.
    context.user_data[KEY_VOICE_PATH] = voice_path

    # Проверяем, есть ли уже путь к фотографии
    photo_path = context.user_data.get(KEY_PHOTO_PATH)
    if photo_path:
        logger.info("Оба файла готовы (голос только что получен), запуск анализа")
        # Если фото уже было прислано ранее — всё готово, запускаем анализ
        await run_analysis(update, context, voice_path, photo_path)
    else:
        # Иначе просим пользователя дослать фото
        logger.debug("Фото ещё нет, запрашиваем")
        await message.reply_text("🎤 Голосовое сохранено. Теперь пришлите, пожалуйста, фото схемы.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Вызывается, когда пользователь присылает фотографию (без голоса).
    Сохраняет изображение, проверяет, есть ли уже голос.
    Если голос уже получен — запускает анализ. Иначе просит записать голосовое.
    """
    message = update.message
    photo = message.photo
    if not photo:
        logger.warning("handle_photo: сообщение без фото")
        return

    user = update.effective_user
    logger.debug(f"Пользователь {user.id} прислал фото")

    # Из массива photo берём последний элемент — фото с самым высоким разрешением.
    # Telegram всегда отправляет массив, в котором photo[-1] — наибольшее.
    photo_file = await photo[-1].get_file()
    photo_path = utils.download_file(context.bot, photo_file.file_id, "schema.jpg")
    logger.info(f"Фото сохранено: {photo_path}")

    # Сохраняем путь к фотографии в контексте пользователя
    context.user_data[KEY_PHOTO_PATH] = photo_path

    # Проверяем наличие голосового
    voice_path = context.user_data.get(KEY_VOICE_PATH)
    if voice_path:
        # Оба компонента на месте — запускаем анализ
        logger.info("Оба файла готовы (фото только что получено), запуск анализа")
        await run_analysis(update, context, voice_path, photo_path)
    else:
        # Просим прислать голос
        logger.debug("Голоса ещё нет, запрашиваем")
        await message.reply_text("📷 Фото сохранено. Теперь пришлите, пожалуйста, голосовое описание задачи.")


async def run_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       voice_path: str, photo_path: str):
    """
    Запускает полную обработку с логированием каждого этапа:
    1. Распознавание речи (STT) из аудиофайла.
    2. Мультимодальный анализ (текст + фото) с помощью Gemma.
    3. Генерация диаграммы (если модель предоставила описание).
    4. Отправка результатов пользователю.
    После завершения (или ошибки) временные файлы удаляются,
    и состояние пользователя очищается для возможности нового запроса.
    """
    user = update.effective_user
    logger.info(f"Начат анализ для пользователя {user.id}")

    message = update.message

    # Отправляем сообщение «статус обработки», которое будем редактировать на каждом шаге
    processing_msg = await message.reply_text("⏳ Начинаю анализ...")

    try:
        # ----------------------------------------------
        # Шаг 1: Распознавание речи (Audio -> Text)
        # ----------------------------------------------
        logger.debug("Этап 1: транскрибация аудио")
        await processing_msg.edit_text("🎤 Распознаю речь...")
        # Вызываем функцию транскрибации, которая отправляет аудио в Groq Whisper
        brief_text = transcribe_audio(voice_path)
        logger.info(f"Распознанный текст (первые 100 символов): {brief_text[:100]}...")

        # Если распознанный текст пустой или состоит только из пробелов — это ошибка
        if not brief_text.strip():
            logger.error("Транскрибация вернула пустой текст")
            raise ValueError("Не удалось распознать речь. Попробуйте записать более чётко.")

        # ----------------------------------------------
        # Шаг 2: Мультимодальный анализ (Text + Image)
        # ----------------------------------------------
        logger.debug("Этап 2: анализ брифа")
        await processing_msg.edit_text("🧠 Анализирую бриф и схему...")
        # Функция analyze_brief отправляет текст и картинку в Gemma через OpenRouter,
        # получает структурированный отчёт и текстовый промпт для генерации диаграммы.
        analysis = analyze_brief(brief_text, photo_path)
        logger.info("Анализ завершён успешно")

        # ----------------------------------------------
        # Шаг 3: Генерация изображения архитектуры
        # ----------------------------------------------
        img_bytes = None
        # Проверяем, вернула ли модель описание диаграммы (prompt)
        if analysis["diagram_prompt"]:
            logger.debug(f"Этап 3: генерация диаграммы, промпт: {analysis['diagram_prompt'][:80]}...")
            try:
                await processing_msg.edit_text("🖼️ Генерирую диаграмму архитектуры ...")
                # Генерируем изображение через Pollinations.ai
                img_bytes = generate_architecture_image(analysis["diagram_prompt"])
                logger.info("Изображение архитектуры успешно сгенерировано")
            except Exception as e:
                # Если генерация не удалась, предупредим, но анализ всё равно отправим
                # Ошибки записываются с трассировкой (exc_info=True),
                # что позволяет моментально понять, что сломалось
                logger.error(f"Ошибка генерации изображения: {str(e)}", exc_info=True)
                await message.reply_text(f"⚠️ Не удалось сгенерировать изображение: {e}")
        else:
            logger.warning("Модель не вернула описание диаграммы, пропускаем генерацию")

        # ----------------------------------------------
        # Шаг 4: Отправка результатов пользователю
        # ----------------------------------------------
        logger.debug("Этап 4: отправка результатов пользователю")
        await processing_msg.delete()   # Удаляем сообщение о ходе обработки

        # Текстовый отчёт: обрезаем до безопасного лимита Telegram (4000 символов)
        report = analysis["report"]
        if len(report) > 4000:
            report = report[:4000] + "\n... (текст обрезан)"

        # Отправляем текстовый отчёт
        await message.reply_text(report)

        # Если изображение сгенерировано, отправляем его как фото
        if img_bytes:
            # Сохраняем байты картинки в файл во временной папке
            img_path = utils.save_response_image(img_bytes)
            # Открываем и отправляем
            with open(img_path, "rb") as img:
                await message.reply_photo(img, caption="Диаграмма архитектуры СППР")

            logger.info(f"Диаграмма отправлена, временный файл: {img_path}")

        logger.info("Анализ успешно завершён и отправлен")

    except Exception as e:
        # Если на любом этапе произошла ошибка, удаляем сообщение «статус» и пишем об ошибке
        logger.exception(f"Ошибка в процессе анализа: {str(e)}")
        await processing_msg.delete()
        await message.reply_text(f"❌ Ошибка обработки: {str(e)}")

    finally:
        # Этот блок выполняется всегда — и при успехе, и при ошибке.
        # Удаляем временные файлы с диска, если они существуют.
        if voice_path and os.path.exists(voice_path):
            os.remove(voice_path)
            logger.debug(f"Удалён временный файл голоса: {voice_path}")
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
            logger.debug(f"Удалён временный файл фото: {photo_path}")

        # Сбрасываем состояние пользователя: теперь он может начинать новый запрос
        context.user_data.clear()
        logger.debug("Контекст пользователя очищен")