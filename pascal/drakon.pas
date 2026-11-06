(*=u-*,p-*)
(* ТРАНСЛЯТОР СХЕМ ЯЗЫКА ДРАКОН ДЛЯ БЭСМ-6.
   Реализация на Паскале-Мониторе алгоритма эталонного генератора
   разметки (re-siprod, tools/drakon_markup.py): разбор текста схемы
   по отступам, перенос длинных подписей на строки, компоновка икон
   по колонкам (основной шампур и правые плечи развилок), рисование
   икон шести видов с соединительными линиями, возвратами плеч и
   слиянием маршрутов, выдача разметки СИПРОДа *RED для печати
   схемы на АЦПУ средствами редактора.
   Ключевые слова: ЗАГОЛОВОК ВЕТКА ДЕЙСТВИЕ КОММЕНТАРИЙ ЕСЛИ ЦИКЛ
   ВЫБОР ВАРИАНТ АДРЕС КОНЕЦ ТО ИНАЧЕ.
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
  TKW = 12;       (* число ключевых слов *)
  CWD = 72;       (* значимых позиций карты *)
  RMAX = 240;     (* строк рисунка *)
  CMAX = 128;     (* колонок рисунка: широкий формат АЦПУ-128 *)
  GAPR = 2;       (* зазор по вертикали *)
  GAPS = 4;       (* зазор между шампуром и плечом *)
  MINW = 20;      (* минимальная ширина поля текста *)
  MXL = 12;       (* строк текста в иконе *)
  MXW = 40;       (* слов в подписи *)

type
  carty = array [1..80] of char;
  prow = packed array [1..CMAX] of char;

var
  card: carty;
  eofin: boolean;

  kw: array [1..TKW] of carty;
  kwl: array [1..TKW] of integer;

  nkind: array [1..NN] of integer;
  ntext: array [1..NN] of carty;
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
  gtxt: carty;
  wtx: array [1..MXL] of carty;
  wln: array [1..MXL] of integer;
  nwl: integer;
  wwd: integer;

  ii, jj, kk, nn1, mm, pp, qq: integer;

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
  kw[12][4] := 'Ч'; kw[12][5] := 'Е'
end;

(* распознавание ключевого слова: индекс или 0 *)
function detect(var s: carty; ln: integer): integer;
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
      if ok then
        res := i
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
  (* контейнеры: ЕСЛИ ЦИКЛ ВЫБОР ВАРИАНТ ТО ИНАЧЕ *)
  if (k = 5) or (k = 6) or (k = 7) or (k = 8) or
     (k = 11) or (k = 12) then begin
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
  i, ind, k, p, ln: integer;
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
      k := detect(txt, ln);
      if k > 0 then begin
        p := kwl[k] + 1;
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

(* вид иконы: 0 прямоугольник, 1 заголовок, 2 трапеция ветки,
   3 вопрос, 4 конец, 5 адрес, 6 выбор *)
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
  else if k = 5 then
    res := 3
  else if k = 6 then
    res := 3
  else if k = 7 then
    res := 6
  else if k = 9 then
    res := 5
  else if k = 10 then
    res := 4;
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
procedure ctext(x, fw, r: integer; var t: carty; tl: integer);
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

(* разложить подпись gtxt длиной tl на строки wtx/wln;
   ширина поля - wwd *)
procedure wraptl(tl: integer);
var
  i, j, cur: integer;
begin
  nwl := 0;
  cur := 0;
  for i := 1 to nwd do begin
    if (cur = 0) or (wln[cur] + 1 + wwp[i] > wwd) then begin
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
   не меньше 20 и самого длинного слова *)
procedure settext(n: integer);
var
  i, tl: integer;
begin
  tl := ntl[n];
  for i := 1 to tl do gtxt[i] := ntext[n][i];
  wwd := MINW;
  splitw(tl)
end;

(* полная ширина иконы узла n *)
function iconw(n: integer): integer;
var
  k, tl, wd: integer;
begin
  k := kindof(n);
  tl := ntl[n];
  if k = 4 then begin
    wd := 10;
    if tl + 6 > wd then
      wd := tl + 6;
    iconw := wd
  end else begin
    settext(n);
    if k = 3 then
      wd := wwd + 6
    else if k = 6 then
      wd := wwd + 6
    else if (k = 2) or (k = 5) then
      wd := wwd + 4
    else
      wd := wwd + 2;
    iconw := wd
  end
end;

(* рисование иконы узла n с центром на колонке col, верх row *)
procedure makeicon(n, col, row: integer);
var
  k, w, tl, i, x, y, r, f: integer;
begin
  k := kindof(n);
  tl := ntl[n];
  for i := 1 to tl do gtxt[i] := ntext[n][i];
  if (k = 4) and (tl = 0) then begin
    tl := 5;
    gtxt[1] := 'к'; gtxt[2] := 'о'; gtxt[3] := 'н';
    gtxt[4] := 'е'; gtxt[5] := 'ц'
  end;
  (* ширина иконы *)
  if k = 4 then begin
    w := 10;
    if tl + 6 > w then
      w := tl + 6
  end else begin
    settext(n);
    if (k = 3) or (k = 6) then
      w := wwd + 6
    else if (k = 2) or (k = 5) then
      w := wwd + 4
    else
      w := wwd + 2
  end;
  (* строки подписи (для конца - одна строка) *)
  if k = 4 then begin
    nwl := 1;
    wln[1] := tl;
    for i := 1 to tl do wtx[1][i] := gtxt[i]
  end else
    wraptl(tl);
  x := col - w div 2;
  ix[n] := x;
  iw[n] := w;
  iy[n] := row;
  y := row;
  if k = 1 then begin
    (* ЗАГОЛОВОК: .-(т)-. в скобках, низ +---+ *)
    ih[n] := nwl + 2;
    put(x, y, '.');
    dash(x + 1, y, w - 2, '-');
    put(x + w - 1, y, '.');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '(');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, ')')
    end;
    put(x, y + nwl + 1, '+');
    dash(x + 1, y + nwl + 1, w - 2, '-');
    put(x + w - 1, y + nwl + 1, '+')
  end else if k = 4 then begin
    (* КОНЕЦ: .-(конец)-+ *)
    ih[n] := 3;
    put(x, y, '.');
    dash(x + 1, y, w - 2, '-');
    put(x + w - 1, y, '.');
    put(x, y + 1, '(');
    ctext(x + 1, w - 2, y + 1, wtx[1], wln[1]);
    put(x + w - 1, y + 1, ')');
    put(x, y + 2, '+');
    dash(x + 1, y + 2, w - 2, '-');
    put(x + w - 1, y + 2, '+')
  end else if (k = 2) or (k = 6) then begin
    (* ВЕТКА и ВЫБОР: трапеция, верх короче низа *)
    ih[n] := nwl + 2;
    put(x + 2, y, '+');
    dash(x + 3, y, w - 4, '-');
    put(x + w - 1, y, '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x + 1, r, '/');
      ctext(x + 2, w - 3, r, wtx[i], wln[i]);
      put(x + w - 1, r, '/')
    end;
    put(x, y + nwl + 1, '+');
    dash(x + 1, y + nwl + 1, w - 2, '-');
    put(x + w - 1, y + nwl + 1, '+')
  end else if k = 5 then begin
    (* АДРЕС: трапеция, верх уже низа, правый край вертикальный *)
    ih[n] := nwl + 2;
    put(x + 3, y, '+');
    dash(x + 4, y, w - 6, '-');
    put(x + w - 2, y, '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x + 2, r, '/');
      ctext(x + 3, w - 3, r, wtx[i], wln[i]);
      put(x + w, r, '/')
    end;
    put(x + 1, y + nwl + 1, '+');
    dash(x + 2, y + nwl + 1, w - 4, '-');
    put(x + w - 2, y + nwl + 1, '+')
  end else if k = 3 then begin
    (* ЕСЛИ, ЦИКЛ: шестиугольник <т> с косыми боками *)
    ih[n] := nwl + 3;
    put(x + 2, y, '+');
    dash(x + 3, y, w - 4, '-');
    put(x + w - 1, y, '+');
    for i := 1 to nwl do begin
      r := y + i;
      if i = 1 then begin
        put(x, r, '<');
        ctext(x + 1, w - 2, r, wtx[i], wln[i]);
        put(x + w - 1, r, '>')
      end else begin
        put(x, r, '|');
        ctext(x + 1, w - 2, r, wtx[i], wln[i]);
        put(x + w - 1, r, '|')
      end
    end;
    put(x + 1, y + nwl + 1, '/');
    put(x + w - 1, y + nwl + 1, '/');
    put(x + 2, y + nwl + 2, '+');
    dash(x + 3, y + nwl + 2, w - 4, '-');
    put(x + w - 1, y + nwl + 2, '+')
  end else begin
    (* ДЕЙСТВИЕ, ВАРИАНТ, КОММЕНТАРИЙ: прямоугольник *)
    ih[n] := nwl + 2;
    put(x, y, '+');
    dash(x + 1, y, w - 2, '-');
    put(x + w - 1, y, '+');
    for i := 1 to nwl do begin
      r := y + i;
      put(x, r, '|');
      ctext(x + 1, wwd, r, wtx[i], wln[i]);
      put(x + w - 1, r, '|')
    end;
    put(x, y + nwl + 1, '+');
    dash(x + 1, y + nwl + 1, w - 2, '-');
    put(x + w - 1, y + nwl + 1, '+')
  end
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
  if nkind[n] = 6 then
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
      row0 := iy[node] + ih[node] - 2;
      rx := col + iw[node] div 2 + GAPS;
      ry := iy[node] + ih[node] div 2 + 1;
      if row0 + 1 > ry then
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

(* шина выхода вправо к осям плеч *)
procedure busout;
var
  i, a, b, r, cl, x, row0, lastr: integer;
begin
  for i := 1 to nfl do begin
    a := flat[i];
    if nbr[a] > 0 then begin
      cl := ix[a] + iw[a] div 2;
      row0 := iy[a] + ih[a] - 2;
      lastr := brx[a, 1];
      for b := 2 to nbr[a] do
        if brx[a, b] > lastr then
          lastr := brx[a, b];
      for x := ix[a] + iw[a] to lastr - 1 do
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
  i: integer;
begin
  for i := 1 to 80 do r[i] := ' ';
  r[1] := '*'; r[2] := 'R'; r[3] := 'E'; r[4] := 'D';
  pasout(r[1], r[80]);
  r[1] := '*'; r[2] := 'R'; r[3] := 'G'; r[4] := '*';
  r[5] := 'R'; r[6] := 'U';
  pasout(r[1], r[80]);
  for i := 1 to rws do
    emitline(i);
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
  (* компоновка: основной шампур в колонке 1 *)
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
      ix[flat[ii]] := ix[flat[ii]] + qq
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
  emit;
  stop
end.
