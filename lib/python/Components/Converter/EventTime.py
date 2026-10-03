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

	# Maps each type to the name of the method that produces its time value.
	HANDLERS = {
		STARTTIME: "timeStart",
		ENDTIME: "timeEnd",
		DURATION: "timeDuration",
		TIMES: "timeTimes",
		REMAINING: "timeRemainingElapsed",
		ELAPSED: "timeRemainingElapsed",
		NEXT_START_TIME: "timeNextStart",
		NEXT_END_TIME: "timeNextEnd",
		NEXT_DURATION: "timeNextDuration",
		NEXT_TIMES: "timeNextTimes",
		THIRD_START_TIME: "timeThirdStart",
		THIRD_END_TIME: "timeThirdEnd",
		THIRD_DURATION: "timeThirdDuration",
		THIRD_TIMES: "timeThirdTimes"
	}

	# Positions within the (start, duration, end) tuple returned by laterEventTimes.
	LATER_START = 0
	LATER_DURATION = 1
	LATER_END = 2

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.epgcache = eEPGCache.getInstance()
		print(f"[EventTime] Converter argument: '{type}'")
		if type not in self.TYPES:
			raise ElementError(f"[EventTime] converter argument '{type}' is not in <{"|".join(sorted(self.TYPES))}>")
		self.type, poll_interval = self.TYPES[type]
		if poll_interval:
			self.poll_interval = poll_interval
			self.poll_enabled = True
		# Resolve the handler once; getTime never has to work out the type again.
		self.handler = getattr(self, self.HANDLERS.get(self.type, "timeNone"))
		self.isProgress = self.type == self.PROGRESS

	@cached
	def getTime(self):
		assert self.type != self.PROGRESS

		event = self.source.event
		if event is None:
			return None
		return self.handler(event)

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
		if self.isProgress and len(self.downstream_elements):
			if not self.source.event and self.downstream_elements[0].visible:
				self.downstream_elements[0].visible = False
			elif self.source.event and not self.downstream_elements[0].visible:
				self.downstream_elements[0].visible = True

	# ---- Current event ----

	def timeNone(self, event):
		return None

	def timeStart(self, event):
		return event.getBeginTime()

	def timeDuration(self, event):
		return event.getDuration()

	def timeEnd(self, event):
		return event.getBeginTime() + event.getDuration()

	def timeTimes(self, event):
		start_time = event.getBeginTime()
		return start_time, start_time + event.getDuration()

	def timeRemainingElapsed(self, event):
		start_time = event.getBeginTime()
		duration = event.getDuration()
		end_time = start_time + duration
		now = int(time())
		if start_time <= now <= end_time:
			return duration, max(end_time - now, 0), now - start_time
		return duration, None, None

	# ---- Next / third events ----

	def laterEventTimes(self, index):
		reference = self.source.service
		info = reference and self.source.info
		if info is None or self.epgcache is None:
			return None
		events = self.epgcache.lookupEvent(["IBDCX", (reference.toString(), 1, -1, 1440)]) or []  # Search next 24 hours.
		if len(events) <= index:
			return None
		event = events[index]
		if not event or len(event) <= 2:
			return None
		start = int(event[1]) if event[1] else None
		duration = int(event[2]) if event[2] else None
		end = start + duration if start and duration else None
		return start, duration, end

	def laterEventTime(self, index, field):
		data = self.laterEventTimes(index)
		return data[field] if data else None

	def laterEventRange(self, index):
		data = self.laterEventTimes(index)
		if data and data[self.LATER_START] and data[self.LATER_END]:
			return data[self.LATER_START], data[self.LATER_END]
		return None

	def timeNextStart(self, event):
		return self.laterEventTime(1, self.LATER_START)

	def timeNextEnd(self, event):
		return self.laterEventTime(1, self.LATER_END)

	def timeNextDuration(self, event):
		return self.laterEventTime(1, self.LATER_DURATION)

	def timeNextTimes(self, event):
		return self.laterEventRange(1)

	def timeThirdStart(self, event):
		return self.laterEventTime(2, self.LATER_START)

	def timeThirdEnd(self, event):
		return self.laterEventTime(2, self.LATER_END)

	def timeThirdDuration(self, event):
		return self.laterEventTime(2, self.LATER_DURATION)

	def timeThirdTimes(self, event):
		return self.laterEventRange(2)
