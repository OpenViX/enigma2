from __future__ import absolute_import

from enigma import iPlayableService

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

	def serviceEvent(self, event):
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
			return NavigationInstance.instance.getCurrentlyPlayingServiceOrGroup()
		return None

	serviceref = property(getCurrentServiceRef)

	def destroy(self):
		PerServiceBase.destroy(self)
		Source.destroy(self)
