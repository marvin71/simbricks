#!/bin/sh
cd /tmp
mkdir guest
mount /dev/sdb guest
cd guest
./run.sh
