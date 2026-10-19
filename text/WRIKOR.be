***************************************************
* WRIKOR - МОДУЛЬ СИПРОДА
*   Источник: личная библиотека (PERSO, зона 2702,
*   том 2248), слово 6336 образа SIPROD.BIN
*   Длина при загрузке: 55 слов, 90 команд
*   Вход: WRIKOR
*   Выход: APNOTF:V2, APNOTF:V1A, APNOTF:V1A, APNOTF:V1A, APNOTF:V1B, 
*   APNOTF:V1F, APNOTF:PAGE1G+1, APNOTF:PAGE1G+1, APNOTF:PAGE1G+1, 
*   APNOTF:PAGE1G+1, CSTRIN:PUSH, CSTRIN:PUSH, CSTRIN:FRAME, 
*   CSTRIN:PUSHD+1, GOTOPO:ADDR, GOTOPO:FRAME, GOTOPO:FRAME+1, 
*   IPONUM:NUM2A, IPONUM:NUM2A+1, NAMENF:V7, NAMENF:WAIT, NAMENF:WAIT+1, 
*   NOTFOR:TYPEA, NOTFOR:NOTFD+1, NOTFOR:NOTFD+1, NOTFOR:NOTFD+1, 
*   ONEPLA:ADDR, ONEPLA:ADDR, ONEPLA:ADDR, ONEPLA:KORT1H+1, 
*   ONEPLA:KORT1H+1, ONEPLA:KORT1H+1, ONEPLA:KORT1H+1, ONEPLA:KORT1H+1, 
*   ONEPLA:KORT1H+1, ONEPLA:KORT1H+1, RASKOM:V9, RASKOM:V9, RASKOM:V9B, 
*   RASKOM:V1, RASKOM:V1, RASKOM:V1P, RASKOM:V20A+1, RASKOM:V20A+1, 
*   RASKOM:V20A+1, RASKOM:V20A+1, RASKOM:V20A+1, RASKOM:V20A+1, 
*   RASKOM:V20A+1, RASKOM:V20A+1, RASKOM:V20A+1, SCHEMA:BLOM, SCHEMA:V12E, 
*   SCHEMA:STANNE+1, SCHEMA:STANNE+1, SCHEMA:STANNE+1, SCHEMA:STANNE+1, 
*   SCHEMA:STANNE+1, TARNYB:KORT1A, TARNYB:TYPE1A, TARNYB:KORT1D, 
*   TARNYB:V1, TARNYB:V1, TARNYB:V1P+1, TARNYB:V1P+1, TARNYB:V1P+1, 
*   TARNYB:V1P+1, TARNYB:V1P+1, TARNYB:V1P+1, TARNYB:V1P+1, TARNYB:V1P+1, 
*   TARNYB:V1P+1, TARNYB:V1P+1, TARNYB:V1P+1, TWOPLA:V1, TWOPLA:V1, 
*   TWOPLA:V15, TWOPLA:V15, TWOPLA:V3B, TWOPLA:V3K, TWOPLA:INS26B+1, 
*   TWOPLA:INS26B+1, TWOPLA:INS26B+1, TWOPLA:INS26B+1, TWOPLA:INS26B+1, 
*   TWOPLA:INS26B+1, TWOPLA:INS26B+1, WRIHOR:PUSH, WRIHOR:PUSH, 
*   WRIHOR:ADDR, WRIHOR:FRAME, WRIHOR:ADDRE+1, WRIHOR:ADDRE+1, 
*   WRIIPO:IPONUA, WRIIPO:SCANEA, WRIIPO:V11C+1, WRIIPO:V11C+1, 
*   WRIIPO:V11C+1, WRIIPO:V11C+1, WRIIPO:V11C+1, WRILIN:V7, WRILIN:V7C, 
*   WRILIN:V7K, WRILIN:V7N+1, WRILIN:V7N+1, WRILIN:V7N+1, WRINUM:V0, 
*   WRINUM:V0D, WRINUM:NUM2D, WRINUM:NUM2I+1, WRINUM:NUM2I+1, 
*   WRINUM:NUM2I+1, WRITEH:ONEPLB, WRIVER:NUM3A, WRIVER:V3J+1, 
*   WRIVER:V3J+1, WRIVER:V3J+1, KORT1K (возврат через М12), 
*   KORT1K (возврат через М10)
*   ЗАПИСЬ В БУФЕР ВЫВОДА.
*   Внешние: KORT, ENDKOR, RNSYMB
*   Смещения в KORT: 14
*   Регистры: М7, М10, М12, М15, М16, М17
***************************************************
*
* СИМВОЛЫ МОДУЛЯ (номер - имя):
*   001 KORT
*   002 KORT14
*   003 ENDKOR
*   004 RNSYMB
*
WRIKOR   СТАРТ  0
         УИА    KORT1A(М16)             ,М16 := KORT1A
KORT1A   ПБ     RNSYMA                  ,переход на RNSYMA
         МОД    KORT1J                  ,мод.адрес по коду: KORT1J
         СЧ     0                       ,СМ := 0
         ЗП     3(М7)                   ,3 := СМ
         РЖА    '3'                     ,РЖ := '3'
KORT1B   МОД    KORT1K                  ,мод.адрес по коду: KORT1K
         СЧ     0                       ,СМ := 0
         ЗП     4(М7)                   ,4 := СМ
         СЧ     0(М7)                   ,СМ := 0(М7)
         ЗП     5(М7)                   ,5 := СМ
KORT1C   РЖА    '22'                    ,РЖ := '22'
         СЧ     2(М7)                   ,СМ := 2(М7)
KORT1D   РЖА    '3'                     ,РЖ := '3'
         МОДА   KORT14                  ,мод.адрес +1: KORT14
         ВЧ     0                       ,СМ -= 0
         СЛ     1(М7)                   ,СМ += 1(М7)
         ЗП     6(М7)                   ,6 := СМ
         ВЧ     4(М7)                   ,СМ -= 4(М7)
         РЖА    '22'                    ,РЖ := '22'
         ПЕ     KORT1C                  ,если СМ≠0 → KORT1C
         ПБ     KORT1D                  ,переход на KORT1D
         СЧ     6(М7)                   ,СМ := 6(М7)
         ЗП     4(М7)                   ,4 := СМ
         РЖА    '3'                     ,РЖ := '3'
         РЖА    '22'                    ,РЖ := '22'
         МОД    KORT1I                  ,мод.адрес по коду: KORT1I
         УИА    0(М16)                  ,М16 := 0
         СЧИМ   М16                     ,стек := М16, СМ := М16
V6       УИА    KORT1G(М16)             ,М16 := KORT1G
V6A      СЧИМ   М16                     ,стек := М16, СМ := М16
         УИА    KORT(М16)               ,М16 := KORT
         СЧИМ   М16                     ,стек := М16, СМ := М16
         УИА    KORT14(М16)             ,М16 := KORT14
         СЧИМ   М16                     ,стек := М16, СМ := М16
         УИА    KORT1H(М16)             ,М16 := KORT1H
V6B      СЧИМ   М16                     ,стек := М16, СМ := М16
RNSYMA   ПВ     RNSYMB(М15)             ,вызов через М15
         РЖА    '3'                     ,РЖ := '3'
         РЖА    '22'                    ,РЖ := '22'
         СЧ     5(М7)                   ,СМ := 5(М7)
         РЖА    '3'                     ,РЖ := '3'
         СЛ     4(М7)                   ,СМ += 4(М7)
KORT1E   ЗП     5(М7)                   ,5 := СМ
         МОДА   KORT14                  ,мод.адрес +1: KORT14
KORT1F   СЧ     0                       ,СМ := 0
         СЛ     4(М7)                   ,СМ += 4(М7)
         МОДА   KORT14                  ,мод.адрес +1: KORT14
KORT1G   ЗП     0                       ,0 := СМ
KORT1H   МОД    KORT1K                  ,мод.адрес по коду: KORT1K
         СЧ     0                       ,СМ := 0
         СЧИМ                           ,СЧИ + магазин
KORT1I   СЧ     5(М7)                   ,СМ := 5(М7)
KORT1J   РЖА    '22'                    ,РЖ := '22'
KORT1K   НТЖ    0(М17)                  ,СМ ^= 0(М17)
         ПО     V6                      ,если СМ=0 → V6
         ПБ     V6A                     ,переход на V6A
         МОДА   0                       ,мод.адрес +1: 0
         ПБ     V6B                     ,переход на V6B
         МОДА   0                       ,мод.адрес +1: 0
         СЧ     3(М7)                   ,СМ := 3(М7)
         РЖА    '3'                     ,РЖ := '3'
         СЛ     4(М7)                   ,СМ += 4(М7)
         ЗП     3(М7)                   ,3 := СМ
         МОД    KORT1K                  ,мод.адрес по коду: KORT1K
         СЧ     0                       ,СМ := 0
         ВЧ     5(М7)                   ,СМ -= 5(М7)
         ЗП     4(М7)                   ,4 := СМ
         РЖА    '22'                    ,РЖ := '22'
         ПВ     ENDKOR(М15)             ,вызов через М15
         ПБ     KORT1B                  ,переход на KORT1B
         МОДА   0                       ,мод.адрес +1: 0
         ПБ     KORT1E                  ,переход на KORT1E
         МОДА   0                       ,мод.адрес +1: 0
         УИИ    М10(М7)                 ,М10 := М7
         УИИ    М12(М16)                ,М12 := М16
         УИА    KORT1F(М7)              ,М7 := KORT1F
         ЗПМ    9(М7)                   ,ЗП + магазин: 9(М7)
         ЗПМ    8(М7)                   ,ЗП + магазин: 8(М7)
         ЗПМ    7(М7)                   ,ЗП + магазин: 7(М7)
         СЧИМ   М15                     ,стек := М15, СМ := М15
         СЧИМ   М10                     ,стек := М10, СМ := М10
         СЧИМ                           ,СЧИ + магазин
         РЖА    '3'                     ,РЖ := '3'
         РЖА    '2'                     ,РЖ := '2'
         ПБ     0(М12)                  ,переход через М12
         УИМ                            ,УИ + магазин
         УИМ    М7                      ,М7 := СМ + стек
         УИМ    М10                     ,М10 := СМ + стек
         ПБ     0(М10)                  ,переход через М10

