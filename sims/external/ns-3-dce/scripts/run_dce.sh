#!/bin/bash

cd /workspace/bake-git/source/ns-3-dce

cmd="dce-e2e-cc"
for var in "$@"
do
	cmd="$cmd \"$var\""
done

python3 waf --cwd "/out" --run "$cmd"
