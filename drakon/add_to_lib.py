#!/usr/bin/env python3
"""Добавление модуля МАДЛЕН в библиотеку СИПРОДа.

Скрипт компилирует исходник на МАДЛЕН и добавляет его в библиотеку DMS.

Использование:
    python3 drakon/add_to_lib.py drakon.madlen
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from siprod_lib import Library, text_encode

WORK = "/tmp/drm-work"
ASMPL = "/home/azizz/Yandex.Disk/monitor80-re/tools/asm.pl"


def compile_madlen(src_path, work_dir):
    """Компилирует исходник МАДЛЕН."""
    basename = os.path.splitext(os.path.basename(src_path))[0]
    masm = os.path.join(work_dir, basename + ".masm")
    
    # Копируем исходник
    with open(src_path, 'r') as f:
        content = f.read()
    
    # Меняем имя модуля на верхний регистр для компилятора
    content = content.replace(basename.upper(), basename.upper())
    
    with open(masm, 'w') as f:
        f.write(content)
    
    # Компилируем
    env = os.environ.copy()
    env["BESM6_PATH"] = work_dir + ":/usr/local/share/besm6"
    env["WORKVOL"] = "2348"
    env["PATH"] = work_dir + ":" + env["PATH"]
    
    result = subprocess.run(
        ["perl", "-CA", ASMPL, masm],
        env=env,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("Ошибка компиляции:", result.stderr)
        return None
    
    # Ищем dtr файл с объектным кодом
    dtr_path = os.path.join(work_dir, basename + ".dtr")
    if os.path.exists(dtr_path):
        return dtr_path
    
    # Пробуем dtra
    dtra_path = os.path.join(work_dir, basename + ".dtra")
    if os.path.exists(dtra_path):
        return dtra_path
    
    print("Объектный файл не найден")
    return None


def read_object_words(path):
    """Читает слова объектного модуля."""
    words = []
    with open(path, 'rb') as f:
        while True:
            data = f.read(6)
            if not data:
                break
            words.append(int.from_bytes(data, 'big'))
    return words


def add_module_to_library(lib_path, module_name, object_words):
    """Добавляет модуль в библиотеку."""
    # Читаем библиотеку
    with open(lib_path, 'rb') as f:
        data = f.read()
    
    words = [int.from_bytes(data[i:i+6], 'big') for i in range(0, len(data), 6)]
    
    # Находим каталог (первые 2 зоны = 2 * 1024 * 8 / 6 = 272 слова)
    cat_words = 2 * 1024 * 8 // 6
    
    # Ищем завершатель каталога
    n = 1
    while 2 * n + 1 < cat_words:
        nm = lib.words[2 * n] if n < len(lib.words)//2 else 0
        if nm == 0 or nm == text_encode(""):
            break
        n += 1
    
    print(f"Добавляем модуль {module_name} на место {n}")
    
    # Создаем новую запись
    # Формат: имя_модуля, длина_загрузки, дата
    name_word = text_encode(module_name.ljust(8)[:8])
    load_len = len(object_words) * 8  # в битах
    
    # Добавляем запись
    words[2 * n] = name_word
    words[2 * n + 1] = load_len
    
    # Добавляем объектный код после последнего модуля
    last_end = len(words)
    words.extend(object_words)
    
    # Записываем обратно
    out_data = b''.join(w.to_bytes(6, 'big') for w in words)
    
    backup = lib_path + ".backup"
    os.rename(lib_path, backup)
    with open(lib_path, 'wb') as f:
        f.write(out_data)
    
    print(f"Библиотека обновлена: {len(words)} слов")
    return True


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 add_to_lib.py <исходник.madlen>")
        sys.exit(1)
    
    src_path = sys.argv[1]
    if not os.path.exists(src_path):
        print(f"Файл не найден: {src_path}")
        sys.exit(1)
    
    module_name = os.path.splitext(os.path.basename(src_path))[0].upper()
    print(f"Обрабатываю: {module_name}")
    
    # Рабочая директория
    work = WORK
    os.makedirs(work, exist_ok=True)
    
    # Копируем диск
    disk = os.path.join(work, "2348")
    if not os.path.exists(disk):
        import shutil
        shutil.copy(os.environ.get("BESM6_SHARE", "/usr/local/share/besm6") + "/2348", disk)
    
    # Компилируем
    print("Компиляция...")
    obj_path = compile_madlen(src_path, work)
    if not obj_path:
        print("Ошибка компиляции")
        sys.exit(1)
    
    print(f"Объект: {obj_path}")
    
    # Читаем объект
    object_words = read_object_words(obj_path)
    print(f"Слов в объекте: {len(object_words)}")
    
    # Добавляем в библиотеку
    lib_path = os.path.join(ROOT, "siprod.bin")
    if os.path.exists(lib_path):
        print("Добавление в библиотеку...")
        add_module_to_library(lib_path, module_name, object_words)
    else:
        print(f"Библиотека не найдена: {lib_path}")


if __name__ == "__main__":
    main()
