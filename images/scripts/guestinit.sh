#!/bin/sh
mkdir /data
mount /dev/sdb /data
cp -r /data/guest /tmp
cd /tmp/guest
./run.sh
