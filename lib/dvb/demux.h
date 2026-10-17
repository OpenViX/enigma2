#ifndef __dvb_demux_h
#define __dvb_demux_h

#include <aio.h>
#include <atomic>
#include <vector>
#include <lib/base/thread.h>
#include <lib/dvb/idvb.h>
#include <lib/dvb/idemux.h>
#include <lib/dvb/pvrparse.h>
#include <lib/service/iservicescrambled.h>
#include "filepush.h"

class eDVBDemux: public iDVBDemux
{
	DECLARE_REF(eDVBDemux);
public:
	enum {
		evtFlush
	};
	eDVBDemux(int adapter, int demux);
	virtual ~eDVBDemux();

	RESULT setSourceFrontend(int fenum);
	int getSource() { return source; }
	RESULT setSourcePVR(int pvrnum);
	int getDvrId() { return m_dvr_id; }

	RESULT createSectionReader(eMainloop *context, ePtr<iDVBSectionReader> &reader);
	RESULT createPESReader(eMainloop *context, ePtr<iDVBPESReader> &reader);
	RESULT createScrambleMonitor(ePtr<iDVBScrambleMonitor> &monitor);
	RESULT createBitrateCounter(ePtr<iDVBBitrateCounter> &counter);
	RESULT createTSRecorder(ePtr<iDVBTSRecorder> &recorder, unsigned int packetsize = 188, bool streaming=false, bool sync_mode=false, bool is_streaming_output=false);
	RESULT getMPEGDecoder(ePtr<iTSMPEGDecoder> &reader, int index);
	RESULT getSTC(pts_t &pts, int num);
	RESULT getCADemuxID(uint8_t &id) { id = demux; return 0; }
	RESULT getCAAdapterID(uint8_t &id) { id = adapter; return 0; }
	RESULT flush();
	RESULT connectEvent(const sigc::slot<void(int)> &event, ePtr<eConnection> &conn);
	int openDVR(int flags);

	int getRefCount() { return ref; }
private:
	int adapter, demux, source;

	int m_dvr_busy;
	int m_dvr_id;
	int m_dvr_source_offset;
	friend class eDVBSectionReader;
	friend class eDVBPESReader;
	friend class eDVBScrambleMonitor;
	friend class eDVBBitrateCounter;
	friend class eDVBAudio;
	friend class eDVBVideo;
	friend class eDVBPCR;
	friend class eDVBTText;
	friend class eDVBTSRecorder;
	friend class eDVBCAService;
	friend class eTSMPEGDecoder;
	sigc::signal<void(int)> m_event;
	int openDemux(void);
};

class eDVBSectionReader: public iDVBSectionReader, public sigc::trackable
{
	DECLARE_REF(eDVBSectionReader);
	int fd;
	sigc::signal<void(const uint8_t*)> read;
	ePtr<eDVBDemux> demux;
	int active;
	int checkcrc;
	void data(int);
	ePtr<eSocketNotifier> notifier;
public:
	eDVBSectionReader(eDVBDemux *demux, eMainloop *context, RESULT &res);
	virtual ~eDVBSectionReader();
	RESULT setBufferSize(int size);
	RESULT start(const eDVBSectionFilterMask &mask);
	RESULT stop();
	RESULT connectRead(const sigc::slot<void(const uint8_t*)> &read, ePtr<eConnection> &conn);
};

class eDVBPESReader: public iDVBPESReader, public sigc::trackable
{
	DECLARE_REF(eDVBPESReader);
	int m_fd;
	sigc::signal<void(const uint8_t*, int)> m_read;
	ePtr<eDVBDemux> m_demux;
	int m_active;
	void data(int);
	ePtr<eSocketNotifier> m_notifier;
public:
	eDVBPESReader(eDVBDemux *demux, eMainloop *context, RESULT &res);
	virtual ~eDVBPESReader();
	RESULT setBufferSize(int size);
	RESULT start(int pid);
	RESULT stop();
	RESULT connectRead(const sigc::slot<void(const uint8_t*,int)> &read, ePtr<eConnection> &conn);
};

class eDVBScrambleMonitor: public iDVBScrambleMonitor, public sigc::trackable
{
	DECLARE_REF(eDVBScrambleMonitor);
	int m_fd, m_pid, m_state, m_idle;
	ePtr<eDVBDemux> m_demux;
	ePtr<eTimer> m_timer;
	void poll();
public:
	eDVBScrambleMonitor(eDVBDemux *demux);
	virtual ~eDVBScrambleMonitor();
	RESULT start(int pid);
	RESULT stop();
	int getState() { return m_state; }
};

/* The thread only reads one PID of a demux and adds up the bytes, nothing is written anywhere. It starts on a
 * PES tap, like the old bitrate tool. A tap that stays silent for TAP_FALLBACK_US is opened again, as the other
 * kind of tap if it never delivered a byte, so a stream that stalls or starts late is picked up again. It gives the
 * demux filter back after IDLE_US without a getKbps() call and getKbps() starts it again. */
class eDVBBitrateCounter: public iDVBBitrateCounter, public eThread
{
	DECLARE_REF(eDVBBitrateCounter);
	/* a demux filter buffer is only a few KB by default, far too small for a video PID */
	static const int BUFFER_SIZE = 1024 * 1024;
	static const int POLL_TIMEOUT_MS = 250;
	static const int64_t IDLE_US = 5000000;
	static const int64_t MIN_WINDOW_US = 500000;
	/* how long a tap may stay silent before it is opened again */
	static const int64_t TAP_FALLBACK_US = 2000000;
	/* the kbit/s of the bytes read are scaled down by this much to leave out the TS header overhead of a
	 * TS tap and the PES header overhead of a PES tap */
	static const int TS_PAYLOAD_PERCENT = 97;
	static const int PES_PAYLOAD_PERCENT = 99;

	ePtr<eDVBDemux> m_demux;
	int m_pid;		/* wanted PID, -1 = stopped (main thread only) */
	int m_fd;		/* demux filter: opened by the main thread, closed by the counting thread when it ends */
	int m_wake_fd;		/* eventfd, wakes the counting thread for stop() */
	std::vector<uint8_t> m_buf;
	std::atomic<uint64_t> m_bytes;
	std::atomic<uint64_t> m_overflows;
	std::atomic<int64_t> m_last_query_us;
	std::atomic<bool> m_exited;
	std::atomic<bool> m_ts_tap;	/* the filter is a TS tap, not a PES tap */
	/* current measuring window (main thread only) */
	uint64_t m_win_bytes;
	int64_t m_win_us;
	int m_kbps;

	int openFilter(int pid, bool ts);
	int startThread();
	void stopThread();
	/* override */ void thread();
public:
	eDVBBitrateCounter(eDVBDemux *demux);
	virtual ~eDVBBitrateCounter();
	RESULT start(int pid);
	RESULT stop();
	int getKbps();
};

class eDVBRecordFileThread: public eFilePushThreadRecorder
{
public:
	eDVBRecordFileThread(int packetsize, int bufferCount, int buffersize = -1, bool sync_mode = false);
	~eDVBRecordFileThread();
	void setTimingPID(int pid, iDVBTSRecorder::timing_pid_type pidtype, int streamtype);
	void startSaveMetaInformation(const std::string &filename);
	void stopSaveMetaInformation();
	int getLastPTS(pts_t &pts);
	int getFirstPTS(pts_t &pts);
	void setTargetFD(int fd) { m_fd_dest = fd; }
	void enableAccessPoints(bool enable) { m_ts_parser.enableAccessPoints(enable); }
	void setDescrambler(ePtr<iServiceScrambled> serviceDescrambler) { m_serviceDescrambler = serviceDescrambler; };
	void setDiscardOnTimeout(bool discard) { m_discard_on_timeout = discard; }
	// See iDVBTSRecorder::setMonitorFD. Only eDVBRecordScrambledThread's
	// writeData() actually feeds this; harmless (unused) elsewhere.
	void setMonitorFD(int fd) { m_monitor_fd = fd; }
	void setCountPID(int slot, int pid);
	int getCountPID(int slot) { return m_count_pid[slot].load(std::memory_order_relaxed); }
	uint64_t getCountedBytes(int slot) { return m_count_bytes[slot].load(std::memory_order_relaxed); }

	// Virtual: wait for first data (only ScrambledThread actually waits)
	virtual bool waitForFirstData(int /*timeout_ms*/) { return true; }

protected:
	int asyncWrite(int len);
	/* override */ int writeData(int len);
	/* override */ void flush();

	struct AsyncIO
	{
		struct aiocb aio;
		unsigned char* buffer;
		AsyncIO()
		{
			memset(&aio, 0, sizeof(aiocb));
			buffer = NULL;
		}
		int wait(const volatile int* stop_flag = nullptr, int* short_write_count = nullptr);
		int start(int fd, off_t offset, size_t nbytes, void* buffer);
		int poll(int* short_write_count = nullptr); // returns 1 if busy, 0 if ready, <0 on error return
		int cancel(int fd); // returns <0 on error, 0 cancelled, >0 bytes written?
	};
	eMPEGStreamParserTS m_ts_parser;
	off_t m_current_offset;
	int m_fd_dest;
	bool m_sync_mode;
	bool m_discard_on_timeout;
	typedef std::vector<AsyncIO> AsyncIOvector;
	unsigned char* m_allocated_buffer;
	AsyncIOvector m_aio;
	AsyncIOvector::iterator m_current_buffer;
	std::vector<int> m_buffer_use_histogram;
	ePtr<iServiceScrambled> m_serviceDescrambler;
	int m_aio_short_write_count = 0;
	int m_monitor_fd = -1;
	/* bytes of up to two PIDs, see iDVBTSRecorder::setCountPID: written by this thread, read by the main thread */
	std::atomic<int> m_count_pid[2];
	std::atomic<uint64_t> m_count_bytes[2];
	void countPIDs(const unsigned char *buf, int len);
};

class eDVBRecordStreamThread: public eDVBRecordFileThread
{
public:
	eDVBRecordStreamThread(int packetsize, int buffersize = -1, bool sync_mode = false);

protected:
	int writeData(int len);
	void flush();
};

// Note: flush() inherited from StreamThread (cancel behavior)
class eDVBRecordScrambledThread: public eDVBRecordStreamThread
{
public:
	eDVBRecordScrambledThread(int packetsize, int buffersize = -1, bool sync_mode = false, bool is_streaming = false);
	~eDVBRecordScrambledThread();

	// Wait for first data to be written (for decoder sync)
	// Returns true if data arrived, false on timeout
	/* override */ bool waitForFirstData(int timeout_ms);

	// Reset the first-data flag (call before start() if reusing)
	void resetFirstDataFlag();

protected:
	int writeData(int len);

private:
	unsigned char key[8];
	uint32_t* ks;

	// Synchronization for first data notification
	pthread_mutex_t m_data_ready_mutex;
	pthread_cond_t m_data_ready_cond;
	bool m_first_data_written;
	bool m_is_streaming;
};

class eDVBTSRecorder: public iDVBTSRecorder, public sigc::trackable
{
	DECLARE_REF(eDVBTSRecorder);
public:
	eDVBTSRecorder(eDVBDemux *demux, int packetsize, bool streaming, bool sync_mode = false, bool is_streaming_output = false);
	~eDVBTSRecorder();

	RESULT setBufferSize(int size);
	RESULT start();
	RESULT addPID(int pid);
	RESULT removePID(int pid);

	RESULT setTimingPID(int pid, timing_pid_type pidtype, int streamtype);

	RESULT setTargetFD(int fd);
	RESULT setTargetFilename(const std::string& filename);
	RESULT setBoundary(off_t max);
	RESULT enableAccessPoints(bool enable);

	RESULT stop();

	RESULT getCurrentPCR(pts_t &pcr);
	RESULT getFirstPTS(pts_t &pts);

	RESULT connectEvent(const sigc::slot<void(int)> &event, ePtr<eConnection> &conn);

	RESULT setDescrambler(ePtr<iServiceScrambled>);
	void setDiscardOnTimeout(bool discard);
	RESULT setMonitorFD(int fd) override;
	RESULT setCountPID(int slot, int pid) override;
	int getCountPID(int slot) override;
	uint64_t getCountedBytes(int slot) override;

	// Wait for first data to be written (for SoftDecoder sync)
	bool waitForFirstData(int timeout_ms);
	void setMinWrite(size_t size) override;
private:
	RESULT startPID(int pid);
	void stopPID(int pid);

	void filepushEvent(int event);

	std::map<int,int> m_pids;
	sigc::signal<void(int)> m_event;

	ePtr<eDVBDemux> m_demux;

	int m_running;
	int m_target_fd;
	int m_source_fd;
	eDVBRecordFileThread *m_thread;
	std::string m_target_filename;
	int m_packetsize;
};

#endif
