(*=Y+*,p+*,u-*)
(* slovo: SCHA(M3)+ATI5; 6 izvlechenij v tmp; bez UTM: ATI3 v cikle *)
program hot2(input, output);
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
  tmp: array [1..6] of integer;
  сл: слово;
  падр: ^слово;
  w, j, k, err: integer;
begin
  маска.м := [40..47];
  for k := 1 to 128 do
    a[k] := chr(32 + (k * 7) mod 96);
  for k := 1 to 128 do
    src[k] := a[k];
  for k := 1 to 128 do
    c[k] := src[k];
  падр := REF(маска);
  besm(00000400002B);  (*ATI2*)
  падр := REF(tmp[1]);
  besm(00000400004B);  (*ATI4*)
  for w := 0 to 21 do begin
    падр := REF(src[6 * w + 1]);
    besm(00000400003B);  (*ATI3*)
    besm(00014100000B);  (*S*)
    besm(00000400005B);  (*TI5*)
    besm(00000360150B);  (*A104*)
    besm(00010110000B);  (*M*)
    besm(00020000000B);  (*Z1*)
    besm(00000360140B);  (*A96*)
    besm(00010110000B);  (*M*)
    besm(00020000001B);  (*Z2*)
    besm(00000360130B);  (*A88*)
    besm(00010110000B);  (*M*)
    besm(00020000002B);  (*Z3*)
    besm(00000360120B);  (*A80*)
    besm(00010110000B);  (*M*)
    besm(00020000003B);  (*Z4*)
    besm(00000360110B);  (*A72*)
    besm(00010110000B);  (*M*)
    besm(00020000004B);  (*Z5*)
    besm(00010110000B);  (*M*)
    besm(00020000005B);  (*Z6*)
    for j := 1 to 6 do
      if 6 * w + j <= 128 then
        b[6 * w + j] := chr(tmp[j]);
  end;
  err := 0;
  for k := 1 to 128 do
    if b[k] <> c[k] then
      err := err + 1;
  writeln('OSH:', err);
  writeln('B:', ord(b[1]), ord(b[2]), ord(b[7]), ord(b[8]),
          ord(b[126]), ord(b[127]), ord(b[128]));
  writeln('C:', ord(c[1]), ord(c[2]), ord(c[7]), ord(c[8]),
          ord(c[126]), ord(c[127]), ord(c[128]))
end.
