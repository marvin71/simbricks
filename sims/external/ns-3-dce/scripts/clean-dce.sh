#!/bin/bash

path=$1

if [ -d "$path/dce-env" ]; then
    sudo rm -rf "$path/dce-env"
fi

rm -rf "$path/ready"