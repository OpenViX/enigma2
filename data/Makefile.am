SUBDIRS = countries fonts extensions keymaps skin_default skin_1080

dist_pkgdata_DATA = \
	encoding.conf \
	keymap.xml \
	keytranslation.xml \
	menu.xml \
	prev.png \
	radio.mvi \
	black.mvi \
	rcpositions.xml \
	setup.xml \
	skin_default.xml \
	skin_subtitles.xml \
	skin.xml \
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

if HAVE_TEXTLCD
dist_pkgdata_DATA += skin_text.xml
endif

if HAVE_COLORLCD220
SUBDIRS += lcd220 lcd_skin220
endif

if HAVE_COLORLCD400
SUBDIRS += lcd400 lcd_skin400
endif

if HAVE_BWLCD255
SUBDIRS += vfd255
endif

if HAVE_TEXTLCD
SUBDIRS += displaytext
endif

skin_display.xml: $(srcdir)/skin_display_default.xml
	test -f $(srcdir)/skin_display_$(MACHINEBUILD).xml && cp $(srcdir)/skin_display_$(MACHINEBUILD).xml skin_display.xml || cp $(srcdir)/skin_display_default.xml skin_display.xml

iso-639-3.pck: $(srcdir)/iso-639-3.tab
	python $(srcdir)/convert-iso-639-3.py $< $@
