	/* note: this requires gstreamer 0.10.x and a big list of plugins. */
	/* it's currently hardcoded to use a big-endian alsasink as sink. */
#include <lib/base/ebase.h>
#include <lib/base/eerror.h>
#include <lib/base/init_num.h>
#include <lib/base/init.h>
#include <lib/base/nconfig.h>
#include <lib/base/object.h>
#include <lib/dvb/epgcache.h>
#include <lib/dvb/decoder.h>
#include <lib/dvb/dvb.h>
#include <lib/dvb/db.h>
#include <lib/components/file_eraser.h>
#include <lib/gui/esubtitle.h>
#include <lib/service/servicemp3.h>
#include <lib/service/servicemp3record.h>
#include <lib/service/service.h>
#ifdef HAS_SOFTWARE_HDR_DETECTION
#include <lib/service/hevc_hdr.h>
#endif
#include <lib/gdi/gpixmap.h>
#include <lib/dvb/subtitle.h>

#include <lib/base/cfile.h>

#include <string>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <vector>
#include <lib/base/estring.h>

#include <gst/gst.h>
#include <gst/pbutils/missing-plugins.h>
#include <sys/stat.h>

#define HTTP_TIMEOUT 60

/*
 * UNUSED variable from service reference is now used as buffer flag for gstreamer
 * REFTYPE:FLAGS:STYPE:SID:TSID:ONID:NS:PARENT_SID:PARENT_TSID:UNUSED
 *   D  D X X X X X X X X
 * 4097:0:1:0:0:0:0:0:0:0:URL:NAME (no buffering)
 * 4097:0:1:0:0:0:0:0:0:1:URL:NAME (buffering enabled)
 * 4097:0:1:0:0:0:0:0:0:3:URL:NAME (progressive download and buffering enabled)
 *
 * Progressive download requires buffering enabled, so it's mandatory to use flag 3 not 2
 */
typedef enum
{
	BUFFERING_ENABLED	= 0x00000001,
	PROGRESSIVE_DOWNLOAD	= 0x00000002
} eServiceMP3Flags;

/*
 * GstPlayFlags flags from playbin2. It is the policy of GStreamer to
 * not publicly expose element-specific enums. That's why this
 * GstPlayFlags enum has been copied here.
 */
typedef enum
{
	GST_PLAY_FLAG_VIDEO         = (1 << 0),
	GST_PLAY_FLAG_AUDIO         = (1 << 1),
	GST_PLAY_FLAG_TEXT          = (1 << 2),
	GST_PLAY_FLAG_VIS           = (1 << 3),
	GST_PLAY_FLAG_SOFT_VOLUME   = (1 << 4),
	GST_PLAY_FLAG_NATIVE_AUDIO  = (1 << 5),
	GST_PLAY_FLAG_NATIVE_VIDEO  = (1 << 6),
	GST_PLAY_FLAG_DOWNLOAD      = (1 << 7),
	GST_PLAY_FLAG_BUFFERING     = (1 << 8),
	GST_PLAY_FLAG_DEINTERLACE   = (1 << 9),
	GST_PLAY_FLAG_SOFT_COLORBALANCE = (1 << 10),
	GST_PLAY_FLAG_FORCE_FILTERS = (1 << 11),
} GstPlayFlags;

namespace
{

struct EAC3AtmosBitReader
{
	const guint8 *data;
	gsize size;
	gsize bitpos;
	bool swap16;
	bool ok;

	EAC3AtmosBitReader(const guint8 *d, gsize s, bool swap)
		: data(d), size(s), bitpos(0), swap16(swap), ok(true)
	{
	}

	guint read(guint bits)
	{
		if (!ok || bits > 32 || bitpos + bits > size * 8)
		{
			ok = false;
			return 0;
		}

		guint value = 0;
		for (guint i = 0; i < bits; ++i)
		{
			gsize bytepos = bitpos >> 3;
			if (swap16)
			{
				gsize swapped = bytepos ^ 1;
				if (swapped >= size)
				{
					ok = false;
					return 0;
				}
				bytepos = swapped;
			}
			value = (value << 1) | ((data[bytepos] >> (7 - (bitpos & 7))) & 1);
			++bitpos;
		}
		return value;
	}

	void skip(guint bits)
	{
		if (!ok || bitpos + bits > size * 8)
			ok = false;
		else
			bitpos += bits;
	}
};

bool parseEAC3AtmosFrame(const guint8 *data, gsize size, bool swap16, guint &frame_size, bool &atmos)
{
	frame_size = 0;
	atmos = false;

	if (!data || size < 7)
		return false;

	EAC3AtmosBitReader br(data, size, swap16);
	if (br.read(16) != 0x0b77)
		return false;

	const guint frame_type = br.read(2);
	const guint substreamid = br.read(3);
	frame_size = (br.read(11) + 1) << 1;
	const guint sr_code = br.read(2);

	guint num_blocks = 6;
	if (sr_code == 3)
	{
		const guint sr_code2 = br.read(2);
		if (sr_code2 == 3)
			return false;
	}
	else
	{
		static const guint blocks[4] = { 1, 2, 3, 6 };
		num_blocks = blocks[br.read(2)];
	}

	const guint channel_mode = br.read(3);
	const bool lfe_on = br.read(1) != 0;

	/* Match FFmpeg's E-AC-3 header validity checks. */
	if (!br.ok || frame_type == 3 || substreamid != 0 ||
		frame_size < 7 || frame_size > size)
		return false;

	const guint bitstream_id = br.read(5);
	if (!br.ok || bitstream_id <= 10 || bitstream_id > 16)
		return false;

	/* volume control parameters */
	for (guint i = 0; i < (channel_mode ? 1U : 2U); ++i)
	{
		br.skip(5); /* dialnorm */
		if (br.read(1))
			br.skip(8); /* compression */
	}

	/* dependent stream channel map */
	if (frame_type == 1)
	{
		if (br.read(1))
			br.skip(16);
	}

	/* mixing metadata */
	if (br.read(1))
	{
		if (channel_mode > 2)
		{
			br.skip(2); /* preferred downmix */
			if (channel_mode & 1)
				br.skip(6); /* center mix levels */
			if (channel_mode & 4)
				br.skip(6); /* surround mix levels */
		}

		if (lfe_on && br.read(1))
			br.skip(5);

		if (frame_type == 0)
		{
			for (guint i = 0; i < (channel_mode ? 1U : 2U); ++i)
			{
				if (br.read(1))
					br.skip(6);
			}

			if (br.read(1))
				br.skip(6);

			switch (br.read(2))
			{
				case 1:
					br.skip(5);
					break;
				case 2:
					br.skip(12);
					break;
				case 3:
				{
					const guint mix_data_size = (br.read(5) + 2) << 3;
					br.skip(mix_data_size);
					break;
				}
				default:
					break;
			}

			if (channel_mode < 2)
			{
				for (guint i = 0; i < (channel_mode ? 1U : 2U); ++i)
				{
					if (br.read(1))
						br.skip(14);
				}
			}

			if (br.read(1))
			{
				for (guint i = 0; i < num_blocks; ++i)
				{
					if (num_blocks == 1 || br.read(1))
						br.skip(5);
				}
			}
		}
	}

	/* informational metadata */
	if (br.read(1))
	{
		br.skip(3); /* bsmod */
		br.skip(2); /* copyright + original */

		if (channel_mode == 2)
			br.skip(4);
		if (channel_mode >= 6)
			br.skip(2);

		for (guint i = 0; i < (channel_mode ? 1U : 2U); ++i)
		{
			if (br.read(1))
				br.skip(8);
		}

		if (sr_code != 3)
			br.skip(1);
	}

	if (frame_type == 0 && num_blocks != 6)
		br.skip(1); /* converter sync */

	if (frame_type == 2)
	{
		bool have_original_size = num_blocks == 6;
		if (!have_original_size)
			have_original_size = br.read(1) != 0;
		if (have_original_size)
			br.skip(6);
	}

	if (!br.ok)
		return false;

	/* additional bitstream info */
	if (br.read(1))
	{
		const guint addbsil = br.read(6);
		if (!br.ok || addbsil > 63)
			return false;

		br.skip(7);
		atmos = br.ok && br.read(1) != 0;
	}

	return br.ok;
}

guint8 ac3LogicalByte(const guint8 *data, gsize pos, bool swap16)
{
	return swap16 ? data[pos ^ 1] : data[pos];
}

guint ac3CoreFrameSize(const guint8 *data, gsize size, bool swap16)
{
	if (!data || size < 7 ||
		ac3LogicalByte(data, 0, swap16) != 0x0b ||
		ac3LogicalByte(data, 1, swap16) != 0x77)
		return 0;

	const guint8 fscod_frmsizecod = ac3LogicalByte(data, 4, swap16);
	const guint fscod = fscod_frmsizecod >> 6;
	const guint frame_size_code = fscod_frmsizecod & 0x3f;
	const guint bitstream_id = ac3LogicalByte(data, 5, swap16) >> 3;

	if (bitstream_id > 10 || fscod == 3 || frame_size_code > 37)
		return 0;

	static const guint bitrates[19] = {
		32, 40, 48, 56, 64, 80, 96, 112, 128, 160,
		192, 224, 256, 320, 384, 448, 512, 576, 640
	};
	const guint bitrate = bitrates[frame_size_code >> 1];

	switch (fscod)
	{
		case 0: /* 48 kHz */
			return bitrate * 4;
		case 1: /* 44.1 kHz */
			return (((bitrate * 320) / 147) + (frame_size_code & 1)) * 2;
		case 2: /* 32 kHz */
			return bitrate * 6;
		default:
			return 0;
	}
}

bool eac3FrameSetHasAtmos(const guint8 *data, gsize size, bool swap16)
{
	gsize offset = 0;

	/*
	 * Some E-AC-3 container packets begin with an AC-3-compatible core
	 * syncframe followed by the E-AC-3 extension. FFmpeg identifies the
	 * core by bsid <= 10. Skip it by its declared AC-3 frame size, then
	 * inspect only subsequent real E-AC-3 frame boundaries.
	 */
	for (guint frame = 0; frame < 8 && offset + 7 <= size; ++frame)
	{
		const guint8 byte5 = ac3LogicalByte(data + offset, 5, swap16);
		const guint bitstream_id = byte5 >> 3;

		if (bitstream_id <= 10)
		{
			const guint frame_size = ac3CoreFrameSize(data + offset, size - offset, swap16);
			if (!frame_size || frame_size > size - offset)
				break;

			offset += frame_size;
			continue;
		}

		guint frame_size = 0;
		bool atmos = false;
		if (!parseEAC3AtmosFrame(data + offset, size - offset, swap16, frame_size, atmos))
			break;

		if (atmos)
			return true;

		if (!frame_size || frame_size > size - offset)
			break;

		offset += frame_size;
	}

	return false;
}

/*
 * E-AC-3 Atmos/JOC detection follows FFmpeg's flag_ec3_extension_type_a.
 * Accept only a real framed stream beginning at the buffer boundary (or an
 * IEC61937 burst payload), then walk any concatenated dependent syncframes by
 * their declared frame_size.
 */
bool eac3FrameHasAtmos(const guint8 *data, gsize size)
{
	if (!data || size < 7)
		return false;

	if (data[0] == 0x0b && data[1] == 0x77)
		return eac3FrameSetHasAtmos(data, size, false);

	if (data[0] == 0x77 && data[1] == 0x0b)
		return eac3FrameSetHasAtmos(data, size, true);

	/* IEC61937 little-endian preamble followed by word-swapped E-AC-3. */
	if (size > 15 &&
		data[0] == 0x72 && data[1] == 0xf8 &&
		data[2] == 0x1f && data[3] == 0x4e &&
		data[8] == 0x77 && data[9] == 0x0b)
		return eac3FrameSetHasAtmos(data + 8, size - 8, true);

	/* IEC61937 big-endian form. */
	if (size > 15 &&
		data[0] == 0xf8 && data[1] == 0x72 &&
		data[2] == 0x4e && data[3] == 0x1f &&
		data[8] == 0x0b && data[9] == 0x77)
		return eac3FrameSetHasAtmos(data + 8, size - 8, false);

	return false;
}

struct EAC3AtmosProbeData
{
	int stream;
	guint buffers;
};

void freeEAC3AtmosProbeData(gpointer data)
{
	delete static_cast<EAC3AtmosProbeData*>(data);
}

GstPadProbeReturn eac3AtmosProbe(GstPad *pad, GstPadProbeInfo *info, gpointer user_data)
{
	EAC3AtmosProbeData *probe = static_cast<EAC3AtmosProbeData*>(user_data);
	GstBuffer *buffer = GST_PAD_PROBE_INFO_BUFFER(info);

	if (!probe || !buffer)
		return GST_PAD_PROBE_OK;

	++probe->buffers;

	GstMapInfo map;
	bool detected = false;
	if (gst_buffer_map(buffer, &map, GST_MAP_READ))
	{
		detected = eac3FrameHasAtmos(map.data, map.size);
		gst_buffer_unmap(buffer, &map);
	}

	if (detected)
	{
		eDebug("[eServiceMP3] E-AC3 Atmos/JOC detected on audio stream %d", probe->stream);

		GstObject *parent = gst_pad_get_parent(pad);
		if (parent && GST_IS_ELEMENT(parent))
		{
			GstStructure *event = gst_structure_new("eventAtmosDetected",
				"stream", G_TYPE_INT, probe->stream,
				NULL);
			gst_element_post_message(GST_ELEMENT(parent),
				gst_message_new_element(parent, event));
		}
		if (parent)
			gst_object_unref(parent);

		return GST_PAD_PROBE_REMOVE;
	}

	if (probe->buffers >= 64)
		return GST_PAD_PROBE_REMOVE;

	return GST_PAD_PROBE_OK;
}

GQuark eac3AtmosProbeQuark()
{
	static GQuark quark = g_quark_from_static_string("enigma2-eac3-atmos-probe");
	return quark;
}


struct DTSHDProbeData
{
	int stream;
	guint buffers;
	std::string codec;

	explicit DTSHDProbeData(int s)
		: stream(s), buffers(0)
	{
	}
};

void freeDTSHDProbeData(gpointer data)
{
	delete static_cast<DTSHDProbeData*>(data);
}

/*
 * DTS-HD MA carries the full channel count in the XLL lossless header.
 * GStreamer may expose only the embedded DTS core count (normally 5.1), so
 * read the XLL metadata directly from the compressed buffer.
 *
 * XLL layout follows FFmpeg's dca_xll parser: the common header declares up
 * to three channel sets, and each byte-aligned channel-set sub-header starts
 * with its byte size and a 4-bit (channels - 1) field.  Multi-set streams
 * form a hierarchy; accumulate their channels while validating the early
 * header fields FFmpeg requires for that hierarchy.  If anything is unclear,
 * return 0 and leave the existing negotiated caps value untouched.
 */
guint detectDTSXLLChannels(const guint8 *data, gsize size)
{
	if (!data || size < 8)
		return 0;

	for (gsize n = 0; n + 7 < size; ++n)
	{
		const guint32 word = (guint32(data[n]) << 24) | (guint32(data[n + 1]) << 16) |
			(guint32(data[n + 2]) << 8) | guint32(data[n + 3]);
		if (word != 0x41a29547)
			continue;

		EAC3AtmosBitReader br(data + n, size - n, false);
		if (br.read(32) != 0x41a29547)
			continue;

		const guint stream_version = br.read(4) + 1;
		const guint common_header_size = br.read(8) + 1;
		const guint frame_size_nbits = br.read(5) + 1;
		if (!br.ok || stream_version != 1 || frame_size_nbits > 32)
			continue;

		const guint frame_size = br.read(frame_size_nbits) + 1;
		const guint channel_sets = br.read(4) + 1;
		if (!br.ok || channel_sets < 1 || channel_sets > 3 ||
			common_header_size > size - n || frame_size < common_header_size ||
			frame_size > (240U << 10))
			continue;

		gsize sub_offset = common_header_size;
		guint total_channels = 0;
		bool valid = true;

		for (guint set = 0; set < channel_sets; ++set)
		{
			if (sub_offset >= size - n || size - n - sub_offset < 2)
			{
				valid = false;
				break;
			}

			const gsize sub_size = size - n - sub_offset;
			EAC3AtmosBitReader chbr(data + n + sub_offset, sub_size, false);
			const guint channel_header_size = chbr.read(10) + 1;
			const guint channels = chbr.read(4) + 1;
			if (!chbr.ok || channel_header_size > sub_size || channels < 1 || channels > 8 ||
				total_channels + channels > 8)
			{
				valid = false;
				break;
			}

			/* Fields before the hierarchy flag in FFmpeg's chs_parse_header(). */
			chbr.skip(channels); /* residual_encode */
			chbr.skip(5);        /* pcm_bit_res */
			chbr.skip(5);        /* storage_bit_res */
			chbr.skip(4);        /* sampling frequency */
			const guint freq_modifier = chbr.read(2);
			const guint replacement_set = chbr.read(2);
			if (!chbr.ok || freq_modifier != 0 || replacement_set != 0)
			{
				valid = false;
				break;
			}

			if (channel_sets > 1)
			{
				const bool primary = chbr.read(1) != 0;
				const bool dmix_present = chbr.read(1) != 0;
				if (dmix_present)
				{
					chbr.read(1); /* dmix_embedded */
					if (primary)
						chbr.skip(3); /* dmix_type */
				}
				const bool hierarchy = chbr.read(1) != 0;
				if (!chbr.ok || primary != (set == 0) || !hierarchy)
				{
					valid = false;
					break;
				}
			}

			total_channels += channels;
			sub_offset += channel_header_size;
		}

		if (valid && total_channels >= 1 && total_channels <= 8)
			return total_channels;
	}

	return 0;
}

const char *detectDTSProfile(const guint8 *data, gsize size)
{
	bool exss = false;
	bool xll = false;
	bool xbr = false;
	bool xch = false;
	bool xxch = false;
	bool x96 = false;
	bool lbr = false;
	bool dtsx = false;
	bool dtsx_imax = false;

	for (gsize n = 0; n + 3 < size; ++n)
	{
		const guint32 word = (guint32(data[n]) << 24) | (guint32(data[n + 1]) << 16) |
			(guint32(data[n + 2]) << 8) | guint32(data[n + 3]);

		switch (word)
		{
			case 0x64582025: exss = true; break; /* DTS extension substream */
			case 0x41a29547: xll = true; break;  /* lossless / DTS-HD MA */
			case 0x655e315e: xbr = true; break;
			case 0x5a5a5a5a: xch = true; break;   /* core XCH / DTS-ES */
			case 0x47004a03: xxch = true; break;
			case 0x1d95f262: x96 = true; break;
			case 0x0a801921: lbr = true; break;  /* DTS Express */
			case 0x02000850: dtsx = true; break;
			default:
				/* FFmpeg accepts either low bit for the DTS:X IMAX marker. */
				if ((word >> 1) == (0xf14000d0U >> 1))
					dtsx_imax = true;
				break;
		}
	}

	/*
	 * Match FFmpeg's DTS profile rules:
	 * core XCH/XXCH is DTS-ES and core X96 is DTS 96/24;
	 * XLL is DTS-HD MA; XBR/XXCH/X96 in EXSS are DTS-HD HRA;
	 * LBR is DTS Express. DTS:X markers are XLL extensions.
	 */
	if (xll && dtsx_imax)
		return "DTS-HD MA + DTS:X IMAX";
	if (xll && dtsx)
		return "DTS-HD MA + DTS:X";
	if (xll)
		return "DTS-HD MA";
	if (exss && (xbr || xxch || x96))
		return "DTS-HD HRA";
	if (exss && lbr)
		return "DTS Express";
	if (!exss && (xch || xxch))
		return "DTS-ES";
	if (!exss && x96)
		return "DTS 96/24";

	return NULL;
}

GstPadProbeReturn dtsHDProbe(GstPad *pad, GstPadProbeInfo *info, gpointer user_data)
{
	DTSHDProbeData *probe = static_cast<DTSHDProbeData*>(user_data);
	GstBuffer *buffer = GST_PAD_PROBE_INFO_BUFFER(info);
	if (!probe || !buffer)
		return GST_PAD_PROBE_OK;

	++probe->buffers;

	const char *detected_codec = NULL;
	guint channels = 0;
	GstMapInfo map;
	if (gst_buffer_map(buffer, &map, GST_MAP_READ))
	{
		detected_codec = detectDTSProfile(map.data, map.size);
		if (detected_codec)
			probe->codec = detected_codec;
		if (!probe->codec.empty() && !strncmp(probe->codec.c_str(), "DTS-HD MA", 9))
			channels = detectDTSXLLChannels(map.data, map.size);
		gst_buffer_unmap(buffer, &map);
	}

	/* For XLL, wait briefly for a buffer with a complete parsable header.
	 * Other DTS-HD profiles can be reported immediately. */
	const bool xll_profile = !probe->codec.empty() && !strncmp(probe->codec.c_str(), "DTS-HD MA", 9);
	if (!probe->codec.empty() && (!xll_profile || channels || probe->buffers >= 64))
	{
		const char *codec = probe->codec.c_str();
		if (channels)
			eDebug("[eServiceMP3] DTS profile detected on audio stream %d: %s channels=%u", probe->stream, codec, channels);
		else
			eDebug("[eServiceMP3] DTS profile detected on audio stream %d: %s (XLL channel count unavailable)", probe->stream, codec);

		GstObject *parent = gst_pad_get_parent(pad);
		if (parent && GST_IS_ELEMENT(parent))
		{
			GstStructure *event = gst_structure_new("eventDTSProfileDetected",
				"stream", G_TYPE_INT, probe->stream,
				"codec", G_TYPE_STRING, codec,
				"channels", G_TYPE_INT, (gint)channels,
				NULL);
			gst_element_post_message(GST_ELEMENT(parent),
				gst_message_new_element(parent, event));
		}
		if (parent)
			gst_object_unref(parent);

		return GST_PAD_PROBE_REMOVE;
	}

	if (probe->buffers >= 64)
		return GST_PAD_PROBE_REMOVE;

	return GST_PAD_PROBE_OK;
}

GQuark dtsHDProbeQuark()
{
	static GQuark quark = g_quark_from_static_string("enigma2-dtshd-probe");
	return quark;
}

enum HDAudioAuxMode
{
	hdAuxNone,
	hdAuxAC3
};

struct HDAudioAuxState
{
	GstElement *pipeline;
	GstElement *dvbSink;
	GstElement *mainAudioSink;
	int audioIndex;
	guint mainFlags;
	HDAudioAuxMode mode;
	bool linked;
	GMutex linkMutex;
	GCond linkCond;
};

GQuark hdAudioAuxStateQuark()
{
	static GQuark quark = g_quark_from_static_string("enigma2-hd-audio-aux");
	return quark;
}

GQuark hdAudioAuxReconfigQuark()
{
	static GQuark quark = g_quark_from_static_string("enigma2-hd-audio-aux-reconfig");
	return quark;
}

GQuark hdAudioAuxRetryBlockQuark()
{
	static GQuark quark = g_quark_from_static_string("enigma2-hd-audio-aux-retry-block");
	return quark;
}

GQuark hdAudioNativeEac3ResetPendingQuark()
{
	static GQuark quark = g_quark_from_static_string("enigma2-hd-audio-native-eac3-reset-pending");
	return quark;
}

GQuark hdAudioNativeRetryQuark()
{
	static GQuark quark = g_quark_from_static_string("enigma2-hd-audio-native-retry");
	return quark;
}

HDAudioAuxState *getHDAudioAuxState(GstElement *playbin)
{
	return playbin ? static_cast<HDAudioAuxState *>(
		g_object_get_qdata(G_OBJECT(playbin), hdAudioAuxStateQuark())) : NULL;
}

bool hdAudioAuxReconfiguring(GstElement *playbin)
{
	return playbin && GPOINTER_TO_INT(g_object_get_qdata(G_OBJECT(playbin), hdAudioAuxReconfigQuark()));
}

void setHDAudioAuxReconfiguring(GstElement *playbin, bool active)
{
	if (playbin)
		g_object_set_qdata(G_OBJECT(playbin), hdAudioAuxReconfigQuark(), GINT_TO_POINTER(active ? 1 : 0));
}

bool hdAudioAuxRetryBlocked(GstElement *playbin)
{
	return playbin && GPOINTER_TO_INT(g_object_get_qdata(G_OBJECT(playbin), hdAudioAuxRetryBlockQuark()));
}

void setHDAudioAuxRetryBlocked(GstElement *playbin, bool blocked)
{
	if (playbin)
		g_object_set_qdata(G_OBJECT(playbin), hdAudioAuxRetryBlockQuark(), GINT_TO_POINTER(blocked ? 1 : 0));
}

bool hdAudioNativeEac3ResetPending(GstElement *playbin)
{
	return playbin && GPOINTER_TO_INT(g_object_get_qdata(G_OBJECT(playbin), hdAudioNativeEac3ResetPendingQuark()));
}

void setHDAudioNativeEac3ResetPending(GstElement *playbin, bool pending)
{
	if (playbin)
		g_object_set_qdata(G_OBJECT(playbin), hdAudioNativeEac3ResetPendingQuark(), GINT_TO_POINTER(pending ? 1 : 0));
}

int hdAudioNativeRetry(GstElement *playbin)
{
	return playbin ? GPOINTER_TO_INT(g_object_get_qdata(G_OBJECT(playbin), hdAudioNativeRetryQuark())) - 1 : -1;
}

void setHDAudioNativeRetry(GstElement *playbin, int stream)
{
	if (playbin)
		g_object_set_qdata(G_OBJECT(playbin), hdAudioNativeRetryQuark(), stream >= 0 ? GINT_TO_POINTER(stream + 1) : NULL);
}

gint hdAudioAuxMatchSinkType(const GValue *velement, gpointer user_data)
{
	GstElement *element = GST_ELEMENT_CAST(g_value_get_object(velement));
	const gchar *type = static_cast<const gchar *>(user_data);
	return element && type ? strcmp(g_type_name(G_OBJECT_TYPE(element)), type) : 1;
}

GstElement *findHDAudioMainSink(GstElement *playbin)
{
	if (!playbin || !GST_IS_BIN(playbin))
		return NULL;
	GstIterator *children = gst_bin_iterate_recurse(GST_BIN(playbin));
	GValue result = G_VALUE_INIT;
	GstElement *sink = NULL;
	if (children && gst_iterator_find_custom(children, (GCompareFunc)hdAudioAuxMatchSinkType,
		&result, (gpointer)"GstDVBAudioSink"))
	{
		sink = GST_ELEMENT_CAST(g_value_dup_object(&result));
		g_value_unset(&result);
	}
	if (children)
		gst_iterator_free(children);
	return sink;
}

GstElement *quiesceHDAudioMainSink(GstElement *playbin)
{
	GstElement *sink = findHDAudioMainSink(playbin);
	if (!sink)
		return NULL;

	gst_element_set_locked_state(sink, TRUE);
	GstStateChangeReturn set_ret = gst_element_set_state(sink, GST_STATE_NULL);
	GstState state = GST_STATE_VOID_PENDING, pending = GST_STATE_VOID_PENDING;
	gst_element_get_state(sink, &state, &pending, 2 * GST_SECOND);
	if (set_ret == GST_STATE_CHANGE_FAILURE || state != GST_STATE_NULL)
	{
		gst_element_set_locked_state(sink, FALSE);
		gst_element_sync_state_with_parent(sink);
		gst_object_unref(sink);
		return NULL;
	}
	return sink;
}

void restoreHDAudioMainSink(GstElement *playbin, GstElement *sink, guint flags)
{
	if (!playbin)
		return;
	g_object_set(G_OBJECT(playbin), "flags", flags, NULL);
	if (sink)
	{
		gst_element_set_locked_state(sink, FALSE);
		gst_element_sync_state_with_parent(sink);
	}
}

HDAudioAuxMode hdAudioAuxModeForCodec(const std::string &codec)
{
	if (codec.find("TrueHD") != std::string::npos)
		return eConfigManager::getConfigValue("config.av.truehd_playback") == "ac3" ? hdAuxAC3 : hdAuxNone;
	if (codec.compare(0, 3, "DTS") == 0)
		return eConfigManager::getConfigValue("config.av.dts_playback") == "ac3" ? hdAuxAC3 : hdAuxNone;
	return hdAuxNone;
}

GstBusSyncReply hdAudioAuxBusSync(GstBus *, GstMessage *, gpointer)
{
	return GST_BUS_DROP;
}

gint hdAudioAuxSelectStream(GstElement *, GstStreamCollection *collection, GstStream *stream, gpointer user_data)
{
	HDAudioAuxState *state = static_cast<HDAudioAuxState *>(user_data);
	if (!state || !stream || !(gst_stream_get_stream_type(stream) & GST_STREAM_TYPE_AUDIO))
		return 0;

	int audio_ordinal = 0;
	const guint size = gst_stream_collection_get_size(collection);
	for (guint n = 0; n < size; ++n)
	{
		GstStream *candidate = gst_stream_collection_get_stream(collection, n);
		if (!candidate || !(gst_stream_get_stream_type(candidate) & GST_STREAM_TYPE_AUDIO))
			continue;
		if (candidate == stream)
			return audio_ordinal == state->audioIndex ? 1 : 0;
		++audio_ordinal;
	}
	return 0;
}

void hdAudioAuxPadAdded(GstElement *, GstPad *pad, gpointer user_data)
{
	HDAudioAuxState *state = static_cast<HDAudioAuxState *>(user_data);
	if (!state || state->linked)
		return;

	GstCaps *caps = gst_pad_get_current_caps(pad);
	if (!caps)
		caps = gst_pad_query_caps(pad, NULL);
	const GstStructure *structure = caps && gst_caps_get_size(caps) ? gst_caps_get_structure(caps, 0) : NULL;
	const gchar *name = structure ? gst_structure_get_name(structure) : NULL;
	if (!name || g_strcmp0(name, "audio/x-raw"))
	{
		if (caps) gst_caps_unref(caps);
		return;
	}

	GstElement *queue = gst_bin_get_by_name(GST_BIN(state->pipeline), "hdaudio_aux_queue");
	GstPad *sink_pad = queue ? gst_element_get_static_pad(queue, "sink") : NULL;
	const GstPadLinkReturn link_ret = sink_pad ? gst_pad_link(pad, sink_pad) : GST_PAD_LINK_REFUSED;
	g_mutex_lock(&state->linkMutex);
	state->linked = link_ret == GST_PAD_LINK_OK;
	if (state->linked)
		g_cond_broadcast(&state->linkCond);
	g_mutex_unlock(&state->linkMutex);
	if (sink_pad) gst_object_unref(sink_pad);
	if (queue) gst_object_unref(queue);
	if (caps) gst_caps_unref(caps);
}

void stopHDAudioAuxPipeline(GstElement *playbin, bool restore_main_audio)
{
	HDAudioAuxState *state = getHDAudioAuxState(playbin);
	if (!state)
		return;

	g_object_set_qdata(G_OBJECT(playbin), hdAudioAuxStateQuark(), NULL);
	if (state->dvbSink)
		gst_element_set_locked_state(state->dvbSink, FALSE);
	gst_element_set_state(state->pipeline, GST_STATE_NULL);
	GstState null_state = GST_STATE_VOID_PENDING, null_pending = GST_STATE_VOID_PENDING;
	gst_element_get_state(state->pipeline, &null_state, &null_pending, 2 * GST_SECOND);

	GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE(state->pipeline));
	if (bus)
	{
		gst_bus_set_sync_handler(bus, NULL, NULL, NULL);
		gst_object_unref(bus);
	}
	gst_object_unref(state->pipeline);

	if (restore_main_audio)
		restoreHDAudioMainSink(playbin, state->mainAudioSink, state->mainFlags);
	if (state->mainAudioSink)
		gst_object_unref(state->mainAudioSink);
	g_cond_clear(&state->linkCond);
	g_mutex_clear(&state->linkMutex);
	delete state;
}

bool prepareHDAudioAuxPipeline(GstElement *playbin, const gchar *uri, int audio_index,
	HDAudioAuxMode mode, int source_channels, guint main_flags, gint64 position_ns,
	GstElement *main_audio_sink)
{
	if (!playbin || !uri || mode == hdAuxNone)
		return false;

	GstElement *pipeline = gst_pipeline_new("enigma2_hdaudio_aux_pipeline");
	GstElement *decode = gst_element_factory_make("uridecodebin3", "hdaudio_aux_decode");
	GstElement *queue = gst_element_factory_make("queue", "hdaudio_aux_queue");
	GstElement *convert = gst_element_factory_make("audioconvert", "hdaudio_aux_convert");
	GstElement *resample = gst_element_factory_make("audioresample", "hdaudio_aux_resample");
	GstElement *raw_capsfilter = gst_element_factory_make("capsfilter", "hdaudio_aux_raw_caps");
	GstElement *encoder = gst_element_factory_make("avenc_ac3", "hdaudio_aux_encoder");
	GstElement *parser = gst_element_factory_make("ac3parse", "hdaudio_aux_parser");
	GstElement *out_capsfilter = gst_element_factory_make("capsfilter", "hdaudio_aux_output_caps");
	GstElement *dvb_sink = gst_element_factory_make("dvbaudiosink", "enigma2_hdaudio_aux_dvb_sink");

	if (!pipeline || !decode || !queue || !convert || !resample || !raw_capsfilter ||
		!encoder || !parser || !out_capsfilter || !dvb_sink)
	{
		if (pipeline) gst_object_unref(pipeline);
		if (decode) gst_object_unref(decode);
		if (queue) gst_object_unref(queue);
		if (convert) gst_object_unref(convert);
		if (resample) gst_object_unref(resample);
		if (raw_capsfilter) gst_object_unref(raw_capsfilter);
		if (encoder) gst_object_unref(encoder);
		if (parser) gst_object_unref(parser);
		if (out_capsfilter) gst_object_unref(out_capsfilter);
		if (dvb_sink) gst_object_unref(dvb_sink);
		return false;
	}

	const guint64 channel_mask = G_GUINT64_CONSTANT(0x003f);
	GstCaps *raw_caps = gst_caps_new_simple("audio/x-raw",
		"format", G_TYPE_STRING, "F32LE",
		"layout", G_TYPE_STRING, "interleaved",
		"rate", G_TYPE_INT, 48000,
		"channels", G_TYPE_INT, 6,
		"channel-mask", GST_TYPE_BITMASK, channel_mask,
		NULL);
	GstCaps *out_caps = gst_caps_new_simple("audio/x-ac3",
		"framed", G_TYPE_BOOLEAN, TRUE,
		"alignment", G_TYPE_STRING, "frame",
		"rate", G_TYPE_INT, 48000,
		"channels", G_TYPE_INT, 6,
		NULL);
	if (!raw_caps || !out_caps)
	{
		if (raw_caps) gst_caps_unref(raw_caps);
		if (out_caps) gst_caps_unref(out_caps);
		gst_object_unref(pipeline);
		gst_object_unref(decode); gst_object_unref(queue); gst_object_unref(convert);
		gst_object_unref(resample); gst_object_unref(raw_capsfilter); gst_object_unref(encoder);
		gst_object_unref(parser); gst_object_unref(out_capsfilter); gst_object_unref(dvb_sink);
		return false;
	}

	GstPad *dvb_pad = gst_element_get_static_pad(dvb_sink, "sink");
	GstCaps *accepted = dvb_pad ? gst_pad_query_caps(dvb_pad, out_caps) : NULL;
	const bool accepted_output = accepted && !gst_caps_is_empty(accepted);
	if (accepted) gst_caps_unref(accepted);
	if (dvb_pad) gst_object_unref(dvb_pad);
	if (!accepted_output)
	{
		gst_caps_unref(raw_caps); gst_caps_unref(out_caps);
		gst_object_unref(pipeline);
		gst_object_unref(decode); gst_object_unref(queue); gst_object_unref(convert);
		gst_object_unref(resample); gst_object_unref(raw_capsfilter); gst_object_unref(encoder);
		gst_object_unref(parser); gst_object_unref(out_capsfilter); gst_object_unref(dvb_sink);
		return false;
	}

	g_object_set(G_OBJECT(raw_capsfilter), "caps", raw_caps, NULL);
	g_object_set(G_OBJECT(out_capsfilter), "caps", out_caps, NULL);
	gst_caps_unref(raw_caps);
	gst_caps_unref(out_caps);
	if (g_object_class_find_property(G_OBJECT_GET_CLASS(encoder), "bitrate"))
		g_object_set(G_OBJECT(encoder), "bitrate", 640000, NULL);
	g_object_set(G_OBJECT(decode), "uri", uri, NULL);
	(void)source_channels;
	(void)position_ns;

	HDAudioAuxState *state = new HDAudioAuxState();
	state->pipeline = pipeline;
	state->dvbSink = dvb_sink;
	state->mainAudioSink = main_audio_sink ? GST_ELEMENT(gst_object_ref(main_audio_sink)) : NULL;
	state->audioIndex = audio_index;
	state->mainFlags = main_flags;
	state->mode = mode;
	state->linked = false;
	g_mutex_init(&state->linkMutex);
	g_cond_init(&state->linkCond);
	g_signal_connect(G_OBJECT(decode), "select-stream", G_CALLBACK(hdAudioAuxSelectStream), state);
	g_signal_connect(G_OBJECT(decode), "pad-added", G_CALLBACK(hdAudioAuxPadAdded), state);

	gst_bin_add_many(GST_BIN(pipeline), decode, queue, convert, resample, raw_capsfilter,
		encoder, parser, out_capsfilter, dvb_sink, NULL);
	if (!gst_element_link_many(queue, convert, resample, raw_capsfilter,
		encoder, parser, out_capsfilter, dvb_sink, NULL))
	{
		gst_object_unref(pipeline);
		if (state->mainAudioSink) gst_object_unref(state->mainAudioSink);
		g_cond_clear(&state->linkCond);
		g_mutex_clear(&state->linkMutex);
		delete state;
		return false;
	}

	GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE(pipeline));
	if (bus)
	{
		gst_bus_set_sync_handler(bus, hdAudioAuxBusSync, state, NULL);
		gst_object_unref(bus);
	}

	g_object_set_qdata(G_OBJECT(playbin), hdAudioAuxStateQuark(), state);
	if (gst_element_set_state(pipeline, GST_STATE_PAUSED) == GST_STATE_CHANGE_FAILURE)
	{
		stopHDAudioAuxPipeline(playbin, false);
		return false;
	}
	GstState aux_state = GST_STATE_NULL, aux_pending = GST_STATE_VOID_PENDING;
	gst_element_get_state(pipeline, &aux_state, &aux_pending, 2 * GST_SECOND);
	gst_element_set_locked_state(dvb_sink, TRUE);
	return true;
}

void setHDAudioAuxState(GstElement *playbin, GstState target)
{
	HDAudioAuxState *state = getHDAudioAuxState(playbin);
	if (state)
		gst_element_set_state(state->pipeline, target);
}

bool seekHDAudioAuxThenResetSink(GstElement *playbin, gint64 position_ns)
{
	HDAudioAuxState *state = getHDAudioAuxState(playbin);
	if (!state || !state->dvbSink || position_ns < 0)
		return false;

	if (!gst_element_seek_simple(state->pipeline, GST_FORMAT_TIME,
		(GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT), position_ns))
		return false;

	gst_element_set_locked_state(state->dvbSink, TRUE);
	GstStateChangeReturn null_ret = gst_element_set_state(state->dvbSink, GST_STATE_NULL);
	GstState sink_state = GST_STATE_VOID_PENDING, sink_pending = GST_STATE_VOID_PENDING;
	gst_element_get_state(state->dvbSink, &sink_state, &sink_pending, 250 * GST_MSECOND);
	if (null_ret == GST_STATE_CHANGE_FAILURE || sink_state != GST_STATE_NULL)
	{
		gst_element_set_locked_state(state->dvbSink, FALSE);
		gst_element_sync_state_with_parent(state->dvbSink);
		return false;
	}

	gst_element_set_locked_state(state->dvbSink, FALSE);
	return gst_element_sync_state_with_parent(state->dvbSink);
}

bool positionHDAudioAuxAfterStart(GstElement *playbin, gint64 position_ns)
{
	HDAudioAuxState *state = getHDAudioAuxState(playbin);
	if (!state)
		return false;

	g_mutex_lock(&state->linkMutex);
	if (!state->linked)
	{
		const gint64 until = g_get_monotonic_time() + G_TIME_SPAN_SECOND;
		while (!state->linked && g_cond_wait_until(&state->linkCond, &state->linkMutex, until))
			;
	}
	const bool linked = state->linked;
	g_mutex_unlock(&state->linkMutex);
	if (!linked)
		return false;

	if (position_ns < 500 * GST_MSECOND)
	{
		gst_element_set_locked_state(state->dvbSink, FALSE);
		return gst_element_sync_state_with_parent(state->dvbSink);
	}
	return seekHDAudioAuxThenResetSink(playbin, position_ns);
}

bool seekHDAudioAuxPersistent(GstElement *playbin, gint64 position_ns)
{
	HDAudioAuxState *state = getHDAudioAuxState(playbin);
	if (!state || position_ns < 0)
		return false;

	const bool already_reconfiguring = hdAudioAuxReconfiguring(playbin);
	if (!already_reconfiguring)
		setHDAudioAuxReconfiguring(playbin, true);
	const gboolean seek_ok = gst_element_seek_simple(state->pipeline, GST_FORMAT_TIME,
		(GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT), position_ns);
	if (!already_reconfiguring)
		setHDAudioAuxReconfiguring(playbin, false);
	return seek_ok;
}

} // namespace


// eServiceFactoryMP3

/*
 * gstreamer suffers from a bug causing sparse streams to loose sync, after pause/resume / skip
 * see: https://bugzilla.gnome.org/show_bug.cgi?id=619434
 * As a workaround, we run the subsink in sync=false mode
 */
#undef GSTREAMER_SUBTITLE_SYNC_MODE_BUG
/**/

eServiceFactoryMP3::eServiceFactoryMP3()
{
	ePtr<eServiceCenter> sc;

	eServiceCenter::getPrivInstance(sc);
	if (sc)
	{
		std::list<std::string> extensions;
		extensions.push_back("dtshd");
		extensions.push_back("dts");
		extensions.push_back("mp3");
		extensions.push_back("wav");
		extensions.push_back("wave");
		extensions.push_back("oga");
		extensions.push_back("ogg");
		extensions.push_back("flac");
		extensions.push_back("m4a");
		extensions.push_back("mp2");
		extensions.push_back("m2a");
		extensions.push_back("wma");
		extensions.push_back("eac3");
		extensions.push_back("ac3");
		extensions.push_back("mka");
		extensions.push_back("aache");
		extensions.push_back("aac");
		extensions.push_back("ape");
		extensions.push_back("alac");
		extensions.push_back("mpg");
		extensions.push_back("vob");
		extensions.push_back("m4v");
		extensions.push_back("mkv");
		extensions.push_back("avi");
		extensions.push_back("divx");
		extensions.push_back("dat");
		extensions.push_back("flv");
		extensions.push_back("mp4");
		extensions.push_back("mov");
		extensions.push_back("wmv");
		extensions.push_back("asf");
		extensions.push_back("3gp");
		extensions.push_back("3g2");
		extensions.push_back("mpeg");
		extensions.push_back("mpe");
		extensions.push_back("rm");
		extensions.push_back("rmvb");
		extensions.push_back("ogm");
		extensions.push_back("ogv");
		extensions.push_back("m3u8");
		extensions.push_back("stream");
		extensions.push_back("webm");
		extensions.push_back("amr");
		extensions.push_back("au");
		extensions.push_back("mid");
		extensions.push_back("wv");
		extensions.push_back("pva");
		extensions.push_back("wtv");
		sc->addServiceFactory(eServiceFactoryMP3::id, this, extensions);
	}

	m_service_info = new eStaticServiceMP3Info();
}

eServiceFactoryMP3::~eServiceFactoryMP3()
{
	ePtr<eServiceCenter> sc;

	eServiceCenter::getPrivInstance(sc);
	if (sc)
		sc->removeServiceFactory(eServiceFactoryMP3::id);
}

DEFINE_REF(eServiceFactoryMP3)

	// iServiceHandler
RESULT eServiceFactoryMP3::play(const eServiceReference &ref, ePtr<iPlayableService> &ptr)
{
		// check resources...
	ptr = new eServiceMP3(ref);
	return 0;
}

RESULT eServiceFactoryMP3::record(const eServiceReference &ref, ePtr<iRecordableService> &ptr)
{
	if (ref.path.find("://") != std::string::npos)
	{
		ptr = new eServiceMP3Record((eServiceReference&)ref);
		return 0;
	}
	ptr=0;
	return -1;
}

RESULT eServiceFactoryMP3::list(const eServiceReference &, ePtr<iListableService> &ptr)
{
	ptr=0;
	return -1;
}

RESULT eServiceFactoryMP3::info(const eServiceReference &ref, ePtr<iStaticServiceInformation> &ptr)
{
	ptr = m_service_info;
	return 0;
}

class eMP3ServiceOfflineOperations: public iServiceOfflineOperations
{
	DECLARE_REF(eMP3ServiceOfflineOperations);
	eServiceReference m_ref;
public:
	eMP3ServiceOfflineOperations(const eServiceReference &ref);

	RESULT deleteFromDisk(int simulate);
	RESULT getListOfFilenames(std::list<std::string> &);
	RESULT reindex();
};

DEFINE_REF(eMP3ServiceOfflineOperations);

eMP3ServiceOfflineOperations::eMP3ServiceOfflineOperations(const eServiceReference &ref): m_ref((const eServiceReference&)ref)
{
}

RESULT eMP3ServiceOfflineOperations::deleteFromDisk(int simulate)
{
	if (!simulate)
	{
		std::list<std::string> res;
		if (getListOfFilenames(res))
			return -1;

		eBackgroundFileEraser *eraser = eBackgroundFileEraser::getInstance();
		if (!eraser)
			eDebug("[eMP3ServiceOfflineOperations] FATAL !! can't get background file eraser");

		for (std::list<std::string>::iterator i(res.begin()); i != res.end(); ++i)
		{
			eDebug("[eMP3ServiceOfflineOperations] Removing %s...", i->c_str());
			if (eraser)
				eraser->erase(i->c_str());
			else
				::unlink(i->c_str());
		}
	}
	return 0;
}

RESULT eMP3ServiceOfflineOperations::getListOfFilenames(std::list<std::string> &res)
{
	res.clear();
	res.push_back(m_ref.path);
	return 0;
}

RESULT eMP3ServiceOfflineOperations::reindex()
{
	return -1;
}


RESULT eServiceFactoryMP3::offlineOperations(const eServiceReference &ref, ePtr<iServiceOfflineOperations> &ptr)
{
	ptr = new eMP3ServiceOfflineOperations(ref);
	return 0;
}

// eStaticServiceMP3Info


// eStaticServiceMP3Info is seperated from eServiceMP3 to give information
// about unopened files.

// probably eServiceMP3 should use this class as well, and eStaticServiceMP3Info
// should have a database backend where ID3-files etc. are cached.
// this would allow listing the mp3 database based on certain filters.

DEFINE_REF(eStaticServiceMP3Info)

eStaticServiceMP3Info::eStaticServiceMP3Info()
{
}

RESULT eStaticServiceMP3Info::getName(const eServiceReference &ref, std::string &name)
{
	if (ref.name.length())
		name = ref.name;
	else
	{
		if (endsWith(ref.path, ".stream") && !m_parser.parseMeta(ref.path)) {
			name = m_parser.m_name;
			return 0;
		}
		size_t last = ref.path.rfind('/');
		if (last != std::string::npos)
			name = ref.path.substr(last+1);
		else
			name = ref.path;
	}

	return 0;
}


/**
 * @brief eStaticServiceMP3Info::getLength
 *
 * Retrieve the playback length (in whole seconds) for the given service reference.
 *
 * Operation:
 *  - Attempts to parse metadata via m_parser.parseMeta(ref.path). If parsing
 *    succeeds (parseMeta returns 0), uses m_parser.m_length (interpreted in
 *    MPEG timebase units) and returns m_parser.m_length / MPEG_TIMEBASE.
 *  - If parsing fails, falls back to reading a sidecar ".cuts" file at
 *    ref.path + ".cuts". The file is read as a sequence of records:
 *      [uint64_t where (big-endian)] [uint32_t what (network byte order)]
 *    For each record, if ntohl(what) == CUT_TYPE_LENGTH, returns
 *    be64toh(where) / MPEG_TIMEBASE.
 *
 * Parameters:
 *  - ref: reference to the service whose length is requested (path used for
 *         metadata parsing and .cuts filename).
 *
 * Return value:
 *  - non-negative int: length in seconds (fractional part discarded).
 *  - -1: if metadata cannot be obtained, the .cuts file cannot be opened, or
 *         no CUT_TYPE_LENGTH entry is found.
 *
 * Notes:
 *  - MPEG_TIMEBASE is 90000.
 *  - The function performs file I/O and endian conversions (ntohl, be64toh).
 */
int eStaticServiceMP3Info::getLength(const eServiceReference& ref) {
	constexpr int MPEG_TIMEBASE = 90000;

	eDebug("[eStaticServiceMP3Info] getLength called for ref: %s", ref.path.c_str());
	if (m_parser.parseMeta(ref.path) == 0)
		return static_cast<int>(m_parser.m_length / MPEG_TIMEBASE);

	/* Fallback: read CUT_TYPE_LENGTH from .cuts file */
	std::string filename = ref.path + ".cuts";
	std::ifstream file(filename, std::ios::binary);

	if (!file)
		return -1;

	uint64_t where;
	uint32_t what;

	while (file.read(reinterpret_cast<char*>(&where), sizeof(where)) && file.read(reinterpret_cast<char*>(&what), sizeof(what))) {
		if (ntohl(what) == 5) // CUT_TYPE_LENGTH
		{
			return static_cast<int>(be64toh(where) / MPEG_TIMEBASE);
		}
	}

	return -1;
}

int eStaticServiceMP3Info::getInfo(const eServiceReference &ref, int w)
{
	switch (w)
	{
	case iServiceInformation::sTimeCreate:
		{
			struct stat s = {};
			if (stat(ref.path.c_str(), &s) == 0)
			{
				return s.st_mtime;
			}
		}
		break;
	case iServiceInformation::sFileSize:
		{
			struct stat s = {};
			if (stat(ref.path.c_str(), &s) == 0)
			{
				return s.st_size;
			}
		}
		break;
	}
	return iServiceInformation::resNA;
}

long long eStaticServiceMP3Info::getFileSize(const eServiceReference &ref)
{
	struct stat s = {};
	if (stat(ref.path.c_str(), &s) == 0)
	{
		return s.st_size;
	}
	return 0;
}

RESULT eStaticServiceMP3Info::getEvent(const eServiceReference &ref, ePtr<eServiceEvent> &evt, time_t start_time)
{
	if (ref.path.find("://") != std::string::npos)
	{
		eServiceReference equivalentref(ref);
		equivalentref.type = eServiceFactoryMP3::id;
		equivalentref.path.clear();
		return eEPGCache::getInstance()->lookupEventTime(equivalentref, start_time, evt);
	}
	else // try to read .eit file
	{
		size_t pos;
		ePtr<eServiceEvent> event = new eServiceEvent;
		std::string filename = ref.path;
		if ( (pos = filename.rfind('.')) != std::string::npos)
		{
			filename.erase(pos + 1);
			filename += "eit";
			if (!event->parseFrom(filename, 0))
			{
				evt = event;
				return 0;
			}
		}
	}
	evt = 0;
	return -1;
}

DEFINE_REF(eStreamBufferInfo)

eStreamBufferInfo::eStreamBufferInfo(int percentage, int inputrate, int outputrate, int space, int size)
: bufferPercentage(percentage),
	inputRate(inputrate),
	outputRate(outputrate),
	bufferSpace(space),
	bufferSize(size)
{
}

int eStreamBufferInfo::getBufferPercentage() const
{
	return bufferPercentage;
}

int eStreamBufferInfo::getAverageInputRate() const
{
	return inputRate;
}

int eStreamBufferInfo::getAverageOutputRate() const
{
	return outputRate;
}

int eStreamBufferInfo::getBufferSpace() const
{
	return bufferSpace;
}

int eStreamBufferInfo::getBufferSize() const
{
	return bufferSize;
}

DEFINE_REF(eServiceMP3InfoContainer);

eServiceMP3InfoContainer::eServiceMP3InfoContainer()
: doubleValue(0.0), bufferValue(NULL), bufferData(NULL), bufferSize(0)
{
}

eServiceMP3InfoContainer::~eServiceMP3InfoContainer()
{
	if (bufferValue)
	{
		gst_buffer_unmap(bufferValue, &map);
		gst_buffer_unref(bufferValue);
		bufferValue = NULL;
		bufferData = NULL;
		bufferSize = 0;
	}
}

double eServiceMP3InfoContainer::getDouble(unsigned int index) const
{
	return doubleValue;
}

unsigned char *eServiceMP3InfoContainer::getBuffer(unsigned int &size) const
{
	size = bufferSize;
	return bufferData;
}

void eServiceMP3InfoContainer::setDouble(double value)
{
	doubleValue = value;
}

void eServiceMP3InfoContainer::setBuffer(GstBuffer *buffer)
{
	bufferValue = buffer;
	gst_buffer_ref(bufferValue);
	gst_buffer_map(bufferValue, &map, GST_MAP_READ);
	bufferData = map.data;
	bufferSize = map.size;
}

// eServiceMP3
int eServiceMP3::ac3_delay = 0,
    eServiceMP3::pcm_delay = 0;

eServiceMP3::eServiceMP3(eServiceReference ref):
	m_nownext_timer(eTimer::create(eApp)),
	m_cuesheet_changed(0),
	m_cutlist_enabled(1),
	m_ref(ref),
	m_pump(eApp, 1, "Servicemp3")
{
	m_subtitle_sync_timer = eTimer::create(eApp);
	m_dvb_subtitle_sync_timer = eTimer::create(eApp);
	m_dvb_subtitle_parser = new eDVBSubtitleParser();
	m_dvb_subtitle_parser->connectNewPage(sigc::mem_fun(*this, &eServiceMP3::newDVBSubtitlePage), m_new_dvb_subtitle_page_connection);
	m_passthrough_fix_timer = eTimer::create(eApp);
	m_stream_tags = 0;
	m_currentAudioStream = -1;
	m_currentSubtitleStream = -1;
	m_cachedSubtitleStream = -2; /* report subtitle stream to be 'cached'. TODO: use an actual cache. */
	m_autoturnon = eConfigManager::getConfigBoolValue("config.subtitles.pango_autoturnon", true);
	m_subtitle_widget = 0;
	m_currentTrickRatio = 1.0;
	m_buffer_size = 5 * 1024 * 1024;
	m_ignore_buffering_messages = 0;
	m_is_live = false;
	m_use_prefillbuffer = false;
	m_paused = false;
	m_clear_buffers = true;
	m_initial_start = false;
	m_send_ev_start = true;
	m_seek_paused = false;
	m_cuesheet_loaded = false; /* cuesheet CVR */
	m_use_chapter_entries = false; /* TOC chapter support CVR */
	m_last_seek_pos = 0; /* CVR last seek position */
	m_useragent = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36";
	m_extra_headers = "";
	m_download_buffer_path = "";
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	m_errorInfo.missing_codec = "";
	audioSink = videoSink = NULL;
	m_decoder = NULL;

	std::string sref = ref.toString();
	eDebug("[eServiceMP3] Init start %s", ref.toString().c_str());
	if (!sref.empty())
	{
		eDebug("[eServiceMP3] Init start !sref.empty()");
		std::vector<eIPTVDBItem> &iptv_services = eDVBDB::getInstance()->iptv_services;
		for(std::vector<eIPTVDBItem>::iterator it = iptv_services.begin(); it != iptv_services.end(); ++it)
		{
			if (sref.find(it->s_ref) != std::string::npos)
			{
				m_currentAudioStream = it->ampeg_pid;
				m_currentSubtitleStream = it->subtitle_pid;
				m_cachedSubtitleStream = m_currentSubtitleStream;
				eDebug("[eServiceMP3] Init start iptv_service use sref pid's A: %d; S: %d", m_currentAudioStream, it->subtitle_pid);
				break;
			}
		}
	}

	CONNECT(m_subtitle_sync_timer->timeout, eServiceMP3::pushSubtitles);
	CONNECT(m_dvb_subtitle_sync_timer->timeout, eServiceMP3::pushDVBSubtitles);
	CONNECT(m_pump.recv_msg, eServiceMP3::gstPoll);
	CONNECT(m_nownext_timer->timeout, eServiceMP3::updateEpgCacheNowNext);
	CONNECT(m_passthrough_fix_timer->timeout, eServiceMP3::forceAudioReset);

	m_aspect = m_width = m_height = m_framerate = m_progressive = m_gamma = -1;
	m_hdr_type = 0;
#ifdef HAS_SOFTWARE_HDR_DETECTION
	m_hdr_probe_id = 0;
	m_hdr_probe_pad = NULL;
	g_atomic_int_set(&m_hdr_probe_active, 0);
	m_hdr_probe_last_classify = 0;
	m_hdr_probe_first_sps_at = 0;
	g_mutex_init(&m_hdr_probe_mutex);
#endif

	m_state = stIdle;
	m_coverart = false;
	eDebug("[eServiceMP3] construct!");

	const char *filename;
	std::string filename_str;
	size_t pos = m_ref.path.find('#');
	size_t pos_q = m_ref.path.find('?');
	if (pos != std::string::npos && (m_ref.path.compare(0, 4, "http") == 0 || m_ref.path.compare(0, 4, "rtsp") == 0))
	{
		filename_str = m_ref.path.substr(0, pos);
		filename = filename_str.c_str();
		m_extra_headers = m_ref.path.substr(pos + 1);

		pos = m_extra_headers.find("User-Agent=");
		if (pos != std::string::npos)
		{
			size_t hpos_start = pos + 11;
			size_t hpos_end = m_extra_headers.find('&', hpos_start);
			if (hpos_end != std::string::npos)
				m_useragent = m_extra_headers.substr(hpos_start, hpos_end - hpos_start);
			else
				m_useragent = m_extra_headers.substr(hpos_start);
		}
	}
	else
	{
		filename_str = m_ref.path;
		filename = m_ref.path.c_str();
	}

	std::string realFilename_str;
	const char *realFilename;

	if (pos_q != std::string::npos)
	{
		realFilename_str = filename_str.substr(0, pos_q);
		realFilename = realFilename_str.c_str();
	}
	else
		realFilename = filename_str.c_str();

	const char *ext = strrchr(realFilename, '.');
	if (!ext)
		ext = realFilename + strlen(realFilename);

	eDebug("[ServiceMP3] ext = %s", ext);

	m_sourceinfo.is_video = FALSE;
	m_sourceinfo.audiotype = atUnknown;
	if (strcasecmp(ext, ".mpeg") == 0 || strcasecmp(ext, ".mpe") == 0 || strcasecmp(ext, ".mpg") == 0 || strcasecmp(ext, ".vob") == 0 || strcasecmp(ext, ".bin") == 0)
	{
		m_sourceinfo.containertype = ctMPEGPS;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".ts") == 0)
	{
		m_sourceinfo.containertype = ctMPEGTS;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".mkv") == 0)
	{
		m_sourceinfo.containertype = ctMKV;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".ogm") == 0 || strcasecmp(ext, ".ogv") == 0)
	{
		m_sourceinfo.containertype = ctOGG;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".avi") == 0 || strcasecmp(ext, ".divx") == 0)
	{
		m_sourceinfo.containertype = ctAVI;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".mp4") == 0 || strcasecmp(ext, ".mov") == 0 || strcasecmp(ext, ".m4v") == 0 || strcasecmp(ext, ".3gp") == 0 || strcasecmp(ext, ".3g2") == 0)
	{
		m_sourceinfo.containertype = ctMP4;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".asf") == 0 || strcasecmp(ext, ".wmv") == 0)
	{
		m_sourceinfo.containertype = ctASF;
		m_sourceinfo.is_video = TRUE;
	}
	else if (strcasecmp(ext, ".webm") == 0)
	{
		m_sourceinfo.containertype = ctWEBM;
		m_sourceinfo.is_video = TRUE;
	}
	else if ( strcasecmp(ext, ".dra") == 0 )
	{
		m_sourceinfo.containertype = ctDRA;
		m_sourceinfo.audiotype = atDRA;
	}
	else if (strcasecmp(ext, ".m3u8") == 0)
		m_sourceinfo.is_hls = TRUE;
	else if (strcasecmp(ext, ".mp3") == 0)
	{
		m_sourceinfo.audiotype = atMP3;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".wma") == 0)
	{
		m_sourceinfo.audiotype = atWMA;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".wav") == 0 || strcasecmp(ext, ".wave") == 0 || strcasecmp(ext, ".wv") == 0)
	{
		m_sourceinfo.audiotype = atPCM;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".dtshd") == 0 || strcasecmp(ext, ".dts-hd") == 0)
	{
		m_sourceinfo.audiotype = atDTSHD;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".dts") == 0)
	{
		m_sourceinfo.audiotype = atDTS;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".flac") == 0)
	{
		m_sourceinfo.audiotype = atFLAC;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".ac3") == 0)
	{
		m_sourceinfo.audiotype = atAC3;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".aac") == 0 || strcasecmp(ext, ".adts") == 0 || strcasecmp(ext, ".aac-lc") == 0 || strcasecmp(ext, ".aaclc") == 0 || strcasecmp(ext, ".mp4a") == 0 || strcasecmp(ext, ".m4a") == 0 || strcasecmp(ext, ".mp4") == 0 || strcasecmp(ext, ".3gp") == 0)
	{
		m_sourceinfo.audiotype = atAAC;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".aache") == 0 || strcasecmp(ext, ".heaac") == 0 || strcasecmp(ext, ".he-aac") == 0 || strcasecmp(ext, ".aac-he") == 0 || strcasecmp(ext, ".adts") == 0 ||  strcasecmp(ext, ".mp4a") == 0 || strcasecmp(ext, ".m4a") == 0 || strcasecmp(ext, ".mp4") == 0 || strcasecmp(ext, ".3gp") == 0 || strcasecmp(ext, ".alac") == 0)
	{
		m_sourceinfo.audiotype = atAACHE;
		m_sourceinfo.is_audio = TRUE;
	}
	else if (strcasecmp(ext, ".cda") == 0)
		m_sourceinfo.containertype = ctCDA;
	if (strcasecmp(ext, ".dat") == 0)
	{
		m_sourceinfo.containertype = ctVCD;
		m_sourceinfo.is_video = TRUE;
	}
	if (strstr(filename, "://"))
		m_sourceinfo.is_streaming = TRUE;

	gchar *uri;
	gchar *suburi = NULL;

	pos = m_ref.path.find("&suburi=");
	if (pos != std::string::npos)
	{
		filename_str = filename;

		std::string suburi_str = filename_str.substr(pos + 8);
		filename = suburi_str.c_str();
		suburi = g_strdup_printf ("%s", filename);

		filename_str = filename_str.substr(0, pos);
		filename = filename_str.c_str();
	}

	if ( m_sourceinfo.is_streaming )
	{
		if (eConfigManager::getConfigBoolValue("config.mediaplayer.useAlternateUserAgent"))
			m_useragent = eConfigManager::getConfigValue("config.mediaplayer.alternateUserAgent");

		uri = g_strdup_printf ("%s", filename);

		if ( m_ref.getData(7) & BUFFERING_ENABLED )
		{
			m_use_prefillbuffer = true;
			if ( m_ref.getData(7) & PROGRESSIVE_DOWNLOAD )
			{
				/* progressive download buffering */
				if (::access("/hdd/movie", X_OK) >= 0)
				{
					/* It looks like /hdd points to a valid mount, so we can store a download buffer on it */
					m_download_buffer_path = "/hdd/gstreamer_XXXXXXXXXX";
				}
			}
		}
	}
	else if ( m_sourceinfo.containertype == ctCDA )
	{
		int i_track = atoi(filename+17);
		uri = g_strdup_printf ("cdda://%i", i_track);
	}
	else if ( m_sourceinfo.containertype == ctVCD )
	{
		int ret = -1;
		int fd = open(filename,O_RDONLY);
		if (fd >= 0)
		{
			char* tmp = new char[128*1024];
			ret = read(fd, tmp, 128*1024);
			close(fd);
			delete [] tmp;
		}
		if ( ret == -1 ) // this is a "REAL" VCD
			uri = g_strdup_printf ("vcd://");
		else
			uri = g_filename_to_uri(filename, NULL, NULL);
	}
	else
		uri = g_filename_to_uri(filename, NULL, NULL);

	eDebug("[eServiceMP3] playbin uri=%s", uri);
	if (suburi != NULL)
		eDebug("[eServiceMP3] playbin suburi=%s", suburi);
	m_gst_playbin = gst_element_factory_make("playbin", "playbin");
	if ( m_gst_playbin )
	{
		/*
		 * avoid video conversion, let the dvbmediasink handle that using native video flag
		 * volume control is done by hardware, do not use soft volume flag
		 */
		guint flags = GST_PLAY_FLAG_AUDIO | GST_PLAY_FLAG_VIDEO | \
				GST_PLAY_FLAG_TEXT | GST_PLAY_FLAG_NATIVE_VIDEO;

		if ( m_sourceinfo.is_streaming )
		{
			g_signal_connect (G_OBJECT (m_gst_playbin), "notify::source", G_CALLBACK (playbinNotifySource), this);
			if (m_download_buffer_path != "")
			{
				/* use progressive download buffering */
				flags |= GST_PLAY_FLAG_DOWNLOAD;
				g_signal_connect(G_OBJECT(m_gst_playbin), "element-added", G_CALLBACK(handleElementAdded), this);
				/* limit file size */
				g_object_set(m_gst_playbin, "ring-buffer-max-size", (guint64)(8LL * 1024LL * 1024LL), NULL);
			}
			/*
			 * regardless whether or not we configured a progressive download file, use a buffer as well
			 * (progressive download might not work for all formats)
			 */
			flags |= GST_PLAY_FLAG_BUFFERING;
			/* increase the default 2 second / 2 MB buffer limitations to 5s / 5MB */
			g_object_set(G_OBJECT(m_gst_playbin), "buffer-duration", 5LL * GST_SECOND, NULL);
			g_object_set(G_OBJECT(m_gst_playbin), "buffer-size", m_buffer_size, NULL);
			if (m_sourceinfo.is_hls)
				g_object_set(G_OBJECT(m_gst_playbin), "connection-speed", (guint64)(4495000LL), NULL);
		}
		g_object_set (G_OBJECT (m_gst_playbin), "flags", flags, NULL);
		g_object_set (G_OBJECT (m_gst_playbin), "uri", uri, NULL);
		GstElement *subsink = gst_element_factory_make("subsink", "subtitle_sink");
		if (!subsink)
			eDebug("[eServiceMP3] sorry, can't play: missing gst-plugin-subsink");
		else
		{
			m_subs_to_pull_handler_id = g_signal_connect (subsink, "new-buffer", G_CALLBACK (gstCBsubtitleAvail), this);
			g_object_set (G_OBJECT (subsink), "caps", gst_caps_from_string("text/plain; text/x-plain; text/x-raw; text/x-pango-markup; subpicture/x-dvd; subpicture/x-dvb; subpicture/x-pgs"), NULL);
			g_object_set (G_OBJECT (m_gst_playbin), "text-sink", subsink, NULL);
			g_object_set (G_OBJECT (m_gst_playbin), "current-text", m_currentSubtitleStream, NULL);
		}
		GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE (m_gst_playbin));
		gst_bus_set_sync_handler(bus, gstBusSyncHandler, this, NULL);
		gst_object_unref(bus);

		if (suburi != NULL)
			g_object_set (G_OBJECT (m_gst_playbin), "suburi", suburi, NULL);
	} else
	{
		m_event((iPlayableService*)this, evUser+12);
		m_gst_playbin = 0;
		m_errorInfo.error_message = "failed to create GStreamer pipeline!\n";

		eDebug("[eServiceMP3] sorry, can't play: %s",m_errorInfo.error_message.c_str());
	}
	g_free(uri);
	if (suburi != NULL)
		g_free(suburi);
}

eServiceMP3::~eServiceMP3()
{
	// disconnect subtitle callback
	GstElement *subsink = gst_bin_get_by_name(GST_BIN(m_gst_playbin), "subtitle_sink");

	if (subsink)
	{
		g_signal_handler_disconnect (subsink, m_subs_to_pull_handler_id);
		gst_object_unref(subsink);
	}

	if (m_subtitle_widget) m_subtitle_widget->destroy();
	m_subtitle_widget = 0;

	if (m_gst_playbin)
	{
		// disconnect sync handler callback
		GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE (m_gst_playbin));
		gst_bus_set_sync_handler(bus, NULL, NULL, NULL);
		gst_object_unref(bus);
	}

	stop();

	if (m_decoder)
	{
		m_decoder = NULL;
	}

	if (m_stream_tags)
		gst_tag_list_free(m_stream_tags);

	if (audioSink)
	{
		gst_object_unref(GST_OBJECT(audioSink));
		audioSink = NULL;
	}
	if (videoSink)
	{
		gst_object_unref(GST_OBJECT(videoSink));
		videoSink = NULL;
	}
	if (m_gst_playbin)
	{
		gst_object_unref (GST_OBJECT (m_gst_playbin));
		eDebug("[eServiceMP3] destruct!");
	}
	m_new_dvb_subtitle_page_connection = 0;
}

int eServiceMP3PendingStopWorkers();

void eServiceMP3::forceAudioReset()
{
	/* start() reuses this existing main-loop timer while a previous
	 * GStreamer pipeline is still releasing the shared hardware sinks.
	 * Polling here keeps Enigma2 responsive and adds no fixed handover
	 * delay: playback starts on the first tick after teardown completes. */
	if (m_state == stIdle && m_gst_playbin)
	{
		int pending = eServiceMP3PendingStopWorkers();
		if (pending > 0)
		{
			m_passthrough_fix_timer->start(10, true);
			return;
		}
		eDebug("[eServiceMP3] previous pipeline teardown complete; starting deferred pipeline");
		start();
		return;
	}

	if (!eConfigManager::getConfigBoolValue("config.av.passthrough_fix", false))
	{
		setHDAudioNativeEac3ResetPending(m_gst_playbin, false);
		setHDAudioNativeRetry(m_gst_playbin, -1);
		m_clear_buffers = true;
		clearBuffers();
		return;
	}
#ifdef PASSTHROUGH_FIX
	if (hdAudioNativeEac3ResetPending(m_gst_playbin))
		setHDAudioNativeEac3ResetPending(m_gst_playbin, false);
	// Toggle Bluetooth audio off->on->off to force audio driver reinitialization
	std::string btaudio = CFile::read("/proc/stb/audio/btaudio");
	if (!btaudio.empty() && btaudio.find("off") != std::string::npos)
	{
		eDebug("[eDVBSoftDecoder] Force audio reset: toggling btaudio on and back off");
		CFile::writeStr("/proc/stb/audio/btaudio", "on");
		CFile::writeStr("/proc/stb/audio/btaudio", "off");
	}

	if (btaudio.empty())
	{
		int currAudioIndex = getCurrentTrack();
		selectAudioStream(currAudioIndex, true);
	}
#endif

	m_clear_buffers = true;
	clearBuffers();
	const int retry_audio = hdAudioNativeRetry(m_gst_playbin);
	if (retry_audio >= 0)
	{
		g_object_set(G_OBJECT(m_gst_playbin), "current-audio", retry_audio, NULL);
		setHDAudioNativeRetry(m_gst_playbin, -1);
	}
}

void eServiceMP3::updateEpgCacheNowNext()
{
	bool update = false;
	ePtr<eServiceEvent> next = 0;
	ePtr<eServiceEvent> ptr = 0;
	eServiceReference ref(m_ref);
	ref.type = eServiceFactoryMP3::id;
	ref.path.clear();
	if (eEPGCache::getInstance() && eEPGCache::getInstance()->lookupEventTime(ref, -1, ptr) >= 0)
	{
		ePtr<eServiceEvent> current = m_event_now;
		if (!current || !ptr || current->getEventId() != ptr->getEventId())
		{
			update = true;
			m_event_now = ptr;
			time_t next_time = ptr->getBeginTime() + ptr->getDuration();
			if (eEPGCache::getInstance()->lookupEventTime(ref, next_time, ptr) >= 0)
			{
				next = ptr;
				m_event_next = ptr;
			}
		}
	}

	int refreshtime = 60;
	if (!next)
	{
		next = m_event_next;
	}
	if (next)
	{
		time_t now = eDVBLocalTimeHandler::getInstance()->nowTime();
		refreshtime = (int)(next->getBeginTime() - now) + 3;
		if (refreshtime <= 0 || refreshtime > 60)
		{
			refreshtime = 60;
		}
	}
	m_nownext_timer->startLongTimer(refreshtime);
	if (update)
	{
		m_event((iPlayableService*)this, evUpdatedEventInfo);
	}
}

DEFINE_REF(eServiceMP3);

DEFINE_REF(GstMessageContainer);

void eServiceMP3::setCacheEntry(bool isAudio, int pid)
{
	bool hasFoundItem = false;

	std::vector<eIPTVDBItem> &iptv_services = eDVBDB::getInstance()->iptv_services;
	for(std::vector<eIPTVDBItem>::iterator it = iptv_services.begin(); it != iptv_services.end(); ++it) {
		if (m_ref.toString().find(it->s_ref) != std::string::npos) {
			hasFoundItem = true;
			if (isAudio) {
				it->ampeg_pid = pid;
			}
			else
			{
				it->subtitle_pid = pid;
			}
			break;
		}
	}
	if (!hasFoundItem) {
		eIPTVDBItem item(m_sourceinfo.is_streaming ? m_ref.toReferenceString() : m_ref.toString(), isAudio ? pid : -1, -1, -1, -1, -1, -1, -1, isAudio ? -1 : pid, -1);
		iptv_services.push_back(item);
	}
}

RESULT eServiceMP3::connectEvent(const sigc::slot<void(iPlayableService*,int)> &event, ePtr<eConnection> &connection)
{
	connection = new eConnection((iPlayableService*)this, m_event.connect(event));
	return 0;
}

RESULT eServiceMP3::start()
{
	ASSERT(m_state == stIdle);

#ifdef PASSTHROUGH_FIX
	if (eConfigManager::getConfigBoolValue("config.av.passthrough_fix", false))
	{
		int pending = eServiceMP3PendingStopWorkers();
		if (pending > 0)
		{
			eDebug("[eServiceMP3] deferring pipeline start while %d previous teardown(s) release hardware", pending);
			m_passthrough_fix_timer->start(10, true);
			return 0;
		}
	}
#endif

	if (m_gst_playbin)
	{
		eDebug("[eServiceMP3] starting pipeline");
		GstStateChangeReturn ret;
		ret = gst_element_set_state (m_gst_playbin, GST_STATE_PLAYING);

		switch(ret)
		{
		case GST_STATE_CHANGE_FAILURE:
			eDebug("[eServiceMP3] failed to start pipeline");
			stop();
			return -1;
			break;
		case GST_STATE_CHANGE_SUCCESS:
			m_is_live = false;
			break;
		case GST_STATE_CHANGE_NO_PREROLL:
			m_is_live = true;
			break;
		default:
			break;
		}
	}

	if (m_ref && m_ref.path.find("://") == std::string::npos)
	{
		/* read event from .eit file */
		size_t pos;
		ePtr<eServiceEvent> event = new eServiceEvent;
		std::string filename = m_ref.path;
		if ( (pos = filename.rfind('.')) != std::string::npos)
		{
			filename.erase(pos + 1);
			filename += "eit";
			if (!event->parseFrom(filename, 0))
			{
				ePtr<eServiceEvent> empty;
				m_event_now = event;
				m_event_next = empty;
			}
		}
	}

	return 0;
}

static volatile gint s_mp3_stop_workers = 0;

int eServiceMP3PendingStopWorkers()
{
	return g_atomic_int_get(&s_mp3_stop_workers);
}

namespace {

const guint STOP_WATCHDOG_TIMEOUT_SECONDS = 10;

/* Shared between stopWorker() and stopWatchdog() only - never touches
 * eServiceMP3/"this", same reasoning as not passing "this" to stopWorker
 * itself: this teardown can outlive the object it came from. refcount starts
 * at 2 (one per thread below); whichever of the two finishes second frees it,
 * so it's torn down properly regardless of which one happens to win the race
 * for the normal (fast) case. */
struct StopWatchdog
{
	gint done;      // atomic bool, set by stopWorker() once GST_STATE_NULL actually returns
	gint refcount;  // atomic
};

void stopWatchdogRelease(StopWatchdog *watchdog)
{
	if (g_atomic_int_dec_and_test(&watchdog->refcount))
		delete watchdog;
}

struct StopWorkerArgs
{
	GstElement *playbin;
	StopWatchdog *watchdog;
	bool hadVideo;
};

/* gst_element_set_state(..., GST_STATE_NULL) is the call that can still block
 * this (main) thread for seconds: unlike other transitions it is defined to
 * not return until the element has fully stopped, and some vendor hardware
 * sinks on this class of STB block synchronously inside their change_state()
 * vfunc instead of returning ASYNC, especially for H.265. Doing it here on a
 * worker thread instead just moves that wait off the main thread; nothing
 * else needs to be touched, since stop() itself already takes just a raw
 * ref (not "this"), and every eServiceMP3 member accessed after this call
 * in stop() (stopHDRProbe(), saveCuesheet()) is independently safe to run
 * before the pipeline has actually reached NULL - see the comments there. */
gpointer stopWorker(gpointer data)
{
	StopWorkerArgs *args = static_cast<StopWorkerArgs*>(data);
	GstElement *playbin = args->playbin;
	StopWatchdog *watchdog = args->watchdog;
	bool hadVideo = args->hadVideo;
	delete args;

	GstStateChangeReturn ret = gst_element_set_state(playbin, GST_STATE_NULL);
	if (ret != GST_STATE_CHANGE_SUCCESS)
		eDebug("[eServiceMP3] stop GST_STATE_NULL failure");
	gst_object_unref(playbin);

	int remaining = g_atomic_int_add(&s_mp3_stop_workers, -1) - 1;
	eDebug("[eServiceMP3] stop worker released hardware; %d teardown(s) remain", remaining);

	/* GstDVBVideoSink's own device fd is gone once GST_STATE_NULL has actually
	 * returned (guaranteed synchronous per the comment above), but whether it
	 * blanks the video plane on the way down is up to that (out-of-tree) sink.
	 * Force it here too so the last decoded frame doesn't stay frozen on
	 * screen after playback has genuinely stopped - this opens its own fd, so
	 * it doesn't race the sink's teardown. */
	if (hadVideo)
		eTSMPEGDecoder::blankPrimaryVideoDecoder();

	g_atomic_int_set(&watchdog->done, 1);
	stopWatchdogRelease(watchdog);
	return NULL;
}

/* Detection only, not recovery - there is no safe way to force-abort a
 * thread stuck inside gst_element_set_state(), so this can't do anything
 * about a genuinely wedged teardown beyond making it visible in the log
 * instead of silently leaking a thread + pipeline forever. Runs as its own
 * thread rather than an eTimer specifically because it has to outlive "this"
 * (the eServiceMP3 destructor calls stop() and then immediately proceeds to
 * destroy the object) - a member eTimer would be destroyed right along with
 * it and never get a chance to fire for exactly the case that matters most. */
gpointer stopWatchdog(gpointer data)
{
	StopWatchdog *watchdog = static_cast<StopWatchdog*>(data);
	g_usleep(STOP_WATCHDOG_TIMEOUT_SECONDS * G_USEC_PER_SEC);
	if (!g_atomic_int_get(&watchdog->done))
		eDebug("[eServiceMP3] stop(): GST_STATE_NULL still hasn't completed after %u seconds - hardware sink likely stuck", STOP_WATCHDOG_TIMEOUT_SECONDS);
	stopWatchdogRelease(watchdog);
	return NULL;
}

}  // namespace

void eServiceMP3::disconnectAsyncSignalHandlers()
{
	if (!m_gst_playbin)
		return;

	/* playbinNotifySource()/handleElementAdded()/gstTextpadHasCAPS() were all
	 * connected with "this" as user_data to react to the pipeline's dynamic
	 * reconfiguration during normal playback. Now that stop() moves
	 * GST_STATE_NULL off the main thread (see stopWorker()), the pipeline can
	 * keep running - and keep emitting these signals - for a while after this
	 * object itself has been destroyed, since the two are no longer
	 * synchronized. A real crash from exactly this (gstTextpadHasCAPS firing
	 * into an already-freed "this") is what prompted this function. None of
	 * these signals' actions matter once we're stopping regardless, so
	 * disconnect all of them synchronously here, before handing the actual
	 * teardown off to the worker thread: g_signal_handlers_disconnect_by_func()
	 * is fast and non-blocking (it doesn't wait for the pipeline to reach any
	 * particular state), so this doesn't reintroduce the freeze stopWorker()
	 * exists to avoid.
	 *
	 * handleElementAdded() reconnects itself on every decodebin/uridecodebin
	 * element it discovers (see its own body) - there is no fixed, known set
	 * of objects it ends up connected to, so walk the live pipeline and
	 * disconnect it from every bin found, not just m_gst_playbin itself.
	 * g_signal_handlers_disconnect_by_func() is a safe no-op on any object
	 * that callback was never actually connected to. */
	g_signal_handlers_disconnect_by_func(m_gst_playbin, (gpointer)playbinNotifySource, this);
	g_signal_handlers_disconnect_by_func(m_gst_playbin, (gpointer)handleElementAdded, this);

	GstIterator *eit = gst_bin_iterate_recurse(GST_BIN(m_gst_playbin));
	GValue eitem = G_VALUE_INIT;
	bool edone = false;
	while (!edone)
	{
		switch (gst_iterator_next(eit, &eitem))
		{
			case GST_ITERATOR_OK:
			{
				GstElement *el = GST_ELEMENT(g_value_get_object(&eitem));
				if (el && GST_IS_BIN(el))
					g_signal_handlers_disconnect_by_func(el, (gpointer)handleElementAdded, this);
				g_value_reset(&eitem);
				break;
			}
			case GST_ITERATOR_RESYNC: gst_iterator_resync(eit); break;
			default: edone = true; break;
		}
	}
	g_value_unset(&eitem);
	gst_iterator_free(eit);

	gint n_text = 0;
	g_object_get(m_gst_playbin, "n-text", &n_text, NULL);
	for (gint i = 0; i < n_text; i++)
	{
		GstPad *pad = NULL;
		g_signal_emit_by_name(m_gst_playbin, "get-text-pad", i, &pad);
		if (pad)
		{
			g_signal_handlers_disconnect_by_func(pad, (gpointer)gstTextpadHasCAPS, this);
			gst_object_unref(pad);
		}
	}
}

RESULT eServiceMP3::stop()
{
	m_passthrough_fix_timer->stop();
	if (!m_gst_playbin || m_state == stStopped || !m_ref)
		return -1;

	eDebug("[eServiceMP3] stop %s", m_ref.path.c_str());
	m_state = stStopped;

	GstStateChangeReturn ret;
	GstState state, pending;
	/* Non-blocking state query, for logging only. */
	ret = gst_element_get_state(m_gst_playbin, &state, &pending, 0);
	eDebug("[eServiceMP3] stop state:%s pending:%s ret:%s",
		gst_element_state_get_name(state),
		gst_element_state_get_name(pending),
		gst_element_state_change_return_get_name(ret));

	stopHDAudioAuxPipeline(m_gst_playbin, false);
	disconnectAsyncSignalHandlers();

	/* See stopWorker()'s comment: hand the actual (potentially blocking)
	 * teardown off to a worker thread instead of doing it here, plus a
	 * watchdog thread that just logs if it's taking unexpectedly long -
	 * see stopWatchdog()'s comment for why that's a thread and not a timer. */
	gst_object_ref(m_gst_playbin);
	g_atomic_int_inc(&s_mp3_stop_workers);
	StopWatchdog *watchdog = new StopWatchdog{0, 2};
	GThread *worker = g_thread_new("mp3stop", stopWorker, new StopWorkerArgs{m_gst_playbin, watchdog, videoSink != NULL});
	g_thread_unref(worker);
	GThread *watchdogThread = g_thread_new("mp3stopwd", stopWatchdog, watchdog);
	g_thread_unref(watchdogThread);

#ifdef HAS_SOFTWARE_HDR_DETECTION
	/* stopHDRProbe() itself deliberately never calls the blocking
	 * gst_pad_remove_probe() - see its own comment - which is correct and
	 * necessary for its OTHER call sites (startHDRProbe() restarting mid
	 * playback, checkHDRProbe() finishing classification), where "this"
	 * stays alive regardless of how long the probe takes to actually detach.
	 * stop() is different: now that GST_STATE_NULL runs on a worker thread
	 * (see stopWorker()), this object can be destroyed shortly after
	 * returning from here, and hdrProbeCallback firing into an already-freed
	 * "this" is exactly what caused a real crash (glibc robust-mutex
	 * assertion / heap corruption). So only here, remove the probe for real
	 * before doing anything else - gst_pad_remove_probe() blocks until any
	 * in-flight invocation finishes (worst case one buffer copy, low
	 * milliseconds - nowhere near the multi-second class of block
	 * stopWorker() exists to avoid), which is the only way to *guarantee*
	 * hdrProbeCallback can never fire again from here on. */
	if (m_hdr_probe_pad && m_hdr_probe_id)
	{
		gst_pad_remove_probe(m_hdr_probe_pad, m_hdr_probe_id);
		m_hdr_probe_id = 0;
	}
	/* Now safe to call as usual - the flag/trylock dance is redundant at this
	 * point (nothing can be mid-callback anymore) but harmless, and this
	 * still does the rest of the cleanup (timer, es/snap buffers, pad ref). */
	stopHDRProbe();
#endif

	saveCuesheet();
	m_nownext_timer->stop();

	return 0;
}

RESULT eServiceMP3::pause(ePtr<iPauseableService> &ptr)
{
	ptr=this;
	return 0;
}

RESULT eServiceMP3::setSlowMotion(int ratio)
{
	if (!ratio)
		return 0;
	eDebug("[eServiceMP3] setSlowMotion ratio=%f",1.0/(gdouble)ratio);
	return trickSeek(1.0/(gdouble)ratio);
}

RESULT eServiceMP3::setFastForward(int ratio)
{
	eDebug("[eServiceMP3] setFastForward ratio=%i",ratio);
	return trickSeek(ratio);
}

		// iPausableService
RESULT eServiceMP3::pause()
{
	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	eDebug("[eServiceMP3] pause");
	trickSeek(0.0);

	return 0;
}

RESULT eServiceMP3::unpause()
{
	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	/* no need to unpase if we are not paused already */
	if (m_currentTrickRatio == 1.0 && !m_paused)
	{
		eDebug("[eServiceMP3] trickSeek no need to unpause!");
		return 0;
	}

	eDebug("[eServiceMP3] unpause");
	trickSeek(1.0);

	return 0;
}

	/* iSeekableService */
RESULT eServiceMP3::seek(ePtr<iSeekableService> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::getLength(pts_t &pts)
{
	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	GstFormat fmt = GST_FORMAT_TIME;
	gint64 len;
	if (!gst_element_query_duration(m_gst_playbin, fmt, &len))
		return -1;
		/* len is in nanoseconds. we have 90 000 pts per second. */

	pts = len / 11111LL;
	return 0;
}

RESULT eServiceMP3::seekToImpl(pts_t to)
{
		/* convert pts to nanoseconds */
	m_last_seek_pos = to * 11111LL;
	if (!gst_element_seek (m_gst_playbin, m_currentTrickRatio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT),
		GST_SEEK_TYPE_SET, m_last_seek_pos,
		GST_SEEK_TYPE_NONE, GST_CLOCK_TIME_NONE))
	{
		eDebug("[eServiceMP3] seekTo failed");
		return -1;
	}

	if (getHDAudioAuxState(m_gst_playbin))
		seekHDAudioAuxPersistent(m_gst_playbin, m_last_seek_pos);

	if (m_paused)
	{
		m_event((iPlayableService*)this, evUpdatedInfo);
	}

	return 0;
}

RESULT eServiceMP3::seekTo(pts_t to)
{
	RESULT ret = -1;

	if (m_gst_playbin)
	{
		m_prev_decoder_time = -1;
		m_decoder_time_valid_state = 0;
		ret = seekToImpl(to);
	}

	return ret;
}


RESULT eServiceMP3::trickSeek(gdouble ratio)
{
	if (!m_gst_playbin)
		return -1;
	GstState state, pending;
	if (ratio > -0.01 && ratio < 0.01)
	{
		gst_element_set_state(m_gst_playbin, GST_STATE_PAUSED);
		setHDAudioAuxState(m_gst_playbin, GST_STATE_PAUSED);
		/* pipeline sometimes block due to audio track issue off gstreamer.
		If the pipeline is blocked up on pending state change to paused ,
        this issue is solved be just reselecting the current audio track.*/
		gst_element_get_state(m_gst_playbin, &state, &pending, 1 * GST_SECOND);
		if (state == GST_STATE_PLAYING && pending == GST_STATE_PAUSED)
		{
			m_clear_buffers = true;
			if (m_currentAudioStream >= 0)
				selectAudioStream(m_currentAudioStream, true);
			else
				selectAudioStream(0, true);
			m_clear_buffers = false;
		}
		return 0;
	}

	bool unpause = (m_currentTrickRatio == 1.0 && ratio == 1.0);
	if (unpause)
	{
		GstElement *source = NULL;
		GstElementFactory *factory = NULL;
		const gchar *name = NULL;
		g_object_get (G_OBJECT (m_gst_playbin), "source", &source, NULL);
		if (!source)
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - cannot get source");
			goto seek_unpause;
		}
		factory = gst_element_get_factory(source);
		g_object_unref(source);
		if (!factory)
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - cannot get source factory");
			goto seek_unpause;
		}
		name = gst_plugin_feature_get_name(GST_PLUGIN_FEATURE(factory));
		if (!name)
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - cannot get source name");
			goto seek_unpause;
		}
		/*
		 * We know that filesrc and souphttpsrc will not timeout after long pause
		 * If there are other sources which will not timeout, add them here
		*/
		if (!strcmp(name, "filesrc") || !strcmp(name, "souphttpsrc"))
		{
			GstStateChangeReturn ret;
			/* make sure that last state change was successfull */
			ret = gst_element_get_state(m_gst_playbin, &state, &pending, 0);
			if (ret == GST_STATE_CHANGE_SUCCESS)
			{
				gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);
				ret = gst_element_get_state(m_gst_playbin, &state, &pending, 0);
				if (ret == GST_STATE_CHANGE_SUCCESS)
				{
					setHDAudioAuxState(m_gst_playbin, GST_STATE_PLAYING);
					return 0;
				}
			}
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - invalid state, state:%s pending:%s ret:%s",
				gst_element_state_get_name(state),
				gst_element_state_get_name(pending),
				gst_element_state_change_return_get_name(ret));
		}
		else
		{
			eDebugNoNewLineStart("[eServiceMP3] trickSeek - source '%s' is not supported", name);
		}
seek_unpause:
		eDebugNoNewLine(", doing seeking unpause\n");
	}

	m_currentTrickRatio = ratio;

	bool validposition = false;
	gint64 pos = 0;
	pts_t pts;
	if (getPlayPosition(pts) >= 0)
	{
		validposition = true;
		pos = pts * 11111LL;
	}

	gst_element_get_state(m_gst_playbin, &state, &pending, 1 * GST_SECOND);
	if (state != GST_STATE_PLAYING)
		gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);

	if (validposition)
	{
		if (ratio >= 0.0)
		{
			gst_element_seek(m_gst_playbin, ratio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT | GST_SEEK_FLAG_SKIP), GST_SEEK_TYPE_SET, pos, GST_SEEK_TYPE_SET, -1);
		}
		else
		{
			/* note that most elements will not support negative speed */
			gst_element_seek(m_gst_playbin, ratio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_SKIP), GST_SEEK_TYPE_SET, 0, GST_SEEK_TYPE_SET, pos);
		}
	}

	setHDAudioAuxState(m_gst_playbin, ratio == 1.0 ? GST_STATE_PLAYING : GST_STATE_PAUSED);
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	return 0;
}


RESULT eServiceMP3::seekRelative(int direction, pts_t to)
{
	if (!m_gst_playbin)
		return -1;

	pts_t ppos;
	if (getPlayPosition(ppos) < 0) return -1;
	ppos += to * direction;

	if (ppos < 0)
		ppos = 0;

	int res = seekTo(ppos);

	// Do double seek to same position so to overcome problem with seeking backward and passthrough on for some boxes
	if (res > -1 && !getHDAudioAuxState(m_gst_playbin))
		seekTo(ppos);

	return res;
}

gint eServiceMP3::match_sinktype(const GValue *velement, const gchar *type)
{
	GstElement *element = GST_ELEMENT_CAST(g_value_get_object(velement));
	return strcmp(g_type_name(G_OBJECT_TYPE(element)), type);
}

RESULT eServiceMP3::getPlayPosition(pts_t &pts)
{
	gint64 pos;
	pts = 0;

	if (!m_gst_playbin || m_state != stRunning)
		return -1;

	bool got_decoder_time = false;
	if ((audioSink || videoSink) && !m_paused)
	{
		if (m_sourceinfo.is_audio && videoSink) {
			g_signal_emit_by_name(audioSink, "get-decoder-time", &pos);
			if (GST_CLOCK_TIME_IS_VALID(pos))
				got_decoder_time = true;
		} else if (!m_sourceinfo.is_audio) {
			/* most stb's work better when pts is taken by audio but some video must be taken cause
			 * audio is 0 or invalid */
			/* avoid taking the audio play position if audio sink is in state NULL */
			if (audioSink) {
				g_signal_emit_by_name(audioSink, "get-decoder-time", &pos);
				if (!GST_CLOCK_TIME_IS_VALID(pos) && videoSink)
					g_signal_emit_by_name(videoSink, "get-decoder-time", &pos);
				if (GST_CLOCK_TIME_IS_VALID(pos))
					got_decoder_time = true;
			} else if (videoSink) {
				g_signal_emit_by_name(videoSink, "get-decoder-time", &pos);
				if (GST_CLOCK_TIME_IS_VALID(pos))
				got_decoder_time = true;
			}
		}
	}

	if (!got_decoder_time) {
		/* Fallback: query playbin position directly. This is needed when dvb sinks
		* exist but get-decoder-time returns invalid values (e.g. MP4 playback on
		* some chipsets like HiSilicon), or when no dvb sinks are available at all. */
		GstFormat fmt = GST_FORMAT_TIME;
		if (!gst_element_query_position(m_gst_playbin, fmt, &pos))
		{
			eDebug("[eServiceMP3] gst_element_query_position failed in getPlayPosition");
			return -1;
		}
	}

	/* pos is in nanoseconds. we have 90 000 pts per second. */
	pts = pos / 11111LL;
	return 0;
}

RESULT eServiceMP3::setTrickmode(int trick)
{
		/* trickmode is not yet supported by our dvbmediasinks. */
	return -1;
}

RESULT eServiceMP3::isCurrentlySeekable()
{
	int ret = 3; /* just assume that seeking and fast/slow winding are possible */

	if (!m_gst_playbin)
		return 0;

	return ret;
}

#ifdef HAS_SOFTWARE_HDR_DETECTION
static int caps_hdr_value(GstCaps *caps)
{
	/* -1 = no colorimetry field, 0 = SDR, 1 = HDR10, 2 = HLG, 3 = generic HDR */
	if (!caps) return -1;
	int res = -1;
	guint n = gst_caps_get_size(caps);
	for (guint i = 0; i < n; i++)
	{
		GstStructure *str = gst_caps_get_structure(caps, i);
		if (!str) continue;
		const gchar *col = gst_structure_get_string(str, "colorimetry");
		if (col)
		{
			if (res < 0) res = 0;
			if (g_strrstr(col, "bt2100-pq") || g_strrstr(col, "smpte2084")) return 1;
			if (g_strrstr(col, "bt2100-hlg") || g_strrstr(col, "arib-std-b67")) return 2;
			/* BT.2020 traditional gamma — plain HDR (driver gamma=1, TC=14/15) */
			if (g_strrstr(col, "bt2020-10") || g_strrstr(col, "bt2020-12")) { if (res < 3) res = 3; }
		}
		if (gst_structure_has_field(str, "mastering-display-info") ||
		    gst_structure_has_field(str, "content-light-level"))
			if (res < 1) res = 1;
	}
	return res;
}

/* Extract parameter-set NAL units from the HEVCDecoderConfigurationRecord
 * (hvcC, ISO 14496-15 §8.3.3) stored in GStreamer codec_data cap.
 * For MP4/MKV files with stream-format=hvc1/hev1, the SPS (and VPS/PPS) live
 * here rather than in the regular buffer stream, so the bitstream probe would
 * never see the SPS — and therefore miss HLG whose only indicator is
 * transfer_characteristics=18 in the SPS VUI. */
static void preingest_hevc_codec_data(GstCaps *caps, std::vector<uint8_t> &out)
{
	if (!caps || gst_caps_get_size(caps) == 0) return;
	GstStructure *str = gst_caps_get_structure(caps, 0);
	if (!str) return;
	const GValue *cdval = gst_structure_get_value(str, "codec_data");
	if (!cdval) return;
	GstBuffer *cdbuf = gst_value_get_buffer(cdval);
	if (!cdbuf) return;
	GstMapInfo map;
	if (!gst_buffer_map(cdbuf, &map, GST_MAP_READ)) return;
	const uint8_t *d = map.data;
	gsize sz = map.size;
	/* Fixed hvcC header is 22 bytes; byte 22 = numOfArrays */
	static const uint8_t sc[4] = {0, 0, 0, 1};
	if (sz > 22)
	{
		uint8_t numArrays = d[22];
		gsize pos = 23;
		for (uint8_t a = 0; a < numArrays && pos + 3 <= sz; a++)
		{
			pos++;  /* array_completeness(1) | reserved(1) | nal_unit_type(6) */
			uint16_t numNalus = ((uint16_t)d[pos] << 8) | d[pos + 1];
			pos += 2;
			for (uint16_t n = 0; n < numNalus && pos + 2 <= sz; n++)
			{
				uint16_t naluLen = ((uint16_t)d[pos] << 8) | d[pos + 1];
				pos += 2;
				if (pos + naluLen > sz) break;
				out.insert(out.end(), sc, sc + 4);
				out.insert(out.end(), d + pos, d + pos + naluLen);
				pos += naluLen;
			}
		}
	}
	gst_buffer_unmap(cdbuf, &map);
}



GstPadProbeReturn eServiceMP3::hdrProbeCallback(GstPad*, GstPadProbeInfo *info, gpointer user_data)
{
	eServiceMP3 *self = static_cast<eServiceMP3*>(user_data);
	GstBuffer *buf = GST_PAD_PROBE_INFO_BUFFER(info);
	if (!buf) return GST_PAD_PROBE_OK;

	/* Atomic pre-check before any buffer mapping or mutex: stopHDRProbe()
	 * sets m_hdr_probe_active to 0 via g_atomic_int_set() WITHOUT acquiring
	 * the mutex, so this check is always safe and avoids the cost of
	 * gst_buffer_map + mutex acquisition when we are already stopping. */
	if (!g_atomic_int_get(&self->m_hdr_probe_active))
		return GST_PAD_PROBE_REMOVE;

	GstMapInfo map;
	if (!gst_buffer_map(buf, &map, GST_MAP_READ))
		return GST_PAD_PROBE_OK;  /* DMA/opaque buffer — skip silently */

	g_mutex_lock(&self->m_hdr_probe_mutex);
	if (!g_atomic_int_get(&self->m_hdr_probe_active))
	{
		/* Double-check under mutex in case stopHDRProbe() ran between the
		 * atomic pre-check above and acquiring the mutex. */
		g_mutex_unlock(&self->m_hdr_probe_mutex);
		gst_buffer_unmap(buf, &map);
		return GST_PAD_PROBE_REMOVE;
	}
	if (self->m_hdr_probe_es.size() < (8 * 1024 * 1024))
	{
		const uint8_t *d = map.data;
		gsize sz = map.size;
		/* Detect Annex-B (00 00 01 or 00 00 00 01 start codes) vs
		 * length-prefixed hvc1/hev1 (4-byte big-endian NAL length).
		 * Convert length-prefixed to Annex-B so HevcHDR::classify works
		 * regardless of what stream-format the downstream sink negotiated. */
		bool annexb = sz >= 3 && d[0] == 0 && d[1] == 0 &&
		              (d[2] == 1 || (sz >= 4 && d[2] == 0 && d[3] == 1));
		if (annexb)
		{
			self->m_hdr_probe_es.insert(self->m_hdr_probe_es.end(), d, d + sz);
		}
		else
		{
			/* Length-prefixed: convert each NAL unit to Annex-B */
			static const uint8_t sc[4] = {0, 0, 0, 1};
			gsize pos = 0;
			while (pos + 4 <= sz)
			{
				uint32_t nlen = ((uint32_t)d[pos] << 24) | ((uint32_t)d[pos+1] << 16)
				              | ((uint32_t)d[pos+2] << 8) | d[pos+3];
				pos += 4;
				if (nlen == 0 || pos + nlen > sz) break;
				self->m_hdr_probe_es.insert(self->m_hdr_probe_es.end(), sc, sc + 4);
				self->m_hdr_probe_es.insert(self->m_hdr_probe_es.end(), d + pos, d + pos + nlen);
				pos += nlen;
			}
		}
	}
	g_mutex_unlock(&self->m_hdr_probe_mutex);

	gst_buffer_unmap(buf, &map);
	return GST_PAD_PROBE_OK;
}

void eServiceMP3::startHDRProbe()
{
	/* Guard against stale GStreamer bus messages delivered after stop() */
	if (m_state != stRunning || !m_gst_playbin) return;
	stopHDRProbe();

	/* Find the first src pad in the pipeline that outputs video/x-h265.
	 * Search by caps rather than by element name — STB pipelines often do not
	 * include a standard h265parse element and use proprietary HEVC decoders.
	 * Demuxer src pads are encountered first and always carry CPU-accessible
	 * buffers (unlike hardware decoder sink/src pads which may be DMA-only). */
	GstPad *hevc_pad = NULL;
	GstIterator *eit = gst_bin_iterate_recurse(GST_BIN(m_gst_playbin));
	GValue eitem = G_VALUE_INIT;
	bool edone = false;
	while (!edone)
	{
		switch (gst_iterator_next(eit, &eitem))
		{
			case GST_ITERATOR_OK:
			{
				GstElement *el = GST_ELEMENT(g_value_get_object(&eitem));
				if (el)
				{
					GstIterator *pit = gst_element_iterate_src_pads(el);
					GValue pitem = G_VALUE_INIT;
					bool pdone = false;
					while (!pdone)
					{
						switch (gst_iterator_next(pit, &pitem))
						{
							case GST_ITERATOR_OK:
							{
								GstPad *pad = GST_PAD(g_value_get_object(&pitem));
								GstCaps *caps = gst_pad_get_current_caps(pad);
								if (caps)
								{
									for (guint i = 0; i < gst_caps_get_size(caps) && !hevc_pad; i++)
									{
										const gchar *sname = gst_structure_get_name(
											gst_caps_get_structure(caps, i));
										if (sname && g_str_has_prefix(sname, "video/x-h265"))
										{
											hevc_pad = GST_PAD(gst_object_ref(pad));
											pdone = edone = true;
										}
									}
									gst_caps_unref(caps);
								}
								g_value_reset(&pitem);
								break;
							}
							case GST_ITERATOR_RESYNC: gst_iterator_resync(pit); break;
							default: pdone = true; break;
						}
					}
					g_value_unset(&pitem);
					gst_iterator_free(pit);
				}
				g_value_reset(&eitem);
				break;
			}
			case GST_ITERATOR_RESYNC: gst_iterator_resync(eit); break;
			default: edone = true; break;
		}
	}
	g_value_unset(&eitem);
	gst_iterator_free(eit);

	if (!hevc_pad)
	{
		eDebug("[eServiceMP3] HDR probe: no HEVC src pad found in pipeline");
		return;
	}

	/* Fast path: check if the HEVC pad caps already carry colorimetry.
	 * updateHDRFromVideoPad() only checked the playbin video pad and static
	 * "src" pads.  Demuxer dynamic pads (video_0 etc.) are found here first.
	 * For MKV/MP4, the demuxer maps ColourTransferCharacteristics / the colr
	 * box directly into pad-caps colorimetry — the same data ffprobe reads. */
	{
		GstCaps *caps = gst_pad_get_current_caps(hevc_pad);
		if (caps)
		{
			int hdrFromCaps = caps_hdr_value(caps);
			gst_caps_unref(caps);
			if (hdrFromCaps > 0)
			{
				eDebug("[eServiceMP3] HDR probe: result %d from HEVC pad colorimetry", hdrFromCaps);
				gst_object_unref(hevc_pad);
				if (hdrFromCaps != m_hdr_type)
				{
					m_hdr_type = hdrFromCaps;
					m_event((iPlayableService*)this, evUpdatedInfo);
				}
				return;
			}
		}
	}

	g_mutex_lock(&m_hdr_probe_mutex);
	m_hdr_probe_es.clear();
	m_hdr_probe_es.reserve(512 * 1024);
	/* Pre-populate from hvcC codec_data so the SPS is visible to classify()
	 * even for hvc1/hev1 streams where parameter sets are not in-band. */
	{
		GstCaps *caps = gst_pad_get_current_caps(hevc_pad);
		if (caps) { preingest_hevc_codec_data(caps, m_hdr_probe_es); gst_caps_unref(caps); }
	}
	m_hdr_probe_last_classify = 0;
	m_hdr_probe_first_sps_at = 0;
	g_atomic_int_set(&m_hdr_probe_active, 1);
	g_mutex_unlock(&m_hdr_probe_mutex);

	m_hdr_probe_id = gst_pad_add_probe(hevc_pad, GST_PAD_PROBE_TYPE_BUFFER,
	                                    hdrProbeCallback, this, NULL);
	m_hdr_probe_pad = hevc_pad; /* takes ownership of ref */

	m_hdr_probe_timer = eTimer::create(eApp);
	CONNECT(m_hdr_probe_timer->timeout, eServiceMP3::checkHDRProbe);
	m_hdr_probe_timer->start(200, false);
	eDebug("[eServiceMP3] HDR probe: started on HEVC src pad");
}

void eServiceMP3::stopHDRProbe()
{
	if (m_hdr_probe_timer) { m_hdr_probe_timer->stop(); m_hdr_probe_timer = 0; }

	/* Set the active flag atomically WITHOUT acquiring m_hdr_probe_mutex.
	 * This is the key fix for the UI lockup on H.265 channel zapping:
	 *  - gst_element_set_state(NULL) can return GST_STATE_CHANGE_ASYNC,
	 *    meaning the streaming thread is still running hdrProbeCallback.
	 *  - hdrProbeCallback holds m_hdr_probe_mutex while copying H.265 I-frame
	 *    data (can be 500KB-2MB per frame), which could block the main thread
	 *    for a significant time if we call g_mutex_lock() here.
	 *  - By using g_atomic_int_set(), we set inactive instantly without
	 *    contending the mutex.  The probe callback's atomic pre-check sees the
	 *    flag and returns GST_PAD_PROBE_REMOVE without touching the mutex at all.
	 * m_hdr_probe_es cleanup: try a non-blocking lock; if the probe is mid-copy
	 * skip the clear — the data is harmless and freed with the object. */
	g_atomic_int_set(&m_hdr_probe_active, 0);
	if (g_mutex_trylock(&m_hdr_probe_mutex))
	{
		std::vector<uint8_t>().swap(m_hdr_probe_es);
		g_mutex_unlock(&m_hdr_probe_mutex);
	}
	std::vector<uint8_t>().swap(m_hdr_probe_snap); /* main-thread only, no lock needed */

	/* Release our pad ref; GStreamer holds its own ref until the probe is removed. */
	m_hdr_probe_id = 0;
	if (m_hdr_probe_pad) { gst_object_unref(m_hdr_probe_pad); m_hdr_probe_pad = NULL; }
}

void eServiceMP3::checkHDRProbe()
{
	/* Swap out new data under lock in O(1), then append to the main-thread
	 * accumulator and classify entirely outside the lock.  This keeps the
	 * mutex hold-time to a pointer swap rather than an O(N) copy that would
	 * stall the streaming thread (hdrProbeCallback) for the copy duration. */
	std::vector<uint8_t> batch;
	g_mutex_lock(&m_hdr_probe_mutex);
	batch.swap(m_hdr_probe_es);                    /* O(1) */
	m_hdr_probe_es.reserve(64 * 1024);             /* pre-allocate for next batch */
	g_mutex_unlock(&m_hdr_probe_mutex);

	if (batch.empty()) return;

	m_hdr_probe_snap.insert(m_hdr_probe_snap.end(), batch.begin(), batch.end());

	/* Only re-classify every 64KB of new data */
	if (m_hdr_probe_snap.size() - m_hdr_probe_last_classify < (64 * 1024) &&
	    m_hdr_probe_snap.size() < (8 * 1024 * 1024))
		return;
	m_hdr_probe_last_classify = m_hdr_probe_snap.size();

	bool sawSPS = false;
	int result = HevcHDR::classify(m_hdr_probe_snap.data(), (int)m_hdr_probe_snap.size(), &sawSPS);

	if (result == HevcHDR::HDR_HDR10 || result == HevcHDR::HDR_HLG || result == HevcHDR::HDR_GENERIC)
	{
		int newHdrType = (result == HevcHDR::HDR_HDR10) ? 1 :
		                 (result == HevcHDR::HDR_HLG)   ? 2 : 3;
		eDebug("[eServiceMP3] HDR probe: result %d from bitstream", newHdrType);
		stopHDRProbe();
		if (newHdrType != m_hdr_type)
		{
			m_hdr_type = newHdrType;
			m_event((iPlayableService*)this, evUpdatedInfo);
		}
		return;
	}

	if (sawSPS)
	{
		if (!m_hdr_probe_first_sps_at) m_hdr_probe_first_sps_at = m_hdr_probe_snap.size();
		if (m_hdr_probe_snap.size() - m_hdr_probe_first_sps_at >= (768 * 1024))
		{
			/* Read enough past first SPS without finding HDR -> SDR */
			stopHDRProbe();
			return;
		}
	}

	if (m_hdr_probe_snap.size() >= (8 * 1024 * 1024))
		stopHDRProbe();
}

/* -------------------------------------------------------------------------- */

void eServiceMP3::updateHDRFromVideoPad()
{
	if (!m_gst_playbin || m_state != stRunning)
		return;

	int hdr = -1;

	/* primary: playbin video pad (pre-sink, carries parsed caps with native video) */
	GstPad *pad = 0;
	g_signal_emit_by_name(m_gst_playbin, "get-video-pad", 0, &pad);
	if (pad)
	{
		GstCaps *caps = gst_pad_get_current_caps(pad);
		if (caps) { hdr = caps_hdr_value(caps); gst_caps_unref(caps); }
		gst_object_unref(pad);
	}

	/* fallback: search pipeline for ANY src pad exposing colorimetry.
	 * Demuxers (matroskademux, qtdemux) expose video on dynamic src pads
	 * named "video_0" etc., NOT on a static pad named "src".  Iterating
	 * all src pads (as startHDRProbe does) finds the pad that carries
	 * ColourTransferCharacteristics / colr-box colorimetry from the container
	 * header — the same data source that ffprobe reads. */
	if (hdr < 0)
	{
		GstIterator *eit = gst_bin_iterate_recurse(GST_BIN(m_gst_playbin));
		GValue eitem = G_VALUE_INIT;
		bool edone = false;
		while (!edone)
		{
			switch (gst_iterator_next(eit, &eitem))
			{
				case GST_ITERATOR_OK:
				{
					GstElement *el = GST_ELEMENT(g_value_get_object(&eitem));
					if (el)
					{
						GstIterator *pit = gst_element_iterate_src_pads(el);
						GValue pitem = G_VALUE_INIT;
						bool pdone = false;
						while (!pdone)
						{
							switch (gst_iterator_next(pit, &pitem))
							{
								case GST_ITERATOR_OK:
								{
									GstPad *sp = GST_PAD(g_value_get_object(&pitem));
									GstCaps *c = gst_pad_get_current_caps(sp);
									if (c) { int v = caps_hdr_value(c); gst_caps_unref(c);
										if (v >= 0) { hdr = v; if (v > 0) pdone = edone = true; }
									}
									g_value_reset(&pitem);
									break;
								}
								case GST_ITERATOR_RESYNC: gst_iterator_resync(pit); break;
								default: pdone = true; break;
							}
						}
						g_value_unset(&pitem);
						gst_iterator_free(pit);
					}
					g_value_reset(&eitem);
					break;
				}
				case GST_ITERATOR_RESYNC: gst_iterator_resync(eit); break;
				default: edone = true; break;
			}
		}
		g_value_unset(&eitem);
		gst_iterator_free(eit);
	}

	eDebug("[eServiceMP3] HDR probe: result %d from video pad colorimetry", hdr);

	/* Only update m_hdr_type when caps give a positive result.
	 * Do NOT reset a previously probed HDR result just because
	 * caps lack colorimetry (e.g. older STB GStreamer builds). */
	if (hdr > 0 && hdr != m_hdr_type)
	{
		m_hdr_type = hdr;
		m_event((iPlayableService*)this, evUpdatedInfo);
	}
}
#endif /* HAS_SOFTWARE_HDR_DETECTION */

RESULT eServiceMP3::info(ePtr<iServiceInformation>&i)
{
	i = this;
	return 0;
}

RESULT eServiceMP3::getName(std::string &name)
{
	std::string title = m_ref.getName();
	if (title.empty())
	{
		name = m_ref.path;
		size_t n = name.rfind('/');
		if (n != std::string::npos)
			name = name.substr(n + 1);
	}
	else
		name = title;

	m_prov = m_ref.prov;

	return 0;
}

RESULT eServiceMP3::getEvent(ePtr<eServiceEvent> &evt, int nownext)
{
	evt = nownext ? m_event_next : m_event_now;
	if (!evt)
		return -1;
	return 0;
}

int eServiceMP3::getInfo(int w)
{
	const gchar *tag = 0;

	switch (w)
	{
	case sServiceref: return m_ref;
	case sVideoHeight: return m_height;
	case sVideoWidth: return m_width;
	case sFrameRate: return m_framerate;
	case sProgressive: return m_progressive;
	case sGamma: return m_gamma;
	case sHDRType: return m_hdr_type;
	case sAspect: return m_aspect;
	case sTagTitle:
	case sTagArtist:
	case sTagAlbum:
	case sTagTitleSortname:
	case sTagArtistSortname:
	case sTagAlbumSortname:
	case sTagDate:
	case sTagComposer:
	case sTagGenre:
	case sTagComment:
	case sTagExtendedComment:
	case sTagLocation:
	case sTagHomepage:
	case sTagDescription:
	case sTagVersion:
	case sTagISRC:
	case sTagOrganization:
	case sTagCopyright:
	case sTagCopyrightURI:
	case sTagContact:
	case sTagLicense:
	case sTagLicenseURI:
	case sTagCodec:
	case sTagAudioCodec:
	case sTagVideoCodec:
	case sTagEncoder:
	case sTagLanguageCode:
	case sTagKeywords:
	case sTagChannelMode:
	case sUser+12:
		return resIsString;
	case sTagTrackGain:
	case sTagTrackPeak:
	case sTagAlbumGain:
	case sTagAlbumPeak:
	case sTagReferenceLevel:
	case sTagBeatsPerMinute:
	case sTagImage:
	case sTagPreviewImage:
	case sTagAttachment:
		return resIsPyObject;
	case sTagTrackNumber:
		tag = GST_TAG_TRACK_NUMBER;
		break;
	case sTagTrackCount:
		tag = GST_TAG_TRACK_COUNT;
		break;
	case sTagAlbumVolumeNumber:
		tag = GST_TAG_ALBUM_VOLUME_NUMBER;
		break;
	case sTagAlbumVolumeCount:
		tag = GST_TAG_ALBUM_VOLUME_COUNT;
		break;
	case sTagBitrate:
		tag = GST_TAG_BITRATE;
		break;
	case sTagNominalBitrate:
		tag = GST_TAG_NOMINAL_BITRATE;
		break;
	case sTagMinimumBitrate:
		tag = GST_TAG_MINIMUM_BITRATE;
		break;
	case sTagMaximumBitrate:
		tag = GST_TAG_MAXIMUM_BITRATE;
		break;
	case sTagSerial:
		tag = GST_TAG_SERIAL;
		break;
	case sTagEncoderVersion:
		tag = GST_TAG_ENCODER_VERSION;
		break;
	case sTagCRC:
		tag = "has-crc";
		break;
	case sBuffer: return m_bufferInfo.bufferPercent;
	case sVideoType:
	{
		if (!videoSink) return -1;
		guint64 v = -1;
		g_signal_emit_by_name(videoSink, "get-video-codec", &v);
		return (int) v;
		break;
	}
	case sSID: return m_ref.getData(1);
	default:
		return resNA;
	}

	if (!m_stream_tags || !tag)
		return 0;

	guint value;
	if (gst_tag_list_get_uint(m_stream_tags, tag, &value))
		return (int) value;

	return 0;
}

std::string eServiceMP3::getInfoString(int w)
{
	switch (w)
	{
	case sProvider:
	{
		if (m_sourceinfo.is_streaming) {
			if (m_prov.empty()) {
				return "IPTV";
			} else {
				return m_prov;
			}
		}
		return "FILE";
	}
	case sServiceref:
		return m_ref.toString();
	default:
		break;
	}

	if (w == sVideoInfo)
	{
		char buff[100];
		snprintf(buff, sizeof(buff), "%d|%d|%d|%d|%d|%d",
				m_width,
				m_height,
				m_framerate,
				m_progressive,
				m_aspect,
				m_gamma
				);
		std::string videoInfo = buff;
		return videoInfo;
	}

	if ( !m_stream_tags && w < sUser && w > 26 )
		return "";
	const gchar *tag = 0;
	switch (w)
	{
	case sTagTitle:
		tag = GST_TAG_TITLE;
		break;
	case sTagArtist:
		tag = GST_TAG_ARTIST;
		break;
	case sTagAlbum:
		tag = GST_TAG_ALBUM;
		break;
	case sTagTitleSortname:
		tag = GST_TAG_TITLE_SORTNAME;
		break;
	case sTagArtistSortname:
		tag = GST_TAG_ARTIST_SORTNAME;
		break;
	case sTagAlbumSortname:
		tag = GST_TAG_ALBUM_SORTNAME;
		break;
	case sTagDate:
		GDate *date;
		GstDateTime *date_time;
		if (gst_tag_list_get_date(m_stream_tags, GST_TAG_DATE, &date))
		{
			gchar res[5];
			snprintf(res, sizeof(res), "%06d", g_date_get_year(date));
			g_date_free(date);
			return (std::string)res;
		}
		else if (gst_tag_list_get_date_time(m_stream_tags, GST_TAG_DATE_TIME, &date_time))
		{
			if (gst_date_time_has_year(date_time))
			{
				gchar res[5];
				snprintf(res, sizeof(res), "%06d", gst_date_time_get_year(date_time));
				gst_date_time_unref(date_time);
				return (std::string)res;
			}
			gst_date_time_unref(date_time);
		}
		break;
	case sTagComposer:
		tag = GST_TAG_COMPOSER;
		break;
	case sTagGenre:
		tag = GST_TAG_GENRE;
		break;
	case sTagComment:
		tag = GST_TAG_COMMENT;
		break;
	case sTagExtendedComment:
		tag = GST_TAG_EXTENDED_COMMENT;
		break;
	case sTagLocation:
		tag = GST_TAG_LOCATION;
		break;
	case sTagHomepage:
		tag = GST_TAG_HOMEPAGE;
		break;
	case sTagDescription:
		tag = GST_TAG_DESCRIPTION;
		break;
	case sTagVersion:
		tag = GST_TAG_VERSION;
		break;
	case sTagISRC:
		tag = GST_TAG_ISRC;
		break;
	case sTagOrganization:
		tag = GST_TAG_ORGANIZATION;
		break;
	case sTagCopyright:
		tag = GST_TAG_COPYRIGHT;
		break;
	case sTagCopyrightURI:
		tag = GST_TAG_COPYRIGHT_URI;
		break;
	case sTagContact:
		tag = GST_TAG_CONTACT;
		break;
	case sTagLicense:
		tag = GST_TAG_LICENSE;
		break;
	case sTagLicenseURI:
		tag = GST_TAG_LICENSE_URI;
		break;
	case sTagCodec:
		tag = GST_TAG_CODEC;
		break;
	case sTagAudioCodec:
		tag = GST_TAG_AUDIO_CODEC;
		break;
	case sTagVideoCodec:
		tag = GST_TAG_VIDEO_CODEC;
		break;
	case sTagEncoder:
		tag = GST_TAG_ENCODER;
		break;
	case sTagLanguageCode:
		tag = GST_TAG_LANGUAGE_CODE;
		break;
	case sTagKeywords:
		tag = GST_TAG_KEYWORDS;
		break;
	case sTagChannelMode:
		tag = "channel-mode";
		break;
	case sUser+12:
		return m_errorInfo.error_message;
	default:
		return "";
	}
	if ( !tag )
		return "";
	gchar *value = NULL;
	if (m_stream_tags && gst_tag_list_get_string(m_stream_tags, tag, &value))
	{
		std::string res = value;
		g_free(value);
		return res;
	}
	return "";
}

ePtr<iServiceInfoContainer> eServiceMP3::getInfoObject(int w)
{
	eServiceMP3InfoContainer *container = new eServiceMP3InfoContainer;
	ePtr<iServiceInfoContainer> retval = container;
	const gchar *tag = 0;
	bool isBuffer = false;
	switch (w)
	{
		case sTagTrackGain:
			tag = GST_TAG_TRACK_GAIN;
			break;
		case sTagTrackPeak:
			tag = GST_TAG_TRACK_PEAK;
			break;
		case sTagAlbumGain:
			tag = GST_TAG_ALBUM_GAIN;
			break;
		case sTagAlbumPeak:
			tag = GST_TAG_ALBUM_PEAK;
			break;
		case sTagReferenceLevel:
			tag = GST_TAG_REFERENCE_LEVEL;
			break;
		case sTagBeatsPerMinute:
			tag = GST_TAG_BEATS_PER_MINUTE;
			break;
		case sTagImage:
			tag = GST_TAG_IMAGE;
			isBuffer = true;
			break;
		case sTagPreviewImage:
			tag = GST_TAG_PREVIEW_IMAGE;
			isBuffer = true;
			break;
		case sTagAttachment:
			tag = GST_TAG_ATTACHMENT;
			isBuffer = true;
			break;
		default:
			break;
	}

	if (m_stream_tags && tag)
	{
		if (isBuffer)
		{
			const GValue *gv_buffer = gst_tag_list_get_value_index(m_stream_tags, tag, 0);
			if ( gv_buffer )
			{
				GstBuffer *buffer;
				buffer = gst_value_get_buffer (gv_buffer);
				container->setBuffer(buffer);
			}
		}
		else
		{
			gdouble value = 0.0;
			gst_tag_list_get_double(m_stream_tags, tag, &value);
			container->setDouble(value);
		}
	}
	return retval;
}

RESULT eServiceMP3::audioChannel(ePtr<iAudioChannelSelection> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::audioTracks(ePtr<iAudioTrackSelection> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::cueSheet(ePtr<iCueSheet> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::subtitle(ePtr<iSubtitleOutput> &ptr)
{
	ptr = this;
	return 0;
}

RESULT eServiceMP3::audioDelay(ePtr<iAudioDelay> &ptr)
{
	ptr = this;
	return 0;
}

int eServiceMP3::getNumberOfTracks()
{
 	return m_audioStreams.size();
}

int eServiceMP3::getCurrentTrack()
{
	if (m_currentAudioStream == -1)
		g_object_get (G_OBJECT (m_gst_playbin), "current-audio", &m_currentAudioStream, NULL);
	return m_currentAudioStream;
}

RESULT eServiceMP3::selectTrack(unsigned int i)
{
	m_clear_buffers = true;
	int result = selectAudioStream(i);
	return result;
}

void eServiceMP3::clearBuffers(bool force)
{
	if ((!m_initial_start || !m_clear_buffers) && !force) return;

	/* Live streams cannot seek back; flushing would stall playback, so skip. */
	if (m_is_live && !force)
	{
		eDebug ("[eServiceMP3] Clear Buffers skipped (live stream)");
		return;
	}

	eDebug ("[eServiceMP3] Clear Buffers!");
	bool validposition = false;
	pts_t ppos = 0;
	if (getPlayPosition(ppos) >= 0)
	{
		validposition = true;
		ppos -= 9000; /* seek back ~100ms instead of 1s for faster audio switch */
		if (ppos < 0)
			ppos = 0;
	}
	if (validposition)
	{
		/* flush */
		int res = seekTo(ppos);
		if (res == -1)
		{
			m_clear_buffers = false;
			m_send_ev_start = false;
			stop();
			m_state = stIdle;
			start();
		}
	}
}

int eServiceMP3::selectAudioStream(int i, bool skipAudioFix)
{
	/* Validate index against our own track list to avoid relying solely on
	 * an immediate g_object_get readback which can return a stale value when
	 * GStreamer is in a transitional state. */
	if (hdAudioAuxRetryBlocked(m_gst_playbin))
		setHDAudioAuxRetryBlocked(m_gst_playbin, false);
	const int pending_native_retry = hdAudioNativeRetry(m_gst_playbin);
	if (pending_native_retry >= 0 && pending_native_retry != i)
		setHDAudioNativeRetry(m_gst_playbin, -1);

	if (i < 0 || i >= (int)m_audioStreams.size())
	{
		eDebug ("[eServiceMP3] selectAudioStream: index %d out of range (n=%d)", i, (int)m_audioStreams.size());
		return -1;
	}

	const HDAudioAuxMode aux_mode = !m_sourceinfo.is_streaming ?
		hdAudioAuxModeForCodec(m_audioStreams[i].codec) : hdAuxNone;
	HDAudioAuxState *active_aux = getHDAudioAuxState(m_gst_playbin);
	const HDAudioAuxMode previous_aux_mode = active_aux ? active_aux->mode : hdAuxNone;
	const bool native_eac3_to_aux = !active_aux && aux_mode == hdAuxAC3 &&
		m_currentAudioStream >= 0 && m_currentAudioStream < (int)m_audioStreams.size() &&
		m_audioStreams[m_currentAudioStream].type == atEAC3;
	bool native_handoff_reset = false;

	if (aux_mode != hdAuxNone || active_aux)
	{
		setHDAudioAuxReconfiguring(m_gst_playbin, true);
		GstState main_state = GST_STATE_NULL, main_pending = GST_STATE_VOID_PENDING;
		gst_element_get_state(m_gst_playbin, &main_state, &main_pending, 0);
		const bool resume_main = main_state == GST_STATE_PLAYING || main_pending == GST_STATE_PLAYING;
		if (resume_main)
		{
			gst_element_set_state(m_gst_playbin, GST_STATE_PAUSED);
			gst_element_get_state(m_gst_playbin, &main_state, &main_pending, 1 * GST_SECOND);
		}

		gint64 position_ns = -1;
		gst_element_query_position(m_gst_playbin, GST_FORMAT_TIME, &position_ns);
		guint restore_flags = 0;
		GstElement *main_audio_sink = NULL;
		if (active_aux)
		{
			restore_flags = active_aux->mainFlags;
			if (active_aux->mainAudioSink)
				main_audio_sink = GST_ELEMENT(gst_object_ref(active_aux->mainAudioSink));
		}
		else
		{
			g_object_get(G_OBJECT(m_gst_playbin), "flags", &restore_flags, NULL);
			if (aux_mode != hdAuxNone)
				main_audio_sink = quiesceHDAudioMainSink(m_gst_playbin);
		}

		if (active_aux)
			stopHDAudioAuxPipeline(m_gst_playbin, false);

		if (aux_mode != hdAuxNone)
		{
			bool prepared = false;
			if (!main_audio_sink)
			{
				setHDAudioAuxRetryBlocked(m_gst_playbin, true);
				g_object_set(G_OBJECT(m_gst_playbin), "flags", restore_flags, NULL);
				if (resume_main)
					gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);
			}
			else
			{
				const guint video_only_flags = restore_flags & ~GST_PLAY_FLAG_AUDIO;
				g_object_set(G_OBJECT(m_gst_playbin), "flags", video_only_flags, NULL);
				g_object_set(G_OBJECT(m_gst_playbin), "current-audio", i, NULL);

				GError *uri_error = NULL;
				gchar *uri = g_filename_to_uri(m_ref.path.c_str(), NULL, &uri_error);
				prepared = uri && prepareHDAudioAuxPipeline(m_gst_playbin, uri, i,
					aux_mode, m_audioStreams[i].channels, restore_flags, position_ns, main_audio_sink);
				if (uri_error) g_error_free(uri_error);
				g_free(uri);

				if (!prepared)
				{
					setHDAudioAuxRetryBlocked(m_gst_playbin, true);
					restoreHDAudioMainSink(m_gst_playbin, main_audio_sink, restore_flags);
					if (resume_main)
						gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);
				}
				else
				{
					setHDAudioAuxState(m_gst_playbin, GST_STATE_PLAYING);
					if (!positionHDAudioAuxAfterStart(m_gst_playbin, position_ns))
					{
						setHDAudioAuxRetryBlocked(m_gst_playbin, true);
						stopHDAudioAuxPipeline(m_gst_playbin, true);
						prepared = false;
					}
					else if (!resume_main)
					{
						setHDAudioAuxState(m_gst_playbin, GST_STATE_PAUSED);
						/* Cold start: the main pipeline was not yet PLAYING (or
						 * pending PLAYING) when this aux setup ran, so the
						 * resume_main branch below - the only other place this
						 * timer gets armed - never runs. That's a pure timing
						 * accident, not a sign the anti-freeze reset isn't
						 * needed: a fresh TrueHD/DTS-to-AC3 handoff can still
						 * leave the hardware audio passthrough/HDMI format in
						 * a state that freezes video on first frames, exactly
						 * as it can when reconfiguring an already-playing
						 * pipeline. Arm it here too so the fix isn't silently
						 * skipped depending on exactly when GStreamer happens
						 * to reach PLAYING relative to this call.
						 * clearBuffers() (forceAudioReset()'s job) already
						 * tolerates firing before a valid play position
						 * exists - it's a no-op in that case - so this is
						 * safe even if PLAYING hasn't been reached yet when
						 * the timer fires. */
						m_passthrough_fix_timer->stop();
						m_passthrough_fix_timer->start(300, true);
					}

					if (resume_main)
					{
						gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);
						if (position_ns < 500 * GST_MSECOND || native_eac3_to_aux)
						{
							m_passthrough_fix_timer->stop();
							m_passthrough_fix_timer->start(300, true);
						}
					}
				}
				gst_object_unref(main_audio_sink);
			}

			if (prepared)
			{
				setHDAudioAuxReconfiguring(m_gst_playbin, false);
				m_currentAudioStream = i;
				if (!skipAudioFix)
				{
					m_event((iPlayableService*)this, evUpdatedInfo);
					setCacheEntry(true, i);
				}
				return 0;
			}
		}
		else
		{
			restoreHDAudioMainSink(m_gst_playbin, main_audio_sink, restore_flags);
#ifdef PASSTHROUGH_FIX
			if (previous_aux_mode == hdAuxAC3 && m_audioStreams[i].type == atEAC3 &&
				eConfigManager::getConfigBoolValue("config.av.passthrough_fix", false))
				native_handoff_reset = true;
#endif
			g_object_set(G_OBJECT(m_gst_playbin), "current-audio", i, NULL);
			if (main_audio_sink)
				gst_object_unref(main_audio_sink);
			if (resume_main)
				gst_element_set_state(m_gst_playbin, GST_STATE_PLAYING);
		}
		setHDAudioAuxReconfiguring(m_gst_playbin, false);
	}

	int current_audio, current_audio_orig;
	g_object_get (G_OBJECT (m_gst_playbin), "current-audio", &current_audio_orig, NULL);
	g_object_set (G_OBJECT (m_gst_playbin), "current-audio", i, NULL);
	g_object_get (G_OBJECT (m_gst_playbin), "current-audio", &current_audio, NULL);
	if (current_audio != i)
	{
#ifdef PASSTHROUGH_FIX
		if (native_handoff_reset)
			setHDAudioNativeRetry(m_gst_playbin, i);
#endif
		/* GStreamer may be in a transitional state and hasn't applied the
		 * property yet. Since we validated the index ourselves, trust the set. */
		eDebug ("[eServiceMP3] selectAudioStream: readback returned %d (expected %d), trusting range-validated set", current_audio, i);
		current_audio = i;
	}
	if ( current_audio == i )
	{
		if (!skipAudioFix)
		{
			eDebug ("[eServiceMP3] switched to audio stream %i", current_audio);
			m_currentAudioStream = i;
			m_event((iPlayableService*)this, evUpdatedInfo);
#ifdef PASSTHROUGH_FIX
			if (native_handoff_reset)
			{
				setHDAudioNativeEac3ResetPending(m_gst_playbin, true);
				m_passthrough_fix_timer->stop();
				m_passthrough_fix_timer->start(300, true);
			}
			else
			{
				GstPad* pad = 0;
				g_signal_emit_by_name (m_gst_playbin, "get-audio-pad", i, &pad);
				GstCaps* caps = gst_pad_get_current_caps(pad);
				gst_object_unref(pad);
				if (caps) {
					GstStructure* str = gst_caps_get_structure(caps, 0);
					const gchar *g_type = gst_structure_get_name(str);
					audiotype_t apidtype = gstCheckAudioPad(str);
					gst_caps_unref(caps);
					if (apidtype == atAC3 || apidtype == atEAC3 || apidtype == atAAC || apidtype == atUnknown || apidtype == atPCM) {
						std::string pass = CFile::read("/proc/stb/audio/ac3");
						if (replace_all(replace_all(pass, "\r", ""), "\n", "") == "passthrough")
						{
							if (m_clear_buffers)
							{
								if (!hdAudioNativeEac3ResetPending(m_gst_playbin))
								{
									m_passthrough_fix_timer->stop();
									m_passthrough_fix_timer->start(apidtype == atEAC3 && i > 0 && current_audio_orig > -1 ? 2000 : 300, true);
								}
							}
						}
						else
							clearBuffers();
					}
					else
						clearBuffers();
				}
			}
#else
			clearBuffers();
#endif
			setCacheEntry(true, i);
		}
		return 0;
	}
	return -1;
}

int eServiceMP3::getCurrentChannel()
{
	return STEREO;
}

RESULT eServiceMP3::selectChannel(int i)
{
	eDebug("[eServiceMP3] selectChannel(%i)",i);
	return 0;
}

RESULT eServiceMP3::getTrackInfo(struct iAudioTrackInfo &info, unsigned int i)
{
	if (i >= m_audioStreams.size())
	{
		return -2;
	}

	info.m_description = m_audioStreams[i].codec;
	info.m_channels = m_audioStreams[i].channels;

	if (info.m_language.empty())
	{
		info.m_language = m_audioStreams[i].language_code;
	}

	return 0;
}

subtype_t getSubtitleType(GstPad* pad, gchar *g_codec=NULL)
{
	subtype_t type = stUnknown;
	GstCaps* caps = gst_pad_get_current_caps(pad);
	if (!caps && !g_codec)
	{
		caps = gst_pad_get_allowed_caps(pad);
	}

	if (caps && !gst_caps_is_empty(caps))
	{
		GstStructure* str = gst_caps_get_structure(caps, 0);
		if (str)
		{
			const gchar *g_type = gst_structure_get_name(str);
			eDebug("[eServiceMP3] getSubtitleType::subtitle probe caps type=%s", g_type ? g_type : "(null)");
			if (g_type)
			{
				if ( !strcmp(g_type, "subpicture/x-dvd") )
					type = stVOB;
				else if ( !strcmp(g_type, "subpicture/x-dvb") )
					type = stDVB;
				else if ( !strcmp(g_type, "text/x-pango-markup") )
					type = stSRT;
				else if ( !strcmp(g_type, "text/plain") || !strcmp(g_type, "text/x-plain") || !strcmp(g_type, "text/x-raw") )
					type = stPlainText;
				else if ( !strcmp(g_type, "subpicture/x-pgs") )
					type = stPGS;
				else
					eDebug("[eServiceMP3] getSubtitleType::unsupported subtitle caps %s (%s)", g_type, g_codec ? g_codec : "(null)");
			}
		}
	}
	else if ( g_codec )
	{
		eDebug("[eServiceMP3] getSubtitleType::subtitle probe codec tag=%s", g_codec);
		if ( !strcmp(g_codec, "VOB") )
			type = stVOB;
		else if ( !strcmp(g_codec, "SubStation Alpha") || !strcmp(g_codec, "SSA") )
			type = stSSA;
		else if ( !strcmp(g_codec, "ASS") )
			type = stASS;
		else if ( !strcmp(g_codec, "SRT") )
			type = stSRT;
		else if ( !strcmp(g_codec, "UTF-8 plain text") )
			type = stPlainText;
		else
			eDebug("[eServiceMP3] getSubtitleType::unsupported subtitle codec %s", g_codec);
	}
	else
		eDebug("[eServiceMP3] getSubtitleType::unidentifiable subtitle stream!");

	return type;
}

void eServiceMP3::gstBusCall(GstMessage *msg)
{
	if (!msg)
		return;
	gchar *sourceName;
	GstObject *source;
	GstElement *subsink;
	source = GST_MESSAGE_SRC(msg);
	if (!GST_IS_OBJECT(source))
		return;
	sourceName = gst_object_get_name(source);
#if 0
	gchar *string;
	if (gst_message_get_structure(msg))
		string = gst_structure_to_string(gst_message_get_structure(msg));
	else
		string = g_strdup(GST_MESSAGE_TYPE_NAME(msg));
	eDebug("[eServiceMP3] eTsRemoteSource::gst_message from %s: %s", sourceName, string);
	g_free(string);
#endif
	switch (GST_MESSAGE_TYPE (msg))
	{
		case GST_MESSAGE_EOS:
			m_event((iPlayableService*)this, evEOF);
			break;
		case GST_MESSAGE_STATE_CHANGED:
		{
			if(GST_MESSAGE_SRC(msg) != GST_OBJECT(m_gst_playbin))
				break;

			GstState old_state, new_state;
			gst_message_parse_state_changed(msg, &old_state, &new_state, NULL);

			if(old_state == new_state)
				break;

			eDebug("[eServiceMP3] state transition %s -> %s", gst_element_state_get_name(old_state), gst_element_state_get_name(new_state));

			GstStateChange transition = (GstStateChange)GST_STATE_TRANSITION(old_state, new_state);

			switch(transition)
			{
				case GST_STATE_CHANGE_READY_TO_PAUSED:
				{
					m_state = stRunning;
					m_event(this, evGstreamerStart);
					if (m_send_ev_start)
						m_event(this, evStart);
					GValue result = { 0, };
					GstIterator *children;
					subsink = gst_bin_get_by_name(GST_BIN(m_gst_playbin), "subtitle_sink");
					if (subsink)
					{
						/*
						 * FIX: Seems that subtitle sink have a delay of receiving subtitles buffer.
						 * So we move ahead the PTS of the subtitle sink by 2 seconds.
						 * Then we do aditional sync of subtitles if they arrive ahead of PTS
						 */
						g_object_set (G_OBJECT (subsink), "ts-offset", -2LL * GST_SECOND, NULL);
#ifdef GSTREAMER_SUBTITLE_SYNC_MODE_BUG
						/*
						 * HACK: disable sync mode for now, gstreamer suffers from a bug causing sparse streams to loose sync, after pause/resume / skip
						 * see: https://bugzilla.gnome.org/show_bug.cgi?id=619434
						 * Sideeffect of using sync=false is that we receive subtitle buffers (far) ahead of their
						 * display time.
						 * Not too far ahead for subtitles contained in the media container.
						 * But for external srt files, we could receive all subtitles at once.
						 * And not just once, but after each pause/resume / skip.
						 * So as soon as gstreamer has been fixed to keep sync in sparse streams, sync needs to be re-enabled.
						 */
						g_object_set (G_OBJECT (subsink), "sync", FALSE, NULL);
#endif
#if 0
						/* we should not use ts-offset to sync with the decoder time, we have to do our own decoder timekeeping */
						g_object_set (G_OBJECT (subsink), "ts-offset", -2LL * GST_SECOND, NULL);
						/* late buffers probably will not occur very often */
						g_object_set (G_OBJECT (subsink), "max-lateness", 0LL, NULL);
						/* avoid prerolling (it might not be a good idea to preroll a sparse stream) */
						g_object_set (G_OBJECT (subsink), "async", TRUE, NULL);
#endif
						eDebug("[eServiceMP3] subsink properties set!");
						gst_object_unref(subsink);
					}
					if (audioSink)
					{
						gst_object_unref(GST_OBJECT(audioSink));
						audioSink = NULL;
					}
					if (videoSink)
					{
						gst_object_unref(GST_OBJECT(videoSink));
						videoSink = NULL;
					}
					children = gst_bin_iterate_recurse(GST_BIN(m_gst_playbin));
					if (gst_iterator_find_custom(children, (GCompareFunc)match_sinktype, &result, (gpointer)"GstDVBAudioSink"))
					{
						audioSink = GST_ELEMENT_CAST(g_value_dup_object(&result));
						g_value_unset(&result);
					}
					gst_iterator_free(children);
					children = gst_bin_iterate_recurse(GST_BIN(m_gst_playbin));
					if (gst_iterator_find_custom(children, (GCompareFunc)match_sinktype, &result, (gpointer)"GstDVBVideoSink"))
					{
						videoSink = GST_ELEMENT_CAST(g_value_dup_object(&result));
						g_value_unset(&result);
					}
					gst_iterator_free(children);

					/* if we are in preroll already do not check again the state */
					if (!m_is_live)
					{
						m_is_live = (gst_element_get_state(m_gst_playbin, NULL, NULL, 0LL) == GST_STATE_CHANGE_NO_PREROLL);
					}

					setAC3Delay(ac3_delay);
					setPCMDelay(pcm_delay);
					if(!m_cuesheet_loaded) /* cuesheet CVR */
						loadCuesheet();
					updateEpgCacheNowNext();

					if (!videoSink || m_ref.getData(0) == 2) // show radio pic
					{
						bool showRadioBackground = eConfigManager::getConfigBoolValue("config.misc.showradiopic", true);
						std::string radio_pic = eConfigManager::getConfigValue(showRadioBackground ? "config.misc.radiopic" : "config.misc.blackradiopic");
						m_decoder = new eTSMPEGDecoder(NULL, 0);
						m_decoder->showSinglePic(radio_pic.c_str());
					}

				}	break;
				case GST_STATE_CHANGE_PAUSED_TO_PLAYING:
				{
					m_paused = false;
					if (hdAudioAuxRetryBlocked(m_gst_playbin))
					{
					}
					else if (getHDAudioAuxState(m_gst_playbin))
					{
						setHDAudioAuxState(m_gst_playbin, GST_STATE_PLAYING);
					}
					else if (hdAudioAuxReconfiguring(m_gst_playbin))
					{
					}
					else if (m_currentAudioStream < 0)
					{
						int autoaudio = -1; // -1 = no configured-language match found; track 0 is a valid match and must not be confused with "nothing to select"
						int autoaudio_level = 5;
						std::string configvalue;
						std::vector<std::string> autoaudio_languages;
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect1");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect2");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect3");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						configvalue = eConfigManager::getConfigValue("config.autolanguage.audio_autoselect4");
						if (configvalue != "" && configvalue != "None")
							autoaudio_languages.push_back(configvalue);
						for (unsigned int i = 0; i < m_audioStreams.size(); i++)
						{
							if (!m_audioStreams[i].language_code.empty())
							{
								int x = 1;
								for (std::vector<std::string>::iterator it = autoaudio_languages.begin(); x < autoaudio_level && it != autoaudio_languages.end(); x++, it++)
								{
									if ((*it).find(m_audioStreams[i].language_code) != std::string::npos)
									{
										autoaudio = i;
										autoaudio_level = x;
										break;
									}
								}
							}
						}

						/* Always select explicitly, even when no configured language
						 * matched and we're falling back to track 0: selectAudioStream()
						 * is what sets up TrueHD/DTS AC3 transcoding (hdAudioAuxModeForCodec)
						 * and the passthrough-fix seek-back that prevents a video freeze
						 * when that track first starts decoding. The previous `if (autoaudio)`
						 * check treated index 0 as "nothing found" and skipped this call
						 * whenever no language preference matched (or matched track 0
						 * itself), silently leaving GStreamer's own default audio selection
						 * in effect with none of the above ever engaging. */
						selectAudioStream(autoaudio >= 0 ? autoaudio : 0);
					}
					else
					{
						selectAudioStream(m_currentAudioStream);
					}
					m_clear_buffers = false;
					if (!m_initial_start)
					{
						m_initial_start = true;
					}
					m_event((iPlayableService*)this, evGstreamerPlayStarted);
				}	break;
				case GST_STATE_CHANGE_PLAYING_TO_PAUSED:
				{
					m_paused = true;
				}	break;
				case GST_STATE_CHANGE_PAUSED_TO_READY:
				{
					if (audioSink)
					{
						gst_object_unref(GST_OBJECT(audioSink));
						audioSink = NULL;
					}
					if (videoSink)
					{
						gst_object_unref(GST_OBJECT(videoSink));
						videoSink = NULL;
					}
				}	break;
			}
			break;
		}
		case GST_MESSAGE_ERROR:
		{
			gchar *debug;
			GError *err;
			gst_message_parse_error (msg, &err, &debug);
			g_free (debug);
			eWarning("[eServiceMP3] Gstreamer error: %s (%i) from %s", err->message, err->code, sourceName );
			if ( err->domain == GST_STREAM_ERROR )
			{
				if ( err->code == GST_STREAM_ERROR_CODEC_NOT_FOUND )
				{
					if ( g_strrstr(sourceName, "videosink") )
						m_event((iPlayableService*)this, evUser+11);
					else if ( g_strrstr(sourceName, "audiosink") )
						m_event((iPlayableService*)this, evUser+10);
				}
			}
			else if ( err->domain == GST_RESOURCE_ERROR )
			{
				if ( err->code == GST_RESOURCE_ERROR_OPEN_READ || err->code == GST_RESOURCE_ERROR_READ )
				{
					stop();
				}
			}
			g_error_free(err);
			break;
		}
		case GST_MESSAGE_WARNING:
		{
			gchar *debug_warn = NULL;
			GError *warn = NULL;
			gst_message_parse_warning (msg, &warn, &debug_warn);
			/* CVR this Warning occurs from time to time with external srt files
			When a new seek is done the problem off to long wait times before subtitles appears,
			after movie was restarted with a resume position is solved. */
			if(!strncmp(warn->message , "Internal data flow problem", 26) && !strncmp(sourceName, "subtitle_sink", 13))
			{
				eWarning("[eServiceMP3] Gstreamer warning : %s (%i) from %s" , warn->message, warn->code, sourceName);
				subsink = gst_bin_get_by_name(GST_BIN(m_gst_playbin), "subtitle_sink");
				if(subsink)
				{
					if (!gst_element_seek (subsink, m_currentTrickRatio, GST_FORMAT_TIME, (GstSeekFlags)(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_KEY_UNIT),
						GST_SEEK_TYPE_SET, m_last_seek_pos,
						GST_SEEK_TYPE_NONE, GST_CLOCK_TIME_NONE))
					{
						eDebug("[eServiceMP3] seekToImpl subsink failed");
					}
					gst_object_unref(subsink);
				}
			}
			g_free(debug_warn);
			g_error_free(warn);
			break;
		}
		case GST_MESSAGE_INFO:
		{
			gchar *debug;
			GError *inf;

			gst_message_parse_info (msg, &inf, &debug);
			g_free (debug);
			if ( inf->domain == GST_STREAM_ERROR && inf->code == GST_STREAM_ERROR_DECODE )
			{
				if ( g_strrstr(sourceName, "videosink") )
					m_event((iPlayableService*)this, evUser+14);
			}
			g_error_free(inf);
			break;
		}
		case GST_MESSAGE_TAG:
		{
			GstTagList *tags, *result;
			gst_message_parse_tag(msg, &tags);

			result = gst_tag_list_merge(m_stream_tags, tags, GST_TAG_MERGE_REPLACE);
			if (result)
			{
				if (m_stream_tags && gst_tag_list_is_equal(m_stream_tags, result))
				{
					gst_tag_list_free(tags);
					gst_tag_list_free(result);
					break;
				}
				if (m_stream_tags)
					gst_tag_list_free(m_stream_tags);
				m_stream_tags = result;
			}

			if (!m_coverart)
			{
				const GValue *gv_image = gst_tag_list_get_value_index(tags, GST_TAG_IMAGE, 0);
				if ( gv_image )
				{
					GstBuffer *buf_image;
					GstSample *sample;
					sample = (GstSample *)g_value_get_boxed(gv_image);
					buf_image = gst_sample_get_buffer(sample);
					int fd = open("/tmp/.id3coverart", O_CREAT|O_WRONLY|O_TRUNC, 0644);
					if (fd >= 0)
					{
						guint8 *data;
						gsize size;
						GstMapInfo map;
						gst_buffer_map(buf_image, &map, GST_MAP_READ);
						data = map.data;
						size = map.size;
						int ret = write(fd, data, size);
						gst_buffer_unmap(buf_image, &map);
						close(fd);
						m_coverart = true;
						m_event((iPlayableService*)this, evUpdateIDv3Cover);
						eDebug("[eServiceMP3] /tmp/.id3coverart %d bytes written ", ret);
					}
				}
			}
			gst_tag_list_free(tags);
			m_event((iPlayableService*)this, evUpdateTags);
			break;
		}
		/* TOC entry intercept used for chapter support CVR */
		case GST_MESSAGE_TOC:
		{
			HandleTocEntry(msg);
			break;
		}
		case GST_MESSAGE_ASYNC_DONE:
		{
			if(GST_MESSAGE_SRC(msg) != GST_OBJECT(m_gst_playbin))
				break;

			if (m_send_ev_start)
			{
				gint i, n_video = 0, n_audio = 0, n_text = 0;

				g_object_get (m_gst_playbin, "n-video", &n_video, NULL);
				g_object_get (m_gst_playbin, "n-audio", &n_audio, NULL);
				g_object_get (m_gst_playbin, "n-text", &n_text, NULL);


				eDebug("[eServiceMP3] async-done - %d video, %d audio, %d subtitle", n_video, n_audio, n_text);

				if ( n_video + n_audio <= 0 )
					stop();

				std::vector<audioStream> audioStreams_temp;
				std::vector<subtitleStream> subtitleStreams_temp;

				for (i = 0; i < n_audio; i++)
				{
					audioStream audio = {};
					gchar *g_codec, *g_lang;
					GstTagList *tags = NULL;
					GstPad* pad = 0;
					g_signal_emit_by_name (m_gst_playbin, "get-audio-pad", i, &pad);
					if(!pad)
						continue;
					GstCaps* caps = gst_pad_get_current_caps(pad);
					if (!caps)
					{
						gst_object_unref(pad);
						continue;
					}
					GstStructure* str = gst_caps_get_structure(caps, 0);
					const gchar *g_type = gst_structure_get_name(str);
					gint channels = 0;
					if (gst_structure_get_int(str, "channels", &channels) && channels > 0)
						audio.channels = channels;
					eDebug("[eServiceMP3] AUDIO STRUCT=%s channels=%d", g_type, audio.channels);

					if ((!strcmp(g_type, "audio/x-eac3") || !strcmp(g_type, "audio/eac3")) &&
						!g_object_get_qdata(G_OBJECT(pad), eac3AtmosProbeQuark()))
					{
						g_object_set_qdata(G_OBJECT(pad), eac3AtmosProbeQuark(), GUINT_TO_POINTER(1));
						gst_pad_add_probe(pad, GST_PAD_PROBE_TYPE_BUFFER, eac3AtmosProbe,
							new EAC3AtmosProbeData{i, 0}, freeEAC3AtmosProbeData);
					}

					if ((!strcmp(g_type, "audio/x-dts") || !strcmp(g_type, "audio/dts")) &&
						!g_object_get_qdata(G_OBJECT(pad), dtsHDProbeQuark()))
					{
						g_object_set_qdata(G_OBJECT(pad), dtsHDProbeQuark(), GUINT_TO_POINTER(1));
						gst_pad_add_probe(pad, GST_PAD_PROBE_TYPE_BUFFER, dtsHDProbe,
							new DTSHDProbeData(i), freeDTSHDProbeData);
					}
					gst_object_unref(pad);
					audio.type = gstCheckAudioPad(str);
					audio.language_code = "und";
					audio.codec = g_type;
					g_codec = NULL;
					g_lang = NULL;
					g_signal_emit_by_name (m_gst_playbin, "get-audio-tags", i, &tags);
					if (tags && GST_IS_TAG_LIST(tags))
					{
						if (gst_tag_list_get_string(tags, GST_TAG_AUDIO_CODEC, &g_codec))
						{
							audio.codec = std::string(g_codec);
							g_free(g_codec);
						}
						if (gst_tag_list_get_string(tags, GST_TAG_LANGUAGE_CODE, &g_lang))
						{
							audio.language_code = std::string(g_lang);
							g_free(g_lang);
						}
					}

					/* Refine only the human-readable codec description. Playback
					 * type/decoder/passthrough selection above is deliberately unchanged. */
					const gchar *profile = gst_structure_get_string(str, "profile");
					gchar *caps_desc = gst_structure_to_string(str);
					std::string audio_meta = audio.codec;
					if (profile) { audio_meta += " "; audio_meta += profile; }
					if (caps_desc) { audio_meta += " "; audio_meta += caps_desc; }

					gchar *audio_meta_lower = g_ascii_strdown(audio_meta.c_str(), -1);
					const bool has_atmos = audio_meta_lower &&
						(strstr(audio_meta_lower, "dolby atmos") || strstr(audio_meta_lower, "atmos") || strstr(audio_meta_lower, "joc"));

					const bool meta_truehd = audio_meta_lower &&
						(strstr(audio_meta_lower, "truehd") || strstr(audio_meta_lower, "true-hd"));
					const bool meta_dtshd = audio_meta_lower &&
						(strstr(audio_meta_lower, "dts-hd") || strstr(audio_meta_lower, "dts hd") || strstr(audio_meta_lower, "dtshd"));
					const bool meta_dtsx_pro = audio_meta_lower &&
						(strstr(audio_meta_lower, "dts:x pro") || strstr(audio_meta_lower, "dts x pro") || strstr(audio_meta_lower, "dtsx pro"));
					const bool meta_dtsx = audio_meta_lower &&
						(strstr(audio_meta_lower, "dts:x") || strstr(audio_meta_lower, "dts x") || strstr(audio_meta_lower, "dtsx"));
					const bool meta_dts_ma = audio_meta_lower &&
						(strstr(audio_meta_lower, "dts-hd master") || strstr(audio_meta_lower, "dts hd master") ||
						 strstr(audio_meta_lower, "dts-hd ma") || strstr(audio_meta_lower, "dts hd ma"));
					const bool meta_dts_hra = audio_meta_lower &&
						(strstr(audio_meta_lower, "dts-hd high resolution") || strstr(audio_meta_lower, "dts hd high resolution") ||
						 strstr(audio_meta_lower, "dts-hd hra") || strstr(audio_meta_lower, "dts hd hra"));
					const bool meta_dts_es = audio_meta_lower &&
						(strstr(audio_meta_lower, "dts-es") || strstr(audio_meta_lower, "dts es"));
					const bool meta_dts_96_24 = audio_meta_lower &&
						(strstr(audio_meta_lower, "dts 96/24") || strstr(audio_meta_lower, "dts 96-24") || strstr(audio_meta_lower, "dts 96 24"));
					const bool meta_mlp = audio_meta_lower &&
						(strstr(audio_meta_lower, "meridian lossless") || strstr(audio_meta_lower, "mlp"));
					const bool meta_realaudio = audio_meta_lower &&
						(strstr(audio_meta_lower, "realaudio") || strstr(audio_meta_lower, "real audio"));
					const bool meta_real_144 = audio_meta_lower &&
						(strstr(audio_meta_lower, "real_144") || strstr(audio_meta_lower, "real 144") ||
						 (meta_realaudio && strstr(audio_meta_lower, "14.4")));
					const bool meta_real_288 = audio_meta_lower &&
						(strstr(audio_meta_lower, "real_288") || strstr(audio_meta_lower, "real 288") ||
						 (meta_realaudio && strstr(audio_meta_lower, "28.8")));

					if (!strcmp(g_type, "audio/x-true-hd") || !strcmp(g_type, "audio/xTrueHD") || meta_truehd)
						audio.codec = has_atmos ? "Dolby Atmos (TrueHD)" : "Dolby TrueHD";
					else if (!strcmp(g_type, "audio/x-mlp") || meta_mlp)
						audio.codec = "MLP";
					else if (!strcmp(g_type, "audio/x-eac3") || !strcmp(g_type, "audio/eac3"))
						audio.codec = has_atmos ? "Dolby Atmos" : "Dolby Digital +";
					else if (!strcmp(g_type, "audio/x-ac3") || !strcmp(g_type, "audio/ac3"))
						audio.codec = "Dolby Digital";
					else if (!strcmp(g_type, "audio/x-ac4") || !strcmp(g_type, "audio/ac4") ||
						(audio_meta_lower && (strstr(audio_meta_lower, "dolby ac-4") || strstr(audio_meta_lower, "ac-4"))))
						audio.codec = "Dolby AC-4";
					else if (meta_dtsx_pro)
						audio.codec = "DTS:X Pro";
					else if (meta_dtsx)
						audio.codec = "DTS:X";
					else if (meta_dts_ma)
						audio.codec = "DTS-HD MA";
					else if (meta_dts_hra)
						audio.codec = "DTS-HD HRA";
					else if (meta_dts_es)
						audio.codec = "DTS-ES";
					else if (meta_dts_96_24)
						audio.codec = "DTS 96/24";
					else if (!strcmp(g_type, "audio/x-dtshd") || !strcmp(g_type, "audio/dtshd") || meta_dtshd)
						audio.codec = "DTS-HD";
					else if (!strcmp(g_type, "audio/x-dts") || !strcmp(g_type, "audio/dts") ||
						(audio_meta_lower && strstr(audio_meta_lower, "dts")))
						audio.codec = "DTS";
					else if (audio.type == atAAC || audio.type == atAACHE)
					{
						if (audio_meta_lower && (strstr(audio_meta_lower, "xhe-aac") || strstr(audio_meta_lower, "xhe aac") || strstr(audio_meta_lower, "usac")))
							audio.codec = "xHE-AAC";
						else if (audio_meta_lower && (strstr(audio_meta_lower, "he-aac-v2") || strstr(audio_meta_lower, "he-aac v2") || strstr(audio_meta_lower, "heaacv2")))
							audio.codec = "HE-AAC v2";
						else if (audio_meta_lower && (strstr(audio_meta_lower, "he-aac-v1") || strstr(audio_meta_lower, "he-aac") || strstr(audio_meta_lower, "he aac") || strstr(audio_meta_lower, "heaac") || strstr(audio_meta_lower, "sbr")))
							audio.codec = "HE-AAC";
						else if (audio_meta_lower && (strstr(audio_meta_lower, "profile=(string)eld") || strstr(audio_meta_lower, "profile=eld") || strstr(audio_meta_lower, "aac-eld") || strstr(audio_meta_lower, "aac eld")))
							audio.codec = "AAC-ELD";
						else if (audio_meta_lower && (strstr(audio_meta_lower, "profile=(string)ld") || strstr(audio_meta_lower, "profile=ld") || strstr(audio_meta_lower, "aac-ld") || strstr(audio_meta_lower, "aac ld")))
							audio.codec = "AAC-LD";
						else if (audio_meta_lower && (strstr(audio_meta_lower, "profile=(string)lc") || strstr(audio_meta_lower, "profile=lc") || strstr(audio_meta_lower, "base-profile=(string)lc") || strstr(audio_meta_lower, "aac-lc") || strstr(audio_meta_lower, "aac lc")))
							audio.codec = "AAC-LC";
						else
							audio.codec = "AAC";
					}
					else if (!strcmp(g_type, "audio/x-flac") || !strcmp(g_type, "audio/flac") ||
						(audio_meta_lower && (strstr(audio_meta_lower, "flac") || strstr(audio_meta_lower, "free lossless audio codec"))))
						audio.codec = "FLAC";
					else if (!strcmp(g_type, "audio/x-alac") ||
						(audio_meta_lower && (strstr(audio_meta_lower, "alac") || strstr(audio_meta_lower, "apple lossless"))))
						audio.codec = "ALAC";
					else if (!strcmp(g_type, "audio/x-opus") || (audio_meta_lower && strstr(audio_meta_lower, "opus")))
						audio.codec = "Opus";
					else if (!strcmp(g_type, "audio/x-vorbis") || (audio_meta_lower && strstr(audio_meta_lower, "vorbis")))
						audio.codec = "Vorbis";
					else if (!strcmp(g_type, "audio/x-wavpack") || (audio_meta_lower && strstr(audio_meta_lower, "wavpack")))
						audio.codec = "WavPack";
					else if (!strcmp(g_type, "audio/x-ape") ||
						(audio_meta_lower && (strstr(audio_meta_lower, "monkey's audio") || strstr(audio_meta_lower, "monkeys audio"))))
						audio.codec = "APE";
					else if (!strcmp(g_type, "audio/x-tta") ||
						(audio_meta_lower && (strstr(audio_meta_lower, "true audio") || strstr(audio_meta_lower, "tta"))))
						audio.codec = "TTA";
					else if (!strcmp(g_type, "audio/x-wma"))
					{
						if (audio_meta_lower && (strstr(audio_meta_lower, "wma lossless") || strstr(audio_meta_lower, "wmalossless")))
							audio.codec = "WMA Lossless";
						else if (audio_meta_lower && (strstr(audio_meta_lower, "wma pro") || strstr(audio_meta_lower, "wmapro") || strstr(audio_meta_lower, "wma/pro")))
							audio.codec = "WMA Pro";
						else
							audio.codec = "WMA";
					}
					else if (!strcmp(g_type, "audio/x-pn-realaudio"))
					{
						gint raversion = 0;
						if (gst_structure_get_int(str, "raversion", &raversion) && raversion == 1)
							audio.codec = "RealAudio 14.4";
						else if (raversion == 2)
							audio.codec = "RealAudio 28.8";
						else
							audio.codec = "RealAudio";
					}
					else if (meta_real_144)
						audio.codec = "RealAudio 14.4";
					else if (meta_real_288)
						audio.codec = "RealAudio 28.8";
					else if (!strcmp(g_type, "audio/AMR-WB") || (audio_meta_lower && strstr(audio_meta_lower, "amr-wb")))
						audio.codec = "AMR-WB";
					else if (!strcmp(g_type, "audio/AMR") || (audio_meta_lower && strstr(audio_meta_lower, "amr")))
						audio.codec = "AMR";
					else if (!strcmp(g_type, "audio/x-speex") || (audio_meta_lower && strstr(audio_meta_lower, "speex")))
						audio.codec = "Speex";
					else if (!strcmp(g_type, "audio/x-dsd") || (audio_meta_lower && strstr(audio_meta_lower, "dsd")))
						audio.codec = "DSD";
					else if (!strcmp(g_type, "audio/mpeg"))
					{
						gint mpegversion = 0, layer = 0;
						if (gst_structure_get_int(str, "mpegversion", &mpegversion) && mpegversion == 1 &&
							gst_structure_get_int(str, "layer", &layer))
						{
							if (layer == 3)
								audio.codec = "MP3";
							else if (layer == 2)
								audio.codec = "MP2";
							else if (layer == 1)
								audio.codec = "MPEG Layer I";
						}
					}
					else if (!strcmp(g_type, "audio/x-alaw"))
						audio.codec = "A-law";
					else if (!strcmp(g_type, "audio/x-mulaw"))
						audio.codec = "mu-law";
					else if (!strcmp(g_type, "audio/x-raw"))
					{
						/*
						 * Keep encoded source identity when playbin has already decoded
						 * the pad (TrueHD/FLAC/etc. are handled from codec metadata above).
						 */
						if (audio_meta_lower && strstr(audio_meta_lower, "lpcm"))
							audio.codec = "LPCM";
						else if (audio.codec == g_type || (audio_meta_lower &&
							(strstr(audio_meta_lower, "raw") || strstr(audio_meta_lower, "pcm"))))
							audio.codec = "PCM";
					}

					eDebug("[eServiceMP3] audio stream=%i codec=%s language=%s channels=%d",
						i, audio.codec.c_str(), audio.language_code.c_str(), audio.channels);
					if (audio_meta_lower) g_free(audio_meta_lower);
					if (caps_desc) g_free(caps_desc);
					if (tags && GST_IS_TAG_LIST(tags)) gst_tag_list_free(tags);
					audioStreams_temp.push_back(audio);
					gst_caps_unref(caps);
				}

				for (i = 0; i < n_text; i++)
				{
					gchar *g_codec = NULL, *g_lang = NULL;
					GstTagList *tags = NULL;
					g_signal_emit_by_name (m_gst_playbin, "get-text-tags", i, &tags);
					subtitleStream subs;
					subs.language_code = "und";
					if (tags && GST_IS_TAG_LIST(tags))
					{
						if (gst_tag_list_get_string(tags, GST_TAG_LANGUAGE_CODE, &g_lang))
						{
							subs.language_code = g_lang;
							g_free(g_lang);
						}
						gst_tag_list_get_string(tags, GST_TAG_SUBTITLE_CODEC, &g_codec);
						gst_tag_list_free(tags);
					}

					eDebug("[eServiceMP3] subtitle stream=%i language=%s codec=%s", i, subs.language_code.c_str(), g_codec ? g_codec : "(null)");

					GstPad* pad = 0;
					g_signal_emit_by_name (m_gst_playbin, "get-text-pad", i, &pad);
					if ( pad )
						g_signal_connect (G_OBJECT (pad), "notify::caps", G_CALLBACK (gstTextpadHasCAPS), this);

					subs.type = getSubtitleType(pad, g_codec);
					gst_object_unref(pad);
					g_free(g_codec);
					subtitleStreams_temp.push_back(subs);
				}

				for (unsigned int ai = 0; ai < audioStreams_temp.size() && ai < m_audioStreams.size(); ++ai)
				{
					const std::string &old_codec = m_audioStreams[ai].codec;
					std::string &new_codec = audioStreams_temp[ai].codec;
					if (old_codec == "Dolby Atmos" && new_codec == "Dolby Digital +")
						new_codec = old_codec;
					else if ((old_codec.find("DTS-HD") == 0 || old_codec.find("DTS:X") == 0) &&
						(new_codec == "DTS" || new_codec == "DTS-HD"))
					{
						new_codec = old_codec;
						if (m_audioStreams[ai].channels > audioStreams_temp[ai].channels)
							audioStreams_temp[ai].channels = m_audioStreams[ai].channels;
					}
				}

				bool hasChanges = m_audioStreams != audioStreams_temp;
				if (!hasChanges)
					hasChanges = m_subtitleStreams != subtitleStreams_temp;

				if (hasChanges)
				{
					eTrace("[eServiceMP3] audio or subtitle stream difference -- re enumerating");
					m_audioStreams.assign(audioStreams_temp.begin(), audioStreams_temp.end());
					m_subtitleStreams.assign(subtitleStreams_temp.begin(), subtitleStreams_temp.end());
					eTrace("[eServiceMP3] evUpdatedInfo called for audiosubs");
					m_event((iPlayableService*)this, evUpdatedInfo);
				}
			}
			else
			{
				m_send_ev_start = true;
			}

#ifdef HAS_SOFTWARE_HDR_DETECTION
			updateHDRFromVideoPad();

			/* Start HEVC bitstream probe early so we capture the very first
			 * I-frame of the stream.  For byte-stream HLG content the SPS
			 * (carrying transfer_characteristics=18) is in those first packets;
			 * if we wait until eventSizeChanged the decoder has already consumed
			 * the SPS and the next one may be many seconds away (next IDR).
			 * For hvc1/hev1 files the SPS is in codec_data and is pre-ingested
			 * by startHDRProbe regardless of timing. */
			if (!m_hdr_probe_active)
				startHDRProbe();
#endif

			if (m_seek_paused)
			{
				m_seek_paused = false;
				gst_element_set_state(m_gst_playbin, GST_STATE_PAUSED);
			}

			if ( m_errorInfo.missing_codec != "" )
			{
				if (m_errorInfo.missing_codec.find("video/") == 0 || (m_errorInfo.missing_codec.find("audio/") == 0 && m_audioStreams.empty()))
					m_event((iPlayableService*)this, evUser+12);
			}
			break;
		}
		case GST_MESSAGE_ELEMENT:
		{
			const GstStructure *msgstruct = gst_message_get_structure(msg);
			if (msgstruct)
			{
				if ( gst_is_missing_plugin_message(msg) )
				{
					GstCaps *caps = NULL;
					gst_structure_get (msgstruct, "detail", GST_TYPE_CAPS, &caps, NULL);
					if (caps)
					{
						std::string codec = (const char*) gst_caps_to_string(caps);
						gchar *description = gst_missing_plugin_message_get_description(msg);
						if ( description )
						{
							eDebug("[eServiceMP3] m_errorInfo.missing_codec = %s", codec.c_str());
							m_errorInfo.error_message = "GStreamer plugin " + (std::string)description + " not available!\n";
							m_errorInfo.missing_codec = codec.substr(0,(codec.find_first_of(',')));
							g_free(description);
						}
						gst_caps_unref(caps);
					}
				}
				else
				{
					const gchar *eventname = gst_structure_get_name(msgstruct);
					if ( eventname )
					{
						if (!strcmp(eventname, "eventSizeChanged") || !strcmp(eventname, "eventSizeAvail"))
						{
							gst_structure_get_int (msgstruct, "aspect_ratio", &m_aspect);
							gst_structure_get_int (msgstruct, "width", &m_width);
							gst_structure_get_int (msgstruct, "height", &m_height);
							if (strstr(eventname, "Changed"))
								m_event((iPlayableService*)this, evVideoSizeChanged);
#ifdef HAS_SOFTWARE_HDR_DETECTION
						updateHDRFromVideoPad();
							/* If the early probe (ASYNC_DONE) already found an SPS,
							 * leave it running — it has good data in flight.
							 * If no SPS yet (HEVC pad wasn't ready at ASYNC_DONE,
							 * or probe not started), restart now that caps are settled. */
							if (!m_hdr_probe_active || m_hdr_probe_first_sps_at == 0)
								startHDRProbe();
#endif
						}
						else if (!strcmp(eventname, "eventFrameRateChanged") || !strcmp(eventname, "eventFrameRateAvail"))
						{
							gst_structure_get_int (msgstruct, "frame_rate", &m_framerate);
							if (strstr(eventname, "Changed"))
								m_event((iPlayableService*)this, evVideoFramerateChanged);
						}
						else if (!strcmp(eventname, "eventProgressiveChanged") || !strcmp(eventname, "eventProgressiveAvail"))
						{
							gst_structure_get_int (msgstruct, "progressive", &m_progressive);
							if (strstr(eventname, "Changed"))
								m_event((iPlayableService*)this, evVideoProgressiveChanged);
						}
						else if (!strcmp(eventname, "eventGammaChanged"))
						{
							gst_structure_get_int (msgstruct, "gamma", &m_gamma);
							m_event((iPlayableService*)this, evVideoGammaChanged);
							/* Derive m_hdr_type from the hardware decoder gamma.
							 * gamma: 0=SDR 1=HDR(generic) 2=SMPTE ST2084/HDR10 3=HLG
							 * This is more reliable than GStreamer caps colorimetry,
							 * which many STB h265parse builds do not populate. */
							int newHdrType = 0;
							if (m_gamma == 2) newHdrType = 1;       /* HDR10 */
							else if (m_gamma == 3) newHdrType = 2;  /* HLG */
							else if (m_gamma == 1) newHdrType = 3;  /* plain HDR */
							if (newHdrType != m_hdr_type)
							{
								m_hdr_type = newHdrType;
								m_event((iPlayableService*)this, evUpdatedInfo);
							}
						}
						else if (!strcmp(eventname, "eventAtmosDetected"))
						{
							int stream = -1;
							if (gst_structure_get_int(msgstruct, "stream", &stream) &&
								stream >= 0 && stream < (int)m_audioStreams.size() &&
								m_audioStreams[stream].codec != "Dolby Atmos")
							{
								m_audioStreams[stream].codec = "Dolby Atmos";
								eDebug("[eServiceMP3] audio stream=%d updated codec=Dolby Atmos", stream);
								m_event((iPlayableService*)this, evUpdatedInfo);
							}
						}
						else if (!strcmp(eventname, "eventDTSProfileDetected"))
						{
							int stream = -1;
							int channels = 0;
							const char *codec = gst_structure_get_string(msgstruct, "codec");
							if (codec && gst_structure_get_int(msgstruct, "stream", &stream) &&
								stream >= 0 && stream < (int)m_audioStreams.size())
							{
								bool changed = false;
								if (m_audioStreams[stream].codec != codec)
								{
									m_audioStreams[stream].codec = codec;
									changed = true;
								}
								if (gst_structure_get_int(msgstruct, "channels", &channels) && channels > 0 &&
									m_audioStreams[stream].channels != channels)
								{
									m_audioStreams[stream].channels = channels;
									changed = true;
								}
								if (changed)
								{
									eDebug("[eServiceMP3] audio stream=%d updated codec=%s channels=%d",
										stream, codec, m_audioStreams[stream].channels);
									m_event((iPlayableService*)this, evUpdatedInfo);
								}
							}
						}
						else if (!strcmp(eventname, "redirect"))
						{
							const char *uri = gst_structure_get_string(msgstruct, "new-location");
							eDebug("[eServiceMP3] redirect to %s", uri);
							gst_element_set_state (m_gst_playbin, GST_STATE_NULL);
							g_object_set(G_OBJECT (m_gst_playbin), "uri", uri, NULL);
							gst_element_set_state (m_gst_playbin, GST_STATE_PLAYING);
						}
					}
				}
			}
			break;
		}
		case GST_MESSAGE_BUFFERING:
			if (m_sourceinfo.is_streaming)
			{
				GstBufferingMode mode;
				gst_message_parse_buffering(msg, &(m_bufferInfo.bufferPercent));
				eTrace("[eServiceMP3] Buffering %u percent done", m_bufferInfo.bufferPercent);
				gst_message_parse_buffering_stats(msg, &mode, &(m_bufferInfo.avgInRate), &(m_bufferInfo.avgOutRate), &(m_bufferInfo.bufferingLeft));
				m_event((iPlayableService*)this, evBuffering);
				/*
				 * we don't react to buffer level messages, unless we are configured to use a prefill buffer
				 * (even if we are not configured to, we still use the buffer, but we rely on it to remain at the
				 * healthy level at all times, without ever having to pause the stream)
				 *
				 * Also, it does not make sense to pause the stream if it is a live stream
				 * (in which case the sink will not produce data while paused, so we won't
				 * recover from an empty buffer)
				 */
				if (m_use_prefillbuffer && !m_is_live && !m_sourceinfo.is_hls && --m_ignore_buffering_messages <= 0)
				{
					if (m_bufferInfo.bufferPercent == 100)
					{
						GstState state;
						gst_element_get_state(m_gst_playbin, &state, NULL, 0LL);
						if (state != GST_STATE_PLAYING)
						{
							eDebug("[eServiceMP3] start playing");
							gst_element_set_state (m_gst_playbin, GST_STATE_PLAYING);
						}
						/*
						 * when we start the pipeline, the contents of the buffer will immediately drain
						 * into the (hardware buffers of the) sinks, so we will receive low buffer level
						 * messages right away.
						 * Ignore the first few buffering messages, giving the buffer the chance to recover
						 * a bit, before we start handling empty buffer states again.
						 */
						m_ignore_buffering_messages = 5;
					}
					else if (m_bufferInfo.bufferPercent == 0)
					{
						eDebug("[eServiceMP3] start pause");
						gst_element_set_state (m_gst_playbin, GST_STATE_PAUSED);
						m_ignore_buffering_messages = 0;
					}
					else
					{
						m_ignore_buffering_messages = 0;
					}
				}
			}
			break;
		default:
			break;
	}
	g_free (sourceName);
}

void eServiceMP3::handleMessage(GstMessage *msg)
{
	if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_STATE_CHANGED && GST_MESSAGE_SRC(msg) != GST_OBJECT(m_gst_playbin))
	{
		/*
		 * ignore verbose state change messages for all active elements;
		 * we only need to handle state-change events for the playbin
		 */
		gst_message_unref(msg);
		return;
	}
	m_pump.send(new GstMessageContainer(1, msg, NULL, NULL));
}

GstBusSyncReply eServiceMP3::gstBusSyncHandler(GstBus *bus, GstMessage *message, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	if (_this) _this->handleMessage(message);
	return GST_BUS_DROP;
}
/*Processing TOC CVR */
void eServiceMP3::HandleTocEntry(GstMessage *msg)
{
	/* limit TOC to dvbvideosink cue sheet only works for video media */
	if (!strncmp(GST_MESSAGE_SRC_NAME(msg), "dvbvideosink", 12))
	{
		GstToc *toc;
		gboolean updated;
		gst_message_parse_toc(msg, &toc, &updated);
		for (GList* i = gst_toc_get_entries(toc); i; i = i->next)
		{
			GstTocEntry *entry = static_cast<GstTocEntry*>(i->data);
			if (gst_toc_entry_get_entry_type (entry) == GST_TOC_ENTRY_TYPE_EDITION)
			{
				/* extra debug info for testing purposes CVR should_be_removed later on */
				eTrace("[eServiceMP3] toc_type %s", gst_toc_entry_type_get_nick(gst_toc_entry_get_entry_type (entry)));
				gint y = 0;
				for (GList* x = gst_toc_entry_get_sub_entries (entry); x; x = x->next)
				{
					GstTocEntry *sub_entry = static_cast<GstTocEntry*>(x->data);
					if (gst_toc_entry_get_entry_type (sub_entry) == GST_TOC_ENTRY_TYPE_CHAPTER)
					{
						if (y == 0)
						{
							m_use_chapter_entries = true;
							if (m_cuesheet_loaded)
								m_cue_entries.clear();
							else
								loadCuesheet();
						}
						/* first chapter is movie start no cut needed */
						else if (y >= 1)
						{
							gint64 start = 0;
							gint64 pts = 0;
							gint type = 0;
							gst_toc_entry_get_start_stop_times(sub_entry, &start, NULL);
							type = 2;
							if(start > 0)
								pts = start / 11111;
							if (pts > 0)
							{
								m_cue_entries.insert(cueEntry(pts, type));
								/* extra debug info for testing purposes CVR should_be_removed later on */
								eTrace("[eServiceMP3] toc_subtype %s,Nr = %d, start= %#" G_GINT64_MODIFIER "x",
										gst_toc_entry_type_get_nick(gst_toc_entry_get_entry_type (sub_entry)), y + 1, pts);
							}
						}
						y++;
					}
				}
				if (y > 0)
				{
					m_cuesheet_changed = 1;
					m_event((iPlayableService*)this, evCuesheetChanged);
				}
			}
		}
		eDebug("[eServiceMP3] TOC entry from source %s processed", GST_MESSAGE_SRC_NAME(msg));
	}
	else
	{
		eDebug("[eServiceMP3] TOC entry from source %s not used", GST_MESSAGE_SRC_NAME(msg));
	}
}
void eServiceMP3::playbinNotifySource(GObject *object, GParamSpec *unused, gpointer user_data)
{
	GstElement *source = NULL;
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	g_object_get(object, "source", &source, NULL);
	if (source)
	{
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "timeout") != 0)
		{
			GstElementFactory *factory = gst_element_get_factory(source);
			if (factory)
			{
				const gchar *sourcename = gst_plugin_feature_get_name(GST_PLUGIN_FEATURE(factory));
				if (!strcmp(sourcename, "souphttpsrc"))
				{
					g_object_set(G_OBJECT(source), "timeout", HTTP_TIMEOUT, NULL);
					g_object_set(G_OBJECT(source), "retries", 20, NULL);
				}
			}
		}
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "ssl-strict") != 0)
		{
			g_object_set(G_OBJECT(source), "ssl-strict", FALSE, NULL);
		}
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "user-agent") != 0 && !_this->m_useragent.empty())
		{
			g_object_set(G_OBJECT(source), "user-agent", _this->m_useragent.c_str(), NULL);
		}
		if (g_object_class_find_property(G_OBJECT_GET_CLASS(source), "extra-headers") != 0 && !_this->m_extra_headers.empty())
		{
			GstStructure *extras = gst_structure_new_empty("extras");
			size_t pos = 0;
			while (pos != std::string::npos)
			{
				std::string name, value;
				size_t start = pos;
				size_t len = std::string::npos;
				pos = _this->m_extra_headers.find('=', pos);
				if (pos != std::string::npos)
				{
					len = pos - start;
					pos++;
					name = _this->m_extra_headers.substr(start, len);
					start = pos;
					len = std::string::npos;
					pos = _this->m_extra_headers.find('&', pos);
					if (pos != std::string::npos)
					{
						len = pos - start;
						pos++;
					}
					value = _this->m_extra_headers.substr(start, len);
				}
				if (!name.empty() && !value.empty())
				{
					GValue header;
					eDebug("[eServiceMP3] setting extra-header '%s:%s'", name.c_str(), value.c_str());
					memset(&header, 0, sizeof(GValue));
					g_value_init(&header, G_TYPE_STRING);
					g_value_set_string(&header, value.c_str());
					gst_structure_set_value(extras, name.c_str(), &header);
				}
				else
				{
					eDebug("[eServiceMP3] Invalid header format %s", _this->m_extra_headers.c_str());
					break;
				}
			}
			if (gst_structure_n_fields(extras) > 0)
			{
				g_object_set(G_OBJECT(source), "extra-headers", extras, NULL);
			}
			gst_structure_free(extras);
		}
		gst_object_unref(source);
	}
}

void eServiceMP3::handleElementAdded(GstBin *bin, GstElement *element, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	if (_this)
	{
		gchar *elementname = gst_element_get_name(element);

		if (g_str_has_prefix(elementname, "queue2"))
		{
			if (_this->m_download_buffer_path != "")
			{
				g_object_set(G_OBJECT(element), "temp-template", _this->m_download_buffer_path.c_str(), NULL);
			}
			else
			{
				g_object_set(G_OBJECT(element), "temp-template", NULL, NULL);
			}
		}
		else if (g_str_has_prefix(elementname, "uridecodebin")
			|| g_str_has_prefix(elementname, "decodebin"))
		{
			/*
			 * Listen for queue2 element added to uridecodebin/decodebin2 as well.
			 * Ignore other bins since they may have unrelated queues
			 */
				g_signal_connect(element, "element-added", G_CALLBACK(handleElementAdded), user_data);
		}
		g_free(elementname);
	}
}

audiotype_t eServiceMP3::gstCheckAudioPad(GstStructure* structure)
{
	if (!structure)
		return atUnknown;

	if ( gst_structure_has_name (structure, "audio/mpeg"))
	{
		gint mpegversion, layer = -1;
		if (!gst_structure_get_int (structure, "mpegversion", &mpegversion))
			return atUnknown;

		switch (mpegversion) {
			case 1:
				{
					gst_structure_get_int (structure, "layer", &layer);
					if ( layer == 3 )
						return atMP3;
					else
						return atMPEG;
					break;
				}
			case 2:
				return atAAC;
			case 4:
				return atAACHE;
			default:
				return atUnknown;
		}
	}

	else if ( gst_structure_has_name (structure, "audio/x-ac3") || gst_structure_has_name (structure, "audio/ac3") )
		return atAC3;
	else if (gst_structure_has_name (structure, "audio/x-eac3") || gst_structure_has_name (structure, "audio/eac3") || gst_structure_has_name (structure, "audio/x-true-hd") || gst_structure_has_name (structure, "audio/xTrueHD"))
		return atEAC3;
	else if ( gst_structure_has_name (structure, "audio/x-dts") || gst_structure_has_name (structure, "audio/dts") )
		return atDTS;
	else if ( gst_structure_has_name (structure, "audio/x-dtshd") || gst_structure_has_name (structure, "audio/dtshd") )
		return atDTSHD;
	else if ( gst_structure_has_name (structure, "audio/x-aache") || gst_structure_has_name (structure, "audio/aache") || gst_structure_has_name (structure, "audio/x-heaac") || gst_structure_has_name (structure, "audio/heaac") )
		return atAACHE;
	else if ( gst_structure_has_name (structure, "audio/x-aac") || gst_structure_has_name (structure, "audio/aac") )
		return atAAC;

	return atPCM;
}

void eServiceMP3::gstPoll(ePtr<GstMessageContainer> const &msg)
{
	switch (msg->getType())
	{
		case 1:
		{
			GstMessage *gstmessage = *((GstMessageContainer*)msg);
			if (gstmessage)
			{
				gstBusCall(gstmessage);
			}
			break;
		}
		case 2:
		{
			GstBuffer *buffer = *((GstMessageContainer*)msg);
			if (buffer)
			{
				pullSubtitle(buffer);
			}
			break;
		}
		case 3:
		{
			GstPad *pad = *((GstMessageContainer*)msg);
			gstTextpadHasCAPS_synced(pad);
			break;
		}
	}
}

eAutoInitPtr<eServiceFactoryMP3> init_eServiceFactoryMP3(eAutoInitNumbers::service+1, "eServiceFactoryMP3");

void eServiceMP3::gstCBsubtitleAvail(GstElement *subsink, GstBuffer *buffer, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;
	if (_this->m_currentSubtitleStream < 0)
	{
		if (buffer) gst_buffer_unref(buffer);
		return;
	}
	_this->m_pump.send(new GstMessageContainer(2, NULL, NULL, buffer));
}

void eServiceMP3::gstTextpadHasCAPS(GstPad *pad, GParamSpec * unused, gpointer user_data)
{
	eServiceMP3 *_this = (eServiceMP3*)user_data;

	gst_object_ref (pad);

	_this->m_pump.send(new GstMessageContainer(3, NULL, pad, NULL));
}

void eServiceMP3::gstTextpadHasCAPS_synced(GstPad *pad)
{
	GstCaps *caps = NULL;

	g_object_get (G_OBJECT (pad), "caps", &caps, NULL);

	if (caps)
	{
		subtitleStream subs;

		eDebug("[eServiceMP3] gstTextpadHasCAPS:: signal::caps = %s", gst_caps_to_string(caps));
//		eDebug("[eServiceMP3] gstGhostpadHasCAPS_synced %p %d", pad, m_subtitleStreams.size());

		if (m_currentSubtitleStream >= 0 && m_currentSubtitleStream < (int)m_subtitleStreams.size())
			subs = m_subtitleStreams[m_currentSubtitleStream];
		else {
			subs.type = stUnknown;
			subs.pad = pad;
		}

		if ( subs.type == stUnknown )
		{
			GstTagList *tags = NULL;
			gchar *g_lang = NULL;
			g_signal_emit_by_name (m_gst_playbin, "get-text-tags", m_currentSubtitleStream, &tags);

			subs.language_code = "und";
			subs.type = getSubtitleType(pad);
			if (tags && GST_IS_TAG_LIST(tags))
			{
				if (gst_tag_list_get_string(tags, GST_TAG_LANGUAGE_CODE, &g_lang))
				{
					subs.language_code = std::string(g_lang);
					g_free(g_lang);
				}
				gst_tag_list_free(tags);
			}

			if (m_currentSubtitleStream >= 0 && m_currentSubtitleStream < (int)m_subtitleStreams.size())
				m_subtitleStreams[m_currentSubtitleStream] = subs;
			else
				m_subtitleStreams.push_back(subs);
		}

//		eDebug("[eServiceMP3] gstGhostpadHasCAPS:: m_gst_prev_subtitle_caps=%s equal=%i",gst_caps_to_string(m_gst_prev_subtitle_caps),gst_caps_is_equal(m_gst_prev_subtitle_caps, caps));

		gst_caps_unref (caps);
	}
}

void eServiceMP3::pullSubtitle(GstBuffer *buffer)
{
	if (buffer && m_currentSubtitleStream >= 0 && m_currentSubtitleStream < (int)m_subtitleStreams.size())
	{
		GstMapInfo map;
		if(!gst_buffer_map(buffer, &map, GST_MAP_READ))
		{
			eLog(3, "[eServiceMP3] pullSubtitle gst_buffer_map failed");
			return;
		}
		int64_t buf_pos = GST_BUFFER_PTS(buffer);
		size_t len = map.size;
		eTrace("[eServiceMP3] gst_buffer_get_size %zu map.size %zu", gst_buffer_get_size(buffer), len);
		int64_t duration_ns = GST_BUFFER_DURATION(buffer);
		int subType = m_subtitleStreams[m_currentSubtitleStream].type;
		eTrace("[eServiceMP3] pullSubtitle type=%d size=%zu", subType, len);
		if ( subType )
		{
			if (subType == stDVB)
			{
				uint8_t * data = map.data;
				m_dvb_subtitle_parser->processBuffer(data, len, buf_pos / 1000000ULL);
			}
			else if ( subType < stVOB )
			{
				int delay = eConfigManager::getConfigIntValue("config.subtitles.pango_subtitles_delay");
				int subtitle_fps = eConfigManager::getConfigIntValue("config.subtitles.pango_subtitles_fps");

				double convert_fps = 1.0;
				if (subtitle_fps > 1 && m_framerate > 0)
					convert_fps = subtitle_fps / (double)m_framerate;

				std::string line((const char*)map.data, len);
				// some media muxers do add an extra new line at the end off a muxed/reencoded srt to ssa codec
				if (!line.empty() && line[line.length()-1] == '\n')
					line.erase(line.length()-1);

				eTrace("[eServiceMP3] got new text subtitle @ buf_pos = %lld ns (in pts=%lld), dur=%lld: '%s' ", buf_pos, buf_pos/11111, duration_ns, line.c_str());

				uint32_t start_ms = ((buf_pos / 1000000ULL) * convert_fps) + (delay / 90);
				uint32_t end_ms = start_ms + (duration_ns / 1000000ULL);
				m_subtitle_pages.insert(subtitle_pages_map_pair_t(end_ms, subtitle_page_t(start_ms, end_ms, line)));
				m_subtitle_sync_timer->start(1, true);
			}
			else
			{
				eLog(3, "[eServiceMP3] unsupported subpicture... ignoring");
			}
		}
		gst_buffer_unmap(buffer, &map);
	}
}

void eServiceMP3::newDVBSubtitlePage(const eDVBSubtitlePage &p)
{
	m_dvb_subtitle_pages.push_back(p);
	pushDVBSubtitles();
}

void eServiceMP3::pushDVBSubtitles()
{
	pts_t running_pts = 0, decoder_ms;

	if (getPlayPosition(running_pts) < 0)
		eTrace("[eServiceMP3] Cant get current decoder time.");

	while (1)
	{
		eDVBSubtitlePage dvb_page;
		pts_t show_time;
		if (!m_dvb_subtitle_pages.empty())
		{
			dvb_page = m_dvb_subtitle_pages.front();
			show_time = dvb_page.m_show_time;
		}
		else
			return;

		decoder_ms = running_pts / 90;

		// If subtitle is overdue or within 20ms the video timing then display it.
		// If cant get decoder PTS then display the subtitles.
		// If not, pause subtitle processing until the subtitle should be shown
		pts_t diff = show_time - decoder_ms;
		if (diff < 20 || decoder_ms == 0)
		{
			eTrace("[eServiceMP3] Showing subtitles at %lld. Current decoder time: %lld. Difference: %lld", show_time, decoder_ms, diff);
			m_subtitle_widget->setPage(dvb_page);
			m_dvb_subtitle_pages.pop_front();
		}
		else
		{
			eDebug("[eServiceMP3] Delay early subtitle by %.03fs. Page stack size %d", diff / 1000.0f, m_dvb_subtitle_pages.size());
			m_dvb_subtitle_sync_timer->start(diff, 1);
			break;
		}
	}
}

void eServiceMP3::pushSubtitles()
{
	pts_t running_pts = 0;
	int32_t next_timer = 0, decoder_ms, start_ms, end_ms, diff_start_ms, diff_end_ms;
	subtitle_pages_map_t::iterator current;

	if (m_currentSubtitleStream < 0 || m_currentSubtitleStream >= (int)m_subtitleStreams.size())
		return;

	// wait until clock is stable

	if (getPlayPosition(running_pts) < 0)
		m_decoder_time_valid_state = 0;

	if (m_decoder_time_valid_state < 4)
	{
		m_decoder_time_valid_state++;

		if (m_prev_decoder_time == running_pts)
			m_decoder_time_valid_state = 0;

		if (m_decoder_time_valid_state < 4)
		{
			//eDebug("[eServiceMP3] *** push subtitles, waiting for clock to stabilise");
			m_prev_decoder_time = running_pts;
			next_timer = 50;
			goto exit;
		}

		//eDebug("[eServiceMP3] *** push subtitles, clock stable");
	}

	decoder_ms = running_pts / 90;

#if 0
		eDebug("[eServiceMP3] *** all subs: ");

		for (current = m_subtitle_pages.begin(); current != m_subtitle_pages.end(); current++)
		{
			start_ms = current->second.start_ms;
			end_ms = current->second.end_ms;
			diff_start_ms = start_ms - decoder_ms;
			diff_end_ms = end_ms - decoder_ms;

			eDebug("[eServiceMP3]    start: %d, end: %d, diff_start: %d, diff_end: %d: %s",
					start_ms, end_ms, diff_start_ms, diff_end_ms, current->second.text.c_str());
		}

#endif

	for (current = m_subtitle_pages.lower_bound(decoder_ms); current != m_subtitle_pages.end(); current++)
	{
		start_ms = current->second.start_ms;
		end_ms = current->second.end_ms;
		diff_start_ms = start_ms - decoder_ms;
		diff_end_ms = end_ms - decoder_ms;

#if 0
		eDebug("[eServiceMP3] *** next subtitle: decoder: %d, start: %d, end: %d, duration_ms: %d, diff_start: %d, diff_end: %d : %s",
			decoder_ms, start_ms, end_ms, end_ms - start_ms, diff_start_ms, diff_end_ms, current->second.text.c_str());
#endif

		if (diff_end_ms < 0)
		{
			//eDebug("[eServiceMP3] *** current sub has already ended, skip: %d", diff_end_ms);
			continue;
		}

		if (diff_start_ms > 20)
		{
			//eDebug("[eServiceMP3] *** current sub in the future, start timer, %d", diff_start_ms);
			next_timer = diff_start_ms;
			goto exit;
		}

		// showtime

		if (m_subtitle_widget && !m_paused)
		{
			//eDebug("[eServiceMP3] *** current sub actual, show!");

			ePangoSubtitlePage pango_page;
			gRGB rgbcol(0xD0,0xD0,0xD0);

			pango_page.m_elements.push_back(ePangoSubtitlePageElement(rgbcol, current->second.text.c_str()));
			pango_page.m_show_pts = start_ms * 90;			// actually completely unused by widget!
			pango_page.m_timeout = end_ms - decoder_ms;		// take late start into account

			m_subtitle_widget->setPage(pango_page);
		}

		//eDebug("[eServiceMP3] *** no next sub scheduled, check NEXT subtitle");
	}

	// no more subs in cache, fall through

exit:
	if (next_timer == 0)
	{
		//eDebug("[eServiceMP3] *** next timer = 0, set default timer!");
		next_timer = 1000;
	}

	m_subtitle_sync_timer->start(next_timer, true);

}

RESULT eServiceMP3::enableSubtitles(iSubtitleUser *user, struct SubtitleTrack &track)
{
	int m_subtitleStreams_size = int(m_subtitleStreams.size());
	if (track.pid > m_subtitleStreams_size || track.pid < 1)
	{
		return -1;
	}
	eDebug ("[eServiceMP3][enableSubtitles] entered: subtitle stream %i track.pid %i", m_currentSubtitleStream, track.pid - 1);
	g_object_set (G_OBJECT (m_gst_playbin), "current-text", -1, NULL);
	m_subtitle_sync_timer->stop();
	m_dvb_subtitle_sync_timer->stop();
	m_dvb_subtitle_pages.clear();
	m_subtitle_pages.clear();
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	m_currentSubtitleStream = track.pid - 1;
	m_cachedSubtitleStream = m_currentSubtitleStream;
	setCacheEntry(false, track.pid - 1);
	g_object_set (G_OBJECT (m_gst_playbin), "current-text", m_currentSubtitleStream, NULL);

	if (track.type != stDVB)
	{
		m_clear_buffers = true;
		clearBuffers();
	}

	m_subtitle_widget = user;

	eDebug ("[eServiceMP3] switched to subtitle stream %i", m_currentSubtitleStream);

#ifdef GSTREAMER_SUBTITLE_SYNC_MODE_BUG
		/*
		 * when we're running the subsink in sync=false mode,
		 * we have to force a seek, before the new subtitle stream will start
		 */
		seekRelative(-1, 90000);
#endif

	return 0;
}

RESULT eServiceMP3::disableSubtitles()
{
	eDebug("[eServiceMP3] disableSubtitles");
	m_currentSubtitleStream = -1;
	m_cachedSubtitleStream = m_currentSubtitleStream;
	setCacheEntry(false, -1);
	g_object_set (G_OBJECT (m_gst_playbin), "current-text", m_currentSubtitleStream, NULL);
	m_subtitle_sync_timer->stop();
	m_dvb_subtitle_sync_timer->stop();
	m_subtitle_pages.clear();
	m_dvb_subtitle_pages.clear();
	m_prev_decoder_time = -1;
	m_decoder_time_valid_state = 0;
	if (m_subtitle_widget) m_subtitle_widget->destroy();
	m_subtitle_widget = 0;
	return 0;
}

RESULT eServiceMP3::getCachedSubtitle(struct SubtitleTrack &track)
{
	int m_subtitleStreams_size = (int)m_subtitleStreams.size();
	if (m_autoturnon && m_subtitleStreams_size)
	{
		eDebug("[eServiceMP3][getCachedSubtitle] m_cachedSubtitleStream == -2 && m_subtitleStreams_size)");
		m_cachedSubtitleStream = 0;
		int autosub_level = 5;
		std::string configvalue;
		std::vector<std::string> autosub_languages;
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect1");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect2");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect3");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		configvalue = eConfigManager::getConfigValue("config.autolanguage.subtitle_autoselect4");
		if (configvalue != "" && configvalue != "None")
			autosub_languages.push_back(configvalue);
		for (int i = 0; i < m_subtitleStreams_size; i++)
		{
			if (!m_subtitleStreams[i].language_code.empty())
			{
				int x = 1;
				for (std::vector<std::string>::iterator it2 = autosub_languages.begin(); x < autosub_level && it2 != autosub_languages.end(); x++, it2++)
				{
					if ((*it2).find(m_subtitleStreams[i].language_code) != std::string::npos)
					{
						autosub_level = x;
						m_cachedSubtitleStream = i;
						break;
					}
				}
			}
		}
	}

	eDebug("[eServiceMP3][getCachedSubtitle] m_cachedSubtitleStream = %d; m_currentSubtitleStream = %d; m_subtitleStreams_size = %d ", m_cachedSubtitleStream, m_currentSubtitleStream, m_subtitleStreams_size);

	if (m_cachedSubtitleStream >= 0 && m_cachedSubtitleStream < m_subtitleStreams_size)
	{
		eDebug("[eServiceMP3][getCachedSubtitle] (m_cachedSubtitleStream >= 0 && m_cachedSubtitleStream < m_subtitleStreams_size)");
		subtype_t type = m_subtitleStreams[m_cachedSubtitleStream].type;
		track.type = type == stDVB ? 0 : 2;
		track.pid = m_cachedSubtitleStream + 1;
		track.page_number = int(type);
		track.magazine_number = 0;
		track.language_code = m_subtitleStreams[m_cachedSubtitleStream].language_code;
		return 0;
	}
	return -1;
}

RESULT eServiceMP3::getSubtitleList(std::vector<struct SubtitleTrack> &subtitlelist)
{
// 	eDebug("[eServiceMP3] getSubtitleList");
	int stream_idx = 1;

	for (std::vector<subtitleStream>::iterator IterSubtitleStream(m_subtitleStreams.begin()); IterSubtitleStream != m_subtitleStreams.end(); ++IterSubtitleStream)
	{
		subtype_t type = IterSubtitleStream->type;
		switch(type)
		{
		case stUnknown:
		case stVOB:
		case stPGS:
			break;
		case stDVB:
		{
			struct SubtitleTrack track = {};
			track.type = 0;
			track.pid = stream_idx;
			track.page_number = int(type);
			track.magazine_number = 0;
			track.language_code = IterSubtitleStream->language_code;
			subtitlelist.push_back(track);
			break;
		}
		default:
		{
			struct SubtitleTrack track = {};
			track.type = 2;
			track.pid = stream_idx;
			track.page_number = int(type);
			track.magazine_number = 0;
			track.language_code = IterSubtitleStream->language_code;
			subtitlelist.push_back(track);
		}
		}
		stream_idx++;
	}
	eDebug("[eServiceMP3] getSubtitleList finished");
	return 0;
}

RESULT eServiceMP3::streamed(ePtr<iStreamedService> &ptr)
{
	ptr = this;
	return 0;
}

ePtr<iStreamBufferInfo> eServiceMP3::getBufferCharge()
{
	return new eStreamBufferInfo(m_bufferInfo.bufferPercent, m_bufferInfo.avgInRate, m_bufferInfo.avgOutRate, m_bufferInfo.bufferingLeft, m_buffer_size);
}
/* cuesheet CVR */
PyObject *eServiceMP3::getCutList()
{
	ePyObject list = PyList_New(0);

	for (std::multiset<struct cueEntry>::iterator i(m_cue_entries.begin()); i != m_cue_entries.end(); ++i)
	{
		ePyObject tuple = PyTuple_New(2);
		PyTuple_SET_ITEM(tuple, 0, PyLong_FromLongLong(i->where));
		PyTuple_SET_ITEM(tuple, 1, PyLong_FromLong(i->what));
		PyList_Append(list, tuple);
		Py_DECREF(tuple);
	}

	return list;
}
/* cuesheet CVR */
void eServiceMP3::setCutList(ePyObject list)
{
	if (!PyList_Check(list))
		return;
	int size = PyList_Size(list);
	int i;

	m_cue_entries.clear();

	for (i=0; i<size; ++i)
	{
		ePyObject tuple = PyList_GET_ITEM(list, i);
		if (!PyTuple_Check(tuple))
		{
			eDebug("[eServiceMP3] non-tuple in cutlist");
			continue;
		}
		if (PyTuple_Size(tuple) != 2)
		{
			eDebug("[eServiceMP3] cutlist entries need to be a 2-tuple");
			continue;
		}
		ePyObject ppts = PyTuple_GET_ITEM(tuple, 0), ptype = PyTuple_GET_ITEM(tuple, 1);
		if (!(PyLong_Check(ppts) && PyLong_Check(ptype)))
		{
			eDebug("[eServiceMP3] cutlist entries need to be (pts, type)-tuples (%d %d)", PyLong_Check(ppts), PyLong_Check(ptype));
			continue;
		}
		pts_t pts = PyLong_AsLongLong(ppts);
		int type = PyLong_AsLong(ptype);
		m_cue_entries.insert(cueEntry(pts, type));
		eDebug("[eServiceMP3] adding %08llx, %d", pts, type);
	}
	m_cuesheet_changed = 1;
	m_event((iPlayableService*)this, evCuesheetChanged);
}

void eServiceMP3::setCutListEnable(int enable)
{
	m_cutlist_enabled = enable;
}

int eServiceMP3::setBufferSize(int size)
{
	m_buffer_size = size;
	g_object_set (G_OBJECT (m_gst_playbin), "buffer-size", m_buffer_size, NULL);
	return 0;
}

int eServiceMP3::getAC3Delay()
{
	return ac3_delay;
}

int eServiceMP3::getPCMDelay()
{
	return pcm_delay;
}

void eServiceMP3::setAC3Delay(int delay)
{
	ac3_delay = delay;
	if (!m_gst_playbin || m_state != stRunning)
		return;
	else
	{
		int config_delay_int = delay;

		/*
		 * NOTE: We only look for dvbmediasinks.
		 * If either the video or audio sink is of a different type,
		 * we have no chance to get them synced anyway.
		 */
		if (videoSink)
		{
			config_delay_int += eConfigManager::getConfigIntValue("config.av.generalAC3delay");
		}
		else
		{
			eDebug("[eServiceMP3] dont apply ac3 delay when no video is running!");
			config_delay_int = 0;
		}

		if (audioSink)
		{
			eTSMPEGDecoder::setHwAC3Delay(config_delay_int);
		}
	}
}

void eServiceMP3::setPCMDelay(int delay)
{
	pcm_delay = delay;
	if (!m_gst_playbin || m_state != stRunning)
		return;
	else
	{
		int config_delay_int = delay;

		/*
		 * NOTE: We only look for dvbmediasinks.
		 * If either the video or audio sink is of a different type,
		 * we have no chance to get them synced anyway.
		 */
		if (videoSink)
		{
			config_delay_int += eConfigManager::getConfigIntValue("config.av.generalPCMdelay");
		}
		else
		{
			eDebug("[eServiceMP3] dont apply pcm delay when no video is running!");
			config_delay_int = 0;
		}

		if (audioSink)
		{
			eTSMPEGDecoder::setHwPCMDelay(config_delay_int);
		}
	}
}
/* cuesheet CVR */
void eServiceMP3::loadCuesheet()
{
	if (!m_cuesheet_loaded)
	{
		eDebug("[eServiceMP3] loading cuesheet");
		m_cuesheet_loaded = true;
	}
	else
	{
		eDebug("[eServiceMP3] skip loading cuesheet multiple times");
		return;
	}

	m_cue_entries.clear();
	/* only load manual cuts if no chapter info avbl CVR */
	if (m_use_chapter_entries)
		return;

	std::string filename = m_ref.path + ".cuts";

	m_cue_entries.clear();

	FILE *f = fopen(filename.c_str(), "rb");

	if (f)
	{
		while (1)
		{
			unsigned long long where;
			unsigned int what;

			if (!fread(&where, sizeof(where), 1, f))
				break;
			if (!fread(&what, sizeof(what), 1, f))
				break;

			where = be64toh(where);
			what = ntohl(what);

			if (what > 3)
				break;

			m_cue_entries.insert(cueEntry(where, what));
		}
		fclose(f);
		eDebug("[eServiceMP3] cuts file has %zd entries", m_cue_entries.size());
	} else
		eDebug("[eServiceMP3] cutfile not found!");

	m_cuesheet_changed = 0;
	m_event((iPlayableService*)this, evCuesheetChanged);
}
/* cuesheet CVR */
void eServiceMP3::saveCuesheet()
{
	std::string filename = m_ref.path;

		/* save cuesheet only when main file is accessible. */
		/* save cuesheet only when main file is accessible. and no TOC chapters avbl*/
	if ((::access(filename.c_str(), R_OK) < 0) || m_use_chapter_entries)
		return;
	filename.append(".cuts");
	/* do not save to file if there are no cuts */
	/* remove the cuts file if cue is empty */
	if(m_cue_entries.begin() == m_cue_entries.end())
	{
		if (::access(filename.c_str(), F_OK) == 0)
			remove(filename.c_str());
		return;
	}

	FILE *f = fopen(filename.c_str(), "wb");

	if (f)
	{
		unsigned long long where;
		int what;

		for (std::multiset<cueEntry>::iterator i(m_cue_entries.begin()); i != m_cue_entries.end(); ++i)
		{
			where = htobe64(i->where);
			what = htonl(i->what);
			fwrite(&where, sizeof(where), 1, f);
			fwrite(&what, sizeof(what), 1, f);

		}
		fclose(f);
	}
	m_cuesheet_changed = 0;
}
