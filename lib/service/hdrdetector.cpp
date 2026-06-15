#include <lib/service/hdrdetector.h>
#include <lib/service/hevc_hdr.h>
#include <lib/dvb/idemux.h>

#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>

#define MAX_ES_BYTES   (8 * 1024 * 1024)
#define CLASSIFY_STEP  (64 * 1024)
#define SDR_COMMIT     (768 * 1024)   /* read past first SPS before committing SDR */
/* 3 s is enough for an I-frame with a typical GOP on any stream rate,
   and it is short enough for the hardware gamma fallback to be queried
   before the user notices a delay. */
#define TAP_TIMEOUT_MS 3000

DEFINE_REF(eHDRStreamDetector);

eHDRStreamDetector::eHDRStreamDetector()
	: m_vpid(-1), m_last_classify(0), m_first_sps_at(0),
	  m_result(HevcHDR::HDR_SDR), m_done(false)
{
	m_svfd[0] = m_svfd[1] = -1;
	m_timeout = eTimer::create(eApp);
	CONNECT(m_timeout->timeout, eHDRStreamDetector::onTimeout);
}

eHDRStreamDetector::~eHDRStreamDetector()
{
	stop();
}

int eHDRStreamDetector::start(iDVBDemux *demux, int pid)
{
	if (pid <= 0)
		return -1;

	m_vpid = pid;
	m_last_classify = 0;
	m_first_sps_at = 0;
	m_result = HevcHDR::HDR_SDR;
	m_done = false;
	m_es.clear();
	m_es.reserve(512 * 1024);

	/* Set up a TS recorder writing to one end of a socket pair.
	 * createTSRecorder uses DMX_OUT_TS_TAP, which taps the multiplex
	 * *before* it routes to the hardware decoder.  This is the same
	 * kernel path used by the streamserver on port 8001, which is why
	 * the Python HDRDetect plugin can read the video ES — and why
	 * DMX_PES_OTHER / DMX_OUT_TAP (createPESReader) silently delivers
	 * nothing for video PIDs on most STBs. */
	if (demux && ::socketpair(AF_UNIX, SOCK_STREAM, 0, m_svfd) == 0)
	{
		/* Large buffers to absorb bursts from the recorder thread */
		int bufsz = 512 * 1024;
		::setsockopt(m_svfd[0], SOL_SOCKET, SO_RCVBUF, &bufsz, sizeof(bufsz));
		::setsockopt(m_svfd[1], SOL_SOCKET, SO_SNDBUF, &bufsz, sizeof(bufsz));

		if (demux->createTSRecorder(m_recorder, 188, /*streaming=*/true) == 0 && m_recorder)
		{
			m_recorder->setTargetFD(m_svfd[1]);
			m_recorder->addPID(pid);
			if (m_recorder->start() == 0)
			{
				::fcntl(m_svfd[0], F_SETFL, O_NONBLOCK);
				m_notifier = eSocketNotifier::create(eApp, m_svfd[0],
				                                     eSocketNotifier::Read, false);
				CONNECT(m_notifier->activated, eHDRStreamDetector::tsData);
				m_notifier->start();
				eDebug("[eHDRStreamDetector] TS recorder started for pid %04x", pid);
			}
			else
			{
				eDebug("[eHDRStreamDetector] TS recorder start failed, timeout-only mode");
				m_recorder = 0;
				::close(m_svfd[0]); m_svfd[0] = -1;
				::close(m_svfd[1]); m_svfd[1] = -1;
			}
		}
		else
		{
			eDebug("[eHDRStreamDetector] createTSRecorder failed, timeout-only mode");
			::close(m_svfd[0]); m_svfd[0] = -1;
			::close(m_svfd[1]); m_svfd[1] = -1;
		}
	}

	/* Always start the timeout — guarantees hdrResult() is called even
	   when no TS data arrives (hardware gamma fallback in servicedvb.cpp). */
	m_timeout->start(TAP_TIMEOUT_MS, true);
	return 0;
}

void eHDRStreamDetector::stop()
{
	if (m_timeout) m_timeout->stop();
	if (m_notifier) { m_notifier->stop(); m_notifier = 0; }
	if (m_recorder) { m_recorder->stop(); m_recorder = 0; }
	if (m_svfd[1] >= 0) { ::close(m_svfd[1]); m_svfd[1] = -1; }
	if (m_svfd[0] >= 0) { ::close(m_svfd[0]); m_svfd[0] = -1; }
}

/* Called by the eSocketNotifier when the recorder has written TS packets
 * to m_svfd[0].  Parses raw 188-byte TS packets and extracts the HEVC ES
 * — identical algorithm to Python's extract_es_from_ts(). */
void eHDRStreamDetector::tsData(int)
{
	if (m_done || m_svfd[0] < 0)
		return;

	/* Read as many packets as are available in one shot */
	uint8_t buf[188 * 64];
	for (;;)
	{
		int r = ::read(m_svfd[0], buf, sizeof(buf));
		if (r <= 0)
			break;

		/* --- TS demux (software, same as Python extract_es_from_ts) --- */
		for (int i = 0; i + 188 <= r; i += 188)
		{
			const uint8_t *pkt = buf + i;
			if (pkt[0] != 0x47)
				continue;  /* lost sync — skip */

			int pid = ((pkt[1] & 0x1f) << 8) | pkt[2];
			if (pid != m_vpid)
				continue;

			int payload_unit_start = (pkt[1] >> 6) & 1;
			int adaptation         = (pkt[3] >> 4) & 0x3;
			int offset = 4;

			if (adaptation & 0x2)       /* adaptation field present */
			{
				int adapt_len = pkt[4];
				offset = 5 + adapt_len;
			}
			if (!(adaptation & 0x1))    /* no payload */
				continue;
			if (offset >= 188)
				continue;

			const uint8_t *payload = pkt + offset;
			int plen = 188 - offset;

			if (payload_unit_start)
			{
				/* Strip PES header: 3 start-code bytes + stream_id + 2 length
				 * bytes + 2 flags bytes + 1 header_data_length byte = 9 fixed
				 * bytes, then PES_header_data_length optional bytes. */
				if (plen >= 9 &&
				    payload[0] == 0 && payload[1] == 0 && payload[2] == 1)
				{
					int hdrlen = payload[8];
					int off = 9 + hdrlen;
					if (off < plen)
						m_es.insert(m_es.end(), payload + off, payload + plen);
				}
				/* else: non-PES payload_unit_start (shouldn't happen for video) */
			}
			else
			{
				m_es.insert(m_es.end(), payload, payload + plen);
			}
		}

		/* Classify when enough new data has accumulated */
		if (m_es.empty() ||
		    (m_es.size() - m_last_classify < CLASSIFY_STEP &&
		     m_es.size() < MAX_ES_BYTES))
			continue;

		m_last_classify = m_es.size();

		bool sawSPS = false;
		int result = HevcHDR::classify(&m_es[0], (int)m_es.size(), &sawSPS);

		if (result == HevcHDR::HDR_HDR10 || result == HevcHDR::HDR_HLG)
		{
			finish(result);
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
		{
			finish(HevcHDR::HDR_SDR);
			return;
		}
	}
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
	if (m_notifier) { m_notifier->stop(); m_notifier = 0; }
	if (m_recorder) { m_recorder->stop(); m_recorder = 0; }
	if (m_svfd[1] >= 0) { ::close(m_svfd[1]); m_svfd[1] = -1; }
	if (m_svfd[0] >= 0) { ::close(m_svfd[0]); m_svfd[0] = -1; }
	std::vector<uint8_t>().swap(m_es);
	resultChanged(result);
}
