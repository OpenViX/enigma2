from time import time

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
		"Progress": (PROGRESS, 30 * 1000),
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

		start_time = event.getBeginTime()
		if self.type == self.STARTTIME:
			return start_time

		duration = event.getDuration()
		if self.type == self.DURATION:
			return duration

		end_time = start_time + duration
		if self.type == self.ENDTIME:
			return end_time

		if self.type == self.TIMES:
			return (start_time, end_time)

		if self.type in (self.REMAINING, self.ELAPSED):
			now = int(time())
			remaining = max(end_time - now, 0)
			elapsed = now - start_time

			if start_time <= now <= end_time:
				return duration, remaining, elapsed
			return duration, None, None

		if self.type in (
			self.NEXT_START_TIME, self.NEXT_END_TIME, self.NEXT_DURATION,
			self.THIRD_START_TIME, self.THIRD_END_TIME, self.THIRD_DURATION,
			self.NEXT_TIMES, self.THIRD_TIMES
		):
			reference = self.source.service
			info = reference and self.source.info
			if info is None or self.epgcache is None:
				return None

			test = ['IBDCX', (reference.toString(), 1, -1, 1440)]
			events = self.epgcache.lookupEvent(test) or []

			def get_event(idx):
				if len(events) > idx:
					return events[idx]
				return None

			def extract(event):
				if event and len(event) > 2:
					start = event[1]
					duration = event[2]

					start = int(start) if start else None
					duration = int(duration) if duration else None
					end = start + duration if start and duration else None

					return start, duration, end
				return None

			idx = 1 if self.type in (
				self.NEXT_START_TIME, self.NEXT_END_TIME,
				self.NEXT_DURATION, self.NEXT_TIMES
			) else 2

			data = extract(get_event(idx))
			if data is None:
				return None

			start, duration, end = data

			if self.type in (self.NEXT_START_TIME, self.THIRD_START_TIME):
				return start
			if self.type in (self.NEXT_DURATION, self.THIRD_DURATION):
				return duration
			if self.type in (self.NEXT_END_TIME, self.THIRD_END_TIME):
				return end
			if self.type in (self.NEXT_TIMES, self.THIRD_TIMES) and start and end:
				return (start, end)

		return None

	@cached
	def getValue(self):
		assert self.type == self.PROGRESS

		event = self.source.event
		if event is None:
			return None

		progress = int(time()) - event.getBeginTime()
		duration = event.getDuration()

		if duration <= 0 or progress < 0:
			return None

		progress = min(progress, duration)
		return progress * 1000 // duration

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
