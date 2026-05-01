from time import time

from enigma import eEPGCache

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached, ElementError


class EventTime(Poll, Converter):
	STARTTIME = 0
	ENDTIME = 1
	REMAINING = 2
	PROGRESS = 3
	DURATION = 4
	ELAPSED = 5
	NEXT_START_TIME = 6
	NEXT_END_TIME = 7
	NEXT_DURATION = 8
	THIRD_START_TIME = 9
	THIRD_END_TIME = 10
	THIRD_DURATION = 11
	TIMES = 12
	NEXT_TIMES = 13
	THIRD_TIMES = 14

	TYPES = {
		"EndTime": (ENDTIME, None),
		"Remaining": (REMAINING, 60 * 1000),
		"VFDRemaining": (REMAINING, 60 * 1000),  # "VFDRemaining" is redundant. "Remaining" could be used instead.
		"StartTime": (STARTTIME, None),
		"Progress": (PROGRESS, None),
		"Duration": (DURATION, None),
		"Elapsed": (ELAPSED, 60 * 1000),
		"VFDElapsed": (ELAPSED, 60 * 1000),  # "VFDElapsed" is redundant. "Elapsed" could be used instead.
		"NextStartTime": (NEXT_START_TIME, None),
		"NextEndTime": (NEXT_END_TIME, None),
		"NextDuration": (NEXT_DURATION, None),
		"ThirdStartTime": (THIRD_START_TIME, None),
		"ThirdEndTime": (THIRD_END_TIME, None),
		"ThirdDuration": (THIRD_DURATION, None),
		"Times": (TIMES, None),
		"NextTimes": (NEXT_TIMES, None),
		"ThirdTimes": (THIRD_TIMES, None),
	}

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		print(f"[EventTime] Converter argument: '{type}'")
		if type not in self.TYPES:
			raise ElementError(f"[EventTime] converter argument '{type}' is not in <{"|".join(sorted(self.TYPES))}>")
		self.type, poll_interval = self.TYPES[type]
		if poll_interval:
			self.poll_interval = poll_interval
			self.poll_enabled = True

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

		if self.type in (self.REMAINING, self.ELAPSED):
			now = int(time())
			remaining = et - now
			if remaining < 0:
				remaining = 0
			start_time = event.getBeginTime()
			end_time = start_time + duration
			elapsed = now - start_time
			if start_time <= now <= end_time:
				return duration, remaining, elapsed
			else:
				return duration, None, None

		elif self.type in (self.NEXT_START_TIME, self.NEXT_END_TIME, self.NEXT_DURATION, self.THIRD_START_TIME, self.THIRD_END_TIME, self.THIRD_DURATION, self.NEXT_TIMES, self.THIRD_TIMES):
			reference = self.source.service
			info = reference and self.source.info
			if info is None:
				return
			test = ['IBDCX', (reference.toString(), 1, -1, 1440)]  # search next 24 hours
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
