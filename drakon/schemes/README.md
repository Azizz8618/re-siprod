# Блок-схемы работы редактора СИПРОД (язык ДРАКОН)

Схемы составлены по текстам модулей СИПРОДа, разобранным в проекте
re-siprod (см. `SIPROD.md`, `bemsh/*.be`, `madlen/*.madlen`): вызов
монитором, разбор блоков, диспетчер команд, модель страницы, ошибки.

## Состав

| файл | что на схеме | модули |
|---|---|---|
| `01-vyzov-potok.drakon` | вызов СИПРОДа монитором МС «Дубна», входной поток, разбор ключевых слов блоков `*RED *NOT *SUB *IPO *HCH *END` | SCHEMA, GETSTR, RASKOM |
| `02-razbor-RED.drakon` | режим `*RED`: первая карта (FIRCAR), цикл карт, конец блока `*E` | FIRCAR, REDTXT |
| `03-dispetcher-SPAUD.drakon` | диспетчер управляющих последовательностей: число-префикс, буква после `*`, ошибка 10 | SCAN, SPAUD |
| `04-stranitsa-pechat.drakon` | модель страницы: строка номера, 60 строк текста, печать листа, `*P` | ENDPG, CHAPAG |
| `05-oshibki.drakon` | авария: `ERROR NR. n`, образ карты, останов | KLAIDA |
| `06-kak-est.drakon` | текст «как есть» и позиционирование: `*D`, `*nH`, `*nG`, `*nCc`, `*nFc`, `*nRF`, `*n(...)` | SPAUD |

## Файлы

* `<имя>.drakon` — исходник схемы на языке ДРАКОН (правила — `DRAKON.md`);
* `<имя>.txt` — рисунок схемы (эталонный генератор `tools/drakon_markup.py`);
* `pechat-katalog.txt` — все шесть схем, напечатанные на АЦПУ средствами
  самого СИПРОДа из личной библиотеки на диске 2348 (эмулятор dispak);
* `_katalog-markup.txt` — разметка `*RED` каталога (вход для `run.sh`).

## Как получить печать

```
tests/siprod/run.sh drakon/schemes/_katalog-markup.txt
```

## Как построить рисунок одной схемы

```
python3 tools/drakon_markup.py drakon/schemes/01-vyzov-potok.drakon
```
