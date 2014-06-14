#include <lib/nav/pcore.h>
#include <lib/service/service.h>
#include <lib/service/event.h>
#include <lib/base/eerror.h>

DEFINE_REF(pNavigation);

pNavigation::pNavigation(int decoder)
{
	ePtr<iServiceHandler> service_center;
	eServiceCenter::getInstance(service_center);

	ASSERT(service_center);
	m_core = new eNavigation(service_center, decoder);

	m_core->connectEvent(slot(*this, &pNavigation::navEvent), m_nav_event_connection);
	m_core->connectRecordEvent(slot(*this, &pNavigation::navRecordEvent), m_nav_record_event_connection);
}

RESULT pNavigation::playService(const eServiceReference &service)
{
	return m_core->playService(service);
}

RESULT pNavigation::getCurrentService(ePtr<iPlayableService> &service)
{
	return m_core->getCurrentService(service);
}

RESULT pNavigation::pause(int p)
{
	return m_core->pause(p);
}

RESULT pNavigation::stopService()
{
	return m_core->stopService();
}

RESULT pNavigation::recordService(const eServiceReference &ref, ePtr<iRecordableService> &service, bool simulate)
{
	return m_core->recordService(ref, service, simulate);
}

RESULT pNavigation::stopRecordService(ePtr<iRecordableService> &service)
{
	return m_core->stopRecordService(service);
}

void pNavigation::getRecordings(std::vector<ePtr<iRecordableService> > &recordings, bool simulate)
{
	m_core->getRecordings(recordings, simulate);
}

void pNavigation::navEvent(int event)
{
		/* just relay the events here. */
	m_event(event);
}

void pNavigation::navRecordEvent(ePtr<iRecordableService> service, int event)
{
		/* just relay the events here. */
	m_record_event(service, event);
}
