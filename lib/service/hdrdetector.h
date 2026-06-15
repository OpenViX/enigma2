#ifndef HDRDETECTOR_H
#define HDRDETECTOR_H

#include <lib/base/object.h>
#include <lib/base/ebase.h>
#include <lib/dvb/idvb.h>
#include <vector>

class iDVBDemux;
class iDVBTSRecorder;

/* Live DVB HDR detector.
 *
 * Uses createTSRecorder (the same kernel path as the streamserver) to capture
 * raw TS packets for the video PID, then parses them in-process — identical
 * algorithm to the Python hdrdetect library.
 *
 * This works on all hardware because DMX_OUT_TS_TAP (used internally by the
 * TS recorder) taps the incoming multiplex before it routes to the hardware
 * decoder, unlike DMX_PES_OTHER / DMX_OUT_TAP which silently delivers no data
 * for video PIDs on most STBs.
 */
class eHDRStreamDetector : public iObject, public sigc::trackable
{
	DECLARE_REF(eHDRStreamDetector);
	ePtr<iDVBTSRecorder>  m_recorder;
	ePtr<eSocketNotifier> m_notifier;
	ePtr<eTimer>          m_timeout;
	int m_svfd[2];   /* socketpair: [0]=we read, [1]=recorder writes */
	int m_vpid;
	std::vector<uint8_t> m_es;
	size_t m_last_classify;
	size_t m_first_sps_at;
	int    m_result;
	bool   m_done;
	void tsData(int fd);
	void onTimeout();
	void finish(int result);
public:
	eHDRStreamDetector();
	virtual ~eHDRStreamDetector();
	int  start(iDVBDemux *demux, int pid);
	void stop();
	int  getResult() const { return m_result; }
	sigc::signal<void(int)> resultChanged;
};

#endif
