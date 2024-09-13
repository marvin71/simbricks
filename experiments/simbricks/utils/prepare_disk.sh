#!/bin/bash

chmod 777 "$1".d/guest/*
chmod 777 "$1".d/guest/.*
$2 create -f raw $1 $3
mkfs.ext4 $1
sudo mount -o loop $1 "$1".d/mount/
sudo mv "$1".d/guest/ "$1".d/mount/
sudo mkdir "$1".d/mount/data
sudo umount "$1".d/mount/