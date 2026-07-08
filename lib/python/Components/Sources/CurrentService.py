from enigma import iPlayableService, eServiceCenter

from Components.Element import cached
from Components.PerServiceDisplay import PerServiceBase
from Components.Sources.Source import Source
import NavigationInstance


class CurrentService(PerServiceBase, Source):
	def __init__(self, navcore):
		Source.__init__(self)
		PerServiceBase.__init__(self, navcore,
			{
				iPlayableService.evStart: self.serviceEvent,
				iPlayableService.evEnd: self.serviceEvent,
				# FIXME: we should check 'interesting_events'
				# which is not always provided.
				iPlayableService.evUpdatedInfo: self.serviceEvent,
				iPlayableService.evUpdatedEventInfo: self.serviceEvent,
				iPlayableService.evNewProgramInfo: self.serviceEvent,
				iPlayableService.evCuesheetChanged: self.serviceEvent,
				iPlayableService.evVideoSizeChanged: self.serviceEvent,
				iPlayableService.evHBBTVInfo: self.serviceEvent
			}, with_event=True)
		self.navcore = navcore
		self.info = None
		self.onManualNewService = []

	def serviceEvent(self, event):
		# pnav.stopService() fires evEnd and pnav.playService() fires evStart
		# synchronously, both before any repaint runs.  Preserve the info
		# pre-populated by newService() across that whole old→new transition so
		# converters (ServiceName etc.) can display the new service immediately.
		# Clear when real service data arrives via later events (evUpdatedInfo etc.).
		if not (getattr(self, 'info', None) is not None and event in (iPlayableService.evEnd, iPlayableService.evStart)):
			self.info = None
		self.changed((self.CHANGED_SPECIFIC, event))

	@cached
	def getCurrentService(self):
		return self.navcore.getCurrentService()

	def getCurrentServiceReference(self):
		return self.navcore.getCurrentlyPlayingServiceReference()

	service = property(getCurrentService)

	@cached
	def getCurrentServiceRef(self):
		if NavigationInstance.instance is not None:
			return NavigationInstance.instance.getCurrentServiceReferenceOriginal()
		return None

	serviceref = property(getCurrentServiceRef)

	def newService(self, ref, num=0):
		if ref and isinstance(ref, bool):
			self.info = None
		elif ref:
			self.info = eServiceCenter.getInstance().info(ref)
		else:
			self.info = None

		for x in self.onManualNewService:
			x()

		if num > 0 and (sref := self.serviceref):
			sref.setChannelNum(num)

		self.changed((self.CHANGED_SPECIFIC, iPlayableService.evStart))

	def destroy(self):
		PerServiceBase.destroy(self)
		Source.destroy(self)
