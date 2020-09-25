# -*- coding: utf-8 -*-
from time import localtime, mktime, time, strftime
from datetime import datetime

from enigma import eEPGCache

from Screens.Screen import Screen
import ChannelSelection
from ServiceReference import ServiceReference
from Components.config import config, ConfigSelection, ConfigText, ConfigSubList, ConfigDateTime, ConfigClock, ConfigYesNo
from Components.ActionMap import NumberActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.Button import Button
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo
from Components.UsageConfig import defaultMoviePath
from Screens.Setup import Setup
from Screens.MovieSelection import getPreferredTagEditor
from Screens.LocationBox import MovieLocationBox
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from RecordTimer import AFTEREVENT


class TimerEntry(Setup):
	def __init__(self, session, timer):
		# Need to create some variables before Setup reads setup.xml
		self.timer = timer
		self.createConfig()

		Setup.__init__(self, session=session, setup="timerentry")

		# Are these actually skinned anywhere?
		self["oktext"] = Label(_("Save"))
		self["canceltext"] = Label(_("Cancel"))
		self["ok"] = Pixmap()
		self["cancel"] = Pixmap()

		self["actions"] = HelpableActionMap(self, ["ConfigListActions", "GlobalActions", "PiPSetupActions"],
		{
                        "select": (self.keySelect, _("Edit channel, location or tags, otherwise save timer")),
			"save": (self.keySave, _("Save timer")),
			"cancel": (self.keyCancel, _("Cancel timer creation / changes")),
			"close": (self.keyCancel, _("Cancel timer creation / changes")),
			"volumeUp": (self.incrementStart, _("Increment start time")),
			"volumeDown": (self.decrementStart, _("Decrement start time")),
			"size+": (self.incrementEnd, _("Increment end time")),
			"size-": (self.decrementEnd, _("Decrement end time")),
		}, prio=-1)

	def createConfig(self):
		justplay = self.timer.justplay
		always_zap = self.timer.always_zap
		pipzap = self.timer.pipzap
		rename_repeat = self.timer.rename_repeat
		conflict_detection = self.timer.conflict_detection

		afterevent = {
			AFTEREVENT.NONE: "nothing",
			AFTEREVENT.DEEPSTANDBY: "deepstandby",
			AFTEREVENT.STANDBY: "standby",
			AFTEREVENT.AUTO: "auto"
			}[self.timer.afterEvent]

		if self.timer.record_ecm and self.timer.descramble:
			recordingtype = "descrambled+ecm"
		elif self.timer.record_ecm:
			recordingtype = "scrambled+ecm"
		elif self.timer.descramble:
			recordingtype = "normal"

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
# 						print "Set to weekday " + str(x)
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

		self.timerentry_justplay = ConfigSelection(choices = [
			("zap", _("zap")), ("record", _("record")), ("zap+record", _("zap and record"))],
			default = {0: "record", 1: "zap", 2: "zap+record"}[justplay + 2*always_zap])
		if SystemInfo["DeepstandbySupport"]:
			shutdownString = _("go to deep standby")
		else:
			shutdownString = _("shut down")
		self.timerentry_afterevent = ConfigSelection(choices = [("nothing", _("do nothing")), ("standby", _("go to standby")), ("deepstandby", shutdownString), ("auto", _("auto"))], default = afterevent)
		self.timerentry_recordingtype = ConfigSelection(choices = [("normal", _("normal")), ("descrambled+ecm", _("descramble and record ecm")), ("scrambled+ecm", _("don't descramble, record ecm"))], default = recordingtype)
		self.timerentry_type = ConfigSelection(choices = [("once",_("once")), ("repeated", _("repeated"))], default = type)
		self.timerentry_name = ConfigText(default = self.timer.name.replace('\xc2\x86', '').replace('\xc2\x87', '').encode("utf-8"), visible_width = 50, fixed_size = False)
		self.timerentry_description = ConfigText(default = self.timer.description, visible_width = 50, fixed_size = False)
		self.timerentry_tags = self.timer.tags[:]
		# if no tags found, make name of event default tag set.
		if not self.timerentry_tags:
				tagname = self.timer.name.strip()
				if tagname:
					tagname = tagname[0].upper() + tagname[1:].replace(" ", "_")
					self.timerentry_tags.append(tagname)

		self.timerentry_tagsset = ConfigSelection(choices = [not self.timerentry_tags and "None" or " ".join(self.timerentry_tags)])

		self.timerentry_repeated = ConfigSelection(default = repeated, choices = [("weekly", _("weekly")), ("daily", _("daily")), ("weekdays", _("Mon-Fri")), ("user", _("user defined"))])
		self.timerentry_renamerepeat = ConfigYesNo(default = rename_repeat)

		self.timerentry_pipzap = ConfigYesNo(default = pipzap)
		self.timerentry_conflictdetection = ConfigYesNo(default = conflict_detection)

		self.timerentry_date = ConfigDateTime(default = self.timer.begin, formatstring = config.usage.date.full.value, increment = 86400)
		self.timerentry_starttime = ConfigClock(default = self.timer.begin)
		self.timerentry_endtime = ConfigClock(default = self.timer.end)
		self.timerentry_showendtime = ConfigSelection(default = False, choices = [(True, _("yes")), (False, _("no"))])

		default = self.timer.dirname or defaultMoviePath()
		tmp = config.movielist.videodirs.value
		if default not in tmp:
			tmp.append(default)
		self.timerentry_dirname = ConfigSelection(default = default, choices = tmp)

		self.timerentry_repeatedbegindate = ConfigDateTime(default = self.timer.repeatedbegindate, formatstring = config.usage.date.full.value, increment = 86400)

		self.timerentry_weekday = ConfigSelection(default = weekday_table[weekday], choices = [("mon",_("Monday")), ("tue", _("Tuesday")), ("wed",_("Wednesday")), ("thu", _("Thursday")), ("fri", _("Friday")), ("sat", _("Saturday")), ("sun", _("Sunday"))])

		self.timerentry_day = ConfigSubList()
		for x in (0, 1, 2, 3, 4, 5, 6):
			self.timerentry_day.append(ConfigYesNo(default = day[x]))

		# FIXME some service-chooser needed here
		servicename = "N/A"
		try: # no current service available?
			servicename = str(self.timer.service_ref.getServiceName())
		except:
			pass
		self.timerentry_service_ref = self.timer.service_ref
		self.timerentry_service = ConfigSelection([servicename])

	# So that setup.xml can call it as self.getPreferredTagEditor()
	def getPreferredTagEditor(self):
		return getPreferredTagEditor()

	def keyLeft(self):
		cur = self["config"].getCurrent()
		if cur and cur[1] in (self.timerentry_service, self.timerentry_tagsset):
			self.keySelect()
		elif cur and isinstance(cur[1], ConfigText):
			self.renameEntry()
		else:
			Setup.keyLeft(self)

	def keyRight(self):
		cur = self["config"].getCurrent()
		if cur and cur[1] in (self.timerentry_service, self.timerentry_tagsset):
			self.keySelect()
		elif cur and isinstance(cur[1], ConfigText):
			self.renameEntry()
		else:
			Setup.keyRight(self)

	def keyText(self):
		self.renameEntry()

	def renameEntry(self):
		cur = self["config"].getCurrent()
		if cur and cur[1] == self.timerentry_name:
			title_text = _("Please enter new name:")
			old_text = self.timerentry_name.value
		else:
			title_text = _("Please enter new description:")
			old_text = self.timerentry_description.value
		self.session.openWithCallback(self.renameEntryCallback, VirtualKeyBoard, title=title_text, text=old_text)

	def renameEntryCallback(self, answer):
		if answer:
			cur = self["config"].getCurrent()
			if cur and cur[1] == self.timerentry_name:
				target = self.timerentry_name
			else:
				target = self.timerentry_description
			target.value = answer
			self.invalidateConfigEntry(target)

#	No longer called from ConfigListScreen since keyFile() removed.
#	def handleKeyFileCallback(self, answer):
#		cur = self["config"].getCurrent()
#		if cur and cur[1] in (self.timerentry_service, self.timerentry_tagsset):
#			self.keySelect()
#		else:
#			Setup.handleKeyFileCallback(self, answer)
#			self.changedEntry()

	def keySelect(self):
		cur = self["config"].getCurrent()
		if cur and cur[1] == self.timerentry_service:
			self.session.openWithCallback(
				self.finishedChannelSelection,
				ChannelSelection.SimpleChannelSelection,
				_("Select channel to record from"),
				currentBouquet=True
			)
		elif cur and cur[1] == self.timerentry_dirname:
			self.session.openWithCallback(
				self.pathSelected,
				MovieLocationBox,
				_("Select target folder"),
				self.timerentry_dirname.value,
				minFree = 100 # We require at least 100MB free space
			)
		elif cur and cur[1] == self.timerentry_tagsset:
			self.session.openWithCallback(
				self.tagEditFinished,
				getPreferredTagEditor(),
				self.timerentry_tags
			)
		else:
			self.keySave()

	def finishedChannelSelection(self, *args):
		if args:
			self.timerentry_service_ref = ServiceReference(args[0])
			self.timerentry_service.setCurrentText(self.timerentry_service_ref.getServiceName())
			self.invalidateConfigEntry(self.timerentry_service)

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

		# if the timer type is a Zap and no end is set, set duration to 1 second so time is shown in EPG's.
		if self.timerentry_justplay.value == "zap":
			if not self.timerentry_showendtime.value:
				end = begin + (config.recording.margin_before.value*60) + 1

		return begin, end

	def selectChannelSelector(self, *args):
		self.session.openWithCallback(
				self.finishedChannelSelectionCorrection,
				ChannelSelection.SimpleChannelSelection,
				_("Select channel to record from")
			)

	def finishedChannelSelectionCorrection(self, *args):
		if args:
			self.finishedChannelSelection(*args)
			self.keySave()

	def keyGo(self, result = None):
		print "[TimerEntry] keyGo() is deprecated, call keySave() instead"
		self.keySave(result)

	def keySave(self, result = None):
		if not self.timerentry_service_ref.isRecordable():
			self.session.openWithCallback(self.selectChannelSelector, MessageBox, _("You didn't select a channel to record from."), MessageBox.TYPE_ERROR)
			return
		self.timer.name = self.timerentry_name.value
		self.timer.description = self.timerentry_description.value
		self.timer.justplay = self.timerentry_justplay.value == "zap"
		self.timer.always_zap = self.timerentry_justplay.value == "zap+record"
		self.timer.pipzap = self.timerentry_pipzap.value
		self.timer.rename_repeat = self.timerentry_renamerepeat.value
		self.timer.conflict_detection = self.timerentry_conflictdetection.value
		if self.timerentry_justplay.value == "zap":
			if not self.timerentry_showendtime.value:
				self.timerentry_endtime.value = self.timerentry_starttime.value
		self.timer.resetRepeated()
		self.timer.afterEvent = {
			"nothing": AFTEREVENT.NONE,
			"deepstandby": AFTEREVENT.DEEPSTANDBY,
			"standby": AFTEREVENT.STANDBY,
			"auto": AFTEREVENT.AUTO
			}[self.timerentry_afterevent.value]
# There is no point doing anything after a Zap-only timer!
# For a start, you can't actually configure anything in the menu, but
# leaving it as AUTO means that the code may try to shutdown at Zap time
# if the Zap timer woke the box up.
#
		if self.timer.justplay:
			self.timer.afterEvent = AFTEREVENT.NONE
		self.timer.descramble = {
			"normal": True,
			"descrambled+ecm": True,
			"scrambled+ecm": False,
			}[self.timerentry_recordingtype.value]
		self.timer.record_ecm = {
			"normal": False,
			"descrambled+ecm": True,
			"scrambled+ecm": True,
			}[self.timerentry_recordingtype.value]
		self.timer.service_ref = self.timerentry_service_ref
		self.timer.tags = self.timerentry_tags

		if self.timer.dirname or self.timerentry_dirname.value != defaultMoviePath():
			self.timer.dirname = self.timerentry_dirname.value
			config.movielist.last_timer_videodir.value = self.timer.dirname
			config.movielist.last_timer_videodir.save()

		if self.timerentry_type.value == "once":
			self.timer.begin, self.timer.end = self.getBeginEnd()
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

		if self.timer.eit is not None:
			event = eEPGCache.getInstance().lookupEventId(self.timer.service_ref.ref, self.timer.eit)
			if event:
				n = event.getNumOfLinkageServices()
				if n > 1:
					tlist = []
					ref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
					parent = self.timer.service_ref.ref
					selection = 0
					for x in range(n):
						i = event.getLinkageService(parent, x)
						if i.toString() == ref.toString():
							selection = x
						tlist.append((i.getName(), i))
					self.session.openWithCallback(self.subserviceSelected, ChoiceBox, title=_("Please select a subservice to record..."), list = tlist, selection = selection)
					return
				elif n > 0:
					parent = self.timer.service_ref.ref
					self.timer.service_ref = ServiceReference(event.getLinkageService(parent, 0))
		self.saveTimer()
		self.close((True, self.timer))

	def changeTimerType(self):
		self.timerentry_justplay.selectNext()
		self.invalidateConfigEntry(self.timerentry_justplay)

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
		if self.timerentry_justplay.value != "zap" or self.timerentry_showendtime.value:
			self.timerentry_endtime.increment()
			self.invalidateConfigEntry(self.timerentry_endtime)

	def decrementEnd(self):
		if self.timerentry_justplay.value != "zap" or self.timerentry_showendtime.value:
			self.timerentry_endtime.decrement()
			self.invalidateConfigEntry(self.timerentry_endtime)

	def subserviceSelected(self, service):
		if not service is None:
			self.timer.service_ref = ServiceReference(service[1])
		self.saveTimer()
		self.close((True, self.timer))

	def saveTimer(self):
		self.session.nav.RecordTimer.saveTimer()

	def keyCancel(self):
		self.close((False,))

	def pathSelected(self, res):
		if res is not None:
			if config.movielist.videodirs.value != self.timerentry_dirname.choices:
				self.timerentry_dirname.setChoices(config.movielist.videodirs.value, default=res)
			self.timerentry_dirname.value = res

	def tagEditFinished(self, ret):
		if ret is not None:
			self.timerentry_tags = ret
			self.timerentry_tagsset.setChoices([not ret and "None" or " ".join(ret)])
			self.invalidateConfigEntry(self.timerentry_tagsset)

	def invalidateConfigEntry(self, conf):
		for ent in self.list:
			if ent[1] is conf:
				self["config"].invalidate(ent)

class TimerLog(Screen):
	def __init__(self, session, timer):
		Screen.__init__(self, session)
		self.setTitle(_("Log"))

		self.timer = timer
		self.log_entries = self.timer.log_entries[:]

		self.fillLogList()

		self["loglist"] = MenuList(self.list)
		self["logentry"] = Label()

		self["key_red"] = Button(_("Delete entry"))
		self["key_blue"] = Button(_("Clear log"))

		self.onShown.append(self.updateText)

		self["actions"] = NumberActionMap(["OkCancelActions", "DirectionActions", "ColorActions"],
		{
			"ok": self.keyClose,
			"cancel": self.keyClose,
			"up": self.up,
			"down": self.down,
			"left": self.left,
			"right": self.right,
			"red": self.deleteEntry,
			"blue": self.clearLog
		}, -1)

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
		self["loglist"].instance.moveSelection(self["loglist"].instance.moveUp)
		self.updateText()

	def down(self):
		self["loglist"].instance.moveSelection(self["loglist"].instance.moveDown)
		self.updateText()

	def left(self):
		self["loglist"].instance.moveSelection(self["loglist"].instance.pageUp)
		self.updateText()

	def right(self):
		self["loglist"].instance.moveSelection(self["loglist"].instance.pageDown)
		self.updateText()

	def updateText(self):
		if self.list:
			self["logentry"].setText(str(self["loglist"].getCurrent()[1][2]))
		else:
			self["logentry"].setText("")

class InstantRecordTimerEntry(TimerEntry):
	def __init__(self, session, timer, zap):
		Screen.__init__(self, session)
		self.timer = timer
		self.timer.justplay = zap
		self.keySave()

	def keySave(self, result = None):
		if self.timer.justplay:
			self.timer.end = self.timer.begin + (config.recording.margin_before.value * 60) + 1
		self.timer.resetRepeated()
		self.saveTimer()

	def retval(self):
		return self.timer

	def saveTimer(self):
		self.session.nav.RecordTimer.saveTimer()
