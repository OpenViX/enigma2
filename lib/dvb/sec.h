#ifndef __dvb_sec_h
#define __dvb_sec_h

#include <lib/dvb/idvb.h>
#include <lib/dvb/fbc.h>

#include <list>

typedef enum
{
	SatCR_format_none = 0,
	SatCR_format_unicable = 1,
	SatCR_format_jess = 2
} SatCR_format_t;

#ifndef SWIG
class eSecCommand
{
public:
	enum { modeStatic, modeDynamic };
	enum {
		NONE, SLEEP, SET_VOLTAGE, SET_TONE, GOTO,
		SEND_DISEQC, SEND_TONEBURST, SET_FRONTEND,
		SET_TIMEOUT, IF_TIMEOUT_GOTO,
		IF_VOLTAGE_GOTO, IF_NOT_VOLTAGE_GOTO,
		SET_POWER_LIMITING_MODE,
		SET_ROTOR_DISEQC_RETRYS, IF_NO_MORE_ROTOR_DISEQC_RETRYS_GOTO,
		MEASURE_IDLE_INPUTPOWER, MEASURE_RUNNING_INPUTPOWER,
		IF_MEASURE_IDLE_WAS_NOT_OK_GOTO, IF_INPUTPOWER_DELTA_GOTO,
		UPDATE_CURRENT_ROTORPARAMS, INVALIDATE_CURRENT_ROTORPARMS,
		UPDATE_CURRENT_SWITCHPARMS, INVALIDATE_CURRENT_SWITCHPARMS,
		IF_ROTORPOS_VALID_GOTO,
		IF_TUNER_LOCKED_GOTO,
		IF_LOCK_TIMEOUT_GOTO,
		IF_TONE_GOTO, IF_NOT_TONE_GOTO,
		START_TUNE_TIMEOUT,
		SET_ROTOR_MOVING,
		SET_ROTOR_STOPPED,
		DELAYED_CLOSE_FRONTEND
	};
	int cmd;
	struct rotor
	{
		union {
			int deltaA;   // difference in mA between running and stopped rotor
			int lastSignal;
		};
		int okcount;  // counter
		int steps;    // goto steps
		int direction;
	};
	struct pair
	{
		union
		{
			int voltage;
			int tone;
			int val;
		};
		int steps;
	};
	union
	{
		int val;
		int steps;
		int timeout;
		int voltage;
		int tone;
		int toneburst;
		int msec;
		int mode;
		rotor measure;
		eDVBDiseqcCommand diseqc;
		pair compare;
	};
	eSecCommand( int cmd )
		:cmd(cmd)
	{}
	eSecCommand( int cmd, int val )
		:cmd(cmd), val(val)
	{}
	eSecCommand( int cmd, eDVBDiseqcCommand diseqc )
		:cmd(cmd), diseqc(diseqc)
	{}
	eSecCommand( int cmd, rotor measure )
		:cmd(cmd), measure(measure)
	{}
	eSecCommand( int cmd, pair compare )
		:cmd(cmd), compare(compare)
	{}
	eSecCommand()
		:cmd(NONE)
	{}
};

class eSecCommandList
{
	typedef std::list<eSecCommand> List;
	List secSequence;
public:
	typedef List::iterator iterator;
private:
	iterator cur;
public:
	eSecCommandList()
		:cur(secSequence.end())
	{
	}
	void push_front(const eSecCommand &cmd)
	{
		secSequence.push_front(cmd);
	}
	void push_back(const eSecCommand &cmd)
	{
		secSequence.push_back(cmd);
	}
	void push_back(eSecCommandList &list)
	{
		secSequence.insert(end(), list.begin(), list.end());
	}
	void clear()
	{
		secSequence.clear();
		cur=secSequence.end();
	}
	inline iterator &current()
	{
		return cur;
	}
	inline iterator begin()
	{
		return secSequence.begin();
	}
	inline iterator end()
	{
		return secSequence.end();
	}
	int size() const
	{
		return secSequence.size();
	}
	operator bool() const
	{
		return secSequence.size();
	}
	eSecCommandList &operator=(const eSecCommandList &lst)
	{
		secSequence = lst.secSequence;
		cur = begin();
		return *this;
	}
};
#endif

class eDVBSatelliteDiseqcParameters
{
#ifdef SWIG
	eDVBSatelliteDiseqcParameters();
	~eDVBSatelliteDiseqcParameters();
#endif
public:
	enum { AA=0, AB=1, BA=2, BB=3, SENDNO=4 /* and 0xF0 .. 0xFF*/  };	// DiSEqC Parameter
	enum t_diseqc_mode { NONE=0, V1_0=1, V1_1=2, V1_2=3, SMATV=4 };	// DiSEqC Mode
	enum t_toneburst_param { NO=0, A=1, B=2 };
#ifndef SWIG
	uint8_t m_committed_cmd;
	t_diseqc_mode m_diseqc_mode;
	t_toneburst_param m_toneburst_param;

	uint8_t m_repeats;	// for cascaded switches
	bool m_use_fast;	// send no DiSEqC on H/V or Lo/Hi change
	bool m_seq_repeat;	// send the complete DiSEqC Sequence twice...
	uint8_t m_command_order;
	/* 	diseqc 1.0)
			0) commited, toneburst
			1) toneburst, committed
		diseqc > 1.0)
			2) committed, uncommitted, toneburst
			3) toneburst, committed, uncommitted
			4) uncommitted, committed, toneburst
			5) toneburst, uncommitted, committed */
	uint8_t m_uncommitted_cmd;	// state of the 4 uncommitted switches..
#endif
};

class eDVBSatelliteSwitchParameters
{
#ifdef SWIG
	eDVBSatelliteSwitchParameters();
	~eDVBSatelliteSwitchParameters();
#endif
public:
	enum t_22khz_signal {	HILO=0, ON=1, OFF=2	}; // 22 Khz
	enum t_voltage_mode	{	HV=0, _14V=1, _18V=2, _0V=3, HV_13=4 }; // 14/18 V
#ifndef SWIG
	t_voltage_mode m_voltage_mode;
	t_22khz_signal m_22khz_signal;
	uint8_t m_rotorPosNum; // 0 is disable.. then use gotoxx
#endif
};

class eDVBSatelliteRotorParameters
{
#ifdef SWIG
	eDVBSatelliteRotorParameters();
	~eDVBSatelliteRotorParameters();
#endif
public:
	enum { NORTH, SOUTH, EAST, WEST };
	enum { FAST, SLOW };
#ifndef SWIG
	eDVBSatelliteRotorParameters() { setDefaultOptions(); }

	struct eDVBSatelliteRotorInputpowerParameters
	{
		bool m_use;	// can we use rotor inputpower to detect rotor running state ?
		uint8_t m_delta;	// delta between running and stopped rotor
		unsigned int m_turning_speed; // SLOW, FAST, or fast turning epoch
	};
	eDVBSatelliteRotorInputpowerParameters m_inputpower_parameters;

	struct eDVBSatelliteRotorGotoxxParameters
	{
		uint8_t m_lo_direction;	// EAST, WEST
		uint8_t m_la_direction;	// NORT, SOUTH
		double m_longitude;	// longitude for gotoXX? function
		double m_latitude;	// latitude for gotoXX? function
	};
	eDVBSatelliteRotorGotoxxParameters m_gotoxx_parameters;

	void setDefaultOptions() // set default rotor options
	{
		m_inputpower_parameters.m_turning_speed = FAST; // fast turning
		m_inputpower_parameters.m_use = true;
		m_inputpower_parameters.m_delta = 60;
		m_gotoxx_parameters.m_lo_direction = EAST;
		m_gotoxx_parameters.m_la_direction = NORTH;
		m_gotoxx_parameters.m_longitude = 0.0;
		m_gotoxx_parameters.m_latitude = 0.0;
	}
#endif
};

class eDVBSatelliteLNBParameters
{
	public:
		eDVBSatelliteLNBParameters()
		{
			SatCR_format = SatCR_format_none;
#ifndef SWIG
			m_12V_relais_state = OFF;
			m_lof_hi = m_lof_lo = m_lof_threshold = LNBNum = 0;
			m_increased_voltage = false;
			m_prio = -1;
			m_advanced_satposdepends = -1;
#endif
		}
#ifdef SWIG
		~eDVBSatelliteLNBParameters();
#endif
	enum t_12V_relais_state { OFF=0, ON };
#ifndef SWIG
	t_12V_relais_state m_12V_relais_state;	// 12V relais output on/off

	int m_slot_mask; // useable by slot ( 1 | 2 | 4...)

	unsigned int m_lof_hi,	// for 2 band universal lnb 10600 Mhz (high band offset frequency)
				m_lof_lo,	// for 2 band universal lnb  9750 Mhz (low band offset frequency)
				m_lof_threshold;	// for 2 band universal lnb 11750 Mhz (band switch frequency)

	bool m_increased_voltage; // use increased voltage ( 14/18V )

	std::map<int, eDVBSatelliteSwitchParameters> m_satellites;
	eDVBSatelliteDiseqcParameters m_diseqc_parameters;
	eDVBSatelliteRotorParameters m_rotor_parameters;

	int m_prio; // to override automatic tuner management ... -1 is Auto
	int LNBNum;
	int m_advanced_satposdepends;
#endif
public:
#define guard_offset_min -8000
#define guard_offset_max 8000
#define guard_offset_step 8000
#define MAX_SATCR 32
#define MAX_FIXED_LNB_POSITIONS 64
#define MAX_MOVABLE_LNBS 7
#define MAX_LNBNUM (MAX_FIXED_LNB_POSITIONS + MAX_MOVABLE_LNBS)

	SatCR_format_t SatCR_format;
	int SatCR_positions;
	int SatCR_position;
	int SatCR_idx;
	unsigned int SatCRvco;
	unsigned int UnicableTuningWord;
	unsigned int UnicableConfigWord;
	int old_frequency;
	int old_polarisation;
	int old_orbital_position;
	int guard_offset_old;
	int guard_offset;
	int boot_up_time = 0;
};

class eDVBRegisteredFrontend;

class eDVBSatelliteEquipmentControl: public iDVBSatelliteEquipmentControl
{
	DECLARE_REF(eDVBSatelliteEquipmentControl);
public:
	enum {
		DELAY_AFTER_CONT_TONE_DISABLE_BEFORE_DISEQC=0,  // delay after continuous tone disable before diseqc command
		DELAY_AFTER_FINAL_CONT_TONE_CHANGE, // delay after continuous tone change before tune
		DELAY_AFTER_FINAL_VOLTAGE_CHANGE, // delay after voltage change at end of complete sequence
		DELAY_BETWEEN_DISEQC_REPEATS, // delay between repeated diseqc commands
		DELAY_AFTER_LAST_DISEQC_CMD, // delay after last diseqc command
		DELAY_AFTER_TONEBURST, // delay after toneburst
		DELAY_AFTER_ENABLE_VOLTAGE_BEFORE_SWITCH_CMDS, // delay after enable voltage before transmit toneburst/diseqc
		DELAY_BETWEEN_SWITCH_AND_MOTOR_CMD, // delay after transmit toneburst / diseqc and before transmit motor command
		DELAY_AFTER_VOLTAGE_CHANGE_BEFORE_MEASURE_IDLE_INPUTPOWER, // delay after voltage change before measure idle input power
		DELAY_AFTER_ENABLE_VOLTAGE_BEFORE_MOTOR_CMD, // delay after enable voltage before transmit motor command
		DELAY_AFTER_MOTOR_STOP_CMD, // delay after transmit motor stop
		DELAY_AFTER_VOLTAGE_CHANGE_BEFORE_MOTOR_CMD, // delay after voltage change before transmit motor command
		DELAY_BEFORE_SEQUENCE_REPEAT, // delay before the complete sequence is repeated (when enabled)
		MOTOR_COMMAND_RETRIES, // max transmit tries of rotor command when the rotor dont start turning (with power measurement)
		MOTOR_RUNNING_TIMEOUT, // max motor running time before timeout
		DELAY_AFTER_VOLTAGE_CHANGE_BEFORE_SWITCH_CMDS, // delay after change voltage before transmit toneburst/diseqc
		DELAY_AFTER_DISEQC_RESET_CMD,
		DELAY_AFTER_DISEQC_PERIPHERIAL_POWERON_CMD,
		UNICABLE_DELAY_AFTER_ENABLE_VOLTAGE_BEFORE_SWITCH_CMDS,
		UNICABLE_DELAY_AFTER_VOLTAGE_CHANGE_BEFORE_SWITCH_CMDS,
		UNICABLE_DELAY_AFTER_LAST_DISEQC_CMD,
		MAX_PARAMS
	};
private:
#ifndef SWIG
	static eDVBSatelliteEquipmentControl *instance;
	std::vector<eDVBSatelliteLNBParameters> m_lnbs;
	int m_lnbidx; // current index for set parameters
	std::map<int, eDVBSatelliteSwitchParameters>::iterator m_curSat;
	eSmartPtrList<eDVBRegisteredFrontend> &m_avail_frontends, &m_avail_simulate_frontends;
	int m_rotorMoving;
	int m_not_linked_slot_mask;
	int m_target_orbital_position;
	bool m_canMeasureInputPower;
#endif
#ifdef SWIG
	eDVBSatelliteEquipmentControl();
	~eDVBSatelliteEquipmentControl();
#endif
	static int m_params[MAX_PARAMS];
public:
#ifndef SWIG
	eDVBSatelliteEquipmentControl(eSmartPtrList<eDVBRegisteredFrontend> &avail_frontends, eSmartPtrList<eDVBRegisteredFrontend> &avail_simulate_frontends);
	RESULT prepare(iDVBFrontend &frontend, const eDVBFrontendParametersSatellite &sat, int &frequency, int frontend_id, unsigned int tunetimeout);
	void prepareTurnOffSatCR(iDVBFrontend &frontend);
	int canTune(const eDVBFrontendParametersSatellite &feparm, iDVBFrontend *, int frontend_id, int *highest_score_lnb=0);
	bool currentLNBValid() { return m_lnbidx > -1 && static_cast<unsigned int>(m_lnbidx) < m_lnbs.size(); }
#endif
	static eDVBSatelliteEquipmentControl *getInstance() { return instance; }
	static void setParam(int param, int value);
	RESULT clear();
/* LNB Specific Parameters */
	RESULT addLNB();
	RESULT setLNBSlotMask(int slotmask);
	RESULT setLNBLOFL(int lofl);
	RESULT setLNBLOFH(int lofh);
	RESULT setLNBThreshold(int threshold);
	RESULT setLNBIncreasedVoltage(bool onoff);
	RESULT setLNBPrio(int prio);
	RESULT setLNBNum(int lnbnum);
	RESULT setLNBsatposdepends(int advanced_satposdepends);
	RESULT getMaxFixedLnbPositions() {return MAX_FIXED_LNB_POSITIONS;}
	RESULT getMaxLnbNum() {return MAX_LNBNUM;}
/* DiSEqC Specific Parameters */
	RESULT setDiSEqCMode(int diseqcmode);
	RESULT setToneburst(int toneburst);
	RESULT setRepeats(int repeats);
	RESULT setCommittedCommand(int command);
	RESULT setUncommittedCommand(int command);
	RESULT setCommandOrder(int order);
	RESULT setFastDiSEqC(bool onoff);
	RESULT setSeqRepeat(bool onoff); // send the complete switch sequence twice (without rotor command)
/* Rotor Specific Parameters */
	RESULT setLongitude(float longitude);
	RESULT setLatitude(float latitude);
	RESULT setLoDirection(int direction);
	RESULT setLaDirection(int direction);
	RESULT setUseInputpower(bool onoff);
	RESULT setInputpowerDelta(int delta);  // delta between running and stopped rotor
	RESULT setRotorTurningSpeed(int speed);  // set turning speed..
/* Unicable Specific Parameters */
	RESULT setLNBSatCR(int SatCR_idx);
	RESULT setLNBSatCRvco(int SatCRvco);
	RESULT setLNBSatCRpositions(int SatCR_positions);
	RESULT setLNBSatCRformat(SatCR_format_t SatCR_format);
	RESULT setLNBSatCRPositionNumber(unsigned int position_number);
	RESULT setLNBBootupTime(int BootUpTime);
	RESULT getLNBSatCR();
	RESULT getLNBSatCRvco();
	RESULT getLNBSatCRpositions();
	RESULT getLNBSatCRformat();
	RESULT getLNBSatCRPositionNumber();
/* Satellite Specific Parameters */
	RESULT addSatellite(int orbital_position);
	RESULT setVoltageMode(int mode);
	RESULT setToneMode(int mode);
	RESULT setRotorPosNum(int rotor_pos_num);
/* Tuner Specific Parameters */
	RESULT setTunerLinked(int from, int to);
	RESULT setTunerDepends(int from, int to);
	RESULT resetAdvancedsatposdependsRoot(int link);
	int getRotorAdvancedsatposdependsPosition(int advanced_satposdepends);
	bool setAdvancedsatposdependsRoot(int advanced_satposdepends);
	void setSlotNotLinked(int tuner_no);
	void setRotorMoving(int, bool); // called from the frontend's
	bool isRotorMoving();
	bool canMeasureInputPower() { return m_canMeasureInputPower; }
	int getTargetOrbitalPosition() { return m_target_orbital_position; }
	bool isOrbitalPositionConfigured(int orbital_position);

	friend class eFBCTunerManager;
};

#endif
