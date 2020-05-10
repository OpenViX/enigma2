from time import time

from enigma import ePoint, eServiceCenter, eServiceReference, eTimer

from RecordTimer import AFTEREVENT, RecordTimerEntry, parseEvent
from ServiceReference import ServiceReference
from Components.ActionMap import ActionMap, HelpableActionMap, HelpableNumberActionMap
from Components.Button import Button
from Components.EpgBouquetList import EPGBouquetList
from Components.Label import Label
from Components.Sources.Event import Event
from Components.Sources.ServiceEvent import ServiceEvent
from Components.UsageConfig import preferredTimerPath
from Components.config import ConfigClock, ConfigDateTime, config, configfile
from Screens.ChoiceBox import ChoiceBox
from Screens.EventView import EventViewEPGSelect
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.PictureInPicture import PictureInPicture
from Screens.Screen import Screen
from Screens.TimeDateInput import TimeDateInput
from Screens.TimerEdit import TimerSanityConflict
from Screens.TimerEntry import InstantRecordTimerEntry, TimerEntry


# PiPServiceRelation installed?
try:
	from Plugins.SystemPlugins.PiPServiceRelation.plugin import getRelationDict
	plugin_PiPServiceRelation_installed = True
except ImportError:
	plugin_PiPServiceRelation_installed = False

def ignoreLongKeyPress(action):
	def fn():
		from Screens.InfoBar import InfoBar
		if not InfoBar.instance.LongButtonPressed:
			action()
	return fn

def getServiceRefStr(service):
	return ":".join(service.ref.toString().split(":")[:11])


class EPGSelectionBase(Screen, HelpableScreen):
	lastEnteredTime = None
	lastEnteredDate = None
	EMPTY = 0
	ADD_TIMER = 1
	REMOVE_TIMER = 2
	ZAP = 1

	def __init__(self, session, epgConfig, startBouquet=None, startRef=None, bouquets=None):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)

		self.epgConfig = epgConfig
		self.bouquets = bouquets
		self.originalPlayingServiceOrGroup = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.startBouquet = startBouquet
		self.startRef = startRef
		self.choiceBoxDialog = None
		self.closeRecursive = False
		self.eventviewDialog = None
		self.eventviewWasShown = False
		self.session.pipshown = False
		self.pipServiceRelation = getRelationDict() if plugin_PiPServiceRelation_installed else {}
		self["Service"] = ServiceEvent()
		self["Event"] = Event()
		self["lab1"] = Label(_("Please wait while gathering EPG data..."))
		self["lab1"].hide()
		self["key_red"] = Button(_("IMDb Search"))
		self["key_green"] = Button(_("Add Timer"))
		self["key_yellow"] = Button(_("EPG Search"))
		self["key_blue"] = Button(_("Add AutoTimer"))

		helpDescription = _("EPG Commands")
		self["dialogactions"] = HelpableActionMap(self, "WizardActions", {
			"back": (self.closeChoiceBoxDialog, _("Close dialog box")),
		}, prio=-1, description=helpDescription)
		self["dialogactions"].setEnabled(False)
		self["okactions"] = HelpableActionMap(self, "OkCancelActions", {
			"cancel": (self.closeScreen, _("Exit EPG")),
			"OK": (ignoreLongKeyPress(self.OK), _("Zap to channel/service")),
			"OKLong": (self.OKLong, _("Zap to channel/service and close"))
		}, prio=-1, description=helpDescription)
		self["colouractions"] = HelpableActionMap(self, "ColorActions", {
			"red": (ignoreLongKeyPress(self.openIMDb), _("IMDB search for current event")),
			"redlong": (self.sortEPG, _("Sort the EPG list")),
			"green": (ignoreLongKeyPress(self.addEditTimer), _("Add/Remove timer for current event")),
			"greenlong": (self.openTimerList, _("Show timer list")),
			"yellow": (ignoreLongKeyPress(self.openEPGSearch), _("Search for similar events")),
			"blue": (ignoreLongKeyPress(self.addAutoTimer), _("Add an autotimer for current event")),
			"bluelong": (self.openAutoTimerList, _("Show autotimer list"))
		}, prio=-1, description=helpDescription)
		self["recordingactions"] = HelpableActionMap(self, "InfobarInstantRecord", {
			"ShortRecord": (self.recordTimerQuestion, _("Add a record timer for current event")),
			"LongRecord": (self.doZapTimer, _("Add a zap timer for current event"))
		}, prio=-1, description=helpDescription)
		self["epgactions"] = HelpableActionMap(self, "EPGSelectActions", {}, -1)

		self.noAutotimer = _("The AutoTimer plugin is not installed!\nPlease install it.")
		self.noEPGSearch = _("The EPGSearch plugin is not installed!\nPlease install it.")
		self.noIMDb = _("The IMDb plugin is not installed!\nPlease install it.")
		self.refreshTimer = eTimer()
		self.refreshTimer.timeout.get().append(self.refreshList)
		self.onLayoutFinish.append(self.onCreate)

	def moveUp(self):
		self["list"].moveTo(self["list"].instance.moveUp)

	def moveDown(self):
		self["list"].moveTo(self["list"].instance.moveDown)

	def nextPage(self):
		self["list"].moveTo(self["list"].instance.pageDown)

	def prevPage(self):
		self["list"].moveTo(self["list"].instance.pageUp)

	def toTop(self):
		self["list"].moveTo(self["list"].instance.moveTop)

	def toEnd(self):
		self["list"].moveTo(self["list"].instance.moveEnd)

	def openEventView(self):
		def openSimilarList(eventId, refstr):
			from Screens.EpgSelectionSimilar import EPGSelectionSimilar
			self.session.open(EPGSelectionSimilar, refstr, eventId)

		event, service = self["list"].getCurrent()[:2]
		if event is not None:
			self.session.open(EventViewEPGSelect, event, service, callback=self.eventViewCallback, similarEPGCB=openSimilarList)

	def sortEPG(self):
		self.closeEventViewDialog()

	def addEditTimer(self):
		self.closeEventViewDialog()
		self.recordTimerQuestion(True)

	def enterDateTime(self):
		if not EPGSelectionBase.lastEnteredTime:
			# The stored date and time is shared by all EPG types.
			EPGSelectionBase.lastEnteredTime = ConfigClock(default=time())
			EPGSelectionBase.lastEnteredDate = ConfigDateTime(default=time(), formatstring=config.usage.date.full.value, increment=86400)
		self.session.openWithCallback(self.onDateTimeInputClosed, TimeDateInput, EPGSelectionBase.lastEnteredTime, EPGSelectionBase.lastEnteredDate)

	def openSingleEPG(self):
		from Screens.EpgSelectionChannel import EPGSelectionChannel
		event, service = self["list"].getCurrent()[:2]
		if service is not None and service.ref is not None:
			self.session.open(EPGSelectionChannel, service.ref, time() if event is None else event.getBeginTime())

	def openIMDb(self):
		self.closeEventViewDialog()
		try:
			from Plugins.Extensions.IMDb.plugin import IMDB, IMDBEPGSelection
			try:
				event = self["list"].getCurrent()[0]
				if event is None:
					return
				name = event.getEventName()
			except Exception:
				name = ""

			self.session.open(IMDB, name, False)
		except ImportError:
			self.session.open(MessageBox, self.noIMDb, type=MessageBox.TYPE_INFO, timeout=10)

	def openEPGSearch(self):
		self.closeEventViewDialog()
		try:
			from Plugins.Extensions.EPGSearch.EPGSearch import EPGSearch
			try:
				event = self["list"].getCurrent()[0]
				if event is None:
					return
				name = event.getEventName()
			except Exception:
				name = ""
			self.session.open(EPGSearch, name, False)
		except ImportError:
			self.session.open(MessageBox, self.noEPGSearch, type=MessageBox.TYPE_INFO, timeout=10)

	def addAutoTimer(self):
		self.closeEventViewDialog()
		try:
			from Plugins.Extensions.AutoTimer.AutoTimerEditor import addAutotimerFromEvent
			event, service = self["list"].getCurrent()[:2]
			if event is None:
				return
			addAutotimerFromEvent(self.session, evt=event, service=service)
			self.refreshTimer.start(3000)
		except ImportError:
			self.session.open(MessageBox, self.noAutotimer, type=MessageBox.TYPE_INFO, timeout=10)

	def addAutoTimerSilent(self):
		try:
			from Plugins.Extensions.AutoTimer.AutoTimerEditor import addAutotimerFromEventSilent
			event, service = self["list"].getCurrent()[:2]
			if event is None:
				return
			addAutotimerFromEventSilent(self.session, evt=event, service=service)
			self.refreshTimer.start(3000)
		except ImportError:
			self.session.open(MessageBox, self.noAutotimer, type=MessageBox.TYPE_INFO, timeout=10)

	def openTimerList(self):
		self.closeEventViewDialog()
		from Screens.TimerEdit import TimerEditList
		self.session.open(TimerEditList, selectItem=self["list"].getCurrent()[:2])

	def openAutoTimerList(self):
		self.closeEventViewDialog()
		global autopoller
		global autotimer
		try:
			from Plugins.Extensions.AutoTimer.AutoPoller import AutoPoller
			from Plugins.Extensions.AutoTimer.AutoTimer import AutoTimer
			from Plugins.Extensions.AutoTimer.plugin import autostart, main
			autopoller = AutoPoller()
			autotimer = AutoTimer()
			try:
				autotimer.readXml()
			except SyntaxError as se:
				self.session.open(MessageBox, _("Your config file is not well formed:\n%s") % str(se), type=MessageBox.TYPE_ERROR, timeout=10)
				return

			if autopoller is not None:
				autopoller.stop()
			from Plugins.Extensions.AutoTimer.AutoTimerOverview import AutoTimerOverview
			self.session.openWithCallback(self.editCallback, AutoTimerOverview, autotimer)
		except ImportError:
			self.session.open(MessageBox, self.noAutotimer, type=MessageBox.TYPE_INFO, timeout=10)

	def editCallback(self, session):
		global autopoller
		global autotimer
		if session is not None:
			autotimer.writeXml()
			autotimer.parseEPG()
		if config.plugins.autotimer.autopoll.value:
			if autopoller is None:
				from Plugins.Extensions.AutoTimer.AutoPoller import AutoPoller
				autopoller = AutoPoller()
			autopoller.start()
		else:
			autopoller = None
			autotimer = None

	def timerAdd(self):
		self.recordTimerQuestion(True)

	def editTimer(self, timer):
		self.session.open(TimerEntry, timer)

	def removeTimer(self, timer):
		self.closeChoiceBoxDialog()
		timer.afterEvent = AFTEREVENT.NONE
		self.session.nav.RecordTimer.removeEntry(timer)
		self["key_green"].setText(_("Add Timer"))
		self.refreshList()

	def disableTimer(self, timer):
		self.closeChoiceBoxDialog()
		timer.disable()
		self.session.nav.RecordTimer.timeChanged(timer)
		self["key_green"].setText(_("Add Timer"))
		self.refreshList()

	def recordTimerQuestion(self, manual=False):
		event, serviceref = self["list"].getCurrent()[:2]
		if event is None:
			return
		eventId = event.getEventId()
		refstr = getServiceRefStr(serviceref)
		title = None
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventId and refstr == getServiceRefStr(timer.service_ref):
				menu = [
					(_("Delete Timer"), "CALLFUNC", self.removeChoiceBoxCB, lambda ret: self.removeTimer(timer)),
					(_("Edit Timer"), "CALLFUNC", self.removeChoiceBoxCB, lambda ret: self.editTimer(timer)),
					(_("Disable Timer"), "CALLFUNC", self.removeChoiceBoxCB, lambda ret: self.disableTimer(timer))
				]
				title = _("Select action for timer %s:") % event.getEventName()
				break
		else:
			if not manual:
				menu = [
					(_("Add Timer"), "CALLFUNC", self.choiceBoxCB, self.doRecordTimer),
					(_("Add AutoTimer"), "CALLFUNC", self.choiceBoxCB, self.addAutoTimerSilent)
				]
				title = "%s?" % event.getEventName()
			else:
				newEntry = RecordTimerEntry(serviceref, checkOldTimers=True, dirname=preferredTimerPath(), *parseEvent(event))
				self.session.openWithCallback(self.finishedAdd, TimerEntry, newEntry)
		if title:
			self.choiceBoxDialog = self.session.instantiateDialog(ChoiceBox, title=title, list=menu, keys=["green", "blue"], skin_name="RecordTimerQuestion")
			posy = self["list"].getSelectionPosition()
			self.choiceBoxDialog.instance.move(ePoint(posy[0] - self.choiceBoxDialog.instance.size().width(), self.instance.position().y() + posy[1]))
			self.showChoiceBoxDialog()

	def removeChoiceBoxCB(self, choice):
		self.closeChoiceBoxDialog()
		if choice:
			choice(self)

	def choiceBoxCB(self, choice):
		self.closeChoiceBoxDialog()
		if choice:
			try:
				choice()
			except Exception:
				choice

	def showChoiceBoxDialog(self):
		self["okactions"].setEnabled(False)
		if "epgcursoractions" in self:
			self["epgcursoractions"].setEnabled(False)
		self["colouractions"].setEnabled(False)
		self["recordingactions"].setEnabled(False)
		self["epgactions"].setEnabled(False)
		self["dialogactions"].setEnabled(True)
		self.choiceBoxDialog["actions"].execBegin()
		self.choiceBoxDialog.show()
		if "input_actions" in self:
			self["input_actions"].setEnabled(False)

	def closeChoiceBoxDialog(self):
		self["dialogactions"].setEnabled(False)
		if self.choiceBoxDialog:
			self.choiceBoxDialog["actions"].execEnd()
			self.session.deleteDialog(self.choiceBoxDialog)
		self["okactions"].setEnabled(True)
		if "epgcursoractions" in self:
			self["epgcursoractions"].setEnabled(True)
		self["colouractions"].setEnabled(True)
		self["recordingactions"].setEnabled(True)
		self["epgactions"].setEnabled(True)
		if "input_actions" in self:
			self["input_actions"].setEnabled(True)

	def doRecordTimer(self):
		self.doInstantTimer(0)

	def doZapTimer(self):
		self.doInstantTimer(1)

	def doInstantTimer(self, zap):
		event, service = self["list"].getCurrent()[:2]
		if event is None:
			return
		newEntry = RecordTimerEntry(service, checkOldTimers=True, *parseEvent(event))
		self.instantRecordDialog = self.session.instantiateDialog(InstantRecordTimerEntry, newEntry, zap)
		retval = [True, self.instantRecordDialog.retval()]
		self.session.deleteDialogWithCallback(self.finishedAdd, self.instantRecordDialog, retval)

	def finishedAdd(self, answer):
		if answer[0]:
			entry = answer[1]
			simulTimerList = self.session.nav.RecordTimer.record(entry)
			if simulTimerList is not None:
				for x in simulTimerList:
					if x.setAutoincreaseEnd(entry):
						self.session.nav.RecordTimer.timeChanged(x)
				simulTimerList = self.session.nav.RecordTimer.record(entry)
				if simulTimerList is not None:
					if not entry.repeated and not config.recording.margin_before.value and not config.recording.margin_after.value and len(simulTimerList) > 1:
						changeTime = False
						conflictBegin = simulTimerList[1].begin
						conflictEnd = simulTimerList[1].end
						if conflictBegin == entry.end:
							entry.end -= 30
							changeTime = True
						elif entry.begin == conflictEnd:
							entry.begin += 30
							changeTime = True
						if changeTime:
							simulTimerList = self.session.nav.RecordTimer.record(entry)
					if simulTimerList is not None:
						self.session.openWithCallback(self.finishSanityCorrection, TimerSanityConflict, simulTimerList)
			self["key_green"].setText(_("Change Timer"))
		else:
			self["key_green"].setText(_("Add Timer"))
		self.refreshList()

	def finishSanityCorrection(self, answer):
		self.finishedAdd(answer)

	def onSelectionChanged(self):
		event, service = self["list"].getCurrent()[:2]
		self["Event"].newEvent(event)
		if service is None:
			self["Service"].newService(None)
		else:
			self["Service"].newService(service.ref)
		if service is None or service.getServiceName() == "":
			self["key_green"].setText("")
			return
		if event is None:
			self["key_green"].setText("")
			return
		eventId = event.getEventId()
		refstr = getServiceRefStr(service)
		isRecordEvent = False
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventId and refstr == getServiceRefStr(timer.service_ref):
				isRecordEvent = True
				break
		self["key_green"].setText(_("Change Timer") if isRecordEvent else _("Add Timer"))

	def closeEventViewDialog(self):
		if self.eventviewDialog:
			self.eventviewDialog.hide()
			del self.eventviewDialog
			self.eventviewDialog = None


class EPGServiceZap:
	def __init__(self, zapFunc):
		self.prevch = None
		self.currch = None
		self.zapFunc = zapFunc

	def OK(self):
		if self.epgConfig.btn_ok.value == "zap":
			self.zap()
		else:
			self.zapExit()

	def OKLong(self):
		if self.epgConfig.btn_oklong.value == "zap":
			self.zap()
		else:
			self.zapExit()

	def zapExit(self):
		self.zapSelectedService()
		self.closeEventViewDialog()
		self.close("close")

	def zap(self):
		if self.session.nav.getCurrentlyPlayingServiceOrGroup() and "0:0:0:0:0:0:0:0:0" in self.session.nav.getCurrentlyPlayingServiceOrGroup().toString():
			from Screens.InfoBarGenerics import setResumePoint
			setResumePoint(self.session)
		self.zapSelectedService(True)
		self.refreshTimer.start(1)
		if not self.currch or self.currch == self.prevch:
			self.zapFunc(None, False)
			self.closeEventViewDialog()
			self.close("close")

	def closeScreen(self):
		closeParam = True

		# When exiting, restore the previous service/playback if a channel has been previewed.
		if self.originalPlayingServiceOrGroup and self.session.nav.getCurrentlyPlayingServiceOrGroup() and self.session.nav.getCurrentlyPlayingServiceOrGroup().toString() != self.originalPlayingServiceOrGroup.toString():
			if self.epgConfig.preview_mode.value:
				if "0:0:0:0:0:0:0:0:0" in self.originalPlayingServiceOrGroup.toString():
  					# Restart movie playback, MoviePlayer screen is still active.
  					from Screens.InfoBar import MoviePlayer
					if MoviePlayer.instance:
						MoviePlayer.instance.forceNextResume()
				self.session.nav.playService(self.originalPlayingServiceOrGroup)
			else:
				if "0:0:0:0:0:0:0:0:0" in self.originalPlayingServiceOrGroup.toString():
					# Previously we were in playback, so we'll need to close the movie player
					closeParam = 'closemovieplayer'
				# Not preview mode and service has been changed before exiting, record it with the zap history
				self.zapFunc(None, False)
		if self.session.pipshown:
			self.session.pipshown = False
			del self.session.pip
		self.closeEventViewDialog()
		self.close(closeParam)

	def zapSelectedService(self, prev=False):
		currservice = self.session.nav.getCurrentlyPlayingServiceReference() and str(self.session.nav.getCurrentlyPlayingServiceReference().toString()) or None
		if self.session.pipshown:
			self.prevch = self.session.pip.getCurrentService() and str(self.session.pip.getCurrentService().toString()) or None
		else:
			self.prevch = self.session.nav.getCurrentlyPlayingServiceReference() and str(self.session.nav.getCurrentlyPlayingServiceReference().toString()) or None
		service = self["list"].getCurrent()[1]
		if service is not None:
			if self.epgConfig.preview_mode.value == "2":
				if not prev:
					if self.session.pipshown:
						self.session.pipshown = False
						del self.session.pip
					self.zapFunc(service.ref, bouquet=self.getCurrentBouquet(), preview=False)
					return
				if not self.session.pipshown:
					self.session.pip = self.session.instantiateDialog(PictureInPicture)
					self.session.pip.show()
					self.session.pipshown = True
				pipPluginService = self.pipServiceRelation.get(str(service.ref), None)
				if pipPluginService is not None:
					serviceRef = eServiceReference(pipPluginService)
				else:
					serviceRef = service.ref
				if self.currch == serviceRef.toString():
					if self.session.pipshown:
						self.session.pipshown = False
						del self.session.pip
					self.zapFunc(service.ref, bouquet=self.getCurrentBouquet(), preview=False)
					return
				if self.prevch != serviceRef.toString() and currservice != serviceRef.toString():
					self.session.pip.playService(serviceRef)
					self.currch = self.session.pip.getCurrentService() and str(self.session.pip.getCurrentService().toString())
			else:
				self.zapFunc(service.ref, bouquet=self.getCurrentBouquet(), preview=prev)
				self.currch = self.session.nav.getCurrentlyPlayingServiceReference() and str(self.session.nav.getCurrentlyPlayingServiceReference().toString())


class EPGServiceNumberSelection:
	def __init__(self):
		self.numberZapTimer = eTimer()
		self.numberZapTimer.callback.append(self.__OK)
		self.numberZapField = None

		self["numberzapokactions"] = HelpableActionMap(self, "OkCancelActions", {
			"cancel": (self.__cancel, _("Close number zap.")),
			"OK": (self.__OK, _("Change to service")),
		}, prio=-1, description=_("Service/Channel number zap commands"))
		self["numberzapokactions"].setEnabled(False)
		helpMsg = _("Enter a number to jump to a service/channel")
		self["input_actions"] = HelpableNumberActionMap(self, "NumberActions", 
			dict([(str(i), (self.keyNumberGlobal, helpMsg)) for i in range(0,9)]),
			prio=-1, description=_("Service/Channel number zap commands"))

		self["zapbackground"] = Label()
		self["zapbackground"].hide()
		self["zapnumber"] = Label()
		self["zapnumber"].hide()
		self["zapservice"] = ServiceEvent()
		self["zapservice"].newService(None)
		self["number"] = Label()
		self["number"].hide()

	def keyNumberGlobal(self, number):
		self["epgcursoractions"].setEnabled(False)
		self["okactions"].setEnabled(False)
		self["numberzapokactions"].setEnabled(True)
		if config.misc.zapkey_delay.value > 0:
			self.numberZapTimer.start(1000*config.misc.zapkey_delay.value, True)
		if self.numberZapField is None:
			self.numberZapField = str(number)
		else:
			self.numberZapField += str(number)
		from Screens.InfoBar import InfoBar
		service, bouquet = InfoBar.instance.searchNumber(int(self.numberZapField))
		self["zapbackground"].show()
		self["zapnumber"].setText(self.numberZapField)
		self["zapnumber"].show()
		self["zapservice"].newService(service)
		if self["number"].skinAttributes:
		 	serviceName = ServiceReference(service).getServiceName()
		 	self["number"].setText("%s\n%s" % (serviceName, self.numberZapField))
			self["number"].show()

		if len(self.numberZapField) >= 4:
			self.__OK()

	def __OK(self):
		if self.numberZapField is not None:
			# It's preferable to reuse the InfoBar searchNumber over copying the implementation
			from Screens.InfoBar import InfoBar
			service, bouquet = InfoBar.instance.searchNumber(int(self.numberZapField))
			if service is not None:
				self.startRef = service
				self.startBouquet = bouquet
				self.onCreate()
		self.__cancel()

	def __cancel(self):
		self.numberZapField = None
		self.numberZapTimer.stop()
		self["epgcursoractions"].setEnabled(True)
		self["okactions"].setEnabled(True)
		self["numberzapokactions"].setEnabled(False)
		self["zapbackground"].hide()
		self["zapnumber"].hide()
		self["zapservice"].newService(None)
		self["number"].hide()


class EPGBouquetSelection:
	lastBouquet = None
	lastService = None
	lastPlaying = None

	def __init__(self, graphic):
		self.services = []
		self.selectedBouquetIndex = -1

		self["bouquetlist"] = EPGBouquetList(graphic)
		self["bouquetlist"].hide()
		self.bouquetlistActive = False

		self["bouquetokactions"] = ActionMap(["OkCancelActions"], {
			"cancel": self.__cancel,
			"OK": self.__OK,
		}, -1)
		self["bouquetokactions"].setEnabled(False)

		self["bouquetcursoractions"] = ActionMap(["DirectionActions"], {
			"left": self.moveBouquetPageUp,
			"right": self.moveBouquetPageDown,
			"up": self.moveBouquetUp,
			"down": self.moveBouquetDown
		}, -1)
		self["bouquetcursoractions"].setEnabled(False)

		self.onClose.append(self.__onClose)
		if self.epgConfig.browse_mode.value == "lastepgservice":
			if EPGBouquetSelection.lastPlaying and self.startRef and EPGBouquetSelection.lastBouquet and EPGBouquetSelection.lastPlaying == self.startRef:
				self.startBouquet = EPGBouquetSelection.lastBouquet
				self.startRef = EPGBouquetSelection.lastService and EPGBouquetSelection.lastService.ref
			EPGBouquetSelection.lastPlaying = self.session.nav.getCurrentlyPlayingServiceOrGroup()

	def __onClose(self):
		EPGSelectionBase.onSelectionChanged(self)
		if self.epgConfig.browse_mode.value == "lastepgservice":
			EPGBouquetSelection.lastBouquet = self.getCurrentBouquet()
			EPGBouquetSelection.lastService = self.getCurrentService()

	def getBouquetServices(self, bouquet):
		servicelist = eServiceCenter.getInstance().list(bouquet)
		if servicelist:
			# Use getContent() instead of getNext() so that the list
			# is sorted according to the "ORDER BY" mechanism.
			return [ServiceReference(service) for service in servicelist.getContent("R", True) if not (service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker))]
		return []

	def _populateBouquetList(self):
		self["bouquetlist"].recalcEntrySize()
		self["bouquetlist"].fillBouquetList(self.bouquets)

		self.selectedBouquetIndex = 0
		if self.startBouquet is not None:
			index = 0
			for bouquet in self.bouquets:
				if bouquet[1] == self.startBouquet:
					self.selectedBouquetIndex = index
					break
				index += 1
		self["bouquetlist"].setCurrentIndex(self.selectedBouquetIndex)
		self.services = self.getBouquetServices(self.startBouquet)

	def toggleBouquetList(self):
		# Do nothing if the skin doesn't contain a bouquetlist
		if not self["bouquetlist"].skinAttributes:
			return
		if not self.bouquetlistActive:
			self.bouquetListShow()
		else:
			self.__cancel()

	def __OK(self):
		self.setBouquetIndex(self["bouquetlist"].instance.getCurrentIndex())
		self.bouquetListHide()

	def __cancel(self):
		self.bouquetListHide()
		self["bouquetlist"].setCurrentIndex(self.selectedBouquetIndex)

	def bouquetListShow(self):
		self["epgcursoractions"].setEnabled(False)
		self["okactions"].setEnabled(False)
		self["bouquetlist"].setCurrentIndex(self.selectedBouquetIndex)
		self["bouquetlist"].show()
		self["bouquetokactions"].setEnabled(True)
		self["bouquetcursoractions"].setEnabled(True)
		self.bouquetlistActive = True

	def bouquetListHide(self):
		self["bouquetokactions"].setEnabled(False)
		self["bouquetcursoractions"].setEnabled(False)
		self["bouquetlist"].hide()
		self["okactions"].setEnabled(True)
		self["epgcursoractions"].setEnabled(True)
		self.bouquetlistActive = False

	def moveBouquetUp(self):
		self["bouquetlist"].moveTo(self["bouquetlist"].instance.moveUp)

	def moveBouquetDown(self):
		self["bouquetlist"].moveTo(self["bouquetlist"].instance.moveDown)

	def moveBouquetPageUp(self):
		self["bouquetlist"].moveTo(self["bouquetlist"].instance.pageUp)

	def moveBouquetPageDown(self):
		self["bouquetlist"].moveTo(self["bouquetlist"].instance.pageDown)

	def getCurrentBouquet(self):
		return self.bouquets[self.selectedBouquetIndex][1] if self.selectedBouquetIndex >= 0 else None

	def getCurrentBouquetName(self):
		return self.bouquets[self.selectedBouquetIndex][0] if self.selectedBouquetIndex >= 0 else None

	def nextBouquet(self):
		self.setBouquetIndex(self.selectedBouquetIndex + 1)

	def prevBouquet(self):
		self.setBouquetIndex(self.selectedBouquetIndex - 1)

	def setBouquetIndex(self, index):
		self.selectedBouquetIndex = index % len(self.bouquets)
		self.services = self.getBouquetServices(self.getCurrentBouquet())
		self.selectedServiceIndex = 0 if len(self.services) > 0 else -1
		self.bouquetChanged()


class EPGServiceBrowse(EPGBouquetSelection):
	def __init__(self):
		EPGBouquetSelection.__init__(self, False)
		self.selectedServiceIndex = -1

	def _populateBouquetList(self):
		EPGBouquetSelection._populateBouquetList(self)
		if len(self.services) == 0:
			return
		if self.startRef is None:
			self.selectedServiceIndex = 0
		else:
			index = 0
			for service in self.services:
				if service.ref == self.startRef:
					self.selectedServiceIndex = index
					break
				index += 1

	def getCurrentService(self):
		return self.services[self.selectedServiceIndex] if self.selectedServiceIndex >= 0 else ServiceReference("0:0:0:0:0:0:0:0:0")

	def nextService(self):
		self.selectedServiceIndex += 1
		if self.selectedServiceIndex >= len(self.services):
			if config.usage.quickzap_bouquet_change.value:
				self.selectedBouquetIndex = (self.selectedBouquetIndex + 1) % len(self.bouquets)
				self.services = self.getBouquetServices(self.getCurrentBouquet())
			self.selectedServiceIndex = 0 if len(self.services) > 0 else -1
		self.serviceChanged()

	def prevService(self):
		self.selectedServiceIndex -= 1
		if self.selectedServiceIndex < 0:
			if config.usage.quickzap_bouquet_change.value:
				self.selectedBouquetIndex = (self.selectedBouquetIndex - 1) % len(self.bouquets)
				self.services = self.getBouquetServices(self.getCurrentBouquet())
			self.selectedServiceIndex = len(self.services) - 1 if len(self.services) > 0 else -1
		self.serviceChanged()
