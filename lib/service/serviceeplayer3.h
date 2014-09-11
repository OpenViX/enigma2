#ifndef __serviceeplayer3_h
#define __serviceeplayer3_h

#include <lib/base/message.h>
#include <lib/service/iservice.h>
#include <lib/dvb/pmt.h>
#include <lib/dvb/subtitle.h>
#include <lib/dvb/teletext.h>

#include <common.h>
#include <subtitle.h>
#define gint int
#define gint64 int64_t
extern OutputHandler_t		OutputHandler;
extern PlaybackHandler_t	PlaybackHandler;
extern ContainerHandler_t	ContainerHandler;
extern ManagerHandler_t	ManagerHandler;

/* for subtitles */
#include <lib/gui/esubtitle.h>

class eStaticServiceEPlayer3Info;

class eServiceFactoryEPlayer3: public iServiceHandler
{
	DECLARE_REF(eServiceFactoryEPlayer3);
public:
	eServiceFactoryEPlayer3();
	virtual ~eServiceFactoryEPlayer3();
	enum { id = 0x1003 };

		// iServiceHandler
	RESULT play(const eServiceReference &, ePtr<iPlayableService> &ptr);
	RESULT record(const eServiceReference &, ePtr<iRecordableService> &ptr);
	RESULT list(const eServiceReference &, ePtr<iListableService> &ptr);
	RESULT info(const eServiceReference &, ePtr<iStaticServiceInformation> &ptr);
	RESULT offlineOperations(const eServiceReference &, ePtr<iServiceOfflineOperations> &ptr);
private:
	ePtr<eStaticServiceEPlayer3Info> m_service_info;
};

class eStaticServiceEPlayer3Info: public iStaticServiceInformation
{
	DECLARE_REF(eStaticServiceEPlayer3Info);
	friend class eServiceFactoryEPlayer3;
	eStaticServiceEPlayer3Info();
public:
	RESULT getName(const eServiceReference &ref, std::string &name);
	int getLength(const eServiceReference &ref);
	int getInfo(const eServiceReference &ref, int w);
	int isPlayable(const eServiceReference &ref, const eServiceReference &ignore, bool simulate) { return 1; }
	long long getFileSize(const eServiceReference &ref);
};

class eStreamBufferEPlayer3Info: public iStreamBufferInfo
{
	DECLARE_REF(eStreamBufferEPlayer3Info);
	int bufferPercentage;
	int inputRate;
	int outputRate;
	int bufferSpace;
	int bufferSize;

public:
	eStreamBufferEPlayer3Info(int percentage, int inputrate, int outputrate, int space, int size);

	int getBufferPercentage() const;
	int getAverageInputRate() const;
	int getAverageOutputRate() const;
	int getBufferSpace() const;
	int getBufferSize() const;
};

class eServiceEPlayer3InfoContainer: public iServiceInfoContainer
{
	DECLARE_REF(eServiceEPlayer3InfoContainer);

	double doubleValue;


	unsigned char *bufferData;
	unsigned int bufferSize;

public:
	eServiceEPlayer3InfoContainer();
	~eServiceEPlayer3InfoContainer();

	double getDouble(unsigned int index) const;
	unsigned char *getBuffer(unsigned int &size) const;

	void setDouble(double value);
};

typedef enum { atUnknown, atMPEG, atMP3, atAC3, atDTS, atAAC, atPCM, atOGG, atFLAC, atWMA } audiotype_t;
typedef enum { stUnknown, stPlainText, stSSA, stASS, stSRT, stVOB, stPGS } subtype_t;
typedef enum { ctNone, ctMPEGTS, ctMPEGPS, ctMKV, ctAVI, ctMP4, ctVCD, ctCDA, ctASF, ctOGG } containertype_t;

class eServiceEPlayer3: public iPlayableService, public iPauseableService,
	public iServiceInformation, public iSeekableService, public iAudioTrackSelection, public iAudioChannelSelection, 
	public iSubtitleOutput, public iStreamedService, public iAudioDelay, public Object
{
	DECLARE_REF(eServiceEPlayer3);
public:
	virtual ~eServiceEPlayer3();

		// iPlayableService
	RESULT connectEvent(const Slot2<void,iPlayableService*,int> &event, ePtr<eConnection> &connection);
	RESULT start();
	RESULT stop();
	RESULT setTarget(int target);
	
	RESULT pause(ePtr<iPauseableService> &ptr);
	RESULT setSlowMotion(int ratio);
	RESULT setFastForward(int ratio);

	RESULT seek(ePtr<iSeekableService> &ptr);
	RESULT audioTracks(ePtr<iAudioTrackSelection> &ptr);
	RESULT audioChannel(ePtr<iAudioChannelSelection> &ptr);
	RESULT subtitle(ePtr<iSubtitleOutput> &ptr);
	RESULT audioDelay(ePtr<iAudioDelay> &ptr);

		// not implemented (yet)
	RESULT frontendInfo(ePtr<iFrontendInformation> &ptr) { ptr = 0; return -1; }
	RESULT subServices(ePtr<iSubserviceList> &ptr) { ptr = 0; return -1; }
	RESULT timeshift(ePtr<iTimeshiftService> &ptr) { ptr = 0; return -1; }
	RESULT cueSheet(ePtr<iCueSheet> &ptr) { ptr = 0; return -1; }

	RESULT rdsDecoder(ePtr<iRdsDecoder> &ptr) { ptr = 0; return -1; }
	RESULT keys(ePtr<iServiceKeys> &ptr) { ptr = 0; return -1; }
	RESULT stream(ePtr<iStreamableService> &ptr) { ptr = 0; return -1; }

		// iPausableService
	RESULT pause();
	RESULT unpause();
	
	RESULT info(ePtr<iServiceInformation>&);
	
		// iSeekableService
	RESULT getLength(pts_t &SWIG_OUTPUT);
	RESULT seekTo(pts_t to);
	RESULT seekRelative(int direction, pts_t to);
	RESULT getPlayPosition(pts_t &SWIG_OUTPUT);
	RESULT setTrickmode(int trick);
	RESULT isCurrentlySeekable();

		// iServiceInformation
	RESULT getName(std::string &name);
	int getInfo(int w);
	std::string getInfoString(int w);

		// iAudioTrackSelection	
	int getNumberOfTracks();
	RESULT selectTrack(unsigned int i);
	RESULT getTrackInfo(struct iAudioTrackInfo &, unsigned int n);
	int getCurrentTrack();

		// iAudioChannelSelection	
	int getCurrentChannel();
	RESULT selectChannel(int i);

		// iSubtitleOutput
	RESULT enableSubtitles(iSubtitleUser *user, SubtitleTrack &track);
	RESULT disableSubtitles();
	RESULT getSubtitleList(std::vector<SubtitleTrack> &sublist);
	RESULT getCachedSubtitle(SubtitleTrack &track);

		// iStreamedService
	RESULT streamed(ePtr<iStreamedService> &ptr);
	ePtr<iStreamBufferInfo> getBufferCharge();
	int setBufferSize(int size);

		// iAudioDelay
	int getAC3Delay();
	int getPCMDelay();
	void setAC3Delay(int);
	void setPCMDelay(int);

	struct audioStream
	{
		audiotype_t type;
		std::string language_code; /* iso-639, if available. */
		std::string codec; /* clear text codec description */
		audioStream()
			:type(atUnknown)
		{
		}
	};
	struct subtitleStream
	{
		subtype_t type;
		std::string language_code; /* iso-639, if available. */
		int id;
		subtitleStream()
		{
		}
	};
	struct sourceStream
	{
		audiotype_t audiotype;
		containertype_t containertype;
		bool is_video;
		bool is_streaming;
		sourceStream()
			:audiotype(atUnknown), containertype(ctNone), is_video(false), is_streaming(false)
		{
		}
	};

	struct bufferInfo
	{
		gint bufferPercent;
		gint avgInRate;
		gint avgOutRate;
		gint64 bufferingLeft;
		bufferInfo()
			:bufferPercent(0), avgInRate(0), avgOutRate(0), bufferingLeft(-1)
		{
		}
	};
	struct errorInfo
	{
		std::string error_message;
		std::string missing_codec;
	};

private:
	static int pcm_delay;
	static int ac3_delay;
	int m_currentAudioStream;
	int m_currentSubtitleStream;
	int m_cachedSubtitleStream;
	int selectAudioStream(int i);
	std::vector<audioStream> m_audioStreams;
	std::vector<subtitleStream> m_subtitleStreams;
	iSubtitleUser *m_subtitle_widget;

	int m_currentTrickRatio;

	friend class eServiceFactoryEPlayer3;
	eServiceReference m_ref;
	int m_buffer_size;

	bufferInfo m_bufferInfo;
	errorInfo m_errorInfo;
	std::string m_download_buffer_path;
	eServiceEPlayer3(eServiceReference ref);
	Signal2<void,iPlayableService*,int> m_event;
	enum
	{
		stIdle, stRunning, stStopped,
	};
	int m_state;

	Context_t * player;

	struct Message
	{
		Message()
			:type(-1)
		{}
		Message(int type)
			:type(type)
		{}
		int type;
	};
	eFixedMessagePump<Message> m_pump;
	static void eplayerCBsubtitleAvail(long int duration_ns, size_t len, char * buffer, void* user_data);

	struct subtitle_page_t
	{
		uint32_t start_ms;
		uint32_t end_ms;
		std::string text;

		subtitle_page_t(uint32_t start_ms_in, uint32_t end_ms_in, std::string text_in)
			: start_ms(start_ms_in), end_ms(end_ms_in), text(text_in)
		{
		}
	};

	typedef std::map<uint32_t, subtitle_page_t> subtitle_pages_map_t;
	typedef std::pair<uint32_t, subtitle_page_t> subtitle_pages_map_pair_t;
	subtitle_pages_map_t m_subtitle_pages;
	ePtr<eTimer> m_subtitle_sync_timer;
	
	ePtr<eTimer> m_streamingsrc_timeout;
	pts_t m_prev_decoder_time;
	int m_decoder_time_valid_state;

	void pushSubtitles();

	void sourceTimeout();
	sourceStream m_sourceinfo;

	RESULT seekToImpl(pts_t to);

	gint m_aspect, m_width, m_height, m_framerate, m_progressive;
	std::string m_useragent;
};

#endif
