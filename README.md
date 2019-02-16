## Our buildserver is currently running on: ##

> Ubuntu 16.04.5 LTS (GNU/Linux 4.9.58-xxxx-std-ipv6-64 x86_64)

## teamBlue 6.3 (based on openPLi) is build using oe-alliance build-environment "4.3" and several git repositories: ##

> [https://github.com/oe-alliance/oe-alliance-core/tree/4.3](https://github.com/oe-alliance/oe-alliance-core/tree/4.3 "OE-Alliance")
> 
> [https://github.com/teamblue-e2/enigma2/tree/master](https://github.com/teamblue-e2/enigma2/tree/6.3 "teamBlue E2")
> 
> [https://github.com/teamblue-e2/skin/tree/master](https://github.com/teamblue-e2/skin/tree/master "teamBlue Skin")

> and a lot more...


----------

# Building Instructions #

1 - Install packages on your buildserver

    sudo apt-get install -y autoconf automake bison bzip2 chrpath coreutils curl cvs default-jre default-jre-headless diffstat flex g++ gawk gcc gettext git-core gzip help2man htop info java-common libc6-dev libglib2.0-dev libperl4-corelibs-perl libproc-processtable-perl libssl-dev libtool libxml2-utils make ncdu ncurses-bin ncurses-dev patch perl pkg-config po4a python-setuptools quilt sgmltools-lite sshpass subversion swig tar texi2html texinfo wget xsltproc zip zlib1g-dev

----------
2 - Set your shell to /bin/bash

    sudo dpkg-reconfigure dash
    When asked: Install dash as /bin/sh?
    select "NO"

----------
3 - Add user teambluebuilder

    sudo adduser teambluebuilder

----------
4 - Switch to user teambluebuilder

    su teambluebuilder

----------
5 - Switch to home of teambluebuilder

    cd ~

----------
6 - Create folder teamblue

    mkdir -p ~/teamblue

----------
7 - Switch to folder teamblue

    cd teamblue

----------
8 - Clone oe-alliance git

    git clone git://github.com/oe-alliance/build-enviroment.git -b 4.3

----------
9 - Switch to folder build-enviroment

    cd build-enviroment

----------
10 - Update build-enviroment

    make update

----------
11 - Finally you can start building a image

    MACHINE=gbquad4k DISTRO=teamblue make image


Build Status - branch master: [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=master)](https://travis-ci.org/teamblue-e2/enigma2)

Build Status - branch 6.1:    [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=6.1)](https://travis-ci.org/teamblue-e2/enigma2)

Build Status - branch 6.2:    [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=6.2)](https://travis-ci.org/teamblue-e2/enigma2)

Build Status - branch 6.3:    [![Build Status](https://travis-ci.org/teamblue-e2/enigma2.svg?branch=6.3)](https://travis-ci.org/teamblue-e2/enigma2)
