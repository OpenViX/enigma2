from __future__ import absolute_import
from __future__ import division

from time import time

from enigma import eEPGCache

from Components.config import config
from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached, ElementError

class EventTime(Poll, Converter, object):
	STARTTIME = 0
	ENDTIME = 1
	REMAINING = 2
	REMAINING_VFD = 3
	PROGRESS = 4
	DURATION = 5
	ELAPSED = 6
	ELAPSED_VFD = 7
	NEXT_START_TIME = 8
	NEXT_END_TIME = 9
	NEXT_DURATION = 10
	THIRD_START_TIME = 11
	THIRD_END_TIME = 12
	THIRD_DURATION = 13
	TIMES = 14
	NEXT_TIMES = 15
	THIRD_TIMES = 16

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.epgcache = eEPGCache.getInstance()
		if type == "EndTime":
			self.type = self.ENDTIME
		elif type == "Remaining":
			self.type = self.REMAINING
			self.poll_interval = 60 * 1000
			self.poll_enabled = True
		elif type == "VFDRemaining":
			self.type = self.REMAINING_VFD
			self.poll_interval = 60 * 1000
			self.poll_enabled = True
		elif type == "StartTime":
			self.type = self.STARTTIME
		elif type == "Duration":
			self.type = self.DURATION
		elif type == "Progress":
			self.type = self.PROGRESS
			self.poll_interval = 30 * 1000
			self.poll_enabled = True
		elif type == "Elapsed":
			self.type = self.ELAPSED
			self.poll_interval = 60 * 1000
			self.poll_enabled = True
		elif type == "VFDElapsed":
			self.type = self.ELAPSED_VFD
			self.poll_interval = 60 * 1000
			self.poll_enabled = True
		elif type == "NextStartTime":
			self.type = self.NEXT_START_TIME
		elif type == "NextEndTime":
			self.type = self.NEXT_END_TIME
		elif type == "NextDuration":
			self.type = self.NEXT_DURATION
		elif type == "ThirdStartTime":
			self.type = self.THIRD_START_TIME
		elif type == "ThirdEndTime":
			self.type = self.THIRD_END_TIME
		elif type == "ThirdDuration":
			self.type = self.THIRD_DURATION
		elif type == "Times":
			self.type = self.TIMES
		elif type == "NextTimes":
			self.type = self.NEXT_TIMES
		elif type == "ThirdTimes":
			self.type = self.THIRD_TIMES
		else:
			raise ElementError("'%s' is not <StartTime|EndTime|Remaining|Elapsed|Duration|Progress|VFDRemaining|VFDElapsed|NextStartTime|NextEndTime|NextDuration|ThirdStartTime|ThirdEndTime|ThirdDuration|Times|NextTimes|ThirdTimes> for EventTime converter" % type)

	@cached
	def getTime(self):
		assert self.type != self.PROGRESS

		event = self.source.event
		if event is None:
			return None

		st = event.getBeginTime()
		if self.type == self.STARTTIME:
			return st

		duration = event.getDuration()
		if self.type == self.DURATION:
			return duration

		et = st + duration
		if self.type == self.ENDTIME:
			return et

		if self.type == self.TIMES:
			return (st, et)

		if self.type in (self.REMAINING, self.REMAINING_VFD, self.ELAPSED, self.ELAPSED_VFD):
			now = int(time())
			remaining = et - now
			if remaining < 0:
				remaining = 0
			start_time = event.getBeginTime()
			end_time = start_time + duration
			elapsed = now - start_time
			if start_time <= now <= end_time:
				if self.type == self.REMAINING and config.usage.swap_time_remaining_on_osd.value == "0":
					return duration, remaining
				elif self.type == self.REMAINING and config.usage.swap_time_remaining_on_osd.value == "1":
					return duration, elapsed
				elif self.type == self.REMAINING and config.usage.swap_time_remaining_on_osd.value == "2":
					return duration, elapsed, remaining
				elif self.type == self.REMAINING and config.usage.swap_time_remaining_on_osd.value == "3":
					return duration, remaining, elapsed
				elif self.type == self.ELAPSED and config.usage.swap_time_remaining_on_osd.value == "0":
					return duration, elapsed
				elif self.type == self.ELAPSED and config.usage.swap_time_remaining_on_osd.value == "1":
					return duration, remaining
				elif self.type == self.ELAPSED and config.usage.swap_time_remaining_on_osd.value == "2":
					return duration, elapsed, remaining
				elif self.type == self.ELAPSED and config.usage.swap_time_remaining_on_osd.value == "3":
					return duration, remaining, elapsed
				elif self.type == self.REMAINING_VFD and config.usage.swap_time_remaining_on_vfd.value == "0":
					return duration, remaining
				elif self.type == self.REMAINING_VFD and config.usage.swap_time_remaining_on_vfd.value == "1":
					return duration, elapsed
				elif self.type == self.REMAINING_VFD and config.usage.swap_time_remaining_on_vfd.value == "2":
					return duration, elapsed, remaining
				elif self.type == self.REMAINING_VFD and config.usage.swap_time_remaining_on_vfd.value == "3":
					return duration, remaining, elapsed
				elif self.type == self.ELAPSED_VFD and config.usage.swap_time_remaining_on_vfd.value == "0":
					return duration, elapsed
				elif self.type == self.ELAPSED_VFD and config.usage.swap_time_remaining_on_vfd.value == "1":
					return duration, remaining
				elif self.type == self.ELAPSED_VFD and config.usage.swap_time_remaining_on_vfd.value == "2":
					return duration, elapsed, remaining
				elif self.type == self.ELAPSED_VFD and config.usage.swap_time_remaining_on_vfd.value == "3":
					return duration, remaining, elapsed
			else:
				return duration, None

		elif self.type in (self.NEXT_START_TIME, self.NEXT_END_TIME, self.NEXT_DURATION, self.THIRD_START_TIME, self.THIRD_END_TIME, self.THIRD_DURATION, self.NEXT_TIMES, self.THIRD_TIMES):
			reference = self.source.service
			info = reference and self.source.info
			if info is None:
				return
			test = ['IBDCX', (reference.toString(), 1, -1, 1440)] # search next 24 hours
			self.list = [] if self.epgcache is None else self.epgcache.lookupEvent(test)
			if self.list:
				try:
					if self.type == self.NEXT_START_TIME and self.list[1][1]:
						return self.list[1][1]
					elif self.type == self.NEXT_DURATION and self.list[1][2]:
						return self.list[1][2]
					elif self.type == self.NEXT_END_TIME and self.list[1][1] and self.list[1][2]:
						return int(self.list[1][1]) + int(self.list[1][2])
					elif self.type == self.NEXT_TIMES and self.list[1][1] and self.list[1][2]:
						return (int(self.list[1][1]), int(self.list[1][1]) + int(self.list[1][2]))
					elif self.type == self.THIRD_START_TIME and self.list[2][1]:
						return self.list[2][1]
					elif self.type == self.THIRD_DURATION and self.list[2][2]:
						return self.list[2][2]
					elif self.type == self.THIRD_END_TIME and self.list[2][1] and self.list[2][2]:
						return int(self.list[2][1]) + int(self.list[2][2])
					elif self.type == self.THIRD_TIMES and self.list[2][1] and self.list[2][2]:
						return (int(self.list[2][1]), int(self.list[2][1]) + int(self.list[2][2]))
					else:
						# failed to return any epg data.
						return None
				except:
					# failed to return any epg data.
					return None

	@cached
	def getValue(self):
		assert self.type == self.PROGRESS

		event = self.source.event
		if event is None:
			return None

		progress = int(time()) - event.getBeginTime()
		duration = event.getDuration()
		if duration > 0 and progress >= 0:
			if progress > duration:
				progress = duration
			return progress * 1000 // duration
		else:
			return None

	time = property(getTime)
	value = property(getValue)
	range = 1000

	def changed(self, what):
		Converter.changed(self, what)
		if self.type == self.PROGRESS and len(self.downstream_elements):
			if not self.source.event and self.downstream_elements[0].visible:
				self.downstream_elements[0].visible = False
			elif self.source.event and not self.downstream_elements[0].visible:
				self.downstream_elements[0].visible = True
