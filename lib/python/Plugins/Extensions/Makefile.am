installdir = $(pkglibdir)/python/Plugins/Extensions

SUBDIRS = CutListEditor PicturePlayer MediaScanner MediaPlayer GraphMultiEPG SocketMMI FileCommander
# SUBDIRS += DVDBurn

if HAVE_LIBDDVD
SUBDIRS += DVDPlayer
endif

install_PYTHON = \
	__init__.py
