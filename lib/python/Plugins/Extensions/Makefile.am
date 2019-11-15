installdir = $(pkglibdir)/python/Plugins/Extensions

SUBDIRS = TuxboxPlugins CutListEditor PicturePlayer MediaScanner SocketMMI DVDBurn MediaPlayer

if HAVE_LIBDDVD
SUBDIRS += DVDPlayer
endif

if HAVE_BWLCD128
SUBDIRS += SoftcamSetup
endif

if HAVE_BWLCD255
SUBDIRS += SoftcamSetup
endif

if HAVE_7SEGMENT
SUBDIRS += SoftcamSetup
endif

if HAVE_TEXTLCD
SUBDIRS += SoftcamSetup
endif

install_PYTHON = __init__.py
