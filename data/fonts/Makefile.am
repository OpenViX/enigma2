installdir = $(datadir)/fonts

dist_install_DATA = \
	ae_AlMateen.ttf \
	andale.ttf \
	DroidSans-Bold.ttf \
	lcd.ttf \
	md_khmurabi_10.ttf \
	nmsbd.ttf \
	OpenSans-Italic.ttf \
	OpenSans-Regular.ttf \
	OpenSans-Semibold.ttf \
	OpenSans-SemiboldItalic.ttf \
	wqy-microhei.ttc

install-exec-hook:
	cd $(DESTDIR)$(datadir)/fonts && \
	$(LN_S) wqy-microhei.ttc fallback.font