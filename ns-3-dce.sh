#!/bin/bash

env_path=$1
outdir=$2
shift 2

sudo mount --bind $outdir $env_path/out
sudo chroot $env_path su simbricks -c "/run_dce.sh $@"
sudo umount $env_path/out
