(*=u-*,p-*)
(* ТРАНСЛЯТОР СХЕМ ЯЗЫКА ДРАКОН ДЛЯ БЭСМ-6.
   Реализация на Паскале-Мониторе алгоритма эталонного генератора
   разметки (re-siprod, tools/drakon_markup.py): разбор текста схемы
   по отступам, перенос длинных подписей на строки, РАЗМЕР ИКОН -
   АДАПТИВНЫЙ к количеству текста (поле от 5 до ~60 знаков в
   строку, длинная подпись - в несколько строк равных долей);
   компоновка икон по колонкам: примитив - основной шампур и
   правые плечи развилок; СИЛУЭТ (по рис. 9 книги Паронджанова) -
   заголовок, под ним ВЕТКИ РЯДОМИ в колонки, верхняя шина от
   заголовка к щитам, снизу гребёнка-петля с возвратом в
   заголовок, ветка с КОНЦОМ - выход вниз;
   рисование
   ПОЛНОГО КОМПЛЕКТА ИКОН ЯЗЫКА ПО РИС. 4 КНИГИ В. Д. ПАРОНДЖАНОВА
   «ДРАКОН-СХЕМЫ» (И1-И25: полуовалы заголовка и конца, щит имени
   ветки, шестиугольник вопроса с валентной точкой, параллелограмм
   выбора, клин варианта, домик адреса, двойные стенки вставки,
   полка, формальные параметры, цикл ДЛЯ, вывод/ввод с полыми
   стрелками, пауза, период, пуск таймера, синхронизатор,
   параллельный процесс, комментарий в двойной рамке, боковые
   комментарии-скобки, петля цикла и гребёнка силуэта), возвраты
   плеч, слияние маршрутов и автоматическая петля цикла ДЛЯ;
   выдача разметки СИПРОДа *RED для печати схемы на АЦПУ средствами
   редактора.
   Ключевые слова: ЗАГОЛОВОК ВЕТКА ДЕЙСТВИЕ КОММЕНТАРИЙ ЕСЛИ ЦИКЛ
   ВЫБОР ВАРИАНТ АДРЕС КОНЕЦ ТО ИНАЧЕ ПОЛКА ПАРАМ ДЛЯ КДЛ ВЫВОД ВВОД
   ПАУЗА ПЕРИОД ПУСК СИНХРО ПАРАЛ ПКОМ ЛКОМ ПЕТЛЯ ГРЕБЕНКА ВСТАВКА.
   Понимаются и краткие формы (2 литеры - см. initkw), краткие
   распознаются после полных.
   Вход: карты после *EXECUTE.  Выход: разметка *RED.
   Особенности компилятора 15.1, учтённые в тексте:
   - идентификатор результата функции нельзя читать в выражениях
     (портится стек - STACK OVERRANGE); подсчёты ведутся в
     локальных переменных;
   - перед разбором нужно явно прочесть первую карту (parse
     обрабатывает текущую карту, а не читает новую). *)
program drakon(input, output);

const
  NN = 120;       (* узлов схемы *)
  TKW = 28;       (* число ключевых слов *)
  NAK = 23;       (* кратких форм ключевых слов (2 литеры) *)
  CWD = 72;       (* значимых позиций карты *)
  RMAX = 240;     (* строк рисунка *)
  CMAX = 128;     (* колонок рисунка: широкий формат АЦПУ-128 *)
  GAPR = 2;       (* зазор по вертикали *)
  GAPS = 4;       (* зазор между шампуром и плечом *)
  GAPB = 3;       (* пустых колонок между ветками силуэта *)
  MINW = 5;       (* минимальная ширина поля текста *)
  WMAXLINE = 30;  (* поле, до которого подпись держится в одну строку *)
  TRN = 60;       (* строк текста на странице широкого формата,
                     как TRN в redakt.pas: разметка рвёт страницу
                     командой *P там же, где её порвёт *DRK *)
  MXL = 12;       (* строк текста в иконе *)
  MXW = 40;       (* слов в подписи *)
  SM = 12;        (* веток силуэта не более *)

type
  carty = array [1..80] of char;
  (* упакованные массивы литер: экономят память (статика
     ограничена - 49К слов на компилятор 15.1) *)
  pcy = packed array [1..80] of char;
  prow = packed array [1..CMAX] of char;

var
  card: carty;
  eofin: boolean;

  kw: array [1..TKW] of pcy;
  kwl: array [1..TKW] of integer;
  ali: array [1..NAK] of packed array [1..2] of char;
  almap: array [1..NAK] of 1..TKW;

  nkind: array [1..NN] of integer;
  ntext: array [1..NN] of pcy;
  ntl: array [1..NN] of integer;
  nkid: array [1..NN] of integer;
  nbro: array [1..NN] of integer;
  ncnt: integer;
  nroot: integer;

  ix, iy, iw, ih: array [1..NN] of integer;
  nxt: array [1..NN] of integer;
  mainb: array [1..NN] of integer;
  brx: array [1..NN, 1..8] of integer;
  bry: array [1..NN, 1..8] of integer;
  brb: array [1..NN, 1..8] of integer;
  nbr: array [1..NN] of integer;

  pic: array [1..RMAX] of prow;
  rws: integer;

  flat: array [1..NN] of integer;
  nfl: integer;

  gtail, gy: integer;
  (* стек разбора вложенности; stl - последний узел уровня *)
  st: array [1..40] of integer;
  sti: array [1..40] of integer;
  stl: array [1..40] of integer;
  stn, last0: integer;

  (* перенос подписи: слова, строки, ширина поля *)
  wsp: array [1..MXW] of integer;
  wwp: array [1..MXW] of integer;
  nwd: integer;
  gtxt: pcy;
  wtx: array [1..MXL] of pcy;
  wln: array [1..MXL] of integer;
  nwl: integer;
  wwd: integer;

  ii, jj, kk, nn1, mm, qq: integer;

  (* силуэт: колонки веток рядом (рис. 9 книги) *)
  silnb: integer;                  (* число веток *)
  silb: array [1..SM] of integer;  (* узел-щит ветки *)
  silf0: array [1..SM] of integer; (* первый узел ветки в flat *)
  silf1: array [1..SM] of integer; (* последний узел ветки в flat *)
  silax: array [1..SM] of integer; (* ось колонки ветки *)
  siltail: array [1..SM] of integer; (* последний узел цепочки ветки *)
  silbot: array [1..SM] of integer;  (* нижняя строка ветки *)
  silhb: integer;                  (* строка верхней шины *)
  silbb: integer;                  (* строка нижней шины (петли) *)
  sillc: integer;                  (* колонка вертикали петли слева *)
  silmd: boolean;                  (* схема - силуэт *)

(* ---------------- печать и ввод ---------------- *)

procedure pasout(var a, b: char); fortran;

procedure outline(var r: prow);
begin
  pasout(r[1], r[CMAX])
end;

procedure getcard;
var
  i: integer;
begin
  if not eof(input) then begin
    for i := 1 to 80 do card[i] := ' ';
    readln(card);
    eofin := false
  end else
    eofin := true
end;

(* ---------------- ключевые слова и узлы ---------------- *)

procedure initkw;
begin
  kwl[1] := 9;
  kw[1][1] := 'З'; kw[1][2] := 'А'; kw[1][3] := 'Г';
  kw[1][4] := 'О'; kw[1][5] := 'Л'; kw[1][6] := 'О';
  kw[1][7] := 'В'; kw[1][8] := 'О'; kw[1][9] := 'К';
  kwl[2] := 5;
  kw[2][1] := 'В'; kw[2][2] := 'Е'; kw[2][3] := 'Т';
  kw[2][4] := 'К'; kw[2][5] := 'А';
  kwl[3] := 8;
  kw[3][1] := 'Д'; kw[3][2] := 'Е'; kw[3][3] := 'Й';
  kw[3][4] := 'С'; kw[3][5] := 'Т'; kw[3][6] := 'В';
  kw[3][7] := 'И'; kw[3][8] := 'Е';
  kwl[4] := 11;
  kw[4][1] := 'К'; kw[4][2] := 'О'; kw[4][3] := 'М';
  kw[4][4] := 'М'; kw[4][5] := 'Е'; kw[4][6] := 'Н';
  kw[4][7] := 'Т'; kw[4][8] := 'А'; kw[4][9] := 'Р';
  kw[4][10] := 'И'; kw[4][11] := 'Й';
  kwl[5] := 4;
  kw[5][1] := 'Е'; kw[5][2] := 'С'; kw[5][3] := 'Л'; kw[5][4] := 'И';
  kwl[6] := 4;
  kw[6][1] := 'Ц'; kw[6][2] := 'И'; kw[6][3] := 'К'; kw[6][4] := 'Л';
  kwl[7] := 5;
  kw[7][1] := 'В'; kw[7][2] := 'Ы'; kw[7][3] := 'Б';
  kw[7][4] := 'О'; kw[7][5] := 'Р';
  kwl[8] := 7;
  kw[8][1] := 'В'; kw[8][2] := 'А'; kw[8][3] := 'Р';
  kw[8][4] := 'И'; kw[8][5] := 'А'; kw[8][6] := 'Н'; kw[8][7] := 'Т';
  kwl[9] := 5;
  kw[9][1] := 'А'; kw[9][2] := 'Д'; kw[9][3] := 'Р';
  kw[9][4] := 'Е'; kw[9][5] := 'С';
  kwl[10] := 5;
  kw[10][1] := 'К'; kw[10][2] := 'О'; kw[10][3] := 'Н';
  kw[10][4] := 'Е'; kw[10][5] := 'Ц';
  kwl[11] := 2;
  kw[11][1] := 'Т'; kw[11][2] := 'О';
  kwl[12] := 5;
  kw[12][1] := 'И'; kw[12][2] := 'Н'; kw[12][3] := 'А';
  kw[12][4] := 'Ч'; kw[12][5] := 'Е';
  (* полный комплект икон рис. 4: ключевые слова 13-28 *)
  kwl[13] := 5;
  kw[13][1] := 'П'; kw[13][2] := 'О'; kw[13][3] := 'Л';
  kw[13][4] := 'К'; kw[13][5] := 'А';
  kwl[14] := 5;
  kw[14][1] := 'П'; kw[14][2] := 'А'; kw[14][3] := 'Р';
  kw[14][4] := 'А'; kw[14][5] := 'М';
  kwl[15] := 3;
  kw[15][1] := 'Д'; kw[15][2] := 'Л'; kw[15][3] := 'Я';
  kwl[16] := 3;
  kw[16][1] := 'К'; kw[16][2] := 'Д'; kw[16][3] := 'Л';
  kwl[17] := 5;
  kw[17][1] := 'В'; kw[17][2] := 'Ы'; kw[17][3] := 'В';
  kw[17][4] := 'О'; kw[17][5] := 'Д';
  kwl[18] := 4;
  kw[18][1] := 'В'; kw[18][2] := 'В'; kw[18][3] := 'О';
  kw[18][4] := 'Д';
  kwl[19] := 5;
  kw[19][1] := 'П'; kw[19][2] := 'А'; kw[19][3] := 'У';
  kw[19][4] := 'З'; kw[19][5] := 'А';
  kwl[20] := 6;
  kw[20][1] := 'П'; kw[20][2] := 'Е'; kw[20][3] := 'Р';
  kw[20][4] := 'И'; kw[20][5] := 'О'; kw[20][6] := 'Д';
  kwl[21] := 4;
  kw[21][1] := 'П'; kw[21][2] := 'У'; kw[21][3] := 'С';
  kw[21][4] := 'К';
  kwl[22] := 6;
  kw[22][1] := 'С'; kw[22][2] := 'И'; kw[22][3] := 'Н';
  kw[22][4] := 'Х'; kw[22][5] := 'Р'; kw[22][6] := 'О';
  kwl[23] := 5;
  kw[23][1] := 'П'; kw[23][2] := 'А'; kw[23][3] := 'Р';
  kw[23][4] := 'А'; kw[23][5] := 'Л';
  kwl[24] := 4;
  kw[24][1] := 'П'; kw[24][2] := 'К'; kw[24][3] := 'О';
  kw[24][4] := 'М';
  kwl[25] := 4;
  kw[25][1] := 'Л'; kw[25][2] := 'К'; kw[25][3] := 'О';
  kw[25][4] := 'М';
  kwl[26] := 5;
  kw[26][1] := 'П'; kw[26][2] := 'Е'; kw[26][3] := 'Т';
  kw[26][4] := 'Л'; kw[26][5] := 'Я';
  kwl[27] := 8;
  kw[27][1] := 'Г'; kw[27][2] := 'Р'; kw[27][3] := 'Е';
  kw[27][4] := 'Б'; kw[27][5] := 'Е'; kw[27][6] := 'Н';
  kw[27][7] := 'К'; kw[27][8] := 'А';
  kwl[28] := 7;
  kw[28][1] := 'В'; kw[28][2] := 'С'; kw[28][3] := 'Т';
  kw[28][4] := 'А'; kw[28][5] := 'В'; kw[28][6] := 'К';
  kw[28][7] := 'А';
  (* краткие формы ключевых слов: код из 2 литер -> канонический
     номер; распознаются в detect ПОСЛЕ полных слов, поэтому полная
     форма всегда понимается как полная; код не должен быть началом
     чужого слова (проверено программно); ТО ДЛЯ КДЛ ПКОМ ЛКОМ -
     уже короткие *)
almap[1] := 1;   ali[1][1] := 'З'; ali[1][2] := 'Г';  (* ЗГ ЗАГОЛОВОК *)
almap[2] := 2;   ali[2][1] := 'В'; ali[2][2] := 'Т';  (* ВТ ВЕТКА *)
almap[3] := 3;   ali[3][1] := 'Д'; ali[3][2] := 'С';  (* ДС ДЕЙСТВИЕ *)
almap[4] := 4;   ali[4][1] := 'К'; ali[4][2] := 'М';  (* КМ КОММЕНТАРИЙ *)
almap[5] := 5;   ali[5][1] := 'Е'; ali[5][2] := 'С';  (* ЕС ЕСЛИ *)
almap[6] := 6;   ali[6][1] := 'Ц'; ali[6][2] := 'И';  (* ЦИ ЦИКЛ *)
almap[7] := 7;   ali[7][1] := 'В'; ali[7][2] := 'Б';  (* ВБ ВЫБОР *)
almap[8] := 8;   ali[8][1] := 'В'; ali[8][2] := 'А';  (* ВА ВАРИАНТ *)
almap[9] := 9;   ali[9][1] := 'А'; ali[9][2] := 'Д';  (* АД АДРЕС *)
almap[10] := 10; ali[10][1] := 'К'; ali[10][2] := 'Ц'; (* КЦ КОНЕЦ *)
almap[11] := 12; ali[11][1] := 'И'; ali[11][2] := 'Н'; (* ИН ИНАЧЕ *)
almap[12] := 13; ali[12][1] := 'П'; ali[12][2] := 'Л'; (* ПЛ ПОЛКА *)
almap[13] := 14; ali[13][1] := 'П'; ali[13][2] := 'М'; (* ПМ ПАРАМ *)
almap[14] := 17; ali[14][1] := 'В'; ali[14][2] := 'Д'; (* ВД ВЫВОД *)
almap[15] := 18; ali[15][1] := 'В'; ali[15][2] := 'В'; (* ВВ ВВОД *)
almap[16] := 19; ali[16][1] := 'П'; ali[16][2] := 'З'; (* ПЗ ПАУЗА *)
almap[17] := 20; ali[17][1] := 'П'; ali[17][2] := 'Р'; (* ПР ПЕРИОД *)
almap[18] := 21; ali[18][1] := 'П'; ali[18][2] := 'У'; (* ПУ ПУСК *)
almap[19] := 22; ali[19][1] := 'С'; ali[19][2] := 'Н'; (* СН СИНХРО *)
almap[20] := 23; ali[20][1] := 'П'; ali[20][2] := 'П'; (* ПП ПАРАЛ *)
almap[21] := 26; ali[21][1] := 'П'; ali[21][2] := 'Т'; (* ПТ ПЕТЛЯ *)
almap[22] := 27; ali[22][1] := 'Г'; ali[22][2] := 'Р'; (* ГР ГРЕБЕНКА *)
almap[23] := 28; ali[23][1] := 'В'; ali[23][2] := 'С'  (* ВС ВСТАВКА *)
end;

(* распознавание ключевого слова: индекс или 0; ml - длина
   совпавшего слова (полного или краткого) - по ней отрезается
   подпись, для краткой формы она не равна kwl[индекса] *)
function detect(var s: carty; ln: integer; var ml: integer): integer;
var
  i, j, res: integer;
  ok: boolean;
begin
  res := 0;
  i := 1;
  while (i <= TKW) and (res = 0) do begin
    if (ln > 0) and (ln >= kwl[i]) then begin
      ok := true;
      j := 1;
      while (j <= kwl[i]) and ok do begin
        if s[j] <> kw[i][j] then
          ok := false;
        j := j + 1
      end;
      if ok then begin
        res := i;
        ml := kwl[i]
      end
    end;
    i := i + 1
  end;
  (* краткие формы - после полных: полная форма всегда понимается
     как полная *)
  i := 1;
  while (i <= NAK) and (res = 0) do begin
    if (ln >= 2) and (s[1] = ali[i][1]) and
       (s[2] = ali[i][2]) then begin
      res := almap[i];
      ml := 2
    end;
    i := i + 1
  end;
  detect := res
end;

(* новый узел схемы с привязкой к дереву по отступам *)
procedure newnode(k: integer; var s: carty; sl, ind, ln: integer);
var
  i: integer;
  done: boolean;
begin
  if ncnt >= NN then
    ncnt := NN;
  ncnt := ncnt + 1;
  nkind[ncnt] := k;
  ntl[ncnt] := ln;
  for i := 1 to ln do ntext[ncnt][i] := s[sl + i - 1];
  nkid[ncnt] := 0;
  nbro[ncnt] := 0;
  nbr[ncnt] := 0;
  nxt[ncnt] := 0;
  done := false;
  while (stn > 0) and (not done) do begin
    if sti[stn] >= ind then
      stn := stn - 1
    else
      done := true
  end;
  if stn = 0 then begin
    if nroot = 0 then
      nroot := ncnt
    else
      nbro[last0] := ncnt;
    last0 := ncnt
  end else begin
    if nkid[st[stn]] = 0 then
      nkid[st[stn]] := ncnt
    else
      nbro[stl[stn]] := ncnt;
    stl[stn] := ncnt
  end;
  (* контейнеры: ЕСЛИ ЦИКЛ ВЫБОР ВАРИАНТ ТО ИНАЧЕ ДЛЯ *)
  if (k = 5) or (k = 6) or (k = 7) or (k = 8) or
     (k = 11) or (k = 12) or (k = 15) then begin
    stn := stn + 1;
    st[stn] := ncnt;
    sti[stn] := ind
  end
end;

(* длина значимой части карты *)
function linelen: integer;
var
  i: integer;
begin
  linelen := 0;
  for i := 1 to CWD do
    if card[i] <> ' ' then
      linelen := i
end;

(* число ведущих пробелов карты.
   Результат функции нельзя читать в выражениях (ошибка
   компилятора 15.1 - порча стека), счёт в локальной j *)
function indent: integer;
var
  j: integer;
begin
  j := 0;
  while (j < CWD) and (card[j + 1] = ' ') do
    j := j + 1;
  indent := j
end;

(* пропуск пробелов и двоеточия после ключевого слова *)
procedure skiphead(var p: integer; ln: integer; var s: carty);
begin
  while (p <= ln) and (s[p] = ' ') do
    p := p + 1;
  if (p <= ln) and (s[p] = ':') then begin
    p := p + 1;
    while (p <= ln) and (s[p] = ' ') do
      p := p + 1
  end
end;

(* разбор текста схемы: карта за картой до конца ввода *)
procedure parse;
var
  i, ind, k, p, ln, ml: integer;
  txt: carty;
begin
  ncnt := 0;
  nroot := 0;
  last0 := 0;
  stn := 0;
  while not eofin do begin
    ind := indent;
    ln := linelen;
    if (ln > 0) and (card[ind + 1] <> '*') then begin
      for i := 1 to ln do txt[i] := card[ind + i];
      k := detect(txt, ln, ml);
      if k > 0 then begin
        p := ml + 1;
        skiphead(p, ln, txt);
        nn1 := 0;
        for i := p to ln do
          if txt[i] <> ' ' then
            nn1 := i - p + 1;
        newnode(k, txt, p, ind, nn1)
      end else begin
        (* неизвестное слово: текст после первого слова *)
        p := 1;
        while (p <= ln) and (txt[p] <> ' ') and
              (txt[p] <> ':') do
          p := p + 1;
        skiphead(p, ln, txt);
        nn1 := 0;
        for i := p to ln do
          if txt[i] <> ' ' then
            nn1 := i - p + 1;
        newnode(0, txt, p, ind, nn1)
      end
    end;
    getcard
  end
end;

(* ---------------- иконы ---------------- *)

(* вид иконы по рис. 4 книги Паронджанова:
   0 действие (прямоугольник), 1 заголовок (полуовал), 2 имя ветки
   (щит), 3 вопрос (шестиугольник), 4 конец (полуовал), 5 адрес
   (домик), 6 выбор (параллелограмм), 7 вариант (прямоугольник
   с клином), 8 комментарий (двойная рамка с полуовалом), 9 полка,
   10 формальные параметры, 11 начало цикла ДЛЯ, 12 конец цикла ДЛЯ,
   13 вывод, 14 ввод, 15 пауза, 16 период, 17 пуск таймера,
   18 синхронизатор, 19 параллельный процесс, 20 правый
   комментарий, 21 левый комментарий, 22 петля цикла, 23 петля
   силуэта (гребёнка), 24 вставка *)
function kindof(n: integer): integer;
var
  k, res: integer;
begin
  k := nkind[n];
  res := 0;
  if k = 1 then
    res := 1
  else if k = 2 then
    res := 2
  else if (k = 5) or (k = 6) then
    res := 3
  else if k = 10 then
    res := 4
  else if k = 9 then
    res := 5
  else if k = 7 then
    res := 6
  else if k = 8 then
    res := 7
  else if k = 4 then
    res := 8
  else if k = 13 then
    res := 9
  else if k = 14 then
    res := 10
  else if k = 15 then
    res := 11
  else if k = 16 then
    res := 12
  else if k = 17 then
    res := 13
  else if k = 18 then
    res := 14
  else if k = 19 then
    res := 15
  else if k = 20 then
    res := 16
  else if k = 21 then
    res := 17
  else if k = 22 then
    res := 18
  else if k = 23 then
    res := 19
  else if k = 24 then
    res := 20
  else if k = 25 then
    res := 21
  else if k = 26 then
    res := 22
  else if k = 27 then
    res := 23
  else if k = 28 then
    res := 24;
  kindof := res
end;

procedure put(x, y: integer; c: char);
begin
  if (y >= 1) and (y <= RMAX) and (x >= 1) and (x <= CMAX) then
    pic[y][x] := c
end;

(* текст в поле ширины fw с позиции x, строка r; центрирование
   как в эталоне: лишний пробел при нечётных поле и остатке
   ставится слева *)
procedure ctext(x, fw, r: integer; var t: pcy; tl: integer);
var
  i, left: integer;
begin
  left := (fw - tl) div 2;
  if (odd(fw - tl)) and (odd(fw)) then
    left := left + 1;
  for i := 1 to tl do
    put(x + left + i - 1, r, t[i])
end;

procedure dash(x, y, ln: integer; c: char);
var
  i: integer;
begin
  for i := 1 to ln do
    put(x + i - 1, y, c)
end;

(* горизонтальная грань: угол, тире, угол *)
procedure hrun(x, y, ln: integer; lc, rc: char);
begin
  put(x, y, lc);
  dash(x + 1, y, ln - 2, '-');
  put(x + ln - 1, y, rc)
end;

(* разложить подпись gtxt длиной tl на строки wtx/wln;
   ширина поля - wwd *)
procedure wraptl(tl: integer);
var
  i, j, cur: integer;
  nl: boolean;
begin
  nwl := 0;
  cur := 0;
  for i := 1 to nwd do begin
    (* НЕ писать «(cur = 0) or (wln[cur] + ... > wwd)»: компилятор 15.1
       не гарантирует короткое замыкание, при cur = 0 читается и
       пишется wln[0]/wtx[0] вне массива - портятся соседние
       переменные, слова подписи теряются *)
    nl := true;
    if cur > 0 then
      if wln[cur] + 1 + wwp[i] <= wwd then
        nl := false;
    if nl then begin
      cur := cur + 1;
      wln[cur] := 0
    end else begin
      wln[cur] := wln[cur] + 1;
      wtx[cur][wln[cur]] := ' '
    end;
    for j := 1 to wwp[i] do begin
      wtx[cur][wln[cur] + j] := gtxt[wsp[i] + j - 1];
    end;
    wln[cur] := wln[cur] + wwp[i]
  end;
  nwl := cur;
  if nwl = 0 then begin
    nwl := 1;
    wln[1] := 0
  end
end;

(* слова подписи: wsp/wwp, самое длинное слово -> wwd *)
procedure splitw(tl: integer);
var
  i: integer;
begin
  nwd := 0;
  i := 1;
  while i <= tl do begin
    while (i <= tl) and (gtxt[i] = ' ') do
      i := i + 1;
    if i <= tl then begin
      nwd := nwd + 1;
      wsp[nwd] := i;
      while (i <= tl) and (gtxt[i] <> ' ') do
        i := i + 1;
      wwp[nwd] := i - wsp[nwd];
      if wwp[nwd] > wwd then
        wwd := wwp[nwd]
    end
  end
end;

(* подпись узла в gtxt, разбор на слова, ширина поля wwd:
   АДАПТИВНО к количеству текста - короткая подпись даёт узкую
   икону (поле от 5 знаков), подпись до WMAXLINE держится в одну
   строку, длинная делится на равные доли.  Поле однострочной
   подписи той же чётности, что и подпись: пробелов слева и
   справа от надписи поровну (ctext при нечётном остатке кладёт
   лишний пробел влево - при нечётном поле неравенство было бы
   в каждой второй иконе).  Поле многострочной подписи нечётное:
   одна средняя колонка, вершины клиньев и острия прилегают к
   оси шампура ровно *)
procedure settext(n: integer);
var
  i, tl, L, tg: integer;
begin
  tl := ntl[n];
  for i := 1 to tl do gtxt[i] := ntext[n][i];
  wwd := MINW;
  splitw(tl);
  if tl > WMAXLINE then begin
    (* длинная подпись: строки равных долей *)
    L := (tl + WMAXLINE - 1) div WMAXLINE;
    tg := (tl + L - 1) div L;
    if tg > wwd then
      wwd := tg
  end else if tl > wwd then
    wwd := tl;
  if tl <= WMAXLINE then begin
    if odd(wwd - tl) then
      wwd := wwd + 1
  end else if (wwd mod 2) = 0 then
    wwd := wwd + 1
end;

(* подогнать поле под подпись: слова могут не упаковаться в
   намеченные строки - расширять поле, пока перенос не уложится *)
procedure fittext(n: integer);
var
  tl, L: integer;
begin
  settext(n);
  tl := ntl[n];
  L := 1;
  if tl > WMAXLINE then
    L := (tl + WMAXLINE - 1) div WMAXLINE;
  wraptl(tl);
  while (nwl > L) and (wwd < WMAXLINE + 12) do begin
    wwd := wwd + 2;
    wraptl(tl)
  end
end;

(* полная ширина иконы узла n *)
function iconw(n: integer): integer;
var
  k, tl, wd: integer;
begin
  k := kindof(n);
  tl := ntl[n];
  if k = 4 then begin
    (* конец: маленький полуовал; без подписи печатается слово
       КОНЕЦ - мерим его 5 литер.  Поле той же чётности, что и
       подпись: пробелов слева и справа поровну *)
    if tl = 0 then
      tl := 5;
    wd := tl + 2;
    if wd < 7 then
      wd := 7;
    if odd(wd - tl) then
      wd := wd + 1;
    iconw := wd
  end else if k = 22 then
    iconw := 18
  else if k = 23 then
    iconw := 30
  else begin
    fittext(n);
    if k = 3 then
      wd := wwd + 4
    else if k = 6 then
      (* параллелограмм: сдвиг верха равен числу строк + 1 *)
      wd := wwd + 3 + nwl
    else if (k = 8) or (k = 17) or (k = 21) or (k = 24) then
      wd := wwd + 4
    else if (k = 10) or (k = 16) or (k = 18) then
      wd := wwd + 6
    else if (k = 13) or (k = 14) then
      wd := wwd + 10
    else if k = 19 then
      wd := wwd + 12
    else if k = 20 then
      wd := wwd + 3
    else
      wd := wwd + 2;
    iconw := wd
  end
end;

(* формы икон: ДЕЙСТВИЕ, ЗАГОЛОВОК, ВОПРОС, КОНЕЦ *)
procedure picon1(k, n, x, y, w: integer);
var
  i, r, f, s, m: integer;
begin
  if k = 0 then begin
    (* ДЕЙСТВИЕ: прямоугольник *)
    ih[n] := nwl + 2;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    hrun(x, y + nwl + 1, w, '+', '+')
  end else if k = 1 then begin
    (* ЗАГОЛОВОК: полуовал И1 *)
    ih[n] := nwl + 2;
    hrun(x, y, w, '.', '.');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '(');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, ')')
    end;
    hrun(x, y + nwl + 1, w, '''', '''')
  end else if k = 3 then begin
    (* ВОПРОС: шестиугольник И4, валентная точка справа -
       линия плеча примыкает к стене на середине высоты *)
    ih[n] := nwl + 4;
    hrun(x + 2, y, wwd, '+', '+');
    put(x + 1, y + 1, '(');
    put(x + w - 2, y + 1, ')');
    for i := 1 to nwl do begin
      r := y + 1 + i;
      put(x, r, '|');
      ctext(x + 1, wwd + 2, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    put(x + 1, y + nwl + 2, '(');
    put(x + w - 2, y + nwl + 2, ')');
    hrun(x + 2, y + nwl + 3, wwd, '+', '+')
  end else if k = 4 then begin
    (* КОНЕЦ: малый полуовал И2 *)
    ih[n] := 3;
    hrun(x, y, w, '.', '.');
    put(x, y + 1, '(');
    ctext(x + 1, w - 2, y + 1, wtx[1], wln[1]);
    put(x + w - 1, y + 1, ')');
    hrun(x, y + 2, w, '''', '''')
  end
end;

(* формы икон: ВЕТКА, ВЫБОР, ВАРИАНТ *)
procedure picon2(k, n, x, y, w: integer);
var
  i, r, f, s, m: integer;
begin
  if k = 2 then begin
    (* ИМЯ ВЕТКИ: щит И7 - стены сходятся к нижней вершине *)
    ih[n] := nwl + 3;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    put(x + 1, y + nwl + 1, '(');
    put(x + w - 2, y + nwl + 1, ')');
    put(x + 2, y + nwl + 2, '(');
    put(x + w - 3, y + nwl + 2, ')');
    dash(x + 3, y + nwl + 2, w - 6, '_')
  end else if k = 6 then begin
    (* ВЫБОР: параллелограмм И5, верх сдвинут вправо *)
    s := nwl + 1;
    ih[n] := nwl + 2;
    hrun(x + s, y, wwd + 2, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      f := s - i;
      put(x + f, r, '/');
      ctext(x + f + 1, wwd, r, wtx[i], wln[i]);
      put(x + f + wwd + 1, r, '/')
    end;
    hrun(x, y + nwl + 1, wwd + 2, '+', '+')
  end else if k = 7 then begin
    (* ВАРИАНТ: прямоугольник с клином И6 *)
    ih[n] := nwl + 4;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    hrun(x, y + nwl + 1, w, '+', '+');
    put(x + 1, y + nwl + 2, '(');
    put(x + w - 2, y + nwl + 2, ')');
    put(x + 2, y + nwl + 3, '(');
    put(x + w - 3, y + nwl + 3, ')');
    dash(x + 3, y + nwl + 3, w - 6, '_')
  end
end;

(* формы икон: АДРЕС, КОММЕНТАРИЙ, ПОЛКА *)
procedure picon3(k, n, x, y, w: integer);
var
  i, r, f, s, m: integer;
begin
  if k = 5 then begin
    (* АДРЕС: домик И8 с треугольной крышей *)
    m := w div 2;
    ih[n] := nwl + 4;
    put(x + m - 1, y, '(');
    put(x + m + 1, y, ')');
    put(x + m - 2, y + 1, '(');
    put(x + m + 2, y + 1, ')');
    hrun(x, y + 2, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + 2 + i;
      put(x, r, '|');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    hrun(x, y + nwl + 3, w, '+', '+')
  end else if k = 8 then begin
    (* КОММЕНТАРИЙ И21: двойная рамка, внутри полуовал *)
    ih[n] := nwl + 4;
    hrun(x, y, w, '+', '+');
    put(x, y + 1, '|');
    put(x + 1, y + 1, '.');
    dash(x + 2, y + 1, wwd, '-');
    put(x + wwd + 2, y + 1, '.');
    put(x + w - 1, y + 1, '|');
    for i := 1 to nwl do begin
      r := y + 1 + i;
      put(x, r, '|');
      put(x + 1, r, '(');
      ctext(x + 2, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 2, r, ')');
      put(x + w - 1, r, '|')
    end;
    put(x, y + nwl + 2, '|');
    put(x + 1, y + nwl + 2, '''');
    dash(x + 2, y + nwl + 2, wwd, '-');
    put(x + wwd + 2, y + nwl + 2, '''');
    put(x + w - 1, y + nwl + 2, '|');
    hrun(x, y + nwl + 3, w, '+', '+')
  end else if k = 10 then begin
    (* ФОРМАЛЬНЫЕ ПАРАМЕТРЫ И11: прямоугольник, точка слева *)
    ih[n] := nwl + 2;
    hrun(x + 2, y, wwd + 2, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x + 2, r, '|');
      ctext(x + 3, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 3, r, '|')
    end;
    hrun(x + 2, y + nwl + 1, wwd + 2, '+', '+');
    r := y + (nwl + 2) div 2;
    put(x, r, '-');
    put(x + 1, r, '-')
  end else if k = 9 then begin
    (* ПОЛКА И10: прямоугольник с горизонтальной серединой *)
    ih[n] := nwl + 4;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    hrun(x, y + nwl + 1, w, '+', '+');
    put(x, y + nwl + 2, '|');
    put(x + w - 1, y + nwl + 2, '|');
    hrun(x, y + nwl + 3, w, '+', '+')
  end
end;

(* формы икон: ЦИКЛ ДЛЯ, КДЛ, ВЫВОД, ВВОД *)
procedure picon4(k, n, x, y, w: integer);
var
  i, r, f, s, m: integer;
begin
  if k = 11 then begin
    (* НАЧАЛО ЦИКЛА ДЛЯ И12: срезаны верхние угла *)
    ih[n] := nwl + 2;
    hrun(x + 1, y, wwd, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      if i = 1 then begin
        put(x, r, '(');
        put(x + w - 1, r, ')')
      end else begin
        put(x, r, '|');
        put(x + w - 1, r, '|')
      end;
      ctext(x + 1, wwd, r, wtx[i], wln[i])
    end;
    hrun(x, y + nwl + 1, w, '+', '+')
  end else if k = 12 then begin
    (* КОНЕЦ ЦИКЛА ДЛЯ И13: срезаны нижние угла *)
    ih[n] := nwl + 2;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      if i = nwl then begin
        put(x, r, '(');
        put(x + w - 1, r, ')')
      end else begin
        put(x, r, '|');
        put(x + w - 1, r, '|')
      end;
      ctext(x + 1, wwd, r, wtx[i], wln[i])
    end;
    hrun(x + 1, y + nwl + 1, wwd, '+', '+')
  end else if k = 13 then begin
    (* ВЫВОД И14: прямоугольник, справа полая стрелка наружу *)
    ih[n] := nwl + 2;
    hrun(x + 4, y, wwd + 2, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x + 4, r, '|');
      ctext(x + 5, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 5, r, '|')
    end;
    hrun(x + 4, y + nwl + 1, wwd + 2, '+', '+');
    r := y + (nwl + 2) div 2;
    dash(x + wwd + 6, r, 3, '=');
    put(x + wwd + 9, r, '>')
  end else if k = 14 then begin
    (* ВВОД И15: прямоугольник, справа стрелка внутрь *)
    ih[n] := nwl + 2;
    hrun(x + 4, y, wwd + 2, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x + 4, r, '|');
      ctext(x + 5, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 5, r, '|')
    end;
    hrun(x + 4, y + nwl + 1, wwd + 2, '+', '+');
    r := y + (nwl + 2) div 2;
    put(x + wwd + 6, r, '<');
    dash(x + wwd + 7, r, 3, '=')
  end
end;

(* формы икон: ПАУЗА, ПЕРИОД, ПУСК, СИНХРОНИЗАТОР *)
procedure picon5(k, n, x, y, w: integer);
var
  i, r, f, s, m: integer;
begin
  if k = 15 then begin
    (* ПАУЗА И16: трапеция, сужающаяся вниз *)
    ih[n] := nwl + 3;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    put(x + 1, y + nwl + 1, '(');
    put(x + w - 2, y + nwl + 1, ')');
    hrun(x + 2, y + nwl + 2, wwd - 2, '+', '+')
  end else if k = 16 then begin
    (* ПЕРИОД И17: трапеция вниз, валентные точки по бокам *)
    ih[n] := nwl + 3;
    hrun(x + 2, y, wwd + 2, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x + 2, r, '|');
      ctext(x + 3, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 3, r, '|')
    end;
    put(x + 3, y + nwl + 1, '(');
    put(x + wwd + 2, y + nwl + 1, ')');
    hrun(x + 4, y + nwl + 2, wwd - 2, '+', '+');
    r := y + (nwl + 3) div 2;
    put(x, r, '-');
    put(x + 1, r, '-');
    put(x + wwd + 4, r, '-');
    put(x + wwd + 5, r, '-')
  end else if k = 17 then begin
    (* ПУСК ТАЙМЕРА И18: трапеция вниз с двойными стенками *)
    ih[n] := nwl + 3;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      put(x + 1, r, '|');
      ctext(x + 2, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 2, r, '|');
      put(x + wwd + 3, r, '|')
    end;
    put(x + 1, y + nwl + 1, '(');
    put(x + 2, y + nwl + 1, '(');
    put(x + wwd + 1, y + nwl + 1, ')');
    put(x + wwd + 2, y + nwl + 1, ')');
    hrun(x + 3, y + nwl + 2, wwd - 2, '+', '+')
  end else if k = 18 then begin
    (* СИНХРОНИЗАТОР И19: трапеция вниз, точка справа *)
    ih[n] := nwl + 3;
    hrun(x + 2, y, wwd + 2, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x + 2, r, '|');
      ctext(x + 3, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 3, r, '|')
    end;
    put(x + 3, y + nwl + 1, '(');
    put(x + wwd + 2, y + nwl + 1, ')');
    hrun(x + 4, y + nwl + 2, wwd - 2, '+', '+');
    r := y + (nwl + 3) div 2;
    put(x + wwd + 4, r, '-');
    put(x + wwd + 5, r, '-')
  end
end;

(* формы икон: ПАРАЛПРОЦЕСС, БОКОВЫЕ КОММЕНТАРИИ, ПЕТЛИ, ВСТАВКА *)
procedure picon6(k, n, x, y, w: integer);
var
  i, r, f, s, m: integer;
begin
  if k = 19 then begin
    (* ПАРАЛЛЕЛЬНЫЙ ПРОЦЕСС И20: прямоугольник со сдвинутым
       вверх-вправо вторым *)
    ih[n] := nwl + 3;
    hrun(x + wwd + 8, y, 4, '+', '+');
    hrun(x + 5, y + 1, wwd + 2, '+', '+');
    put(x + w - 1, y + 1, '|');
    for i := 1 to nwl do begin
      r := y + 1 + i;
      put(x + 5, r, '|');
      ctext(x + 6, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 6, r, '|')
    end;
    put(x + w - 1, y + 2, '+');
    dash(x + wwd + 7, y + 2, 4, '-');
    hrun(x + 5, y + nwl + 2, wwd + 2, '+', '+')
  end else if k = 20 then begin
    (* ПРАВЫЙ КОММЕНТАРИЙ И22: скобка слева от текста *)
    ih[n] := nwl;
    for i := 1 to nwl do begin
      r := y + i - 1;
      put(x, r, '(');
      ctext(x + 2, wwd, r, wtx[i], wln[i])
    end
  end else if k = 21 then begin
    (* ЛЕВЫЙ КОММЕНТАРИЙ И23: текст, скобка справа *)
    ih[n] := nwl;
    for i := 1 to nwl do begin
      r := y + i - 1;
      ctext(x + 2, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 2, r, ')')
    end
  end else if k = 22 then begin
    (* ПЕТЛЯ ЦИКЛА И24: остриё упирается в вертикаль *)
    ih[n] := 2;
    put(x + 9, y, '|');
    put(x + 10, y, '<');
    dash(x + 11, y, 7, '-');
    put(x + w - 1, y, '+');
    put(x + 9, y + 1, '|');
    put(x + w - 1, y + 1, '|')
  end else if k = 23 then begin
    (* ПЕТЛЯ СИЛУЭТА И25: остриё в вертикаль, зубцы гребёнки *)
    ih[n] := 2;
    put(x + 15, y, '|');
    put(x + 16, y, '<');
    dash(x + 17, y, 13, '-');
    put(x + 15, y + 1, '|');
    put(x + 19, y + 1, '|');
    put(x + 23, y + 1, '|');
    put(x + 27, y + 1, '|');
    put(x + 29, y + 1, '|')
  end else if k = 24 then begin
    (* ВСТАВКА И9: прямоугольник с двойными стенками *)
    ih[n] := nwl + 2;
    hrun(x, y, w, '+', '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      put(x + 1, r, '|');
      ctext(x + 2, wwd, r, wtx[i], wln[i]);
      put(x + wwd + 2, r, '|');
      put(x + wwd + 3, r, '|')
    end;
    hrun(x, y + nwl + 1, w, '+', '+')
  end
end;

(* рисование иконы узла n с центром на колонке col, верх row;
   формы разбиты на picon1..picon6: у компилятора 15.1 предел
   числа команд в блоке *)
procedure makeicon(n, col, row: integer);
var
  k, w, tl, i, x, y: integer;
begin
  k := kindof(n);
  tl := ntl[n];
  if (k = 4) and (tl = 0) then begin
    (* конец без подписи печатает слово КОНЕЦ *)
    gtxt[1] := 'к'; gtxt[2] := 'о'; gtxt[3] := 'н';
    gtxt[4] := 'е'; gtxt[5] := 'ц'
  end;
  w := iconw(n);
  (* строки подписи: поле и перенос подогнаны в iconw/fittext;
     у конца - одна строка *)
  if k = 4 then begin
    tl := ntl[n];
    if tl = 0 then
      tl := 5;
    nwl := 1;
    wln[1] := tl;
    for i := 1 to tl do wtx[1][i] := gtxt[i]
  end;
  x := col - w div 2;
  ix[n] := x;
  iw[n] := w;
  iy[n] := row;
  y := row;
  if (k = 2) or (k = 6) or (k = 7) then
    picon2(k, n, x, y, w)
  else if (k = 5) or (k = 8) or (k = 9) or (k = 10) then
    picon3(k, n, x, y, w)
  else if (k = 11) or (k = 12) or (k = 13) or (k = 14) then
    picon4(k, n, x, y, w)
  else if (k = 15) or (k = 16) or (k = 17) or (k = 18) then
    picon5(k, n, x, y, w)
  else if k >= 19 then
    picon6(k, n, x, y, w)
  else
    picon1(k, n, x, y, w)
end;

(* ---------------- компоновка ---------------- *)

(* первый потомок основного пути: у ЦИКЛа сами потомки,
   у прочих - потомки ветки ТО *)
function mainkids(n: integer): integer;
var
  ch, res: integer;
  done: boolean;
begin
  res := 0;
  ch := 0;
  if (nkind[n] = 6) or (nkind[n] = 15) then
    res := nkid[n]
  else
    ch := nkid[n];
  done := false;
  while (ch <> 0) and (not done) do begin
    if nkind[ch] = 11 then begin
      res := nkid[ch];
      done := true
    end else
      ch := nbro[ch]
  end;
  mainkids := res
end;

(* строка бокового выхода иконы: у вопроса - валентная точка
   на середине высоты (правая стена), у остальных - нижняя грань *)
function exrow(n: integer): integer;
var
  r: integer;
begin
  r := iy[n] + ih[n] - 1;
  if (nkind[n] = 5) or (nkind[n] = 6) then
    r := iy[n] + ih[n] div 2;
  exrow := r
end;

(* собрать правые плечи: ИНАЧЕ (минус - начало с потомков),
   ВАРИАНТ (плюс - икона и потомки) *)
procedure sidebranches(n: integer);
var
  ch: integer;
begin
  nbr[n] := 0;
  ch := nkid[n];
  while ch <> 0 do begin
    if nkind[ch] = 12 then begin
      if nkid[ch] <> 0 then begin
        nbr[n] := nbr[n] + 1;
        brx[n, nbr[n]] := -nkid[ch]
      end
    end else if nkind[ch] = 8 then begin
      if (ntl[ch] > 0) or (nkid[ch] <> 0) then begin
        nbr[n] := nbr[n] + 1;
        brx[n, nbr[n]] := ch
      end
    end;
    ch := nbro[ch]
  end
end;

(* ширина самой широкой иконы цепочки *)
function chainw(first: integer): integer;
var
  ch, w, mw: integer;
begin
  mw := 0;
  ch := first;
  while ch <> 0 do begin
    w := iconw(ch);
    if w > mw then
      mw := w;
    ch := nbro[ch]
  end;
  chainw := mw
end;

(* разложить цепочку по шампуру col от строки row;
   gy - нижняя свободная строка, gtail - последний узел цепочки;
   one <> 0 - разложить только первый узел, без братьев
   (икона ВАРИАНТа раскладывается отдельно от своих потомков) *)
procedure layout(first, col, row, tail, one: integer);
var
  node, y, rx, rail, wmax, ry, row0, mk, b, k, yb: integer;
  f0: integer;
begin
  y := row;
  node := first;
  while node <> 0 do begin
    if tail <> 0 then
      nxt[tail] := node;
    nfl := nfl + 1;
    flat[nfl] := node;
    makeicon(node, col, y);
    y := y + ih[node] + GAPR;
    mk := mainkids(node);
    if mk <> 0 then begin
      layout(mk, col, y, node, 0);
      if gy > y then
        y := gy;
      mainb[node] := gy - GAPR;
      tail := gtail
    end else begin
      mainb[node] := iy[node] + ih[node];
      tail := node
    end;
    sidebranches(node);
    if nbr[node] > 0 then begin
      row0 := exrow(node);
      rx := col + iw[node] div 2 + GAPS;
      ry := row0 + 1;
      for b := 1 to nbr[node] do begin
        if brx[node, b] < 0 then begin
          f0 := -brx[node, b];
          wmax := chainw(f0)
        end else begin
          f0 := brx[node, b];
          wmax := iconw(f0);
          if nkid[f0] <> 0 then begin
            k := chainw(nkid[f0]);
            if k > wmax then
              wmax := k
          end
        end;
        rail := rx + wmax div 2;
        if brx[node, b] < 0 then
          layout(f0, rail, ry, 0, 0)
        else begin
          layout(f0, rail, ry, 0, 1);
          if nkid[f0] <> 0 then
            layout(nkid[f0], rail, gy, f0, 0)
        end;
        brx[node, b] := rail;
        bry[node, b] := ry;
        yb := gy - GAPR;
        brb[node, b] := yb;
        if yb + GAPR > y then
          y := yb + GAPR;
        rx := rail + (wmax + 1) div 2 + GAPS
      end
    end;
    node := nbro[node];
    if one <> 0 then
      node := 0
  end;
  gtail := tail;
  gy := y
end;

(* ---------------- рисунок ---------------- *)

(* вертикальные линии между иконами одной цепочки *)
procedure connectors;
var
  i, a, b, cl, r: integer;
begin
  for i := 1 to nfl do begin
    a := flat[i];
    if nxt[a] <> 0 then begin
      b := nxt[a];
      cl := ix[a] + iw[a] div 2;
      for r := iy[a] + ih[a] to iy[b] - 1 do
        put(cl, r, '|')
    end
  end
end;

(* шина выхода вправо к осям плеч; линия начинается от самой
   правой литеры иконы в строке выхода (у параллелограмма низ
   уже верха, у вопроса стена на середине высоты) *)
procedure busout;
var
  i, a, b, r, cl, x, row0, lastr, wx: integer;
begin
  for i := 1 to nfl do begin
    a := flat[i];
    if nbr[a] > 0 then begin
      cl := ix[a] + iw[a] div 2;
      row0 := exrow(a);
      lastr := brx[a, 1];
      for b := 2 to nbr[a] do
        if brx[a, b] > lastr then
          lastr := brx[a, b];
      wx := ix[a];
      for x := ix[a] to ix[a] + iw[a] - 1 do
        if pic[row0][x] <> ' ' then
          wx := x;
      for x := wx + 1 to lastr - 1 do
        put(x, row0, '-');
      for b := 1 to nbr[a] do begin
        put(brx[a, b], row0, '+');
        for r := row0 + 1 to bry[a, b] - 1 do
          put(brx[a, b], r, '|')
      end
    end
  end
end;

(* возврат правых плеч на основную вертикаль *)
procedure mergeback;
var
  i, a, b, r, x, cl, base, mr: integer;
  stop: boolean;
begin
  for i := 1 to nfl do begin
    a := flat[i];
    if nbr[a] > 0 then begin
      cl := ix[a] + iw[a] div 2;
      base := mainb[a];
      for b := 1 to nbr[a] do
        if brb[a, b] > base then
          base := brb[a, b];
      (* слияние не рисуется, если икона основной цепочки
         начинается ровно на строке base *)
      stop := false;
      for r := 1 to nfl do
        if flat[r] <> a then
          if (ix[flat[r]] + iw[flat[r]] div 2 = cl) and
             (iy[flat[r]] = base) then
            stop := true;
      if not stop then begin
        for b := 1 to nbr[a] do
          for r := brb[a, b] to base - 1 do
            put(brx[a, b], r, '|');
        mr := brx[a, 1];
        for b := 2 to nbr[a] do
          if brx[a, b] > mr then
            mr := brx[a, b];
        for x := cl + 1 to mr - 1 do
          put(x, base, '-');
        for b := 1 to nbr[a] do
          put(brx[a, b], base, '+');
        put(cl, base, '+')
      end
    end
  end
end;

(* петля цикла ДЛЯ: возврат от КДЛ к вертикали под ДЛЯ (икона
   И24): от правой стены КДЛ на середине высоты - вправо, вверх
   и остриём в вертикаль между ДЛЯ и телом цикла *)
procedure forloop;
var
  i, nd, kd, ch, cl, ax, r1, r2, wx, xx, rr: integer;
begin
  for i := 1 to nfl do
    if nkind[flat[i]] = 15 then begin
      nd := flat[i];
      (* последний ребёнок-КДЛ *)
      kd := 0;
      ch := nkid[nd];
      while ch <> 0 do begin
        if nkind[ch] = 16 then
          kd := ch;
        ch := nbro[ch]
      end;
      if kd <> 0 then begin
        cl := ix[nd] + iw[nd] div 2;
        (* ось правее всех икон тела (от первого ребёнка до КДЛ) *)
        ax := cl;
        ch := nkid[nd];
        while ch <> 0 do begin
          if ix[ch] + iw[ch] > ax then
            ax := ix[ch] + iw[ch];
          ch := nbro[ch]
        end;
        ax := ax + 2;
        r1 := iy[nd] + ih[nd] + 1;
        r2 := iy[kd] + ih[kd] div 2;
        wx := ix[kd];
        for xx := ix[kd] to ix[kd] + iw[kd] - 1 do
          if pic[r2][xx] <> ' ' then
            wx := xx;
        put(cl + 1, r1, '<');
        for xx := cl + 2 to ax - 1 do
          put(xx, r1, '-');
        put(ax, r1, '+');
        for rr := r1 + 1 to r2 - 1 do
          put(ax, rr, '|');
        put(ax, r2, '+');
        for xx := wx + 1 to ax - 1 do
          put(xx, r2, '-')
      end
    end
end;

(* ---------------- силуэт ---------------- *)

(* раскладка силуэта по рис. 9 книги: заголовок, под ним ветки
   РЯДОМИ в колонки слева направо; ось заголовка - над первой
   веткой; верхняя шина соединяет заголовок со всеми щитами;
   снизу петля: ветка, не кончающаяся КОНЦОМ, спускается на
   нижнюю шину, та уходит в вертикаль слева и остриём (вправо)
   возвращается в заголовок; ветка с КОНЦОМ - выход вниз *)
procedure silout;
var
  h, b, p, sav, f0, j, nn1, kk, mn, mx, bot, prevr, d,
  minall, gsh: integer;
begin
  silnb := 0;
  h := nroot;
  (* заголовок: только икона, без потомков *)
  layout(h, 1, 1, 0, 1);
  silhb := iy[h] + ih[h] + 1;
  (* ветки: отрезки корневой цепочки между узлами-щитами;
     цепочка отрезается до следующего щита (nbro := 0) *)
  b := nbro[h];
  while b <> 0 do begin
    p := b;
    while (nbro[p] <> 0) and (nkind[nbro[p]] <> 2) do
      p := nbro[p];
    sav := nbro[p];
    nbro[p] := 0;
    silnb := silnb + 1;
    silb[silnb] := b;
    f0 := nfl + 1;
    silf0[silnb] := f0;
    layout(b, 1, silhb + 2, 0, 0);
    silf1[silnb] := nfl;
    siltail[silnb] := gtail;
    nbro[p] := sav;
    mn := ix[b];
    mx := ix[b] + iw[b] - 1;
    bot := iy[b] + ih[b] - 1;
    for j := f0 to nfl do begin
      nn1 := flat[j];
      if ix[nn1] < mn then
        mn := ix[nn1];
      if ix[nn1] + iw[nn1] - 1 > mx then
        mx := ix[nn1] + iw[nn1] - 1;
      if iy[nn1] + ih[nn1] - 1 > bot then
        bot := iy[nn1] + ih[nn1] - 1
    end;
    if silnb > 1 then begin
      (* следующая ветка - правее предыдущей *)
      d := prevr + GAPB + 1 - mn;
      for j := silf0[silnb] to nfl do begin
        nn1 := flat[j];
        ix[nn1] := ix[nn1] + d;
        for kk := 1 to nbr[nn1] do
          brx[nn1, kk] := brx[nn1, kk] + d
      end;
      mx := mx + d
    end;
    prevr := mx;
    silbot[silnb] := bot;
    b := sav
  end;
  (* оси веток; заголовок над первой веткой *)
  for j := 1 to silnb do
    silax[j] := ix[silb[j]] + iw[silb[j]] div 2;
  ix[h] := silax[1] - iw[h] div 2;
  (* вертикаль петли - на 2 левее самого левого узла *)
  minall := ix[h];
  for j := 1 to nfl do
    if ix[flat[j]] < minall then
      minall := ix[flat[j]];
  sillc := minall - 2;
  gsh := 0;
  if sillc < 1 then
    gsh := 1 - sillc;
  (* колонки обязаны уместиться в ширину АЦПУ: правый край с
     учётом сдвига петли - не правее CMAX-1; иначе ветки -
     в один столбец (общая раскладка, как у примитива) *)
  if prevr + gsh > CMAX - 1 then begin
    silmd := false;
    for j := 1 to nfl do
      nxt[flat[j]] := 0;
    nfl := 0
  end else if gsh > 0 then begin
    (* заголовок тоже в flat - сдвигается общим циклом *)
    for j := 1 to nfl do begin
      nn1 := flat[j];
      ix[nn1] := ix[nn1] + gsh;
      for kk := 1 to nbr[nn1] do
        brx[nn1, kk] := brx[nn1, kk] + gsh
    end;
    for j := 1 to silnb do
      silax[j] := silax[j] + gsh;
    sillc := 1
  end;
  if not silmd then
    exit;
  (* нижняя шина - ниже самой глубокой ветки *)
  bot := 0;
  for j := 1 to silnb do
    if silbot[j] > bot then
      bot := silbot[j];
  silbb := bot + 2
end;

(* линии силуэта, верхняя часть: вертикаль заголовка, верхняя
   шина с остриём петли и спуски к щитам (разбивка на две
   процедуры - у компилятора 15.1 предел числа команд в блоке) *)
procedure silconnect;
var
  i, r, x, lasta: integer;
begin
  (* заголовок -> верхняя шина *)
  for r := iy[nroot] + ih[nroot] to silhb - 1 do
    put(silax[1], r, '|');
  (* верхняя шина: от петли до последней ветки *)
  lasta := silax[silnb];
  put(sillc, silhb, '+');
  for x := sillc + 1 to lasta - 1 do
    put(x, silhb, '-');
  for i := 1 to silnb do
    put(silax[i], silhb, '+');
  (* остриё петли - вправо, в вертикаль заголовка *)
  if silax[1] - 1 > sillc then
    put(silax[1] - 1, silhb, '>');
  (* шина -> щиты веток *)
  for i := 1 to silnb do
    put(silax[i], silhb + 1, '|')
end;

(* линии силуэта, нижняя часть: вертикаль петли слева и нижняя
   шина (гребёнка): спуски веток, не кончающихся КОНЦОМ *)
procedure silloop;
var
  i, r, x, lasta: integer;
begin
  (* вертикаль петли слева *)
  for r := silhb + 1 to silbb - 1 do
    put(sillc, r, '|');
  put(sillc, silbb, '+');
  (* нижняя шина: спуски веток, не кончающихся КОНЦОМ; сначала
     тире шины, затем кресты на осях - крест не затереть *)
  lasta := sillc;
  for i := 1 to silnb do
    if nkind[siltail[i]] <> 10 then begin
      if silax[i] > lasta then
        lasta := silax[i]
    end;
  for x := sillc + 1 to lasta - 1 do
    put(x, silbb, '-');
  for i := 1 to silnb do
    if nkind[siltail[i]] <> 10 then begin
      for r := iy[siltail[i]] + ih[siltail[i]] to silbb - 1 do
        put(silax[i], r, '|');
      put(silax[i], silbb, '+')
    end
end;

(* ---------------- выдача разметки СИПРОД ---------------- *)

(* строка рисунка -> карты разметки; карта не длиннее 80 позиций:
   * /*D + 76 литер или *D + 78 литер; пустая строка даёт
   одну карту * /*D *)
procedure emitline(y: integer);
var
  r: carty;
  i, p, ln, q: integer;
  first: boolean;
begin
  ln := 0;
  for i := 1 to CMAX do
    if pic[y][i] <> ' ' then
      ln := i;
  p := 1;
  first := true;
  while (p <= ln) or first do begin
    for i := 1 to 80 do r[i] := ' ';
    if first then begin
      r[1] := '*'; r[2] := '/'; r[3] := '*'; r[4] := 'D';
      q := 76
    end else begin
      r[1] := '*'; r[2] := 'D';
      q := 78
    end;
    if first then begin
      for i := 1 to q do
        if p + i - 1 <= ln then
          r[4 + i] := pic[y][p + i - 1]
    end else begin
      for i := 1 to q do
        if p + i - 1 <= ln then
          r[2 + i] := pic[y][p + i - 1]
    end;
    pasout(r[1], r[80]);
    p := p + q;
    first := false
  end
end;

(* выдача всей разметки *)
procedure emit;
var
  r: carty;
  i, e, used, j: integer;
  keep: array [1..RMAX] of boolean;
begin
  for i := 1 to 80 do r[i] := ' ';
  r[1] := '*'; r[2] := 'R'; r[3] := 'E'; r[4] := 'D';
  pasout(r[1], r[80]);
  r[1] := '*'; r[2] := 'R'; r[3] := 'G'; r[4] := '*';
  r[5] := 'R'; r[6] := 'U';
  pasout(r[1], r[80]);
  (* страницы: разметку печатает редактор, страница широкого
     формата - TRN строк, интервал rln = 0, строка рисунка -
     одна строка страницы.  Икона переносится на новую страницу
     только целиком - тем же правилом, что в *DRK (drkemit
     redakt.pas): пробег строк, накрытых одной иконой, не
     умещающийся на текущей странице, начинается на новой.
     Перед таким пробегом выдаётся *P; при used = TRN *P не
     нужна - естественный перенос commitrow рвёт страницу перед
     той же строкой и без пустой строки в конце листа *)
  for i := 1 to rws do
    keep[i] := false;
  for i := 1 to nfl do
    for j := iy[flat[i]] + 1 to iy[flat[i]] + ih[flat[i]] - 1 do
      if j <= rws then
        keep[j] := true;
  used := 0;
  for i := 1 to rws do begin
    if (i = 1) or (not keep[i]) then begin
      (* первая строка пробега, связанного иконой: i..e *)
      e := i;
      while (e < rws) and keep[e + 1] do
        e := e + 1;
      if (e > i) and (used > 0) and (used < TRN) and
         (used + (e - i + 1) > TRN) then begin
        for j := 1 to 80 do r[j] := ' ';
        r[1] := '*'; r[2] := 'P';
        pasout(r[1], r[80]);
        used := 0
      end
    end;
    if used >= TRN then
      used := 0;
    used := used + 1;
    emitline(i)
  end;
  for i := 1 to 80 do r[i] := ' ';
  r[1] := '*'; r[2] := 'E';
  pasout(r[1], r[80]);
  r[1] := '*'; r[2] := 'E'; r[3] := 'N'; r[4] := 'D';
  pasout(r[1], r[80])
end;

(* ---------------- главная программа ---------------- *)

begin
  initkw;
  for ii := 1 to RMAX do
    for jj := 1 to CMAX do
      pic[ii][jj] := ' ';
  ncnt := 0;
  nroot := 0;
  nfl := 0;
  gtail := 0;
  getcard;
  parse;
  if ncnt = 0 then begin
    writeln('СХЕМА ПУСТА');
    stop
  end;
  (* компоновка.  Силуэт: корневая цепочка - заголовок (И1), за
     ним ветки-щиты (И7); ветки раскладываются РЯДОМИ в колонки.
     Иначе - основной шампур в колонке 1 *)
  silmd := (nkind[nroot] = 1) and (nbro[nroot] <> 0) and
           (nkind[nbro[nroot]] = 2);
  if silmd then begin
    (* веток больше SM - общая раскладка *)
    qq := 0;
    nn1 := nbro[nroot];
    while nn1 <> 0 do begin
      if nkind[nn1] = 2 then
        qq := qq + 1;
      nn1 := nbro[nn1]
    end;
    if qq > SM then
      silmd := false
  end;
  if silmd then
    silout;
  (* silout может отменить силуэт: колонки не уместились в
     ширину АЦПУ - тогда общий шампур *)
  if not silmd then
    layout(nroot, 1, 1, 0, 0);
  (* сдвиг рисунка: левый край икон к колонке 1; оси плеч
     не сдвигаются - они уже отсчитаны от шампура *)
  mm := 1;
  for ii := 1 to nfl do
    if ix[flat[ii]] < mm then
      mm := ix[flat[ii]];
  if mm < 1 then begin
    qq := 1 - mm;
    for ii := 1 to nfl do
      ix[flat[ii]] := ix[flat[ii]] + qq;
    (* оси плеч - те же абсолютные колонки рисунка *)
    for ii := 1 to ncnt do
      for jj := 1 to 8 do
        if brx[ii, jj] <> 0 then
          brx[ii, jj] := brx[ii, jj] + qq
  end;
  (* число строк рисунка: самая низкая занятая строка *)
  rws := 0;
  for ii := 1 to nfl do
    if iy[flat[ii]] + ih[flat[ii]] - 1 > rws then
      rws := iy[flat[ii]] + ih[flat[ii]] - 1;
  kk := 0;
  while (rws > 0) and (kk = 0) do begin
    jj := 0;
    for ii := 1 to CMAX do
      if pic[rws][ii] <> ' ' then
        jj := ii;
    if jj > 0 then
      kk := 1
    else
      rws := rws - 1
  end;
  (* у силуэта ниже икон ещё нижняя шина петли (рисуется после
     перерисовки икон) *)
  if silmd and (silbb > rws) then
    rws := silbb;
  (* перерисовка со сдвигом *)
  for ii := 1 to RMAX do
    for jj := 1 to CMAX do
      pic[ii][jj] := ' ';
  for ii := 1 to nfl do
    makeicon(flat[ii], ix[flat[ii]] + iw[flat[ii]] div 2,
             iy[flat[ii]]);
  connectors;
  busout;
  mergeback;
  forloop;
  if silmd then begin
    silconnect;
    silloop
  end;
  emit;
  stop
end.
