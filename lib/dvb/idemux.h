#ifndef __dvb_idemux_h
#define __dvb_idemux_h

#include <lib/dvb/idvb.h>
#include <lib/service/iservicescrambled.h>

class iDVBSectionReader: public iObject
{
public:
	virtual RESULT setBufferSize(int size)=0;
	virtual RESULT start(const eDVBSectionFilterMask &mask)=0;
	virtual RESULT stop()=0;
	virtual RESULT connectRead(const sigc::slot<void(const uint8_t*)> &read, ePtr<eConnection> &conn)=0;
	virtual ~iDVBSectionReader() { };
};

class iDVBPESReader: public iObject
{
public:
	virtual RESULT setBufferSize(int size)=0;
	virtual RESULT start(int pid)=0;
	virtual RESULT stop()=0;
	virtual RESULT connectRead(const sigc::slot<void(const uint8_t*,int)> &read, ePtr<eConnection> &conn)=0;
	virtual ~iDVBPESReader() { };
};

	/* records a given set of pids into a file descriptor. */
	/* the FD must not be modified between start() and stop() ! */
class iDVBTSRecorder: public iObject
{
public:
	virtual RESULT setBufferSize(int size) = 0;
	virtual RESULT start() = 0;
	virtual RESULT addPID(int pid) = 0;
	virtual RESULT removePID(int pid) = 0;

	enum timing_pid_type { none = -1, video_pid, audio_pid };
	virtual RESULT setTimingPID(int pid, timing_pid_type pidtype, int streamtype) = 0;

	virtual RESULT setTargetFD(int fd) = 0;
		/* for saving additional meta data. */
	virtual RESULT setTargetFilename(const std::string& filename) = 0;
	virtual RESULT setBoundary(off_t max) = 0;
	virtual RESULT enableAccessPoints(bool enable) = 0;

	virtual RESULT stop() = 0;

	virtual RESULT getCurrentPCR(pts_t &pcr) = 0;
	virtual RESULT getFirstPTS(pts_t &pts) = 0;

	virtual RESULT setDescrambler(ePtr<iServiceScrambled>) = 0;

	// Discard data on sync write timeout instead of retrying.
	// Use for live soft decoding where stale data is worthless and
	virtual void setDiscardOnTimeout(bool discard) = 0;

	// Wait for first data to be written (for SoftDecoder sync)
	virtual bool waitForFirstData(int timeout_ms) = 0;

	// Set write accumulation threshold (0 = continuous writing)
	virtual void setMinWrite(size_t size) = 0;

	/* Attach (or, with fd=-1, detach) a passive monitor fd. When set, a
	 * best-effort, non-blocking copy of the data actually written to the
	 * target fd - i.e. already descrambled, when a descrambler is set -
	 * is also written to the monitor fd. Writes are silently dropped on
	 * backpressure or error; this must never be allowed to block or
	 * otherwise affect the primary recording/decode path. The caller is
	 * responsible for making the fd non-blocking and for closing it -
	 * detach with fd=-1 before closing. */
	virtual RESULT setMonitorFD(int fd) = 0;

	enum {
		eventWriteError,
				/* a write error has occurred. data won't get lost if fd is writable after return. */
				/* you MUST respond with either stop() or fixing the problems, else you get the error */
				/* again. */
		eventReachedBoundary,
				/* the programmed boundary was reached. you might set a new target fd. you can close the */
				/* old one. */
		eventStreamCorrupt
	};
	virtual RESULT connectEvent(const sigc::slot<void(int)> &event, ePtr<eConnection> &conn)=0;
};

#endif
