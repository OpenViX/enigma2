#include <lib/service/audiochanneldetector.h>
#include <lib/service/servicedvbsoftdecoder.h>
#include <lib/dvb/idemux.h>
#include <lib/dvb/pmtparse.h>
#include <lib/base/eerror.h>

#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <cstring>
#include <cerrno>

// Ported from DVBAudioChannels.py. Kept deliberately close to the Python
// original so the two can be compared line-for-line during review.

namespace
{
	const size_t MAX_CAPTURE_BYTES = 1024 * 1024;
	const int PROBE_TIMEOUT_MS = 10000;

	// Once an initial answer is found, the probe switches to continuously
	// re-checking with a small rolling window instead of tearing down (see
	// feed()) - this bounds resource use per window without needing the
	// full 1MB safety margin the initial, never-yet-detected search gets.
	const size_t MONITOR_WINDOW_BYTES = 65536;

	// Generous margin covering the worst-case E-AC-3 bsi() walk (dialnorm/
	// compr, dependent-stream chanmap, full mixing metadata, informational
	// metadata, converter sync) before reaching addbsi - real streams rarely
	// come close to this, but this is cheap insurance against stopping the
	// probe just short of the Atmos flag.
	const size_t EAC3_ATMOS_MIN_BYTES = 512;

	const int AAC_CHANNELS[8] = { 0, 1, 2, 3, 4, 5, 6, 8 }; // index 7 -> 8 (7.1)

	int ac3MainChannels(int acmod)
	{
		static const int table[8] = { 2, 1, 2, 3, 3, 4, 4, 5 }; // 0=dual mono(2)
		if (acmod < 0 || acmod > 7)
			return 0;
		return table[acmod];
	}

	// Minimal MSB-first bit reader over a byte buffer. Mirrors BitReader in
	// the Python proof of concept; 'bad' replaces its ValueError/IndexError
	// on underrun - callers must check it after each parse attempt.
	struct BitReader
	{
		const uint8_t *data;
		size_t len;
		size_t bitpos;
		bool bad;

		BitReader(const uint8_t *data_, size_t len_) : data(data_), len(len_), bitpos(0), bad(false) {}

		size_t remaining() const { return len * 8 - bitpos; }

		unsigned int read(int count)
		{
			if (bad || count < 0 || remaining() < (size_t)count)
			{
				bad = true;
				return 0;
			}
			unsigned int value = 0;
			for (int i = 0; i < count; ++i)
			{
				uint8_t byte = data[bitpos >> 3];
				int shift = 7 - (bitpos & 7);
				value = (value << 1) | ((byte >> shift) & 1);
				++bitpos;
			}
			return value;
		}

		void skip(int count) { read(count); }
	};

	unsigned int readAudioObjectType(BitReader &bits)
	{
		unsigned int object_type = bits.read(5);
		if (object_type == 31)
			object_type = 32 + bits.read(6);
		return object_type;
	}

	unsigned int readSamplingFrequency(BitReader &bits)
	{
		unsigned int index = bits.read(4);
		if (index == 15)
			bits.read(24);
		return index;
	}

	// Returns channel count, or 0 on any failure/unsupported configuration.
	int parseAudioSpecificConfig(BitReader &bits)
	{
		unsigned int object_type = readAudioObjectType(bits);
		readSamplingFrequency(bits);
		unsigned int channel_config = bits.read(4);

		if (object_type == 5 || object_type == 29)
		{
			readSamplingFrequency(bits);
			object_type = readAudioObjectType(bits);
			if (object_type == 22)
				bits.read(4);
		}

		if (bits.bad || channel_config == 0)
			return 0;

		switch (object_type)
		{
			case 1: case 2: case 3: case 4: case 6: case 7:
			case 17: case 19: case 20: case 21: case 22: case 23:
				break;
			default:
				return 0;
		}

		bits.read(1); // frameLengthFlag
		unsigned int depends_on_core = bits.read(1);
		if (depends_on_core)
			bits.read(14);
		unsigned int extension_flag = bits.read(1);

		if (object_type == 6 || object_type == 20)
			bits.read(3);

		if (extension_flag)
		{
			if (object_type == 22)
			{
				bits.read(5);
				bits.read(11);
			}
			else if (object_type == 17 || object_type == 19 || object_type == 20 || object_type == 23)
				bits.read(3);
		}

		if (bits.bad || channel_config > 7)
			return 0;

		return AAC_CHANNELS[channel_config];
	}

	unsigned int latmGetValue(BitReader &bits)
	{
		unsigned int bytes_for_value = bits.read(2);
		return bits.read((bytes_for_value + 1) * 8);
	}

	// Returns channel count, or 0 on failure/unsupported multiplex.
	int parseStreamMuxConfig(BitReader &bits)
	{
		unsigned int audio_mux_version = bits.read(1);
		unsigned int audio_mux_version_a = audio_mux_version ? bits.read(1) : 0;
		if (audio_mux_version_a)
			return 0;

		if (audio_mux_version)
			latmGetValue(bits);

		unsigned int all_same_time = bits.read(1);
		bits.read(6); // numSubFrames
		unsigned int num_program = bits.read(4);
		if (!all_same_time || num_program != 0)
			return 0;

		unsigned int num_layer = bits.read(3);
		if (num_layer != 0)
			return 0;

		int channels;
		if (audio_mux_version)
		{
			unsigned int asc_length = latmGetValue(bits);
			size_t asc_start = bits.bitpos;
			channels = parseAudioSpecificConfig(bits);
			size_t consumed = bits.bitpos - asc_start;
			if (asc_length > consumed)
				bits.skip((int)(asc_length - consumed));
		}
		else
			channels = parseAudioSpecificConfig(bits);

		if (bits.bad)
			return 0;

		return channels;
	}

	int parseLOAS(const uint8_t *data, size_t len)
	{
		if (len < 3)
			return 0;
		for (size_t pos = 0; pos + 3 <= len; ++pos)
		{
			if (data[pos] != 0x56 || (data[pos + 1] & 0xE0) != 0xE0)
				continue;

			unsigned int mux_length = ((data[pos + 1] & 0x1F) << 8) | data[pos + 2];
			size_t end = pos + 3 + mux_length;
			if (mux_length == 0 || end > len)
				continue;

			BitReader bits(data + pos + 3, end - (pos + 3));
			if (bits.read(1)) // useSameStreamMux
				continue;

			int channels = parseStreamMuxConfig(bits);
			if (bits.bad)
				continue;

			if (channels > 0)
				return channels;
		}
		return 0;
	}

	int parseADTS(const uint8_t *data, size_t len)
	{
		if (len < 7)
			return 0;
		for (size_t pos = 0; pos + 7 <= len; ++pos)
		{
			if (data[pos] != 0xFF)
				continue;
			if ((data[pos + 1] & 0xF6) != 0xF0)
				continue;

			unsigned int sample_index = (data[pos + 2] >> 2) & 0x0F;
			if (sample_index == 0x0F)
				continue;

			unsigned int channel_config = ((data[pos + 2] & 0x01) << 2) | ((data[pos + 3] >> 6) & 0x03);
			if (channel_config > 7 || AAC_CHANNELS[channel_config] == 0)
				continue;

			unsigned int frame_length =
				((data[pos + 3] & 0x03) << 11) |
				(data[pos + 4] << 3) |
				((data[pos + 5] >> 5) & 0x07);
			if (frame_length < 7)
				continue;

			return AAC_CHANNELS[channel_config];
		}
		return 0;
	}

	int parseMPEGAudio(const uint8_t *data, size_t len)
	{
		static const int mpeg1_l2_bitrates[16] = { 0,32,48,56,64,80,96,112,128,160,192,224,256,320,384,0 };
		static const int mpeg2_l2_bitrates[16] = { 0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0 };
		static const int base_rates[3] = { 44100, 48000, 32000 };

		if (len < 4)
			return 0;
		for (size_t pos = 0; pos + 4 <= len; ++pos)
		{
			unsigned int header =
				(data[pos] << 24) | (data[pos + 1] << 16) |
				(data[pos + 2] << 8) | data[pos + 3];

			if (((header >> 21) & 0x7FF) != 0x7FF)
				continue;

			unsigned int version = (header >> 19) & 0x03;
			unsigned int layer = (header >> 17) & 0x03;
			unsigned int bitrate_index = (header >> 12) & 0x0F;
			unsigned int sample_index = (header >> 10) & 0x03;
			unsigned int padding = (header >> 9) & 0x01;
			unsigned int channel_mode = (header >> 6) & 0x03;

			if (version == 1 || layer != 2) // version 1 reserved; only Layer II
				continue;
			if (bitrate_index == 0 || bitrate_index == 15 || sample_index == 3)
				continue;

			int sample_rate = base_rates[sample_index];
			int bitrate;
			if (version == 3) // MPEG-1
				bitrate = mpeg1_l2_bitrates[bitrate_index];
			else
			{
				bitrate = mpeg2_l2_bitrates[bitrate_index];
				sample_rate /= (version == 2) ? 2 : 4;
			}
			if (!bitrate || !sample_rate)
				continue;

			unsigned int frame_length = (144000u * bitrate) / sample_rate + padding;
			if (frame_length < 4)
				continue;

			size_t next_pos = pos + frame_length;
			if (next_pos + 2 <= len)
			{
				if (data[next_pos] != 0xFF || (data[next_pos + 1] & 0xE0) != 0xE0)
					continue;
			}
			else
				continue;

			return (channel_mode == 3) ? 1 : 2;
		}
		return 0;
	}

	int parseAC3EAC3(const uint8_t *data, size_t len, bool want_eac3)
	{
		if (len < 16)
			return 0;
		for (size_t pos = 0; pos + 16 <= len; ++pos)
		{
			if (data[pos] != 0x0B || data[pos + 1] != 0x77)
				continue;

			BitReader bits(data + pos, 16);

			if (want_eac3)
			{
				if (bits.read(16) != 0x0B77)
					continue;
				unsigned int stream_type = bits.read(2);
				unsigned int substream_id = bits.read(3);
				unsigned int frame_size = (bits.read(11) + 1) * 2;
				unsigned int fscod = bits.read(2);

				if (bits.bad || stream_type == 3 || frame_size < 8 || frame_size > 8192)
					continue;

				if (fscod == 3)
				{
					if (bits.read(2) == 3)
						continue;
				}
				else
					bits.read(2);

				unsigned int acmod = bits.read(3);
				unsigned int lfeon = bits.read(1);
				unsigned int bsid = bits.read(5);
				if (bits.bad)
					continue;

				// Only trust acmod/lfeon from the independent substream.
				if (bsid >= 11 && bsid <= 16 && stream_type == 0 && substream_id == 0)
				{
					int channels = ac3MainChannels(acmod) + lfeon;
					if (channels)
						return channels;
				}
			}
			else
			{
				if (bits.read(16) != 0x0B77)
					continue;
				bits.read(16); // crc1
				unsigned int fscod = bits.read(2);
				unsigned int frmsizecod = bits.read(6);
				unsigned int bsid = bits.read(5);
				if (bits.bad || fscod == 3 || frmsizecod >= 38 || bsid > 10)
					continue;

				bits.read(3); // bsmod
				unsigned int acmod = bits.read(3);

				if ((acmod & 1) && acmod != 1)
					bits.read(2);
				if (acmod & 4)
					bits.read(2);
				if (acmod == 2)
					bits.read(2);

				unsigned int lfeon = bits.read(1);
				if (bits.bad)
					continue;

				int channels = ac3MainChannels(acmod) + lfeon;
				if (channels)
					return channels;
			}
		}
		return 0;
	}

	// Ported from eDVBAudioChannelDetector's sibling in eServiceMP3
	// (lib/service/servicemp3.cpp: parseEAC3AtmosFrame), which already does
	// this for local file playback and is production-tested in this same
	// codebase. Simplified here for raw broadcast ES: no byte-swap or
	// IEC61937 container framing applies - a DVB elementary stream is
	// always plain big-endian E-AC-3, unlike GStreamer's various local-file
	// inputs. Walks the full bitstream info (ETSI TS 102 366 Annex E)
	// through to the additional bitstream info extension, where
	// flag_ec3_extension_type_a signals Dolby Atmos (Joint Object Coding).
	// Same acmod/lfeon either way - this is a separate signal, not
	// something the channel-count parser above can distinguish on its own.
	bool parseEAC3AtmosFrame(const uint8_t *data, size_t len, unsigned int &frame_size, bool &atmos)
	{
		frame_size = 0;
		atmos = false;

		if (!data || len < 7)
			return false;

		BitReader bits(data, len);
		if (bits.read(16) != 0x0B77)
			return false;

		unsigned int frame_type = bits.read(2);
		unsigned int substreamid = bits.read(3);
		frame_size = (bits.read(11) + 1) << 1;
		unsigned int sr_code = bits.read(2);

		unsigned int num_blocks = 6;
		if (sr_code == 3)
		{
			if (bits.read(2) == 3)
				return false;
		}
		else
		{
			static const unsigned int blocks[4] = { 1, 2, 3, 6 };
			num_blocks = blocks[bits.read(2)];
		}

		unsigned int channel_mode = bits.read(3);
		bool lfe_on = bits.read(1) != 0;

		// Match eServiceMP3's / FFmpeg's E-AC-3 header validity checks.
		if (bits.bad || frame_type == 3 || substreamid != 0 ||
			frame_size < 7 || frame_size > len)
			return false;

		unsigned int bitstream_id = bits.read(5);
		if (bits.bad || bitstream_id <= 10 || bitstream_id > 16)
			return false;

		// Volume control parameters (dialnorm/compr, per substream count).
		for (unsigned int i = 0; i < (channel_mode ? 1U : 2U); ++i)
		{
			bits.skip(5); // dialnorm
			if (bits.read(1))
				bits.skip(8); // compr
		}

		// Dependent stream channel map.
		if (frame_type == 1)
		{
			if (bits.read(1))
				bits.skip(16);
		}

		// Mixing metadata.
		if (bits.read(1))
		{
			if (channel_mode > 2)
			{
				bits.skip(2); // preferred downmix
				if (channel_mode & 1)
					bits.skip(6);
				if (channel_mode & 4)
					bits.skip(6);
			}

			if (lfe_on && bits.read(1))
				bits.skip(5);

			if (frame_type == 0)
			{
				for (unsigned int i = 0; i < (channel_mode ? 1U : 2U); ++i)
				{
					if (bits.read(1))
						bits.skip(6);
				}

				if (bits.read(1))
					bits.skip(6);

				switch (bits.read(2))
				{
					case 1: bits.skip(5); break;
					case 2: bits.skip(12); break;
					case 3:
					{
						unsigned int mix_data_size = (bits.read(5) + 2) << 3;
						bits.skip(mix_data_size);
						break;
					}
					default: break;
				}

				if (channel_mode < 2)
				{
					for (unsigned int i = 0; i < (channel_mode ? 1U : 2U); ++i)
					{
						if (bits.read(1))
							bits.skip(14);
					}
				}

				if (bits.read(1))
				{
					for (unsigned int i = 0; i < num_blocks; ++i)
					{
						if (num_blocks == 1 || bits.read(1))
							bits.skip(5);
					}
				}
			}
		}

		// Informational metadata.
		if (bits.read(1))
		{
			bits.skip(3); // bsmod
			bits.skip(2); // copyright + original

			if (channel_mode == 2)
				bits.skip(4);
			if (channel_mode >= 6)
				bits.skip(2);

			for (unsigned int i = 0; i < (channel_mode ? 1U : 2U); ++i)
			{
				if (bits.read(1))
					bits.skip(8);
			}

			if (sr_code != 3)
				bits.skip(1);
		}

		if (frame_type == 0 && num_blocks != 6)
			bits.skip(1); // converter sync

		if (frame_type == 2)
		{
			bool have_original_size = num_blocks == 6;
			if (!have_original_size)
				have_original_size = bits.read(1) != 0;
			if (have_original_size)
				bits.skip(6);
		}

		if (bits.bad)
			return false;

		// Additional bitstream info - where the Atmos/JOC flag lives.
		if (bits.read(1)) // addbsie
		{
			unsigned int addbsil = bits.read(6);
			if (bits.bad || addbsil > 63)
				return false;

			bits.skip(7);
			atmos = !bits.bad && bits.read(1) != 0;
		}

		return !bits.bad;
	}

	// Scans the accumulated capture for any E-AC-3 sync frame carrying the
	// Atmos flag. Unlike eServiceMP3's frame-hopping variant (which receives
	// buffers already aligned to a frame boundary by GStreamer), our capture
	// may start mid-frame, so this checks every candidate sync position
	// rather than jumping by declared frame_size.
	bool scanForAtmos(const uint8_t *data, size_t len)
	{
		if (len < 7)
			return false;
		for (size_t pos = 0; pos + 7 <= len; ++pos)
		{
			if (data[pos] != 0x0B || data[pos + 1] != 0x77)
				continue;

			unsigned int frame_size = 0;
			bool atmos = false;
			if (parseEAC3AtmosFrame(data + pos, len - pos, frame_size, atmos) && atmos)
				return true;
		}
		return false;
	}
}

DEFINE_REF(eDVBAudioChannelDetector);

eDVBAudioChannelDetector::eDVBAudioChannelDetector()
	: m_pid(-1), m_codec(ctUnsupported), m_identity(nullptr), m_softcsa(false),
	  m_channels(0), m_atmos(false), m_monitoring(false), m_gaveUp(false)
{
	m_monitor_fd[0] = m_monitor_fd[1] = -1;
	m_timeout = eTimer::create(eApp);
	CONNECT(m_timeout->timeout, eDVBAudioChannelDetector::onTimeout);
}

eDVBAudioChannelDetector::~eDVBAudioChannelDetector()
{
	stop();
}

int eDVBAudioChannelDetector::codecFromStreamType(int pmt_audio_type)
{
	switch (pmt_audio_type)
	{
		case eDVBPMTParser::audioStream::atMPEG: return ctMPEG;
		case eDVBPMTParser::audioStream::atAC3:  return ctAC3;
		case eDVBPMTParser::audioStream::atDDP:  return ctEAC3;
		case eDVBPMTParser::audioStream::atAAC:
		case eDVBPMTParser::audioStream::atAACHE:
			return ctAAC;
		default:
			// DTS, DTS-HD, LPCM, DRA, AC4: unsupported here by design.
			// TrueHD/DTS transcoding is handled entirely separately and
			// this detector must not interfere with it.
			return ctUnsupported;
	}
}

bool eDVBAudioChannelDetector::matches(int pid, int codec, const void *identity) const
{
	return pid == m_pid && codec == m_codec && identity == m_identity;
}

void eDVBAudioChannelDetector::reset()
{
	stop();
	m_data.clear();
	m_data.reserve(16384);
	m_channels = 0;
	m_atmos = false;
	m_monitoring = false;
	m_gaveUp = false;
}

void eDVBAudioChannelDetector::stop()
{
	m_timeout->stop();

	if (m_pes_reader)
	{
		m_pes_reader->stop();
		m_pes_conn = 0;
		m_pes_reader = 0;
	}

	if (m_notifier)
	{
		m_notifier->stop();
		m_notifier = 0;
	}

	if (m_soft_decoder)
	{
		m_soft_decoder->setAudioMonitorFD(-1);
		m_soft_decoder = 0;
	}

	if (m_monitor_fd[0] >= 0) { ::close(m_monitor_fd[0]); m_monitor_fd[0] = -1; }
	if (m_monitor_fd[1] >= 0) { ::close(m_monitor_fd[1]); m_monitor_fd[1] = -1; }
}

void eDVBAudioChannelDetector::start(iDVBDemux *demux, int pid, int codec)
{
	reset();

	m_pid = pid;
	m_codec = codec;
	m_identity = demux;
	m_softcsa = false;

	if (pid <= 0 || codec == ctUnsupported || !demux)
	{
		eDebug("[eDVBAudioChannelDetector] start: skipping pid=%d codec=%d (unsupported or invalid)", pid, codec);
		giveUp();
		return;
	}

	if (demux->createPESReader(eApp, m_pes_reader) || !m_pes_reader)
	{
		eDebug("[eDVBAudioChannelDetector] start: createPESReader failed for pid=%d", pid);
		m_pes_reader = 0;
		giveUp();
		return;
	}

	m_pes_reader->connectRead(sigc::mem_fun(*this, &eDVBAudioChannelDetector::pesData), m_pes_conn);
	if (m_pes_reader->start(pid))
	{
		eDebug("[eDVBAudioChannelDetector] start: PES reader start() failed for pid=%d", pid);
		m_pes_reader = 0;
		m_pes_conn = 0;
		giveUp();
		return;
	}

	eDebug("[eDVBAudioChannelDetector] probing pid=%04x codec=%d via PES reader", pid, codec);
	m_timeout->start(PROBE_TIMEOUT_MS, true);
}

void eDVBAudioChannelDetector::startSoftCSA(eDVBSoftDecoder *soft_decoder, int pid, int codec)
{
	reset();

	m_pid = pid;
	m_codec = codec;
	m_identity = soft_decoder;
	m_softcsa = true;

	if (pid <= 0 || codec == ctUnsupported || !soft_decoder)
	{
		eDebug("[eDVBAudioChannelDetector] startSoftCSA: skipping pid=%d codec=%d (unsupported or invalid)", pid, codec);
		giveUp();
		return;
	}

	if (::socketpair(AF_UNIX, SOCK_STREAM, 0, m_monitor_fd) != 0)
	{
		eDebug("[eDVBAudioChannelDetector] startSoftCSA: socketpair() failed for pid=%d: %m", pid);
		m_monitor_fd[0] = m_monitor_fd[1] = -1;
		giveUp();
		return;
	}

	// Both ends non-blocking: the write end is used from the record thread
	// and must never be allowed to block the real decode path on backpressure.
	::fcntl(m_monitor_fd[0], F_SETFL, O_NONBLOCK);
	::fcntl(m_monitor_fd[1], F_SETFL, O_NONBLOCK);

	int bufsz = 256 * 1024;
	::setsockopt(m_monitor_fd[0], SOL_SOCKET, SO_RCVBUF, &bufsz, sizeof(bufsz));
	::setsockopt(m_monitor_fd[1], SOL_SOCKET, SO_SNDBUF, &bufsz, sizeof(bufsz));

	if (soft_decoder->setAudioMonitorFD(m_monitor_fd[1]))
	{
		eDebug("[eDVBAudioChannelDetector] startSoftCSA: setAudioMonitorFD failed for pid=%d (recorder not active yet?)", pid);
		::close(m_monitor_fd[0]); m_monitor_fd[0] = -1;
		::close(m_monitor_fd[1]); m_monitor_fd[1] = -1;
		giveUp();
		return;
	}

	m_soft_decoder = soft_decoder;

	m_notifier = eSocketNotifier::create(eApp, m_monitor_fd[0], eSocketNotifier::Read, false);
	CONNECT(m_notifier->activated, eDVBAudioChannelDetector::monitorData);
	m_notifier->start();

	eDebug("[eDVBAudioChannelDetector] probing pid=%04x codec=%d via SoftCSA monitor fd", pid, codec);
	m_timeout->start(PROBE_TIMEOUT_MS, true);
}

void eDVBAudioChannelDetector::pesData(const uint8_t *data, int len)
{
	feed(data, len);
}

void eDVBAudioChannelDetector::monitorData(int)
{
	uint8_t buffer[16384];
	for (;;)
	{
		int r = ::read(m_monitor_fd[0], buffer, sizeof(buffer));

		if (r == 0)
		{
			// Peer (write end, held by the recorder) closed. A closed,
			// non-blocking socket is always "readable" - if we just return
			// here and leave the notifier running, it fires again
			// immediately, forever (a busy-loop / permanent spinner). This
			// probe can never get more data, so stop it outright.
			eDebug("[eDVBAudioChannelDetector] monitor fd closed for pid=%04x, giving up", m_pid);
			giveUp();
			return;
		}

		if (r < 0)
		{
			if (errno == EAGAIN || errno == EWOULDBLOCK)
				return; // no data right now - wait for the next real notification
			eDebug("[eDVBAudioChannelDetector] monitor fd read error for pid=%04x: %m", m_pid);
			giveUp();
			return;
		}

		// The monitor delivers raw 188-byte TS packets for every PID the
		// SoftCSA recorder carries (video + audio + PCR, ...). Filter down
		// to our target PID's payload before handing bytes to the same
		// byte-level scanners used by the PES paths - PES header bytes
		// embedded in that payload are harmless, exactly as in the
		// Python proof of concept, which never stripped them either.
		for (int pos = 0; pos + 188 <= r; pos += 188)
		{
			const uint8_t *packet = buffer + pos;
			if (packet[0] != 0x47)
				continue;

			int packet_pid = ((packet[1] & 0x1F) << 8) | packet[2];
			if (packet_pid != m_pid)
				continue;

			int adaptation_control = (packet[3] >> 4) & 0x03;
			if (adaptation_control == 0 || adaptation_control == 2)
				continue; // no payload

			int offset = 4;
			if (adaptation_control == 3)
			{
				if (offset >= 188)
					continue;
				int adaptation_length = packet[offset];
				offset += 1 + adaptation_length;
			}
			if (offset >= 188)
				continue;

			feed(packet + offset, 188 - offset);
			if (finished())
				return;
		}

		if (r != (int)sizeof(buffer))
			return;
	}
}

void eDVBAudioChannelDetector::feed(const uint8_t *data, int len)
{
	if (m_gaveUp || len <= 0)
		return;

	// Inactivity timeout, not a wall-clock deadline from start(): a slow-to-
	// establish source (StreamRelay in particular can take a while to open)
	// must not be abandoned just because setup took time - as long as data
	// keeps arriving, keep pushing the deadline out. It only fires if data
	// genuinely stops for the full window. Also doubles as "the track has
	// gone silent" once monitoring - see onTimeout().
	m_timeout->start(PROBE_TIMEOUT_MS, true);

	size_t cap = m_monitoring ? MONITOR_WINDOW_BYTES : MAX_CAPTURE_BYTES;
	size_t room = cap - m_data.size();
	if (room > 0)
	{
		size_t take = (size_t)len < room ? (size_t)len : room;
		m_data.insert(m_data.end(), data, data + take);
	}

	int prev_channels = m_channels;
	bool prev_atmos = m_atmos;

	tryDetect();

	if (settled())
	{
		if (m_channels != prev_channels || m_atmos != prev_atmos)
		{
			eDebug("[eDVBAudioChannelDetector] %d channel(s)%s for pid=%04x (was %d%s)",
				m_channels, m_atmos ? " (Dolby Atmos)" : "", m_pid,
				prev_channels, prev_atmos ? " (Dolby Atmos)" : "");
			channelsDetected();
		}

		// Got a fresh, complete answer for this window. Do NOT tear down
		// the reader/notifier - the format can legitimately change later on
		// the very same pid/codec (e.g. an ad break swapping 5.1 program
		// audio for 2.0, or vice versa, with no PID/PMT change at all) and
		// matches() has no way to notice that on its own. Instead, keep
		// watching: start a fresh, bounded window so a later change gets
		// picked up rather than being permanently masked by whatever was
		// seen first. channels()/isAtmos() keep reporting the last answer
		// found until a new one replaces it.
		m_monitoring = true;
		m_data.clear();
		return;
	}

	if (m_data.size() >= cap)
	{
		if (!m_monitoring)
		{
			// Initial detection never found anything in the full safety
			// margin - give up for good, same as before.
			eDebug("[eDVBAudioChannelDetector] giving up on pid=%04x: no valid header found in %zu bytes",
				m_pid, m_data.size());
			// Self-teardown hazard as elsewhere - mark finished now (so
			// further feed() calls are no-ops) but defer stop() to next tick.
			m_gaveUp = true;
			m_timeout->start(0, true);
		}
		else
		{
			// Already monitoring, this window just didn't turn up a fresh
			// answer - not a failure, the last known channels()/isAtmos()
			// is still valid. Reset the window and keep watching.
			m_data.clear();
		}
	}
}

bool eDVBAudioChannelDetector::settled() const
{
	if (m_channels <= 0)
		return false;
	if (m_codec == ctEAC3 && !m_atmos && m_data.size() < EAC3_ATMOS_MIN_BYTES)
		return false; // channel count known, but give isAtmos() more data first
	return true;
}

bool eDVBAudioChannelDetector::finished() const
{
	// "No point feeding this probe any more data at all" - true once given
	// up outright. Deliberately does NOT include settled(): a settled probe
	// still wants more data, forever, to notice a later format change - see
	// feed(). Callers that mean "do we have an answer yet" should check
	// channels() (or settled()) instead.
	return m_gaveUp;
}

void eDVBAudioChannelDetector::tryDetect()
{
	if (m_data.empty())
		return;

	int channels = 0;
	switch (m_codec)
	{
		case ctMPEG:
			channels = parseMPEGAudio(m_data.data(), m_data.size());
			break;
		case ctAC3:
			channels = parseAC3EAC3(m_data.data(), m_data.size(), false);
			break;
		case ctEAC3:
			channels = parseAC3EAC3(m_data.data(), m_data.size(), true);
			if (!m_atmos && scanForAtmos(m_data.data(), m_data.size()))
			{
				m_atmos = true;
				eDebug("[eDVBAudioChannelDetector] Dolby Atmos (JOC) detected for pid=%04x", m_pid);
			}
			break;
		case ctAAC:
			channels = parseLOAS(m_data.data(), m_data.size());
			if (!channels)
				channels = parseADTS(m_data.data(), m_data.size());
			break;
		default:
			break;
	}

	if (channels > 0)
		m_channels = channels;
}

void eDVBAudioChannelDetector::giveUp()
{
	m_gaveUp = true;
	stop();
}

void eDVBAudioChannelDetector::onTimeout()
{
	// Fires either as the deferred teardown scheduled by feed() right after
	// giving up outright (m_gaveUp already true, a 0ms one-shot - see
	// feed()), or as a genuine 10s-inactivity timeout: no data at all
	// during initial probing, or - now that a settled probe keeps watching
	// indefinitely for a later format change instead of tearing down (see
	// feed()) - the track has gone quiet after having been settled for a
	// while. Either way, that means give up for good: keep whatever
	// channels()/isAtmos() already found (frozen at their last value) and
	// stop watching, rather than spinning forever on a source that has
	// stopped producing data.
	if (!finished())
	{
		eDebug("[eDVBAudioChannelDetector] probe timed out for pid=%04x after %zu bytes", m_pid, m_data.size());
		m_gaveUp = true;
	}
	stop();
}
