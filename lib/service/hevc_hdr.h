#ifndef HEVC_HDR_H
#define HEVC_HDR_H

#include <stdint.h>

namespace HevcHDR {

enum { HDR_SDR = 0, HDR_HDR10 = 1, HDR_HLG = 2, HDR_GENERIC = 3 };

/* Classify an Annex-B HEVC elementary stream buffer.
   Returns HDR_SDR / HDR_HDR10 / HDR_HLG / HDR_GENERIC.
   *sawSPS is set true if at least one SPS (RAP) was seen (= result trustworthy). */
int classify(const uint8_t *buf, int len, bool *sawSPS);

} // namespace
#endif
