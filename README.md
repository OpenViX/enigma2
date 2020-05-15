## Our buildserver is currently running on: ##

> Ubuntu 18.04.3 LTS (GNU/Linux 4.15.0-65-generic x86_64)

## teamBlue 6.5 (based on openPLi) is build using oe-alliance build-environment "4.5" and several git repositories: ##

> [https://github.com/oe-alliance/oe-alliance-core/tree/4.5](https://github.com/oe-alliance/oe-alliance-core/tree/4.5 "OE-Alliance")
> 
> [https://github.com/teamblue-e2/enigma2/tree/6.5](https://github.com/teamblue-e2/enigma2/tree/6.5 "teamBlue E2")
> 
> [https://github.com/teamblue-e2/skin/tree/master](https://github.com/teamblue-e2/skin/tree/master "teamBlue Skin")

> and a lot more...


----------

# Building Instructions #

1 - Install packages on your buildserver

    sudo apt-get install -y autoconf automake bison bzip2 chrpath coreutils cpio curl cvs debianutils default-jre default-jre-headless diffstat flex g++ gawk gcc gcc-8 gettext git git-core gzip help2man info iputils-ping java-common libc6-dev libegl1-mesa libglib2.0-dev libncurses5-dev libperl4-corelibs-perl libproc-processtable-perl libsdl1.2-dev libserf-dev libtool libxml2-utils make ncurses-bin patch perl pkg-config psmisc python3 python3-git python3-jinja2 python3-pexpect python3-pip python-setuptools qemu quilt socat sshpass subversion tar texi2html texinfo unzip wget xsltproc xterm xz-utils zip zlib1g-dev

----------
2 - Set your shell to /bin/bash

    sudo dpkg-reconfigure dash
    When asked: Install dash as /bin/sh?
    select "NO"

----------
3 - Use update-alternatives for having gcc redirected automatically to gcc-8

    sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-7 700 --slave /usr/bin/g++ g++ /usr/bin/g++-7
    sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-8 800 --slave /usr/bin/g++ g++ /usr/bin/g++-8

----------
4 - Repair g++ after gcc8 installation

    sudo apt-get remove -y  g++
    sudo apt-get install -y  g++

----------
5 - modify max_user_watches

    echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
    sysctl -n -w fs.inotify.max_user_watches=524288

----------
6 - Add user teambluebuilder

    sudo adduser teambluebuilder

----------
7 - Switch to user teambluebuilder

    su teambluebuilder

----------
8 - Switch to home of teambluebuilder

    cd ~

----------
9 - Create folder teamblue

    mkdir -p ~/teamblue

----------
10 - Switch to folder teamblue

    cd teamblue

----------
11 - Clone oe-alliance git

    git clone git://github.com/oe-alliance/build-enviroment.git -b 4.5

----------
12 - Switch to folder build-enviroment

    cd build-enviroment

----------
13 - Update build-enviroment

    make update

----------
14 - Finally you can start building a image

    MACHINE=gbquad4k DISTRO=teamblue make image


Build Status - branch master: [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=master)](https://travis-ci.org/teamblue-e2/enigma2)

Build Status - branch 6.5:    [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=6.5)](https://travis-ci.org/teamblue-e2/enigma2)
