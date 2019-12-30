SUBDIRS = countries fonts extensions keymaps skin_default skin_fallback_1080

if HAVE_TEXTLCD
DISPLAYTYPE = text
TEXTSKIN = 7segment
else
DISPLAYTYPE = display
TEXTSKIN = default
endif

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
	skin_display.xml \
	freesat.t1 \
	freesat.t2 \
	iso-639-3.pck \
	timezone.xml \
	unicable.xml \
	groupedservices \
	otv_011a0000_0002_07d4.dict \
	otv_00820000_fbff_16a8.dict \
	otv_06180000_1000_0011.dict \
	otv_06400000_00a9_0003.dict

if GBIPBOX
SUBDIRS += gbipbox
else
dist_pkgdata_DATA += startwizard.xml
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

# Use box-specific XML if it exists, otherwise get the default
# TEXTSKIN is either "default" or "7segment"
# TODO: Missing dependency on optional "skin_$(DISPLAYTYPE)_$(MACHINEBUILD).xml"
skin_display.xml: $(srcdir)/skin_$(DISPLAYTYPE)_$(TEXTSKIN).xml
	cp $(srcdir)/skin_$(DISPLAYTYPE)_$(MACHINEBUILD).xml $@ 2>/dev/null || cp $(srcdir)/skin_$(DISPLAYTYPE)_$(TEXTSKIN).xml $@

iso-639-3.pck: $(srcdir)/iso-639-3.tab
	python $(srcdir)/convert-iso-639-3.py $< $@
