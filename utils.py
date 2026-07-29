import os
import base64  # для кодирования картинок в текст (base64) при отправке модели
import logging
from config import TEMP_DIR
from logger import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)



def ensure_temp_dir():
    """Создаём временную папку, если её нет."""
    os.makedirs(TEMP_DIR, exist_ok=True) # exist_ok=True — не выдаёт ошибку, если папка уже существует
    logger.debug(f"Создана/найдена временная папка: {TEMP_DIR}")


async def download_file(bot, file_id, file_name):
        """
            Асинхронно скачиваем файл из Telegram по его file_id и сохраняем во временную папку.
            - bot — объект бота (через него получаем информацию о файле)
            - file_id — уникальный идентификатор файла в Telegram
            - file_name — под каким именем сохранить файл на диске
            Возвращаем полный путь к сохранённому файлу.
        """
        ensure_temp_dir()
        file = await bot.get_file(file_id)                    # Асинхронно получаем объект File через API Telegram
        file_path = os.path.join(TEMP_DIR, file_name)   # формируем полный путь
        await file.download_to_drive(file_path)                # Асинхронно скачиваем файл на диск
        logger.debug(f"Файл {file_name} сохранён: {file_path}")
        return file_path



def encode_file_to_base64(file_path):
    """
        Читаем файл и кодируем его в строку base64.
        Мультимодальные модели часто принимают картинки именно в таком формате.
    """
    with open(file_path, "rb") as f:                        # открываем файл в бинарном режиме
        file_data = f.read()                                # читаем все байты

        logger.debug(f"Файл {file_path} закодирован в base64, исходный размер: {len(file_data)} байт")

        # кодируем байты в base64 и декодируем в обычную строку (UTF-8)
        return base64.b64encode(file_data).decode("utf-8")


def save_response_image(image_data, filename="architecture.png"):
    """
        Сохраняем бинарные данные картинки в файл.
        - image_data — байты (то, что вернул генератор)
        - filename — имя файла
        Возвращаем путь к сохранённому изображению.
    """
    ensure_temp_dir()
    path = os.path.join(TEMP_DIR, filename)
    with open(path, "wb") as f:               # wb — запись бинарных данных
        f.write(image_data)
    logger.debug(f"Изображение сохранено: {path}, размер: {len(image_data)} байт")
    return path