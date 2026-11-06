(*=u-*,p-*)
(* РЕДАКТОР СИПРОД-П: реализация режима *RED системы СИПРОД (БЭСМ-6)
   на языке Паскаль-Монитор (МС «Дубна»).
   Реализовано: заполнение и выравнивание строк; команды
   *nS *n/ *nP *E *D *nH *nG *nCc *Knc *nFc *nRFc *n(...), *nW...),
   *T *MD *nRL *nRC *OLR *RT *RU *ORU *nMCS *nMCP *nN *NN *RG,
   *nSTA *nSTO *nSTP *nSTG *STN, таблицы *ST *SL (*NL *NR *NU *ND),
   макроопределения *nM=...$ и вставки *nM, листинг *MF и ///,
   печать на АЦПУ-128 (две страницы по 64 поз., формат А 84,
   широкий формат), рамки, номера страниц, штамп ЕСПД,
   ошибки 10 20 30 40 61 62 64 66 80 91 100.
   Вход: карты после *EXECUTE (*RED ... *E, *END).  Выход: АЦПУ.
   Отличие от оригинала: прогон страницы (код 0201) недоступен через
   стандартный вывод Паскаля, листы разделяются пустой строкой. *)
program redakt(input, output);

label 1, 9;

const
  CW = 72;        (* значимых позиций карты *)
  TRN = 60;       (* строк текста: обычный и широкий формат *)
  TRA = 65;       (* строк текста: формат А *)
  MRW = 44;       (* макс. слов в строке *)
  MKMAX = 20;     (* макроопределений *)
  MKLEN = 400;    (* длина тела макро *)
  TCDEEP = 6;     (* глубина вложения макро *)
  TCMAX = 30;      (* строк в ячейке таблицы *)

type
  rowty = array [1..128] of char;    (* строка печати, по слову на
  * литеру *)
  carty = array [1..80] of char;
  prow = packed array [1..128] of char; (* строка в хранении, 6
  * литер/слово *)
  pwty = packed array [1..100] of char; (* слово в хранении *)
  mkty = packed array [1..MKLEN] of char; (* тело макроопределения *)

var
  card: carty;            (* текущая карта *)
  cpos: integer;          (* позиция на карте *)
  eofin: boolean;

  (* формат страницы *)
  fmt: integer;           (* 0 обычный, 1 широкий, 2 формат А *)
  shrows: integer;        (* строк в листе *)
  rowbase: integer;       (* листовая строка первой текстовой минус 1 *)
  tmax: integer;          (* текстовых строк на странице *)
  defl, defw: integer;    (* поле по умолчанию: центровка и номера *)
  flda, fldw: integer;    (* текущее поле левой страницы *)
  mcsa, mcsw: integer;    (* параметры *MCS *)

  (* лист и страницы *)
  sheet: array [1..72] of rowty;
  htxt: array [0..1] of array [1..66] of prow;
  hused: array [0..1] of boolean;
  hpno: array [0..1] of integer;
  hrows: array [0..1] of integer;   (* занятых текстовых строк *)
  pageno, pnext: integer; (* счётчик страниц и номер от *N *)
  numon, rgon: boolean;

  (* текущая строка *)
  cur: rowty;
  curpos: integer;        (* следующая свободная позиция *)
  rowno: integer;         (* занято текстовых строк на странице *)
  side: integer;          (* 0 левая страница, 1 правая *)
  posmode: boolean;       (* позиционный набор после G/C/K/F/RF/D *)
  indon: boolean;         (* абзацный отступ *)
  rln, rcn: integer;      (* интервал и разрядка *)
  fillon: boolean;        (* перенос по словам *)

  (* очередь слов строки *)
  wt: array [1..MRW] of pwty;
  wl: array [1..MRW] of integer;
  wrc: array [1..MRW] of integer;
  nw: integer;
  natq: integer;          (* естественная ширина очереди слов *)
  word: pwty;             (* накопитель слова *)
  wleng: integer;
  wrcl: integer;          (* разрядка слова при наборе *)

  (* режимы *)
  listing: boolean;       (* *MF *)
  endtxt: boolean;        (* *E *)
  stpon, stgon: boolean;
  stpend: boolean;        (* штамп задан на свежей странице - поставить *)
  pgfirst: boolean;       (* ещё не напечатан первый лист (для *1STP/*1STG) *)
  freshpg: boolean;       (* страница начата, но текста на ней нет *)
  fmpending: integer;     (* сменa формата, ждущая следующей страницы *)
  fir: boolean;           (* первая карта блока *RED - разбор FIRCAR *)
  stponly, stgonly: boolean;
  stp, stg: carty;
  stpl, stgl: integer;

  (* таблицы *)
  tabon: boolean;         (* режим таблицы *)
  tabline: boolean;       (* с линейками (SL) *)
  tbda: array [1..8] of integer;   (* старт колонки, абсолютно *)
  tbdw: array [1..8] of integer;   (* ширина колонки *)
  tbn: integer;           (* число колонок *)
  tslpos: array [1..8] of integer; (* позиции линеек SL, абсолютно *)
  tcol: integer;          (* номер текущей колонки *)
  tbn2: integer;          (* число колонок таблицы *)
  svflda, svfldw: integer; (* сохранённое поле на время ячейки *)
  prevnd: array [1..8] of boolean; (* нижние линии предыдущей строки *)
  tline: array [1..8] of array [1..TCMAX] of prow; (* строки ячеек *)
  tcnt: array [1..8] of integer;
  tcln: integer;          (* строк в текущей ячейке *)
  incell: boolean;        (* накопление ячейки *)
  cnol, cnr, cnu, cnd: boolean;    (* убранные линии ячейки *)
  rownol, rownr: array [1..8] of boolean;
  rownu, rownd: array [1..8] of boolean;
  trows: integer;         (* колонок в текущей строке таблицы *)

  (* макроопределения *)
  mktx: array [1..MKMAX] of mkty;
  mkln: array [1..MKMAX] of integer;
  mkcnt: integer;
  mkbuf: mkty;
  mkbl: integer;
  mksav: array [1..TCDEEP] of carty;
  mksl, mksq: array [1..TCDEEP] of integer;
  mknum: array [1..TCDEEP] of integer;   (* номер макро на уровне *)
  mkpp: array [1..TCDEEP] of integer;    (* позиция в теле макро *)
  mkres: array [1..TCDEEP] of boolean;   (* тело исчерпано, идёт
                                            продолжение карты *)
  mksp: integer;

  cwv: integer;           (* конец текущей карты или тела макро *)
  ii, jj, kk, nn1, mm, pp, qq: integer;
  c2, c3: char;

procedure pasout(var a, b: char); fortran;

(* ---------------- ввод ---------------- *)

(* чтение следующей карты *)
procedure getcard;
var
  i: integer;
begin
  if eof(input) then begin
    eofin := true;
    exit
  end;
  for i := 1 to 80 do card[i] := ' ';
  readln(card);
  cpos := 1;
  (* карты значимы до 80-й позиции: разметка *D несёт текст
     и за 72-й (SIPROD.md, 2.1; каталог разметки ДРАКОНа) *)
  cwv := 80;
  eofin := false
end;

(* ---------------- утилиты печати ---------------- *)

(* печать строки листа: 128 позиций, хвостовые пробелы срезает Э64 *)
procedure outline(var r: rowty);
begin
  pasout(r[1], r[128])
end;

(* пустая строка печати *)
procedure blankl;
var
  r: rowty;
  i: integer;
begin
  for i := 1 to 128 do r[i] := ' ';
  outline(r)
end;

(* очистка строки *)
procedure clrrow(var r: rowty);
var
  i: integer;
begin
  for i := 1 to 128 do r[i] := ' '
end;

(* число вправо в поле шириной w с позиции pos строки r *)
procedure putnum(var r: rowty; pos, val, w: integer);
var
  d: array [1..8] of char;
  nd, i, v: integer;
begin
  v := val;
  nd := 0;
  repeat
    nd := nd + 1;
    d[nd] := chr(60B + v mod 10);
    v := v div 10
  until v = 0;
  for i := 1 to w do r[pos + i - 1] := ' ';
  i := 0;
  while (i < nd) and (i < w) do begin
    r[pos + w - 1 - i] := d[i + 1];
    i := i + 1
  end
end;

(* ---------------- ошибки ---------------- *)

(* печать ошибки и останов задачи, как KLAIDA оригинала *)
procedure klaida(num: integer);
var
  r: rowty;
  i: integer;
begin
  blankl; blankl;
  clrrow(r);
  r[20] := 'Е'; r[21] := ' '; r[22] := 'R'; r[23] := ' ';
  r[24] := 'R'; r[25] := ' '; r[26] := 'О'; r[27] := ' ';
  r[28] := 'R';
  r[33] := 'N'; r[34] := 'R'; r[35] := '.';
  putnum(r, 36, num, 7);
  outline(r);
  blankl;
  clrrow(r);
  r[20] := 'О'; r[21] := ' '; r[22] := 'Б'; r[23] := ' ';
  r[24] := 'Р'; r[25] := ' '; r[26] := 'А'; r[27] := ' ';
  r[28] := 'З'; r[31] := 'П'; r[32] := ' '; r[33] := 'Е';
  r[34] := ' '; r[35] := 'Р'; r[36] := ' '; r[37] := 'Ф';
  r[38] := ' '; r[39] := 'О'; r[40] := ' '; r[41] := 'К';
  r[42] := ' '; r[43] := 'А'; r[44] := ' '; r[45] := 'Р';
  r[46] := ' '; r[47] := 'Т'; r[48] := ' '; r[49] := 'Ы';
  r[51] := ':';
  outline(r);
  blankl;
  clrrow(r);
  for i := 1 to CW do
    if card[i] <> ' ' then r[i + 2] := card[i];
  outline(r);
  blankl;
  stop
end;

(* ---------------- формат страницы ---------------- *)

(* установить параметры формата; f: 0 обычный, 1 широкий, 2 А *)
procedure setfmt(f: integer);
begin
  fmt := f;
  if f = 0 then begin
    shrows := 67; rowbase := 4; tmax := TRN;
    defl := 6; defw := 56
  end else if f = 1 then begin
    shrows := 68; rowbase := 5; tmax := TRN;
    defl := 6; defw := 120
  end else begin
    shrows := 72; rowbase := 5; tmax := TRA;
    defl := 12; defw := 67
  end;
  mcsa := 1; mcsw := defw;
  flda := defl; fldw := defw
end;

(* применить *MCS a w; ошибка 30 - поле или ширина за страницей *)
procedure setmcs(a, w: integer);
begin
  if (w <= 0) or (a <= 0) then klaida(30);
  if defl + a - 1 + w - 1 > defl + defw - 1 then klaida(30);
  mcsa := a; mcsw := w;
  flda := defl + a - 1; fldw := w
end;
(* поле текущей страницы: правая сдвинута на 64 позиции *)
function curflda: integer;
begin
  if fmt = 0 then curflda := flda + 64 * side
  else curflda := flda
end;

(* ---------------- лист ---------------- *)

(* печать собранного листа; final - окончание текста (*E) *)
procedure sheetprint(final: boolean);
var
  rows, top, bot, i, s, np, k2, st2, lim: integer;
  sideon: array [0..1] of boolean;
begin
  (* при окончании текста лист печатается до последней занятой строки
     (эталон red-fill); с рамкой и в широком формате лист печатается
     целиком - эталоны red-frame/red-header/red-wide *)
  if fmt = 0 then begin
    top := 2; rows := 67
  end else if fmt = 1 then begin
    top := 3; rows := 68
  end else begin
    top := 3; rows := 72
  end;
  (* чистые строки листа: верх листа и незанятый низ; занятые строки
     обеих страниц переписываются копированием целиком *)
  lim := rowbase + hrows[0];
  if (fmt = 0) and (hrows[1] < hrows[0]) then lim := rowbase + hrows[1];
  if lim > rows then lim := rows;
  for i := 1 to rowbase do clrrow(sheet[i]);
  for i := lim + 1 to rows do clrrow(sheet[i]);
  (* строки страниц - только занятые *)
  for i := 1 to tmax do
    if fmt = 0 then begin
      if i <= hrows[0] then
        for k2 := 1 to 64 do sheet[rowbase + i][k2] := htxt[0][i][k2];
      if i <= hrows[1] then
        for k2 := 65 to 128 do sheet[rowbase + i][k2] := htxt[1][i][k2]
    end else
      if i <= hrows[0] then
        for k2 := 1 to 128 do sheet[rowbase + i][k2] := htxt[0][i][k2];
  (* рамка *)
  bot := rows;
  if rgon then begin
    for i := top + 1 to bot - 1 do begin
      if fmt = 2 then begin
        sheet[i][1] := 'I'; sheet[i][84] := 'I'
      end else if fmt = 1 then begin
        sheet[i][2] := 'I'; sheet[i][128] := 'I'
      end else begin
        sheet[i][2] := 'I'; sheet[i][64] := 'I';
        sheet[i][66] := 'I'; sheet[i][128] := 'I'
      end
    end;
    if fmt = 2 then begin
      sheet[top][1] := '.'; sheet[top][84] := '.';
      sheet[bot][1] := '.'; sheet[bot][84] := '.';
      for i := 2 to 83 do begin
        sheet[top][i] := '-'; sheet[bot][i] := '-'
      end
    end else if fmt = 1 then begin
      sheet[top][2] := '.'; sheet[top][128] := '.';
      sheet[bot][2] := '.'; sheet[bot][128] := '.';
      for i := 3 to 127 do begin
        sheet[top][i] := '-'; sheet[bot][i] := '-'
      end
    end else begin
      sheet[top][2] := '.'; sheet[top][64] := '.';
      sheet[top][66] := '.'; sheet[top][128] := '.';
      sheet[bot][2] := '.'; sheet[bot][64] := '.';
      sheet[bot][66] := '.'; sheet[bot][128] := '.';
      for i := 3 to 63 do sheet[top][i] := '-';
      for i := 67 to 127 do sheet[top][i] := '-';
      for i := 3 to 63 do sheet[bot][i] := '-';
      for i := 67 to 127 do sheet[bot][i] := '-'
    end
  end;
  (* строка номеров страниц *)
  sideon[0] := hused[0];
  sideon[1] := hused[1];
  np := hpno[1];
  if final and (not hused[1]) and hused[0] then begin
    sideon[1] := true;
    np := hpno[0] + 1
  end;
  if numon then begin
    if fmt = 0 then begin
      if sideon[0] then begin
        sheet[3][31] := '-';
        sheet[3][35] := ' ';
        sheet[3][36] := '-';
        putnum(sheet[3], 32, hpno[0], 3)
      end;
      if sideon[1] then begin
        sheet[3][95] := '-';
        sheet[3][99] := ' ';
        sheet[3][100] := '-';
        putnum(sheet[3], 96, np, 3)
      end
    end else if fmt = 1 then begin
      if hused[0] or final then begin
        sheet[4][63] := '-';
        sheet[4][67] := ' ';
        sheet[4][68] := '-';
        putnum(sheet[4], 64, hpno[0], 3)
      end
    end else begin
      if hused[0] or final then begin
        sheet[4][42] := '-';
        sheet[4][46] := ' ';
        sheet[4][47] := '-';
        putnum(sheet[4], 43, hpno[0], 3)
      end
    end
  end;
  (* подвал STG: строка внизу страницы, над нижним полем *)
  if stgon and (stgl > 0) and ((not stgonly) or pgfirst) then begin
    if fmt = 0 then begin
      if sideon[0] then begin
        st2 := (64 - stgl) div 2 + 1;
        for i := 1 to stgl do sheet[bot - 2][st2 + i - 1] := stg[i]
      end;
      if sideon[1] then begin
        st2 := 64 + (64 - stgl) div 2 + 1;
        for i := 1 to stgl do sheet[bot - 2][st2 + i - 1] := stg[i]
      end
    end else begin
      if fmt = 1 then
        st2 := (128 - stgl) div 2 + 1
      else
        st2 := (84 - stgl) div 2 + 1;
      for i := 1 to stgl do sheet[bot - 2][st2 + i - 1] := stg[i]
    end
  end;
  (* выдача листа; строки прогона заменены пустыми *)
  for i := 1 to rows do
    if (i > 1) and ((fmt = 0) or (i > 2)) then
      outline(sheet[i]);
  pgfirst := false
end;

(* очистка листа *)
procedure newsheet;
var
  i, s, k2: integer;
begin
  (* чистота листа: строки, не занятые на прошлом листе, не писались
     с своей последней очистки; достаточно стереть занятые *)
  k2 := hrows[0];
  if hrows[1] > k2 then k2 := hrows[1];
  for s := 0 to 1 do
    for i := 1 to k2 do
      for jj := 1 to 128 do htxt[s][i][jj] := ' ';
  hused[0] := false; hused[1] := false;
  hpno[0] := 0; hpno[1] := 0;
  hrows[0] := 0; hrows[1] := 0;
  rowno := 0;
  clrrow(cur);
  curpos := 1
end;

(* штамп STP в первую текстовую строку страницы *)
procedure putstp;
var
  r: rowty;
  st: integer;
  i: integer;
begin
  if (not stpon) or (stpl = 0) then exit;
  if stponly and (pageno <> 1) then exit;
  clrrow(r);
  st := defl + (defw - stpl) div 2;
  for i := 1 to stpl do r[st + i - 1] := stp[i];
  for i := 1 to 128 do htxt[side][1][i] := r[i];
  rowno := 1;
  (* строка 1 листа занята штампом - учесть в высоте страницы *)
  if hrows[side] = 0 then hrows[side] := 1
end;

(* начало новой страницы: номер, сторона, штамп *)
procedure pagestart;
begin
  (* отложенная смена формата применяется к новой странице *)
  if fmpending >= 0 then begin
    setfmt(fmpending);
    fmpending := -1
  end;
  if pnext <> 0 then pageno := pnext
  else pageno := pageno + 1;
  pnext := 0;
  if fmt = 1 then begin
    (* широкий формат: лист - одна страница во всю ширину,
       очередная страница печатает предыдущий лист целиком *)
    if hused[0] then begin
      sheetprint(false);
      newsheet
    end;
    side := 0
  end else begin
    side := (pageno - 1) mod 2;
    if (side = 0) and hused[0] then begin
      (* нечётная страница всегда начинает новый лист *)
      sheetprint(false);
      newsheet
    end
  end;
  hpno[side] := pageno;
  rowno := 0;
  freshpg := true;
  putstp
end;

(* конец текущей страницы, начало следующей *)
procedure pageend;
begin
  if rowno > 0 then hused[side] := true;
  pagestart
end;

(* ---------------- текущая строка ---------------- *)

(* сдвиг строки r на лист (или в ячейку таблицы) *)
procedure commitrow(var r: rowty; withrl: boolean);
var
  i, k2: integer;
  sv: rowty;   (* копия строки на время pageend: newsheet внутри
                  pageend стирает cur, а r - тот же участок памяти;
                  без копии строка, зафиксированная точно на границе
                  страниц, попадает на новый лист пустой и рамки
                  фигур ДРАКОН обрываются *)
  svd: boolean;
begin
  if incell then begin
    tcln := tcln + 1;
    if tcln <= TCMAX then
      for k2 := 1 to 128 do tline[tcol][tcln][k2] := r[k2];
    exit
  end;
  svd := false;
  if withrl and (rowno > 0) then
    for i := 1 to rln do begin
      if rowno >= tmax then begin
        if not svd then begin
          for k2 := 1 to 128 do sv[k2] := r[k2];
          svd := true
        end;
        pageend;
        for k2 := 1 to 128 do r[k2] := sv[k2]
      end;
      (* строка интервала пуста; чистую строку листа писать не нужно *)
      rowno := rowno + 1
    end;
  if rowno >= tmax then begin
    if not svd then
      for k2 := 1 to 128 do sv[k2] := r[k2];
    pageend;
    for k2 := 1 to 128 do r[k2] := sv[k2]
  end;
  (* строка листа чиста от очистки листа и пишется один раз, поэтому
     достаточно записать непробельные литеры - доступ к упакованной
     строке htxt дорог, а пробел там уже стоит *)
  for k2 := 1 to 128 do
    if r[k2] <> ' ' then htxt[side][rowno + 1][k2] := r[k2];
  rowno := rowno + 1;
  freshpg := false;
  if rowno > hrows[side] then hrows[side] := rowno
end;

(* сдвиг текущей строки на лист *)
procedure commit(withrl: boolean);
begin
  commitrow(cur, withrl);
  clrrow(cur);
  curpos := curflda;
  indon := false
end;

(* положить слово w длиной ln в строку r с позиции p *)
procedure putword(var r: rowty; var pp: integer; var w: pwty;
                  ln: integer);
var
  i: integer;
begin
  for i := 1 to ln do r[pp + i - 1] := w[i];
  pp := pp + ln
end;

(* выровненная постановка очереди; just - выравнивать по ширине;
   непомещающиеся слова переносятся, длинное слово рвётся *)
procedure flushq(just: boolean);
var
  p, nat, extra, effw, i, g, sh: integer;
  gap: array [1..MRW] of integer;
begin
  if nw = 0 then exit;
  effw := fldw;
  if indon then effw := effw - 3;
  nat := natq;
  for i := 2 to nw do
    gap[i] := 1 + 2 * wrc[i - 1] + 2 * wrc[i];
  if (nat > effw) and (wl[1] > effw) then begin
    (* слово длиннее строки: разорвать, хвост остаётся в очереди *)
    for i := 1 to effw do cur[curflda + i - 1] := wt[1][i];
    commit(true);
    sh := effw;
    for i := sh + 1 to wl[1] do wt[1][i - sh] := wt[1][i];
    wl[1] := wl[1] - sh;
    wrc[1] := 0;
    natq := wl[1];
    exit
  end;
  p := curflda;
  if indon then p := p + 3;
  extra := 0;
  if just and fillon and (nw > 1) then extra := effw - nat;
  for i := 1 to nw do begin
    putword(cur, p, wt[i], wl[i]);
    if i < nw then begin
      g := gap[i + 1];
      if (extra > 0) and (i > nw - 1 - extra) then
        g := g + 1;
      p := p + g
    end
  end;
  curpos := p + 1;
  nw := 0;
  natq := 0;
  indon := false
end;

(* конец строки: очередь без выравнивания и сдвиг *)
procedure endline;
begin
  flushq(false);
  commit(true)
end;

(* n пустых строк текста *)
procedure empties(cnt: integer);
var
  i: integer;
begin
  for i := 1 to cnt do begin
    clrrow(cur);
    curpos := curflda;
    commit(false)
  end
end;

(* очередное слово в очередь; если слово не входит в строку,
   строка закрывается с выравниванием *)
procedure addword;
var
  n2: integer;
begin
  if wleng = 0 then exit;
  (* естественная ширина: накопленная очередь и новое слово *)
  n2 := natq;
  if nw > 0 then
    n2 := n2 + 1 + 2 * wrc[nw] + 2 * wrcl + wleng
  else
    n2 := n2 + wleng;
  if indon then n2 := n2 + 3;
  if (n2 > fldw) and (nw > 0) then begin
    flushq(true);
    commit(true)
  end;
  nw := nw + 1;
  wt[nw] := word;
  wl[nw] := wleng;
  wrc[nw] := wrcl;
  if nw > 1 then
    natq := natq + 1 + 2 * wrc[nw - 1] + 2 * wrc[nw];
  natq := natq + wleng;
  wleng := 0;
  wrcl := rcn;
  if nw >= MRW then begin
    flushq(true);
    commit(true)
  end
end;

(* литера текста; без переноса по словам - прямо в строку *)
procedure addch(c: char);
var
  i: integer;
begin
  if posmode or not fillon then begin
    if curpos <= 128 then begin
      cur[curpos] := c;
      curpos := curpos + 1
    end;
    exit
  end;
  if c = ' ' then begin
    addword;
    exit
  end;
  if wleng = 0 then wrcl := rcn;
  if wleng >= 99 then addword;
  wleng := wleng + 1;
  word[wleng] := c;
  (* разрядка: n пробелов после каждой литеры слова *)
  if rcn > 0 then
    for i := 1 to rcn do begin
      if wleng >= 99 then addword;
      wleng := wleng + 1;
      word[wleng] := ' '
    end
end;

procedure scancard; forward;


(* ---------------- команды позиционирования ---------------- *)

(* числовой префикс или параметр с карты *)
function readnum(var val: integer): boolean;
var
  v: integer;
  any: boolean;
begin
  v := 0;
  any := false;
  while (cpos <= cwv) and (card[cpos] = ' ') do cpos := cpos + 1;
  while (cpos <= cwv) and (card[cpos] >= '0') and (card[cpos] <= '9')
     do begin
    v := v * 10 + (ord(card[cpos]) - 48);
    cpos := cpos + 1;
    any := true
  end;
  val := v;
  readnum := any
end;

(* *nFc: литера заполняет остаток строки и ещё n-1 строк *)
procedure fillrest(c: char; n: integer);
var
  fe, i, j: integer;
  r: rowty;
begin
  flushq(false);
  fe := curflda + fldw - 1;
  for i := curpos to fe do cur[i] := c;
  commit(true);
  for j := 2 to n do begin
    clrrow(r);
    for i := curflda to fe do r[i] := c;
    commitrow(r, true)
  end
end;

(* *nRFc: литера заполняет строку до позиции n поля *)
procedure fillto(np: integer; c: char);
var
  fe, i: integer;
begin
  flushq(false);
  fe := curflda + np - 1;
  if fe > curflda + fldw - 1 then klaida(80);
  if fe >= curpos then
    for i := curpos to fe do cur[i] := c;
  curpos := fe + 1
end;

(* *nCc / *Knc: повторить литеру n раз с текущей позиции *)
procedure putrep(c: char; n: integer);
var
  fe, i: integer;
begin
  flushq(false);
  fe := curflda + fldw - 1;
  for i := 1 to n do begin
    if curpos > fe then exit;
    cur[curpos] := c;
    curpos := curpos + 1
  end
end;

(* *n(текст) и *nWтекст): повторение текста до скобки;
   one=true - весь текст одним словом *)
procedure group(rep: integer; one: boolean);
var
  buf: carty;
  bn, i, k2: integer;
  c: char;
begin
  bn := 0;
  while cpos <= cwv do begin
    c := card[cpos];
    cpos := cpos + 1;
    if c = ')' then begin
      if one then begin
        for k2 := 1 to rep do
          for i := 1 to bn do begin
            if wleng >= 99 then addword;
            wleng := wleng + 1;
            word[wleng] := buf[i]
          end;
        wrcl := 0;
        addword
      end else begin
        for k2 := 1 to rep do begin
          for i := 1 to bn do addch(buf[i]);
          if k2 < rep then addch(' ')
        end;
        addword
      end;
      exit
    end;
    if bn < 72 then begin
      bn := bn + 1;
      buf[bn] := c
    end
  end
end;

(* *nH: следующие n литер как есть дописываются к слову *)
procedure hword(cnt: integer);
var
  i: integer;
begin
  for i := 1 to cnt do begin
    if cpos > cwv then exit;
    if wleng >= 99 then addword;
    wleng := wleng + 1;
    word[wleng] := card[cpos];
    cpos := cpos + 1
  end
end;

(* *D: остаток карты выводится как есть *)
procedure verbatim;
var
  i: integer;
begin
  flushq(false);
  for i := cpos to cwv do begin
    if curpos > 128 then exit;
    cur[curpos] := card[i];
    curpos := curpos + 1
  end
end;

(* центрирование остатка карты (с позиции from) в поле *)
procedure centerrest(from: integer);
var
  r: rowty;
  ln, st, i: integer;
begin
  ln := 0;
  for i := from to cwv do
    if card[i] <> ' ' then ln := i - from + 1;
  if ln > 0 then begin
    clrrow(r);
    st := curflda + (fldw - ln) div 2;
    for i := 1 to ln do r[st + i - 1] := card[from + i - 1];
    commitrow(r, true)
  end
end;

(* дописать текущий лист и начать новый в формате f *)
procedure newfmt(f: integer; dop: boolean);
begin
  (* *RU без единичного префикса не допечатывает текущий лист:
     пустой лист просто заменяется (SIPROD.md, таблица команд);
     *1RU - сначала допечатать (dop=true) *)
  flushq(false);
  if (rowno > 0) or (curpos > curflda) or dop then begin
    commit(true);
    hused[side] := true;
    sheetprint(false)
  end else
    (* лист не печатался - номер страницы не тратим *)
    pnext := pageno;
  newsheet;
  if fir then begin
    (* первая карта блока разбирается FIRCAR до начала страницы:
       формат действует немедленно *)
    setfmt(f);
    pagestart
  end else begin
    (* смена формата в середине текста - с новой страницы:
       формат применит очередной pagestart *)
    fmpending := f;
    freshpg := true
  end
end;

(* ---------------- таблицы ---------------- *)

(* разбор карты *ST (колонки) или *SL (линейки) *)
procedure tabledef(withline: boolean);
var
  nums: array [1..16] of integer;
  nnums, i, v, a, b: integer;
  loop: boolean;
begin
  flushq(false);
  commit(true);
  if not withline then
    cpos := cpos + 1;   (* литера T в ST *)
  nnums := 0;
  loop := true;
  while loop do begin
    while (cpos <= cwv) and (card[cpos] = ' ') do cpos := cpos + 1;
    if cpos > cwv then loop := false
    else if (card[cpos] < '0') or (card[cpos] > '9') then
      klaida(61)
    else begin
      v := 0;
      while (cpos <= cwv) and (card[cpos] >= '0') and (card[cpos] <=
         '9') do begin
        v := v * 10 + (ord(card[cpos]) - 48);
        cpos := cpos + 1
      end;
      nnums := nnums + 1;
      if nnums <= 16 then nums[nnums] := v
    end
  end;
  if withline then begin
    (* SL: линейки в позициях, колонки между ними *)
    if nnums < 2 then klaida(62);
    tbn := nnums;
    tbn2 := nnums - 1;
    for i := 1 to nnums do begin
      if nums[i] > fldw then klaida(64);
      tslpos[i] := curflda + nums[i] - 1
    end;
    for i := 1 to nnums - 1 do begin
      tbda[i] := tslpos[i] + 1;
      tbdw[i] := tslpos[i + 1] - tslpos[i] - 1;
      if tbdw[i] <= 0 then klaida(64)
    end
  end else begin
    (* ST: пары начало-конец *)
    if nnums mod 2 <> 0 then klaida(62);
    tbn2 := nnums div 2;
    tbn := 0;
    for i := 1 to nnums div 2 do begin
      a := nums[2 * i - 1];
      b := nums[2 * i];
      if b > fldw then klaida(64);
      tbda[i] := curflda + a - 1;
      tbdw[i] := b - a + 1;
      if tbdw[i] <= 0 then klaida(64)
    end
  end;
  tabon := true;
  tabline := withline;
  tcol := 0;
  trows := 0;
  tcln := 0;
  incell := false;
  for i := 1 to 8 do begin
    tcnt[i] := 0;
    prevnd[i] := false
  end
end;

(* выдача строки таблицы: линейка сверху, затем ячейки рядом *)
procedure tablerow;
var
  r: rowty;
  h, i, k2, j: integer;
  vis: boolean;
begin
  h := 0;
  for k2 := 1 to trows do
    if tcnt[k2] > h then h := tcnt[k2];
  if tabline and (h > 0) then begin
    clrrow(r);
    for j := tslpos[1] to tslpos[tbn] do r[j] := '-';
    for j := 1 to tbn do r[tslpos[j]] := 'I';
    for k2 := 1 to trows do
      if rownu[k2] or prevnd[k2] then
        for j := tslpos[k2] + 1 to tslpos[k2 + 1] - 1 do
          r[j] := ' ';
    commitrow(r, true)
  end;
  for i := 1 to h do begin
    clrrow(r);
    for k2 := 1 to trows do
      if i <= tcnt[k2] then
        for j := 1 to tbdw[k2] do
          r[tbda[k2] + j - 1] := tline[k2][i][tbda[k2] + j - 1];
    if tabline then
      for j := 1 to trows + 1 do begin
        vis := true;
        if (j <= trows) and rownol[j] then vis := false;
        if (j > 1) and rownr[j - 1] then vis := false;
        if (j <= tbn) and vis then r[tslpos[j]] := 'I'
      end;
    commitrow(r, true)
  end;
  for k2 := 1 to trows do prevnd[k2] := rownd[k2];
  for k2 := 1 to 8 do tcnt[k2] := 0
end;

(* закрытие текущей ячейки *)
procedure cellend;
begin
  flushq(false);
  commit(true);
  incell := false;
  rownol[tcol] := cnol;
  rownr[tcol] := cnr;
  rownu[tcol] := cnu;
  rownd[tcol] := cnd;
  tcnt[tcol] := tcln;
  flda := svflda;
  fldw := svfldw
end;

(* открытие ячейки k *)
procedure cellstart(k2: integer);
begin
  if incell then cellend;
  if (k2 <= tcol) and (tcol > 0) then begin
    (* возврат к меньшему номеру колонки - новая строка таблицы *)
    tablerow;
    trows := 0;
    tcol := 0
  end;
  if k2 > trows then trows := k2;
  if k2 > tbn2 then klaida(66);
  tcol := k2;
  tcln := 0;
  incell := true;
  cnol := false; cnr := false; cnu := false; cnd := false;
  svflda := flda;
  svfldw := fldw;
  flda := tbda[k2];
  fldw := tbdw[k2];
  indon := false;
  clrrow(cur);
  curpos := curflda
end;

(* конец таблицы по карте с долларом *)
procedure tabledone;
var
  r: rowty;
  i, j, k2: integer;
begin
  if incell then cellend;
  if trows > 0 then tablerow;
  if tabline and (tbn >= 2) and (trows > 0) then begin
    clrrow(r);
    for j := tslpos[1] to tslpos[tbn] do r[j] := '-';
    for j := 1 to tbn do r[tslpos[j]] := 'I';
    for k2 := 1 to trows do
      if rownd[k2] then
        for j := tslpos[k2] + 1 to tslpos[k2 + 1] - 1 do
          r[j] := ' ';
    commitrow(r, true)
  end;
  tabon := false;
  incell := false;
  trows := 0;
  tcol := 0
end;

(* карта в режиме таблицы: ячейка k), продолжение или доллар *)
procedure tablecard;
var
  k2, v: integer;
  iscell: boolean;
  pp: integer;
begin
  if card[1] = '$' then begin
    tabledone;
    cpos := cwv + 1;
    exit
  end;
  pp := 1;
  while (pp <= CW) and (card[pp] = ' ') do pp := pp + 1;
  iscell := false;
  k2 := 0;
  if (pp <= CW) and (card[pp] >= '0') and (card[pp] <= '9') then begin
    v := 0;
    while (pp <= CW) and (card[pp] >= '0') and (card[pp] <= '9') do
       begin
      v := v * 10 + (ord(card[pp]) - 48);
      pp := pp + 1
    end;
    if (pp <= CW) and (card[pp] = ')') then begin
      iscell := true;
      k2 := v
    end
  end;
  if iscell then begin
    cpos := pp + 1;
    cellstart(k2);
    scancard
  end else if incell then begin
    (* продолжение ячейки *)
    cpos := 1;
    scancard
  end else
    klaida(66)
end;

(* ---------------- макроопределения ---------------- *)

(* *nM=: тело до знака доллара, может занимать несколько карт *)
procedure macdef;
var
  c: char;
  done: boolean;
  i: integer;
begin
  if nn1 <> mkcnt + 1 then klaida(91);
  mkcnt := mkcnt + 1;
  mkbl := 0;
  done := false;
  while not done do begin
    while (cpos <= cwv) and (not done) do begin
      c := card[cpos];
      cpos := cpos + 1;
      if c = '$' then
        done := true
      else if mkbl < MKLEN then begin
        mkbl := mkbl + 1;
        mkbuf[mkbl] := c
      end
    end;
    if not done then begin
      getcard;
      if eofin then klaida(91)
    end
  end;
  for i := 1 to MKLEN do mktx[mkcnt][i] := ' ';
  for i := 1 to mkbl do mktx[mkcnt][i] := mkbuf[i];
  mkln[mkcnt] := mkbl
end;

(* *nM: вставка макро n.  Раскрытие БЕЗ рекурсии: scancard -> command
   -> macins -> scancard переполняла стек времени исполнения 15.1
   (OVERANGE).  macins лишь запоминает прерванную карту (mksav/mksl/
   mksq) и кладёт в card первый кусок тела; сканирование продолжается
   в текущем вызове scancard.  Окончание куска, продолжение
   прерванной карты и снятие уровня делает macstep из главного цикла.
   Состояние уровней: mknum/mkpp/mkres, глубина mksp <= TCDEEP. *)
procedure macins;
var
  ln, i: integer;
begin
  if (nn1 < 1) or (nn1 > mkcnt) then begin
    klaida(91);
    exit
  end;
  if mksp >= TCDEEP then begin
    klaida(91);
    exit
  end;
  if tabon or listing then begin
    (* в таблицах и листингах макросы не раскрываются *)
    klaida(91);
    exit
  end;
  mksp := mksp + 1;
  mksav[mksp] := card;
  mksl[mksp] := cwv;
  mksq[mksp] := cpos;
  mknum[mksp] := nn1;
  mkpp[mksp] := 1;
  mkres[mksp] := false;
  (* первый кусок тела - в card, сканирует текущий вызов scancard *)
  ln := mkln[nn1];
  if ln > CW then ln := CW;
  for i := 1 to 80 do card[i] := ' ';
  for i := 1 to ln do card[i] := mktx[nn1][i];
  cwv := ln;
  cpos := 1;
  mkpp[mksp] := ln + 1
end;

(* шаг раскрытия макро из главного цикла: очередной кусок тела,
   продолжение прерванной карты или снятие уровня *)
procedure macstep;
var
  ln, i: integer;
begin
  if mkpp[mksp] <= mkln[mknum[mksp]] then begin
    (* следующий кусок тела макро *)
    ln := mkln[mknum[mksp]] - mkpp[mksp] + 1;
    if ln > CW then ln := CW;
    for i := 1 to 80 do card[i] := ' ';
    for i := 1 to ln do
      card[i] := mktx[mknum[mksp]][mkpp[mksp] + i - 1];
    cwv := ln;
    cpos := 1;
    mkpp[mksp] := mkpp[mksp] + ln;
    scancard
  end else if not mkres[mksp] then begin
    (* тело исчерпано: продолжить прерванную карту *)
    mkres[mksp] := true;
    card := mksav[mksp];
    cwv := mksl[mksp];
    cpos := mksq[mksp];
    scancard
  end else
    mksp := mksp - 1
end;

(* ---------------- листинг программ ---------------- *)

(* карта режима *MF: печать как есть с позиции c+3 *)
procedure listcard;
var
  r: rowty;
  i: integer;
  isend: boolean;
begin
  if (card[1] = '/') and (card[2] = '/') and (card[3] = '/') then begin
    listing := false;
    exit
  end;
  clrrow(r);
  for i := 1 to CW do
    if card[i] <> ' ' then r[i + 3] := card[i];
  commitrow(r, false);
  isend := false;
  i := 1;
  while (i <= CW - 2) and (card[i] = ' ') do i := i + 1;
  if (card[i] = 'E') and (card[i + 1] = 'N') and (card[i + 2] = 'D') and
     ((i + 2 = CW) or (card[i + 3] = ' ') or (card[i + 3] = '.')) then
    isend := true;
  if isend then begin
    clrrow(r);
    commitrow(r, false);
    commitrow(r, false)
  end
end;

(* ---------------- сканер команд ---------------- *)

(* обработка команды после звездочки *)
procedure command;
var
  c, c2, c3: char;
  hasnum: boolean;
  a, b, i: integer;
begin
  nn1 := 1;
  hasnum := false;
  if (cpos <= cwv) and (card[cpos] >= '0') and (card[cpos] <= '9')
     then begin
    nn1 := 0;
    while (cpos <= cwv) and (card[cpos] >= '0') and (card[cpos] <=
       '9') do begin
      nn1 := nn1 * 10 + (ord(card[cpos]) - 48);
      cpos := cpos + 1
    end;
    hasnum := true
  end;
  if cpos > cwv then exit;
  c := card[cpos];
  cpos := cpos + 1;
  if c = 'F' then begin
    if cpos <= cwv then begin
      c2 := card[cpos];
      cpos := cpos + 1;
      if nn1 > 0 then fillrest(c2, nn1);
      posmode := true
    end
  end else if c = 'T' then begin
    flushq(false);
    commit(true);
    posmode := false;
    centerrest(cpos);
    cpos := cwv + 1;
    empties(2)
  end else if c = 'M' then begin
    if (cpos <= cwv) and (card[cpos] = 'F') then begin
      cpos := cpos + 1;
      listing := true;
      cpos := cwv + 1
    end else if (cpos <= cwv) and (card[cpos] = 'C') then begin
      cpos := cpos + 1;
      if (cpos <= cwv) and (card[cpos] = 'S') then begin
        cpos := cpos + 1;
        if not readnum(a) then klaida(20);
        if not readnum(b) then klaida(20);
        flushq(false);
        commit(true);
        setmcs(a, b)
      end else if (cpos <= cwv) and (card[cpos] = 'P') then begin
        cpos := cpos + 1;
        if not readnum(a) then klaida(20);
        if not readnum(b) then klaida(20);
        if (a > 127) or (b > 127) then klaida(40)
      end else
        klaida(10)
    end else if (cpos <= cwv) and (card[cpos] = 'D') then begin
      cpos := cpos + 1;
      flushq(false);
      commit(true);
      posmode := false;
      centerrest(cpos);
      cpos := cwv + 1
    end else if (cpos <= cwv) and (card[cpos] = '=') then begin
      cpos := cpos + 1;
      macdef
    end else
      macins
  end else if c = 'S' then begin
    if (cpos <= cwv) and (card[cpos] = 'T') then begin
      if (cpos + 1 <= cwv) and (card[cpos + 1] >= '0') and
         (card[cpos + 1] <= '9') then
        tabledef(false)
      else begin
        cpos := cpos + 1;
        if cpos > cwv then klaida(10);
        c2 := card[cpos];
        cpos := cpos + 1;
        if c2 = 'A' then
          newfmt(2, hasnum and (nn1 = 1))
        else if c2 = 'O' then
          newfmt(0, hasnum and (nn1 = 1))
        else if c2 = 'P' then begin
          stpon := true;
          stponly := (nn1 = 1);
          stpl := 0;
          for i := cpos to cwv do
            if card[i] <> ' ' then stpl := i - cpos + 1;
          for i := 1 to stpl do stp[i] := card[cpos + i - 1];
          cpos := cwv + 1;
          (* страница ещё пуста - штамп ставится сразу, иначе он
             появился бы только со следующей *)
          stpend := true
        end else if c2 = 'G' then begin
          stgon := true;
          stgonly := (nn1 = 1);
          stgl := 0;
          for i := cpos to cwv do
            if card[i] <> ' ' then stgl := i - cpos + 1;
          for i := 1 to stgl do stg[i] := card[cpos + i - 1];
          cpos := cwv + 1
        end else if c2 = 'N' then begin
          (* сдвиг штампа - принимается без действия *)
        end else
          klaida(10)
      end
    end else if (cpos <= cwv) and (card[cpos] = 'L') then begin
      cpos := cpos + 1;
      tabledef(true)
    end else begin
      flushq(false);
      commit(true);
      if nn1 > 1 then empties(nn1 - 1);
      indon := true
    end
  end else if c = 'L' then begin
    (* SL - таблица с линейками *)
    tabledef(true)
  end else if c = '/' then begin
    flushq(false);
    (* пустая текущая строка не сдвигается на лист: первая карта
       */ *D рисунка не должна давать пустую текстовую строку *)
    if curpos > curflda then
      commit(true)
    else
      curpos := curflda;
    posmode := false;
    if nn1 > 1 then empties(nn1 - 1)
  end else if c = 'P' then begin
    flushq(false);
    (* на свежей странице без текста *P не пишет пустую строку
       и не тратит номер страницы *)
    if (not freshpg) or (curpos > curflda) then
      commit(true);
    posmode := false;
    for i := 1 to nn1 do pageend
  end else if c = 'E' then begin
    endtxt := true;
    posmode := false;
    cpos := cwv + 1
  end else if c = 'G' then begin
    flushq(false);
    posmode := true;
    pp := curflda + nn1 - 1;
    if pp > curpos then curpos := pp
  end else if c = 'C' then begin
    if cpos <= cwv then begin
      c2 := card[cpos];
      cpos := cpos + 1;
      putrep(c2, nn1);
      posmode := true
    end
  end else if c = 'H' then begin
    hword(nn1)
  end else if c = 'D' then begin
    verbatim;
    posmode := true;
    cpos := cwv + 1
  end else if c = 'N' then begin
    (* *nN: номер следующей страницы; перед знаком команды пробел
       не обязателен - *254N*1RL задаёт номер так же, как *254N_.
       На свежей странице (ничего не напечатано) номер действует
       на неё сразу, иначе - на следующую (pnext) *)
    if cpos <= cwv then begin
      c2 := card[cpos];
      if c2 = ' ' then begin
        if rowno = 0 then begin
          pageno := nn1;
          hpno[side] := nn1
        end else
          pnext := nn1;
        cpos := cpos + 1
      end else begin
        (* номер регистрируется в первой карте блока (FIRCAR) или
           перед пробелом; *7N*P номер не задаёт *)
        if hasnum and fir then begin
          if rowno = 0 then begin
            pageno := nn1;
            hpno[side] := nn1
          end else
            pnext := nn1
        end;
        if c2 = 'N' then begin
          numon := false;
          cpos := cpos + 1
        end else if (c2 = 'L') or (c2 = 'R') or (c2 = 'U') or (c2 =
           'D') then begin
          cpos := cpos + 1;
          if tabon then begin
            if c2 = 'L' then cnol := true;
            if c2 = 'R' then cnr := true;
            if c2 = 'U' then cnu := true;
            if c2 = 'D' then cnd := true
          end else
            addch(c2)
        end else if (c2 >= 'A') and (c2 <= 'Z') then begin
          (* N поглощается, буква остаётся текстом *)
          addch(c2);
          cpos := cpos + 1
        end
        (* перед не-буквой N просто опускается *)
      end
    end else if hasnum and fir then begin
      if rowno = 0 then begin
        pageno := nn1;
        hpno[side] := nn1
      end else
        pnext := nn1
    end
  end else if c = 'O' then begin
    if cpos <= cwv then begin
      c2 := card[cpos];
      cpos := cpos + 1;
      if c2 = 'L' then begin
        if (cpos <= cwv) and (card[cpos] = 'R') then cpos := cpos + 1;
        flushq(false);
        fillon := false
      end else if c2 = 'R' then begin
        if (cpos <= cwv) and (card[cpos] = 'U') then cpos := cpos + 1;
        newfmt(0, hasnum and (nn1 = 1))
      end else
        klaida(10)
    end
  end else if c = 'W' then begin
    group(nn1, true)
  end else if c = '(' then begin
    group(nn1, false)
  end else if c = 'R' then begin
    if cpos <= cwv then begin
      c2 := card[cpos];
      cpos := cpos + 1;
      if c2 = 'T' then begin
        flushq(false);
        fillon := true
      end else if c2 = 'L' then begin
        rln := nn1
      end else if c2 = 'C' then begin
        rcn := nn1
      end else if c2 = 'G' then begin
        rgon := true
      end else if c2 = 'U' then begin
        newfmt(1, hasnum and (nn1 = 1))
      end else if c2 = 'F' then begin
        if cpos <= cwv then begin
          c2 := card[cpos];
          cpos := cpos + 1;
          fillto(nn1, c2);
          posmode := true
        end
      end else
        klaida(10)
    end
  end else if c = 'K' then begin
    if not readnum(a) then klaida(10);
    if cpos <= cwv then begin
      c2 := card[cpos];
      cpos := cpos + 1;
      putrep(c2, a);
      posmode := true
    end
  end else if hasnum then begin
    (* число без команды - режим листинга *)
    listing := true;
    cpos := cwv + 1
  end else
    klaida(10)
end;

(* просмотр карты: команды и текст *)
procedure scancard;
var
  c: char;
begin
  while cpos <= cwv do begin
    c := card[cpos];
    cpos := cpos + 1;
    if c = '*' then begin
      if (cpos <= cwv) and (card[cpos] <> ' ') then
        command
    end else
      addch(c)
  end;
  (* граница карты: слово продолжается, если 72-я позиция занята *)
  if wleng > 0 then begin
    if (mksp > 0) or (cwv < CW) then
      addword
    else if card[CW] = ' ' then
      addword
  end
end;

(* ---------------- главная программа ---------------- *)

begin
  setfmt(0);
  (* статическая память чистых упакованных строк листа содержит нули,
     а не пробелы: первый newsheet заливает пробелами весь htxt, дальше
     достаточно чистить занятые строки (пишутся только непробельные) *)
  hrows[0] := 66;
  hrows[1] := 66;
  newsheet;
  pageno := 0;
  pnext := 0;
  numon := true;
  pgfirst := true;
  stpend := false;
  rgon := false;
  rln := 0;
  rcn := 0;
  fillon := true;
  indon := false;
  listing := false;
  endtxt := false;
  stpon := false;
  stgon := false;
  stponly := false;
  stgonly := false;
  stpl := 0;
  stgl := 0;
  tabon := false;
  incell := false;
  trows := 0;
  tcol := 0;
  mkcnt := 0;
  mksp := 0;
  fmpending := -1;
  fir := false;
  nw := 0;
  wleng := 0;
  wrcl := 0;
  cwv := 72;
  pagestart;

1: (* ключевое слово блока *)
  getcard;
  if eofin then goto 9;
  if (card[1] = '*') and (card[2] = 'R') and (card[3] = 'E') and
     (card[4] = 'D') then begin
    endtxt := false;
    fir := true;
    while not endtxt do begin
      getcard;
      if eofin then
        endtxt := true
      else if listing then
        listcard
      else if tabon then
        tablecard
      else begin
        (* раскрытие макро без рекурсии: macstep докручивает куски
           тел, продолжения карт и снятие уровней *)
        scancard;
        while mksp > 0 do
          macstep;
        if stpend then begin
          stpend := false;
          if rowno = 0 then
            putstp
        end;
        (* FIRCAR действует только на первую карту блока *)
        fir := false
      end
    end;
    flushq(false);
    commit(true);
    if rowno > 0 then hused[side] := true;
    sheetprint(true);
    newsheet;
    goto 1
  end;
  if (card[1] = '*') and (card[2] = 'E') and (card[3] = 'N') and
     (card[4] = 'D') then
    goto 9;
  klaida(100);
9: stop
end.
