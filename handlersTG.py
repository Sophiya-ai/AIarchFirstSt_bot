"""
Обработчики сообщений Telegram-бота.
Реализован диалоговый режим: пользователь может отправить голосовое
сообщение или фотографию в любом порядке. Бот запоминает полученное
и запрашивает недостающее. Когда оба файла (голос + фото) получены,
автоматически запускается полный цикл анализа.
"""
import os
import logging
import asyncio
from telegram import Update                      # Объект с информацией о событии
from telegram.ext import ContextTypes            # Контекст для хранения данных между вызовами

# Импортируем функции из наших сервисов
from services.stt import transcribe_audio        # Распознавание речи
from services.analyzer import analyze_brief      # Анализ брифа (текст + фото)
from services.kroki import generate_diagram  # Генерация диаграммы
from services.image_gen import generate_architecture_image # Генерация логотипа
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


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Вызывается, когда пользователь присылает голосовое/аудио любого типа -
    voice, audio, аудиодокумент (без фото).
    Сохраняет аудиофайл, проверяет, есть ли уже фото.
    Если фото уже получено — запускает анализ. Если нет — просит прислать фото.
    """
    try:
        message = update.message         # Извлекаем объект сообщения
        # Определяем file_id в зависимости от того, что пришло
        file_id = None
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
        elif message.document and message.document.mime_type and "audio" in message.document.mime_type:
            file_id = message.document.file_id
        else:
            logger.warning("handle_audio: нет аудиоданных")
            return

        user = update.effective_user
        logger.info(f"Пользователь {user.id} прислал аудио (тип: {type(message).__name__})")

        # Асинхронно скачиваем файл, используя его file_id
        audio_path = await utils.download_file(context.bot, file_id, "voice.ogg")
        logger.info(f"Аудио сохранено: {audio_path}")

        # Сохраняем путь к файлу в «памяти» бота для этого конкретного пользователя.
        context.user_data[KEY_VOICE_PATH] = audio_path

        # Проверяем, есть ли уже путь к фотографии
        photo_path = context.user_data.get(KEY_PHOTO_PATH)
        if photo_path:
            logger.info("Оба файла готовы (голос только что получен), запуск анализа")
            # Если фото уже было прислано ранее — всё готово, запускаем анализ
            await run_analysis(update, context, audio_path, photo_path)
        else:
            # Иначе просим пользователя дослать фото
            logger.debug("Фото ещё нет, запрашиваем")
            await message.reply_text("🎤 Аудио сохранено. Теперь пришлите, пожалуйста, фото схемы.")

    except Exception as e:
            logger.exception(f"Ошибка в handle_audio: {e}")
            await update.message.reply_text("Произошла ошибка при обработке аудио. Попробуйте снова или обратитесь к администратору.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Вызывается, когда пользователь присылает фотографию (без голоса).
    Сохраняет изображение, проверяет, есть ли уже голос.
    Если голос уже получен — запускает анализ. Иначе просит записать голосовое.
    """
    try:
        message = update.message
        photo = message.photo
        if not photo:
            logger.warning("handle_photo: сообщение без фото")
            return

        user = update.effective_user
        logger.debug(f"Пользователь {user.id} прислал фото")

        # Используем file_id самого большого размера (последний в списке).
        # Telegram всегда отправляет массив, в котором photo[-1] — наибольшее.
        photo_path = await utils.download_file(context.bot, photo[-1].file_id, "schema.jpg")
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
    except Exception as e:
            logger.exception(f"Ошибка в handle_photo: {e}")
            await update.message.reply_text("Произошла ошибка при обработке фото. Попробуйте снова или обратитесь к администратору.")


async def combined_handler(update, context):
    """
    Обработчик на случай, если пользователь отправил одним сообщением
    сразу и голосовое, и фотографию.
    Мы вручную сохраняем оба файла и, если всё готово, запускаем анализ.
    """
    try:
        logger.debug("Вызван combined_handler (голос + фото в одном сообщении)")
        message = update.message

        # Определяем аудио file_id
        file_id = None
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
        elif message.document and message.document.mime_type and "audio" in message.document.mime_type:
            file_id = message.document.file_id

        if file_id:
            audio_path = await utils.download_file(context.bot, file_id, "voice.ogg")
            context.user_data[KEY_VOICE_PATH] = audio_path
            logger.info(f"Аудио сохранено в combined: {audio_path}")

        if message.photo:
            photo_path = await utils.download_file(context.bot, message.photo[-1].file_id, "schema.jpg")
            context.user_data[KEY_PHOTO_PATH] = photo_path
            logger.info(f"Фото сохранено в combined: {photo_path}")

        if context.user_data.get(KEY_VOICE_PATH) and context.user_data.get(KEY_PHOTO_PATH):
            await run_analysis(update, context,
                               context.user_data[KEY_VOICE_PATH],
                               context.user_data[KEY_PHOTO_PATH])
        else:
            await message.reply_text("Пожалуйста, убедитесь, что вы отправили и аудио, и фото.")
    except Exception as e:
        logger.exception(f"Ошибка в combined_handler: {e}")



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

    # --- Таймер долгого ожидания ---
    async def notify_long_wait():
        await asyncio.sleep(15)
        try:
            await processing_msg.edit_text("🕐 Всё ещё анализирую бриф и схему... Пожалуйста, подождите.")
        except Exception:
            pass  # если сообщение уже удалено или изменено, игнорируем

    long_wait_task = asyncio.create_task(notify_long_wait())
    # -------------------------------

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

        logger.info(f"mermaid_code сырой: {analysis['mermaid_code']}")
        if analysis['mermaid_code']:
            logger.info(f"Первые 200 символов кода: {analysis['mermaid_code'][:200]}")

        # После завершения анализа отменяем таймер
        long_wait_task.cancel()
        try:
            await long_wait_task
        except asyncio.CancelledError:
            pass


        # ----------------------------------------------
        # Шаг 3: Генерация логотипа (Pollinations)
        # ----------------------------------------------
        logo_bytes = None
        # Проверяем, вернула ли модель описание
        if analysis['logo_prompt']:
            logger.debug(f"Этап 3: генерация логотипа (Pollinations), промпт: {analysis['logo_prompt'][:80]}...")
            try:
                await processing_msg.edit_text("🎨 Создаю логотип системы...")
                # Генерируем изображение через Pollinations.ai
                logo_bytes = generate_architecture_image(analysis["logo_prompt"])
                logger.info("Логотип успешно создан")
            except Exception as e:
                # Если генерация не удалась, предупредим, но анализ всё равно отправим
                # Ошибки записываются с трассировкой (exc_info=True),
                # что позволяет моментально понять, что сломалось
                logger.error(f"Ошибка генерации логотипа: {str(e)}", exc_info=True)
                await message.reply_text(f"⚠️ Не удалось создать логотип: {e}")
        else:
            logger.warning("Модель не вернула описание диаграммы, пропускаем генерацию")

        # ----------------------------------------------
        # Шаг 4: Генерация архитектурной диаграммы (Kroki)
        # ----------------------------------------------
        diagram_bytes = None
        if analysis.get("mermaid_code"):
            try:
                await processing_msg.edit_text("📐 Рисую архитектурную диаграмму...")
                diagram_bytes = generate_diagram(analysis["mermaid_code"])
                logger.info("Диаграмма успешно создана")
            except Exception as e:
                logger.error(f"Ошибка генерации диаграммы: {str(e)}", exc_info=True)
                await message.reply_text(f"⚠️ Не удалось создать диаграмму: {e}")

        await processing_msg.delete() # Удаляем сообщение о ходе обработки

        # ----------------------------------------------
        # Шаг 5: Отправка результатов пользователю
        # ----------------------------------------------
        logger.debug("Этап 4: отправка результатов пользователю")

        # Текстовый отчёт: обрезаем до безопасного лимита Telegram (4000 символов)
        report = analysis["report"]
        if len(report) > 4000:
            report = report[:4000] + "\n... (текст обрезан)"
        await message.reply_text(report) # Отправляем текстовый отчёт

        # Если изображение сгенерировано, отправляем его как фото
        if logo_bytes:
            # Сохраняем байты картинки в файл во временной папке
            logo_path = utils.save_response_image(logo_bytes, "logo.png")
            # Открываем и отправляем
            with open(logo_path, "rb") as img:
                await message.reply_photo(img, caption="Логотип системы")
            logger.info(f"Логотип отправлен, временный файл: {logo_path}")

        # Отправляем диаграмму, если есть
        if diagram_bytes:
            diagram_path = utils.save_response_image(diagram_bytes, "architecture.png")
            with open(diagram_path, "rb") as img:
                await message.reply_photo(img, caption="Диаграмма архитектуры СППР")

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