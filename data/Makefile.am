SUBDIRS = countries display fonts extensions keymaps skin_default skin_fallback_1080

dist_pkgdata_DATA = \
	encoding.conf \
	keymap.xml \
	keytranslation.xml \
	menu.xml \
	otv_00820000_fbff_16a8.dict \
	otv_011a0000_0002_07d4.dict \
	otv_06180000_1000_0011.dict \
	otv_06400000_00a9_0003.dict \
	radio.mvi \
	black.mvi \
	rcpositions.xml \
	setup.xml \
	skin_subtitles.xml \
	freesat.t1 \
	freesat.t2 \
	iso-639-3.pck \
	timezone.xml \
	unicable.xml \
	groupedservices

if GBIPBOX
SUBDIRS += gbipbox
else
dist_pkgdata_DATA += startwizard.xml
endif

iso-639-3.pck: $(srcdir)/iso-639-3.tab
	python $(srcdir)/convert-iso-639-3.py $< $@
