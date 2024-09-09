#!/bin/bash

sudo mount -o loop $1 "$1".d/mount/
sudo mv "$1".d/mount/data "$1".d/
sudo umount "$1".d/mount/
sudo chown -R "$(id -u)":"$(id -g)" "$1".d/data/