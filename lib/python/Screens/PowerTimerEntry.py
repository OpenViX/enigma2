from Screens.Screen import Screen
from Screens.Setup import Setup
from Components.config import ConfigSelection, ConfigSubList, ConfigDateTime, ConfigClock, ConfigYesNo, ConfigInteger
from Components.ActionMap import HelpableActionMap, NumberActionMap
from Components.MenuList import MenuList
from Components.Button import Button
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo
#from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
from Components.config import config
from PowerTimer import AFTEREVENT, TIMERTYPE
from time import localtime, mktime, time, strftime
from datetime import datetime

class TimerEntry(Setup):
	def __init__(self, session, timer):
		# Need to create some variables before Setup reads setup.xml
		self.timer = timer
		self.createConfig()

		Setup.__init__(self, session=session, setup="powertimerentry")

		self["oktext"] = Label(_("Save"))
		self["canceltext"] = Label(_("Cancel"))
		self["ok"] = Pixmap()
		self["cancel"] = Pixmap()

		self["actions"] = HelpableActionMap(self, ["ConfigListActions", "GlobalActions", "PiPSetupActions"],
		{
			"save": (self.keySave, _("Save timer")),
			"cancel": (self.keyCancel, _("Cancel timer creation / changes")),
			"close": (self.keyCancel, _("Cancel timer creation / changes")),
			"volumeUp": (self.incrementStart, _("Increment start time")),
			"volumeDown": (self.decrementStart, _("Decrement start time")),
			"size+": (self.incrementEnd, _("Increment end time")),
			"size-": (self.decrementEnd, _("Decrement end time")),
		}, prio=-1)

	def createConfig(self):
		afterevent = {
			AFTEREVENT.NONE: "nothing",
			AFTEREVENT.WAKEUPTOSTANDBY: "wakeuptostandby",
			AFTEREVENT.STANDBY: "standby",
			AFTEREVENT.DEEPSTANDBY: "deepstandby"
			}[self.timer.afterEvent]

		timertype = {
			TIMERTYPE.WAKEUP: "wakeup",
			TIMERTYPE.WAKEUPTOSTANDBY: "wakeuptostandby",
			TIMERTYPE.AUTOSTANDBY: "autostandby",
			TIMERTYPE.AUTODEEPSTANDBY: "autodeepstandby",
			TIMERTYPE.STANDBY: "standby",
			TIMERTYPE.DEEPSTANDBY: "deepstandby",
			TIMERTYPE.REBOOT: "reboot",
			TIMERTYPE.RESTART: "restart"
			}[self.timer.timerType]

		weekday_table = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

		# calculate default values
		day = []
		weekday = 0
		for x in (0, 1, 2, 3, 4, 5, 6):
			day.append(0)
		if self.timer.repeated: # repeated
			type = "repeated"
			if self.timer.repeated == 31: # Mon-Fri
				repeated = "weekdays"
			elif self.timer.repeated == 127: # daily
				repeated = "daily"
			else:
				flags = self.timer.repeated
				repeated = "user"
				count = 0
				for x in (0, 1, 2, 3, 4, 5, 6):
					if flags == 1: # weekly
						print "[PowerTimerEntry] Set to weekday " + str(x)
						weekday = x
					if flags & 1 == 1: # set user defined flags
						day[x] = 1
						count += 1
					else:
						day[x] = 0
					flags >>= 1
				if count == 1:
					repeated = "weekly"
		else: # once
			type = "once"
			repeated = None
			weekday = int(strftime("%u", localtime(self.timer.begin))) - 1
			day[weekday] = 1

		autosleepinstandbyonly = self.timer.autosleepinstandbyonly
		autosleepdelay = self.timer.autosleepdelay
		autosleeprepeat = self.timer.autosleeprepeat

		if SystemInfo["DeepstandbySupport"]:
			shutdownString = _("go to deep standby")
		else:
			shutdownString = _("shut down")
		self.timerentry_timertype = ConfigSelection(choices = [("wakeup", _("wakeup")),("wakeuptostandby", _("wakeup to standby")), ("autostandby", _("auto standby")), ("autodeepstandby", _("auto deepstandby")), ("standby", _("go to standby")), ("deepstandby", shutdownString), ("reboot", _("reboot system")), ("restart", _("restart GUI"))], default = timertype)
		self.timerentry_afterevent = ConfigSelection(choices = [("nothing", _("do nothing")), ("wakeuptostandby", _("wakeup to standby")), ("standby", _("go to standby")), ("deepstandby", shutdownString), ("nothing", _("do nothing"))], default = afterevent)
		self.timerentry_type = ConfigSelection(choices = [("once",_("once")), ("repeated", _("repeated"))], default = type)

		self.timerentry_repeated = ConfigSelection(default = repeated, choices = [("daily", _("daily")), ("weekly", _("weekly")), ("weekdays", _("Mon-Fri")), ("user", _("user defined"))])
		self.timerentry_autosleepdelay = ConfigInteger(default=autosleepdelay, limits = (10, 300))
		self.timerentry_autosleeprepeat = ConfigSelection(choices = [("once",_("once")), ("repeated", _("repeated"))], default = autosleeprepeat)
		self.timerentry_autosleepinstandbyonly = ConfigSelection(choices = [("yes",_("Yes")), ("no", _("No"))],default=autosleepinstandbyonly)

		self.timerentry_date = ConfigDateTime(default = self.timer.begin, formatstring = config.usage.date.full.value, increment = 86400)
		self.timerentry_starttime = ConfigClock(default = self.timer.begin)
		self.timerentry_endtime = ConfigClock(default = self.timer.end)
		self.timerentry_showendtime = ConfigYesNo(default = (((self.timer.end - self.timer.begin) /60 ) > 1))

		self.timerentry_repeatedbegindate = ConfigDateTime(default = self.timer.repeatedbegindate, formatstring = config.usage.date.full.value, increment = 86400)

		self.timerentry_weekday = ConfigSelection(default = weekday_table[weekday], choices = [("mon",_("Monday")), ("tue", _("Tuesday")), ("wed",_("Wednesday")), ("thu", _("Thursday")), ("fri", _("Friday")), ("sat", _("Saturday")), ("sun", _("Sunday"))])

		self.timerentry_day = ConfigSubList()
		for x in (0, 1, 2, 3, 4, 5, 6):
			self.timerentry_day.append(ConfigYesNo(default = day[x]))

	def keyGo(self):
		print "[TimerLog] keyGo() is deprecated, call keySelect() instead"
		self.keySave()

	def keySelect(self, result=None):
		self.keySave()

	def getTimestamp(self, date, mytime):
		d = localtime(date)
		dt = datetime(d.tm_year, d.tm_mon, d.tm_mday, mytime[0], mytime[1])
		return int(mktime(dt.timetuple()))

	def getBeginEnd(self):
		date = self.timerentry_date.value
		endtime = self.timerentry_endtime.value
		starttime = self.timerentry_starttime.value

		begin = self.getTimestamp(date, starttime)
		end = self.getTimestamp(date, endtime)

		# if the endtime is less than the starttime, add 1 day.
		if end < begin:
			end += 86400

		return begin, end

	def keySave(self):
		if not self.timerentry_showendtime.value:
			self.timerentry_endtime.value = self.timerentry_starttime.value

		self.timer.resetRepeated()
		self.timer.timerType = {
			"wakeup": TIMERTYPE.WAKEUP,
			"wakeuptostandby": TIMERTYPE.WAKEUPTOSTANDBY,
			"autostandby": TIMERTYPE.AUTOSTANDBY,
			"autodeepstandby": TIMERTYPE.AUTODEEPSTANDBY,
			"standby": TIMERTYPE.STANDBY,
			"deepstandby": TIMERTYPE.DEEPSTANDBY,
			"reboot": TIMERTYPE.REBOOT,
			"restart": TIMERTYPE.RESTART
			}[self.timerentry_timertype.value]
		self.timer.afterEvent = {
			"nothing": AFTEREVENT.NONE,
			"wakeuptostandby": AFTEREVENT.WAKEUPTOSTANDBY,
			"standby": AFTEREVENT.STANDBY,
			"deepstandby": AFTEREVENT.DEEPSTANDBY
			}[self.timerentry_afterevent.value]

		if self.timerentry_type.value == "once":
			self.timer.begin, self.timer.end = self.getBeginEnd()

		if self.timerentry_timertype.value == "autostandby" or self.timerentry_timertype.value == "autodeepstandby":
			self.timer.begin = int(time()) + 10
			self.timer.end = self.timer.begin
			self.timer.autosleepinstandbyonly = self.timerentry_autosleepinstandbyonly.value
			self.timer.autosleepdelay = self.timerentry_autosleepdelay.value
			self.timer.autosleeprepeat = self.timerentry_autosleeprepeat.value
# Ensure that the timer repeated is cleared if we have an autosleeprepeat
			if self.timerentry_type.value == "repeated":
				self.timer.resetRepeated()
				self.timerentry_type.value = "once" # Stop it being set again

		if self.timerentry_type.value == "repeated":
			if self.timerentry_repeated.value == "daily":
				for x in (0, 1, 2, 3, 4, 5, 6):
					self.timer.setRepeated(x)

			if self.timerentry_repeated.value == "weekly":
				self.timer.setRepeated(self.timerentry_weekday.index)

			if self.timerentry_repeated.value == "weekdays":
				for x in (0, 1, 2, 3, 4):
					self.timer.setRepeated(x)

			if self.timerentry_repeated.value == "user":
				for x in (0, 1, 2, 3, 4, 5, 6):
					if self.timerentry_day[x].value:
						self.timer.setRepeated(x)

			self.timer.repeatedbegindate = self.getTimestamp(self.timerentry_repeatedbegindate.value, self.timerentry_starttime.value)
			if self.timer.repeated:
				self.timer.begin = self.getTimestamp(self.timerentry_repeatedbegindate.value, self.timerentry_starttime.value)
				self.timer.end = self.getTimestamp(self.timerentry_repeatedbegindate.value, self.timerentry_endtime.value)
			else:
				self.timer.begin = self.getTimestamp(time.time(), self.timerentry_starttime.value)
				self.timer.end = self.getTimestamp(time.time(), self.timerentry_endtime.value)

			# when a timer end is set before the start, add 1 day
			if self.timer.end < self.timer.begin:
				self.timer.end += 86400

		self.saveTimer()
		self.close((True, self.timer))

# The following four functions check for the item to be changed existing
# as for auto[deep]standby timers it doesn't, so we'll crash otherwise.
#
	def incrementStart(self):
		if self.timerentry_timertype.value in ("autostandby", "autodeepstandby"):
			return
		self.timerentry_starttime.increment()
		self.invalidateConfigEntry(self.timerentry_starttime)
		if self.timerentry_type.value == "once" and self.timerentry_starttime.value == [0, 0]:
			self.timerentry_date.value += 86400
			self.invalidateConfigEntry(self.timerentry_date)

	def decrementStart(self):
		if self.timerentry_timertype.value in ("autostandby", "autodeepstandby"):
			return
		self.timerentry_starttime.decrement()
		self.invalidateConfigEntry(self.timerentry_starttime)
		if self.timerentry_type.value == "once" and self.timerentry_starttime.value == [23, 59]:
			self.timerentry_date.value -= 86400
			self.invalidateConfigEntry(self.timerentry_date)

	def incrementEnd(self):
		if self.timerentry_showendtime.value:
			self.timerentry_endtime.increment()
			self.invalidateConfigEntry(self.timerentry_endtime)

	def decrementEnd(self):
		if self.timerentry_showendtime.value:
			self.timerentry_endtime.decrement()
			self.invalidateConfigEntry(self.timerentry_endtime)

	def saveTimer(self):
		self.session.nav.PowerTimer.saveTimer()

	def keyCancel(self):
		self.closeConfigList(((False,),))

	def invalidateConfigEntry(self, conf):
		for ent in self.list:
			if ent[1] is conf:
				self["config"].invalidate(ent)

from TimerEntry import TimerLog as TimerLogTE

class TimerLog(TimerLogTE):
	pass
