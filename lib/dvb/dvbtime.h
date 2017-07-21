#ifndef __LIB_DVB_DVBTIME_H_
#define __LIB_DVB_DVBTIME_H_

#ifndef SWIG

#include <lib/base/eerror.h>
#include <lib/dvb/esection.h>
#include <lib/dvb/atsc.h>
#include <dvbsi++/time_date_section.h>

class eDVBChannel;

inline int fromBCD(int bcd)
{
	if ((bcd&0xF0)>=0xA0)
		return -1;
	if ((bcd&0xF)>=0xA)
		return -1;
	return ((bcd&0xF0)>>4)*10+(bcd&0xF);
}

inline int toBCD(int dec)
{
	if (dec >= 100)
		return -1;
	return int(dec/10)*0x10 + dec%10;
}

time_t parseDVBtime(uint16_t mjd, uint32_t stime_bcd);
time_t parseDVBtime(const uint8_t* data);
time_t parseDVBtime(const uint8_t* data, uint16_t *hash);

class TimeTable : public eGTable
{
protected:
	eDVBChannel *chan;
	ePtr<iDVBDemux> demux;
	ePtr<eTimer> m_interval_timer;
	void ready(int);
	int update_count;
public:
	TimeTable(eDVBChannel *chan, int update_count=0);
	void startTable(eDVBTableSpec spec);
	void startTimer(int interval);
	int getUpdateCount() { return update_count; }
	virtual void start() = 0;
};

class TDT: public TimeTable
{
	int createTable(unsigned int nr, const __u8 *data, unsigned int max);
public:
	TDT(eDVBChannel *chan, int update_count=0);
	void start();
};

class STT: public TimeTable
{
	int createTable(unsigned int nr, const __u8 *data, unsigned int max);
public:
	STT(eDVBChannel *chan, int update_count=0);
	void start();
};

#endif  // SWIG

class eDVBLocalTimeHandler: public sigc::trackable
{
	DECLARE_REF(eDVBLocalTimeHandler);
	struct channel_data
	{
		ePtr<TimeTable> timetable;
		ePtr<eDVBChannel> channel;
		ePtr<eConnection> m_stateChangedConn;
		int m_prevChannelState;
	};
	bool m_use_dvb_time;
	ePtr<eTimer> m_updateNonTunedTimer;
	friend class TDT;
	friend class STT;
	friend class TimeTable;
	std::map<iDVBChannel*, channel_data> m_knownChannels;
	std::map<eDVBChannelID,int> m_timeOffsetMap;
	ePtr<eConnection> m_chanAddedConn;
	bool m_time_ready;
	int m_time_difference;
	int m_last_tp_time_difference;
	void DVBChannelAdded(eDVBChannel*);
	void DVBChannelStateChanged(iDVBChannel*);
	void readTimeOffsetData(const char*);
	void writeTimeOffsetData(const char*);
	void updateTime(time_t tp_time, eDVBChannel*, int updateCount);
	void updateNonTuned();
	static eDVBLocalTimeHandler *instance;
#ifdef SWIG
	eDVBLocalTimeHandler();
	~eDVBLocalTimeHandler();
#endif
public:
#ifndef SWIG
	eDVBLocalTimeHandler();
	~eDVBLocalTimeHandler();
#endif
	// 1.1.2004 - system time can be assumed to be OK if >= timeOK
	static const time_t timeOK = 1072915200;

	bool getUseDVBTime() { return m_use_dvb_time; }
	void setUseDVBTime(bool b);
	void syncDVBTime();
	PSignal0<void> m_timeUpdated;
	time_t nowTime() const { return m_time_ready ? ::time(0)+m_time_difference : -1; }
	bool ready() const { return m_time_ready; }
	static eDVBLocalTimeHandler *getInstance() { return instance; }
};

#endif // __LIB_DVB_DVBTIME_H_
