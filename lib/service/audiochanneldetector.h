#ifndef AUDIOCHANNELDETECTOR_H
#define AUDIOCHANNELDETECTOR_H

#include <lib/base/object.h>
#include <lib/base/ebase.h>
#include <lib/dvb/idvb.h>
#include <cstdint>
#include <vector>

class iDVBDemux;
class eDVBSoftDecoder;

/*
 * eDVBAudioChannelDetector
 *
 * Detects the channel count (2.0 / 5.1 / 7.1 / ...) - and, for E-AC-3,
 * whether Dolby Atmos (Joint Object Coding) metadata is present - of the
 * currently selected DVB audio track, by inspecting the actual elementary
 * stream for codecs whose frame header encodes this: MPEG-1 Layer II,
 * AC3, E-AC3, and AAC (ADTS and LATM/LOAS).
 *
 * This does NOT use PMT/EIT metadata, codec-name inference (e.g.
 * assuming AC3 == 5.1), /proc, or any hardware/Broadcom-specific
 * offsets - those approaches were evaluated during development and
 * rejected as unreliable. The bit-level parsing here mirrors the
 * DVBAudioChannels.py proof of concept, ported to run in-process
 * against native demux data instead of a raw ioctl demux fd opened
 * from Python.
 *
 * Two acquisition paths, selected by the caller:
 *
 *  - start(): live DVB, local .ts/.trp playback, and StreamRelay.
 *    Reads PES for the audio PID via iDVBDemux::createPESReader(),
 *    the same mechanism already used in this codebase for subtitle,
 *    teletext, and radiotext PES (lib/dvb/subtitle.cpp,
 *    lib/dvb/teletext.cpp, lib/dvb/radiotext.cpp). The reader delivers
 *    raw bytes straight off the demux fd (PES headers included,
 *    unaligned to packet boundaries) - the byte-level sync scanners
 *    below tolerate that exactly as the Python proof of concept did.
 *
 *  - startSoftCSA(): SoftCSA. A second independent TSRecorder sharing
 *    the live eDVBCSASession was deliberately rejected: eDVBCSAEngine
 *    keeps reusable scratch buffers (m_batch_even/m_batch_odd) that
 *    are only safe for a single concurrent caller, so two recorders
 *    calling descramble() on the same session/engine at once would
 *    race. Instead this taps the *existing* SoftCSA recorder
 *    (eDVBSoftDecoder::setAudioMonitorFD) right after it descrambles
 *    in place, via a best-effort, non-blocking monitor fd - see
 *    eDVBTSRecorder::setMonitorFD. That delivers raw TS packets for
 *    every PID the recorder carries, so this path additionally filters
 *    down to our target PID's payload before handing bytes to the same
 *    byte-level scanners used everywhere else.
 *
 * Initial detection is bounded (a safety byte-cap, and an inactivity
 * timeout that resets on every batch of real data - so a source that's
 * merely slow to establish, StreamRelay in particular, isn't abandoned
 * before it ever produces data). Once an initial answer is found, the
 * probe does NOT tear itself down: the format can legitimately change
 * later on the very same pid/codec - most commonly an ad break swapping
 * 5.1 program audio for 2.0 stereo, or vice versa, with no PID/PMT
 * change at all - and matches() has no way to notice that on its own.
 * Instead it keeps watching with a small rolling window (see
 * MONITOR_WINDOW_BYTES), so channels()/isAtmos() always reflect the most
 * recently detected value rather than freezing on whatever was seen
 * first. It only actually stops - closing the reader or detaching the
 * monitor fd - on sustained inactivity (the source genuinely stopped
 * producing data), a setup failure, or when the caller starts a fresh
 * probe for a different pid/codec/source (see matches()).
 */
class eDVBAudioChannelDetector : public iObject, public sigc::trackable
{
	DECLARE_REF(eDVBAudioChannelDetector);
public:
	// Keep in sync with eDVBServicePMTHandler::program::audioStream::type
	// (lib/dvb/pmtparse.h) via codecFromStreamType(). DTS/DTS-HD/LPCM/DRA/
	// AC4 are intentionally excluded - unsupported, no probing attempted.
	enum { ctUnsupported = -1, ctMPEG, ctAC3, ctEAC3, ctAAC };

	eDVBAudioChannelDetector();
	~eDVBAudioChannelDetector();

	// True if this probe already covers the given pid/codec/source identity,
	// i.e. no need to start a new one. 'identity' distinguishes e.g. two
	// different demux instances (live vs. timeshift) using the same pid.
	bool matches(int pid, int codec, const void *identity) const;

	// Start for live DVB / local file / StreamRelay: reads PES for 'pid'
	// from 'demux'. Safe to call even if a previous probe is running; it
	// will be stopped first.
	void start(iDVBDemux *demux, int pid, int codec);

	// Start for SoftCSA: taps the post-descramble monitor fd exposed by
	// 'soft_decoder' (see eDVBSoftDecoder::setAudioMonitorFD).
	void startSoftCSA(eDVBSoftDecoder *soft_decoder, int pid, int codec);

	// Stop and release any reader/monitor fd. Safe to call repeatedly.
	void stop();

	// 0 until a channel count has been found at least once. Once settled(),
	// this keeps being updated live for as long as the probe runs: the
	// format can legitimately change on the very same pid/codec mid-stream
	// (e.g. an ad break swapping 5.1 program audio for 2.0, or vice versa,
	// with no PID/PMT change at all), so this is never a one-shot answer -
	// it always reflects the most recently detected value.
	int channels() const { return m_channels; }

	// Valid only once channels() > 0 and the codec is ctEAC3. True if the
	// most recently detected frame carries Dolby Atmos (Joint Object
	// Coding) metadata rather than plain Dolby Digital Plus - same
	// underlying acmod/lfeon signal either way, so this is a separate
	// check into the additional bitstream info, not something channels()
	// can distinguish on its own. Like channels(), kept live once settled.
	bool isAtmos() const { return m_atmos; }

	// True once channels() (and, for E-AC-3, isAtmos()) reflects a complete
	// answer for the current window. For E-AC3, channels() alone isn't
	// enough: the Atmos/JOC flag lives in addbsi, well past the
	// variable-length mixing/informational metadata that precedes it in the
	// same frame, so channels() can be known before addbsi is even in
	// reach - settled() waits for both. Becoming settled does NOT stop the
	// probe - see feed().
	bool settled() const;

	// True once the probe has genuinely given up for good (setup failure,
	// sustained inactivity, or the initial safety byte-cap with nothing
	// ever found) and torn itself down. Unlike settled(), this does NOT
	// become true just because an answer was found - a settled probe keeps
	// running indefinitely, watching for a later format change, and only
	// finished() (i.e. actually stopped) once the source itself goes away.
	bool finished() const;

	static int codecFromStreamType(int pmt_audio_type);

	// Fired each time channels()/isAtmos() changes to a new value (initial
	// detection, or a later live format change once settled()). Currently
	// unused externally - getTrackInfo() polls channels()/isAtmos()
	// directly - kept for any future push-based consumer.
	sigc::signal<void()> channelsDetected;

private:
	void reset();
	void feed(const uint8_t *data, int len);
	void tryDetect();
	void giveUp();

	void pesData(const uint8_t *data, int len);
	void monitorData(int);
	void onTimeout();

	int m_pid;
	int m_codec;
	const void *m_identity;
	bool m_softcsa;

	std::vector<uint8_t> m_data;
	int m_channels;
	bool m_atmos;
	bool m_monitoring; // true once settled() at least once - see feed()
	bool m_gaveUp;

	ePtr<iDVBPESReader> m_pes_reader;
	ePtr<eConnection> m_pes_conn;

	int m_monitor_fd[2]; // [0] = we read (main thread), [1] = handed to the recorder to write into
	ePtr<eSocketNotifier> m_notifier;
	ePtr<eDVBSoftDecoder> m_soft_decoder; // held only to detach the monitor fd again in stop()

	ePtr<eTimer> m_timeout;
};

#endif
