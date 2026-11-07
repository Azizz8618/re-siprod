(* Тест 19: даёт ли REF с переменным индексом верный адрес?
   рпw := 1; REF(src[6*рпw+1]) = REF(src[7]) - слово 1.
   Литера 7 должна быть 81. *)
program рпт19(input, output);
type
  rowty = array [1..128] of char;
  prow = packed array [1..128] of char;
  слово = record case integer of
    0: (ц: integer);
    1: (м: set of 0..47)
  end;
var
  src: prow;
  a, c: rowty;
  маска: слово;
  рбyф: array [1..2] of integer;
  падр: ^слово;
  рпw, k: integer;
begin
  маска.м := [40..47];
  for k := 1 to 128 do
    a[k] := chr(32 + (k * 7) mod 96);
  for k := 1 to 128 do
    src[k] := a[k];
  for k := 1 to 128 do
    c[k] := src[k];
  падр := REF(маска);
  besm(00000400002B);              (* АТI2: М2 := @маска *)
  падр := REF(рбyф[1]);
  besm(00000400004B);              (* АТI4: М4 := @рбyф[1] *)
  (* константный индекс: слово 1 *)
  падр := REF(src[7]);
  besm(00000400003B);              (* АТI3 *)
  besm(00014100000B);              (* СЧ М3 *)
  besm(00000360150B);              (* АСН 104 *)
  besm(00010110000B);              (* ААХ М2 *)
  besm(00020000000B);              (* ЗП (М4)+0 *)
  writeln('КОН: ', ord(c[7]));
  writeln('КОН2: ', рбyф[1]);
  (* переменный индекс: тоже слово 1 *)
  рбyф[1] := 0;
  рпw := 1;
  падр := REF(src[6 * рпw + 1]);
  besm(00000400003B);              (* АТI3 *)
  besm(00014100000B);              (* СЧ М3 *)
  besm(00000360150B);              (* АСН 104 *)
  besm(00010110000B);              (* ААХ М2 *)
  besm(00020000000B);              (* ЗП (М4)+0 *)
  writeln('ПЕР: ', ord(c[7]));
  writeln('ПЕР2: ', рбyф[1])
end.
