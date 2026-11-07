(* Тест 11: выживание М2/М3/М4 в цикле при приёме с индексом-выражением
   6*рпw+j (умножение) и с базой+смещением. *)
program рпт11(input, output);
type
  rowty = array [1..128] of char;
  prow = packed array [1..128] of char;
  слово = record case integer of
    0: (ц: integer);
    1: (м: set of 0..47)
  end;
var
  src: prow;
  a, b, c: rowty;
  маска: слово;
  рбyф: array [1..2] of integer;
  падр: ^слово;
  рпw, j, k: integer;
begin
  маска.м := [40..47];
  for k := 1 to 128 do
    a[k] := chr(32 + (k * 7) mod 96);
  for k := 1 to 128 do
    src[k] := a[k];
  for k := 1 to 128 do
    c[k] := src[k];
  падр := REF(маска);
  besm(00000400002B);              (* АТI2 *)
  падр := REF(рбyф[1]);
  besm(00000400004B);              (* АТI4 *)
  падр := REF(src[1]);
  besm(00000400003B);              (* АТI3 *)
  (* приём с умножением 6*рпw+j *)
  for рпw := 0 to 3 do begin
    for j := 1 to 6 do begin
      besm(00014100000B);          (* СЧ М3 *)
      besm(00000360100B);          (* АСН 64 *)
      besm(00010110000B);          (* ААХ М2 *)
      besm(00020000000B);          (* ЗП (М4)+0 *)
      b[6 * рпw + j] := chr(рбyф[1])
    end
  end;
  write('УМНОЖ: ');
  for k := 1 to 24 do
    write(ord(b[k]):1, ',');
  writeln(' (всё 39?)');
  (* приём с базой bb := 6*рпw и смещением *)
  for рпw := 0 to 3 do begin
    j := 6 * рпw;
    for k := 1 to 6 do begin
      besm(00014100000B);          (* СЧ М3 *)
      besm(00000360100B);          (* АСН 64 *)
      besm(00010110000B);          (* ААХ М2 *)
      besm(00020000000B);          (* ЗП (М4)+0 *)
      b[j + k] := chr(рбyф[1])
    end
  end;
  write('БАЗА:   ');
  for k := 1 to 24 do
    write(ord(b[k]):1, ',');
  writeln(' (всё 39?)')
end.
