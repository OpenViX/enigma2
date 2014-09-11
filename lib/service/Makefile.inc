noinst_LIBRARIES += service/libenigma_service.a

service_libenigma_service_a_CXXFLAGS = \
	$(LIBXINE_CFLAGS)

service_libenigma_service_a_SOURCES = \
	service/event.cpp \
	service/listboxservice.cpp \
	service/service.cpp \
	service/servicedvb.cpp \
	service/servicedvbrecord.cpp \
	service/servicefs.cpp \
	service/servicemp3.cpp \
	service/servicem2ts.cpp \
	service/servicedvbstream.cpp \
	service/servicehdmi.cpp

if ENABLE_LIBEPLAYER3 
service_libenigma_service_a_SOURCES += \
	service/serviceeplayer3.cpp
endif

serviceincludedir = $(pkgincludedir)/lib/service
serviceinclude_HEADERS = \
	service/event.h \
	service/iservice.h \
	service/listboxservice.h \
	service/service.h \
	service/servicedvb.h \
	service/servicedvbrecord.h \
	service/servicefs.h \
	service/servicemp3.h \
	service/servicem2ts.h \
	service/servicedvbstream.h \
	service/servicehdmi.h

if ENABLE_LIBEPLAYER3 
serviceinclude_HEADERS += \
	service/serviceeplayer3.h
endif

if HAVE_LIBXINE
service_libenigma_service_a_SOURCES += \
	service/servicexine.cpp
serviceinclude_HEADERS += \
	service/servicexine.h
endif

if HAVE_LIBDDVD
service_libenigma_service_a_SOURCES += \
	service/servicedvd.cpp
serviceinclude_HEADERS += \
	service/servicedvd.h
endif
