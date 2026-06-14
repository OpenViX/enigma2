#ifndef HDRDETECTOR_H
#define HDRDETECTOR_H

#include <lib/base/object.h>
#include <lib/base/ebase.h>
#include <lib/dvb/idvb.h>
#include <vector>

class iDVBDemux;
class iDVBPESReader;

/* Live DVB HDR tap: PES reader on the video PID (runs on eApp mainloop,
   no threads), classifies HDR via HevcHDR::classify, reports via signal.
   Works on any hardware with a DVB demux. */
class eHDRStreamDetector : public iObject, public sigc::trackable
{
	DECLARE_REF(eHDRStreamDetector);
	ePtr<iDVBPESReader> m_reader;
	ePtr<eConnection>   m_conn;
	ePtr<eTimer>        m_timeout;
	std::vector<uint8_t> m_es;
	size_t m_last_classify;
	size_t m_first_sps_at;
	int  m_result;
	bool m_done;
	void pesData(const uint8_t *data, int len);
	void onTimeout();
	void finish(int result);
public:
	eHDRStreamDetector();
	virtual ~eHDRStreamDetector();
	int start(iDVBDemux *demux, int pid);
	void stop();
	int getResult() const { return m_result; }
	sigc::signal<void(int)> resultChanged;
};

#endif
