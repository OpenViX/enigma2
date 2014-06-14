/* DVB CI Transport Connection */

#include <lib/base/eerror.h>
#include <lib/dvb_ci/dvbci_session.h>
#include <lib/dvb_ci/dvbci_resmgr.h>
#include <lib/dvb_ci/dvbci_appmgr.h>
#include <lib/dvb_ci/dvbci_camgr.h>
#include <lib/dvb_ci/dvbci_datetimemgr.h>
#include <lib/dvb_ci/dvbci_mmi.h>

DEFINE_REF(eDVBCISession);

ePtr<eDVBCISession> eDVBCISession::sessions[SLMS];

int eDVBCISession::buildLengthField(unsigned char *pkt, int len)
{
	if (len < 127)
	{
		*pkt++=len;
		return 1;
	} else if (len < 256)
	{
		*pkt++=0x81;
		*pkt++=len;
		return 2;
	} else if (len < 65535)
	{
		*pkt++=0x82;
		*pkt++=len>>8;
		*pkt++=len;
		return 3;
	} else
	{
		eDebug("too big length");
		exit(0);
	}
}

int eDVBCISession::parseLengthField(const unsigned char *pkt, int &len)
{
	len=0;
	if (!(*pkt&0x80))
	{
		len = *pkt;
		return 1;
	}
	for (int i=0; i<(pkt[0]&0x7F); ++i)
	{
		len <<= 8;
		len |= pkt[i + 1];
	}
	return (pkt[0] & 0x7F) + 1;
}

void eDVBCISession::sendAPDU(const unsigned char *tag, const void *data, int len)
{
	unsigned char pkt[len+3+4];
	int l;
	memcpy(pkt, tag, 3);
	l=buildLengthField(pkt+3, len);
	if (data)
		memcpy(pkt+3+l, data, len);
	sendSPDU(0x90, 0, 0, pkt, len+3+l);
}

void eDVBCISession::sendSPDU(unsigned char tag, const void *data, int len, const void *apdu, int alen)
{
	sendSPDU(slot, tag, data, len, session_nb, apdu, alen);
}

void eDVBCISession::sendSPDU(eDVBCISlot *slot, unsigned char tag, const void *data, int len, unsigned short session_nb, const void *apdu,int alen)
{
	unsigned char pkt[4096];
	unsigned char *ptr=pkt;
	*ptr++=tag;
	ptr+=buildLengthField(ptr, len+2);
	if (data)
		memcpy(ptr, data, len);
	ptr+=len;
	*ptr++=session_nb>>8;
	*ptr++=session_nb;

	if (apdu)
		memcpy(ptr, apdu, alen);

	ptr+=alen;
	slot->send(pkt, ptr - pkt);
}

void eDVBCISession::sendOpenSessionResponse(eDVBCISlot *slot, unsigned char session_status, const unsigned char *resource_identifier, unsigned short session_nb)
{
	char pkt[6];
	pkt[0]=session_status;
	eDebug("sendOpenSessionResponse");
	memcpy(pkt + 1, resource_identifier, 4);
	sendSPDU(slot, 0x92, pkt, 5, session_nb);
}

void eDVBCISession::recvCreateSessionResponse(const unsigned char *data)
{
	status = data[0];
	state = stateStarted;
	action = 1;
	eDebug("create Session Response, status %x", status);
}

void eDVBCISession::recvCloseSessionRequest(const unsigned char *data)
{
	state = stateInDeletion;
	action = 1;
	eDebug("close Session Request");
}

void eDVBCISession::deleteSessions(const eDVBCISlot *slot)
{
	ePtr<eDVBCISession> ptr;
	for (unsigned short session_nb=0; session_nb < SLMS; ++session_nb)
	{
		ptr = sessions[session_nb];
		if (ptr && ptr->slot == slot)
			sessions[session_nb]=0;
	}
}

void eDVBCISession::createSession(eDVBCISlot *slot, const unsigned char *resource_identifier, unsigned char &status, ePtr<eDVBCISession> &session)
{
	unsigned long tag;
	unsigned short session_nb;

	for (session_nb=1; session_nb < SLMS; ++session_nb)
		if (!sessions[session_nb-1])
			break;
	if (session_nb == SLMS)
	{
		status=0xF3;
		return;
	}

	tag = resource_identifier[0] << 24;
	tag|= resource_identifier[1] << 16;
	tag|= resource_identifier[2] << 8;
	tag|= resource_identifier[3];

	switch (tag)
	{
	case 0x00010041:
		session=new eDVBCIResourceManagerSession;
		eDebug("RESOURCE MANAGER");
		break;
	case 0x00020041:
		session=new eDVBCIApplicationManagerSession(slot);
		eDebug("APPLICATION MANAGER");
		break;
	case 0x00030041:
		session = new eDVBCICAManagerSession(slot);
		eDebug("CA MANAGER");
		break;
	case 0x00240041:
		session=new eDVBCIDateTimeSession;
		eDebug("DATE-TIME");
		break;
	case 0x00400041:
		session = new eDVBCIMMISession(slot);
		eDebug("MMI - create session");
		break;
	case 0x00100041:
//		session=new eDVBCIAuthSession;
		eDebug("AuthSession");
//		break;
	case 0x00200041:
	default:
		eDebug("unknown resource type %02x %02x %02x %02x", resource_identifier[0], resource_identifier[1], resource_identifier[2],resource_identifier[3]);
		session=0;
		status=0xF0;
	}

	if (!session)
	{
		eDebug("unknown session.. expect crash");
		return;
	}

	eDebug("new session nb %d %p", session_nb, &(*session));
	session->session_nb = session_nb;

	if (session)
	{
		sessions[session_nb - 1] = session;
		session->slot = slot;
		status = 0;
	}
	session->state = stateInCreation;
}

void eDVBCISession::handleClose()
{
	unsigned char data[1]={0x00};
	sendSPDU(0x96, data, 1, 0, 0);
}

int eDVBCISession::pollAll()
{
	for (int session_nb=1; session_nb < SLMS; ++session_nb)
		if (sessions[session_nb-1])
		{
			int r;

			if (sessions[session_nb-1]->state == stateInDeletion)
			{
				sessions[session_nb-1]->handleClose();
				sessions[session_nb-1]=0;
				r=1;
			} else
				r=sessions[session_nb-1]->poll();

			if (r)
				return 1;
		}
	return 0;
}

void eDVBCISession::receiveData(eDVBCISlot *slot, const unsigned char *ptr, size_t len)
{
	const unsigned char *pkt = (const unsigned char*)ptr;
	unsigned char tag = *pkt++;
	int llen, hlen;

	eDebug("slot: %p",slot);

	for(unsigned int i=0;i<len;i++)
		eDebugNoNewLine("%02x ",ptr[i]);
	eDebug("");

	llen = parseLengthField(pkt, hlen);
	pkt += llen;

	ePtr<eDVBCISession> session;

	if(tag == 0x91)
	{
		unsigned char status;
		createSession(slot, pkt, status, session);
		sendOpenSessionResponse(slot, status, pkt, session?session->session_nb:0);

		if (session)
		{
			session->state=stateStarted;
			session->action=1;
		}
	}
	else
	{
		unsigned session_nb;
		session_nb=pkt[hlen-2]<<8;
		session_nb|=pkt[hlen-1]&0xFF;

		if ((!session_nb) || (session_nb >= SLMS))
		{
			eDebug("PROTOCOL: illegal session number %x", session_nb);
#ifdef __sh__
			//Dagobert during start-up we seems to have some problems
			//on some modules which "looses" the connection. So reset it
			deleteSessions(slot);
			slot->reset();
#endif
			return;
		}

		session=sessions[session_nb-1];
		if (!session)
		{
			eDebug("PROTOCOL: data on closed session %x", session_nb);
			return;
		}

		switch (tag)
		{
		case 0x90:
			break;
		case 0x94:
			session->recvCreateSessionResponse(pkt);
			break;
		case 0x95:
			eDebug("recvCloseSessionRequest");
			session->recvCloseSessionRequest(pkt);
			break;
		default:
			eDebug("INTERNAL: nyi, tag %02x.", tag);
			return;
		}
	}

	hlen += llen + 1; // lengthfield and tag

	pkt = ((const unsigned char*)ptr) + hlen;
	len -= hlen;

	if (session)
		while (len > 0)
		{
			int alen;
			const unsigned char *tag=pkt;
			pkt+=3; // tag
			len-=3;
			hlen=parseLengthField(pkt, alen);
			pkt+=hlen;
			len-=hlen;

			//if (eDVBCIModule::getInstance()->workarounds_active & eDVBCIModule::workaroundMagicAPDULength)
			{
				if (((len-alen) > 0) && ((len - alen) < 3))
				{
					eDebug("WORKAROUND: applying work around MagicAPDULength");
					alen=len;
				}
			}
			if (session->receivedAPDU(tag, pkt, alen))
				session->action = 1;
			pkt+=alen;
			len-=alen;
		}

	if (len)
		eDebug("PROTOCOL: warning, TL-Data has invalid length");
}

eDVBCISession::~eDVBCISession()
{
//	eDebug("destroy %p", this);
}

