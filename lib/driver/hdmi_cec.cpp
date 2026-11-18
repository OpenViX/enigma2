#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <string.h>

#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/base/eerror.h>
#include <lib/base/ebase.h>
#include <lib/base/nconfig.h>
#include <lib/driver/input_fake.h>
#include <lib/driver/hdmi_cec.h>
#include <lib/driver/avswitch.h>
#define CEC_LOG_ADDR_TUNER_1		3
#define CEC_MAX_MSG_SIZE	16
#define CEC_VENDOR_ENIGMA2_STB          0x000934

static int hexValue(char value)
{
	if (value >= '0' && value <= '9')
		return value - '0';
	if (value >= 'A' && value <= 'F')
		return value - 'A' + 10;
	if (value >= 'a' && value <= 'f')
		return value - 'a' + 10;
	return -1;
}

eHdmiCEC *eHdmiCEC::instance = NULL;

DEFINE_REF(eHdmiCEC::eCECMessage);

eHdmiCEC::eCECMessage::eCECMessage(int addr, int cmd, char *data, int length)
{
	address = addr;
	command = cmd;
	dataLength = 0;
	memset(messageData, 0, sizeof(messageData));
	control0 = control1 = control2 = control3 = 0;

	if (length < 0)
		length = 0;
	if (length > (int)sizeof(messageData)) length = sizeof(messageData);
	if (length && data)
	{
		memcpy(messageData, data, length);
		if (length > 0) control0 = data[0];
		if (length > 1) control1 = data[1];
		if (length > 2) control2 = data[2];
		if (length > 3) control3 = data[3];
		dataLength = length;
	}
}

int eHdmiCEC::eCECMessage::getAddress()
{
	return address;
}

int eHdmiCEC::eCECMessage::getCommand()
{
	return command;
}

int eHdmiCEC::eCECMessage::getData(char *data, int length)
{
	if (!data || length <= 0)
		return 0;
	if (length > (int)dataLength) length = dataLength;
	memcpy(data, messageData, length);
	return length;
}

eHdmiCEC::eHdmiCEC()
: eRCDriver(eRCInput::getInstance())
{
	ASSERT(!instance);
	instance = this;
	hdmiFd = -1;
	fixedAddress = false;
	cecEnabled = false;
	physicalAddress[0] = 0x10;
	physicalAddress[1] = 0x00;
	logicalAddress = CEC_LOG_ADDR_TUNER_1;
	deviceType = CEC_LOG_ADDR_TUNER_1; /* default: tuner / set-top box */
}

void eHdmiCEC::initializeCEC()
{
#ifdef DREAMBOX
#define HDMIDEV "/dev/misc/hdmi_cec0"
#else
#define HDMIDEV "/dev/hdmi_cec"
#endif

	hdmiFd = ::open(HDMIDEV, O_RDWR | O_NONBLOCK | O_CLOEXEC);
	eTrace("[eHdmiCEC] ****** open HDMIDEV: %s hdmiFd: %d", HDMIDEV, hdmiFd);
	if (hdmiFd >= 0)
	{
#ifdef DREAMBOX
		unsigned int val = 0;
		::ioctl(hdmiFd, 4, &val);
#else
		::ioctl(hdmiFd, 0); /* flush old messages */
#endif
		eDebug("[eHdmiCEC] using legacy HDMI-CEC backend on %s", HDMIDEV);
		messageNotifier = eSocketNotifier::create(eApp, hdmiFd, eSocketNotifier::Read | eSocketNotifier::Priority);
		CONNECT(messageNotifier->activated, eHdmiCEC::hdmiEvent);
		getAddressInfo();
	}
	else
	{
		eTrace("[eHdmiCEC] cannot open %s: %m", HDMIDEV); /* Error - should not happen */
	}
}

eHdmiCEC::~eHdmiCEC()
{
	if (hdmiFd >= 0) ::close(hdmiFd);
	eTrace("[eHdmiCEC] *********>> close hdmiFD");	
}

eHdmiCEC *eHdmiCEC::getInstance()
{
	return instance;
}

void eHdmiCEC::reportPhysicalAddress()
{
	struct cec_message txmessage = {};
	memset(&txmessage, 0, sizeof(txmessage));
	txmessage.address = 0x0f; /* broadcast */
	txmessage.data[0] = 0x84; /* report address */
	txmessage.data[1] = physicalAddress[0];
	txmessage.data[2] = physicalAddress[1];
	txmessage.data[3] = deviceType;
	txmessage.length = 4;
	sendMessage(txmessage);
}

void eHdmiCEC::getAddressInfo()
{
	if (hdmiFd >= 0)
	{
		bool hasdata = false;
		struct addressinfo addressinfo = {};
		if (::ioctl(hdmiFd, 1, &addressinfo) >= 0)
		{
			hasdata = true;
#if DREAMBOX
			/* we do not get the device type, check the logical address to determine the type */
			switch (addressinfo.logical)
			{
			case 0x1:
			case 0x2:
			case 0x9:
				addressinfo.type = 1; /* recorder */
				break;
			case 0x3:
			case 0x6:
			case 0x7:
			case 0xa:
				addressinfo.type = 3; /* tuner */
				break;
			case 0x4:
			case 0x8:
			case 0xb:
				addressinfo.type = 4; /* playback */
				break;
			}
#endif
		}
		if (hasdata)
		{
			deviceType = addressinfo.type;
			logicalAddress = addressinfo.logical;
			if (!fixedAddress)
			{
				if (memcmp(physicalAddress, addressinfo.physical, sizeof(physicalAddress)))
				{
					eTrace("[eHdmiCEC] detected physical address change: %02X%02X --> %02X%02X", physicalAddress[0], physicalAddress[1], addressinfo.physical[0], addressinfo.physical[1]);
					memcpy(physicalAddress, addressinfo.physical, sizeof(physicalAddress));
					reportPhysicalAddress();
					/* emit */ addressChanged((physicalAddress[0] << 8) | physicalAddress[1]);
				}
			}
		}
	}
}

int eHdmiCEC::getLogicalAddress()
{
	return logicalAddress;
}

int eHdmiCEC::getPhysicalAddress()
{
	return (physicalAddress[0] << 8) | physicalAddress[1];
}

void eHdmiCEC::setFixedPhysicalAddress(int address)
{
	if (address)
	{
		fixedAddress = true;
		physicalAddress[0] = (address >> 8) & 0xff;
		physicalAddress[1] = address & 0xff;
		/* report our (possibly new) address */
		reportPhysicalAddress();
	}
	else
	{
		fixedAddress = false;
		/* get our current address */
		getAddressInfo();
	}
}

int eHdmiCEC::getDeviceType()
{
	return deviceType;
}

void eHdmiCEC::setEnabled(bool enabled)
{
	cecEnabled = enabled;
	if (cecEnabled && hdmiFd < 0)
		initializeCEC();
}

bool eHdmiCEC::getActiveStatus()
{
	bool active = true;
	eAVSwitch *avswitch = eAVSwitch::getInstance();
	if (avswitch) active = avswitch->isActive();
	return active;
}

void eHdmiCEC::hdmiEvent(int what)
{
	if (what & eSocketNotifier::Priority)
	{
		getAddressInfo();
	}

	if (what & eSocketNotifier::Read)
	{
		bool hasdata = false;
		struct cec_rx_message rxmessage;
#ifdef DREAMBOX
		if (::ioctl(hdmiFd, 2, &rxmessage) >= 0)
		{
			hasdata = true;
		}
		unsigned int val = 0;
		::ioctl(hdmiFd, 4, &val);
#else
		if (::read(hdmiFd, &rxmessage, 2) == 2)
		{
			if (::read(hdmiFd, &rxmessage.data, rxmessage.length) == rxmessage.length)
			{
				hasdata = true;
			}
		}
#endif
		bool hdmicec_enabled = eConfigManager::getConfigBoolValue("config.hdmicec.enabled", false);
		if (hasdata && hdmicec_enabled && rxmessage.length > 0)
		{
			bool keypressed = false;
			static unsigned char pressedkey = 0;
			if (rxmessage.data[0] != 0x87)
			{
				eTraceNoNewLineStart("[eHdmiCEC] received message");
				eTraceNoNewLine(" %02X", rxmessage.address);
				for (int i = 0; i < rxmessage.length; i++)
				{
					eTraceNoNewLine(" %02X", rxmessage.data[i]);
				}
				eTraceNoNewLine("\n");
				bool hdmicec_report_active_menu = eConfigManager::getConfigBoolValue("config.hdmicec.report_active_menu", false);
				if (hdmicec_report_active_menu)
				{
					switch (rxmessage.data[0])
					{
						case 0x44: /* key pressed */
							if (rxmessage.length < 2)
								break;
							keypressed = true;
							pressedkey = rxmessage.data[1];
							[[fallthrough]];
						case 0x45: /* key released */
						{
							long code = translateKey(pressedkey);
							if (keypressed) code |= 0x80000000;
							for (std::list<eRCDevice*>::iterator i(listeners.begin()); i != listeners.end(); ++i)
							{
								(*i)->handleCode(code);
							}
							break;
						}
					}
				}
			}
			int operandLength = rxmessage.length > 1 ? rxmessage.length - 1 : 0;
			ePtr<iCECMessage> msg = new eCECMessage(rxmessage.address, rxmessage.data[0], (char*)&rxmessage.data[1], operandLength);
			messageReceived(msg);
		}
	}
}

long eHdmiCEC::translateKey(unsigned char code)
{
	long key = 0;
	switch (code)
	{
		case 0x32:
			key = 0x8b;
			break;
		case 0x20:
			key = 0x0b;
			break;
		case 0x21:
			key = 0x02;
			break;
		case 0x22:
			key = 0x03;
			break;
		case 0x23:
			key = 0x04;
			break;
		case 0x24:
			key = 0x05;
			break;
		case 0x25:
			key = 0x06;
			break;
		case 0x26:
			key = 0x07;
			break;
		case 0x27:
			key = 0x08;
			break;
		case 0x28:
			key = 0x09;
			break;
		case 0x29:
			key = 0x0a;
			break;
		case 0x30:
			key = 0x192;
			break;
		case 0x31:
			key = 0x193;
			break;
		case 0x44:
			key = 0xcf;
			break;
		case 0x45:
			key = 0x80;
			break;
		case 0x46:
			key = 0x77;
			break;
		case 0x47:
			key = 0xa7;
			break;
		case 0x48:
			key = 0xa8;
			break;
		case 0x49:
			key = 0xd0;
			break;
		case 0x53:
			key = 0x16d;
			break;
		case 0x54:
			key = 0x16a;
			break;
		case 0x60:
			key = 0xcf;
			break;
		case 0x61:
			key = 0xa4;
			break;
		case 0x62:
			key = 0xa7;
			break;
		case 0x64:
			key = 0x80;
			break;
		case 0x00:
			key = 0x160;
			break;
		case 0x03:
			key = 0x69;
			break;
		case 0x04:
			key = 0x6a;
			break;
		case 0x01:
			key = 0x67;
			break;
		case 0x02:
			key = 0x6c;
			break;
		case 0x0d:
			key = 0xae;
			break;
		case 0x72:
			key = 0x18e;
			break;
		case 0x71:
			key = 0x191;
			break;
		case 0x73:
			key = 0x18f;
			break;
		case 0x74:
			key = 0x190;
			break;
		default:
			key = 0x8b;
			eTrace("eHdmiCEC: unknown code 0x%02X", (unsigned int)(code & 0xFF));
			break;
	}
	return key;
}

void eHdmiCEC::sendMessage(struct cec_message &message)
{
	if (hdmiFd >= 0)
	{
		eTraceNoNewLineStart("[eHdmiCEC] send message");
		eTraceNoNewLine(" %02X", message.address);
		for (int i = 0; i < message.length; i++)
		{
			eTraceNoNewLine(" %02X", message.data[i]);
		}
		eTraceNoNewLine("\n");
#ifdef DREAMBOX
		message.flag = 1;
		::ioctl(hdmiFd, 3, &message);
#else
		ssize_t ret = ::write(hdmiFd, &message, 2 + message.length);
		if (ret < 0) eTrace("[eHdmiCEC] write failed: %m");
#endif
	}
}

void eHdmiCEC::sendMessage(unsigned char address, unsigned char cmd, char *data, int length)
{
	struct cec_message message = {};
	if (length < 0 || !data)
		length = 0;
	/* CEC_MAX_MSG_SIZE includes the initiator/destination header byte. */
	if (length > CEC_MAX_MSG_SIZE - 2)
		length = CEC_MAX_MSG_SIZE - 2;
	message.address = address;
	if (length > (int)(sizeof(message.data) - 1)) length = sizeof(message.data) - 1;
	message.length = length + 1;
	message.data[0] = cmd;
	if (length)
		memcpy(&message.data[1], data, length);
	sendMessage(message);
}

void eHdmiCEC::sendMessageBytes(unsigned char address, unsigned char cmd, char *hexdata)
{
	struct cec_message message = {};
	message.address = address;
	message.length = 1;
	message.data[0] = cmd;

	if (hexdata)
	{
		int highNibble = -1;
		for (const char *item = hexdata; *item && message.length < CEC_MAX_MSG_SIZE - 1 && message.length < sizeof(message.data); ++item)
		{
			int nibble = hexValue(*item);
			if (nibble < 0)
				continue;
			if (highNibble < 0)
			{
				highNibble = nibble;
			}
			else
			{
				message.data[message.length++] = (highNibble << 4) | nibble;
				highNibble = -1;
			}
		}
	}

	sendMessage(message);
}

void eHdmiCECDevice::handleCode(long code)
{
	if (code & 0x80000000)
	{
		/*emit*/ input->keyPressed(eRCKey(this, code & 0xffff, 0));
	}
	else
	{
		/*emit*/ input->keyPressed(eRCKey(this, code & 0xffff, eRCKey::flagBreak));
	}
}

eHdmiCECDevice::eHdmiCECDevice(eRCDriver *driver)
 : eRCDevice("Hdmi-CEC", driver)
{
}

const char *eHdmiCECDevice::getDescription() const
{
	return "Hdmi-CEC device";
}

class eHdmiCECInit
{
	eHdmiCEC driver;
	eHdmiCECDevice device;

public:
	eHdmiCECInit(): driver(), device(&driver)
	{
	}
};

eAutoInitP0<eHdmiCECInit> init_hdmicec(eAutoInitNumbers::rc + 2, "Hdmi CEC driver");
