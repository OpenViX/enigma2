#include <lib/dvb_ci/dvbci_ui.h>
#include <lib/dvb_ci/dvbci.h>

#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>

#include <lib/base/init.h>
#include <lib/base/init_num.h>
#include <lib/base/eerror.h>
#include <lib/base/estring.h>

#define MAX_SLOTS 4

eDVBCI_UI *eDVBCI_UI::instance;

eDVBCI_UI::eDVBCI_UI()
	:eMMI_UI(MAX_SLOTS), m_messagepump(eApp,1, "dvb_ui")
{
	ASSERT(!instance);
	instance = this;
	CONNECT(m_messagepump.recv_msg, eDVBCI_UI::gotMessage);
}

eDVBCI_UI *eDVBCI_UI::getInstance()
{
	return instance;
}

void eDVBCI_UI::gotMessage(const eDVBCIInterfaces::Message &message)
{
	switch (message.m_type)
	{
		case eDVBCIInterfaces::Message::slotStateChanged:
			setState(message.m_slotid, message.m_state);
			break;
		case eDVBCIInterfaces::Message::slotDecodingStateChanged:
			setDecodingState(message.m_slotid, message.m_state);
			break;
		case eDVBCIInterfaces::Message::mmiSessionDestroyed:
			mmiSessionDestroyed(message.m_slotid);
			break;
		case eDVBCIInterfaces::Message::mmiDataReceived:
			processMMIData(message.m_slotid, message.m_tag, message.m_data, message.m_len);
			break;
		case eDVBCIInterfaces::Message::appNameChanged:
			setAppName(message.m_slotid, message.m_appName.c_str());
			break;
	}
}

void eDVBCI_UI::setInit(int slot)
{
	eDVBCIInterfaces::getInstance()->initialize(slot);
}

void eDVBCI_UI::setReset(int slot)
{
	eDVBCIInterfaces::getInstance()->reset(slot);
}

int eDVBCI_UI::startMMI(int slot)
{
	eDVBCIInterfaces::getInstance()->startMMI(slot);
	return 0;
}

int eDVBCI_UI::stopMMI(int slot)
{
	eDVBCIInterfaces::getInstance()->stopMMI(slot);
	return 0;
}

int eDVBCI_UI::answerMenu(int slot, int answer)
{
	eDVBCIInterfaces::getInstance()->answerText(slot, answer);
	return 0;
}

int eDVBCI_UI::answerEnq(int slot, char *value)
{
	eDVBCIInterfaces::getInstance()->answerEnq(slot, value);
	return 0;
}

int eDVBCI_UI::cancelEnq(int slot)
{
	eDVBCIInterfaces::getInstance()->cancelEnq(slot);
	return 0;
}

int eDVBCI_UI::getMMIState(int slot)
{
	return eDVBCIInterfaces::getInstance()->getMMIState(slot);
}

int eDVBCI_UI::setClockRate(int slot, const std::string &rate)
{
	return eDVBCIInterfaces::getInstance()->setCIClockRate(slot, rate);
}

int eDVBCI_UI::setEnabled(int slot, bool enabled)
{
	return eDVBCIInterfaces::getInstance()->setCIEnabled(slot, enabled);
}

//FIXME: correct "run/startlevel"
eAutoInitP0<eDVBCI_UI> init_dvbciui(eAutoInitNumbers::rc, "DVB-CI UI");
