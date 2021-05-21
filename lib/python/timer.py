from __future__ import print_function
from bisect import insort
from time import time, localtime, mktime
from enigma import eTimer, eActionMap
import datetime


class TimerEntry:
	StateWaiting = 0	# Waiting for the recording start time
	StatePrepared = 1	# Pre recording preparation has been completed, about to start recording
	StateRunning = 2 	# Currently recording
	StateEnded = 3		# Recording was completed successfully
	StateFailed = 4		# Something went wrong

	States = {
		0: "Waiting",
		1: "Prepared",
		2: "Running",
		3: "Ended",
		4: "Failed"
	}

	def __init__(self, begin, end):
		self.begin = begin
		self.prepare_time = 20
		self.end = end
		self.state = 0
		self.findRunningEvent = True
		self.findNextEvent = False
		self.resetRepeated()
		self.repeatedbegindate = begin
		self.backoff = 0

		self.disabled = False
		self.failed = False
		self.log_entries = []

	def resetState(self):
		self.state = self.StateWaiting
		self.cancelled = False
		self.first_try_prepare = True
		self.findRunningEvent = True
		self.findNextEvent = False
		self.timeChanged()

	def resetRepeated(self):
		self.repeated = int(0)

	def setRepeated(self, day):
		self.repeated |= (2 ** day)

	def isRunning(self):
		return self.state == self.StateRunning

	def addOneDay(self, timedatestruct):
		oldHour = timedatestruct.tm_hour
		newdate = (datetime.datetime(timedatestruct.tm_year, timedatestruct.tm_mon, timedatestruct.tm_mday, timedatestruct.tm_hour, timedatestruct.tm_min, timedatestruct.tm_sec) + datetime.timedelta(days=1)).timetuple()
		if localtime(mktime(newdate)).tm_hour != oldHour:
			return (datetime.datetime(timedatestruct.tm_year, timedatestruct.tm_mon, timedatestruct.tm_mday, timedatestruct.tm_hour, timedatestruct.tm_min, timedatestruct.tm_sec) + datetime.timedelta(days=2)).timetuple()
		return newdate

	def isFindRunningEvent(self):
		return self.findRunningEvent

	def isFindNextEvent(self):
		return self.findNextEvent

	# update self.begin and self.end according to the self.repeated-flags
	def processRepeated(self, findRunningEvent=True, findNextEvent=False):
		if self.repeated != 0:
			now = int(time()) + 1
			if findNextEvent:
				now = self.end + 120
			self.findRunningEvent = findRunningEvent
			self.findNextEvent = findNextEvent
			#to avoid problems with daylight saving, we need to calculate with localtime, in struct_time representation
			localrepeatedbegindate = localtime(self.repeatedbegindate)
			localbegin = localtime(self.begin)
			localend = localtime(self.end)
			localnow = localtime(now)

			day = []
			flags = self.repeated
			for x in (0, 1, 2, 3, 4, 5, 6):
				if flags & 1 == 1:
					day.append(0)
				else:
					day.append(1)
				flags >>= 1

			# if day is NOT in the list of repeated days
			# OR if the day IS in the list of the repeated days, check, if event is currently running... then if findRunningEvent is false, go to the next event
			while ((day[localbegin.tm_wday] != 0) or (mktime(localrepeatedbegindate) > mktime(localbegin)) or
				(day[localbegin.tm_wday] == 0 and (findRunningEvent and localend < localnow) or ((not findRunningEvent) and localbegin < localnow))):
				localbegin = self.addOneDay(localbegin)
				localend = self.addOneDay(localend)

			#we now have a struct_time representation of begin and end in localtime, but we have to calculate back to (gmt) seconds since epoch
			self.begin = int(mktime(localbegin))
			self.end = int(mktime(localend))
			if self.begin == self.end:
				self.end += 1

			self.timeChanged()

	def __lt__(self, o):
		return self.getNextActivation() < o.getNextActivation()

	# must be overridden
	def activate(self):
		pass

	# can be overridden
	def timeChanged(self):
		pass

	# check if a timer entry must be skipped
	def shouldSkip(self):
		if self.disabled:
			if self.end <= time() and not "PowerTimerEntry" in repr(self):
				self.disabled = False
			return True
		if "PowerTimerEntry" in repr(self):
			if (self.timerType == 3 or self.timerType == 4) and self.autosleeprepeat != 'once':
				return False
			elif self.begin >= time() and (self.timerType == 3 or self.timerType == 4) and self.autosleeprepeat == 'once':
				return False
			elif (self.timerType == 3 or self.timerType == 4) and self.autosleeprepeat == 'once' and self.state != TimerEntry.StatePrepared:
				return True
			else:
				return self.end <= time() and self.state == TimerEntry.StateWaiting and self.timerType != 3 and self.timerType != 4
		else:
			return self.end <= time() and (self.state == TimerEntry.StateWaiting or self.state == TimerEntry.StateFailed)

	def abort(self):
		self.end = time()

		# in case timer has not yet started, but gets aborted (so it's preparing),
		# set begin to now.
		if self.begin > self.end:
			self.begin = self.end

		self.cancelled = True

	# must be overridden!
	def getNextActivation(self):
		pass

	def saveTimer(self):
		pass

	def fail(self):
		self.faileded = True

	def disable(self):
		self.disabled = True

	def enable(self):
		self.disabled = False


class Timer:
	# the time between "polls". We do this because
	# we want to account for time jumps etc.
	# of course if they occur <100s before starting,
	# it's not good. thus, you have to repoll when
	# you change the time.
	#
	# this is just in case. We don't want the timer
	# hanging. we use this "edge-triggered-polling-scheme"
	# anyway, so why don't make it a bit more fool-proof?
	MaxWaitTime = 100

	def __init__(self):
		self.timer_list = []
		self.processed_timers = []

		self.timer = eTimer()
		self.timer.callback.append(self.calcNextActivation)
		self.lastActivation = time()

		self.calcNextActivation()
		self.on_state_change = []

	def stateChanged(self, entry):
		for f in self.on_state_change:
			f(entry)

	def cleanup(self):
		self.processed_timers = [entry for entry in self.processed_timers if entry.disabled]

	def cleanupDisabled(self):
		disabled_timers = [entry for entry in self.processed_timers if entry.disabled]
		for timer in disabled_timers:
			timer.shouldSkip()

	def cleanupDaily(self, days, finishedLogDays=None):
		now = time()
		keepThreshold = now - days * 86400 if days else 0
		keepFinishedLogThreshold = now - finishedLogDays * 86400 if finishedLogDays else 0
		for entry in self.timer_list:
			if entry.repeated:
				# Handle repeat entries, which never end
				# Repeating timers get, e.g., repeated="127" (day of week bitmap)
				entry.log_entries = [log_entry for log_entry in entry.log_entries if log_entry[0] > keepThreshold]

		self.processed_timers = [entry for entry in self.processed_timers if (entry.disabled and entry.repeated) or (entry.end and (entry.end > keepThreshold))]
		for entry in self.processed_timers:
			if entry.end < keepFinishedLogThreshold and len(entry.log_entries) > 0:
				# Clear logs on finished timers
				entry.log_entries = []

	def addTimerEntry(self, entry, noRecalc=0, dosave=True):
		entry.processRepeated()

		# when the timer has not yet started, and is already passed,
		# don't go trough waiting/running/end-states, but sort it
		# right into the processedTimers.
		if entry.shouldSkip() or entry.state == TimerEntry.StateEnded or (entry.state == TimerEntry.StateWaiting and entry.disabled):
			insort(self.processed_timers, entry)
			entry.state = TimerEntry.StateEnded
		else:
			insort(self.timer_list, entry)
			if not noRecalc:
				self.calcNextActivation(dosave)

# small piece of example code to understand how to use record simulation
#		if NavigationInstance.instance:
#			lst = [ ]
#			cnt = 0
#			for timer in self.timer_list:
#				print "timer", cnt
#				cnt += 1
#				if timer.state == 0: #waiting
#					lst.append(NavigationInstance.instance.recordService(timer.service_ref))
#				else:
#					print "STATE: ", timer.state
#
#			for rec in lst:
#				if rec.start(True): #simulate
#					print "FAILED!!!!!!!!!!!!"
#				else:
#					print "OK!!!!!!!!!!!!!!"
#				NavigationInstance.instance.stopRecordService(rec)
#		else:
#			print "no NAV"

	def setNextActivation(self, now, when):
		delay = int((when - now) * 1000)
		self.timer.start(delay, 1)
		self.next = when

	def calcNextActivation(self, dosave=True):
		now = time()
		if self.lastActivation > now:
			print("[timer.py] timewarp - re-evaluating all processed timers.")
			tl = self.processed_timers
			self.processed_timers = []
			for x in tl:
				# simulate a "waiting" state to give them a chance to re-occure
				x.resetState()
				self.addTimerEntry(x, noRecalc=1, dosave=dosave)

		self.processActivation(dosave)
		self.lastActivation = now

		min = int(now) + self.MaxWaitTime

		self.timer_list and self.timer_list.sort() #  resort/refresh list, try to fix hanging timers

		# calculate next activation point
		timer_list = [t for t in self.timer_list if not t.disabled]
		if timer_list:
			w = timer_list[0].getNextActivation()
			if w < min:
				min = w

		if int(now) < 1072224000 and min > now + 5:
			# system time has not yet been set (before 01.01.2004), keep a short poll interval
			min = now + 5

		self.setNextActivation(now, min)

	def timeChanged(self, timer, dosave=True):
		timer.timeChanged()
		if timer.state == TimerEntry.StateEnded:
			self.processed_timers.remove(timer)
		else:
			try:
				self.timer_list.remove(timer)
			except:
				print("[timer] Failed to remove, not in list")
				return
		# give the timer a chance to re-enqueue
		if timer.state == TimerEntry.StateEnded:
			timer.state = TimerEntry.StateWaiting
		elif "PowerTimerEntry" in repr(timer) and (timer.timerType == 3 or timer.timerType == 4):
			if timer.state > 0:
				eActionMap.getInstance().unbindAction('', timer.keyPressed)
			timer.state = TimerEntry.StateWaiting

		self.addTimerEntry(timer, dosave=dosave)

	def doActivate(self, w, dosave=True):
		self.timer_list.remove(w)

		# when activating a timer which has already passed,
		# simply abort the timer. don't run trough all the stages.
		if w.shouldSkip():
			w.state = TimerEntry.StateEnded
		else:
			# when active returns true, this means "accepted".
			# otherwise, the current state is kept.
			# the timer entry itself will fix up the delay then.
			if w.activate():
				w.state += 1

		# did this timer reached the last state?
		if w.state < TimerEntry.StateEnded:
			# no, sort it into active list
			insort(self.timer_list, w)
		else:
			# yes. Process repeated, and re-add.
			if w.repeated:
				w.processRepeated()
				w.state = TimerEntry.StateWaiting
				self.addTimerEntry(w, dosave=dosave)
			else:
				insort(self.processed_timers, w)

		self.stateChanged(w)

	def processActivation(self, dosave):
		t = int(time()) + 1
		# We keep on processing the first entry until it goes into the future.
		#
		# As we activate a timer, mark it as such and don't activate it again if
		# it is so marked.
		# This is to prevent a situation that obtains for Record timers.
		# These do not remove themselves from the timer_list at the start of
		# their doActivate() (as various parts of that code expects them to
		# still be there - each timers steps through various states) and hence
		# one thread can activate it and then, on a file-system access, python
		# switches to another thread and, if that happens to end up running the
		# timer code, the same timer will be run again.
		#
		# Since this tag is only for use here, we remove it after use.
		#

		wasActivated = False
		while True:
			entry = None
			for tmr in self.timer_list:
				if not tmr.disabled and not getattr(tmr, "currentlyActivated", False):
					entry = tmr
					break
			if entry and entry.getNextActivation() < t:
				entry.currentlyActivated = True
				self.doActivate(entry, False)
				del entry.currentlyActivated
				wasActivated = True
			else:
				break
		if wasActivated and dosave:
			self.saveTimer()
