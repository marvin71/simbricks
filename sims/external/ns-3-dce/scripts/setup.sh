#!/bin/bash

userid=$1
groupid=$2
shift 2

# add additional sources to apt
echo "deb http://archive.ubuntu.com/ubuntu focal main restricted" \
    > /etc/apt/sources.list
echo "deb http://archive.ubuntu.com/ubuntu focal-updates main restricted" \
    >> /etc/apt/sources.list
echo "deb http://archive.ubuntu.com/ubuntu focal universe" \
    >> /etc/apt/sources.list
echo "deb http://archive.ubuntu.com/ubuntu focal-updates universe" \
    >> /etc/apt/sources.list

apt-get update \
 && DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Berlin \
    apt-get install -y \
    bison \
    cmake \
    g++ \
    gawk \
    gcc \
    git \
    libc6-dev \
    libboost-coroutine-dev \
    libboost-fiber-dev \
    libboost-iostreams-dev \
    libpcap-dev \
    make \
    ninja-build \
    pkgconf \
    python-is-python3 \
    python3 \
    python3-pip \
    rsync \
    unzip \
    wget \

pip3 install requests distro

# clean apt lists and cache
rm -rf /var/lib/apt/lists/*
rm -rf /var/cache/apt/*

# create non-root user simbricks
groupadd --gid $groupid simbricks
useradd --uid $userid --gid $groupid -m simbricks --shell /bin/bash
mkdir workspace
chown simbricks:simbricks workspace

#run the following with user simbricks
su simbricks << "EOF"
cd /workspace
git clone https://github.com/marvin71/bake-git.git
cd bake-git
git switch simbricks
python3 bake.py configure -p dce-simbricks-ns3
python3 bake.py download
python3 bake.py build -j $(nproc)
EOF

# remove unnecessary source and build files
if [ "$1" = "clean" ]; then
    cd /workspace/bake-git
    rm -rf build/glibc-build
    mkdir savedir
    mv source/ns-3-dce savedir
    rm -rf source/*
    mv savedir/ns-3-dce source
    rmdir savedir
fi
