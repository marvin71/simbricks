#!/bin/bash

path=$1
setup_script=$2
run_script=$3

sudo debootstrap --variant=minbase focal "$path"/dce-env
sudo cp "$setup_script" "$path"/dce-env
sudo cp "$run_script" "$path"/dce-env
sudo chroot "$path"/dce-env /setup.sh $(id -u) $(id -g) clean