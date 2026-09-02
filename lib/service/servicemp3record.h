#ifndef __servicemp3record_h
#define __servicemp3record_h

#include <lib/service/iservice.h>
#include <lib/service/servicemp3.h>
#include <lib/dvb/idvb.h>
#include <lib/dvb/pvrparse.h>
#include <gst/gst.h>
#include <vector>

class eServiceMP3Record:
	public iRecordableService,
	public sigc::trackable
{
	DECLARE_REF(eServiceMP3Record);
public:
	RESULT connectEvent(const sigc::slot<void(iRecordableService*,int)> &event, ePtr<eConnection> &connection);
	RESULT prepare(const char *filename, time_t begTime, time_t endTime, int eit_event_id, const char *name, const char *descr, const char *tags, bool descramble, bool recordecm, int packetsize);
	RESULT prepareStreaming(bool descramble, bool includeecm);
	RESULT start(bool simulate=false);
	RESULT stop();
	RESULT stream(ePtr<iStreamableService> &ptr);
	RESULT getError(int &error) { error = m_error; return 0; };
	RESULT frontendInfo(ePtr<iFrontendInformation> &ptr);
	RESULT subServices(ePtr<iSubserviceList> &ptr);
	RESULT getFilenameExtension(std::string &ext) { ext = ".ts"; return 0; };

private:
	enum { stateIdle, statePrepared, stateRecording };
	GstElement* m_recording_pipeline;
	GstElement* m_source;
	bool m_simulate;
	int m_state;
	int m_error;
	std::string m_filename;
	eServiceReference m_ref;
	ePtr<eConnection> m_con_record_event;
	std::string m_useragent;
	std::string m_extra_headers;
	eFixedMessagePump<ePtr<GstMessageContainer> > m_pump;

	friend class eServiceFactoryMP3;
	eServiceMP3Record(const eServiceReference &ref);
	~eServiceMP3Record();

	int doRecord();
	int doPrepare();
	void gstPoll(ePtr<GstMessageContainer> const &);
	void sourceTimeout();
	void restartRecordingFromEos();
	void disconnectAsyncSignalHandlers();
	void gstBusCall(GstMessage *msg);
	void handleMessage(GstMessage *msg);
	static GstBusSyncReply gstBusSyncHandler(GstBus *bus, GstMessage *message, gpointer user_data);
	static void handleUridecNotifySource(GObject *object, GParamSpec *unused, gpointer user_data);
	static void handlePadAdded(GstElement *element, GstPad *pad, gpointer user_data);
	static gboolean handleAutoPlugCont(GstElement *bin, GstPad *pad, GstCaps *caps, gpointer user_data);
	static GstPadProbeReturn handleRecordProbe(GstPad *pad, GstPadProbeInfo *info, gpointer user_data);

	/* .ap/.sc generation. eServiceMP3Record's pipeline is a raw GStreamer
	 * passthrough (uridecodebin -> filesink, see doPrepare()) with no PMT
	 * handler of its own, unlike native DVB recording - the video PID has to
	 * be discovered by scanning the stream's own PAT/PMT before
	 * eMPEGStreamParserTS (the same class native recording uses, see
	 * lib/dvb/demux.cpp's eDVBRecordFileThread) can be told what to track.
	 * Once found, all recorded bytes are handed to it via parseData(), which
	 * does its own internal partial-packet buffering - m_apsc_buf below is
	 * only needed for the PAT/PMT discovery phase, not after. */
	void processApScData(const unsigned char *data, unsigned int len);
	void findVideoPid();
	std::vector<unsigned char> m_apsc_buf;  /* discovery-phase only, freed once m_apsc_video_pid_found */
	off_t m_apsc_base_pos;    /* absolute file offset of m_apsc_buf[0] */
	unsigned int m_apsc_next_pkt;  /* packets already checked for PAT/PMT, in m_apsc_buf */
	int m_apsc_pmt_pid;
	bool m_apsc_video_pid_found;
	bool m_apsc_sync_checked;  /* true once the early "does this even look like TS" check has run */
	bool m_apsc_disabled;   /* not MPEG-TS at all, PAT with no program, or PMT with no supported video stream */
	off_t m_record_offset;  /* running byte offset of everything written to m_filename so far */
	/* Pointer, not a plain member: restartRecordingFromEos() reuses this same
	 * eServiceMP3Record for a new segment file, and eMPEGStreamParserTS's own
	 * internal state (locked pid/streamtype, partial-packet buffer, PTS
	 * tracking) needs a genuinely clean instance per recording, not just the
	 * m_apsc_* bookkeeping above reset in place - see doPrepare(). */
	eMPEGStreamParserTS *m_ts_parser;
	/* Pad/probe-id of the handleRecordProbe() buffer probe added in
	 * handlePadAdded() - kept so disconnectAsyncSignalHandlers() can
	 * synchronously detach it in stop(), see that method's comment. */
	GstPad *m_record_probe_pad;
	gulong m_record_probe_id;

			/* events */
	sigc::signal<void(iRecordableService*,int)> m_event;
};

#endif
