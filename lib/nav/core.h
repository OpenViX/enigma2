#ifndef __nav_core_h
#define __nav_core_h

#include <lib/base/object.h>
#include <lib/service/iservice.h>
#include <connection.h>
#include <map>
#include <set>
#include <lib/dvb/fcc.h>

class eNavigation: public iObject, public sigc::trackable
{
	static eNavigation *instance;
	DECLARE_REF(eNavigation);
	int m_decoder;
	ePtr<iServiceHandler> m_servicehandler;

	ePtr<iPlayableService> m_runningService;
	sigc::signal<void(int)> m_event;
	ePtr<eConnection> m_service_event_conn;
	void serviceEvent(iPlayableService* service, int event);

	std::map<ePtr<iRecordableService>, ePtr<eConnection>, std::less<iRecordableService*> > m_recordings;
	std::map<ePtr<iRecordableService>, eServiceReference, std::less<iRecordableService*> > m_recordings_services;
	std::set<ePtr<iRecordableService>, std::less<iRecordableService*> > m_simulate_recordings;

	sigc::signal<void(ePtr<iRecordableService>,int)> m_record_event;
	void recordEvent(iRecordableService* service, int event);

	friend class eFCCServiceManager;
	ePtr<eFCCServiceManager> m_fccmgr;
public:

	RESULT playService(const eServiceReference &service);
	RESULT connectEvent(const sigc::slot<void(int)> &event, ePtr<eConnection> &connection);
	RESULT connectRecordEvent(const sigc::slot<void(ePtr<iRecordableService>,int)> &event, ePtr<eConnection> &connection);
/*	int connectServiceEvent(const sigc::slot<void(iPlayableService*,int> &event, ePtr<eConnection)> &connection); */
	RESULT getCurrentService(ePtr<iPlayableService> &service);
	RESULT stopService(void);

	RESULT recordService(const eServiceReference &ref, ePtr<iRecordableService> &service, bool simulate=false);
	RESULT stopRecordService(ePtr<iRecordableService> &service);
	void getRecordings(std::vector<ePtr<iRecordableService> > &recordings, bool simulate=false);
	std::map<ePtr<iRecordableService>, eServiceReference, std::less<iRecordableService*> > getRecordingsServices() { return m_recordings_services; }

	RESULT pause(int p);
	eNavigation(iServiceHandler *serviceHandler, int decoder = 0);
	static eNavigation *getInstance() { return instance; }
	virtual ~eNavigation();
};

#endif
