import os
import base64  # для кодирования картинок в текст (base64) при отправке модели
from config import TEMP_DIR


"""Создаём временную папку, если её нет."""
def ensure_temp_dir():
    os.makedirs(TEMP_DIR, exist_ok=True) # exist_ok=True — не выдаёт ошибку, если папка уже существует

"""
    Скачиваем файл из Telegram по его file_id и сохраняем во временную папку.
    - bot — объект бота (через него получаем информацию о файле)
    - file_id — уникальный идентификатор файла в Telegram
    - file_name — под каким именем сохранить файл на диске
    Возвращаем полный путь к сохранённому файлу.
"""
def download_file(bot, file_id, file_name):
    ensure_temp_dir()
    file = bot.get_file(file_id)                    # получаем объект файла
    file_path = os.path.join(TEMP_DIR, file_name)   # формируем полный путь
    file.download(file_path)
    return file_path


"""
    Читаем файл и кодируем его в строку base64.
    Мультимодальные модели часто принимают картинки именно в таком формате.
"""
def encode_file_to_base64(file_path):
    with open(file_path, "rb") as f:                        # открываем файл в бинарном режиме
        file_data = f.read()                                # читаем все байты

        # кодируем байты в base64 и декодируем в обычную строку (UTF-8)
        return base64.b64encode(file_data).decode("utf-8")

"""
    Сохраняем бинарные данные картинки в файл.
    - image_data — байты (то, что вернул генератор)
    - filename — имя файла
    Возвращаем путь к сохранённому изображению.
"""
def save_response_image(image_data, filename="architecture.png"):

    ensure_temp_dir()
    path = os.path.join(TEMP_DIR, filename)
    with open(path, "wb") as f:               # wb — запись бинарных данных
        f.write(image_data)
    return path