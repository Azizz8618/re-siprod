# re-siprod

Восстановление описания СИПРОДа — системы подготовки документации для БЭСМ-6
(в основном на Фортране).  В СИПРОДе набраны описания ОС «Диспак» на сайте
[besm6.github.io](https://github.com/besm6/besm6.github.io/tree/master/wiki)
(файлы `*.txt`, начинающиеся с `*RED`).  Исходных текстов и документации
системы не сохранилось; входной язык восстановлен по объектному коду
библиотеки и опытам в эмуляторе.

Результат — **[SIPROD.md](SIPROD.md)**: справочник по режимам (`*RED`, `*NOT`,
`*SUB`, `*IPO`, `*HCH`), управляющим последовательностям и сообщениям об
ошибках.  Журнал опытов — [notes/commands.md](notes/commands.md).

Программа СИПРОДа разобрана в автокод БЕМШ: листинги всех модулей лежат в
[dis/](dis) (генерируются `make dis`), откомментированные тексты модулей -
в [text/](text) (`make be`, правила оформления - как в проекте re-dispak).

## Состав

| путь | что это |
|---|---|
| `siprod.bin`, `siprod.list` | образ личной библиотеки СИПРОДа и её оглавление |
| `tools/siprod_lib.py` | разбор библиотеки: каталог и объектные модули |
| `tools/siprod_dis.py` | дизассемблирование модулей в автокод БЕМШ (`disbesm6`) |
| `tools/siprod_be.py` | тексты БЕМШ модулей с комментариями (правила re-dispak) |
| `tools/siprod_asm.py` | обратная сборка команд БЕМШ и проверка разбора |
| `tools/siprod_perso.py` | запись библиотеки в PERSO на дисковом томе |
| `dtr/*.dtr`, `dtran-siprod.sh` | директивы детранслятора DTRAN для каждого модуля и сценарий его запуска |
| `tests/siprod/` | запуск СИПРОДа в эмуляторе, регрессионные примеры, проверка на документах вики |
| `tools/` | трассировка ветвей диспетчера, покрытие кода, разбор команд в документах |

## Использование

Нужны эмуляторы [dispak](https://github.com/leobru/dispak) и [dubna](https://github.com/besm6/dubna)
в `PATH`, а также [besmtool](https://github.com/besm6/besm6) и дизассемблер
БЕМШ `disbesm6`.

```
make            # листинги автокода dis/*.asm, тексты text/*.be, карты загрузки
make check      # проверка: разбор команд и обратная сборка совпадают
make test       # регрессионные примеры и документы вики (WIKI=каталог)
make test-perso # СИПРОД из библиотеки, записанной заново в PERSO
make coverage   # код, не пройденный ни одним примером
```

Отформатировать свой текст:

```
tests/siprod/run.sh файл              # всё после *EXECUTE: *RED ... *E / *END
tests/siprod/frag.sh 'строка' ...     # быстрый опыт с несколькими строками *RED
```

Дизассемблирование одного модуля:

```
tools/siprod_lib.py --dump SCAN       # что внутри модуля
tools/siprod_dis.py SCAN              # -> dis/SCAN.asm
tools/siprod_be.py SCAN               # -> text/SCAN.be
tools/siprod_asm.py SCAN              # проверка обратной сборки
tools/siprod_asm.py --emit=lib.bin    # пересборка библиотеки заново
```

Язык директив DTRAN:
[Dtran-instr.md](https://github.com/besm6/besm6.github.io/blob/master/wiki/Dtran-instr.md).

## Лицензия

MIT, см. [LICENSE.txt](LICENSE.txt).
