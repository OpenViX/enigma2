	/* note: this requires gstreamer 0.10.x and a big list of plugins. */
	/* it's currently hardcoded to use a big-endian alsasink as sink. */
#include <lib/base/ebase.h>
#include <lib/base/eerror.h>
#include <lib/base/init_num.h>
#include <lib/base/init.h>
#include <lib/base/nconfig.h>
#include <lib/base/object.h>
#include <lib/dvb/decoder.h>
#include <lib/components/file_eraser.h>
#include <lib/gui/esubtitle.h>
#include <lib/service/serviceeplayer3.h>
#include <lib/service/service.h>
#include <lib/gdi/gpixmap.h>

#include <string>
#include <sys/stat.h>

#define HTTP_TIMEOUT 60

typedef enum
{
	GST_PLAY_FLAG_VIDEO         = 0x00000001,
	GST_PLAY_FLAG_AUDIO         = 0x00000002,
	GST_PLAY_FLAG_TEXT          = 0x00000004,
	GST_PLAY_FLAG_VIS           = 0x00000008,
	GST_PLAY_FLAG_SOFT_VOLUME   = 0x00000010,
	GST_PLAY_FLAG_NATIVE_AUDIO  = 0x00000020,
	GST_PLAY_FLAG_NATIVE_VIDEO  = 0x00000040,
	GST_PLAY_FLAG_DOWNLOAD      = 0x00000080,
	GST_PLAY_FLAG_BUFFERING     = 0x00000100
} GstPlayFlags;

// eServiceFactoryEPlayer3

/*
 * gstreamer suffers from a bug causing sparse streams to loose sync, after pause/resume / skip
 * see: https://bugzilla.gnome.org/show_bug.cgi?id=619434
 * As a workaround, we run the subsink in sync=false mode
 */
#define GSTREAMER_SUBTITLE_SYNC_MODE_BUG
/**/

void ep3Blit(){
	fbClass *fb = fbClass::getInstance();
	fb->blit();
}


eServiceFactoryEPlayer3::eServiceFactoryEPlayer3()
{
	ePtr<eServiceCenter> sc;

	eServiceCenter::getPrivInstance(sc);
	if (sc)
	{
		std::list<std::string> extensions;
		//extensions.push_back("dts");
		//extensions.push_back("mp2");
		//extensions.push_back("mp3");
		//extensions.push_back("ogg");
		//extensions.push_back("ogm");
		//extensions.push_back("ogv");
		extensions.push_back("mpg");
		extensions.push_back("vob");
		//extensions.push_back("wav");
		//extensions.push_back("wave");
		extensions.push_back("m4v");
		extensions.push_back("mkv");
		extensions.push_back("avi");
		extensions.push_back("divx");
		extensions.push_back("dat");
		//extensions.push_back("flac");
		//extensions.push_back("flv");
		extensions.push_back("mp4");
		extensions.push_back("mov");
		//extensions.push_back("m4a");
		//extensions.push_back("3gp");
		//extensions.push_back("3g2");
		//extensions.push_back("asf");
#if defined(__sh__)
		extensions.push_back("mpeg");
		extensions.push_back("m2ts");
		extensions.push_back("trp");
		extensions.push_back("vdr");
		extensions.push_back("mts");
		extensions.push_back("rar");
		extensions.push_back("img");
		extensions.push_back("iso");
		extensions.push_back("ifo");
		extensions.push_back("wmv");
#endif
		//extensions.push_back("wma");
		sc->addServiceFactory(eServiceFactoryEPlayer3::id, this, extensions);
	}

	m_service_info = new eStaticServiceEPlayer3Info();
}

eServiceFactoryEPlayer3::~eServiceFactoryEPlayer3()
{
	ePtr<eServiceCenter> sc;

	eServiceCenter::getPrivInstance(sc);
	if (sc)
		sc->removeServiceFactory(eServiceFactoryEPlayer3::id);
}

DEFINE_REF(eServiceFactoryEPlayer3)

	// iServiceHandler
RESULT eServiceFactoryEPlayer3::play(const eServiceReference &ref, ePtr<iPlayableService> &ptr)
{
		// check resources...
	ptr = new eServiceEPlayer3(ref);
	return 0;
}

RESULT eServiceFactoryEPlayer3::record(const eServiceReference &ref, ePtr<iRecordableService> &ptr)
{
	ptr=0;
	return -1;
}

RESULT eServiceFactoryEPlayer3::list(const eServiceReference &, ePtr<iListableService> &ptr)
{
	ptr=0;
	return -1;
}

RESULT eServiceFactoryEPlayer3::info(const eServiceReference &ref, ePtr<iStaticServiceInformation> &ptr)
{
	ptr = m_service_info;
	return 0;
}

class eEPlayer3ServiceOfflineOperations: public iServiceOfflineOperations
{
	DECLARE_REF(eEPlayer3ServiceOfflineOperations);
	eServiceReference m_ref;
public:
	eEPlayer3ServiceOfflineOperations(const eServiceReference &ref);

	RESULT deleteFromDisk(int simulate);
	RESULT getListOfFilenames(std::list<std::string> &);
	RESULT reindex();
};

DEFINE_REF(eEPlayer3ServiceOfflineOperations);

eEPlayer3ServiceOfflineOperations::eEPlayer3ServiceOfflineOperations(const eServiceReference &ref): m_ref((const eServiceReference&)ref)
{
}

RESULT eEPlayer3ServiceOfflineOperations::deleteFromDisk(int simulate)
{
	if (!simulate)
	{
		std::list<std::string> res;
		if (getListOfFilenames(res))
			return -1;

		eBackgroundFileEraser *eraser = eBackgroundFileEraser::getInstance();
		if (!eraser)
			eDebug("FATAL !! can't get background file eraser");

		for (std::list<std::string>::iterator i(res.begin()); i != res.end(); ++i)
		{
			eDebug("Removing %s...", i->c_str());
			if (eraser)
				eraser->erase(i->c_str());
			else
				::unlink(i->c_str());
		}
	}
	return 0;
}

RESULT eEPlayer3ServiceOfflineOperations::getListOfFilenames(std::list<std::string> &res)
{
	res.clear();
	res.push_back(m_ref.path);
	return 0;
}

RESULT eEPlayer3ServiceOfflineOperations::reindex()
{
	return -1;
}


RESULT eServiceFactoryEPlayer3::offlineOperations(const eServiceReference &ref, ePtr<iServiceOfflineOperations> &ptr)
{
	ptr = new eEPlayer3ServiceOfflineOperations(ref);
	return 0;
}

// eStaticServiceEPlayer3Info


// eStaticServiceEPlayer3Info is seperated from eServiceEPlayer3 to give information
// about unopened files.

// probably eServiceEPlayer3 should use this class as well, and eStaticServiceEPlayer3Info
// should have a database backend where ID3-files etc. are cached.
// this would allow listing the mp3 database based on certain filters.

DEFINE_REF(eStaticServiceEPlayer3Info)

eStaticServiceEPlayer3Info::eStaticServiceEPlayer3Info()
{
}

RESULT eStaticServiceEPlayer3Info::getName(const eServiceReference &ref, std::string &name)
{
	if ( ref.name.length() )
		name = ref.name;
	else
	{
		size_t last = ref.path.rfind('/');
		if (last != std::string::npos)
			name = ref.path.substr(last+1);
		else
			name = ref.path;
	}
	return 0;
}

int eStaticServiceEPlayer3Info::getLength(const eServiceReference &ref)
{
	return -1;
}

int eStaticServiceEPlayer3Info::getInfo(const eServiceReference &ref, int w)
{
	switch (w)
	{
	case iServiceInformation::sTimeCreate:
		{
			struct stat s;
			if (stat(ref.path.c_str(), &s) == 0)
			{
				return s.st_mtime;
			}
		}
		break;
	case iServiceInformation::sFileSize:
		{
			struct stat s;
			if (stat(ref.path.c_str(), &s) == 0)
			{
				return s.st_size;
			}
		}
		break;
	}
	return iServiceInformation::resNA;
}

long long eStaticServiceEPlayer3Info::getFileSize(const eServiceReference &ref)
{
	struct stat s;
	if (stat(ref.path.c_str(), &s) == 0)
	{
		return s.st_size;
	}
	return 0;
}

DEFINE_REF(eStreamBufferEPlayer3Info)

eStreamBufferEPlayer3Info::eStreamBufferEPlayer3Info(int percentage, int inputrate, int outputrate, int space, int size)
: bufferPercentage(percentage),
	inputRate(inputrate),
	outputRate(outputrate),
	bufferSpace(space),
	bufferSize(size)
{
}

int eStreamBufferEPlayer3Info::getBufferPercentage() const
{
	return bufferPercentage;
}

int eStreamBufferEPlayer3Info::getAverageInputRate() const
{
	return inputRate;
}

int eStreamBufferEPlayer3Info::getAverageOutputRate() const
{
	return outputRate;
}

int eStreamBufferEPlayer3Info::getBufferSpace() const
{
	return bufferSpace;
}

int eStreamBufferEPlayer3Info::getBufferSize() const
{
	return bufferSize;
}

// eServiceEPlayer3
int eServiceEPlayer3::ac3_delay = 0,
    eServiceEPlayer3::pcm_delay = 0;

eServiceEPlayer3::eServiceEPlayer3(eServiceReference ref)
	:m_ref(ref), m_pump(eApp, 1)
{
	m_subtitle_sync_timer = eTimer::create(eApp);
	m_streamingsrc_timeout = 0;

	m_currentAudioStream = -1;
	m_currentSubtitleStream = -1;
	m_cachedSubtitleStream = 0; /* report the first subtitle stream to be 'cached'. TODO: use an actual cache. */
	m_subtitle_widget = 0;
	m_currentTrickRatio = 1.0;
	m_buffer_size = 8 * 1024 * 1024;

	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	m_errorInfo.missing_codec = "";


	CONNECT(m_subtitle_sync_timer->timeout, eServiceEPlayer3::pushSubtitles);

	m_aspect = m_width = m_height = m_framerate = m_progressive = -1;

	m_state = stIdle;
	eDebug("eServiceEPlayer3::construct!");

	const char *filename = m_ref.path.c_str();
	const char *ext = strrchr(filename, '.');
	if (!ext)
		ext = filename + strlen(filename);

	player = (Context_t*) malloc(sizeof(Context_t));

	if (player)
	{
		player->playback  = &PlaybackHandler;
		player->output    = &OutputHandler;
		player->container = &ContainerHandler;
		player->manager   = &ManagerHandler;
		printf("%s\n", player->output->Name);
	}

	//Registration of output devices
	if (player && player->output)
	{
		player->output->Command(player,OUTPUT_ADD, (void*)"audio");
		player->output->Command(player,OUTPUT_ADD, (void*)"video");
		player->output->Command(player,OUTPUT_ADD, (void*)"subtitle");
	}

	if (player && player->output && player->output->subtitle)
	{
		fbClass *fb = fbClass::getInstance();
		SubtitleOutputDef_t out;
		out.screen_width = fb->getScreenResX();
		out.screen_height = fb->getScreenResY();
		out.shareFramebuffer = 1;
		out.framebufferFD = fb->getFD();
		out.destination = fb->getLFB_Direct();
		out.destStride = fb->Stride();
		out.framebufferBlit = ep3Blit;
		player->output->subtitle->Command(player, (OutputCmd_t)OUTPUT_SET_SUBTITLE_OUTPUT, (void*) &out);
	}

	//create playback path
	char file[800] = {""};

	if (!strncmp("http://", m_ref.path.c_str(), 7))
		;
	else if (!strncmp("rtsp://", m_ref.path.c_str(), 7))
		;
	else if (!strncmp("rtmp://", m_ref.path.c_str(), 7))
		;
	else if (!strncmp("rtmpe://", m_ref.path.c_str(), 8))
		;
	else if (!strncmp("rtmpt://", m_ref.path.c_str(), 8))
		;
	else if (!strncmp("rtmps://", m_ref.path.c_str(), 8))
		;
	else if (!strncmp("rtmpte://", m_ref.path.c_str(), 9))
		;
	else if (!strncmp("rtp://", m_ref.path.c_str(), 6))
		;
	else if (!strncmp("upnp://", m_ref.path.c_str(), 7))
		;
	else if (!strncmp("mms://", m_ref.path.c_str(), 6))
		;
	else if (!strncmp("file://", m_ref.path.c_str(), 7))
		;
	else
		strcat(file, "file://");
	strcat(file, m_ref.path.c_str());

	//try to open file
	if (player && player->playback && player->playback->Command(player, PLAYBACK_OPEN, file) >= 0)
	{
		//VIDEO
		//We dont have to register video tracks, or do we ?
		//AUDIO
		if (player && player->manager && player->manager->audio)
		{
			char ** TrackList = NULL;
			player->manager->audio->Command(player, MANAGER_LIST, &TrackList);
			if (TrackList != NULL)
			{
				printf("AudioTrack List\n");
				int i = 0;
				for (i = 0; TrackList[i] != NULL; i+=2)
				{
					printf("\t%s - %s\n", TrackList[i], TrackList[i+1]);
					audioStream audio;
					audio.language_code = TrackList[i];

					// atUnknown, atMPEG, atMP3, atAC3, atDTS, atAAC, atPCM, atOGG, atFLAC
					if (    !strncmp("A_MPEG/L3",   TrackList[i+1], 9))
						audio.type = atMP3;
					else if (!strncmp("A_MP3",      TrackList[i+1], 5))
						audio.type = atMP3;
					else if (!strncmp("A_AC3",      TrackList[i+1], 5))
						audio.type = atAC3;
					else if (!strncmp("A_DTS",      TrackList[i+1], 5))
						audio.type = atDTS;
					else if (!strncmp("A_AAC",      TrackList[i+1], 5))
						audio.type = atAAC;
					else if (!strncmp("A_PCM",      TrackList[i+1], 5))
						audio.type = atPCM;
					else if (!strncmp("A_VORBIS",   TrackList[i+1], 8))
						audio.type = atOGG;
					else if (!strncmp("A_FLAC",     TrackList[i+1], 6))
						audio.type = atFLAC;
					else
						audio.type = atUnknown;

					m_audioStreams.push_back(audio);
					free(TrackList[i]);
					free(TrackList[i+1]);
				}
				free(TrackList);
			}
		}
		//SUB
		if (player && player->manager && player->manager->subtitle)
		{
			char ** TrackList = NULL;
			player->manager->subtitle->Command(player, MANAGER_LIST, &TrackList);
			if (TrackList != NULL)
			{
				printf("SubtitleTrack List\n");
				int i = 0;
				for (i = 0; TrackList[i] != NULL; i+=2)
				{
					printf("\t%s - %s\n", TrackList[i], TrackList[i+1]);
					subtitleStream sub;
					sub.language_code = TrackList[i];
					//  stPlainText, stSSA, stSRT
					if (    !strncmp("S_TEXT/SSA",   TrackList[i+1], 10) ||
							!strncmp("S_SSA", TrackList[i+1], 5))
						sub.type = stSSA;
					else if (!strncmp("S_TEXT/ASS",   TrackList[i+1], 10) ||
							!strncmp("S_AAS", TrackList[i+1], 5))
						sub.type = stSSA;
					else if (!strncmp("S_TEXT/SRT",   TrackList[i+1], 10) ||
							!strncmp("S_SRT", TrackList[i+1], 5))
						sub.type = stSRT;
					else
						sub.type = stPlainText;

					m_subtitleStreams.push_back(sub);
					free(TrackList[i]);
					free(TrackList[i+1]);
				}
				free(TrackList);
			}
		}
		m_event(this, evStart);
	}
	else
	{
		//Creation failed, no playback support for insert file, so delete playback context
		//FIXME: How to tell e2 that we failed?
		if (player && player->output)
		{
			player->output->Command(player,OUTPUT_DEL, (void*)"audio");
			player->output->Command(player,OUTPUT_DEL, (void*)"video");
			player->output->Command(player,OUTPUT_DEL, (void*)"subtitle");
		}

		if (player && player->playback)
			player->playback->Command(player,PLAYBACK_CLOSE, NULL);

		if (player)
			free(player);
		player = NULL;
	}
	//m_state = stRunning;
	eDebug("eServiceEPlayer3-<\n");
}

eServiceEPlayer3::~eServiceEPlayer3()
{
	if (m_subtitle_widget) m_subtitle_widget->destroy();
	m_subtitle_widget = 0;

	if (m_state == stRunning)
		stop();
}

DEFINE_REF(eServiceEPlayer3);

RESULT eServiceEPlayer3::connectEvent(const Slot2<void,iPlayableService*,int> &event, ePtr<eConnection> &connection)
{
	connection = new eConnection((iPlayableService*)this, m_event.connect(event));
	m_event(this, evSeekableStatusChanged);
	return 0;
}

RESULT eServiceEPlayer3::start()
{
	if (m_state != stIdle)
	{
		eDebug("eServiceEPlayer3::%s < m_state != stIdle", __func__);
		return -1;
	}

	m_state = stRunning;

	if (player && player->output && player->playback)
	{
		player->output->Command(player, OUTPUT_OPEN, NULL);
		player->playback->Command(player, PLAYBACK_PLAY, NULL);
	}

	m_event(this, evStart);

	return 0;
}

void eServiceEPlayer3::sourceTimeout()
{
	eDebug("eServiceEPlayer3::http source timeout! issuing eof...");
	m_event((iPlayableService*)this, evEOF);
}

RESULT eServiceEPlayer3::stop()
{
	if (m_state == stIdle)
	{
		eDebug("eServiceEPlayer3::%s < m_state == stIdle", __func__);
		return -1;
	}

	if (m_state == stStopped)
		return -1;

	eDebug("eServiceEPlayer3::stop %s", m_ref.path.c_str());

	if (player && player->playback && player->output)
	{
		player->playback->Command(player, PLAYBACK_STOP, NULL);
		player->output->Command(player, OUTPUT_CLOSE, NULL);
	}

	if (player && player->output)
	{
		player->output->Command(player,OUTPUT_DEL, (void*)"audio");
		player->output->Command(player,OUTPUT_DEL, (void*)"video");
		player->output->Command(player,OUTPUT_DEL, (void*)"subtitle");
	}

	if (player && player->playback)
		player->playback->Command(player,PLAYBACK_CLOSE, NULL);

	if (player)
		free(player);

	if (player != NULL)
		player = NULL;

	m_state = stStopped;

	return 0;
}

RESULT eServiceEPlayer3::setTarget(int target)
{
	return -1;
}

RESULT eServiceEPlayer3::pause(ePtr<iPauseableService> &ptr)
{
	ptr=this;
	return 0;
}

int speed_mapping[] =
{
 /* e2_ratio   speed */
	2,         1,
	4,         3,
	8,         7,
	16,        15,
	32,        31,
	64,        63,
	128,      127,
	-2,       -5,
	-4,      -10,
	-8,      -20,
	-16,      -40,
	-32,      -80,
	-64,     -160,
	-128,     -320,
	-1,       -1
};

int getSpeed(int ratio)
{
	int i = 0;
	while (speed_mapping[i] != -1)
	{
		if (speed_mapping[i] == ratio)
			return speed_mapping[i+1];
		i += 2;
	}
	return -1;
}

RESULT eServiceEPlayer3::setSlowMotion(int ratio)
{
// konfetti: in libeplayer3 we changed this because I dont like application specific stuff in a library
	int speed = getSpeed(ratio);
	if (player && player->playback && (speed != -1))
	{
		int result = 0;
		if (ratio > 1)
			result = player->playback->Command(player, PLAYBACK_SLOWMOTION, (void*)&speed);

		if (result != 0)
			return -1;
	}
	return 0;
}

RESULT eServiceEPlayer3::setFastForward(int ratio)
{
// konfetti: in libeplayer3 we changed this because I dont like application specific stuff in a library
	int speed = getSpeed(ratio);
	if (player && player->playback && (speed != -1))
	{
		int result = 0;
		if (ratio > 1)
			result = player->playback->Command(player, PLAYBACK_FASTFORWARD, (void*)&speed);
		else if (ratio < -1)
		{
			//speed = speed * -1;
			result = player->playback->Command(player, PLAYBACK_FASTBACKWARD, (void*)&speed);
		}
		else
			result = player->playback->Command(player, PLAYBACK_CONTINUE, NULL);

		if (result != 0)
			return -1;
	}
	return 0;
}

		// iPausableService
RESULT eServiceEPlayer3::pause()
{
	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_PAUSE, NULL);

	return 0;
}

RESULT eServiceEPlayer3::unpause()
{
	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_CONTINUE, NULL);

	return 0;
}

	/* iSeekableService */
RESULT eServiceEPlayer3::seek(ePtr<iSeekableService> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceEPlayer3::getLength(pts_t &pts)
{
	double length = 0;

	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_LENGTH, &length);

	if (length <= 0)
		return -1;

	pts = length * 90000;
	return 0;
}

RESULT eServiceEPlayer3::seekToImpl(pts_t to)
{
	return 0;
}

RESULT eServiceEPlayer3::seekTo(pts_t to)
{
	RESULT ret = -1;

	float pos = (to/90000.0)-10;
	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_SEEK, (void*)&pos);

	ret =0;
	return ret;
}

RESULT eServiceEPlayer3::seekRelative(int direction, pts_t to)
{
	pts_t ppos;
	if (getPlayPosition(ppos) < 0) return -1;
	ppos += to * direction;
	if (ppos < 0)
		ppos = 0;

	float pos = direction*(to/90000.0);
	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_SEEK, (void*)&pos);

	return 0;
}

RESULT eServiceEPlayer3::getPlayPosition(pts_t &pts)
{
	if (player && player->playback && !player->playback->isPlaying)
	{
		eDebug("eServiceEPlayer3::%s !!!!EOF!!!! < -1", __func__);
		if(m_state == stRunning)
			m_event((iPlayableService*)this, evEOF);
		pts = 0;
		return -1;
	}

	unsigned long long int vpts = 0;
	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_PTS, &vpts);

	if (vpts<=0)
		return -1;

	/* len is in nanoseconds. we have 90 000 pts per second. */
	pts = vpts>0?vpts:pts;;

	return 0;
}

RESULT eServiceEPlayer3::setTrickmode(int trick)
{
		/* trickmode is not yet supported by our dvbmediasinks. */
	return -1;
}

RESULT eServiceEPlayer3::isCurrentlySeekable()
{
	return 3;
}

RESULT eServiceEPlayer3::info(ePtr<iServiceInformation>&i)
{
	i = this;
	return 0;
}

RESULT eServiceEPlayer3::getName(std::string &name)
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
	return 0;
}

int eServiceEPlayer3::getInfo(int w)
{
	switch (w)
	{
	case sServiceref: return m_ref;
	case sVideoHeight: return m_height;
	case sVideoWidth: return m_width;
	case sFrameRate: return m_framerate;
	case sProgressive: return m_progressive;
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
#if not defined(__sh__)
		return resIsString;
#endif
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
	default:
		return resNA;
	}

	return 0;
}

std::string eServiceEPlayer3::getInfoString(int w)
{
	char * tag = NULL;
	char * res_str = NULL;
	switch (w)
	{
	case sTagTitle:
		tag = strdup("Title");
		break;
	case sTagArtist:
		tag = strdup("Artist");
		break;
	case sTagAlbum:
		tag = strdup("Album");
		break;
	case sTagComment:
		tag = strdup("Comment");
		break;
	case sTagTrackNumber:
		tag = strdup("Track");
		break;
	case sTagGenre:
		tag = strdup("Genre");
		break;
	case sTagDate:
		tag = strdup("Year");
		break;
	case sTagVideoCodec:
		tag = strdup("VideoType");
		break;
	case sTagAudioCodec:
		tag = strdup("AudioType");
		break;
	default:
		return "";
	}

	if (player && player->playback)
	{
		/*Hellmaster1024: we need to save the adress of tag to free the strduped mem
		  the command will retun a new adress for a new strduped string.
		  Both Strings need to be freed! */
		res_str = tag;
		player->playback->Command(player, PLAYBACK_INFO, &res_str);
		/* Hellmaster1024: in case something went wrong maybe no new adress is returned */
		if (tag != res_str)
		{
			std::string res = res_str;
			free(tag);
			free(res_str);
			return res;
		}
		else
		{
			free(tag);
			return "";
		}
	}
	free(tag);

	return "";
}

RESULT eServiceEPlayer3::audioChannel(ePtr<iAudioChannelSelection> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceEPlayer3::audioTracks(ePtr<iAudioTrackSelection> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceEPlayer3::subtitle(ePtr<iSubtitleOutput> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceEPlayer3::audioDelay(ePtr<iAudioDelay> &ptr)
{
	ptr = this;
	return 0;
}

int eServiceEPlayer3::getNumberOfTracks()
{
 	return m_audioStreams.size();
}

int eServiceEPlayer3::getCurrentTrack()
{
	return m_currentAudioStream;
}

RESULT eServiceEPlayer3::selectTrack(unsigned int i)
{
	int ret = selectAudioStream(i);

	return ret;
}

int eServiceEPlayer3::selectAudioStream(int i)
{
	if (i != m_currentAudioStream)
	{
		if (player && player->playback)
			player->playback->Command(player, PLAYBACK_SWITCH_AUDIO, (void*)&i);
		m_currentAudioStream = i;
		return 0;
	}
	return -1;
}

int eServiceEPlayer3::getCurrentChannel()
{
	return STEREO;
}

RESULT eServiceEPlayer3::selectChannel(int i)
{
	eDebug("eServiceEPlayer3::selectChannel(%i)",i);
	return 0;
}

RESULT eServiceEPlayer3::getTrackInfo(struct iAudioTrackInfo &info, unsigned int i)
{
 	if (i >= m_audioStreams.size())
		return -2;

	if (m_audioStreams[i].type == atMPEG)
		info.m_description = "MPEG";
	else if (m_audioStreams[i].type == atMP3)
		info.m_description = "MP3";
	else if (m_audioStreams[i].type == atAC3)
		info.m_description = "AC3";
	else if (m_audioStreams[i].type == atAAC)
		info.m_description = "AAC";
	else if (m_audioStreams[i].type == atDTS)
		info.m_description = "DTS";
	else if (m_audioStreams[i].type == atPCM)
		info.m_description = "PCM";
	else if (m_audioStreams[i].type == atOGG)
		info.m_description = "OGG";

	if (info.m_language.empty())
		info.m_language = m_audioStreams[i].language_code;
	return 0;
}

eAutoInitPtr<eServiceFactoryEPlayer3> init_eServiceFactoryEPlayer3(eAutoInitNumbers::service+1, "eServiceFactoryEPlayer3");

void eServiceEPlayer3::eplayerCBsubtitleAvail(long int duration_ms, size_t len, char * buffer, void* user_data)
{
	eDebug("eServiceEPlayer3::%s >", __func__);
	unsigned char tmp[len+1];
	memcpy(tmp, buffer, len);
	tmp[len] = 0;
	eDebug("gstCBsubtitleAvail: %s", tmp);
	eServiceEPlayer3 *_this = (eServiceEPlayer3*)user_data;
	if ( _this->m_subtitle_widget )
	{
		ePangoSubtitlePage page;
		gRGB rgbcol(0xD0,0xD0,0xD0);
		page.m_elements.push_back(ePangoSubtitlePageElement(rgbcol, (const char*)tmp));
		page.m_timeout = duration_ms;
		(_this->m_subtitle_widget)->setPage(page);
	}
	eDebug("eServiceEPlayer3::%s <", __func__);
}

void eServiceEPlayer3::pushSubtitles()
{
}

RESULT eServiceEPlayer3::enableSubtitles(iSubtitleUser *user, struct SubtitleTrack &track)
{
	if (m_currentSubtitleStream != track.pid)
	{
		m_subtitle_sync_timer->stop();
		m_subtitle_pages.clear();
		m_prev_decoder_time = -1;
		m_decoder_time_valid_state = 0;

		m_subtitle_widget = user;

	}

	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_SWITCH_SUBTITLE, (void*)&track.pid);

	return 0;
}

RESULT eServiceEPlayer3::disableSubtitles()
{
	eDebug("eServiceEPlayer3::disableSubtitles");

	m_subtitle_sync_timer->stop();
	m_subtitle_pages.clear();
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	if (m_subtitle_widget) m_subtitle_widget->destroy();
	m_subtitle_widget = 0;

	int pid = -1;
	if (player && player->playback)
		player->playback->Command(player, PLAYBACK_SWITCH_SUBTITLE, (void*)&pid);

	return 0;
}

RESULT eServiceEPlayer3::getCachedSubtitle(struct SubtitleTrack &track)
{

	bool autoturnon = eConfigManager::getConfigBoolValue("config.subtitles.pango_autoturnon", true);
	if (!autoturnon)
		return -1;

	if (m_cachedSubtitleStream >= 0 && m_cachedSubtitleStream < (int)m_subtitleStreams.size())
	{
		track.type = 2;
		track.pid = m_cachedSubtitleStream;
		track.page_number = int(m_subtitleStreams[m_cachedSubtitleStream].type);
		track.magazine_number = 0;
		return 0;
	}
	return -1;
}

RESULT eServiceEPlayer3::getSubtitleList(std::vector<struct SubtitleTrack> &subtitlelist)
{
// 	eDebug("eServiceEPlayer3::getSubtitleList");
	int stream_idx = 0;

	for (std::vector<subtitleStream>::iterator IterSubtitleStream(m_subtitleStreams.begin()); IterSubtitleStream != m_subtitleStreams.end(); ++IterSubtitleStream)
	{
		subtype_t type = IterSubtitleStream->type;
		switch(type)
		{
		case stUnknown:
		case stVOB:
		case stPGS:
			break;
		default:
		{
			struct SubtitleTrack track;
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
	eDebug("eServiceEPlayer3::getSubtitleList finished");
	return 0;
}

RESULT eServiceEPlayer3::streamed(ePtr<iStreamedService> &ptr)
{
	ptr = this;
	return 0;
}

ePtr<iStreamBufferInfo> eServiceEPlayer3::getBufferCharge()
{
	return new eStreamBufferEPlayer3Info(m_bufferInfo.bufferPercent, m_bufferInfo.avgInRate, m_bufferInfo.avgOutRate, m_bufferInfo.bufferingLeft, m_buffer_size);
}

int eServiceEPlayer3::setBufferSize(int size)
{
	m_buffer_size = size;
	return 0;
}

int eServiceEPlayer3::getAC3Delay()
{
	return ac3_delay;
}

int eServiceEPlayer3::getPCMDelay()
{
	return pcm_delay;
}

void eServiceEPlayer3::setAC3Delay(int delay)
{

}

void eServiceEPlayer3::setPCMDelay(int delay)
{
}
