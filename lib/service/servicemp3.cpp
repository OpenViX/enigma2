	/* note: this requires gstreamer 0.10.x and a big list of plugins. */
	/* it's currently hardcoded to use a big-endian alsasink as sink. */
#include <lib/base/ebase.h>
#include <lib/base/eerror.h>
#include <lib/base/init_num.h>
#include <lib/base/init.h>
#include <lib/base/nconfig.h>
#include <lib/base/object.h>
#include <lib/dvb/epgcache.h>
#include <lib/dvb/decoder.h>
#include <lib/dvb/dvb.h>
#include <lib/dvb/db.h>
#include <lib/components/file_eraser.h>
#include <lib/gui/esubtitle.h>
#include <lib/service/servicemp3.h>
#include <lib/service/servicemp3record.h>
#include <lib/service/service.h>
#include <lib/gdi/gpixmap.h>
#include <lib/dvb/subtitle.h>

#include <string>
#include <lib/base/estring.h>

#include <gst/gst.h>
#include <gst/pbutils/missing-plugins.h>
#include <sys/stat.h>

#define HTTP_TIMEOUT 30

#define DVB_SUB_SEGMENT_PAGE_COMPOSITION 0x10
#define DVB_SUB_SEGMENT_REGION_COMPOSITION 0x11
#define DVB_SUB_SEGMENT_CLUT_DEFINITION 0x12
#define DVB_SUB_SEGMENT_OBJECT_DATA 0x13
#define DVB_SUB_SEGMENT_DISPLAY_DEFINITION 0x14
#define DVB_SUB_SEGMENT_END_OF_DISPLAY_SET 0x80
#define DVB_SUB_SEGMENT_STUFFING 0xFF

#define DVB_SUB_SYNC_BYTE 0x0f

/*
 * UNUSED variable from service reference is now used as buffer flag for gstreamer
 * REFTYPE:FLAGS:STYPE:SID:TSID:ONID:NS:PARENT_SID:PARENT_TSID:UNUSED
 *   D  D X X X X X X X X
 * 4097:0:1:0:0:0:0:0:0:0:URL:NAME (no buffering)
 * 4097:0:1:0:0:0:0:0:0:1:URL:NAME (buffering enabled)
 * 4097:0:1:0:0:0:0:0:0:3:URL:NAME (progressive download and buffering enabled)
 *
 * Progressive download requires buffering enabled, so it's mandatory to use flag 3 not 2
 */
typedef enum
{
	BUFFERING_ENABLED	= 0x00000001,
	PROGRESSIVE_DOWNLOAD	= 0x00000002
} eServiceMP3Flags;

/*
 * GstPlayFlags flags from playbin2. It is the policy of GStreamer to
 * not publicly expose element-specific enums. That's why this
 * GstPlayFlags enum has been copied here.
 */
typedef enum
{
	GST_PLAY_FLAG_VIDEO         = (1 << 0),
	GST_PLAY_FLAG_AUDIO         = (1 << 1),
	GST_PLAY_FLAG_TEXT          = (1 << 2),
	GST_PLAY_FLAG_VIS           = (1 << 3),
	GST_PLAY_FLAG_SOFT_VOLUME   = (1 << 4),
	GST_PLAY_FLAG_NATIVE_AUDIO  = (1 << 5),
	GST_PLAY_FLAG_NATIVE_VIDEO  = (1 << 6),
	GST_PLAY_FLAG_DOWNLOAD      = (1 << 7),
	GST_PLAY_FLAG_BUFFERING     = (1 << 8),
	GST_PLAY_FLAG_DEINTERLACE   = (1 << 9),
	GST_PLAY_FLAG_SOFT_COLORBALANCE = (1 << 10),
	GST_PLAY_FLAG_FORCE_FILTERS = (1 << 11),
} GstPlayFlags;

// eServiceFactoryMP3

/*
 * gstreamer suffers from a bug causing sparse streams to loose sync, after pause/resume / skip
 * see: https://bugzilla.gnome.org/show_bug.cgi?id=619434
 * As a workaround, we run the subsink in sync=false mode
 */
#undef GSTREAMER_SUBTITLE_SYNC_MODE_BUG
/**/

void bitstream_gs_init(bitstream *bit, const void *buffer, int size)
{
	bit->data = (uint8_t*) buffer;
	bit->size = size;
	bit->avail = 8;
	bit->consumed = 0;
}

int bitstream_gs_get(bitstream *bit)
{
	int val;
	bit->avail -= bit->size;
	val = ((*bit->data) >> bit->avail) & ((1<<bit->size) - 1);
	if (!bit->avail)
	{
		bit->data++;
		bit->consumed++;
		bit->avail = 8;
	}
	return val;
}

eServiceFactoryMP3::eServiceFactoryMP3()
{
	ePtr<eServiceCenter> sc;

	eServiceCenter::getPrivInstance(sc);
	if (sc)
	{
		std::list<std::string> extensions;
		extensions.push_back("dts");
		extensions.push_back("mp3");
		extensions.push_back("wav");
		extensions.push_back("wave");
		extensions.push_back("oga");
		extensions.push_back("ogg");
		extensions.push_back("flac");
		extensions.push_back("m4a");
		extensions.push_back("mp2");
		extensions.push_back("m2a");
		extensions.push_back("wma");
		extensions.push_back("ac3");
		extensions.push_back("mka");
		extensions.push_back("aac");
		extensions.push_back("ape");
		extensions.push_back("alac");
		extensions.push_back("mpg");
		extensions.push_back("vob");
		extensions.push_back("m4v");
		extensions.push_back("mkv");
		extensions.push_back("avi");
		extensions.push_back("divx");
		extensions.push_back("dat");
		extensions.push_back("flv");
		extensions.push_back("mp4");
		extensions.push_back("mov");
		extensions.push_back("wmv");
		extensions.push_back("asf");
		extensions.push_back("3gp");
		extensions.push_back("3g2");
		extensions.push_back("mpeg");
		extensions.push_back("mpe");
		extensions.push_back("rm");
		extensions.push_back("rmvb");
		extensions.push_back("ogm");
		extensions.push_back("ogv");
		extensions.push_back("m3u8");
		extensions.push_back("stream");
		extensions.push_back("webm");
		extensions.push_back("amr");
		extensions.push_back("au");
		extensions.push_back("mid");
		extensions.push_back("wv");
		extensions.push_back("pva");
		extensions.push_back("wtv");
		sc->addServiceFactory(eServiceFactoryMP3::id, this, extensions);
	}

	m_service_info = new eStaticServiceMP3Info();
}

eServiceFactoryMP3::~eServiceFactoryMP3()
{
	ePtr<eServiceCenter> sc;

	eServiceCenter::getPrivInstance(sc);
	if (sc)
		sc->removeServiceFactory(eServiceFactoryMP3::id);
}

DEFINE_REF(eServiceFactoryMP3)

	// iServiceHandler
RESULT eServiceFactoryMP3::play(const eServiceReference &ref, ePtr<iPlayableService> &ptr)
{
		// check resources...
	ptr = new eServiceMP3(ref);
	return 0;
}

RESULT eServiceFactoryMP3::record(const eServiceReference &ref, ePtr<iRecordableService> &ptr)
{
	if (ref.path.find("://") != std::string::npos)
	{
		ptr = new eServiceMP3Record((eServiceReference&)ref);
		return 0;
	}
	ptr=0;
	return -1;
}

RESULT eServiceFactoryMP3::list(const eServiceReference &, ePtr<iListableService> &ptr)
{
	ptr=0;
	return -1;
}

RESULT eServiceFactoryMP3::info(const eServiceReference &ref, ePtr<iStaticServiceInformation> &ptr)
{
	ptr = m_service_info;
	return 0;
}

class eMP3ServiceOfflineOperations: public iServiceOfflineOperations
{
	DECLARE_REF(eMP3ServiceOfflineOperations);
	eServiceReference m_ref;
public:
	eMP3ServiceOfflineOperations(const eServiceReference &ref);

	RESULT deleteFromDisk(int simulate);
	RESULT getListOfFilenames(std::list<std::string> &);
	RESULT reindex();
};

DEFINE_REF(eMP3ServiceOfflineOperations);

eMP3ServiceOfflineOperations::eMP3ServiceOfflineOperations(const eServiceReference &ref): m_ref((const eServiceReference&)ref)
{
}

RESULT eMP3ServiceOfflineOperations::deleteFromDisk(int simulate)
{
	if (!simulate)
	{
		std::list<std::string> res;
		if (getListOfFilenames(res))
			return -1;

		eBackgroundFileEraser *eraser = eBackgroundFileEraser::getInstance();
		if (!eraser)
			eDebug("[eMP3ServiceOfflineOperations] FATAL !! can't get background file eraser");

		for (std::list<std::string>::iterator i(res.begin()); i != res.end(); ++i)
		{
			eDebug("[eMP3ServiceOfflineOperations] Removing %s...", i->c_str());
			if (eraser)
				eraser->erase(i->c_str());
			else
				::unlink(i->c_str());
		}
	}
	return 0;
}

RESULT eMP3ServiceOfflineOperations::getListOfFilenames(std::list<std::string> &res)
{
	res.clear();
	res.push_back(m_ref.path);
	return 0;
}

RESULT eMP3ServiceOfflineOperations::reindex()
{
	return -1;
}


RESULT eServiceFactoryMP3::offlineOperations(const eServiceReference &ref, ePtr<iServiceOfflineOperations> &ptr)
{
	ptr = new eMP3ServiceOfflineOperations(ref);
	return 0;
}

// eStaticServiceMP3Info


// eStaticServiceMP3Info is seperated from eServiceMP3 to give information
// about unopened files.

// probably eServiceMP3 should use this class as well, and eStaticServiceMP3Info
// should have a database backend where ID3-files etc. are cached.
// this would allow listing the mp3 database based on certain filters.

DEFINE_REF(eStaticServiceMP3Info)

eStaticServiceMP3Info::eStaticServiceMP3Info()
{
}

RESULT eStaticServiceMP3Info::getName(const eServiceReference &ref, std::string &name)
{
	if (ref.name.length())
		name = ref.name;
	else
	{
		size_t last = ref.path.rfind('/');
		if (last != std::string::npos)
			name = ref.path.substr(last+1);
		else
			name = ref.path;
	}

	std::string res_name = "";
	std::string res_provider = "";
	eServiceReference::parseNameAndProviderFromName(name, res_name, res_provider);
	name = res_name;

	return 0;
}

int eStaticServiceMP3Info::getLength(const eServiceReference &ref)
{
	return -1;
}

int eStaticServiceMP3Info::getInfo(const eServiceReference &ref, int w)
{
	switch (w)
	{
	case iServiceInformation::sTimeCreate:
		{
			struct stat s = {};
			if (stat(ref.path.c_str(), &s) == 0)
			{
				return s.st_mtime;
			}
		}
		break;
	case iServiceInformation::sFileSize:
		{
			struct stat s = {};
			if (stat(ref.path.c_str(), &s) == 0)
			{
				return s.st_size;
			}
		}
		break;
	}
	return iServiceInformation::resNA;
}

long long eStaticServiceMP3Info::getFileSize(const eServiceReference &ref)
{
	struct stat s = {};
	if (stat(ref.path.c_str(), &s) == 0)
	{
		return s.st_size;
	}
	return 0;
}

RESULT eStaticServiceMP3Info::getEvent(const eServiceReference &ref, ePtr<eServiceEvent> &evt, time_t start_time)
{
	if (ref.path.find("://") != std::string::npos)
	{
		eServiceReference equivalentref(ref);
		equivalentref.type = eServiceFactoryMP3::id;
		equivalentref.path.clear();
		return eEPGCache::getInstance()->lookupEventTime(equivalentref, start_time, evt);
	}
	else // try to read .eit file
	{
		size_t pos;
		ePtr<eServiceEvent> event = new eServiceEvent;
		std::string filename = ref.path;
		if ( (pos = filename.rfind('.')) != std::string::npos)
		{
			filename.erase(pos + 1);
			filename += "eit";
			if (!event->parseFrom(filename, 0))
			{
				evt = event;
				return 0;
			}
		}
	}
	evt = 0;
	return -1;
}

DEFINE_REF(eStreamBufferInfo)

eStreamBufferInfo::eStreamBufferInfo(int percentage, int inputrate, int outputrate, int space, int size)
: bufferPercentage(percentage),
	inputRate(inputrate),
	outputRate(outputrate),
	bufferSpace(space),
	bufferSize(size)
{
}

int eStreamBufferInfo::getBufferPercentage() const
{
	return bufferPercentage;
}

int eStreamBufferInfo::getAverageInputRate() const
{
	return inputRate;
}

int eStreamBufferInfo::getAverageOutputRate() const
{
	return outputRate;
}

int eStreamBufferInfo::getBufferSpace() const
{
	return bufferSpace;
}

int eStreamBufferInfo::getBufferSize() const
{
	return bufferSize;
}

DEFINE_REF(eServiceMP3InfoContainer);

eServiceMP3InfoContainer::eServiceMP3InfoContainer()
: doubleValue(0.0), bufferValue(NULL), bufferData(NULL), bufferSize(0)
{
}

eServiceMP3InfoContainer::~eServiceMP3InfoContainer()
{
	if (bufferValue)
	{
		gst_buffer_unmap(bufferValue, &map);
		gst_buffer_unref(bufferValue);
		bufferValue = NULL;
		bufferData = NULL;
		bufferSize = 0;
	}
}

double eServiceMP3InfoContainer::getDouble(unsigned int index) const
{
	return doubleValue;
}

unsigned char *eServiceMP3InfoContainer::getBuffer(unsigned int &size) const
{
	size = bufferSize;
	return bufferData;
}

void eServiceMP3InfoContainer::setDouble(double value)
{
	doubleValue = value;
}

void eServiceMP3InfoContainer::setBuffer(GstBuffer *buffer)
{
	bufferValue = buffer;
	gst_buffer_ref(bufferValue);
	gst_buffer_map(bufferValue, &map, GST_MAP_READ);
	bufferData = map.data;
	bufferSize = map.size;
}

// eServiceMP3
int eServiceMP3::ac3_delay = 0,
    eServiceMP3::pcm_delay = 0;

eServiceMP3::eServiceMP3(eServiceReference ref):
	m_nownext_timer(eTimer::create(eApp)),
	m_cuesheet_changed(0),
	m_cutlist_enabled(1),
	m_ref(ref),
	m_pages(0),
	m_display_size(720,576),
	m_pump(eApp, 1, "Servicemp3")
{
	m_subtitle_sync_timer = eTimer::create(eApp);
	m_stream_tags = 0;
	m_currentAudioStream = -1;
	m_currentSubtitleStream = -1;
	m_cachedSubtitleStream = -2; /* report subtitle stream to be 'cached'. TODO: use an actual cache. */
	m_autoturnon = eConfigManager::getConfigBoolValue("config.subtitles.pango_autoturnon", true);
	m_subtitle_widget = 0;
	m_currentTrickRatio = 1.0;
	m_buffer_size = 5 * 1024 * 1024;
	m_ignore_buffering_messages = 0;
	m_is_live = false;
	m_use_prefillbuffer = false;
	m_paused = false;
	m_seek_paused = false;
	m_cuesheet_loaded = false; /* cuesheet CVR */
	m_use_chapter_entries = false; /* TOC chapter support CVR */
	m_last_seek_pos = 0; /* CVR last seek position */
	m_useragent = "HbbTV/1.1.1 (+PVR+RTSP+DL; Sonic; TV44; 1.32.455; 2.002) Bee/3.5";
	m_extra_headers = "";
	m_download_buffer_path = "";
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	m_errorInfo.missing_codec = "";
	audioSink = videoSink = NULL;
	m_decoder = NULL;

	std::string sref = ref.toString();
	eDebug("[eServiceMP3] Init start %s", ref.toString().c_str());
	if (!sref.empty())
	{
		eDebug("[eServiceMP3] Init start !sref.empty()");	
		std::vector<eIPTVDBItem> &iptv_services = eDVBDB::getInstance()->iptv_services;
		for(std::vector<eIPTVDBItem>::iterator it = iptv_services.begin(); it != iptv_services.end(); ++it)
		{
			if (sref.find(it->s_ref) != std::string::npos)
			{
				m_currentAudioStream = it->ampeg_pid;
				m_currentSubtitleStream = it->subtitle_pid;
				m_cachedSubtitleStream = m_currentSubtitleStream;
				eDebug("[eServiceMP3] Init start iptv_service use sref pid's A: %d; S: %d", m_currentAudioStream, it->subtitle_pid);				
			}
		}
	}

	CONNECT(m_subtitle_sync_timer->timeout, eServiceMP3::pushSubtitles);
	CONNECT(m_pump.recv_msg, eServiceMP3::gstPoll);
	CONNECT(m_nownext_timer->timeout, eServiceMP3::updateEpgCacheNowNext);
	m_aspect = m_width = m_height = m_framerate = m_progressive = m_gamma = -1;

	m_state = stIdle;
	m_coverart = false;
	eDebug("[eServiceMP3] construct!");

	const char *filename;
	std::string filename_str;
	size_t pos = m_ref.path.find('#');
	if (pos != std::string::npos && (m_ref.path.compare(0, 4, "http") == 0 || m_ref.path.compare(0, 4, "rtsp") == 0))
	{
		filename_str = m_ref.path.substr(0, pos);
		filename = filename_str.c_str();
		m_extra_headers = m_ref.path.substr(pos + 1);

		pos = m_extra_headers.find("User-Agent=");
		if (pos != std::string::npos)
		{
			size_t hpos_start = pos + 11;
			size_t hpos_end = m_extra_headers.find('&', hpos_start);
			if (hpos_end != std::string::npos)
				m_useragent = m_extra_headers.substr(hpos_start, hpos_end - hpos_start);
			else
				m_useragent = m_extra_headers.substr(hpos_start);
		}
	}
	else
		filename = m_ref.path.c_str();
	const char *ext = strrchr(filename, '.');
	if (!ext)
		ext = filename + strlen(filename);

	m_sourceinfo.is_video = FALSE;
	m_sourceinfo.audiotype = atUnknown;
	if (strcasecmp(ext, ".mpeg") == 0 || strcasecmp(ext, ".mpe") == 0 || strcasecmp(ext, ".mpg") == 0 || strcasecmp(ext, ".vob") == 0 || strcasecmp(ext, ".bin") == 0)
	{
		m_sourceinfo.containertype = ctMPEGPS;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".ts") == 0)
	{
		m_sourceinfo.containertype = ctMPEGTS;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".mkv") == 0)
	{
		m_sourceinfo.containertype = ctMKV;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".ogm") == 0 || strcasecmp(ext, ".ogv") == 0)
	{
		m_sourceinfo.containertype = ctOGG;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".avi") == 0 || strcasecmp(ext, ".divx") == 0)
	{
		m_sourceinfo.containertype = ctAVI;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".mp4") == 0 || strcasecmp(ext, ".mov") == 0 || strcasecmp(ext, ".m4v") == 0 || strcasecmp(ext, ".3gp") == 0 || strcasecmp(ext, ".3g2") == 0)
	{
		m_sourceinfo.containertype = ctMP4;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".asf") == 0 || strcasecmp(ext, ".wmv") == 0)
	{
		m_sourceinfo.containertype = ctASF;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".webm") == 0)
	{
		m_sourceinfo.containertype = ctWEBM;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".m4a") == 0 || strcasecmp(ext, ".alac") == 0)
	{
		m_sourceinfo.containertype = ctMP4;
		m_sourceinfo.audiotype = atAAC;
	}
	else if ( strcasecmp(ext, ".dra") == 0 )
	{
		m_sourceinfo.containertype = ctDRA;
		m_sourceinfo.audiotype = atDRA;
	}
	else if (strcasecmp(ext, ".m3u8") == 0)
		m_sourceinfo.is_hls = TRUE;
	else if (strcasecmp(ext, ".mp3") == 0)
		m_sourceinfo.audiotype = atMP3;
	else if (strcasecmp(ext, ".wma") == 0)
		m_sourceinfo.audiotype = atWMA;
	else if (strcasecmp(ext, ".wav") == 0 || strcasecmp(ext, ".wave") == 0 || strcasecmp(ext, ".wv") == 0)
		m_sourceinfo.audiotype = atPCM;
	else if (strcasecmp(ext, ".dts") == 0)
		m_sourceinfo.audiotype = atDTS;
	else if (strcasecmp(ext, ".flac") == 0)
		m_sourceinfo.audiotype = atFLAC;
	else if (strcasecmp(ext, ".ac3") == 0)
		m_sourceinfo.audiotype = atAC3;
	else if (strcasecmp(ext, ".cda") == 0)
		m_sourceinfo.containertype = ctCDA;
	if (strcasecmp(ext, ".dat") == 0)
	{
		m_sourceinfo.containertype = ctVCD;
		m_sourceinfo.is_video = TRUE;
	}
	if (strstr(filename, "://"))
		m_sourceinfo.is_streaming = TRUE;

	gchar *uri;
	gchar *suburi = NULL;

	pos = m_ref.path.find("&suburi=");
	if (pos != std::string::npos)
	{
		filename_str = filename;

		std::string suburi_str = filename_str.substr(pos + 8);
		filename = suburi_str.c_str();
		suburi = g_strdup_printf ("%s", filename);

		filename_str = filename_str.substr(0, pos);
		filename = filename_str.c_str();
	}

	if ( m_sourceinfo.is_streaming )
	{
		if (eConfigManager::getConfigBoolValue("config.mediaplayer.useAlternateUserAgent"))
			m_useragent = eConfigManager::getConfigValue("config.mediaplayer.alternateUserAgent");

		uri = g_strdup_printf ("%s", filename);

		if ( m_ref.getData(7) & BUFFERING_ENABLED )
		{
			m_use_prefillbuffer = true;
			if ( m_ref.getData(7) & PROGRESSIVE_DOWNLOAD )
			{
				/* progressive download buffering */
				if (::access("/hdd/movie", X_OK) >= 0)
				{
					/* It looks like /hdd points to a valid mount, so we can store a download buffer on it */
					m_download_buffer_path = "/hdd/gstreamer_XXXXXXXXXX";
				}
			}
		}
	}
	else if ( m_sourceinfo.containertype == ctCDA )
	{
		int i_track = atoi(filename+17);
		uri = g_strdup_printf ("cdda://%i", i_track);
	}
	else if ( m_sourceinfo.containertype == ctVCD )
	{
		int tmp_fd = -1;
		tmp_fd = ::open("/dev/null", O_RDONLY | O_CLOEXEC);
		/* eDebug("[servicemp3] Twol00 Opened tmp_fd: %d", tmp_fd); */
		if (tmp_fd == 0)
		{
			::close(tmp_fd);
			tmp_fd = -1;
			fd0lock = ::open("/dev/null", O_RDONLY | O_CLOEXEC);
			/* eDebug("[servicemp3] opening null fd returned: %d", fd0lock); */
		}
		if (tmp_fd != -1)
		{
			::close(tmp_fd);
		}
		int ret = -1;
		int fd = open(filename,O_RDONLY);
		if (fd >= 0)
		{
			char* tmp = new char[128*1024];
			ret = read(fd, tmp, 128*1024);
			close(fd);
			delete [] tmp;
		}
		if ( ret == -1 ) // this is a "REAL" VCD
			uri = g_strdup_printf ("vcd://");
		else
			uri = g_filename_to_uri(filename, NULL, NULL);
	}
	else
		uri = g_filename_to_uri(filename, NULL, NULL);

	eDebug("[eServiceMP3] playbin uri=%s", uri);
	if (suburi != NULL)
		eDebug("[eServiceMP3] playbin suburi=%s", suburi);
	bool useplaybin3 = eConfigManager::getConfigBoolValue("config.misc.usegstplaybin3", false);
	if(useplaybin3)
		m_gst_playbin = gst_element_factory_make("playbin3", "playbin");
	else
		m_gst_playbin = gst_element_factory_make("playbin", "playbin");
	if ( m_gst_playbin )
	{
		/*
		 * avoid video conversion, let the dvbmediasink handle that using native video flag
		 * volume control is done by hardware, do not use soft volume flag
		 */
		guint flags = GST_PLAY_FLAG_AUDIO | GST_PLAY_FLAG_VIDEO | \
				GST_PLAY_FLAG_TEXT | GST_PLAY_FLAG_NATIVE_VIDEO;

		if ( m_sourceinfo.is_streaming )
		{
			g_signal_connect (G_OBJECT (m_gst_playbin), "notify::source", G_CALLBACK (playbinNotifySource), this);
			if (m_download_buffer_path != "")
			{
				/* use progressive download buffering */
				flags |= GST_PLAY_FLAG_DOWNLOAD;
				g_signal_connect(G_OBJECT(m_gst_playbin), "element-added", G_CALLBACK(handleElementAdded), this);
				/* limit file size */
				g_object_set(m_gst_playbin, "ring-buffer-max-size", (guint64)(8LL * 1024LL * 1024LL), NULL);
			}
			/*
			 * regardless whether or not we configured a progressive download file, use a buffer as well
			 * (progressive download might not work for all formats)
			 */
			flags |= GST_PLAY_FLAG_BUFFERING;
			/* increase the default 2 second / 2 MB buffer limitations to 5s / 5MB */
			g_object_set(G_OBJECT(m_gst_playbin), "buffer-duration", 5LL * GST_SECOND, NULL);
			g_object_set(G_OBJECT(m_gst_playbin), "buffer-size", m_buffer_size, NULL);
			if (m_sourceinfo.is_hls)
				g_object_set(G_OBJECT(m_gst_playbin), "connection-speed", (guint64)(4495000LL), NULL);
		}
		g_object_set (G_OBJECT (m_gst_playbin), "flags", flags, NULL);
		g_object_set (G_OBJECT (m_gst_playbin), "uri", uri, NULL);
		GstElement *subsink = gst_element_factory_make("subsink", "subtitle_sink");
		if (!subsink)
			eDebug("[eServiceMP3] sorry, can't play: missing gst-plugin-subsink");
		else
		{
			m_subs_to_pull_handler_id = g_signal_connect (subsink, "new-buffer", G_CALLBACK (gstCBsubtitleAvail), this);
			g_object_set (G_OBJECT (subsink), "caps", gst_caps_from_string("text/plain; text/x-plain; text/x-raw; text/x-pango-markup; subpicture/x-dvd; subpicture/x-dvb; subpicture/x-pgs"), NULL);
			g_object_set (G_OBJECT (m_gst_playbin), "text-sink", subsink, NULL);
			g_object_set (G_OBJECT (m_gst_playbin), "current-text", m_currentSubtitleStream, NULL);
		}
		GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE (m_gst_playbin));
		gst_bus_set_sync_handler(bus, gstBusSyncHandler, this, NULL);
		gst_object_unref(bus);

		if (suburi != NULL)
			g_object_set (G_OBJECT (m_gst_playbin), "suburi", suburi, NULL);
		else
		{
			char srt_filename[ext - filename + 5];
			strncpy(srt_filename,filename, ext - filename);
			srt_filename[ext - filename] = '\0';
			strcat(srt_filename, ".srt");
			if (::access(srt_filename, R_OK) >= 0)
			{
				gchar *luri = g_filename_to_uri(srt_filename, NULL, NULL);
				eDebug("[eServiceMP3] subtitle uri: %s", luri);
				g_object_set (m_gst_playbin, "suburi", luri, NULL);
				g_free(luri);
			}
		}
	} else
	{
		m_event((iPlayableService*)this, evUser+12);
		m_gst_playbin = 0;
		m_errorInfo.error_message = "failed to create GStreamer pipeline!\n";

		eDebug("[eServiceMP3] sorry, can't play: %s",m_errorInfo.error_message.c_str());
	}
	g_free(uri);
	if (suburi != NULL)
		g_free(suburi);
}

eServiceMP3::~eServiceMP3()
{
	// disconnect subtitle callback
	GstElement *subsink = gst_bin_get_by_name(GST_BIN(m_gst_playbin), "subtitle_sink");

	if (subsink)
	{
		g_signal_handler_disconnect (subsink, m_subs_to_pull_handler_id);
		gst_object_unref(subsink);
	}

	if (m_subtitle_widget) m_subtitle_widget->destroy();
	m_subtitle_widget = 0;

	if (m_gst_playbin)
	{
		// disconnect sync handler callback
		GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE (m_gst_playbin));
		gst_bus_set_sync_handler(bus, NULL, NULL, NULL);
		gst_object_unref(bus);
	}

	stop();

	if (m_decoder)
	{
		m_decoder = NULL;
	}

	if (m_stream_tags)
		gst_tag_list_free(m_stream_tags);

	if (audioSink)
	{
		gst_object_unref(GST_OBJECT(audioSink));
		audioSink = NULL;
	}
	if (videoSink)
	{
		gst_object_unref(GST_OBJECT(videoSink));
		videoSink = NULL;
	}
	if (m_gst_playbin)
	{
		gst_object_unref (GST_OBJECT (m_gst_playbin));
		eDebug("[eServiceMP3] destruct!");
	}
}

void eServiceMP3::updateEpgCacheNowNext()
{
	bool update = false;
	ePtr<eServiceEvent> next = 0;
	ePtr<eServiceEvent> ptr = 0;
	eServiceReference ref(m_ref);
	ref.type = eServiceFactoryMP3::id;
	ref.path.clear();
	if (eEPGCache::getInstance() && eEPGCache::getInstance()->lookupEventTime(ref, -1, ptr) >= 0)
	{
		ePtr<eServiceEvent> current = m_event_now;
		if (!current || !ptr || current->getEventId() != ptr->getEventId())
		{
			update = true;
			m_event_now = ptr;
			time_t next_time = ptr->getBeginTime() + ptr->getDuration();
			if (eEPGCache::getInstance()->lookupEventTime(ref, next_time, ptr) >= 0)
			{
				next = ptr;
				m_event_next = ptr;
			}
		}
	}

	int refreshtime = 60;
	if (!next)
	{
		next = m_event_next;
	}
	if (next)
	{
		time_t now = eDVBLocalTimeHandler::getInstance()->nowTime();
		refreshtime = (int)(next->getBeginTime() - now) + 3;
		if (refreshtime <= 0 || refreshtime > 60)
		{
			refreshtime = 60;
		}
	}
	m_nownext_timer->startLongTimer(refreshtime);
	if (update)
	{
		m_event((iPlayableService*)this, evUpdatedEventInfo);
	}
}

DEFINE_REF(eServiceMP3);

DEFINE_REF(GstMessageContainer);

void eServiceMP3::setCacheEntry(bool isAudio, int pid)
{
	bool hasFoundItem = false;
	std::vector<eIPTVDBItem> &iptv_services = eDVBDB::getInstance()->iptv_services;
	for(std::vector<eIPTVDBItem>::iterator it = iptv_services.begin(); it != iptv_services.end(); ++it) {
		if (m_ref.toString().find(it->s_ref) != std::string::npos) {
			hasFoundItem = true;
			if (isAudio) {
				it->ampeg_pid = pid;
			}
			else
			{
				it->subtitle_pid = pid;
			}
			break;
		}
	}
	if (!hasFoundItem) {
		eIPTVDBItem item(m_ref.toReferenceString(), isAudio ? pid : -1, -1, -1, -1, -1, -1, -1, isAudio ? -1 : pid, -1);
		iptv_services.push_back(item);
	}
}

RESULT eServiceMP3::connectEvent(const sigc::slot<void(iPlayableService*,int)> &event, ePtr<eConnection> &connection)
{
	connection = new eConnection((iPlayableService*)this, m_event.connect(event));
	return 0;
}

RESULT eServiceMP3::start()
{
	ASSERT(m_state == stIdle);

	if (m_gst_playbin)
	{
		eDebug("[eServiceMP3] starting pipeline");
		GstStateChangeReturn ret;
		ret = gst_element_set_state (m_gst_playbin, GST_STATE_PLAYING);

		switch(ret)
		{
		case GST_STATE_CHANGE_FAILURE:
			eDebug("[eServiceMP3] failed to start pipeline");
			stop();
			return -1;
			break;
		case GST_STATE_CHANGE_SUCCESS:
			m_is_live = false;
			break;
		case GST_STATE_CHANGE_NO_PREROLL:
			m_is_live = true;
			break;
		default:
			break;
		}
	}

	if (m_ref.path.find("://") == std::string::npos)
	{
		/* read event from .eit file */
		size_t pos;
		ePtr<eServiceEvent> event = new eServiceEvent;
		std::string filename = m_ref.path;
		if ( (pos = filename.rfind('.')) != std::string::npos)
		{
			filename.erase(pos + 1);
			filename += "eit";
			if (!event->parseFrom(filename, 0))
			{
				ePtr<eServiceEvent> empty;
				m_event_now = event;
				m_event_next = empty;
			}
		}
	}

	return 0;
}

RESULT eServiceMP3::stop()
{
	if (!m_gst_playbin || m_state == stStopped)
		return -1;

	eDebug("[eServiceMP3] stop %s", m_ref.path.c_str());
	m_state = stStopped;

	GstStateChangeReturn ret;
	GstState state, pending;
	/* make sure that last state change was successfull */
	ret = gst_element_get_state(m_gst_playbin, &state, &pending, 5 * GST_SECOND);
	eDebug("[eServiceMP3] stop state:%s pending:%s ret:%s",
		gst_element_state_get_name(state),
		gst_element_state_get_name(pending),
		gst_element_state_change_return_get_name(ret));

	ret = gst_element_set_state(m_gst_playbin, GST_STATE_NULL);
	if (ret != GST_STATE_CHANGE_SUCCESS)
		eDebug("[eServiceMP3] stop GST_STATE_NULL failure");

	saveCuesheet();
	m_nownext_timer->stop();

	return 0;
}

RESULT eServiceMP3::pause(ePtr<iPauseableService> &ptr)
{
	ptr=this;
	return 0;
}

RESULT eServiceMP3::setSlowMotion(int ratio)
{
	if (!ratio)
		return 0;
	eDebug("[eServiceMP3] setSlowMotion ratio=%f",1.0/(gdouble)ratio);
	return trickSeek(1.0/(gdouble)ratio);
}

RESULT eServiceMP3::setFastForward(int ratio)
{
	eDebug("[eServiceMP3] setFastForward ratio=%i",ratio);
	return trickSeek(ratio);
}

		// iPausableService
RESULT eServiceMP3::pause()
{
	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	eDebug("[eServiceMP3] pause");
	trickSeek(0.0);

	return 0;
}

RESULT eServiceMP3::unpause()
{
	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	/* no need to unpase if we are not paused already */
	if (m_currentTrickRatio == 1.0 && !m_paused)
	{
		eDebug("[eServiceMP3] trickSeek no need to unpause!");
		return 0;
	}

	eDebug("[eServiceMP3] unpause");
	trickSeek(1.0);

	return 0;
}

	/* iSeekableService */
RESULT eServiceMP3::seek(ePtr<iSeekableService> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::getLength(pts_t &pts)
{
	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	GstFormat fmt = GST_FORMAT_TIME;
	gint64 len;
	if (!gst_element_query_duration(m_gst_playbin, fmt, &len))
		return -1;
		/* len is in nanoseconds. we have 90 000 pts per second. */

	pts = len / 11111LL;
	return 0;
}

RESULT eServiceMP3::seekToImpl(pts_t to)
{
		/* convert pts to nanoseconds */
	m_last_seek_pos = to * 11111LL;
	if (!gst_element_seek (m_gst_playbin, m_currentTrickRatio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT),
		GST_SEEK_TYPE_SET, m_last_seek_pos,
		GST_SEEK_TYPE_NONE, GST_CLOCK_TIME_NONE))
	{
		eDebug("[eServiceMP3] seekTo failed");
		return -1;
	}

	if (m_paused)
	{
		m_event((iPlayableService*)this, evUpdatedInfo);
	}

	return 0;
}

RESULT eServiceMP3::seekTo(pts_t to)
{
	RESULT ret = -1;

	if (m_gst_playbin)
	{
		m_prev_decoder_time = -1;
		m_decoder_time_valid_state = 0;
		ret = seekToImpl(to);
	}

	return ret;
}


RESULT eServiceMP3::trickSeek(gdouble ratio)
{
	if (!m_gst_playbin)
		return -1;
	GstState state, pending;
	if (ratio > -0.01 && ratio < 0.01)
	{
		gst_element_set_state(m_gst_playbin, GST_STATE_PAUSED);
		/* pipeline sometimes block due to audio track issue off gstreamer.
		If the pipeline is blocked up on pending state change to paused ,
        this issue is solved be just reslecting the current audio track.*/
		gst_element_get_state(m_gst_playbin, &state, &pending, 1 * GST_SECOND);
		if (state == GST_STATE_PLAYING && pending == GST_STATE_PAUSED)
		{
			if (m_currentAudioStream >= 0)
				selectTrack(m_currentAudioStream);
			else
				selectTrack(0);
		}
		return 0;
	}

	bool unpause = (m_currentTrickRatio == 1.0 && ratio == 1.0);
	if (unpause)
	{
		GstElement *source = NULL;
		GstElementFactory *factory = NULL;
		const gchar *name = NULL;
		g_object_get (G_OBJECT (m_gst_playbin), "source", &source, NULL);
		if (!source)
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - cannot get source");
			goto seek_unpause;
		}
		factory = gst_element_get_factory(source);
		g_object_unref(source);
		if (!factory)
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - cannot get source factory");
			goto seek_unpause;
		}
		name = gst_plugin_feature_get_name(GST_PLUGIN_FEATURE(factory));
		if (!name)
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - cannot get source name");
			goto seek_unpause;
		}
		/*
		 * We know that filesrc and souphttpsrc will not timeout after long pause
		 * If there are other sources which will not timeout, add them here
		*/
		if (!strcmp(name, "filesrc") || !strcmp(name, "souphttpsrc"))
		{
			GstStateChangeReturn ret;
			/* make sure that last state change was successfull */
			ret = gst_element_get_state(m_gst_playbin, &state, &pending, 0);
			if (ret == GST_STATE_CHANGE_SUCCESS)
			{
				gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);
				ret = gst_element_get_state(m_gst_playbin, &state, &pending, 0);
				if (ret == GST_STATE_CHANGE_SUCCESS)
					return 0;
			}
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - invalid state, state:%s pending:%s ret:%s",
				gst_element_state_get_name(state),
				gst_element_state_get_name(pending),
				gst_element_state_change_return_get_name(ret));
		}
		else
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - source '%s' is not supported", name);
		}
seek_unpause:
		eDebugNoNewLine(", doing seeking unpause\n");
	}

	m_currentTrickRatio = ratio;

	bool validposition = false;
	gint64 pos = 0;
	pts_t pts;
	if (getPlayPosition(pts) >= 0)
	{
		validposition = true;
		pos = pts * 11111LL;
	}

	gst_element_get_state(m_gst_playbin, &state, &pending, 1 * GST_SECOND);
	if (state != GST_STATE_PLAYING)
		gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);

	if (validposition)
	{
		if (ratio >= 0.0)
		{
			gst_element_seek(m_gst_playbin, ratio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT | GST_SEEK_FLAG_SKIP), GST_SEEK_TYPE_SET, pos, GST_SEEK_TYPE_SET, -1);
		}
		else
		{
			/* note that most elements will not support negative speed */
			gst_element_seek(m_gst_playbin, ratio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_SKIP), GST_SEEK_TYPE_SET, 0, GST_SEEK_TYPE_SET, pos);
		}
	}

	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	return 0;
}


RESULT eServiceMP3::seekRelative(int direction, pts_t to)
{
	if (!m_gst_playbin)
		return -1;

	pts_t ppos;
	if (getPlayPosition(ppos) < 0) return -1;
	ppos += to * direction;
	if (ppos < 0)
		ppos = 0;
	return seekTo(ppos);
}

gint eServiceMP3::match_sinktype(const GValue *velement, const gchar *type)
{
	GstElement *element = GST_ELEMENT_CAST(g_value_get_object(velement));
	return strcmp(g_type_name(G_OBJECT_TYPE(element)), type);
}

RESULT eServiceMP3::getPlayPosition(pts_t &pts)
{
	gint64 pos;
	pts = 0;

	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	if ((audioSink || videoSink) && !m_paused && !m_sourceinfo.is_hls)
	{
		g_signal_emit_by_name(videoSink ? videoSink : audioSink, "get-decoder-time", &pos);
		if (!GST_CLOCK_TIME_IS_VALID(pos)) return -1;
	}
	else
	{
		GstFormat fmt = GST_FORMAT_TIME;
		if (!gst_element_query_position(m_gst_playbin, fmt, &pos))
		{
			eDebug("[eServiceMP3] gst_element_query_position failed in getPlayPosition");
			return -1;
		}
	}

	/* pos is in nanoseconds. we have 90 000 pts per second. */
	pts = pos / 11111LL;
	return 0;
}

RESULT eServiceMP3::setTrickmode(int trick)
{
		/* trickmode is not yet supported by our dvbmediasinks. */
	return -1;
}

RESULT eServiceMP3::isCurrentlySeekable()
{
	int ret = 3; /* just assume that seeking and fast/slow winding are possible */

	if (!m_gst_playbin)
		return 0;

	return ret;
}

RESULT eServiceMP3::info(ePtr<iServiceInformation>&i)
{
	i = this;
	return 0;
}

RESULT eServiceMP3::getName(std::string &name)
{
	std::string title = m_ref.getName();
	if (title.empty())
	{
		name = m_ref.path;
		size_t n = name.rfind('/');
		if (n != std::string::npos)
			name = name.substr(n + 1);
	}
	else
		name = title;

	m_prov = m_ref.prov;

	return 0;
}

RESULT eServiceMP3::getEvent(ePtr<eServiceEvent> &evt, int nownext)
{
	evt = nownext ? m_event_next : m_event_now;
	if (!evt)
		return -1;
	return 0;
}

int eServiceMP3::getInfo(int w)
{
	const gchar *tag = 0;

	switch (w)
	{
	case sServiceref: return m_ref;
	case sVideoHeight: return m_height;
	case sVideoWidth: return m_width;
	case sFrameRate: return m_framerate;
	case sProgressive: return m_progressive;
	case sGamma: return m_gamma;
	case sAspect: return m_aspect;
	case sTagTitle:
	case sTagArtist:
	case sTagAlbum:
	case sTagTitleSortname:
	case sTagArtistSortname:
	case sTagAlbumSortname:
	case sTagDate:
	case sTagComposer:
	case sTagGenre:
	case sTagComment:
	case sTagExtendedComment:
	case sTagLocation:
	case sTagHomepage:
	case sTagDescription:
	case sTagVersion:
	case sTagISRC:
	case sTagOrganization:
	case sTagCopyright:
	case sTagCopyrightURI:
	case sTagContact:
	case sTagLicense:
	case sTagLicenseURI:
	case sTagCodec:
	case sTagAudioCodec:
	case sTagVideoCodec:
	case sTagEncoder:
	case sTagLanguageCode:
	case sTagKeywords:
	case sTagChannelMode:
	case sUser+12:
		return resIsString;
	case sTagTrackGain:
	case sTagTrackPeak:
	case sTagAlbumGain:
	case sTagAlbumPeak:
	case sTagReferenceLevel:
	case sTagBeatsPerMinute:
	case sTagImage:
	case sTagPreviewImage:
	case sTagAttachment:
		return resIsPyObject;
	case sTagTrackNumber:
		tag = GST_TAG_TRACK_NUMBER;
		break;
	case sTagTrackCount:
		tag = GST_TAG_TRACK_COUNT;
		break;
	case sTagAlbumVolumeNumber:
		tag = GST_TAG_ALBUM_VOLUME_NUMBER;
		break;
	case sTagAlbumVolumeCount:
		tag = GST_TAG_ALBUM_VOLUME_COUNT;
		break;
	case sTagBitrate:
		tag = GST_TAG_BITRATE;
		break;
	case sTagNominalBitrate:
		tag = GST_TAG_NOMINAL_BITRATE;
		break;
	case sTagMinimumBitrate:
		tag = GST_TAG_MINIMUM_BITRATE;
		break;
	case sTagMaximumBitrate:
		tag = GST_TAG_MAXIMUM_BITRATE;
		break;
	case sTagSerial:
		tag = GST_TAG_SERIAL;
		break;
	case sTagEncoderVersion:
		tag = GST_TAG_ENCODER_VERSION;
		break;
	case sTagCRC:
		tag = "has-crc";
		break;
	case sBuffer: return m_bufferInfo.bufferPercent;
	case sVideoType:
	{
		if (!videoSink) return -1;
		guint64 v = -1;
		g_signal_emit_by_name(videoSink, "get-video-codec", &v);
		return (int) v;
		break;
	}
	case sSID: return m_ref.getData(1);
	default:
		return resNA;
	}

	if (!m_stream_tags || !tag)
		return 0;

	guint value;
	if (gst_tag_list_get_uint(m_stream_tags, tag, &value))
		return (int) value;

	return 0;
}

std::string eServiceMP3::getInfoString(int w)
{
	switch (w)
	{
	case sProvider:
	{
		if (m_sourceinfo.is_streaming) {
			if (m_prov.empty()) {
				return "IPTV";
			} else {
				return m_prov;
			}
		}
		return "FILE";
	}
	case sServiceref:
		return m_ref.toString();
	default:
		break;
	}

	if ( !m_stream_tags && w < sUser && w > 26 )
		return "";
	const gchar *tag = 0;
	switch (w)
	{
	case sTagTitle:
		tag = GST_TAG_TITLE;
		break;
	case sTagArtist:
		tag = GST_TAG_ARTIST;
		break;
	case sTagAlbum:
		tag = GST_TAG_ALBUM;
		break;
	case sTagTitleSortname:
		tag = GST_TAG_TITLE_SORTNAME;
		break;
	case sTagArtistSortname:
		tag = GST_TAG_ARTIST_SORTNAME;
		break;
	case sTagAlbumSortname:
		tag = GST_TAG_ALBUM_SORTNAME;
		break;
	case sTagDate:
		GDate *date;
		GstDateTime *date_time;
		if (gst_tag_list_get_date(m_stream_tags, GST_TAG_DATE, &date))
		{
			gchar res[5];
			snprintf(res, sizeof(res), "%06d", g_date_get_year(date));
			g_date_free(date);
			return (std::string)res;
		}
		else if (gst_tag_list_get_date_time(m_stream_tags, GST_TAG_DATE_TIME, &date_time))
		{
			if (gst_date_time_has_year(date_time))
			{
				gchar res[5];
				snprintf(res, sizeof(res), "%06d", gst_date_time_get_year(date_time));
				gst_date_time_unref(date_time);
				return (std::string)res;
			}
			gst_date_time_unref(date_time);
		}
		break;
	case sTagComposer:
		tag = GST_TAG_COMPOSER;
		break;
	case sTagGenre:
		tag = GST_TAG_GENRE;
		break;
	case sTagComment:
		tag = GST_TAG_COMMENT;
		break;
	case sTagExtendedComment:
		tag = GST_TAG_EXTENDED_COMMENT;
		break;
	case sTagLocation:
		tag = GST_TAG_LOCATION;
		break;
	case sTagHomepage:
		tag = GST_TAG_HOMEPAGE;
		break;
	case sTagDescription:
		tag = GST_TAG_DESCRIPTION;
		break;
	case sTagVersion:
		tag = GST_TAG_VERSION;
		break;
	case sTagISRC:
		tag = GST_TAG_ISRC;
		break;
	case sTagOrganization:
		tag = GST_TAG_ORGANIZATION;
		break;
	case sTagCopyright:
		tag = GST_TAG_COPYRIGHT;
		break;
	case sTagCopyrightURI:
		tag = GST_TAG_COPYRIGHT_URI;
		break;
	case sTagContact:
		tag = GST_TAG_CONTACT;
		break;
	case sTagLicense:
		tag = GST_TAG_LICENSE;
		break;
	case sTagLicenseURI:
		tag = GST_TAG_LICENSE_URI;
		break;
	case sTagCodec:
		tag = GST_TAG_CODEC;
		break;
	case sTagAudioCodec:
		tag = GST_TAG_AUDIO_CODEC;
		break;
	case sTagVideoCodec:
		tag = GST_TAG_VIDEO_CODEC;
		break;
	case sTagEncoder:
		tag = GST_TAG_ENCODER;
		break;
	case sTagLanguageCode:
		tag = GST_TAG_LANGUAGE_CODE;
		break;
	case sTagKeywords:
		tag = GST_TAG_KEYWORDS;
		break;
	case sTagChannelMode:
		tag = "channel-mode";
		break;
	case sUser+12:
		return m_errorInfo.error_message;
	default:
		return "";
	}
	if ( !tag )
		return "";
	gchar *value = NULL;
	if (m_stream_tags && gst_tag_list_get_string(m_stream_tags, tag, &value))
	{
		std::string res = value;
		g_free(value);
		return res;
	}
	return "";
}

ePtr<iServiceInfoContainer> eServiceMP3::getInfoObject(int w)
{
	eServiceMP3InfoContainer *container = new eServiceMP3InfoContainer;
	ePtr<iServiceInfoContainer> retval = container;
	const gchar *tag = 0;
	bool isBuffer = false;
	switch (w)
	{
		case sTagTrackGain:
			tag = GST_TAG_TRACK_GAIN;
			break;
		case sTagTrackPeak:
			tag = GST_TAG_TRACK_PEAK;
			break;
		case sTagAlbumGain:
			tag = GST_TAG_ALBUM_GAIN;
			break;
		case sTagAlbumPeak:
			tag = GST_TAG_ALBUM_PEAK;
			break;
		case sTagReferenceLevel:
			tag = GST_TAG_REFERENCE_LEVEL;
			break;
		case sTagBeatsPerMinute:
			tag = GST_TAG_BEATS_PER_MINUTE;
			break;
		case sTagImage:
			tag = GST_TAG_IMAGE;
			isBuffer = true;
			break;
		case sTagPreviewImage:
			tag = GST_TAG_PREVIEW_IMAGE;
			isBuffer = true;
			break;
		case sTagAttachment:
			tag = GST_TAG_ATTACHMENT;
			isBuffer = true;
			break;
		default:
			break;
	}

	if (m_stream_tags && tag)
	{
		if (isBuffer)
		{
			const GValue *gv_buffer = gst_tag_list_get_value_index(m_stream_tags, tag, 0);
			if ( gv_buffer )
			{
				GstBuffer *buffer;
				buffer = gst_value_get_buffer (gv_buffer);
				container->setBuffer(buffer);
			}
		}
		else
		{
			gdouble value = 0.0;
			gst_tag_list_get_double(m_stream_tags, tag, &value);
			container->setDouble(value);
		}
	}
	return retval;
}

RESULT eServiceMP3::audioChannel(ePtr<iAudioChannelSelection> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::audioTracks(ePtr<iAudioTrackSelection> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::cueSheet(ePtr<iCueSheet> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::subtitle(ePtr<iSubtitleOutput> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::audioDelay(ePtr<iAudioDelay> &ptr)
{
	ptr = this;
	return 0;
}

int eServiceMP3::getNumberOfTracks()
{
 	return m_audioStreams.size();
}

int eServiceMP3::getCurrentTrack()
{
	if (m_currentAudioStream == -1)
		g_object_get (G_OBJECT (m_gst_playbin), "current-audio", &m_currentAudioStream, NULL);
	return m_currentAudioStream;
}

RESULT eServiceMP3::selectTrack(unsigned int i)
{
	bool validposition = false;
	pts_t ppos = 0;
	if (getPlayPosition(ppos) >= 0)
	{
		validposition = true;
		ppos -= 90000;
		if (ppos < 0)
			ppos = 0;
	}
	if (validposition)
	{
		/* flush */
		seekTo(ppos);
	}
	return selectAudioStream(i);
}

int eServiceMP3::selectAudioStream(int i)
{
	int current_audio;
	g_object_set (G_OBJECT (m_gst_playbin), "current-audio", i, NULL);
	g_object_get (G_OBJECT (m_gst_playbin), "current-audio", &current_audio, NULL);
	if ( current_audio == i )
	{
		eDebug ("[eServiceMP3] switched to audio stream %i", current_audio);
		m_currentAudioStream = i;
		setCacheEntry(true, i);
		return 0;
	}
	return -1;
}

int eServiceMP3::getCurrentChannel()
{
	return STEREO;
}

RESULT eServiceMP3::selectChannel(int i)
{
	eDebug("[eServiceMP3] selectChannel(%i)",i);
	return 0;
}

RESULT eServiceMP3::getTrackInfo(struct iAudioTrackInfo &info, unsigned int i)
{
	if (i >= m_audioStreams.size())
	{
		return -2;
	}

	info.m_description = m_audioStreams[i].codec;

	if (info.m_language.empty())
	{
		info.m_language = m_audioStreams[i].language_code;
	}

	return 0;
}

subtype_t getSubtitleType(GstPad* pad, gchar *g_codec=NULL)
{
	subtype_t type = stUnknown;
	GstCaps* caps = gst_pad_get_current_caps(pad);
	if (!caps && !g_codec)
	{
		caps = gst_pad_get_allowed_caps(pad);
	}

	if (caps && !gst_caps_is_empty(caps))
	{
		GstStructure* str = gst_caps_get_structure(caps, 0);
		if (str)
		{
			const gchar *g_type = gst_structure_get_name(str);
			eDebug("[eServiceMP3] getSubtitleType::subtitle probe caps type=%s", g_type ? g_type : "(null)");
			if (g_type)
			{
				if ( !strcmp(g_type, "subpicture/x-dvd") )
					type = stVOB;
				else if ( !strcmp(g_type, "subpicture/x-dvb") )
					type = stDVB;
				else if ( !strcmp(g_type, "text/x-pango-markup") )
					type = stSRT;
				else if ( !strcmp(g_type, "text/plain") || !strcmp(g_type, "text/x-plain") || !strcmp(g_type, "text/x-raw") )
					type = stPlainText;
				else if ( !strcmp(g_type, "subpicture/x-pgs") )
					type = stPGS;
				else
					eDebug("[eServiceMP3] getSubtitleType::unsupported subtitle caps %s (%s)", g_type, g_codec ? g_codec : "(null)");
			}
		}
	}
	else if ( g_codec )
	{
		eDebug("[eServiceMP3] getSubtitleType::subtitle probe codec tag=%s", g_codec);
		if ( !strcmp(g_codec, "VOB") )
			type = stVOB;
		else if ( !strcmp(g_codec, "SubStation Alpha") || !strcmp(g_codec, "SSA") )
			type = stSSA;
		else if ( !strcmp(g_codec, "ASS") )
			type = stASS;
		else if ( !strcmp(g_codec, "SRT") )
			type = stSRT;
		else if ( !strcmp(g_codec, "UTF-8 plain text") )
			type = stPlainText;
		else
			eDebug("[eServiceMP3] getSubtitleType::unsupported subtitle codec %s", g_codec);
	}
	else
		eDebug("[eServiceMP3] getSubtitleType::unidentifiable subtitle stream!");

	return type;
}

void eServiceMP3::gstBusCall(GstMessage *msg)
{
	if (!msg)
		return;
	gchar *sourceName;
	GstObject *source;
	GstElement *subsink;
	source = GST_MESSAGE_SRC(msg);
	if (!GST_IS_OBJECT(source))
		return;
	sourceName = gst_object_get_name(source);
#if 0
	gchar *string;
	if (gst_message_get_structure(msg))
		string = gst_structure_to_string(gst_message_get_structure(msg));
	else
		string = g_strdup(GST_MESSAGE_TYPE_NAME(msg));
	eDebug("[eServiceMP3] eTsRemoteSource::gst_message from %s: %s", sourceName, string);
	g_free(string);
#endif
	switch (GST_MESSAGE_TYPE (msg))
	{
		case GST_MESSAGE_EOS:
			m_event((iPlayableService*)this, evEOF);
			break;
		case GST_MESSAGE_STATE_CHANGED:
		{
			if(GST_MESSAGE_SRC(msg) != GST_OBJECT(m_gst_playbin))
				break;

			GstState old_state, new_state;
			gst_message_parse_state_changed(msg, &old_state, &new_state, NULL);

			if(old_state == new_state)
				break;

			eDebug("[eServiceMP3] state transition %s -> %s", gst_element_state_get_name(old_state), gst_element_state_get_name(new_state));

			GstStateChange transition = (GstStateChange)GST_STATE_TRANSITION(old_state, new_state);

			switch(transition)
			{
				case GST_STATE_CHANGE_READY_TO_PAUSED:
				{
					m_state = stRunning;
					m_event(this, evStart);
					GValue result = { 0, };
					GstIterator *children;
					subsink = gst_bin_get_by_name(GST_BIN(m_gst_playbin), "subtitle_sink");
					if (subsink)
					{
#ifdef GSTREAMER_SUBTITLE_SYNC_MODE_BUG
						/*
						 * HACK: disable sync mode for now, gstreamer suffers from a bug causing sparse streams to loose sync, after pause/resume / skip
						 * see: https://bugzilla.gnome.org/show_bug.cgi?id=619434
						 * Sideeffect of using sync=false is that we receive subtitle buffers (far) ahead of their
						 * display time.
						 * Not too far ahead for subtitles contained in the media container.
						 * But for external srt files, we could receive all subtitles at once.
						 * And not just once, but after each pause/resume / skip.
						 * So as soon as gstreamer has been fixed to keep sync in sparse streams, sync needs to be re-enabled.
						 */
						g_object_set (G_OBJECT (subsink), "sync", FALSE, NULL);
#endif
#if 0
						/* we should not use ts-offset to sync with the decoder time, we have to do our own decoder timekeeping */
						g_object_set (G_OBJECT (subsink), "ts-offset", -2LL * GST_SECOND, NULL);
						/* late buffers probably will not occur very often */
						g_object_set (G_OBJECT (subsink), "max-lateness", 0LL, NULL);
						/* avoid prerolling (it might not be a good idea to preroll a sparse stream) */
						g_object_set (G_OBJECT (subsink), "async", TRUE, NULL);
#endif
						eDebug("[eServiceMP3] subsink properties set!");
						gst_object_unref(subsink);
					}
					if (audioSink)
					{
						gst_object_unref(GST_OBJECT(audioSink));
						audioSink = NULL;
					}
					if (videoSink)
					{
						gst_object_unref(GST_OBJECT(videoSink));
						videoSink = NULL;
					}
					children = gst_bin_iterate_recurse(GST_BIN(m_gst_playbin));
					if (gst_iterator_find_custom(children, (GCompareFunc)match_sinktype, &result, (gpointer)"GstDVBAudioSink"))
					{
						audioSink = GST_ELEMENT_CAST(g_value_dup_object(&result));
						g_value_unset(&result);
					}
					gst_iterator_free(children);
					children = gst_bin_iterate_recurse(GST_BIN(m_gst_playbin));
					if (gst_iterator_find_custom(children, (GCompareFunc)match_sinktype, &result, (gpointer)"GstDVBVideoSink"))
					{
						videoSink = GST_ELEMENT_CAST(g_value_dup_object(&result));
						g_value_unset(&result);
					}
					gst_iterator_free(children);

					/* if we are in preroll already do not check again the state */
					if (!m_is_live)
					{
						m_is_live = (gst_element_get_state(m_gst_playbin, NULL, NULL, 0LL) == GST_STATE_CHANGE_NO_PREROLL);
					}

					setAC3Delay(ac3_delay);
					setPCMDelay(pcm_delay);
					if(!m_cuesheet_loaded) /* cuesheet CVR */
						loadCuesheet();
					updateEpgCacheNowNext();

					if (!videoSink || m_ref.getData(0) == 2) // show radio pic
					{
						bool showRadioBackground = eConfigManager::getConfigBoolValue("config.misc.showradiopic", true);
						std::string radio_pic = eConfigManager::getConfigValue(showRadioBackground ? "config.misc.radiopic" : "config.misc.blackradiopic");
						m_decoder = new eTSMPEGDecoder(NULL, 0);
						m_decoder->showSinglePic(radio_pic.c_str());
					}

				}	break;
				case GST_STATE_CHANGE_PAUSED_TO_PLAYING:
				{
					m_paused = false;
					if (m_currentAudioStream < 0)
					{
						unsigned int autoaudio = 0;
						int autoaudio_level = 5;
						std::string configvalue;
						std::vector<std::string> autoaudio_languages;
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect1");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect2");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect3");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect4");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						for (unsigned int i = 0; i < m_audioStreams.size(); i++)
						{
							if (!m_audioStreams[i].language_code.empty())
							{
								int x = 1;
								for (std::vector<std::string>::iterator it = autoaudio_languages.begin(); x < autoaudio_level && it != autoaudio_languages.end(); x++, it++)
								{
									if ((*it).find(m_audioStreams[i].language_code) != std::string::npos)
									{
										autoaudio = i;
										autoaudio_level = x;
										break;
									}
								}
							}
						}

						if (autoaudio)
							selectTrack(autoaudio);
					}
					else
					{
						selectTrack(m_currentAudioStream);
					}
					m_event((iPlayableService*)this, evGstreamerPlayStarted);
				}	break;
				case GST_STATE_CHANGE_PLAYING_TO_PAUSED:
				{
					m_paused = true;
				}	break;
				case GST_STATE_CHANGE_PAUSED_TO_READY:
				{
					if (audioSink)
					{
						gst_object_unref(GST_OBJECT(audioSink));
						audioSink = NULL;
					}
					if (videoSink)
					{
						gst_object_unref(GST_OBJECT(videoSink));
						videoSink = NULL;
					}
				}	break;
			}
			break;
		}
		case GST_MESSAGE_ERROR:
		{
			gchar *debug;
			GError *err;
			gst_message_parse_error (msg, &err, &debug);
			g_free (debug);
			eWarning("[eServiceMP3] Gstreamer error: %s (%i) from %s", err->message, err->code, sourceName );
			if ( err->domain == GST_STREAM_ERROR )
			{
				if ( err->code == GST_STREAM_ERROR_CODEC_NOT_FOUND )
				{
					if ( g_strrstr(sourceName, "videosink") )
						m_event((iPlayableService*)this, evUser+11);
					else if ( g_strrstr(sourceName, "audiosink") )
						m_event((iPlayableService*)this, evUser+10);
				}
			}
			else if ( err->domain == GST_RESOURCE_ERROR )
			{
				if ( err->code == GST_RESOURCE_ERROR_OPEN_READ || err->code == GST_RESOURCE_ERROR_READ )
				{
					stop();
				}
			}
			g_error_free(err);
			break;
		}
		case GST_MESSAGE_WARNING:
		{
			gchar *debug_warn = NULL;
			GError *warn = NULL;
			gst_message_parse_warning (msg, &warn, &debug_warn);
			/* CVR this Warning occurs from time to time with external srt files
			When a new seek is done the problem off to long wait times before subtitles appears,
			after movie was restarted with a resume position is solved. */
			if(!strncmp(warn->message , "Internal data flow problem", 26) && !strncmp(sourceName, "subtitle_sink", 13))
			{
				eWarning("[eServiceMP3] Gstreamer warning : %s (%i) from %s" , warn->message, warn->code, sourceName);
				subsink = gst_bin_get_by_name(GST_BIN(m_gst_playbin), "subtitle_sink");
				if(subsink)
				{
					if (!gst_element_seek (subsink, m_currentTrickRatio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT),
						GST_SEEK_TYPE_SET, m_last_seek_pos,
						GST_SEEK_TYPE_NONE, GST_CLOCK_TIME_NONE))
					{
						eDebug("[eServiceMP3] seekToImpl subsink failed");
					}
					gst_object_unref(subsink);
				}
			}
			g_free(debug_warn);
			g_error_free(warn);
			break;
		}
		case GST_MESSAGE_INFO:
		{
			gchar *debug;
			GError *inf;

			gst_message_parse_info (msg, &inf, &debug);
			g_free (debug);
			if ( inf->domain == GST_STREAM_ERROR && inf->code == GST_STREAM_ERROR_DECODE )
			{
				if ( g_strrstr(sourceName, "videosink") )
					m_event((iPlayableService*)this, evUser+14);
			}
			g_error_free(inf);
			break;
		}
		case GST_MESSAGE_TAG:
		{
			GstTagList *tags, *result;
			gst_message_parse_tag(msg, &tags);

			result = gst_tag_list_merge(m_stream_tags, tags, GST_TAG_MERGE_REPLACE);
			if (result)
			{
				if (m_stream_tags && gst_tag_list_is_equal(m_stream_tags, result))
				{
					gst_tag_list_free(tags);
					gst_tag_list_free(result);
					break;
				}
				if (m_stream_tags)
					gst_tag_list_free(m_stream_tags);
				m_stream_tags = result;
			}

			if (!m_coverart)
			{
				const GValue *gv_image = gst_tag_list_get_value_index(tags, GST_TAG_IMAGE, 0);
				if ( gv_image )
				{
					GstBuffer *buf_image;
					GstSample *sample;
					sample = (GstSample *)g_value_get_boxed(gv_image);
					buf_image = gst_sample_get_buffer(sample);
					int fd = open("/tmp/.id3coverart", O_CREAT|O_WRONLY|O_TRUNC, 0644);
					if (fd >= 0)
					{
						guint8 *data;
						gsize size;
						GstMapInfo map;
						gst_buffer_map(buf_image, &map, GST_MAP_READ);
						data = map.data;
						size = map.size;
						int ret = write(fd, data, size);
						gst_buffer_unmap(buf_image, &map);
						close(fd);
						m_coverart = true;
						m_event((iPlayableService*)this, evUser+13);
						eDebug("[eServiceMP3] /tmp/.id3coverart %d bytes written ", ret);
					}
				}
			}
			gst_tag_list_free(tags);
			m_event((iPlayableService*)this, evUser+15); // Use user event for tags changed notification since if we use evUpdatedInfo it causes constant refreshes of AudioSelectionLists
			break;
		}
		/* TOC entry intercept used for chapter support CVR */
		case GST_MESSAGE_TOC:
		{
			HandleTocEntry(msg);
			break;
		}
		case GST_MESSAGE_ASYNC_DONE:
		{
			if(GST_MESSAGE_SRC(msg) != GST_OBJECT(m_gst_playbin))
				break;

			gint i, n_video = 0, n_audio = 0, n_text = 0;

			g_object_get (m_gst_playbin, "n-video", &n_video, NULL);
			g_object_get (m_gst_playbin, "n-audio", &n_audio, NULL);
			g_object_get (m_gst_playbin, "n-text", &n_text, NULL);


			eDebug("[eServiceMP3] async-done - %d video, %d audio, %d subtitle", n_video, n_audio, n_text);

			if ( n_video + n_audio <= 0 )
				stop();

			std::vector<audioStream> audioStreams_temp;
			std::vector<subtitleStream> subtitleStreams_temp;

			for (i = 0; i < n_audio; i++)
			{
				audioStream audio = {};
				gchar *g_codec, *g_lang;
				GstTagList *tags = NULL;
				GstPad* pad = 0;
				g_signal_emit_by_name (m_gst_playbin, "get-audio-pad", i, &pad);
				GstCaps* caps = gst_pad_get_current_caps(pad);
				gst_object_unref(pad);
				if (!caps)
					continue;
				GstStructure* str = gst_caps_get_structure(caps, 0);
				const gchar *g_type = gst_structure_get_name(str);
				eDebug("[eServiceMP3] AUDIO STRUCT=%s", g_type);
				audio.type = gstCheckAudioPad(str);
				audio.language_code = "und";
				audio.codec = g_type;
				g_codec = NULL;
				g_lang = NULL;
				g_signal_emit_by_name (m_gst_playbin, "get-audio-tags", i, &tags);
				if (tags && GST_IS_TAG_LIST(tags))
				{
					if (gst_tag_list_get_string(tags, GST_TAG_AUDIO_CODEC, &g_codec))
					{
						audio.codec = std::string(g_codec);
						g_free(g_codec);
					}
					if (gst_tag_list_get_string(tags, GST_TAG_LANGUAGE_CODE, &g_lang))
					{
						audio.language_code = std::string(g_lang);
						g_free(g_lang);
					}
					gst_tag_list_free(tags);
				}
				eDebug("[eServiceMP3] audio stream=%i codec=%s language=%s", i, audio.codec.c_str(), audio.language_code.c_str());
				audioStreams_temp.push_back(audio);
				gst_caps_unref(caps);
			}

			for (i = 0; i < n_text; i++)
			{
				gchar *g_codec = NULL, *g_lang = NULL;
				GstTagList *tags = NULL;
				g_signal_emit_by_name (m_gst_playbin, "get-text-tags", i, &tags);
				subtitleStream subs;
				subs.language_code = "und";
				if (tags && GST_IS_TAG_LIST(tags))
				{
					if (gst_tag_list_get_string(tags, GST_TAG_LANGUAGE_CODE, &g_lang))
					{
						subs.language_code = g_lang;
						g_free(g_lang);
					}
					gst_tag_list_get_string(tags, GST_TAG_SUBTITLE_CODEC, &g_codec);
					gst_tag_list_free(tags);
				}

				eDebug("[eServiceMP3] subtitle stream=%i language=%s codec=%s", i, subs.language_code.c_str(), g_codec ? g_codec : "(null)");

				GstPad* pad = 0;
				g_signal_emit_by_name (m_gst_playbin, "get-text-pad", i, &pad);
				if ( pad )
					g_signal_connect (G_OBJECT (pad), "notify::caps", G_CALLBACK (gstTextpadHasCAPS), this);

				subs.type = getSubtitleType(pad, g_codec);
				gst_object_unref(pad);
				g_free(g_codec);
				subtitleStreams_temp.push_back(subs);
			}

			bool hasChanges = m_audioStreams.size() != audioStreams_temp.size() || std::equal(m_audioStreams.begin(), m_audioStreams.end(), audioStreams_temp.begin());
			if (!hasChanges)
				hasChanges = m_subtitleStreams.size() != subtitleStreams_temp.size() || std::equal(m_subtitleStreams.begin(), m_subtitleStreams.end(), subtitleStreams_temp.begin());

			if (hasChanges)
			{
				eTrace("[eServiceMP3] audio or subtitle stream difference -- re enumerating");
				m_audioStreams.clear();
				m_subtitleStreams.clear();
				std::copy(audioStreams_temp.begin(), audioStreams_temp.end(), back_inserter(m_audioStreams));
				std::copy(subtitleStreams_temp.begin(), subtitleStreams_temp.end(), back_inserter(m_subtitleStreams));
				eTrace("[eServiceMP3] evUpdatedInfo called for audiosubs");
				m_event((iPlayableService*)this, evUpdatedInfo);
			}

			if (m_seek_paused)
			{
				m_seek_paused = false;
				gst_element_set_state(m_gst_playbin, GST_STATE_PAUSED);
			}

			if ( m_errorInfo.missing_codec != "" )
			{
				if (m_errorInfo.missing_codec.find("video/") == 0 || (m_errorInfo.missing_codec.find("audio/") == 0 && m_audioStreams.empty()))
					m_event((iPlayableService*)this, evUser+12);
			}
			break;
		}
		case GST_MESSAGE_ELEMENT:
		{
			const GstStructure *msgstruct = gst_message_get_structure(msg);
			if (msgstruct)
			{
				if ( gst_is_missing_plugin_message(msg) )
				{
					GstCaps *caps = NULL;
					gst_structure_get (msgstruct, "detail", GST_TYPE_CAPS, &caps, NULL);
					if (caps)
					{
						std::string codec = (const char*) gst_caps_to_string(caps);
						gchar *description = gst_missing_plugin_message_get_description(msg);
						if ( description )
						{
							eDebug("[eServiceMP3] m_errorInfo.missing_codec = %s", codec.c_str());
							m_errorInfo.error_message = "GStreamer plugin " + (std::string)description + " not available!\n";
							m_errorInfo.missing_codec = codec.substr(0,(codec.find_first_of(',')));
							g_free(description);
						}
						gst_caps_unref(caps);
					}
				}
				else
				{
					const gchar *eventname = gst_structure_get_name(msgstruct);
					if ( eventname )
					{
						if (!strcmp(eventname, "eventSizeChanged") || !strcmp(eventname, "eventSizeAvail"))
						{
							gst_structure_get_int (msgstruct, "aspect_ratio", &m_aspect);
							gst_structure_get_int (msgstruct, "width", &m_width);
							gst_structure_get_int (msgstruct, "height", &m_height);
							if (strstr(eventname, "Changed"))
								m_event((iPlayableService*)this, evVideoSizeChanged);
						}
						else if (!strcmp(eventname, "eventFrameRateChanged") || !strcmp(eventname, "eventFrameRateAvail"))
						{
							gst_structure_get_int (msgstruct, "frame_rate", &m_framerate);
							if (strstr(eventname, "Changed"))
								m_event((iPlayableService*)this, evVideoFramerateChanged);
						}
						else if (!strcmp(eventname, "eventProgressiveChanged") || !strcmp(eventname, "eventProgressiveAvail"))
						{
							gst_structure_get_int (msgstruct, "progressive", &m_progressive);
							if (strstr(eventname, "Changed"))
								m_event((iPlayableService*)this, evVideoProgressiveChanged);
						}
						else if (!strcmp(eventname, "eventGammaChanged"))
						{
							gst_structure_get_int (msgstruct, "gamma", &m_gamma);
							if (strstr(eventname, "Changed"))
								m_event((iPlayableService*)this, evVideoGammaChanged);
						}
						else if (!strcmp(eventname, "redirect"))
						{
							const char *uri = gst_structure_get_string(msgstruct, "new-location");
							eDebug("[eServiceMP3] redirect to %s", uri);
							gst_element_set_state (m_gst_playbin, GST_STATE_NULL);
							g_object_set(G_OBJECT (m_gst_playbin), "uri", uri, NULL);
							gst_element_set_state (m_gst_playbin, GST_STATE_PLAYING);
						}
					}
				}
			}
			break;
		}
		case GST_MESSAGE_BUFFERING:
			if (m_sourceinfo.is_streaming)
			{
				GstBufferingMode mode;
				gst_message_parse_buffering(msg, &(m_bufferInfo.bufferPercent));
				eTrace("[eServiceMP3] Buffering %u percent done", m_bufferInfo.bufferPercent);
				gst_message_parse_buffering_stats(msg, &mode, &(m_bufferInfo.avgInRate), &(m_bufferInfo.avgOutRate), &(m_bufferInfo.bufferingLeft));
				m_event((iPlayableService*)this, evBuffering);
				/*
				 * we don't react to buffer level messages, unless we are configured to use a prefill buffer
				 * (even if we are not configured to, we still use the buffer, but we rely on it to remain at the
				 * healthy level at all times, without ever having to pause the stream)
				 *
				 * Also, it does not make sense to pause the stream if it is a live stream
				 * (in which case the sink will not produce data while paused, so we won't
				 * recover from an empty buffer)
				 */
				if (m_use_prefillbuffer && !m_is_live && !m_sourceinfo.is_hls && --m_ignore_buffering_messages <= 0)
				{
					if (m_bufferInfo.bufferPercent == 100)
					{
						GstState state;
						gst_element_get_state(m_gst_playbin, &state, NULL, 0LL);
						if (state != GST_STATE_PLAYING)
						{
							eDebug("[eServiceMP3] start playing");
							gst_element_set_state (m_gst_playbin, GST_STATE_PLAYING);
						}
						/*
						 * when we start the pipeline, the contents of the buffer will immediately drain
						 * into the (hardware buffers of the) sinks, so we will receive low buffer level
						 * messages right away.
						 * Ignore the first few buffering messages, giving the buffer the chance to recover
						 * a bit, before we start handling empty buffer states again.
						 */
						m_ignore_buffering_messages = 5;
					}
					else if (m_bufferInfo.bufferPercent == 0)
					{
						eDebug("[eServiceMP3] start pause");
						gst_element_set_state (m_gst_playbin, GST_STATE_PAUSED);
						m_ignore_buffering_messages = 0;
					}
					else
					{
						m_ignore_buffering_messages = 0;
					}
				}
			}
			break;
		default:
			break;
	}
	g_free (sourceName);
}

void eServiceMP3::handleMessage(GstMessage *msg)
{
	if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_STATE_CHANGED && GST_MESSAGE_SRC(msg) != GST_OBJECT(m_gst_playbin))
	{
		/*
		 * ignore verbose state change messages for all active elements;
		 * we only need to handle state-change events for the playbin
		 */
		gst_message_unref(msg);
		return;
	}
	m_pump.send(new GstMessageContainer(1, msg, NULL, NULL));
}

GstBusSyncReply eServiceMP3::gstBusSyncHandler(GstBus *bus, GstMessage *message, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	if (_this) _this->handleMessage(message);
	return GST_BUS_DROP;
}
/*Processing TOC CVR */
void eServiceMP3::HandleTocEntry(GstMessage *msg)
{
	/* limit TOC to dvbvideosink cue sheet only works for video media */
	if (!strncmp(GST_MESSAGE_SRC_NAME(msg), "dvbvideosink", 12))
	{
		GstToc *toc;
		gboolean updated;
		gst_message_parse_toc(msg, &toc, &updated);
		for (GList* i = gst_toc_get_entries(toc); i; i = i->next)
		{
			GstTocEntry *entry = static_cast<GstTocEntry*>(i->data);
			if (gst_toc_entry_get_entry_type (entry) == GST_TOC_ENTRY_TYPE_EDITION)
			{
				/* extra debug info for testing purposes CVR should_be_removed later on */
				eTrace("[eServiceMP3] toc_type %s", gst_toc_entry_type_get_nick(gst_toc_entry_get_entry_type (entry)));
				gint y = 0;
				for (GList* x = gst_toc_entry_get_sub_entries (entry); x; x = x->next)
				{
					GstTocEntry *sub_entry = static_cast<GstTocEntry*>(x->data);
					if (gst_toc_entry_get_entry_type (sub_entry) == GST_TOC_ENTRY_TYPE_CHAPTER)
					{
						if (y == 0)
						{
							m_use_chapter_entries = true;
							if (m_cuesheet_loaded)
								m_cue_entries.clear();
							else
								loadCuesheet();
						}
						/* first chapter is movie start no cut needed */
						else if (y >= 1)
						{
							gint64 start = 0;
							gint64 pts = 0;
							gint type = 0;
							gst_toc_entry_get_start_stop_times(sub_entry, &start, NULL);
							type = 2;
							if(start > 0)
								pts = start / 11111;
							if (pts > 0)
							{
								m_cue_entries.insert(cueEntry(pts, type));
								/* extra debug info for testing purposes CVR should_be_removed later on */
								eTrace("[eServiceMP3] toc_subtype %s,Nr = %d, start= %#" G_GINT64_MODIFIER "x",
										gst_toc_entry_type_get_nick(gst_toc_entry_get_entry_type (sub_entry)), y + 1, pts);
							}
						}
						y++;
					}
				}
				if (y > 0)
				{
					m_cuesheet_changed = 1;
					m_event((iPlayableService*)this, evCuesheetChanged);
				}
			}
		}
		eDebug("[eServiceMP3] TOC entry from source %s processed", GST_MESSAGE_SRC_NAME(msg));
	}
	else
	{
		eDebug("[eServiceMP3] TOC entry from source %s not used", GST_MESSAGE_SRC_NAME(msg));
	}
}
void eServiceMP3::playbinNotifySource(GObject *object, GParamSpec *unused, gpointer user_data)
{
	GstElement *source = NULL;
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	g_object_get(object, "source", &source, NULL);
	if (source)
	{
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "timeout") != 0)
		{
			GstElementFactory *factory = gst_element_get_factory(source);
			if (factory)
			{
				const gchar *sourcename = gst_plugin_feature_get_name(GST_PLUGIN_FEATURE(factory));
				if (!strcmp(sourcename, "souphttpsrc"))
				{
					g_object_set(G_OBJECT(source), "timeout", HTTP_TIMEOUT, NULL);
				}
			}
		}
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "ssl-strict") != 0)
		{
			g_object_set(G_OBJECT(source), "ssl-strict", FALSE, NULL);
		}
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "user-agent") != 0 && !_this->m_useragent.empty())
		{
			g_object_set(G_OBJECT(source), "user-agent", _this->m_useragent.c_str(), NULL);
		}
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "extra-headers") != 0 && !_this->m_extra_headers.empty())
		{
			GstStructure *extras = gst_structure_new_empty("extras");
			size_t pos = 0;
			while (pos != std::string::npos)
			{
				std::string name, value;
				size_t start = pos;
				size_t len = std::string::npos;
				pos = _this->m_extra_headers.find('=', pos);
				if (pos != std::string::npos)
				{
					len = pos - start;
					pos++;
					name = _this->m_extra_headers.substr(start, len);
					start = pos;
					len = std::string::npos;
					pos = _this->m_extra_headers.find('&', pos);
					if (pos != std::string::npos)
					{
						len = pos - start;
						pos++;
					}
					value = _this->m_extra_headers.substr(start, len);
				}
				if (!name.empty() && !value.empty())
				{
					GValue header;
					eDebug("[eServiceMP3] setting extra-header '%s:%s'", name.c_str(), value.c_str());
					memset(&header, 0, sizeof(GValue));
					g_value_init(&header, G_TYPE_STRING);
					g_value_set_string(&header, value.c_str());
					gst_structure_set_value(extras, name.c_str(), &header);
				}
				else
				{
					eDebug("[eServiceMP3] Invalid header format %s", _this->m_extra_headers.c_str());
					break;
				}
			}
			if (gst_structure_n_fields(extras) > 0)
			{
				g_object_set(G_OBJECT(source), "extra-headers", extras, NULL);
			}
			gst_structure_free(extras);
		}
		gst_object_unref(source);
	}
}

void eServiceMP3::handleElementAdded(GstBin *bin, GstElement *element, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	if (_this)
	{
		gchar *elementname = gst_element_get_name(element);

		if (g_str_has_prefix(elementname, "queue2"))
		{
			if (_this->m_download_buffer_path != "")
			{
				g_object_set(G_OBJECT(element), "temp-template", _this->m_download_buffer_path.c_str(), NULL);
			}
			else
			{
				g_object_set(G_OBJECT(element), "temp-template", NULL, NULL);
			}
		}
		else if (g_str_has_prefix(elementname, "uridecodebin")
			|| g_str_has_prefix(elementname, "decodebin"))
		{
			/*
			 * Listen for queue2 element added to uridecodebin/decodebin2 as well.
			 * Ignore other bins since they may have unrelated queues
			 */
				g_signal_connect(element, "element-added", G_CALLBACK(handleElementAdded), user_data);
		}
		g_free(elementname);
	}
}

audiotype_t eServiceMP3::gstCheckAudioPad(GstStructure* structure)
{
	if (!structure)
		return atUnknown;

	if ( gst_structure_has_name (structure, "audio/mpeg"))
	{
		gint mpegversion, layer = -1;
		if (!gst_structure_get_int (structure, "mpegversion", &mpegversion))
			return atUnknown;

		switch (mpegversion) {
			case 1:
				{
					gst_structure_get_int (structure, "layer", &layer);
					if ( layer == 3 )
						return atMP3;
					else
						return atMPEG;
					break;
				}
			case 2:
				return atAAC;
			case 4:
				return atAAC;
			default:
				return atUnknown;
		}
	}

	else if ( gst_structure_has_name (structure, "audio/x-ac3") || gst_structure_has_name (structure, "audio/ac3") )
		return atAC3;
	else if ( gst_structure_has_name (structure, "truehd") || gst_structure_has_name (structure, "audio/ac3") )
		return atAC3;
	else if ( gst_structure_has_name (structure, "audio/x-dts") || gst_structure_has_name (structure, "audio/dts") )
		return atDTS;
	else if ( gst_structure_has_name (structure, "audio/x-raw") )
		return atPCM;

	return atUnknown;
}

void eServiceMP3::gstPoll(ePtr<GstMessageContainer> const &msg)
{
	switch (msg->getType())
	{
		case 1:
		{
			GstMessage *gstmessage = *((GstMessageContainer*)msg);
			if (gstmessage)
			{
				gstBusCall(gstmessage);
			}
			break;
		}
		case 2:
		{
			GstBuffer *buffer = *((GstMessageContainer*)msg);
			if (buffer)
			{
				pullSubtitle(buffer);
			}
			break;
		}
		case 3:
		{
			GstPad *pad = *((GstMessageContainer*)msg);
			gstTextpadHasCAPS_synced(pad);
			break;
		}
	}
}

eAutoInitPtr<eServiceFactoryMP3> init_eServiceFactoryMP3(eAutoInitNumbers::service+1, "eServiceFactoryMP3");

void eServiceMP3::gstCBsubtitleAvail(GstElement *subsink, GstBuffer *buffer, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	if (_this->m_currentSubtitleStream < 0)
	{
		if (buffer) gst_buffer_unref(buffer);
		return;
	}
	_this->m_pump.send(new GstMessageContainer(2, NULL, NULL, buffer));
}

void eServiceMP3::gstTextpadHasCAPS(GstPad *pad, GParamSpec * unused, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;

	gst_object_ref (pad);

	_this->m_pump.send(new GstMessageContainer(3, NULL, pad, NULL));
}

void eServiceMP3::gstTextpadHasCAPS_synced(GstPad *pad)
{
	GstCaps *caps = NULL;

	g_object_get (G_OBJECT (pad), "caps", &caps, NULL);

	if (caps)
	{
		subtitleStream subs;

		eDebug("[eServiceMP3] gstTextpadHasCAPS:: signal::caps = %s", gst_caps_to_string(caps));
//		eDebug("[eServiceMP3] gstGhostpadHasCAPS_synced %p %d", pad, m_subtitleStreams.size());

		if (m_currentSubtitleStream >= 0 && m_currentSubtitleStream < (int)m_subtitleStreams.size())
			subs = m_subtitleStreams[m_currentSubtitleStream];
		else {
			subs.type = stUnknown;
			subs.pad = pad;
		}

		if ( subs.type == stUnknown )
		{
			GstTagList *tags = NULL;
			gchar *g_lang = NULL;
			g_signal_emit_by_name (m_gst_playbin, "get-text-tags", m_currentSubtitleStream, &tags);

			subs.language_code = "und";
			subs.type = getSubtitleType(pad);
			if (tags && GST_IS_TAG_LIST(tags))
			{
				if (gst_tag_list_get_string(tags, GST_TAG_LANGUAGE_CODE, &g_lang))
				{
					subs.language_code = std::string(g_lang);
					g_free(g_lang);
				}
				gst_tag_list_free(tags);
			}

			if (m_currentSubtitleStream >= 0 && m_currentSubtitleStream < (int)m_subtitleStreams.size())
				m_subtitleStreams[m_currentSubtitleStream] = subs;
			else
				m_subtitleStreams.push_back(subs);
		}

//		eDebug("[eServiceMP3] gstGhostpadHasCAPS:: m_gst_prev_subtitle_caps=%s equal=%i",gst_caps_to_string(m_gst_prev_subtitle_caps),gst_caps_is_equal(m_gst_prev_subtitle_caps, caps));

		gst_caps_unref (caps);
	}
}

void eServiceMP3::subtitle_redraw_all()
{
	subtitle_page *page = m_pages;

	while(page)
	{
		subtitle_redraw(page->page_id);
		page = page->next;
	}
}

void eServiceMP3::subtitle_reset()
{
	while (subtitle_page *page = m_pages)
	{
			/* free page regions */
		while (page->page_regions)
		{
			subtitle_page_region *p = page->page_regions->next;
			delete page->page_regions;
			page->page_regions = p;
		}
			/* free regions */
		while (page->regions)
		{
			subtitle_region *region = page->regions;

			while (region->objects)
			{
				subtitle_region_object *obj = region->objects;
				region->objects = obj->next;
				delete obj;
			}

			if (region->buffer)
				region->buffer=0;

			page->regions = region->next;
			delete region;
		}

			/* free CLUTs */
		while (page->cluts)
		{
			subtitle_clut *clut = page->cluts;
			page->cluts = clut->next;
			delete clut;
		}

		m_pages = page->next;
		delete page;
	}
}

void eServiceMP3::subtitle_redraw(int page_id)
{
	eDebug("REDRAWINGGGGGGGGGGG!!!!! %d", page_id);
	subtitle_page *page = m_pages;

	while (page)
	{
		if (page->page_id == page_id)
			break;
		page = page->next;
	}
	if (!page){
		eDebug("NOT PAGE!!!!!");
		return;
	}

	/* iterate all regions in this pcs */
	subtitle_page_region *region = page->page_regions;

	eDVBSubtitlePage Page;
	Page.m_show_time = m_show_time;
	for (; region; region=region->next)
	{
		/* find corresponding region */
		subtitle_region *reg = page->regions;
		while (reg)
		{
			eDebug("LOOP REGIONS!!!!!");
			eDebug("REGION reg->region_id/region->region_id = %d/%d", reg->region_id, region->region_id);
			if (reg->region_id == region->region_id){
				eDebug("REGION FFFFFFOUND   reg->region_id == region->region_id");
				break;
			}
				
			reg = reg->next;
		}
		if (reg)
		{
			eDebug("FOUND REGION!!!!!");
			int x0 = region->region_horizontal_address;
			int y0 = region->region_vertical_address;

			if ((x0 < 0) || (y0 < 0))
				continue;

			/* find corresponding clut */
			subtitle_clut *clut = page->cluts;
			while (clut)
			{
				if (clut->clut_id == reg->clut_id)
					break;
				clut = clut->next;
			}

			int clut_size = reg->buffer->surface->clut.colors = reg->depth == subtitle_region::bpp2 ?
				4 : reg->depth == subtitle_region::bpp4 ? 16 : 256;

			reg->buffer->surface->clut.data = new gRGB[clut_size];

			gRGB *palette = reg->buffer->surface->clut.data;

			subtitle_clut_entry *entries=0;
			switch(reg->depth)
			{
				case subtitle_region::bpp2:
					if (clut)
						entries = clut->entries_2bit;
					memset(static_cast<void*>(palette), 0, 4 * sizeof(gRGB));
					// this table is tested on cyfra .. but in EN300743 the table palette[2] and palette[1] is swapped.. i dont understand this ;)
					palette[0].a = 0xFF;
					palette[2].r = palette[2].g = palette[2].b = 0xFF;
					palette[3].r = palette[3].g = palette[3].b = 0x80;
					break;
				case subtitle_region::bpp4: // tested on cyfra... but the map is another in EN300743... dont understand this...
					if (clut)
						entries = clut->entries_4bit;
					memset(static_cast<void*>(palette), 0, 16*sizeof(gRGB));
					for (int i=0; i < 16; ++i)
					{
						if (!i)
							palette[i].a = 0xFF;
						else if (i & 8)
						{
							if (i & 1)
								palette[i].r = 0x80;
							if (i & 2)
								palette[i].g = 0x80;
							if (i & 4)
								palette[i].b = 0x80;
						}
						else
						{
							if (i & 1)
								palette[i].r = 0xFF;
							if (i & 2)
								palette[i].g = 0xFF;
							if (i & 4)
								palette[i].b = 0xFF;
						}
					}
					break;
				case subtitle_region::bpp8:  // completely untested.. i never seen 8bit DVB subtitles
					if (clut)
						entries = clut->entries_8bit;
					memset(static_cast<void*>(palette), 0, 256*sizeof(gRGB));
					for (int i=0; i < 256; ++i)
					{
						switch (i & 17)
						{
						case 0: // b1 == 0 && b5 == 0
							if (!(i & 14)) // b2 == 0 && b3 == 0 && b4 == 0
							{
								if (!(i & 224)) // b6 == 0 && b7 == 0 && b8 == 0
									palette[i].a = 0xFF;
								else
								{
									if (i & 128) // R = 100% x b8
										palette[i].r = 0xFF;
									if (i & 64) // G = 100% x b7
										palette[i].g = 0xFF;
									if (i & 32) // B = 100% x b6
										palette[i].b = 0xFF;
									palette[i].a = 0xBF; // T = 75%
								}
								break;
							}
							[[fallthrough]];
						case 16: // b1 == 0 && b5 == 1
							if (i & 128) // R = 33% x b8
								palette[i].r = 0x55;
							if (i & 64) // G = 33% x b7
								palette[i].g = 0x55;
							if (i & 32) // B = 33% x b6
								palette[i].b = 0x55;
							if (i & 8) // R + 66,7% x b4
								palette[i].r += 0xAA;
							if (i & 4) // G + 66,7% x b3
								palette[i].g += 0xAA;
							if (i & 2) // B + 66,7% x b2
								palette[i].b += 0xAA;
							if (i & 16) // needed for fall through from case 0!!
								palette[i].a = 0x80; // T = 50%
							break;
						case 1: // b1 == 1 && b5 == 0
							palette[i].r =
							palette[i].g =
							palette[i].b = 0x80; // 50%
							[[fallthrough]];
						case 17: // b1 == 1 && b5 == 1
							if (i & 128) // R += 16.7% x b8
								palette[i].r += 0x2A;
							if (i & 64) // G += 16.7% x b7
								palette[i].g += 0x2A;
							if (i & 32) // B += 16.7% x b6
								palette[i].b += 0x2A;
							if (i & 8) // R += 33% x b4
								palette[i].r += 0x55;
							if (i & 4) // G += 33% x b3
								palette[i].g += 0x55;
							if (i & 2) // B += 33% x b2
								palette[i].b += 0x55;
							break;
						}
					}
					break;
			}

			int bcktrans = eConfigManager::getConfigIntValue("config.subtitles.dvb_subtitles_backtrans");
			bool yellow = eConfigManager::getConfigBoolValue("config.subtitles.dvb_subtitles_yellow");

			for (int i=0; i<clut_size; ++i)
			{
				if (entries && entries[i].valid)
				{
					int y = entries[i].Y,
						cr = entries[i].Cr,
						cb = entries[i].Cb;
					if (y > 0)
					{
						y -= 16;
						cr -= 128;
						cb -= 128;
						palette[i].r = MAX(MIN(((298 * y            + 460 * cr) / 256), 255), 0);
						palette[i].g = MAX(MIN(((298 * y -  55 * cb - 137 * cr) / 256), 255), 0);
						palette[i].b = yellow?0:MAX(MIN(((298 * y + 543 * cb  ) / 256), 255), 0);
						if (bcktrans)
						{
							if (palette[i].r || palette[i].g || palette[i].b)
								palette[i].a = (entries[i].T) & 0xFF;
							else
								palette[i].a = bcktrans;
						}
						else
							palette[i].a = (entries[i].T) & 0xFF;
					}
					else
					{
						palette[i].r = 0;
						palette[i].g = 0;
						palette[i].b = 0;
						palette[i].a = 0xFF;
					}
				}
			}

			eDVBSubtitleRegion Region;
			Region.m_pixmap = reg->buffer;
			Region.m_position.setX(x0);
			Region.m_position.setY(y0);
			Page.m_regions.push_back(Region);
			reg->committed = true;
		}
	}
	Page.m_display_size = m_display_size;
	pushDVBSubtitles(Page);
	Page.m_regions.clear();
}

void eServiceMP3::subtitle_process_line(subtitle_region *region, subtitle_region_object *object, int line, uint8_t *data, int len)
{
	bool subcentered = eConfigManager::getConfigBoolValue("config.subtitles.dvb_subtitles_centered");
	int x = subcentered ? (region->width - len) /2 : object->object_horizontal_position;
	int y = object->object_vertical_position + line;
	if (x + len > region->width)
		len = region->width - x;
	if (len < 0 || y >= region->height)
		return;

	memcpy((uint8_t*)region->buffer->surface->data + region->buffer->surface->stride * y + x, data, len);
}

static int map_2_to_4_bit_table[4];
static int map_2_to_8_bit_table[4];
static int map_4_to_8_bit_table[16];

int eServiceMP3::subtitle_process_pixel_data(subtitle_region *region, subtitle_region_object *object, int *linenr, int *linep, uint8_t *data)
{
	int data_type = *data++;
	static uint8_t line[1920];

	bitstream bit;
	bit.size=0;
	switch (data_type)
	{
	case 0x10: // 2bit pixel data
		bitstream_gs_init(&bit, data, 2);
		while (1)
		{
			int len=0, col=0;
			int code = bitstream_gs_get(&bit);
			if (code)
			{
				col = code;
				len = 1;
			} else
			{
				code = bitstream_gs_get(&bit);
				if (!code)
				{
					code = bitstream_gs_get(&bit);
					if (code == 1)
					{
						col = 0;
						len = 2;
					} else if (code == 2)
					{
						len = bitstream_gs_get(&bit) << 2;
						len |= bitstream_gs_get(&bit);
						len += 12;
						col = bitstream_gs_get(&bit);
					} else if (code == 3)
					{
						len = bitstream_gs_get(&bit) << 6;
						len |= bitstream_gs_get(&bit) << 4;
						len |= bitstream_gs_get(&bit) << 2;
						len |= bitstream_gs_get(&bit);
						len += 29;
						col = bitstream_gs_get(&bit);
					} else
						break;
				} else if (code==1)
				{
					col = 0;
					len = 1;
				} else if (code&2)
				{
					if (code&1)
						len = 3 + 4 + bitstream_gs_get(&bit);
					else
						len = 3 + bitstream_gs_get(&bit);
					col = bitstream_gs_get(&bit);
				}
			}
			uint8_t c = region->depth == subtitle_region::bpp4 ?
				map_2_to_4_bit_table[col] :
				region->depth == subtitle_region::bpp8 ?
				map_2_to_8_bit_table[col] : col;
			while (len && ((*linep) < m_display_size.width()))
			{
				line[(*linep)++] = c;
				len--;
			}
		}
		while (bit.avail != 8)
			bitstream_gs_get(&bit);
		return bit.consumed + 1;
	case 0x11: // 4bit pixel data
		bitstream_gs_init(&bit, data, 4);
		while (1)
		{
			int len=0, col=0;
			int code = bitstream_gs_get(&bit);
			if (code)
			{
				col = code;
				len = 1;
			} else
			{
				code = bitstream_gs_get(&bit);
				if (!code)
					break;
				else if (code == 0xC)
				{
					col = 0;
					len = 1;
				} else if (code == 0xD)
				{
					col = 0;
					len = 2;
				} else if (code < 8)
				{
					col = 0;
					len = (code & 7) + 2;
				} else if ((code & 0xC) == 0x8)
				{
					col = bitstream_gs_get(&bit);
					len = (code & 3) + 4;
				} else if (code == 0xE)
				{
					len = bitstream_gs_get(&bit) + 9;
					col = bitstream_gs_get(&bit);
				} else if (code == 0xF)
				{
					len  = bitstream_gs_get(&bit) << 4;
					len |= bitstream_gs_get(&bit);
					len += 25;
					col  = bitstream_gs_get(&bit);
				}
			}
			uint8_t c = region->depth == subtitle_region::bpp8 ?
				map_4_to_8_bit_table[col] : col;
			while (len && ((*linep) < m_display_size.width()))
			{
				line[(*linep)++] = c;
				len--;
			}
		}
		while (bit.avail != 8)
			bitstream_gs_get(&bit);
		return bit.consumed + 1;
	case 0x12: // 8bit pixel data
		bitstream_gs_init(&bit, data, 8);
		while(1)
		{
			int len=0, col=0;
			int code = bitstream_gs_get(&bit);
			if (code)
			{
				col = code;
				len = 1;
			} else
			{
				code = bitstream_gs_get(&bit);
				if ((code & 0x80) == 0x80)
				{
					len = code&0x7F;
					col = bitstream_gs_get(&bit);
				} else if (code&0x7F)
				{
					len = code&0x7F;
					col = 0;
				} else
					break;
			}
			while (len && ((*linep) < m_display_size.width()))
			{
				line[(*linep)++] = col;
				len--;
			}
		}
		return bit.consumed + 1;
	case 0x20:
		bitstream_gs_init(&bit, data, 4);
		for ( int i=0; i < 4; ++i )
		{
			map_2_to_4_bit_table[i] = bitstream_gs_get(&bit);
		}
		return bit.consumed + 1;
	case 0x21:
		bitstream_gs_init(&bit, data, 8);
		for ( int i=0; i < 4; ++i )
		{
			map_2_to_8_bit_table[i] = bitstream_gs_get(&bit);
		}
		return bit.consumed + 1;
	case 0x22:
		bitstream_gs_init(&bit, data, 8);
		for ( int i=0; i < 16; ++i )
		{
			map_4_to_8_bit_table[i] = bitstream_gs_get(&bit);
		}
		return bit.consumed + 1;
	case 0xF0:
		subtitle_process_line(region, object, *linenr, line, *linep);
		(*linenr)+=2; // interlaced
		*linep = 0;
		return 1;
	default:
		return -1;
	}
	return 0;
}

void eServiceMP3::pullSubtitle(GstBuffer *buffer)
{
	if (buffer && m_currentSubtitleStream >= 0 && m_currentSubtitleStream < (int)m_subtitleStreams.size())
	{
		GstMapInfo map;
		if(!gst_buffer_map(buffer, &map, GST_MAP_READ))
		{
			eLog(3, "[eServiceMP3] pullSubtitle gst_buffer_map failed");
			return;
		}
		int64_t buf_pos = GST_BUFFER_PTS(buffer);
		m_show_time = buf_pos;
		size_t len = map.size;
		eTrace("[eServiceMP3] gst_buffer_get_size %zu map.size %zu", gst_buffer_get_size(buffer), len);
		int64_t duration_ns = GST_BUFFER_DURATION(buffer);
		int subType = m_subtitleStreams[m_currentSubtitleStream].type;
		eTrace("[eServiceMP3] pullSubtitle type=%d size=%zu", subType, len);
		if ( subType )
		{
			if (subType == stDVB)
			{
				unsigned int pos = 0;
				uint8_t * data = map.data;
				if (len <= 3) {               /* len(0x20 0x00 end_of_PES_data_field_marker) */
					eWarning("Data length too short");
					return;
				}

				if (data[pos++] != 0x20) {
					eWarning("Tried to handle a PES packet private data that isn't a subtitle packet (does not start with 0x20)");
					return;
				}

				if (data[pos++] != 0x00) {
					eWarning("'Subtitle stream in this PES packet' was not 0x00, so this is in theory not a DVB subtitle stream (but some other subtitle standard?); bailing out");
					return;
				}

				while (data[pos++] == DVB_SUB_SYNC_BYTE) 
				{
					int segment_type, page_id, segment_len, processed_length;
					if ((len - pos) < (2 * 2 + 1)) {
						eWarning("Data after SYNC BYTE too short, less than needed to even get to segment_length");
						break;
					}
					segment_type = data[pos++];
					page_id = (data[pos] << 8) | data[pos + 1];
					pos += 2;
    				segment_len = (data[pos] << 8) | data[pos + 1];
					pos += 2;
					if ((len - pos) < segment_len) {
						eWarning("segment_length was told to be %u, but we only have %d bytes left", segment_len, len - pos);
						break;
					}
					subtitle_page *page, **ppage;
					page = m_pages; ppage = &m_pages;

					while (page)
					{
						if (page->page_id == page_id)
							break;
						ppage = &page->next;
						page = page->next;
					}

					processed_length = 0;
					uint8_t* segment = data+pos;
					switch (segment_type) {
						case DVB_SUB_SEGMENT_PAGE_COMPOSITION:
						{
							eTrace("Page composition segment at buffer pos %u", pos);
							int page_time_out = *segment++;
							processed_length++;
							int page_version_number = *segment >> 4;
							int page_state = ((*segment++) >> 2) & 3;
							processed_length++;
							if (!page)
							{
								page = new subtitle_page;
								page->page_regions = 0;
								page->regions = 0;
								page->page_id = page_id;
								page->cluts = 0;
								page->next = 0;
								*ppage = page;
							} else
							{
								if (page->pcs_size != segment_len)
									page->page_version_number = -1;
								// if no update, just skip this data.
								if (page->page_version_number == page_version_number)
									break;
							}

							page->state = page_state;

							// Clear page_region list before processing any type of PCS
							while (page->page_regions)
							{
								subtitle_page_region *p = page->page_regions->next;
								delete page->page_regions;
								page->page_regions = p;
							}
							page->page_regions=0;

							// when acquisition point or mode change: remove all displayed regions.
							if ((page_state == 1) || (page_state == 2))
							{
								while (page->regions)
								{
									subtitle_region *p = page->regions->next;
									while(page->regions->objects)
									{
										subtitle_region_object *ob = page->regions->objects->next;
										delete page->regions->objects;
										page->regions->objects = ob;
									}
									delete page->regions;
									page->regions = p;
								}

							}

							page->page_time_out = page_time_out;

							page->page_version_number = page_version_number;

							subtitle_page_region **r = &page->page_regions;

							// go to last entry
							while (*r)
								r = &(*r)->next;

							while (processed_length < segment_len)
							{
								uint8_t region_id = *segment++;
    							segment += 1;
								subtitle_page_region *pr;

									// append new entry to list
								pr = new subtitle_page_region;
								pr->next = 0;
								*r = pr;
								r = &pr->next;

								pr->region_id = region_id; 
								processed_length++;
								processed_length++;

								pr->region_horizontal_address  = GST_READ_UINT16_BE (segment);
								segment += 2;
								processed_length += 2;

								pr->region_vertical_address  = GST_READ_UINT16_BE (segment);
								segment += 2;
								processed_length += 2;
							}

							break;
						}
						case DVB_SUB_SEGMENT_REGION_COMPOSITION:
						{
							eDebug("Region composition segment at buffer pos %u", pos);
							int region_id = *segment++; 
							processed_length++;
							int version_number = *segment >> 4;
							int region_fill_flag = (*segment++ >> 3) & 1;
							processed_length++;

							// if we didn't yet received the pcs for this page, drop the region
							if (!page)
							{
								eDebug("[eServiceMP3] ignoring region %x, since page %02x doesn't yet exist.", region_id, page_id);
								break;
							}

							subtitle_region *region, **pregion;

							region = page->regions; pregion = &page->regions;

							while (region)
							{
								fflush(stdout);
								if (region->region_id == region_id)
									break;
								pregion = &region->next;
								region = region->next;
							}

							if (!region)
							{
								*pregion = region = new subtitle_region;
								region->next = 0;
								region->buffer=0;
								region->committed = false;
							}
							else if (region->version_number != version_number)
							{
								subtitle_region_object *objects = region->objects;
								while (objects)
								{
									subtitle_region_object *n = objects->next;
									delete objects;
									objects = n;
								}
							}
							else
								break;

							region->region_id = region_id;
							region->version_number = version_number;

							region->width  = GST_READ_UINT16_BE(segment);
							segment += 2;
							processed_length += 2;

							region->height  = GST_READ_UINT16_BE(segment);
							segment += 2;
							processed_length += 2;

							//int depth = 1 << (((*segment++) >> 2) & 7);
							int depth;
							depth = (*segment++ >> 2) & 7;

							region->depth = (subtitle_region::tDepth)depth;
							processed_length++;

							int CLUT_id = *segment++; processed_length++;

							region->clut_id = CLUT_id;

							int region_8bit_pixel_code, region_4bit_pixel_code, region_2bit_pixel_code;
							region_8bit_pixel_code = *segment++; processed_length++;
							region_4bit_pixel_code = *segment >> 4;
							region_2bit_pixel_code = (*segment++ >> 2) & 3;
							processed_length++;

							if (!region_fill_flag)
							{
								region_2bit_pixel_code = region_4bit_pixel_code = region_8bit_pixel_code = 0;
								region_fill_flag = 1;
							}

							//	create and initialise buffer only when buffer does not yet exist.

							if (region->buffer==0) {
								region->buffer = new gPixmap(eSize(region->width, region->height), 8, 1);
								memset(region->buffer->surface->data, 0, region->height * region->buffer->surface->stride);

								if (region_fill_flag)
								{
									if (depth == 1)
										memset(region->buffer->surface->data, region_2bit_pixel_code, region->height * region->width);
									else if (depth == 2)
										memset(region->buffer->surface->data, region_4bit_pixel_code, region->height * region->width);
									else if (depth == 3)
										memset(region->buffer->surface->data, region_8bit_pixel_code, region->height * region->width);
									else
										eDebug("[eServiceMP3] !!!! invalid depth");
								}
							}

							region->objects = 0;
							subtitle_region_object **pobject = &region->objects;

							while (processed_length < segment_len)
							{
								subtitle_region_object *object;

								object = new subtitle_region_object;

								*pobject = object;
								object->next = 0;
								pobject = &object->next;

								object->object_id  = *segment++ << 8;
								object->object_id |= *segment++; processed_length += 2;

								object->object_type = *segment >> 6;
								object->object_provider_flag = (*segment >> 4) & 3;
								object->object_horizontal_position  = (*segment++ & 0xF) << 8;
								object->object_horizontal_position |= *segment++;
								processed_length += 2;

								object->object_vertical_position  = (*segment++ & 0xF) << 8;
								object->object_vertical_position |= *segment++ ;
								processed_length += 2;

								if ((object->object_type == 1) || (object->object_type == 2))
								{
									object->foreground_pixel_value = *segment++;
									object->background_pixel_value = *segment++;
									processed_length += 2;
								}
							}

							if (processed_length != segment_len)
								eDebug("[eServiceMP3] DVB subtitle too less data! (%d < %d)", segment_len, processed_length);

							break;
						}
						case DVB_SUB_SEGMENT_CLUT_DEFINITION:
						{
							eDebug("CLUT definition segment at buffer pos %u", pos);
							int CLUT_id, CLUT_version_number;
							subtitle_clut *clut, **pclut;

							if (!page)
								break;

							CLUT_id = *segment++;

							CLUT_version_number = *segment++ >> 4;
							processed_length += 2;

							clut = page->cluts; pclut = &page->cluts;

							while (clut)
							{
								if (clut->clut_id == CLUT_id)
									break;
								pclut = &clut->next;
								clut = clut->next;
							}

							if (!clut)
							{
								*pclut = clut = new subtitle_clut;
								clut->next = 0;
								clut->clut_id = CLUT_id;
							}
							else if (clut->CLUT_version_number == CLUT_version_number)
								break;

							clut->CLUT_version_number=CLUT_version_number;

							memset(clut->entries_2bit, 0, sizeof(clut->entries_2bit));
							memset(clut->entries_4bit, 0, sizeof(clut->entries_4bit));
							memset(clut->entries_8bit, 0, sizeof(clut->entries_8bit));

							while (processed_length < segment_len)
							{
								int CLUT_entry_id, entry_CLUT_flag, full_range;
								int v_Y, v_Cr, v_Cb, v_T;

								CLUT_entry_id = *segment++;
								full_range = *segment & 1;
								entry_CLUT_flag = (*segment++ & 0xE0) >> 5;
								processed_length += 2;

								if (full_range)
								{
									v_Y  = *segment++;
									v_Cr = *segment++;
									v_Cb = *segment++;
									v_T  = *segment++;
									processed_length += 4;
								} else
								{
									v_Y   = *segment & 0xFC;
									v_Cr  = (*segment++ & 3) << 6;
									v_Cr |= (*segment & 0xC0) >> 2;
									v_Cb  = (*segment & 0x3C) << 2;
									v_T   = (*segment++ & 3) << 6;
									processed_length += 2;
								}

								if (entry_CLUT_flag & 1) // 8bit
								{
									clut->entries_8bit[CLUT_entry_id].Y = v_Y;
									clut->entries_8bit[CLUT_entry_id].Cr = v_Cr;
									clut->entries_8bit[CLUT_entry_id].Cb = v_Cb;
									clut->entries_8bit[CLUT_entry_id].T = v_T;
									clut->entries_8bit[CLUT_entry_id].valid = 1;
								}
								if (entry_CLUT_flag & 2) // 4bit
								{
									if (CLUT_entry_id < 16)
									{
										clut->entries_4bit[CLUT_entry_id].Y = v_Y;
										clut->entries_4bit[CLUT_entry_id].Cr = v_Cr;
										clut->entries_4bit[CLUT_entry_id].Cb = v_Cb;
										clut->entries_4bit[CLUT_entry_id].T = v_T;
										clut->entries_4bit[CLUT_entry_id].valid = 1;
									}
									else
										eDebug("[eServiceMP3] DVB subtitle CLUT entry marked as 4 bit with id %d (>15)", CLUT_entry_id);
								}
								if (entry_CLUT_flag & 4) // 2bit
								{
									if (CLUT_entry_id < 4)
									{
										clut->entries_2bit[CLUT_entry_id].Y = v_Y;
										clut->entries_2bit[CLUT_entry_id].Cr = v_Cr;
										clut->entries_2bit[CLUT_entry_id].Cb = v_Cb;
										clut->entries_2bit[CLUT_entry_id].T = v_T;
										clut->entries_2bit[CLUT_entry_id].valid = 1;
									}
									else
										eDebug("[eServiceMP3] DVB subtitle CLUT entry marked as 2 bit with id %d (>3)", CLUT_entry_id);
								}
							}
							break;
						}
						case DVB_SUB_SEGMENT_OBJECT_DATA:
						{
							eDebug("Object data segment at buffer pos %u", pos);
							int object_id;
							int object_coding_method;

							object_id  = *segment++ << 8;
							object_id |= *segment++;
							processed_length += 2;

							object_coding_method  = (*segment >> 2) & 3;
							segment++; // non_modifying_color_flag
							processed_length++;

							subtitle_region *region = page->regions;
							while (region)
							{
								subtitle_region_object *object = region->objects;
								while (object)
								{
									if (object->object_id == object_id)
									{
										if (object_coding_method == 0)
										{
											int top_field_data_blocklength, bottom_field_data_blocklength;
											int i=1, line, linep;

											top_field_data_blocklength  = *segment++ << 8;
											top_field_data_blocklength |= *segment++;

											bottom_field_data_blocklength  = *segment++ << 8;
											bottom_field_data_blocklength |= *segment++;
											processed_length += 4;

											// its working on cyfra channels.. but hmm in EN300743 the default table is 0, 7, 8, 15
											map_2_to_4_bit_table[0] = 0;
											map_2_to_4_bit_table[1] = 8;
											map_2_to_4_bit_table[2] = 7;
											map_2_to_4_bit_table[3] = 15;

											// this map is realy untested...
											map_2_to_8_bit_table[0] = 0;
											map_2_to_8_bit_table[1] = 0x88;
											map_2_to_8_bit_table[2] = 0x77;
											map_2_to_8_bit_table[3] = 0xff;

											map_4_to_8_bit_table[0] = 0;
											for (; i < 16; ++i)
												map_4_to_8_bit_table[i] = i * 0x11;

											i = 0;
											line = 0;
											linep = 0;
											while (i < top_field_data_blocklength)
											{
												int len;
												len = subtitle_process_pixel_data(region, object, &line, &linep, segment);
												if (len < 0)
													break;
												segment += len;
												processed_length += len;
												i += len;
											}

											line = 1;
											linep = 0;

											if (bottom_field_data_blocklength)
											{
												i = 0;
												while (i < bottom_field_data_blocklength)
												{
													int len;
													len = subtitle_process_pixel_data(region, object, &line, &linep, segment);
													if (len < 0)
														break;
													segment += len;
														processed_length += len;
													i += len;
												}
											}
											else if (top_field_data_blocklength)
												eDebug("[eDVBSubtitleParser] !!!! unimplemented: no bottom field! (%d : %d)", top_field_data_blocklength, bottom_field_data_blocklength);

											if ((top_field_data_blocklength + bottom_field_data_blocklength) & 1)
											{
												segment++; processed_length++;
											}
										}
										else if (object_coding_method == 1)
											eDebug("[eDVBSubtitleParser] ---- object_coding_method 1 unsupported!");
									}
									object = object->next;
								}
								region = region->next;
							}
							break;
						}
						case DVB_SUB_SEGMENT_DISPLAY_DEFINITION:
						{
							eDebug("display definition segment at buffer pos %u", pos);
							if (segment_len > 4)
							{
								int display_window_flag = (segment[0] >> 3) & 1;
								int display_width = (segment[1] << 8) | (segment[2]);
								int display_height = (segment[3] << 8) | (segment[4]);
								processed_length += 5;
								m_display_size = eSize(display_width+1, display_height+1);
								if (display_window_flag)
								{
									if (segment_len > 12)
									{
										int display_window_horizontal_position_min = (segment[4] << 8) | segment[5];
										int display_window_horizontal_position_max = (segment[6] << 8) | segment[7];
										int display_window_vertical_position_min = (segment[8] << 8) | segment[9];
										int display_window_vertical_position_max = (segment[10] << 8) | segment[11];
										eDebug("[eServiceMP3] DVB subtitle NYI hpos min %d, hpos max %d, vpos min %d, vpos max %d",
											display_window_horizontal_position_min,
											display_window_horizontal_position_max,
											display_window_vertical_position_min,
											display_window_vertical_position_max);
										processed_length += 8;
									}
									else
										eDebug("[eServiceMP3] DVB subtitle display window flag set but display definition segment to short %d!", segment_len);
								}
							}
							else
								eDebug("[eServiceMP3] DVB subtitle display definition segment to short %d!", segment_len);
							break;
						}
						case DVB_SUB_SEGMENT_END_OF_DISPLAY_SET:
						{
							eDebug("End of display set at buffer pos %u", pos);
							subtitle_redraw_all();
							m_seen_eod = true;
							break;
						}
						default:
							eWarning("Unhandled segment type 0x%x", segment_type);
							break;
					}
					pos += segment_len;
					if (pos == len) {
						eWarning("Data ended without a PES data end marker");
						return;
					}
				}

			} 
			else if ( subType < stVOB )
			{
				int delay = eConfigManager::getConfigIntValue("config.subtitles.pango_subtitles_delay");
				int subtitle_fps = eConfigManager::getConfigIntValue("config.subtitles.pango_subtitles_fps");

				double convert_fps = 1.0;
				if (subtitle_fps > 1 && m_framerate > 0)
					convert_fps = subtitle_fps / (double)m_framerate;

				std::string line((const char*)map.data, len);
				// some media muxers do add an extra new line at the end off a muxed/reencoded srt to ssa codec
				if (!line.empty() && line[line.length()-1] == '\n')
					line.erase(line.length()-1);

				eTrace("[eServiceMP3] got new text subtitle @ buf_pos = %lld ns (in pts=%lld), dur=%lld: '%s' ", buf_pos, buf_pos/11111, duration_ns, line.c_str());

				uint32_t start_ms = ((buf_pos / 1000000ULL) * convert_fps) + (delay / 90);
				uint32_t end_ms = start_ms + (duration_ns / 1000000ULL);
				m_subtitle_pages.insert(subtitle_pages_map_pair_t(end_ms, subtitle_page_t(start_ms, end_ms, line)));
				m_subtitle_sync_timer->start(1, true);
			}
			else
			{
				eLog(3, "[eServiceMP3] unsupported subpicture... ignoring");
			}
		}
		gst_buffer_unmap(buffer, &map);
	}
}

void eServiceMP3::pushDVBSubtitles(const eDVBSubtitlePage &p)
{
	m_dvb_subtitle_pages.push_back(p);

	while (1)
	{
		eDVBSubtitlePage dvb_page;
		pts_t show_time;
		if (!m_dvb_subtitle_pages.empty())
		{
			dvb_page = m_dvb_subtitle_pages.front();
			show_time = dvb_page.m_show_time;
			m_subtitle_widget->setPage(dvb_page);
			m_dvb_subtitle_pages.pop_front();
		}
		else
			return;

		// If subtitle is overdue or within 20ms the video timing then display it.
		// If not, pause subtitle processing until the subtitle should be shown
		// int diff = show_time - pos;
		// if (diff < 20*90)
		// {
		// 	//eDebug("[eDVBServicePlay] Showing subtitle with pts:%lld Video pts:%lld diff:%.03fs. Page stack size %d", show_time, pos, diff / 90000.0f, m_dvb_subtitle_pages.size());
		// 	if (type == TELETEXT)
		// 	{
		// 		m_subtitle_widget->setPage(page);
		// 		m_subtitle_pages.pop_front();
		// 	}
		// 	else
		// 	{
		// 		m_subtitle_widget->setPage(dvb_page);
		// 		m_dvb_subtitle_pages.pop_front();
		// 	}
		// }
		// else
		// {
		// 	//eDebug("[eDVBServicePlay] Delay early subtitle by %.03fs. Page stack size %d", diff / 90000.0f, m_dvb_subtitle_pages.size());
		// 	m_subtitle_sync_timer->start(diff / 90, 1);
		// 	break;
		// }
	}
}

void eServiceMP3::pushSubtitles()
{
	pts_t running_pts = 0;
	int32_t next_timer = 0, decoder_ms, start_ms, end_ms, diff_start_ms, diff_end_ms;
	subtitle_pages_map_t::iterator current;

	// wait until clock is stable

	if (getPlayPosition(running_pts) < 0)
		m_decoder_time_valid_state = 0;

	if (m_decoder_time_valid_state < 4)
	{
		m_decoder_time_valid_state++;

		if (m_prev_decoder_time == running_pts)
			m_decoder_time_valid_state = 0;

		if (m_decoder_time_valid_state < 4)
		{
			//eDebug("[eServiceMP3] *** push subtitles, waiting for clock to stabilise");
			m_prev_decoder_time = running_pts;
			next_timer = 50;
			goto exit;
		}

		//eDebug("[eServiceMP3] *** push subtitles, clock stable");
	}

	decoder_ms = running_pts / 90;

#if 0
		eDebug("[eServiceMP3] *** all subs: ");

		for (current = m_subtitle_pages.begin(); current != m_subtitle_pages.end(); current++)
		{
			start_ms = current->second.start_ms;
			end_ms = current->second.end_ms;
			diff_start_ms = start_ms - decoder_ms;
			diff_end_ms = end_ms - decoder_ms;

			eDebug("[eServiceMP3]    start: %d, end: %d, diff_start: %d, diff_end: %d: %s",
					start_ms, end_ms, diff_start_ms, diff_end_ms, current->second.text.c_str());
		}

#endif

	for (current = m_subtitle_pages.lower_bound(decoder_ms); current != m_subtitle_pages.end(); current++)
	{
		start_ms = current->second.start_ms;
		end_ms = current->second.end_ms;
		diff_start_ms = start_ms - decoder_ms;
		diff_end_ms = end_ms - decoder_ms;

#if 0
		eDebug("[eServiceMP3] *** next subtitle: decoder: %d, start: %d, end: %d, duration_ms: %d, diff_start: %d, diff_end: %d : %s",
			decoder_ms, start_ms, end_ms, end_ms - start_ms, diff_start_ms, diff_end_ms, current->second.text.c_str());
#endif

		if (diff_end_ms < 0)
		{
			//eDebug("[eServiceMP3] *** current sub has already ended, skip: %d", diff_end_ms);
			continue;
		}

		if (diff_start_ms > 20)
		{
			//eDebug("[eServiceMP3] *** current sub in the future, start timer, %d", diff_start_ms);
			next_timer = diff_start_ms;
			goto exit;
		}

		// showtime

		if (m_subtitle_widget && !m_paused)
		{
			//eDebug("[eServiceMP3] *** current sub actual, show!");

			ePangoSubtitlePage pango_page;
			gRGB rgbcol(0xD0,0xD0,0xD0);

			pango_page.m_elements.push_back(ePangoSubtitlePageElement(rgbcol, current->second.text.c_str()));
			pango_page.m_show_pts = start_ms * 90;			// actually completely unused by widget!
			pango_page.m_timeout = end_ms - decoder_ms;		// take late start into account

			m_subtitle_widget->setPage(pango_page);
		}

		//eDebug("[eServiceMP3] *** no next sub scheduled, check NEXT subtitle");
	}

	// no more subs in cache, fall through

exit:
	if (next_timer == 0)
	{
		//eDebug("[eServiceMP3] *** next timer = 0, set default timer!");
		next_timer = 1000;
	}

	m_subtitle_sync_timer->start(next_timer, true);

}

RESULT eServiceMP3::enableSubtitles(iSubtitleUser *user, struct SubtitleTrack &track)
{
	int m_subtitleStreams_size = int(m_subtitleStreams.size());
	if (track.pid > m_subtitleStreams_size || track.pid < 1)
	{
		return -1;
	}
	eDebug ("[eServiceMP3][enableSubtitles] entered: subtitle stream %i track.pid %i", m_currentSubtitleStream, track.pid - 1);
	g_object_set (G_OBJECT (m_gst_playbin), "current-text", -1, NULL);
	m_subtitle_sync_timer->stop();
	m_subtitle_pages.clear();
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	m_currentSubtitleStream = track.pid - 1;
	m_cachedSubtitleStream = m_currentSubtitleStream;
	setCacheEntry(false, track.pid - 1);
	g_object_set (G_OBJECT (m_gst_playbin), "current-text", m_currentSubtitleStream, NULL);

	m_subtitle_widget = user;

	eDebug ("[eServiceMP3] switched to subtitle stream %i", m_currentSubtitleStream);

#ifdef GSTREAMER_SUBTITLE_SYNC_MODE_BUG
		/*
		 * when we're running the subsink in sync=false mode,
		 * we have to force a seek, before the new subtitle stream will start
		 */
		seekRelative(-1, 90000);
#endif

	return 0;
}

RESULT eServiceMP3::disableSubtitles()
{
	eDebug("[eServiceMP3] disableSubtitles");
	m_currentSubtitleStream = -1;
	m_cachedSubtitleStream = m_currentSubtitleStream;
	setCacheEntry(false, -1);
	g_object_set (G_OBJECT (m_gst_playbin), "current-text", m_currentSubtitleStream, NULL);
	m_subtitle_sync_timer->stop();
	m_subtitle_pages.clear();
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	if (m_subtitle_widget) m_subtitle_widget->destroy();
	m_subtitle_widget = 0;
	return 0;
}

RESULT eServiceMP3::getCachedSubtitle(struct SubtitleTrack &track)
{
	int m_subtitleStreams_size = (int)m_subtitleStreams.size();
	if (m_autoturnon && m_subtitleStreams_size)
	{
		eDebug("[eServiceMP3][getCachedSubtitle] m_cachedSubtitleStream == -2 && m_subtitleStreams_size)");
		m_cachedSubtitleStream = 0;
		int autosub_level = 5;
		std::string configvalue;
		std::vector<std::string> autosub_languages;
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect1");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect2");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect3");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect4");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		for (int i = 0; i < m_subtitleStreams_size; i++)
		{
			if (!m_subtitleStreams[i].language_code.empty())
			{
				int x = 1;
				for (std::vector<std::string>::iterator it2 = autosub_languages.begin(); x < autosub_level && it2 != autosub_languages.end(); x++, it2++)
				{
					if ((*it2).find(m_subtitleStreams[i].language_code) != std::string::npos)
					{
						autosub_level = x;
						m_cachedSubtitleStream = i;
						break;
					}
				}
			}
		}
	}

	eDebug("[eServiceMP3][getCachedSubtitle] m_cachedSubtitleStream = %d; m_currentSubtitleStream = %d; m_subtitleStreams_size = %d ", m_cachedSubtitleStream, m_currentSubtitleStream, m_subtitleStreams_size);

	if (m_cachedSubtitleStream >= 0 && m_cachedSubtitleStream < m_subtitleStreams_size)
	{
		eDebug("[eServiceMP3][getCachedSubtitle] (m_cachedSubtitleStream >= 0 && m_cachedSubtitleStream < m_subtitleStreams_size)");
		subtype_t type = m_subtitleStreams[m_cachedSubtitleStream].type;
		track.type = type == stDVB ? 0 : 2;
		track.pid = m_cachedSubtitleStream + 1;
		track.page_number = int(type);
		track.magazine_number = 0;
		track.language_code = m_subtitleStreams[m_cachedSubtitleStream].language_code;
		return 0;
	}
	return -1;
}

RESULT eServiceMP3::getSubtitleList(std::vector<struct SubtitleTrack> &subtitlelist)
{
// 	eDebug("[eServiceMP3] getSubtitleList");
	int stream_idx = 1;

	for (std::vector<subtitleStream>::iterator IterSubtitleStream(m_subtitleStreams.begin()); IterSubtitleStream != m_subtitleStreams.end(); ++IterSubtitleStream)
	{
		subtype_t type = IterSubtitleStream->type;
		switch(type)
		{
		case stUnknown:
		case stVOB:
		case stPGS:
			break;
		case stDVB:
		{
			struct SubtitleTrack track = {};
			track.type = 0;
			track.pid = stream_idx;
			track.page_number = int(type);
			track.magazine_number = 0;
			track.language_code = IterSubtitleStream->language_code;
			subtitlelist.push_back(track);
			break;
		}
		default:
		{
			struct SubtitleTrack track = {};
			track.type = 2;
			track.pid = stream_idx;
			track.page_number = int(type);
			track.magazine_number = 0;
			track.language_code = IterSubtitleStream->language_code;
			subtitlelist.push_back(track);
		}
		}
		stream_idx++;
	}
	eDebug("[eServiceMP3] getSubtitleList finished");
	return 0;
}

RESULT eServiceMP3::streamed(ePtr<iStreamedService> &ptr)
{
	ptr = this;
	return 0;
}

ePtr<iStreamBufferInfo> eServiceMP3::getBufferCharge()
{
	return new eStreamBufferInfo(m_bufferInfo.bufferPercent, m_bufferInfo.avgInRate, m_bufferInfo.avgOutRate, m_bufferInfo.bufferingLeft, m_buffer_size);
}
/* cuesheet CVR */
PyObject *eServiceMP3::getCutList()
{
	ePyObject list = PyList_New(0);

	for (std::multiset<struct cueEntry>::iterator i(m_cue_entries.begin()); i != m_cue_entries.end(); ++i)
	{
		ePyObject tuple = PyTuple_New(2);
		PyTuple_SET_ITEM(tuple, 0, PyLong_FromLongLong(i->where));
		PyTuple_SET_ITEM(tuple, 1, PyLong_FromLong(i->what));
		PyList_Append(list, tuple);
		Py_DECREF(tuple);
	}

	return list;
}
/* cuesheet CVR */
void eServiceMP3::setCutList(ePyObject list)
{
	if (!PyList_Check(list))
		return;
	int size = PyList_Size(list);
	int i;

	m_cue_entries.clear();

	for (i=0; i<size; ++i)
	{
		ePyObject tuple = PyList_GET_ITEM(list, i);
		if (!PyTuple_Check(tuple))
		{
			eDebug("[eServiceMP3] non-tuple in cutlist");
			continue;
		}
		if (PyTuple_Size(tuple) != 2)
		{
			eDebug("[eServiceMP3] cutlist entries need to be a 2-tuple");
			continue;
		}
		ePyObject ppts = PyTuple_GET_ITEM(tuple, 0), ptype = PyTuple_GET_ITEM(tuple, 1);
		if (!(PyLong_Check(ppts) && PyLong_Check(ptype)))
		{
			eDebug("[eServiceMP3] cutlist entries need to be (pts, type)-tuples (%d %d)", PyLong_Check(ppts), PyLong_Check(ptype));
			continue;
		}
		pts_t pts = PyLong_AsLongLong(ppts);
		int type = PyLong_AsLong(ptype);
		m_cue_entries.insert(cueEntry(pts, type));
		eDebug("[eServiceMP3] adding %08llx, %d", pts, type);
	}
	m_cuesheet_changed = 1;
	m_event((iPlayableService*)this, evCuesheetChanged);
}

void eServiceMP3::setCutListEnable(int enable)
{
	m_cutlist_enabled = enable;
}

int eServiceMP3::setBufferSize(int size)
{
	m_buffer_size = size;
	g_object_set (G_OBJECT (m_gst_playbin), "buffer-size", m_buffer_size, NULL);
	return 0;
}

int eServiceMP3::getAC3Delay()
{
	return ac3_delay;
}

int eServiceMP3::getPCMDelay()
{
	return pcm_delay;
}

void eServiceMP3::setAC3Delay(int delay)
{
	ac3_delay = delay;
	if (!m_gst_playbin || m_state != stRunning)
		return;
	else
	{
		int config_delay_int = delay;

		/*
		 * NOTE: We only look for dvbmediasinks.
		 * If either the video or audio sink is of a different type,
		 * we have no chance to get them synced anyway.
		 */
		if (videoSink)
		{
			config_delay_int += eConfigManager::getConfigIntValue("config.av.generalAC3delay");
		}
		else
		{
			eDebug("[eServiceMP3] dont apply ac3 delay when no video is running!");
			config_delay_int = 0;
		}

		if (audioSink)
		{
			eTSMPEGDecoder::setHwAC3Delay(config_delay_int);
		}
	}
}

void eServiceMP3::setPCMDelay(int delay)
{
	pcm_delay = delay;
	if (!m_gst_playbin || m_state != stRunning)
		return;
	else
	{
		int config_delay_int = delay;

		/*
		 * NOTE: We only look for dvbmediasinks.
		 * If either the video or audio sink is of a different type,
		 * we have no chance to get them synced anyway.
		 */
		if (videoSink)
		{
			config_delay_int += eConfigManager::getConfigIntValue("config.av.generalPCMdelay");
		}
		else
		{
			eDebug("[eServiceMP3] dont apply pcm delay when no video is running!");
			config_delay_int = 0;
		}

		if (audioSink)
		{
			eTSMPEGDecoder::setHwPCMDelay(config_delay_int);
		}
	}
}
/* cuesheet CVR */
void eServiceMP3::loadCuesheet()
{
	if (!m_cuesheet_loaded)
	{
		eDebug("[eServiceMP3] loading cuesheet");
		m_cuesheet_loaded = true;
	}
	else
	{
		eDebug("[eServiceMP3] skip loading cuesheet multiple times");
		return;
	}

	m_cue_entries.clear();
	/* only load manual cuts if no chapter info avbl CVR */
	if (m_use_chapter_entries)
		return;

	std::string filename = m_ref.path + ".cuts";

	m_cue_entries.clear();

	FILE *f = fopen(filename.c_str(), "rb");

	if (f)
	{
		while (1)
		{
			unsigned long long where;
			unsigned int what;

			if (!fread(&where, sizeof(where), 1, f))
				break;
			if (!fread(&what, sizeof(what), 1, f))
				break;

			where = be64toh(where);
			what = ntohl(what);

			if (what > 3)
				break;

			m_cue_entries.insert(cueEntry(where, what));
		}
		fclose(f);
		eDebug("[eServiceMP3] cuts file has %zd entries", m_cue_entries.size());
	} else
		eDebug("[eServiceMP3] cutfile not found!");

	m_cuesheet_changed = 0;
	m_event((iPlayableService*)this, evCuesheetChanged);
}
/* cuesheet CVR */
void eServiceMP3::saveCuesheet()
{
	std::string filename = m_ref.path;

		/* save cuesheet only when main file is accessible. */
		/* save cuesheet only when main file is accessible. and no TOC chapters avbl*/
	if ((::access(filename.c_str(), R_OK) < 0) || m_use_chapter_entries)
		return;
	filename.append(".cuts");
	/* do not save to file if there are no cuts */
	/* remove the cuts file if cue is empty */
	if(m_cue_entries.begin() == m_cue_entries.end())
	{
		if (::access(filename.c_str(), F_OK) == 0)
			remove(filename.c_str());
		return;
	}

	FILE *f = fopen(filename.c_str(), "wb");

	if (f)
	{
		unsigned long long where;
		int what;

		for (std::multiset<cueEntry>::iterator i(m_cue_entries.begin()); i != m_cue_entries.end(); ++i)
		{
			where = htobe64(i->where);
			what = htonl(i->what);
			fwrite(&where, sizeof(where), 1, f);
			fwrite(&what, sizeof(what), 1, f);

		}
		fclose(f);
	}
	m_cuesheet_changed = 0;
}
