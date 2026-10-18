#!/bin/sh -x
fn=`echo "$1" | tr '*/' '#_'`
cat << EOF > tmp$$
*name dtran
*disc:1/local
*file:siprod,67
*libra:23
*call ficmemory
*call setftn:one,long
*call dtran:67($1)
EOF
if [ -f "dtr/$fn.dtr" ]; then
	cat "dtr/$fn.dtr" >> tmp$$
fi
cat << EOF >> tmp$$
*edit
*r:1
*ll
*ee
*end file
EOF
mkdir -p build
dubna tmp$$ | sed '/,NAME,/,/,END,/!d' > build/$fn.dtran
if [ -s "build/$fn.dtran" ]; then
	rm tmp$$
else
	mv tmp$$ build/$fn.err
fi
