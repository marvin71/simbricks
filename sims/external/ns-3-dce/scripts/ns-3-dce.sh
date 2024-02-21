#!/bin/bash

env_path=$1
outdir=$2
shift 2

cmd="/run_dce.sh"
for var in "$@"
do
	cmd="$cmd \"$var\""
done

cleaned="false"
cleanup() {
	if [ "$cleaned" = "true" ]; then
		return 0
	fi
	cleaned="true"
	sudo umount $env_path/out
}

trap cleanup SIGINT SIGTERM

# wait a little bit so that mount doesn't fail
sleep 3
sudo mount --bind $outdir $env_path/out

chroot $env_path su simbricks -c "$cmd"
cleanup