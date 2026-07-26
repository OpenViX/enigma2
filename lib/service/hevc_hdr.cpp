#include <lib/service/hevc_hdr.h>
#include <vector>

namespace {

class BitReader {
	std::vector<uint8_t> d;
	int pos, size;
public:
	BitReader(const uint8_t *data, int len) : pos(0) {
		d.reserve(len);
		/* RBSP trailing bits + emulation-prevention removal */
		int zeros = 0;
		for (int i = 0; i < len; i++) {
			uint8_t b = data[i];
			if (zeros >= 2 && b == 0x03) { zeros = 0; continue; }
			d.push_back(b);
			zeros = (b == 0x00) ? zeros + 1 : 0;
		}
		size = (int)d.size() * 8;
	}
	int bit() {
		if (pos >= size) return 0;
		int bi = pos >> 3, off = 7 - (pos & 7);
		pos++;
		return (d[bi] >> off) & 1;
	}
	bool exhausted() const { return pos >= size; }
	uint32_t u(int n) { uint32_t v = 0; while (n--) v = (v << 1) | bit(); return v; }
	uint32_t ue() { int lz = 0; while (bit() == 0 && lz < 32) lz++; return (1u << lz) - 1 + u(lz); }
	int32_t se() { uint32_t k = ue(); return (k & 1) ? (int32_t)((k + 1) >> 1) : -(int32_t)(k >> 1); }
};

void skip_ptl(BitReader &br, int maxSub) {
	br.u(2); br.u(1); br.u(5);
	br.u(32); br.u(32); br.u(16); br.u(8);
	int sp[8] = {0}, sl[8] = {0};
	for (int i = 0; i < maxSub; i++) { sp[i] = br.u(1); sl[i] = br.u(1); }
	if (maxSub > 0) for (int i = maxSub; i < 8; i++) br.u(2);
	for (int i = 0; i < maxSub; i++) {
		if (sp[i]) {
			br.u(2); br.u(1); br.u(5); br.u(32); br.u(32); br.u(16); }
		if (sl[i]) br.u(8);
	}
}

void skip_strps(BitReader &br, int num) {
	/* num comes straight from a bitstream ue() read; a truncated/misaligned
	 * SPS can desync the bit reader and yield a huge garbage count here.
	 * Spec caps num_short_term_ref_pic_sets at 64 - clamp defensively, and
	 * also bail as soon as the reader runs dry rather than looping on
	 * synthetic zero-bits. */
	if (num > 64) num = 64;
	std::vector<int> ndp(num + 1, 0);
	for (int idx = 0; idx < num; idx++) {
		if (br.exhausted()) break;
		int inter = (idx != 0) ? br.u(1) : 0;
		if (inter) {
			br.u(1); br.ue();
			int nd = ndp[idx - 1], cnt = 0;
			for (int j = 0; j <= nd; j++) {
				int used = br.u(1), useDelta = 1;
				if (!used) useDelta = br.u(1);
				if (used || useDelta) cnt++;
			}
			ndp[idx] = cnt;
		} else {
			/* num_negative_pics / num_positive_pics: spec bounds their sum
			 * by sps_max_dec_pic_buffering (<=16) - same desync risk as
			 * num above, clamp each defensively. */
			uint32_t neg = br.ue(), pos = br.ue();
			if (neg > 16) neg = 16;
			if (pos > 16) pos = 16;
			ndp[idx] = neg + pos;
			for (uint32_t j = 0; j < neg && !br.exhausted(); j++) { br.ue(); br.u(1); }
			for (uint32_t j = 0; j < pos && !br.exhausted(); j++) { br.ue(); br.u(1); }
		}
	}
}

void skip_scaling(BitReader &br) {
	for (int s = 0; s < 4; s++) {
		int mc = (s != 3) ? 6 : 2;
		for (int m = 0; m < mc; m++) {
			if (!br.u(1)) br.ue();
			else {
				int n = (1 << (4 + (s << 1))); if (n > 64) n = 64;
				if (s > 1) br.se();
				for (int k = 0; k < n; k++) br.se();
			}
		}
	}
}

/* returns transfer_characteristics, or -1 */
int sps_transfer(const uint8_t *rbsp, int len) {
	BitReader br(rbsp, len);
	br.u(4);
	int maxSub = br.u(3);
	br.u(1);
	skip_ptl(br, maxSub);
	br.ue();
	uint32_t chroma = br.ue();
	if (chroma == 3) br.u(1);
	br.ue(); br.ue();
	if (br.u(1)) { br.ue(); br.ue(); br.ue(); br.ue(); }
	br.ue(); br.ue();
	uint32_t log2poc = br.ue();
	int subPresent = br.u(1);
	for (int i = subPresent ? 0 : maxSub; i <= maxSub; i++) { br.ue(); br.ue(); br.ue(); }
	br.ue(); br.ue(); br.ue(); br.ue(); br.ue(); br.ue();
	if (br.u(1)) { if (br.u(1)) skip_scaling(br); }
	br.u(1); br.u(1);
	if (br.u(1)) { br.u(4); br.u(4); br.ue(); br.ue(); br.u(1); }
	uint32_t numShort = br.ue();
	if (numShort > 0) skip_strps(br, numShort);
	if (br.u(1)) {
		/* num_long_term_ref_pics_sps: same desync risk as numShort above -
		 * spec caps this at 32, clamp and bail early on exhaustion. */
		uint32_t n = br.ue();
		if (n > 32) n = 32;
		for (uint32_t i = 0; i < n && !br.exhausted(); i++) { br.u(log2poc + 4); br.u(1); }
	}
	br.u(1); br.u(1);
	if (!br.u(1)) return -1;                 /* vui_present */
	if (br.u(1)) { uint32_t idc = br.u(8); if (idc == 255) { br.u(16); br.u(16); } }
	if (br.u(1)) br.u(1);
	if (br.u(1)) {                           /* video_signal_type */
		br.u(3); br.u(1);
		if (br.u(1)) { br.u(8); int tc = br.u(8); br.u(8); return tc; }
	}
	return -1;
}

/* bit0=mdcv(137) bit1=cll(144); altTransfer=147 value or -1 */
int sei_flags(const uint8_t *rbsp, int len, int *altTransfer) {
	std::vector<uint8_t> d; d.reserve(len);
	int zeros = 0;
	for (int i = 0; i < len; i++) {
		uint8_t b = rbsp[i];
		if (zeros >= 2 && b == 0x03) { zeros = 0; continue; }
		d.push_back(b);
		zeros = (b == 0x00) ? zeros + 1 : 0;
	}
	int flags = 0; *altTransfer = -1;
	int i = 0, n = (int)d.size();
	while (i < n) {
		int type = 0;
		while (i < n && d[i] == 0xff) { type += 255; i++; }
		if (i < n) { type += d[i]; i++; }
		int sz = 0;
		while (i < n && d[i] == 0xff) { sz += 255; i++; }
		if (i < n) { sz += d[i]; i++; }
		if (type == 137) flags |= 1;
		else if (type == 144) flags |= 2;
		else if (type == 147) { if (sz >= 1 && i < n) *altTransfer = d[i]; }
		i += sz;
		if (type == 0 && sz == 0) break;
	}
	return flags;
}

} // anon

namespace HevcHDR {

int classify(const uint8_t *buf, int len, bool *sawSPS) {
	int bestTc = -1, altTc = -1, seiFlags = 0;
	bool gotSPS = false;
	int i = 0;
	while (i + 4 < len) {
		if (buf[i] == 0 && buf[i+1] == 0 && buf[i+2] == 1) {
			int nalStart = i + 3;
			int type = (buf[nalStart] >> 1) & 0x3f;
			int payload = nalStart + 2;
			int j = payload;
			while (j + 3 < len && !(buf[j]==0 && buf[j+1]==0 && buf[j+2]==1)) j++;
			int plen = j - payload;
			if (plen > 0) {
				if (type == 33) {
					gotSPS = true;
					int tc = sps_transfer(buf + payload, plen);
					if (tc >= 0) bestTc = tc;
				} else if (type == 39 || type == 40) {
					int at = -1;
					seiFlags |= sei_flags(buf + payload, plen, &at);
					if (at >= 0) altTc = at;
				}
			}
			i = nalStart;
		} else i++;
	}
	if (sawSPS) *sawSPS = gotSPS;
	int effTc = (altTc >= 0) ? altTc : bestTc;
	if (effTc == 16 || (seiFlags & 1)) return HDR_HDR10;
	if (effTc == 18) return HDR_HLG;
	if (effTc == 14 || effTc == 15) return HDR_GENERIC; /* BT.2020 traditional gamma */
	return HDR_SDR;
}

} // namespace
