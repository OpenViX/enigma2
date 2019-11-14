installdir = $(pkglibdir)/python/Plugins/Extensions

SUBDIRS = TuxboxPlugins CutListEditor PicturePlayer MediaScanner SocketMMI DVDBurn MediaPlayer \
          SoftcamSetup
		  
if INIHDP
SUBDIRS += SoftcamSetup
endif

if U5PVR
SUBDIRS += SoftcamSetup
endif

if U53
SUBDIRS += SoftcamSetup
endif

if OSMIO4KPLUS
SUBDIRS += SoftcamSetup
endif

if MUTANTHD51
SUBDIRS += SoftcamSetup
endif				  

if HAVE_LIBDDVD
SUBDIRS += DVDPlayer
endif

install_PYTHON = __init__.py
