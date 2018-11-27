installdir = $(datadir)/fonts

dist_install_DATA = *.ttf, *.ttc

install-exec-hook:
    cd $(DESTDIR)$(datadir)/fonts && \
    $(LN_S) wqy-microhei.ttc fallback.font