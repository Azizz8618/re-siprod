#!/usr/bin/env python3
"""Прогон варианта библиотеки: *PERSO + *CALL YESMEMORY + *MAIN DRAKON.

Печатает вердикт: чисто (есть дата библиотеки «02.10.81») или
«ИСПОРЧЕНЫ ПОДПРОГРАММЫ» / иная ошибка.

Использование: python3 scripts/probe_load.py variant-<имя>.bin [вариант...]
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHARE = os.environ.get("BESM6_SHARE", "/home/z/my-project/besm6")
VOL = "2348"

JOB = """ШИФР 419900ЗС5^ОЗУ 32^ТРА 100^АЦП 64^ЛЕН 67(%(vol)s)^ЕЕВ1А3
*name
*no lo
*perso:672100
*call yesmemory
*main %(main)s
*execute
ЗАГОЛОВОК: Проверка
ДЕЙСТВИЕ: Сделать
КОНЕЦ
*end file
``````
ЕКОНЕЦ
"""


def probe(lib_path, keep=False, main="drakon"):
    lib_path = os.path.abspath(lib_path)
    work = tempfile.mkdtemp(prefix="probe-")
    vol = os.path.join(work, VOL)
    shutil.copy(os.path.join(SHARE, VOL), vol)
    env = dict(os.environ, BESM6_PATH=work + ":" + SHARE)
    wenv = dict(os.environ, BESM6_PATH=work)
    r = subprocess.run(["besmtool", "write", VOL, "--from-file=%s" % lib_path,
                        "--start=1088"], cwd=work, env=wenv,
                       capture_output=True, text=True)
    if r.returncode:
        print("  запись тома не прошла:", (r.stdout + r.stderr).strip()[:200])
        shutil.rmtree(work, ignore_errors=True)
        return None
    if r.returncode:
        print("  запись тома не прошла:", r.stderr.strip())
        shutil.rmtree(work, ignore_errors=True)
        return None
    job = os.path.join(work, "job.b6")
    with open(job, "w") as f:
        f.write(JOB % {"vol": VOL, "main": main})
    r = subprocess.run(["dispak", job], cwd=work, env=env,
                       capture_output=True, text=True, timeout=240)
    out = r.stdout + r.stderr
    if keep:
        with open(lib_path + ".run.log", "w") as f:
            f.write(out)
    shutil.rmtree(work, ignore_errors=True)
    return out


def verdict(out):
    if out is None:
        return "ОШИБКА ЗАПИСИ"
    if "СПОРЧЕН" in out:
        return "ИСПОРЧЕНЫ"
    if "02.10.81" in out:
        if "КОНЕЦ ЗАДАЧИ" in out and "ДЕЛЕНИЕ" not in out and \
                "ош" not in out.lower():
            return "ЧИСТО + ЗАПУСК"
        return "ЧИСТО (каталог), сбой пуска"
    if "КОНЕЦ ЗАДАЧИ" in out:
        return "без даты, конец задачи"
    return "прочее"


def main():
    import os as _os
    m = _os.environ.get("MAIN", "drakon")
    for p in sys.argv[1:]:
        out = probe(p, main=m)
        print("%-40s %s" % (os.path.basename(p), verdict(out)))
        if os.environ.get("V") and out:
            tail = [l for l in out.splitlines() if l.strip()][:30]
            for l in tail:
                print("    |", l)


if __name__ == "__main__":
    main()
