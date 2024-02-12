[![Gitter](https://badges.gitter.im/OpenViX/community.svg)](https://gitter.im/OpenViX/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## OpenViX buildserver requirements: ##

> Ubuntu 22.04.1 LTS (Kernel 5.15.0) 64-bit

## minimum hardware requirement for image build (building feeds may require more):

> RAM:  16GB
> SWAP: 16GB (if building feeds then RAM+SWAP should be larger)> 
> CPU:  Multi core\thread Model
> HDD:  for Single Build 250GB Free, for Multibuild 500GB or more

## OpenViX python3 is built using oe-alliance build-environment and several git repositories: ##

> [https://github.com/oe-alliance/oe-alliance-core/tree/5.4](https://github.com/oe-alliance/oe-alliance-core/tree/5.4 "OE-Alliance")
>
> [https://github.com/OpenViX/enigma2/tree/Release](https://github.com/OpenViX/enigma2/tree/Release "openViX E2")


----------

# Building Instructions #

1 - Install packages on your buildserver

    sudo apt-get install -y autoconf automake bison bzip2 chrpath coreutils cpio curl cvs debianutils default-jre default-jre-headless diffstat flex g++ gawk gcc gcc-12 gcc-multilib g++-multilib gettext git git-core gzip help2man info iputils-ping java-common libc6-dev libegl1-mesa libglib2.0-dev libncurses5-dev libperl4-corelibs-perl libproc-processtable-perl libsdl1.2-dev libserf-dev libtool libxml2-utils make ncurses-bin patch perl pkg-config psmisc python3 python3-git python3-jinja2 python3-pexpect python3-pip python-setuptools qemu quilt socat sshpass subversion tar texi2html texinfo unzip wget xsltproc xterm xz-utils zip zlib1g-dev zstd fakeroot lz4 liblz4-tool

----------
2 - Set python3 as preferred provider for python

    sudo update-alternatives --install /usr/bin/python python /usr/bin/python2 1
    sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 2
    sudo update-alternatives --config python
    select python3

----------
3 - Set your shell to /bin/bash.

    sudo dpkg-reconfigure dash
    When asked: Install dash as /bin/sh?
    select "NO"

----------
4 - modify max_user_watches

    echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf

    sudo sysctl -n -w fs.inotify.max_user_watches=524288

----------
5 - Add user openvixbuilder

    sudo adduser openvixbuilder

----------
6 - Switch to user openvixbuilder

    su openvixbuilder

----------
7 - Switch to home of openvixbuilder

    cd ~

----------
8 - Create folder openvix

    mkdir -p ~/openvix

----------
9 - Switch to folder openvix

    cd openvix

----------
10 - Clone oe-alliance git

    git clone https://github.com/oe-alliance/build-enviroment.git -b 5.4

----------
11 - Switch to folder build-enviroment

    cd build-enviroment

----------
12 - Update build-enviroment

    make update

----------
13 - Initialise the first machine so site.conf gets created

    MACHINE=zgemmah9combo DISTRO=openvix DISTRO_TYPE=release make init

----------
14 - Update site.conf

    - BB_NUMBER_THREADS, PARALLEL_MAKE set to number of threads supported by the CPU
    - add/modify DL_DIR = " location for build sources " to point to a location where you can save derived build sources,
    this will reduce build time in fetching these sources again.

----------
15 - Building image with feeds  e.g.:-

	MACHINE=vuultimo4k DISTRO=openvix DISTRO_TYPE=release make image

----------
16 - Building an image without feeds (Build time 1-2h)

    MACHINE=zgemmah9combo DISTRO=openvix DISTRO_TYPE=release make enigma2-image

----------
17 - Building feeds only

    MACHINE=zgemmah9combo DISTRO=openvix DISTRO_TYPE=release make feeds

