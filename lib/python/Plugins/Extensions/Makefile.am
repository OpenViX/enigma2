installdir = $(pkglibdir)/python/Plugins/Extensions

SUBDIRS = TuxboxPlugins CutListEditor PicturePlayer MediaScanner MediaPlayer GraphMultiEPG SocketMMI FileCommander
# SUBDIRS += DVDBurn

if HAVE_LIBDDVD
SUBDIRS += DVDPlayer
endif

install_PYTHON = \
	__init__.py
