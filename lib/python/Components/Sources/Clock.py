from time import time as getTime

from enigma import eTimer

import Components.ClockRealtimeMonitor

from Components.Element import cached
from Components.Sources.Source import Source


class Clock(Source):
	def __init__(self):
		Source.__init__(self)
		self.clock_timer = eTimer()
		self.clock_timer.callback.append(self.poll)
		self.clock_timer.startEpochAligned(1000)
		Components.ClockRealtimeMonitor.realtimeMonitor.addRealtimeChangedCallback(self._timeUpdated)

	@cached
	def getClock(self):
		return getTime()

	time = property(getClock)

	def poll(self):
		print("[Clock] poll")  # temporary debug
		self.changed((self.CHANGED_POLL,))

	def _timeUpdated(self):
		# Re-align after CLOCK_REALTIME discontinuity.
		self.clock_timer.startEpochAligned(1000)
		self.poll()

	def doSuspend(self, suspended):
		if suspended:
			self.clock_timer.stop()
		else:
			self.clock_timer.startEpochAligned(1000)
			self.poll()

	def destroy(self):
		Components.ClockRealtimeMonitor.realtimeMonitor.removeRealtimeChangedCallback(self._timeUpdated)
		self.clock_timer.callback.remove(self.poll)
		Source.destroy(self)
