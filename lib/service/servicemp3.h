#ifndef __servicemp3_h
#define __servicemp3_h

#include <lib/base/message.h>
#include <lib/dvb/metaparser.h>
#include <lib/service/iservice.h>
#include <lib/dvb/pmt.h>
#include <lib/dvb/subtitle.h>
#include <lib/dvb/teletext.h>
#include <gst/gst.h>
/* for subtitles */
#include <lib/gui/esubtitle.h>
#include <atomic>

class eStaticServiceMP3Info;

class eServiceFactoryMP3: public iServiceHandler
{
	DECLARE_REF(eServiceFactoryMP3);
public:
	eServiceFactoryMP3();
	virtual ~eServiceFactoryMP3();
	enum { id = 0x1001 };

		// iServiceHandler
	RESULT play(const eServiceReference &, ePtr<iPlayableService> &ptr);
	RESULT record(const eServiceReference &, ePtr<iRecordableService> &ptr);
	RESULT list(const eServiceReference &, ePtr<iListableService> &ptr);
	RESULT info(const eServiceReference &, ePtr<iStaticServiceInformation> &ptr);
	RESULT offlineOperations(const eServiceReference &, ePtr<iServiceOfflineOperations> &ptr);
private:
	ePtr<eStaticServiceMP3Info> m_service_info;
};

class eStaticServiceMP3Info: public iStaticServiceInformation
{
	DECLARE_REF(eStaticServiceMP3Info);
	friend class eServiceFactoryMP3;
	eStaticServiceMP3Info();
	eDVBMetaParser m_parser;
public:
	RESULT getName(const eServiceReference &ref, std::string &name);
	int getLength(const eServiceReference &ref);
	int getInfo(const eServiceReference &ref, int w);
	int isPlayable(const eServiceReference &ref, const eServiceReference &ignore, bool simulate) { return 1; }
	long long getFileSize(const eServiceReference &ref);
	RESULT getEvent(const eServiceReference &ref, ePtr<eServiceEvent> &ptr, time_t start_time);
};

class eStreamBufferInfo: public iStreamBufferInfo
{
	DECLARE_REF(eStreamBufferInfo);
	int bufferPercentage;
	int inputRate;
	int outputRate;
	int bufferSpace;
	int bufferSize;

public:
	eStreamBufferInfo(int percentage, int inputrate, int outputrate, int space, int size);

	int getBufferPercentage() const;
	int getAverageInputRate() const;
	int getAverageOutputRate() const;
	int getBufferSpace() const;
	int getBufferSize() const;
};

class eServiceMP3InfoContainer: public iServiceInfoContainer
{
	DECLARE_REF(eServiceMP3InfoContainer);

	double doubleValue;
	GstBuffer *bufferValue;

	unsigned char *bufferData;
	unsigned int bufferSize;
	GstMapInfo map;

public:
	eServiceMP3InfoContainer();
	~eServiceMP3InfoContainer();

	double getDouble(unsigned int index) const;
	unsigned char *getBuffer(unsigned int &size) const;
	void setDouble(double value);
	void setBuffer(GstBuffer *buffer);
};

class GstMessageContainer: public iObject
{
	DECLARE_REF(GstMessageContainer);
	GstMessage *messagePointer;
	GstPad *messagePad;
	GstBuffer *messageBuffer;
	int messageType;
	int messageGeneration;

public:
	GstMessageContainer(int type, GstMessage *msg, GstPad *pad, GstBuffer *buffer, int generation = 0)
	{
		messagePointer = msg;
		messagePad = pad;
		messageBuffer = buffer;
		messageType = type;
		messageGeneration = generation;
	}
	~GstMessageContainer()
	{
		if (messagePointer) gst_message_unref(messagePointer);
		if (messagePad) gst_object_unref(messagePad);
		if (messageBuffer) gst_buffer_unref(messageBuffer);
	}
	int getType() { return messageType; }
	/* Only meaningful for type 2 (subtitle buffer) messages - see
	 * eServiceMP3::m_subtitle_generation. */
	int getGeneration() { return messageGeneration; }
	operator GstMessage *() { return messagePointer; }
	operator GstPad *() { return messagePad; }
	operator GstBuffer *() { return messageBuffer; }
};

typedef struct _GstElement GstElement;

typedef enum { atUnknown, atMPEG, atMP3, atAC3, atDTS, atAACHE, atPCM, atOGG, atFLAC, atWMA, atDRA, atEAC3, atDTSHD, atAAC } audiotype_t;
typedef enum { stUnknown, stPlainText, stSSA, stASS, stSRT, stVOB, stPGS, stDVB } subtype_t;
typedef enum { ctNone, ctMPEGTS, ctMPEGPS, ctMKV, ctAVI, ctMP4, ctVCD, ctCDA, ctASF, ctOGG, ctWEBM, ctDRA} containertype_t;

class eServiceMP3: public iPlayableService, public iPauseableService,
	public iServiceInformation, public iSeekableService, public iAudioTrackSelection, public iAudioChannelSelection,
	public iSubtitleOutput, public iStreamedService, public iAudioDelay, public sigc::trackable, public iCueSheet
{
	DECLARE_REF(eServiceMP3);
public:
	virtual ~eServiceMP3();

	void setCacheEntry(bool isAudio, int pid);
		// iPlayableService
	RESULT connectEvent(const sigc::slot<void(iPlayableService*,int)> &event, ePtr<eConnection> &connection);
	RESULT start();
	RESULT stop();

	RESULT pause(ePtr<iPauseableService> &ptr);
	RESULT setSlowMotion(int ratio);
	RESULT setFastForward(int ratio);

	RESULT seek(ePtr<iSeekableService> &ptr);
	RESULT audioTracks(ePtr<iAudioTrackSelection> &ptr);
	RESULT audioChannel(ePtr<iAudioChannelSelection> &ptr);
	RESULT subtitle(ePtr<iSubtitleOutput> &ptr);
	RESULT audioDelay(ePtr<iAudioDelay> &ptr);
	RESULT cueSheet(ePtr<iCueSheet> &ptr);

		// not implemented (yet)
	RESULT setTarget(int target, bool noaudio = false) { return -1; }
	RESULT frontendInfo(ePtr<iFrontendInformation> &ptr) { ptr = 0; return -1; }
	RESULT subServices(ePtr<iSubserviceList> &ptr) { ptr = 0; return -1; }
	RESULT timeshift(ePtr<iTimeshiftService> &ptr) { ptr = 0; return -1; }
	RESULT tap(ePtr<iTapService> &ptr) { ptr = nullptr; return -1; };
//	RESULT cueSheet(ePtr<iCueSheet> &ptr) { ptr = 0; return -1; }

		// iCueSheet
	PyObject *getCutList();
	void setCutList(SWIG_PYOBJECT(ePyObject));
	void setCutListEnable(int enable);

	RESULT rdsDecoder(ePtr<iRdsDecoder> &ptr) { ptr = 0; return -1; }
	RESULT keys(ePtr<iServiceKeys> &ptr) { ptr = 0; return -1; }
	RESULT stream(ePtr<iStreamableService> &ptr) { ptr = 0; return -1; }

	void setQpipMode(bool value, bool audio) { }

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
	RESULT getEvent(ePtr<eServiceEvent> &evt, int nownext);
	int getInfo(int w);
	std::string getInfoString(int w);
	ePtr<iServiceInfoContainer> getInfoObject(int w);

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
		GstPad* pad;
		audiotype_t type;
		std::string language_code; /* iso-639, if available. */
		std::string codec; /* clear text codec description */
		int channels; /* selected-track channels; normally caps, refined from DTS-HD XLL when available. */
		audioStream()
			:pad(0), type(atUnknown), channels(0)
		{
		}

		bool operator==(const audioStream& rhs) const { return type == rhs.type && language_code == rhs.language_code && codec == rhs.codec && channels == rhs.channels; }

		bool operator!=(const audioStream& rhs) const { return !(*this == rhs); }
	};
	struct subtitleStream
	{
		GstPad* pad;
		subtype_t type;
		std::string language_code; /* iso-639, if available. */
		subtitleStream()
			:pad(0) { }
		bool operator==(const subtitleStream& rhs) const { return type == rhs.type && language_code == rhs.language_code; }

		bool operator!=(const subtitleStream& rhs) const { return !(*this == rhs); }
	};
	struct sourceStream
	{
		audiotype_t audiotype;
		containertype_t containertype;
		bool is_video;
		bool is_audio;
		bool is_streaming;
		bool is_hls;
		sourceStream()
			:audiotype(atUnknown), containertype(ctNone), is_video(FALSE), is_audio(FALSE), is_streaming(FALSE), is_hls(FALSE)
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

protected:
	ePtr<eTimer> m_nownext_timer;
	ePtr<eServiceEvent> m_event_now, m_event_next;
	void updateEpgCacheNowNext();

		/* cuesheet */
	struct cueEntry
	{
		pts_t where;
		unsigned int what;

		bool operator < (const struct cueEntry &o) const
		{
			return where < o.where;
		}
		cueEntry(const pts_t &where, unsigned int what) :
			where(where), what(what)
		{
		}
	};

	std::multiset<cueEntry> m_cue_entries;
	int m_cuesheet_changed, m_cutlist_enabled;
	void loadCuesheet();
	void saveCuesheet();
private:
	static int pcm_delay;
	static int ac3_delay;
	int m_currentAudioStream;
	int m_currentSubtitleStream;
	int m_cachedSubtitleStream;
	int selectAudioStream(int i, bool skipAudioFix=false);
	std::vector<audioStream> m_audioStreams;
	std::vector<subtitleStream> m_subtitleStreams;
	iSubtitleUser *m_subtitle_widget;
	gdouble m_currentTrickRatio;
	friend class eServiceFactoryMP3;
	eServiceReference m_ref;
	std::string m_prov;
	int m_buffer_size;
	int m_ignore_buffering_messages;
	bool m_is_live;
	bool m_use_prefillbuffer;
	bool m_paused;
	bool m_clear_buffers;
	bool m_initial_start;
	bool m_send_ev_start;
	bool m_seek_paused;
	bool m_autoturnon;
	/* cuesheet load check */
	bool m_cuesheet_loaded;
	/* servicemMP3 chapter TOC support CVR */
	bool m_use_chapter_entries;
	/* last used seek position gst-1 only */
	gint64 m_last_seek_pos;

	/* An "&e2startoffset=<pts>" URL parameter (see the constructor) - the
	 * position to resume from once the pipeline is actually able to seek.
	 * -1 once there is nothing left to apply. */
	pts_t m_pending_start_position;
	/* True while evGstreamerStart/evStart are being held back because
	 * m_pending_start_position was still pending when start() requested
	 * PLAYING - see fireDeferredStartEvents()/tryApplyPendingStartOffset(). */
	bool m_start_events_deferred;
	void fireDeferredStartEvents();
	void tryApplyPendingStartOffset();
	/*
	 * Switches playbin's text stream to m_currentSubtitleStream, then calls
	 * flushNearCurrentPosition() - see its own comment for why an actual
	 * (near-)flushing seek, not just the property set, is what's needed to
	 * make the new track show its current cue immediately rather than
	 * waiting for its own next one. Must only be called while the pipeline
	 * is settled in PLAYING (a flushing seek against an unsettled pipeline
	 * risks the deadlock fixed independently upstream in
	 * openatv/enigma2#3913, "servicemp3: fix audio track switch stall and
	 * subtitle switch deadlock") - see enableSubtitles(), which defers the
	 * call via m_subtitle_switch_deferred otherwise. Replaces the previous
	 * approach of tearing down and restarting the whole pipeline on every
	 * subtitle switch, which paid for the same re-sync with a visible
	 * playback stall.
	 */
	void applySubtitleStreamSwitch();
	/* current-text switch requested while the pipeline was not settled in
	 * PLAYING; applied on the next PAUSED->PLAYING transition - see
	 * enableSubtitles()/applySubtitleStreamSwitch() and
	 * selectAudioStream()'s m_audio_switch_deferred, which defers for the
	 * same reason. */
	bool m_subtitle_switch_deferred;
	/*
	 * Whether applySubtitleStreamSwitch() should flush at all - set by
	 * enableSubtitles() right before it, and (for a deferred switch) read
	 * back out by it later once gstBusCall() actually runs it, so the
	 * decision survives that gap. True only when an already-active
	 * subtitle track is being replaced by a different one - not for the
	 * very first enable of a session, automatic or manual, since there is
	 * no old track's stale data to clear yet and, more importantly,
	 * nothing yet displayed whose timing a flush could disturb.
	 *
	 * flushNearCurrentPosition()'s accurate flushing seek is confirmed on
	 * device to introduce a small but *permanent* subtitle timing offset
	 * for the rest of the session (independent of any actual track switch
	 * happening later) - almost certainly some interaction between
	 * GST_SEEK_FLAG_ACCURATE and this hardware's decoder-time reporting,
	 * which subtitle sync (pushSubtitles()) compares raw subtitle-buffer
	 * PTS against. A genuine track-to-track switch still needs the flush -
	 * see flushNearCurrentPosition()'s own comment for why a passive
	 * property switch alone doesn't make the new track's current cue show
	 * up - so this only narrows *when* it runs, rather than removing it
	 * outright and reintroducing that older bug.
	 */
	bool m_subtitle_switch_needs_flush;
	/* Bumped on every subtitle track switch/disable. A subtitle buffer
	 * captured by gstCBsubtitleAvail() under one generation, but not yet
	 * processed by gstPoll() (it hops through m_pump onto the main thread)
	 * when a switch to a new generation lands, still carries the old
	 * track's raw bytes - without this it would get parsed as though it
	 * were the new track's data. Written on the main thread, read on the
	 * GStreamer thread that captures buffers. */
	std::atomic<int> m_subtitle_generation;
	/* Audio stream index deferred until the pipeline is settled in PLAYING -
	 * see selectAudioStream()'s own comment for why setting "current-audio"
	 * against an unsettled pipeline is unsafe. -1 when nothing is pending. */
	int m_audio_switch_deferred;

	/*
	 * An ordinary (non-hardware-passthrough) audio track switch runs an
	 * explicit PAUSE -> accurate flushing seek to the current position ->
	 * PLAY sequence instead of clearBuffers()'s usual flush-while-PLAYING:
	 * seeking while genuinely PAUSED lets the pipeline preroll the exact
	 * target frame before anything is displayed again, so there is nothing
	 * for the viewer to see change at all - not even the brief decode
	 * stutter a same-position accurate seek issued while PLAYING can still
	 * produce - which is the whole point here, video stutter being exactly
	 * what this was asked to minimize.
	 *
	 * Driven entirely off gstBusCall()'s existing GST_STATE_CHANGE_
	 * PLAYING_TO_PAUSED and GST_MESSAGE_ASYNC_DONE handling rather than any
	 * blocking gst_element_get_state() wait between steps - deliberately,
	 * same reasoning as tryApplyPendingStartOffset()'s own comment: an
	 * explicit blocking PAUSE -> wait -> PLAY was tried elsewhere in this
	 * class before and confirmed on device to hang the whole UI (the "Main
	 * thread is busy" watchdog firing) for several seconds. Each step here
	 * instead just requests the next thing and returns; the following step
	 * runs whenever its bus message naturally arrives.
	 */
	enum { AudioSwitchFlushNone, AudioSwitchFlushWaitPaused, AudioSwitchFlushWaitSeek } m_audio_switch_flush_phase;
	/* Whether to resume PLAYING once the flush completes. False when the
	 * pipeline was already paused (by the user) when the switch began -
	 * GStreamer then won't fire a new PLAYING_TO_PAUSED transition for a
	 * state it's already in (gstBusCall() filters out old_state==new_state),
	 * so beginAudioSwitchPauseFlush() skips straight to the seek in that
	 * case - and resuming PLAYING afterward would then incorrectly override
	 * the user's own pause. */
	bool m_audio_switch_flush_resume;
	/* Set right before the ASYNC_DONE handler's own gst_element_set_state()
	 * call resumes PLAYING, and consumed by gstBusCall()'s GST_STATE_CHANGE_
	 * PAUSED_TO_PLAYING handling: that handler unconditionally re-applies
	 * m_currentAudioStream on every PLAYING transition (to recover from a
	 * *real* pause/resume or startup), which would otherwise re-enter
	 * beginAudioSwitchPauseFlush() right as it resumes from its own seek -
	 * current-audio is already exactly right at that point (that's what
	 * just got paused and seeked for), so re-running the whole sequence
	 * would just repeat it forever. */
	bool m_audio_switch_flush_resuming;
	void beginAudioSwitchPauseFlush();
	/* The seek step of the sequence above, run once the pipeline is
	 * confirmed PAUSED (or was already paused - see m_audio_switch_flush_resume).
	 * Safe to call gst_element_seek() synchronously here, unlike
	 * flushNearCurrentPosition()'s subtitle-switch equivalent: that one's
	 * confirmed-on-device deadlock risk is specifically a thread blocked in
	 * a sink's clock wait, which only happens in PLAYING (a running clock),
	 * never in PAUSED. */
	void doAudioSwitchFlushSeek();
	bufferInfo m_bufferInfo;
	errorInfo m_errorInfo;
	std::string m_download_buffer_path;
	eServiceMP3(eServiceReference ref);
	sigc::signal<void(iPlayableService*,int)> m_event;
	enum
	{
		stIdle, stRunning, stStopped,
	};
	int m_state;
	GstElement *m_gst_playbin, *audioSink, *videoSink;
	GstTagList *m_stream_tags;
	bool m_coverart;
	std::list<eDVBSubtitlePage> m_dvb_subtitle_pages;

	eFixedMessagePump<ePtr<GstMessageContainer> > m_pump;

	audiotype_t gstCheckAudioPad(GstStructure* structure);
	void gstBusCall(GstMessage *msg);
	void handleMessage(GstMessage *msg);
	static GstBusSyncReply gstBusSyncHandler(GstBus *bus, GstMessage *message, gpointer user_data);
	static void gstTextpadHasCAPS(GstPad *pad, GParamSpec * unused, gpointer user_data);
	void gstTextpadHasCAPS_synced(GstPad *pad);
	static void gstCBsubtitleAvail(GstElement *element, GstBuffer *buffer, gpointer user_data);
	GstPad* gstCreateSubtitleSink(eServiceMP3* _this, subtype_t type);
	void gstPoll(ePtr<GstMessageContainer> const &);
	static void playbinNotifySource(GObject *object, GParamSpec *unused, gpointer user_data);
/* TOC processing CVR */
	void HandleTocEntry(GstMessage *msg);
	static gint match_sinktype(const GValue *velement, const gchar *type);
	static void handleElementAdded(GstBin *bin, GstElement *element, gpointer user_data);
	void disconnectAsyncSignalHandlers();

	struct subtitle_page_t
	{
		uint32_t start_ms;
		uint32_t end_ms;
		std::string text;

		subtitle_page_t(uint32_t start_ms_in, uint32_t end_ms_in, const std::string& text_in)
			: start_ms(start_ms_in), end_ms(end_ms_in), text(text_in)
		{
		}
	};

	typedef std::map<uint32_t, subtitle_page_t> subtitle_pages_map_t;
	typedef std::pair<uint32_t, subtitle_page_t> subtitle_pages_map_pair_t;
	subtitle_pages_map_t m_subtitle_pages;
	ePtr<eTimer> m_subtitle_sync_timer;
	ePtr<eTimer> m_dvb_subtitle_sync_timer;
	ePtr<eDVBSubtitleParser> m_dvb_subtitle_parser;
	ePtr<eConnection> m_new_dvb_subtitle_page_connection;
	void newDVBSubtitlePage(const eDVBSubtitlePage &p);

	pts_t m_prev_decoder_time;
	int m_decoder_time_valid_state;

	RESULT getRawPlayPosition(pts_t &pts);
	bool m_position_baseline_valid;
	bool m_position_correction_enabled;
	pts_t m_position_baseline;
	/* Used by getPlayPosition() to avoid capturing m_position_baseline from
	 * a transient/unrepresentative raw reading seen before the decoder
	 * clock has actually locked onto real playback - especially likely on
	 * network streams, which take longer to buffer/preroll than local
	 * files, so there is more opportunity for an early, spurious reading to
	 * be mistaken for the real starting offset.
	 *
	 * Gated on wall-clock time (g_get_monotonic_time(), microseconds), not
	 * a fixed number of getPlayPosition() calls: getPlayPosition() is
	 * polled independently by several UI timers (position display,
	 * subtitle renderer, timeshift, ...) all sharing this same state, so a
	 * call-count gate's real-time cost is unpredictable - it can span much
	 * longer than intended depending on how those pollers happen to
	 * interleave, or how coarsely the underlying decoder-time/position
	 * query updates. Since every one of those seconds is then baked in as
	 * a permanent baseline offset (position display appearing to "start"
	 * several seconds in), the wait itself needs a hard, small, real-time
	 * bound instead.
	 *
	 * The candidate these track can be seeded from two places: getPlayPosition()
	 * itself on its own first call, or earlier, from gstBusCall()'s
	 * GST_STATE_CHANGE_PAUSED_TO_PLAYING handling as soon as the pipeline
	 * first reaches PLAYING - whichever happens first. The latter matters
	 * because getPlayPosition() may not be called by anything until well
	 * after real playback has already started (a network/HLS source can sit
	 * PAUSED filling its prefill buffer for a few real seconds first), and
	 * whatever raw reading its first caller happens to see would otherwise
	 * be mistaken for "time zero". */
	pts_t m_position_baseline_provisional;
	gint64 m_position_baseline_first_seen_us;

	void pushDVBSubtitles();
	void pushSubtitles();
	void pullSubtitle(GstBuffer *buffer);
	void sourceTimeout();
	void clearBuffers(bool force=false);
	ePtr<eTimer> m_passthrough_fix_timer;
	void forceAudioReset();
	sourceStream m_sourceinfo;
	gulong m_subs_to_pull_handler_id;

	/* accurate=false (the default, used by every real user seek/trickplay
	 * path) seeks with GST_SEEK_FLAG_KEY_UNIT - fast, snaps to the nearest
	 * keyframe, right when the goal is to get somewhere quickly.
	 * accurate=true (used by clearBuffers(), for an audio track switch)
	 * seeks with GST_SEEK_FLAG_ACCURATE instead - see clearBuffers()'s own
	 * comment for why. flushNearCurrentPosition() below needs the same
	 * accurate seek for a subtitle track switch, but - unlike clearBuffers()
	 * - can't safely call through here: see its own comment for why it
	 * builds and dispatches the gst_element_seek() call itself instead. */
	RESULT seekToImpl(pts_t to, bool accurate = false);
	/*
	 * A flushing seek to (current position - ~1ms) instead of an outright
	 * reposition, dispatched to a GStreamer pool thread rather than called
	 * synchronously. This is what actually makes a plain "current-text"
	 * property switch (applySubtitleStreamSwitch()) take visible effect
	 * immediately, instead of waiting for a sparse embedded subtitle track's
	 * (SRT/ASS/PGS) own next cue, possibly minutes away: a real seek is what
	 * forces the demuxer to re-read and re-emit data at the current position
	 * on every pad, including whichever one was just switched to - a
	 * passive property switch alone never does that on its own account.
	 *
	 * Seeks with GST_SEEK_FLAG_KEY_UNIT, same as seekToImpl()'s usual real
	 * user seek - deliberately NOT GST_SEEK_FLAG_ACCURATE, despite that
	 * being exactly what doAudioSwitchFlushSeek() uses for the equivalent
	 * audio-switch flush to avoid a keyframe-snap video jump: confirmed on
	 * device that ACCURATE here left subtitle timing permanently skewed
	 * for the rest of the session after any actual subtitle track switch -
	 * almost certainly this hardware's decoder-time reporting disagreeing
	 * with itself across an accurate seek in some way pushSubtitles()'s
	 * raw-PTS comparison then inherits permanently. Avoiding a video jump
	 * was never a requirement for a subtitle switch specifically - only
	 * avoiding the hang/freeze it used to cause, which this still does
	 * regardless of which seek flag is used - so there is nothing here
	 * KEY_UNIT's usual keyframe snap is worth trading that correctness
	 * away for.
	 *
	 * Unlike clearBuffers()'s equivalent audio-switch flush, this cannot
	 * call gst_element_seek() directly on the calling (E2 main) thread:
	 * confirmed on device to block for several seconds - a hard UI freeze,
	 * since applySubtitleStreamSwitch() runs synchronously from a
	 * key-press handler - when the seek races the text selector's own
	 * active-pad switch issued moments earlier (a thread blocked in the
	 * subtitle sink's clock wait holds a lock the seek's FLUSH_START also
	 * needs). See doDeferredFlush() in the .cpp, which does the actual
	 * gst_element_seek() call from a GStreamer pool thread instead.
	 *
	 * Returns false only if there's no playbin or no valid current position
	 * to flush at - not confirmation that the seek has landed, or even that
	 * it started, both of which happen later, off-thread. Skips itself for
	 * a live source, same as clearBuffers() and for the same reason
	 * (nothing to seek back to).
	 */
	bool flushNearCurrentPosition();

	gint m_aspect, m_width, m_height, m_framerate, m_progressive, m_gamma;
	int m_hdr_type;                  // 0=SDR 1=HDR10 2=HLG 3=HDR

#ifdef HAS_SOFTWARE_HDR_DETECTION
	void updateHDRFromVideoPad();

	/* GStreamer buffer probe for direct HEVC bitstream HDR classification.
	 * Runs in the GStreamer streaming thread; data is consumed by a periodic
	 * timer in the main thread via a mutex-protected shared buffer. */
	GMutex          m_hdr_probe_mutex;
	std::vector<uint8_t> m_hdr_probe_es;      /* shared: streaming thread appends, main thread swaps out (O(1)) */
	std::vector<uint8_t> m_hdr_probe_snap;    /* main thread only: accumulated bitstream for classify() */
	size_t          m_hdr_probe_last_classify;
	size_t          m_hdr_probe_first_sps_at;
	gulong          m_hdr_probe_id;
	GstPad         *m_hdr_probe_pad;
	gint            m_hdr_probe_active; /* atomic: 0=inactive, 1=active; use g_atomic_int_* */
	ePtr<eTimer>    m_hdr_probe_timer;
	void startHDRProbe();
	void stopHDRProbe();
	void checkHDRProbe();
	static GstPadProbeReturn hdrProbeCallback(GstPad*, GstPadProbeInfo*, gpointer);
#endif /* HAS_SOFTWARE_HDR_DETECTION */
	std::string m_useragent;
	std::string m_extra_headers;
	RESULT trickSeek(gdouble ratio);
	ePtr<iTSMPEGDecoder> m_decoder; // for showSinglePic when radio
};

#endif
