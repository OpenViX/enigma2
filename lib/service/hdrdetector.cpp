#include <lib/service/hdrdetector.h>
#include <lib/service/hevc_hdr.h>
#include <lib/dvb/demux.h>

#define MAX_ES_BYTES     (8 * 1024 * 1024)
#define CLASSIFY_STEP    (64 * 1024)
#define SDR_COMMIT       (768 * 1024)   /* read past first SPS before committing SDR */
#define TAP_TIMEOUT_MS   8000

DEFINE_REF(eHDRStreamDetector);

eHDRStreamDetector::eHDRStreamDetector()
	: m_last_classify(0), m_first_sps_at(0),
	  m_result(HevcHDR::HDR_SDR), m_done(false)
{
	m_timeout = eTimer::create(eApp);
	CONNECT(m_timeout->timeout, eHDRStreamDetector::onTimeout);
}

eHDRStreamDetector::~eHDRStreamDetector()
{
	stop();
}

int eHDRStreamDetector::start(iDVBDemux *demux, int pid)
{
	if (!demux || pid <= 0)
		return -1;
	if (demux->createPESReader(eApp, m_reader) != 0 || !m_reader)
		return -1;
	m_reader->connectRead(sigc::mem_fun(*this, &eHDRStreamDetector::pesData), m_conn);
	m_es.clear();
	m_es.reserve(512 * 1024);
	m_last_classify = 0;
	m_first_sps_at = 0;
	m_result = HevcHDR::HDR_SDR;
	m_done = false;
	if (m_reader->start(pid) != 0)
	{
		m_reader = 0;
		m_conn = 0;
		return -1;
	}
	m_timeout->start(TAP_TIMEOUT_MS, true);
	return 0;
}

void eHDRStreamDetector::stop()
{
	if (m_timeout) m_timeout->stop();
	if (m_reader) { m_reader->stop(); m_reader = 0; }
	m_conn = 0;
}

void eHDRStreamDetector::pesData(const uint8_t *data, int len)
{
	if (m_done || len <= 0)
		return;

	/* strip PES header -> ES (Annex-B) */
	if (len > 9 && data[0] == 0 && data[1] == 0 && data[2] == 1)
	{
		int hdrlen = data[8];
		int off = 9 + hdrlen;
		if (off < len)
			m_es.insert(m_es.end(), data + off, data + len);
	}
	else
		m_es.insert(m_es.end(), data, data + len);

	if (m_es.size() - m_last_classify < CLASSIFY_STEP && m_es.size() < MAX_ES_BYTES)
		return;
	m_last_classify = m_es.size();

	bool sawSPS = false;
	int r = HevcHDR::classify(&m_es[0], (int)m_es.size(), &sawSPS);

	if (r == HevcHDR::HDR_HDR10 || r == HevcHDR::HDR_HLG)
	{
		finish(r);
		return;
	}
	if (sawSPS)
	{
		if (!m_first_sps_at) m_first_sps_at = m_es.size();
		if (m_es.size() - m_first_sps_at >= SDR_COMMIT)
		{
			finish(HevcHDR::HDR_SDR);
			return;
		}
	}
	if (m_es.size() >= MAX_ES_BYTES)
		finish(HevcHDR::HDR_SDR);
}

void eHDRStreamDetector::onTimeout()
{
	if (!m_done)
		finish(m_result);
}

void eHDRStreamDetector::finish(int result)
{
	if (m_done) return;
	m_done = true;
	m_result = result;
	if (m_timeout) m_timeout->stop();
	if (m_reader) { m_reader->stop(); m_reader = 0; }
	m_conn = 0;
	std::vector<uint8_t>().swap(m_es);
	resultChanged(result);
}
