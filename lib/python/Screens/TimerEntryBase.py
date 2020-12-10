from Components.ActionMap import HelpableActionMap
from Components.MenuList import MenuList
from Components.Button import Button
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.config import config, ConfigSelection, ConfigSubList, ConfigDateTime, ConfigClock, ConfigYesNo
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.HelpMenu import HelpableScreen

from time import localtime, mktime, strftime
from datetime import datetime

class TimerEntryBase(Setup):
	def __init__(self, session, timer, setup):
		# Need to create some variables before Setup reads setup.xml
		self.timer = timer
		self.createConfig()

		Setup.__init__(self, session, setup)

		# Are these actually skinned anywhere?
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
# 						print "[TimerEntryBase] Set to weekday " + str(x)
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

		self.timerentry_type = ConfigSelection(choices = [("once",_("once")), ("repeated", _("repeated"))], default = type)
		self.timerentry_repeated = ConfigSelection(default = repeated, choices = [("weekly", _("weekly")), ("daily", _("daily")), ("weekdays", _("Mon-Fri")), ("user", _("user defined"))])

		self.timerentry_date = ConfigDateTime(default = self.timer.begin, formatstring = config.usage.date.full.value, increment = 86400)
		self.timerentry_starttime = ConfigClock(default = self.timer.begin)
		self.timerentry_endtime = ConfigClock(default = self.timer.end)

		self.timerentry_repeatedbegindate = ConfigDateTime(default = self.timer.repeatedbegindate, formatstring = config.usage.date.full.value, increment = 86400)

		choices = [("mon",_("Monday")), ("tue", _("Tuesday")), ("wed",_("Wednesday")), ("thu", _("Thursday")), ("fri", _("Friday")), ("sat", _("Saturday")), ("sun", _("Sunday"))]
		self.timerentry_weekday = ConfigSelection(default = choices[weekday][0], choices = choices)

		self.timerentry_day = ConfigSubList()
		for x in (0, 1, 2, 3, 4, 5, 6):
			self.timerentry_day.append(ConfigYesNo(default = day[x]))

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

	def incrementStart(self):
		self.timerentry_starttime.increment()
		self.invalidateConfigEntry(self.timerentry_starttime)
		if self.timerentry_type.value == "once" and self.timerentry_starttime.value == [0, 0]:
			self.timerentry_date.value += 86400
			self.invalidateConfigEntry(self.timerentry_date)

	def decrementStart(self):
		self.timerentry_starttime.decrement()
		self.invalidateConfigEntry(self.timerentry_starttime)
		if self.timerentry_type.value == "once" and self.timerentry_starttime.value == [23, 59]:
			self.timerentry_date.value -= 86400
			self.invalidateConfigEntry(self.timerentry_date)

	def incrementEnd(self):
		self.timerentry_endtime.increment()
		self.invalidateConfigEntry(self.timerentry_endtime)

	def decrementEnd(self):
		self.timerentry_endtime.decrement()
		self.invalidateConfigEntry(self.timerentry_endtime)

	def saveTimer(self):  # Placeholder
		pass

	def keyGo(self, result = None):
		print "[TimerEntryBase] keyGo() is deprecated, call keySave() instead"
		self.keySave(result)

	def keyCancel(self):
		self.closeConfigList(((False,),))

	def keySave(self, result = None):
		self.timer.resetRepeated()

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
				self.timer.begin = self.getTimestamp(time(), self.timerentry_starttime.value)
				self.timer.end = self.getTimestamp(time(), self.timerentry_endtime.value)

			# when a timer end is set before the start, add 1 day
			if self.timer.end < self.timer.begin:
				self.timer.end += 86400
		# vital, otherwise start_prepare will be wrong if begin time has been changed
		self.timer.timeChanged()

	def invalidateConfigEntry(self, conf):
		for ent in self.list:
			if ent[1] is conf:
				self["config"].invalidate(ent)

class TimerLogBase(Screen, HelpableScreen):
	def __init__(self, session, timer):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.setTitle(_("Log"))

		self.timer = timer
		self.log_entries = self.timer.log_entries[:]

		self.fillLogList()

		self["loglist"] = MenuList(self.list)
		self["logentry"] = Label()

		self["key_red"] = Button(_("Delete entry"))
		self["key_blue"] = Button(_("Clear log"))

		self["loglist"].onSelectionChanged.append(self.updateText)

		self["actions"] = HelpableActionMap(self, ["OkCancelActions", "DirectionActions", "ColorActions"],
		{
			"ok": (self.keyClose, _("Close screen")),
			"cancel": (self.keyClose, _("Close screen")),
			"up": (self.moveUp, _("Move up a line")),
			"down": (self.moveDown, _("Move down a line")),
			"left": (self.pageUp, _("Move up a screen")),
			"right": (self.pageDown, _("Move down a screen")),
			"red": (self.deleteEntry, _("Delete log entry")),
			"blue": (self.clearLog, _("Delete all log entries")),
		})

	def deleteEntry(self):
		cur = self["loglist"].getCurrent()
		if cur is None:
			return
		self.log_entries.remove(cur[1])
		self.fillLogList()
		self["loglist"].l.setList(self.list)
		self.updateText()

	def fillLogList(self):
		self.list = [(str(strftime(config.usage.date.daylong.value + " " + config.usage.time.short.value, localtime(x[0])) + " - " + x[2]), x) for x in self.log_entries]

	def clearLog(self):
		self.log_entries = []
		self.fillLogList()
		self["loglist"].l.setList(self.list)
		self.updateText()

	def keyClose(self):
		if self.timer.log_entries != self.log_entries:
			self.timer.log_entries = self.log_entries
			self.close((True, self.timer))
		else:
			self.close((False,))

	def up(self):
		print "[TimerLog] up() is deprecated, call moveUp() instead"
		self.moveUp()

	def moveUp(self):
		self["loglist"].moveUp()

	def down(self):
		print "[TimerLog] down() is deprecated, call moveDown() instead"
		self.moveDown()

	def moveDown(self):
		self["loglist"].moveDown()

	def left(self):
		print "[TimerLog] left() is deprecated, call pageUp() instead"
		self.pageUp()

	def pageUp(self):
		self["loglist"].pageUp()

	def right(self):
		print "[TimerLog] right() is deprecated, call pageDown() instead"
		self.pageDown()

	def pageDown(self):
		self["loglist"].pageDown()

	def updateText(self):
		if self.list:
			self["logentry"].text = str(self["loglist"].getCurrent()[1][2])
		else:
			self["logentry"].text = ""
