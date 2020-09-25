# -*- coding: utf-8 -*-
from time import localtime, time, strftime

from enigma import eEPGCache

from Screens.Screen import Screen
import ChannelSelection
from ServiceReference import ServiceReference
from Components.config import config, ConfigSelection, ConfigText, ConfigYesNo
from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo
from Components.UsageConfig import defaultMoviePath
from Screens.TimerEntryBase import TimerEntryBase, TimerLogBase
from Screens.MovieSelection import getPreferredTagEditor
from Screens.LocationBox import MovieLocationBox
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from RecordTimer import AFTEREVENT


class TimerEntry(TimerEntryBase):
	def __init__(self, session, timer):
		TimerEntryBase.__init__(self, session, timer, "timerentry")

	def createConfig(self):
		TimerEntryBase.createConfig(self)
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

		self.timerentry_justplay = ConfigSelection(choices = [
			("zap", _("zap")), ("record", _("record")), ("zap+record", _("zap and record"))],
			default = {0: "record", 1: "zap", 2: "zap+record"}[justplay + 2*always_zap])
		if SystemInfo["DeepstandbySupport"]:
			shutdownString = _("go to deep standby")
		else:
			shutdownString = _("shut down")
		self.timerentry_afterevent = ConfigSelection(choices = [("nothing", _("do nothing")), ("standby", _("go to standby")), ("deepstandby", shutdownString), ("auto", _("auto"))], default = afterevent)
		self.timerentry_recordingtype = ConfigSelection(choices = [("normal", _("normal")), ("descrambled+ecm", _("descramble and record ecm")), ("scrambled+ecm", _("don't descramble, record ecm"))], default = recordingtype)
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

		self.timerentry_renamerepeat = ConfigYesNo(default = rename_repeat)

		self.timerentry_pipzap = ConfigYesNo(default = pipzap)
		self.timerentry_conflictdetection = ConfigYesNo(default = conflict_detection)

		self.timerentry_showendtime = ConfigSelection(default = False, choices = [(True, _("yes")), (False, _("no"))])

		default = self.timer.dirname or defaultMoviePath()
		tmp = config.movielist.videodirs.value
		if default not in tmp:
			tmp.append(default)
		self.timerentry_dirname = ConfigSelection(default = default, choices = tmp)

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
		elif cur and isinstance(cur[1], ConfigText):
			self.renameEntry()
		else:
			Setup.keySelect(self)

	def finishedChannelSelection(self, *args):
		if args:
			self.timerentry_service_ref = ServiceReference(args[0])
			self.timerentry_service.setCurrentText(self.timerentry_service_ref.getServiceName())
			self.invalidateConfigEntry(self.timerentry_service)

	def getBeginEnd(self):
		begin, end = TimerEntryBase.getBeginEnd(self)

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

		TimerEntryBase.keySave(self)

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

	def incrementEnd(self):
		if self.timerentry_showendtime.value or self.timerentry_justplay.value != "zap":
			TimerEntryBase.incrementEnd(self)

	def decrementEnd(self):
		if self.timerentry_showendtime.value or self.timerentry_justplay.value != "zap":
			TimerEntryBase.decrementEnd(self)

	def subserviceSelected(self, service):
		if not service is None:
			self.timer.service_ref = ServiceReference(service[1])
		self.saveTimer()
		self.close((True, self.timer))

	def saveTimer(self):
		self.session.nav.RecordTimer.saveTimer()

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

class TimerLog(TimerLogBase):
	pass

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
