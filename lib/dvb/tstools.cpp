#include <lib/dvb/tstools.h>
#include <lib/dvb/specs.h>
#include <lib/base/eerror.h>
#include <lib/base/cachedtssource.h>
#include <unistd.h>
#include <fcntl.h>

#include <stdio.h>

static const int m_maxrange = 256*1024;

DEFINE_REF(eTSFileSectionReader);

eTSFileSectionReader::eTSFileSectionReader(eMainloop *context)
{
	sectionSize = 0;
}

eTSFileSectionReader::~eTSFileSectionReader()
{
}

void eTSFileSectionReader::data(unsigned char *packet, unsigned int size)
{
	if (sectionSize + size <= sizeof(sectionData))
	{
		memcpy(&sectionData[sectionSize], packet, size);
		sectionSize += size;
	}
	if (sectionSize >= (unsigned int)(3 + ((sectionData[1] & 0x0f) << 8) + sectionData[2]))
	{
		sectionSize = 0;
		read(sectionData);
	}
}

RESULT eTSFileSectionReader::start(const eDVBSectionFilterMask &mask)
{
	sectionSize = 0;
	return 0;
}

RESULT eTSFileSectionReader::stop()
{
	sectionSize = 0;
	return 0;
}

RESULT eTSFileSectionReader::connectRead(const sigc::slot1<void,const uint8_t*> &r, ePtr<eConnection> &conn)
{
	conn = new eConnection(this, read.connect(r));
	return 0;
}

eDVBTSTools::eDVBTSTools():
	m_pid(-1),
	m_packet_size(188),
	m_begin_valid (0),
	m_end_valid(0),
	m_samples_taken(0),
	m_last_filelength(0),
	m_futile(0)
{
}

void eDVBTSTools::closeSource()
{
	m_source = NULL;
	m_packet_size = 188;
}

eDVBTSTools::~eDVBTSTools()
{
	closeSource();
}

int eDVBTSTools::openFile(const char *filename, int nostreaminfo)
{
	eRawFile *f = new eRawFile();
	ePtr<iTsSource> src = f;

	if (f->open(filename) < 0)
		return -1;

	src = new eCachedSource(src);

	setSource(src, nostreaminfo ? NULL : filename);

	return 0;
}

void eDVBTSTools::setSource(ePtr<iTsSource> &source, const char *stream_info_filename)
{
	closeSource();
	m_source = source;
	if (stream_info_filename)
	{
		eDebug("[eDVBTSTools] setSource loading streaminfo for %s", stream_info_filename);
		m_streaminfo.load(stream_info_filename);
	}
	m_samples_taken = 0;
	m_packet_size = m_source ? m_source->getPacketSize() : 188;
}

	/* getPTS extracts a pts value from any PID at a given offset. */
int eDVBTSTools::getPTS(off_t &offset, pts_t &pts, int fixed)
{
	if (m_streaminfo.getPTS(offset, pts) == 0)
		return 0; // Okay, the cache had it

	if (m_streaminfo.hasStructure())
	{
		off_t local_offset = offset;
		unsigned long long data;
		if (m_streaminfo.getStructureEntryFirst(local_offset, data) == 0)
		{
			for(int retries = 8; retries != 0; --retries)
			{
				if ((data & 0x1000000) != 0)
				{
					pts = data >> 31;
					if (pts == 0)
					{
						// obsolete data that happens to have a '1' there
						continue;
					}
					eDebug("[eDVBTSTools] getPTS got it from sc file offset=%lld pts=%lld", local_offset, pts);
					if (fixed && fixupPTS(local_offset, pts))
					{
						eDebug("[eDVBTSTools]    But failed to fixup!");
						break;
					}
					offset = local_offset;
					return 0;
				}
				else
				{
					eDebug("[eDVBTSTools] getPTS No PTS, try next");
				}
				if (m_streaminfo.getStructureEntryNext(local_offset, data, 1) != 0)
				{
					eDebug("[eDVBTSTools] getPTS Cannot find next structure entry");
					break;
				}
			}
		}
	}
	if (!m_source || !m_source->valid())
		return -1;

	offset -= offset % m_packet_size;

	int left = m_maxrange;
	int resync_failed_counter = 64;

	while (left >= m_packet_size)
	{
		unsigned char buffer[m_packet_size];
		unsigned char *packet = &buffer[m_packet_size - 188];
		if (m_source->read(offset, buffer, m_packet_size) != m_packet_size)
		{
			eDebug("[eDVBTSTools] getPTS read error");
			return -1;
		}
		left -= m_packet_size;
		offset += m_packet_size;

		if (packet[0] != 0x47)
		{
			const unsigned char* match = (const unsigned char*)memchr(packet+1, 0x47, 188-1);
			if (match != NULL)
			{
				eDebug("[eDVBTSTools] getPTS resync %d", match - packet);
				offset += (match - packet) - 188;
			}
			else
			{
				eDebug("[eDVBTSTools] getPTS resync failed");
				if (resync_failed_counter == 0)
				{
					eDebug("[eDVBTSTools] getPTS Too many resync failures, probably not a valid stream");
					return -1;
				}
				--resync_failed_counter;
			}
			continue;
		}

		int pid = ((packet[1] << 8) | packet[2]) & 0x1FFF;
		int pusi = !!(packet[1] & 0x40);

//		printf("PID %04x, PUSI %d\n", pid, pusi);

		unsigned char *payload;

			/* check for adaption field */
		if (packet[3] & 0x20)
		{
			if (packet[4] >= 183)
				continue;
			if (packet[4])
			{
				if (packet[5] & 0x10) /* PCR present */
				{
					pts  = ((unsigned long long)(packet[ 6]&0xFF)) << 25;
					pts |= ((unsigned long long)(packet[ 7]&0xFF)) << 17;
					pts |= ((unsigned long long)(packet[ 8]&0xFE)) << 9;
					pts |= ((unsigned long long)(packet[ 9]&0xFF)) << 1;
					pts |= ((unsigned long long)(packet[10]&0x80)) >> 7;
					offset -= 188;
					eDebug("[eDVBTSTools] getPTS PCR %16llx found at %lld pid %02x (%02x %02x %02x %02x %02x %02x %02x %02x %02x %02x %02x)", pts, offset, pid, packet[0], packet[1], packet[2], packet[3], packet[4], packet[5], packet[6], packet[7], packet[8], packet[9], packet[10]);
					if (fixed && fixupPTS(offset, pts))
						return -1;
					return 0;
				}
			}
			payload = packet + packet[4] + 4 + 1;
		} else
			payload = packet + 4;

/*		if (m_pid >= 0)
			if (pid != m_pid)
				continue; */
		if (!pusi)
			continue;

			/* somehow not a startcode. (this is invalid, since pusi was set.) ignore it. */
		if (payload[0] || payload[1] || (payload[2] != 1))
			continue;

		if (payload[3] == 0xFD)
		{ // stream use extension mechanism defined in ISO 13818-1 Amendment 2
			if (payload[7] & 1) // PES extension flag
			{
				int offs = 0;
				if (payload[7] & 0x80) // pts avail
					offs += 5;
				if (payload[7] & 0x40) // dts avail
					offs += 5;
				if (payload[7] & 0x20) // escr avail
					offs += 6;
				if (payload[7] & 0x10) // es rate
					offs += 3;
				if (payload[7] & 0x8) // dsm trickmode
					offs += 1;
				if (payload[7] & 0x4) // additional copy info
					offs += 1;
				if (payload[7] & 0x2) // crc
					offs += 2;
				if (payload[8] < offs)
					continue;
				uint8_t pef = payload[9+offs++]; // pes extension field
				if (pef & 1) // pes extension flag 2
				{
					if (pef & 0x80) // private data flag
						offs += 16;
					if (pef & 0x40) // pack header field flag
						offs += 1;
					if (pef & 0x20) // program packet sequence counter flag
						offs += 2;
					if (pef & 0x10) // P-STD buffer flag
						offs += 2;
					if (payload[8] < offs)
						continue;
					uint8_t stream_id_extension_len = payload[9+offs++] & 0x7F;
					if (stream_id_extension_len >= 1)
					{
						if (payload[8] < (offs + stream_id_extension_len) )
							continue;
						if (payload[9+offs] & 0x80) // stream_id_extension_bit (should not set)
							continue;
						switch (payload[9+offs])
						{
						case 0x55 ... 0x5f: // VC-1
							break;
						case 0x71: // AC3 / DTS
							break;
						case 0x72: // DTS - HD
							break;
						default:
							eDebug("[eDVBTSTools] getPTS skip unknown stream_id_extension %02x\n", payload[9+offs]);
							continue;
						}
					}
					else
						continue;
				}
				else
					continue;
			}
			else
				continue;
		}
			/* drop non-audio, non-video packets because other streams
			   can be non-compliant.*/
		else if (((payload[3] & 0xE0) != 0xC0) &&  // audio
			((payload[3] & 0xF0) != 0xE0)) // video
			continue;

		if (payload[7] & 0x80) /* PTS */
		{
			pts  = ((unsigned long long)(payload[ 9]&0xE))  << 29;
			pts |= ((unsigned long long)(payload[10]&0xFF)) << 22;
			pts |= ((unsigned long long)(payload[11]&0xFE)) << 14;
			pts |= ((unsigned long long)(payload[12]&0xFF)) << 7;
			pts |= ((unsigned long long)(payload[13]&0xFE)) >> 1;
			offset -= 188;

			eDebug("[eDVBTSTools] getPTS PTS %16llx found at %lld pid %02x stream: %02x", pts, offset, pid, payload[3]);

				/* convert to zero-based */
			if (fixed && fixupPTS(offset, pts))
				return -1;
			return 0;
		}
	}

	return -1;
}

int eDVBTSTools::fixupPTS(const off_t &offset, pts_t &now)
{
	if (m_streaminfo.fixupPTS(offset, now) == 0)
	{
		return 0;
	}
	else
	{
			/* for the simple case, we assume one epoch, with up to one wrap around in the middle. */
		calcBegin();
		if (!m_begin_valid)
		{
			eDebug("[eDVBTSTools] fixupPTS begin not valid, can't fixup");
			return -1;
		}

		pts_t pos = m_pts_begin;
		if ((now < pos) && ((pos - now) < 90000 * 10))
		{
			pos = 0;
			return 0;
		}

		if (now < pos) /* wrap around */
			now = now + 0x200000000LL - pos;
		else
			now -= pos;
		return 0;
	}
	eDebug("[eDVBTSTools] fixupPTS failed!");
	return -1;
}

int eDVBTSTools::getOffset(off_t &offset, pts_t &pts, int marg)
{
	if (m_streaminfo.hasAccessPoints())
	{
		if ((pts >= m_pts_end) && (marg > 0) && m_end_valid)
			offset = m_offset_end;
		else
			offset = m_streaminfo.getAccessPoint(pts, marg);
		return 0;
	}
	else
	{
		calcBeginAndEnd();
		if (!m_begin_valid)
			return -1;
		if (!m_end_valid)
			return -1;

		if (!m_samples_taken)
			takeSamples();

		if (!m_samples.empty())
		{
			int maxtries = 5;
			pts_t p = -1;

			while (maxtries--)
			{
					/* search entry before and after */
				std::map<pts_t, off_t>::const_iterator l = m_samples.lower_bound(pts);
				std::map<pts_t, off_t>::const_iterator u = l;

				if (l != m_samples.begin())
					--l;

					/* we could have seeked beyond the end */
				if (u == m_samples.end())
				{
						/* use last segment for interpolation. */
					if (l != m_samples.begin())
					{
						--u;
						--l;
					}
				}

					/* if we don't have enough points */
				if (u == m_samples.end())
					break;

				pts_t pts_diff = u->first - l->first;
				off_t offset_diff = u->second - l->second;

				if (offset_diff < 0)
				{
					eDebug("[eDVBTSTools] getOffset something went wrong when taking samples.");
					m_samples.clear();
					takeSamples();
					continue;
				}

				eDebug("[eDVBTSTools] getOffset using: %lld:%lld -> %lld:%lld", l->first, u->first, l->second, u->second);

				int bitrate;

				if (pts_diff)
					bitrate = offset_diff * 90000 * 8 / pts_diff;
				else
					bitrate = 0;

				offset = l->second;
				offset += ((pts - l->first) * (pts_t)bitrate) / 8ULL / 90000ULL;
				offset -= offset % m_packet_size;
				if (offset > m_offset_end)
				{
					/*
					 * NOTE: the bitrate calculation can be way off, especially when the pts difference is small.
					 * So the calculated offset might be far ahead of the end of the file.
					 * When that happens, avoid poisoning our sample list (m_samples) with an invalid value,
					 * which could eventually cause (timeshift) playback to be stopped.
					 * Because the file could be growing (timeshift), instead of returning the currently known end
					 * of file offset, we return an offset 1MB ahead of the end of the file.
					 * This allows jumping to the live point of the timeshift, for instance.
					 */
					offset = m_offset_end + 1024 * 1024;
					return 0;
				}

				p = pts;

				if (!takeSample(offset, p))
				{
					int diff = (p - pts) / 90;

					eDebug("[eDVBTSTools] getOffset calculated diff %d ms", diff);
					if (abs(diff) > 300)
					{
						eDebug("[eDVBTSTools] getOffset diff to big, refining");
						continue;
					}
				} else
					eDebug("[eDVBTSTools] getOffset no sample taken, refinement not possible.");

				break;
			}

				/* if even the first sample couldn't be taken, fall back. */
				/* otherwise, return most refined result. */
			if (p != -1)
			{
				pts = p;
				eDebug("[eDVBTSTools] getOffset aborting. Taking %lld as offset for %lld", offset, pts);
				return 0;
			}
		}

		int bitrate = calcBitrate();
		offset = pts * (pts_t)bitrate / 8ULL / 90000ULL;
		eDebug("[eDVBTSTools] getOffset fallback, bitrate=%d, results in %016llx", bitrate, offset);
		offset -= offset % m_packet_size;
		return 0;
	}
}

int eDVBTSTools::getNextAccessPoint(pts_t &ts, const pts_t &start, int direction)
{
	return m_streaminfo.getNextAccessPoint(ts, start, direction);
}

void eDVBTSTools::calcBegin()
{
	if (!m_source || !m_source->valid())
		return;

	if (!(m_begin_valid || m_futile))
	{
		// Just ask streaminfo
		if (m_streaminfo.getFirstFrame(m_offset_begin, m_pts_begin) == 0)
		{
			off_t begin = m_offset_begin;
			pts_t pts = m_pts_begin;
			if (m_streaminfo.fixupPTS(begin, pts) == 0)
			{
				eDebug("[eDVBTSTools] calcBegin [@ML] m_streaminfo.getLastFrame returned %lld, %lld (%us), fixup to: %lld, %lld (%us)",
				       m_offset_begin, m_pts_begin, (unsigned int)(m_pts_begin/90000), begin, pts, (unsigned int)(pts/90000));
			}
			m_begin_valid = 1;
		}
		else
		{
			m_offset_begin = 0;
			if (!getPTS(m_offset_begin, m_pts_begin))
				m_begin_valid = 1;
			else
				m_futile = 1;
		}
		if (m_begin_valid)
		{
			/*
			 * We've just calculated the begin position, which will have an effect on the
			 * calculated length.
			 * (when the end position had been determined before the begin position, the length
			 * will be invalid)
			 * So we force the end position to be (re-)calculated after the begin position has
			 * been determined, in order to ensure m_pts_length will be corrected.
			 */
			 m_end_valid = 0;

		}
	}
}

static pts_t pts_diff(pts_t low, pts_t high)
{
	high -= low;
	if (high < 0)
		high += 0x200000000LL;
	return high;
}

void eDVBTSTools::calcEnd()
{
	if (!m_source || !m_source->valid())
		return;

	// If there's a structure file, the calculation is much smarter, so we can try more often
	off_t threshold = m_streaminfo.hasStructure() ? 100*1024 : 1024*1024;

	off_t end = m_source->length();
	if (llabs(end - m_last_filelength) > threshold)
	{
		m_last_filelength = end;
		m_end_valid = 0;
		m_futile = 0;
//		eDebug("[eDVBTSTools] calcEnd file size changed, recalc length");
	}

	int maxiter = 10;

	if (!m_end_valid)
	{
		off_t offset = m_offset_end = m_last_filelength;
		pts_t pts = m_pts_end;
		if (m_streaminfo.getLastFrame(offset, pts) == 0)
		{
			m_offset_end = offset;
			m_pts_length = m_pts_end = pts;
			end = m_offset_end;
			if (m_streaminfo.fixupPTS(end, m_pts_length) != 0)
			{
				/* Not enough structure info, estimate */
				m_pts_length = pts_diff(m_pts_begin, m_pts_end);
			}
			m_end_valid = 1;
		}
		else
		{
			eDebug("[eDVBTSTools] calcEnd [@ML] m_streaminfo.getLastFrame failed, fallback");
			while (!(m_end_valid || m_futile))
			{
				if (!--maxiter)
				{
					m_futile = 1;
					return;
				}

				m_offset_end -= m_maxrange;
				if (m_offset_end < 0)
					m_offset_end = 0;

				offset = m_offset_end;
				pts = m_pts_end;
				if (!getPTS(offset, pts))
				{
					offset = m_offset_end;
					m_pts_end = pts;
					m_pts_length = pts_diff(m_pts_begin, m_pts_end);
					m_end_valid = 1;
				}

				if (!m_offset_end)
				{
					m_futile = 1;
					break;
				}
			}
		}
	}
}

void eDVBTSTools::calcBeginAndEnd()
{
	calcBegin();
	calcEnd();
}

int eDVBTSTools::calcLen(pts_t &len)
{
	calcBeginAndEnd();
	if (!(m_begin_valid && m_end_valid))
		return -1;
	len = m_pts_length;
	return 0;
}

int eDVBTSTools::calcBitrate()
{
	pts_t len_in_pts;
	if (calcLen(len_in_pts) != 0)
		return -1;
	off_t len_in_bytes = m_offset_end - m_offset_begin;

	if (!len_in_pts)
		return -1;

	unsigned long long bitrate = len_in_bytes * 90000 * 8 / len_in_pts;
	if ((bitrate < 10000) || (bitrate > 100000000))
		return -1;

	return bitrate;
}

	/* pts, off */
void eDVBTSTools::takeSamples()
{
	m_samples_taken = 1;
	m_samples.clear();
	int retries=2;

	calcBeginAndEnd();
	if (!(m_begin_valid && m_end_valid))
		return;

	int nr_samples = 30;
	off_t bytes_per_sample = (m_offset_end - m_offset_begin) / (long long)nr_samples;
	if (bytes_per_sample < 40*1024*1024)
		bytes_per_sample = 40*1024*1024;

	bytes_per_sample -= bytes_per_sample % m_packet_size;

	eDebug("[eDVBTSTools] takeSamples step %lld, pts begin %lld, pts end %lld, offs begin %lld, offs end %lld:",
		bytes_per_sample, m_pts_begin, m_pts_end, m_offset_begin, m_offset_end);

	for (off_t offset = m_offset_begin; offset < m_offset_end;)
	{
		pts_t p;
		if (takeSample(offset, p) && retries--)
			continue;
		retries = 2;
		offset += bytes_per_sample;
	}
	m_samples[0] = m_offset_begin;
	m_samples[m_pts_end - m_pts_begin] = m_offset_end;
}

	/* returns 0 when a sample was taken. */
int eDVBTSTools::takeSample(off_t off, pts_t &p)
{
	off_t offset_org = off;

	if (!eDVBTSTools::getPTS(off, p, 1))
	{
			/* as we are happily mixing PTS and PCR values (no comment, please), we might
			   end up with some "negative" segments.

			   so check if this new sample is between the previous and the next field*/

		std::map<pts_t, off_t>::const_iterator l = m_samples.lower_bound(p);
		std::map<pts_t, off_t>::const_iterator u = l;

		if (l != m_samples.begin())
		{
			--l;
			if (u != m_samples.end())
			{
				if ((l->second > off) || (u->second < off))
				{
					eDebug("[eDVBTSTools] takeSample ignoring sample %lld %lld %lld (%lld %lld %lld)",
						l->second, off, u->second, l->first, p, u->first);
					return 1;
				}
			}
		}

		eDebug("[eDVBTSTools] takeSample adding sample %lld: pts %lld -> pos %lld (diff %lld bytes)", offset_org, p, off, off-offset_org);
		m_samples[p] = off;
		return 0;
	}
	return -1;
}

int eDVBTSTools::findPMT(eDVBPMTParser::program &program)
{
	int pmtpid = -1;
	ePtr<iDVBSectionReader> sectionreader;

	eDVBPMTParser::clearProgramInfo(program);

		/* FIXME: this will be factored out soon! */
	if (!m_source || !m_source->valid())
	{
		eDebug("[eDVBTSTools] findPMT file not valid");
		return -1;
	}

	off_t position=0;
	m_pmtready = false;

	for (int attempts_left = (5*1024*1024)/m_packet_size; attempts_left != 0; --attempts_left)
	{
		unsigned char buffer[m_packet_size];
		unsigned char *packet = &buffer[m_packet_size - 188];
		int ret = m_source->read(position, buffer, m_packet_size);
		if (ret != m_packet_size)
		{
			eDebug("[eDVBTSTools] findPMT read error");
			break;
		}
		position += m_packet_size;

		if (packet[0] != 0x47)
		{
			int i = 0;
			while (i < 188)
			{
				if (packet[i] == 0x47)
					break;
				--position;
				++i;
			}
			continue;
		}

		if (pmtpid < 0 && !(packet[1] & 0x40)) /* pusi */
			continue;

			/* ok, now we have a PES header or section header*/
		unsigned char *sec;

			/* check for adaption field */
		if (packet[3] & 0x20)
		{
			if (packet[4] >= 183)
				continue;
			sec = packet + packet[4] + 4 + 1;
		} else
			sec = packet + 4;

		if (pmtpid < 0)
		{
			if (sec[0]) /* table pointer, assumed to be 0 */
				continue;
			if (sec[1] == 0x02) /* program map section */
			{
				pmtpid = ((packet[1] << 8) | packet[2]) & 0x1FFF;
				int sid = (sec[4] << 8) | sec[5];
				sectionreader = new eTSFileSectionReader(eApp);
				m_PMT.begin(eApp, eDVBPMTSpec(pmtpid, sid), sectionreader);
				((eTSFileSectionReader*)(iDVBSectionReader*)sectionreader)->data(&sec[1], 188 - (sec + 1 - packet));
			}
		}
		else if (pmtpid == (((packet[1] << 8) | packet[2]) & 0x1FFF))
		{
			((eTSFileSectionReader*)(iDVBSectionReader*)sectionreader)->data(sec, 188 - (sec - packet));
		}
		if (m_pmtready)
		{
			program = m_program;
			return 0;
		}
	}
	m_PMT.stop();
	return -1;
}

int eDVBTSTools::findFrame(off_t &_offset, size_t &len, int &direction, int frame_types)
{
//	eDebug("[eDVBTSTools] findFrame trying to find iFrame at %lld", offset);
	if (!m_streaminfo.hasStructure())
	{
//		eDebug("[eDVBTSTools] findFrame can't get next iframe without streaminfo");
		return -1;
	}

	off_t offset = _offset;
	int nr_frames = 0;
	bool is_mpeg2 = false;

		/* let's find the iframe before the given offset */
	if (direction < 0)
		offset--;

	unsigned long long longdata;
	if (m_streaminfo.getStructureEntryFirst(offset, longdata) != 0)
	{
		eDebug("[eDVBTSTools] findFrame getStructureEntryFirst failed");
		return -1;
	}
	if (direction == 0)
	{
		// Special case, move an extra frame ahead
		if (m_streaminfo.getStructureEntryNext(offset, longdata, 1) != 0)
			return -1;
		direction = 1;
	}
	while (1)
	{
		unsigned int data = (unsigned int)longdata; // only the lower bits are interesting
			/* data is usually the start code in the lower 8 bit, and the next byte <<8. we extract the picture type from there */
			/* we know that we aren't recording startcode 0x09 for mpeg2, so this is safe */
			/* TODO: check frame_types */
		// is_frame
		if (((data & 0xFF) == 0x0009) || ((data & 0xFF) == 0x00) || ((data & 0x7E) == 0x0046)) /* H.264 UAD or H.265 UAD or MPEG2 start code */
		{
			++nr_frames;
			if ((data & 0xE0FF) == 0x0009)		/* H.264 NAL unit access delimiter with I-frame*/
			{
				break;
			}
			if ((data & 0xE07E) == 0x0046) 		/* H.265 NAL unit access delimiter with I-frame*/
			{
				break;
			}
			if ((data & 0x3800FF) == 0x080000)	/* MPEG2 picture start code with I-frame */
			{
				is_mpeg2 = true;
				break;
			}
		}
		if (m_streaminfo.getStructureEntryNext(offset, longdata, direction) != 0)
			return -1;
	}
	off_t start = offset;

	/* calculate length of I-frame -> search next frame -> length = offset - start */
	unsigned int data;
	int count_passes = 0;
	do
	{
		if (m_streaminfo.getStructureEntryNext(offset, longdata, 1))
		{
			eDebug("[eDVBTSTools] findFrame get next failed");
			return -1;
		}
		data = ((unsigned int)longdata);
		count_passes++;
	}
	while (((data & 0xff) != 0x09) && ((data & 0xff) != 0x00) && ((data & 0x7E) != 0x46)); /* next frame */

	if (is_mpeg2)
	{
// First we have to get back to where we were when we set start!
// getStructureEntryNext() has a private variable to remember where it was at
// the end of the last call, and getStructureEntryFirst() sets it.
		if (m_streaminfo.getStructureEntryFirst(start, longdata) != 0)
		{
			eDebug("[eDVBTSTools] findFrame getStructureEntryFirst for is_mpeg2 failed");
			return -1;
                }
		// Seek back to sequence start (appears to be needed for e.g. a few TCM streams)
		// length calculation changes m_streaminfo -> reset it to start offset
		while (count_passes)
		{
			off_t dummy;
			if (m_streaminfo.getStructureEntryNext(dummy, longdata, -1))
			{
				eDebug("[eDVBTSTools] findFrame get previous frame failed");
				return -1;
			}
			count_passes--;
		}
		// In case of fast forward seek back max to start offset
		// In case of rewind there is no limit
		if (direction < 0)
			nr_frames *= -1;
		while (nr_frames)
		{
			if (m_streaminfo.getStructureEntryNext(start, longdata, -1))
			{
				eDebug("[eDVBTSTools] findFrame Failed to find MPEG2 start frame");
				break;
			}
			if ((((unsigned int)longdata) & 0xFF) == 0xB3) /* sequence start or previous frame */
				break;
			if ((((unsigned int)longdata) & 0xFF) == 0x00) /* see above count only 0x00 frames */
				--nr_frames;
		}
		if (direction < 0)
			nr_frames *= -1;
	}

	/* make sure we've ended up in the right direction, ignore the result if we didn't */
	if ((direction >= 0 && start <= _offset) || (direction < 0 && start >= _offset)) return -1;

	len = offset - start;
	_offset = start;
	if (direction < 0)
		direction = -nr_frames;
	else
		direction = nr_frames;
//	eDebug("[eDVBTSTools] findFrame result: offset=%lld, len: %ld", offset, (int)len);
	return 0;
}

int eDVBTSTools::findNextPicture(off_t &offset, size_t &len, int &distance, int frame_types)
{
	int nr_frames, direction;
//	eDebug("[eDVBTSTools] findNextPicture trying to move %d frames at %lld", distance, offset);

	frame_types = frametypeI; /* TODO: intelligent "allow IP frames when not crossing an I-Frame */

	off_t new_offset = offset;
	size_t new_len = len;
	int first = 1;

	if (distance > 0) {
		direction = 0;
                nr_frames = 0;
        } else {
		direction = -1;
                nr_frames = -1;
		distance = -distance+1;
        }
	while (distance > 0)
	{
// Save this for possible reset and 1-frame change retry.
		off_t loop_start_frame = new_offset/m_packet_size;

		int dir = direction;
		if (findFrame(new_offset, new_len, dir, frame_types))
		{
//			eDebug("[eDVBTSTools] findNextPicture findFrame failed!\n");
			return -1;
		}

// Check that we are moving in the right direction.
// If not, try again with a 1 frame change
// All done before we change distance...
		int retry_frame_offset = 0;
		off_t new_frame = new_offset/m_packet_size;
		if (direction < 0)
		{
			if (loop_start_frame <= new_frame)
			{
				retry_frame_offset = -1;
			}
		}
		else
		{
			if (loop_start_frame >= new_frame)
			{
				retry_frame_offset = 1;
			}
		}
		if (retry_frame_offset != 0)
		{
			new_offset = (loop_start_frame + retry_frame_offset)*m_packet_size;
			continue;
		}

		distance -= abs(dir);

//		eDebug("[eDVBTSTools] findNextPicture we moved %d, %d to go frames (now at %lld)", dir, distance, new_offset);

		if (distance >= 0 || direction == 0)
		{
			first = 0;
			offset = new_offset;
			len = new_len;
			nr_frames += abs(dir);
		}
		else if (first)
		{
			first = 0;
			offset = new_offset;
			len = new_len;
			nr_frames += abs(dir) + distance; // never jump forward during rewind
		}

		if (direction == 0)
			new_offset += new_len;
	}

	distance = (direction < 0) ? -nr_frames : nr_frames;
//	eDebug("[eDVBTSTools] findNextPicture in total, we moved %d frames", nr_frames);

	return 0;
}

void eDVBTSTools::PMTready(int error)
{
	if (!error)
	{
		if (getProgramInfo(m_program) >= 0)
		{
			m_PMT.stop();
			m_pmtready = true;
		}
	}
}
