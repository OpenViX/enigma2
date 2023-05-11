SUBDIRS = fonts keymaps

dist_pkgdata_DATA = \
	encoding.conf \
	keymap.xml \
	menu.xml \
	black.mvi \
	rcpositions.xml \
	setup.xml \
	skin_subtitles.xml \
	startwizard.xml \
	userinterfacepositionerwizard.xml \
	videowizard.xml \
	freesat.t1 \
	freesat.t2 \
	unicable.xml \
	hd-testcard.mvi \
	iso-639-3.pck \
	distro-logo.png \
	groupedservices \
	otv_011a0000_0002_07d4.dict \
	otv_00820000_fbff_16a8.dict \
	otv_06180000_1000_0011.dict \
	otv_06400000_00a9_0003.dict

if HAVE_TEXTLCD
SUBDIRS += displaytext
endif

if HAVE_COLORLCD
SUBDIRS += display96
endif

if HAVE_COLORLCD128
SUBDIRS += display128
endif

if HAVE_COLORLCD220
SUBDIRS += display220
endif

if HAVE_COLORLCD400
SUBDIRS += display400
endif

if HAVE_COLORLCD480
SUBDIRS += display480
endif

if HAVE_COLORLCD720
SUBDIRS += display720
endif

if HAVE_COLORLCD800
SUBDIRS += display800
endif

if HAVE_BWLCD255
SUBDIRS += vfd255
endif

if HAVE_BWLCD140
SUBDIRS += vfd140
endif

if HAVE_BWLCD128
SUBDIRS += vfd128
endif

if HAVE_7SEGMENT
SUBDIRS += 7segment
endif

iso-639-3.pck: $(srcdir)/iso-639-3.tab
	python $(srcdir)/convert-iso-639-3.py $< $@
