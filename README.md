[![Gitter](https://badges.gitter.im/OpenViX/community.svg)](https://gitter.im/OpenViX/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

### 🤝 Contributing & Contact

OpenViX Enigma2 is created by users for users and we welcome every contribution. There are no highly paid developers. There are only users who have seen a problem and done their best to fix it. This means OpenVix will always need the contributions of users like you. How can you get involved?

For questions or feedback, feel free and please open an issue or contribute with a Pull Request. Or post on the [OpenViX forum](https://world-of-satellite.com/)

Pull requests are very welcome for:
- **Coding:** Developers can help by fixing a bug, adding new features, Integration improvements, Feature enhancements
- **Localization:** Translate into your native language.
- **Helping users:** Our support process relies on enthusiastic contributors like you to help others.

Your contribution is very welcome! Follow these steps:

1. 🍴 Fork this repository
2. 🔄 Create a branch for your feature
3. 💻 Make your changes
4. ✅ Commit using conventional messages
5. 📤 Push to your branch
6. 🔍 Open a Pull Request

Enjoy and help us improve it today. :)

### 🚨 Disclaimer

The project author is not responsible for how this software is used by others. It is not intended to be used for accessing or distributing copyrighted materials without authorization.
Users are solely responsible for determining the legality of their actions.

This repository has no control over the streams, links, or the legality of the content provided by the different hosts (including all mirror sites). It is the end user's responsibility to ensure the legal use of these streams, and we strongly recommend verifying that the content complies with all applicable laws, including copyright laws and regulations of your country's jurisdiction before use.

---

### 🤝 Contributing Details

For detailed contributing guidelines including testing procedures and AI policy, please see [CONTRIBUTING.md](https://github.com/OpenViX/enigma2/blob/Developer/doc/CONTRIBUTING.md).

---

## OpenViX buildserver requirements: ##

>Ubuntu 24.04 LTS (GNU/Linux 6.8.0-39-generic x86_64) or (Ubuntu 26.04 LTS (GNU/Linux 7.0.0-14-generic x86_64) - for OE-A 5.6 see note 15)

## minimum hardware requirement for image build (building feeds may require more):

> RAM:  16GB
> SWAP: 16GB (if building feeds then RAM+SWAP should be larger)> 
> CPU:  Multi core\thread Model
> HDD:  for Single Build 250GB Free, for Multibuild 500GB or more

## OpenViX python3 is built using oe-alliance build-environment and several git repositories: ##

> [https://github.com/oe-alliance/oe-alliance-core/tree/6.0](https://github.com/oe-alliance/oe-alliance-core/tree/6.0 "OE-Alliance")
>
> [https://github.com/OpenViX/enigma2/tree/Release](https://github.com/OpenViX/enigma2/tree/Release "openViX E2")


----------

# Building Instructions #

1 - Install packages on your buildserver

    sudo apt-get install -y autoconf automake bison bzip2 chrpath cmake coreutils cpio curl cvs debianutils default-jre default-jre-headless diffstat flex g++ gawk gcc gcc-12 gcc-multilib g++-multilib gettext git gzip help2man info iputils-ping java-common libc6-dev libc6-dev-i386 libglib2.0-dev libncurses-dev libperl4-corelibs-perl libproc-processtable-perl libsdl1.2-dev libserf-dev libtool libxml2-utils make ncurses-bin patch perl pkg-config psmisc python3 python3-git python3-html5lib python3-jinja2 python3-pexpect python3-pip python3-setuptools quilt socat sshpass subversion tar texi2html texinfo unzip wget xsltproc xterm xz-utils zip zlib1g-dev zstd fakeroot lz4 git-lfs

----------
2 - Set python3 as preferred provider for python

    sudo update-alternatives --install /usr/bin/python python /usr/bin/python2 1
    sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 2
    sudo update-alternatives --config python
    select python3

----------
3 - Set your shell to /bin/bash.

    sudo ln -sf /bin/bash /bin/sh

----------
4 - modify max_user_watches

    echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf

    sudo sysctl -n -w fs.inotify.max_user_watches=524288

----------
5 - Update apparmor profile

## Workaround for ubuntu issue [Allow bitbake to create user namespace](https://bugs.launchpad.net/ubuntu/+source/apparmor/+bug/2056555) ##
## Credit to Changqing Li (sandy-lcq), Karsten S. Opdal (karsten-s-opdal) and Ferry Toth (ftoth) ##
   
    echo 'kernel.apparmor_restrict_unprivileged_userns=0' | sudo tee /etc/sysctl.d/60-apparmor-namespace.conf > /dev/null && sudo sysctl --system
    sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0

----------
6 - Add user openvixbuilder

    sudo adduser openvixbuilder

----------
7 - Add your git user and email

    git config --global user.email "you@example.com"

    git config --global user.name "Your Name"

----------
8 - Switch to user openvixbuilder

    su openvixbuilder

----------
9 - Switch to home of openvixbuilder

    cd ~

----------
10 - Create folder openvix

    mkdir -p ~/openvix

----------
11 - Switch to folder openvix

    cd openvix

----------
12 - Clone oe-alliance git

    git clone https://github.com/oe-alliance/build-enviroment.git -b 6.0

----------
13 - Switch to folder build-enviroment

    cd build-enviroment

----------
14 - Update build-enviroment

    make update

----------
15 - Ubuntu 26.04 Users, building OE-A 5.6.

    Edit openembedded-core/meta/classes-global/base-bbclass
        - change line 130 ---->            srctool = bb.utils.which(path, tool, executable=True)
        - to 1line update ---->            srctool = (bb.utils.which(path, "gnu" + tool, executable=True) or bb.utils.which(path, tool, executable=True))
  
    Unzip OE5.6onUB26.04.zip attachment from post #968 in https://world-of-satellite.com/threads/build-my-own-vix-image.61295/page-49
	Copy unzipped files from recipes-local into your OE-A 5.6 meta-local/recipes-local

----------
16 - Initialise the first machine so site.conf gets created

    MACHINE=zgemmah9combo DISTRO=openvix DISTRO_TYPE=release make init

----------
17 - Update site.conf

    - BB_NUMBER_THREADS, PARALLEL_MAKE set to number of threads supported by the CPU
    - add/modify DL_DIR = " location for build sources " to point to a location where you can save 
      derived build sources, this will reduce build time in fetching these sources again.
    - Avoid wasting disk space creating spdx packages: INHERIT:remove = "create-spdx"

----------
18 - Building image with feeds  e.g.:-

    MACHINE=vuultimo4k DISTRO=openvix DISTRO_TYPE=release make image

----------
19 - Building an image without feeds (Build time 1-2h)

    MACHINE=zgemmah9combo DISTRO=openvix DISTRO_TYPE=release make enigma2-image

----------
20 - Building feeds only

    MACHINE=zgemmah9combo DISTRO=openvix DISTRO_TYPE=release make feeds
