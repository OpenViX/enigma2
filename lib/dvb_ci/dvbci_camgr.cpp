/* DVB CI CA Manager */

#include <lib/base/eerror.h>
#include <lib/dvb_ci/dvbci_camgr.h>
#include <lib/dvb_ci/dvbci_ui.h>

eDVBCICAManagerSession::eDVBCICAManagerSession(eDVBCISlot *tslot)
{
	slot = tslot;
	slot->setCAManager(this);
}

eDVBCICAManagerSession::~eDVBCICAManagerSession()
{
	slot->setCAManager(NULL);
}

int eDVBCICAManagerSession::receivedAPDU(const unsigned char *tag, const void *data, int len)
{
	eTraceNoNewLine("[CI%d CA] SESSION(%d)/CA %02x %02x %02x: ", slot->getSlotID(), session_nb, tag[0], tag[1], tag[2]);
	for (int i=0; i<len; i++)
		eTraceNoNewLine("%02x ", ((const unsigned char*)data)[i]);
	eTraceNoNewLine("\n");

	if ((tag[0]==0x9f) && (tag[1]==0x80))
	{
		switch (tag[2])
		{
		case 0x31:
			eDebugNoNewLineStart("[CI%d CA]ca info:", slot->getSlotID());
			for (int i=0; i<len; i+=2)
			{
				eDebugNoNewLine("%04x ", (((const unsigned char*)data)[i]<<8)|(((const unsigned char*)data)[i+1]));
				caids.push_back((((const unsigned char*)data)[i]<<8)|(((const unsigned char*)data)[i+1]));
			}
			std::sort(caids.begin(), caids.end());
			eDebugNoNewLine("\n");
			eDVBCIInterfaces::getInstance()->executeRecheckPMTHandlersInMainloop();
			break;
		case 0x33: // ca_pmt_reply
		{
			const unsigned char *d = (const unsigned char*)data;
			if (len < 4)
				break;
			// CA_enable 0x01: descrambling possible; 0x02/0x03: only after dialogue; 0x71/0x73: not possible
			bool known = false, possible = false;
			if (d[3] & 0x80)
			{
				known = true;
				possible = (d[3] & 0x7f) == 0x01;
			}
			for (int i = 4; i + 3 <= len; i += 3)
			{
				if (d[i + 2] & 0x80)
				{
					known = true;
					if ((d[i + 2] & 0x7f) == 0x01)
						possible = true;
				}
			}
			eDebug("[CI%d CA] ca pmt reply program %04x: %s", slot->getSlotID(), (d[0] << 8) | d[1],
				!known ? "no CA enable info" : possible ? "descrambling possible" : "descrambling NOT possible");
			if (known)
			{
				slot->setCaDenied(!possible);
				/* emit */ eDVBCI_UI::getInstance()->m_messagepump.send(eDVBCIInterfaces::Message(eDVBCIInterfaces::Message::slotDecodingStateChanged, slot->getSlotID(), possible ? 2 : 1));
			}
			break;
		}
		default:
			eWarning("[CI%d CA] unknown APDU tag 9F 80 %02x", slot->getSlotID(), tag[2]);
			break;
		}
	}
	return 0;
}

int eDVBCICAManagerSession::doAction()
{
	switch (state)
	{
	case stateStarted:
	{
		const unsigned char tag[3]={0x9F, 0x80, 0x30}; // ca info enq
		sendAPDU(tag);
		state=stateFinal;
		return 0;
	}
	case stateFinal:
		eWarning("[CI%d CA] stateFinal and action should not happen", slot->getSlotID());
		[[fallthrough]];
	default:
		return 0;
	}
}

int eDVBCICAManagerSession::sendCAPMT(unsigned char *data, int len)
{
	const unsigned char tag[3]={0x9F, 0x80, 0x32}; // ca_pmt

	sendAPDU(tag, data, len);

	return 0;
}

