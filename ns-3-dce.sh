#!/bin/bash

env_path=$1
outdir=$2
shift 2

cmd="/run_dce.sh"
for var in "$@"
do
	cmd="$cmd \"$var\""
done

sudo mount --bind /etc/passwd $env_path/etc/passwd
sudo mount -o remount,ro,bind $env_path/etc/passwd
sudo mount --bind /etc/group $env_path/etc/group
sudo mount -o remount,ro,bind $env_path/etc/group
sudo mount --bind /etc/shadow $env_path/etc/shadow
sudo mount -o remount,ro,bind $env_path/etc/shadow
sudo mount --bind $outdir $env_path/out

sudo chroot $env_path su $(whoami) -c "$cmd"

sudo umount $env_path/etc/passwd
sudo umount $env_path/etc/group
sudo umount $env_path/etc/shadow
sudo umount $env_path/out
