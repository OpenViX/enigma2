## Our buildserver is currently running on: ##

> Ubuntu 18.04.3 LTS (GNU/Linux 4.15.0-65-generic x86_64)

## teamBlue 6.4 (based on openPLi) is build using oe-alliance build-environment "4.3" and several git repositories: ##

> [https://github.com/oe-alliance/oe-alliance-core/tree/4.3](https://github.com/oe-alliance/oe-alliance-core/tree/4.4 "OE-Alliance")
> 
> [https://github.com/teamblue-e2/enigma2/tree/master](https://github.com/teamblue-e2/enigma2/tree/6.4 "teamBlue E2")
> 
> [https://github.com/teamblue-e2/skin/tree/master](https://github.com/teamblue-e2/skin/tree/master "teamBlue Skin")

> and a lot more...


----------

# Building Instructions #

1 - Install packages on your buildserver

    sudo apt-get install -y autoconf automake bison bzip2 chrpath coreutils cpio curl cvs debianutils default-jre default-jre-headless diffstat flex g++ gawk gcc gcc-8 gcc-multilib gettext git git-core gzip help2man info iputils-ping java-common libc6-dev libegl1-mesa libglib2.0-dev libncurses5-dev libperl4-corelibs-perl libproc-processtable-perl libsdl1.2-dev libserf-dev libtool libxml2-utils make ncurses-bin patch perl pkg-config psmisc python3 python3-git python3-jinja2 python3-pexpect python3-pip python-setuptools qemu quilt socat sshpass subversion tar texi2html texinfo unzip wget xsltproc xterm xz-utils zip zlib1g-dev

----------
2 - Set your shell to /bin/bash

    sudo dpkg-reconfigure dash
    When asked: Install dash as /bin/sh?
    select "NO"

----------
3 - modify max_user_watches

    echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf

    sysctl -n -w fs.inotify.max_user_watches=524288

----------
4 - Add user teambluebuilder

    sudo adduser teambluebuilder

----------
5 - Switch to user teambluebuilder

    su teambluebuilder

----------
6 - Switch to home of teambluebuilder

    cd ~

----------
7 - Create folder teamblue

    mkdir -p ~/teamblue

----------
8 - Switch to folder teamblue

    cd teamblue

----------
9 - Clone oe-alliance git

    git clone git://github.com/oe-alliance/build-enviroment.git -b 4.4

----------
10 - Switch to folder build-enviroment

    cd build-enviroment

----------
11 - Update build-enviroment

    make update

----------
12 - Finally you can start building a image

    MACHINE=gbquad4k DISTRO=teamblue make image


Build Status - branch master: [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=master)](https://travis-ci.org/teamblue-e2/enigma2)

Build Status - branch 6.4:    [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=6.4)](https://travis-ci.org/teamblue-e2/enigma2)
