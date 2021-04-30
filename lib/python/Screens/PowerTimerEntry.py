from Screens.TimerEntryBase import TimerEntryBase, TimerLogBase
from Components.config import ConfigSelection, ConfigYesNo, ConfigInteger
from Components.ActionMap import HelpableActionMap, NumberActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo
#from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
from PowerTimer import AFTEREVENT, TIMERTYPE
from time import localtime, time, strftime


class TimerEntry(TimerEntryBase):
	def __init__(self, session, timer):
		TimerEntryBase.__init__(self, session, timer, "powertimerentry")

	def createConfig(self):
		TimerEntryBase.createConfig(self)
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

		autosleepinstandbyonly = self.timer.autosleepinstandbyonly
		autosleepdelay = self.timer.autosleepdelay
		autosleeprepeat = self.timer.autosleeprepeat

		if SystemInfo["DeepstandbySupport"]:
			shutdownString = _("go to deep standby")
		else:
			shutdownString = _("shut down")
		self.timerentry_timertype = ConfigSelection(choices=[("wakeup", _("wakeup")), ("wakeuptostandby", _("wakeup to standby")), ("autostandby", _("auto standby")), ("autodeepstandby", _("auto deepstandby")), ("standby", _("go to standby")), ("deepstandby", shutdownString), ("reboot", _("reboot system")), ("restart", _("restart GUI"))], default=timertype)
		self.timerentry_afterevent = ConfigSelection(choices=[("nothing", _("do nothing")), ("wakeuptostandby", _("wakeup to standby")), ("standby", _("go to standby")), ("deepstandby", shutdownString), ("nothing", _("do nothing"))], default=afterevent)

		self.timerentry_autosleepdelay = ConfigInteger(default=autosleepdelay, limits=(10, 300))
		self.timerentry_autosleeprepeat = ConfigSelection(choices=[("once", _("once")), ("repeated", _("repeated"))], default=autosleeprepeat)
		self.timerentry_autosleepinstandbyonly = ConfigSelection(choices=[("yes", _("Yes")), ("no", _("No"))], default=autosleepinstandbyonly)

		self.timerentry_showendtime = ConfigYesNo(default=(((self.timer.end - self.timer.begin) / 60) > 1))

	def keySelect(self, result=None):
		self.keySave()

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

		TimerEntryBase.keySave(self)

		self.saveTimer()
		self.close((True, self.timer))

# The following four functions check for the item to be changed existing
# as for auto[deep]standby timers it doesn't, so we'll crash otherwise.
#
	def incrementStart(self):
		if self.timerentry_timertype.value not in ("autostandby", "autodeepstandby"):
			TimerEntryBase.incrementStart(self)

	def decrementStart(self):
		if self.timerentry_timertype.value not in ("autostandby", "autodeepstandby"):
			TimerEntryBase.decrementStart(self)

	def incrementEnd(self):
		if self.timerentry_showendtime.value:
			TimerEntryBase.incrementEnd(self)

	def decrementEnd(self):
		if self.timerentry_showendtime.value:
			TimerEntryBase.decrementEnd(self)

	def saveTimer(self):
		self.session.nav.PowerTimer.saveTimer()


class TimerLog(TimerLogBase):
	pass
