from time import time

from enigma import ePoint, eServiceCenter, eServiceReference, eTimer

from RecordTimer import AFTEREVENT, RecordTimerEntry, parseEvent
from Components.ActionMap import ActionMap, HelpableActionMap, HelpableNumberActionMap
from Components.Button import Button
from Components.EpgBouquetList import EPGBouquetList
from Components.Label import Label
from Components.Sources.Event import Event
from Components.Sources.ServiceEvent import ServiceEvent
from Components.UsageConfig import preferredTimerPath
from Components.config import ConfigClock, ConfigDateTime, config
from Screens.ChoiceBox import PopupChoiceBox
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

epgActions = [
	# function name, button label, help text
	("", _("Do nothing")),
	("openIMDb", _("IMDb Search"), _("IMDB search for current event")),
	("sortEPG", _("Sort"), _("Sort the EPG list")),
	("addEditTimer", _("Add Timer"), _("Add/Remove timer for current event")),
	("openTimerList", _("Show Timer List")),
	("openEPGSearch", _("EPG Search"), _("Search for similar events")),
	("addEditAutoTimer", _("Add AutoTimer"), _("Add/Edit an autotimer for current event")),
	("openAutoTimerList", _("AutoTimer List"), _("Show autotimer list")),
	("forward24Hours", _("+24 hours"), _("Go forward 24 hours")),
	("back24Hours", _("-24 hours"), _("Go back 24 hours")),
	("openEventView", _("Event Info"), _("Show detailed event info")),
	("openSingleEPG", _("Single EPG"), _("Show Single EPG")),
	("showMovies", _("Recordings"), _("Show recorded movies"))
]

okActions = [
	("zap",_("Zap")),
	("zapExit", _("Zap + Exit")),
	("openEventView", _("Event Info"), _("Show detailed event info"))
]

recActions = [
	("addEditTimerMenu", _("Timer Menu"), _("Add a record timer or an autotimer for current event")),
	("addEditTimer", _("Add Timer"), _("Add and edit a record timer for current event")),
	("addEditTimerSilent", _("Create Timer"), _("Add a record timer for current event")),
	("addEditZapTimerSilent", _("Create Zap Timer"), _("Add a zap timer for current event")),
	("addEditAutoTimer", _("Add AutoTimer"), _("Add an autotimer for current event"))
]

infoActions = [
	("", _("Do nothing")),
	("openEventView", _("Event Info"), _("Show detailed event info")),
	("openSingleEPG", _("Single EPG"), _("Show Single EPG")),
	("switchToSingleEPG", _("Switch to Single EPG")),
	("switchToGridEPG", _("Switch to Grid EPG")),
	("switchToMultiEPG", _("Switch to Multi EPG"))
]

channelUpActions = [
	("forward24Hours", _("+24 hours"), _("Go forward 24 hours")),
	("prevPage", _("Page up"))
]

channelDownActions = [
	("back24Hours", _("-24 hours"), _("Go back 24 hours")),
	("nextPage", _("Page down"))
]

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
		self.startBouquet = startBouquet
		self.startRef = startRef
		self.popupDialog = None
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

		self["okactions"] = HelpableActionMap(self, "OkCancelActions", {
			"cancel": (self.closeScreen, _("Exit EPG")),
			"OK": (self.helpKeyAction("ok")),
			"OKLong": (self.helpKeyAction("oklong"))
		}, prio=-1, description=helpDescription)

		self["colouractions"] = HelpableActionMap(self, "ColorActions", {
			"red": self.helpKeyAction("red"),
			"redlong": self.helpKeyAction("redlong"),
			"green": self.helpKeyAction("green"),
			"greenlong": self.helpKeyAction("greenlong"),
			"yellow": self.helpKeyAction("yellow"),
			"yellowlong": self.helpKeyAction("yellowlong"),
			"blue": self.helpKeyAction("blue"),
			"bluelong": self.helpKeyAction("bluelong")
		}, prio=-1, description="EPG Commands")
		self._updateButtonText()

		self["recordingactions"] = HelpableActionMap(self, "InfobarInstantRecord", {
			"ShortRecord": self.helpKeyAction("rec"),
			"LongRecord": self.helpKeyAction("reclong")
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

	def enterDateTime(self):
		if not EPGSelectionBase.lastEnteredTime:
			# The stored date and time is shared by all EPG types.
			EPGSelectionBase.lastEnteredTime = ConfigClock(default=time())
			EPGSelectionBase.lastEnteredDate = ConfigDateTime(default=time(), formatstring=config.usage.date.full.value, increment=86400)
		self.session.openWithCallback(self.onDateTimeInputClosed, TimeDateInput, EPGSelectionBase.lastEnteredTime, EPGSelectionBase.lastEnteredDate)

	def showMovies(self):
		from Screens.InfoBar import InfoBar
		InfoBar.instance.showMovies() 

	def openSingleEPG(self):
		from Screens.EpgSelectionChannel import EPGSelectionChannel
		event, service = self["list"].getCurrent()[:2]
		if service is not None:
			self.session.open(EPGSelectionChannel, service, time() if event is None else event.getBeginTime())

	def switchToSingleEPG(self):
		from Screens.EpgSelectionSingle import EPGSelectionSingle
		event, service = self["list"].getCurrent()[:2]
		if service is not None:
			self.close("open", EPGSelectionSingle, self.getCurrentBouquet(), service, self.bouquets, time() if event is None else event.getBeginTime())

	def switchToGridEPG(self):
		from Screens.EpgSelectionGrid import EPGSelectionGrid
		event, service = self["list"].getCurrent()[:2]
		if service is not None:
			self.close("open", EPGSelectionGrid, self.getCurrentBouquet(), service, self.bouquets, time() if event is None else event.getBeginTime())

	def switchToMultiEPG(self):
		from Screens.EpgSelectionMulti import EPGSelectionMulti
		event, service = self["list"].getCurrent()[:2]
		if service is not None:
			self.close("open", EPGSelectionMulti, self.getCurrentBouquet(), service, self.bouquets, time() if event is None else event.getBeginTime())

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

	def addEditAutoTimer(self):
		self.closeEventViewDialog()
		event, service = self["list"].getCurrent()[:2]
		if event is None:
			return
		timer = self.session.nav.RecordTimer.getTimerForEvent(service, event)
		if timer is not None and timer.autoTimerId:
			self.editAutoTimer(timer)
		else:
			self.addAutoTimer()

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

	def editAutoTimer(self, timer):
		try:
			from Plugins.Extensions.AutoTimer.AutoTimerEditor import editAutotimerFromTimer
			editAutotimerFromTimer(self.session, timer)
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

	def editTimer(self, timer):
		def callback(ret):
			self.refreshList()
		self.session.openWithCallback(callback, TimerEntry, timer)

	def removeTimer(self, timer):
		self.closePopupDialog()
		timer.afterEvent = AFTEREVENT.NONE
		self.session.nav.RecordTimer.removeEntry(timer)
		self.setActionButtonText("addEditTimer", _("Add Timer"))
		self.refreshList()

	def disableTimer(self, timer):
		self.closePopupDialog()
		timer.disable()
		self.session.nav.RecordTimer.timeChanged(timer)
		self.setActionButtonText("addEditTimer", _("Add Timer"))
		self.refreshList()

	def addEditTimerMenu(self):
		def callback(choice):
			self.closePopupDialog()
			if choice:
				choice()

		self.closeEventViewDialog()
		event, service = self.__timerEditPopupMenu()
		if event is not None:
			if event.getBeginTime() + event.getDuration() <= time():
				return
			self.__popupMenu(
					"%s?" % event.getEventName(),
					[(_("Add Timer"), "CALLFUNC", callback, self.doInstantTimer),
					(_("Add AutoTimer"), "CALLFUNC", callback, self.addAutoTimerSilent)])

	def addEditTimer(self):
		self.closeEventViewDialog()
		event, service = self.__timerEditPopupMenu()
		if event is not None:
			newEntry = RecordTimerEntry(service, checkOldTimers=True, dirname=preferredTimerPath(), *parseEvent(event, service=service))
			self.session.openWithCallback(self.finishedAdd, TimerEntry, newEntry)

	def addEditTimerSilent(self):
		self.closeEventViewDialog()
		event, service = self.__timerEditPopupMenu()
		if event is not None:
			self.doInstantTimer(0)

	def addEditZapTimerSilent(self):
		self.closeEventViewDialog()
		event, service = self.__timerEditPopupMenu()
		if event is not None:
			self.doInstantTimer(1)

	def __timerEditPopupMenu(self):
		def callback(choice):
			self.closePopupDialog()
			if choice:
				choice(self)

		event, service = self["list"].getCurrent()[:2]
		if event is None:
			return None, None
		timer = self.session.nav.RecordTimer.getTimerForEvent(service, event)
		if timer is not None:
			self.__popupMenu(
				_("Select action for timer %s:") % event.getEventName(),
				[(_("Delete Timer"), "CALLFUNC", callback, lambda ret: self.removeTimer(timer)),
				(_("Edit Timer"), "CALLFUNC", callback, lambda ret: self.editTimer(timer)),
				(_("Disable Timer"), "CALLFUNC", callback, lambda ret: self.disableTimer(timer))])
			return None, None
		return event, service

	def __popupMenu(self, title, menu):
		self.popupDialog = self.session.instantiateDialog(PopupChoiceBox, title=title, list=menu, keys=["green", "blue"], skin_name="RecordTimerQuestion", closeCB=self.closePopupDialog)
		pos = self["list"].getSelectionPosition()
		self.popupDialog.instance.move(ePoint(pos[0] - self.popupDialog.instance.size().width(), self.instance.position().y() + pos[1]))
		self.showPopupDialog()

	def showPopupDialog(self):
		self["okactions"].setEnabled(False)
		if "epgcursoractions" in self:
			self["epgcursoractions"].setEnabled(False)
		self["colouractions"].setEnabled(False)
		self["recordingactions"].setEnabled(False)
		self["epgactions"].setEnabled(False)
		if "numberactions" in self:
			self["numberactions"].setEnabled(False)
		self["helpActions"].setEnabled(False)
		self.popupDialog.show()

	def closePopupDialog(self):
		if self.popupDialog is not None:
			self.popupDialog.doClose()
			self.popupDialog = None
		self["okactions"].setEnabled(True)
		if "epgcursoractions" in self:
			self["epgcursoractions"].setEnabled(True)
		self["colouractions"].setEnabled(True)
		self["recordingactions"].setEnabled(True)
		self["epgactions"].setEnabled(True)
		if "numberactions" in self:
			self["numberactions"].setEnabled(True)
		self["helpActions"].setEnabled(True)

	def doInstantTimer(self, zap=0):
		event, service = self["list"].getCurrent()[:2]
		if event is None or event.getBeginTime() + event.getDuration() < time():
			return
		newEntry = RecordTimerEntry(service, checkOldTimers=True, *parseEvent(event, service=service))
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
			self.setActionButtonText("addEditTimer", _("Change Timer"))
		else:
			self.setActionButtonText("addEditTimer", _("Add Timer"))
		self.refreshList()

	def finishSanityCorrection(self, answer):
		self.finishedAdd(answer)

	def onSelectionChanged(self):
		event, service = self["list"].getCurrent()[:2]
		self["Event"].newEvent(event)
		if service is None:
			self["Service"].newService(None)
		else:
			self["Service"].newService(service)
		if service is None or service.getServiceName() == "":
			self.setActionButtonText("addEditTimer", "")
			return
		if event is None or event.getBeginTime() + event.getDuration() < time():
			self.setActionButtonText("addEditTimer", "")
			return
		timer = self.session.nav.RecordTimer.getTimerForEvent(service, event)
		self.setActionButtonText("addEditTimer", _("Change Timer") if timer is not None else _("Add Timer"))
		self.setActionButtonText("addEditAutoTimer", _("Edit AutoTimer") if timer is not None and timer.autoTimerId else _("Add AutoTimer"))

	def closeEventViewDialog(self):
		if self.eventviewDialog:
			self.eventviewDialog.hide()
			del self.eventviewDialog
			self.eventviewDialog = None


class EPGServiceZap:
	def __init__(self, zapFunc):
		self.__originalPlayingService = self.session.nav.getCurrentlyPlayingServiceOrGroup() or eServiceReference()
		self.prevch = None
		self.currch = None
		self.zapFunc = zapFunc

	def zapExit(self):
		selectedService = self["list"].getCurrent()[1]
		from Screens.InfoBar import MoviePlayer
		MoviePlayer.ensureClosed(selectedService)
		self.zapSelectedService()
		self.closeEventViewDialog()
		self.close()

	def zap(self):
		currentService = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if currentService and currentService.isPlayback():
			# in movie playback, so store the resume point before zapping
			from Screens.InfoBarGenerics import setResumePoint
			setResumePoint(self.session)
		self.zapSelectedService(True)
		self.refreshTimer.start(1)
		if not self.currch or self.currch == self.prevch:
			# Zapping the same service for a second time, record it with the zap history and exit
			from Screens.InfoBar import MoviePlayer
			MoviePlayer.ensureClosed(currentService)
			self.zapFunc(None, False)
			self.closeEventViewDialog()
			self.close()

	def closeScreen(self):
		# When exiting, restore the previous service/playback if a channel has been previewed.
		currentService = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if currentService and currentService.toString() != self.__originalPlayingService.toString():
			# service has changed from the original
			if self.epgConfig.preview_mode.value:
				# In preview mode, the original service or movie playback is restored
				if self.__originalPlayingService.isPlayback():
					# Restart movie playback at the resume point stored earlier
					from Screens.InfoBar import MoviePlayer
					if MoviePlayer.instance:
						MoviePlayer.instance.forceNextResume()
				self.session.nav.playService(self.__originalPlayingService)
			else:
				# In non-preview mode, stick with the now playing service; this means closing the movieplayer
				# if it's open, and setting the infobar's lastservice
				from Screens.InfoBar import MoviePlayer
				MoviePlayer.ensureClosed(currentService)
				self.zapFunc(None, False)
		if self.session.pipshown:
			self.session.pipshown = False
			del self.session.pip
		self.closeEventViewDialog()
		self.close()

	def zapSelectedService(self, prev=False):
		currservice = self.session.nav.getCurrentlyPlayingServiceReference() and self.session.nav.getCurrentlyPlayingServiceReference().toString() or None
		if self.session.pipshown:
			self.prevch = self.session.pip.getCurrentService() and self.session.pip.getCurrentService().toString() or None
		else:
			self.prevch = currservice
		service = self["list"].getCurrent()[1]
		if service is not None:
			if self.epgConfig.preview_mode.value == "2":
				if not prev:
					if self.session.pipshown:
						self.session.pipshown = False
						del self.session.pip
					self.zapFunc(service, bouquet=self.getCurrentBouquet(), preview=False)
					return
				if not self.session.pipshown:
					self.session.pip = self.session.instantiateDialog(PictureInPicture)
					self.session.pip.show()
					self.session.pipshown = True
				pipPluginService = self.pipServiceRelation.get(service.toString(), None)
				if pipPluginService is not None:
					serviceRef = pipPluginService
				else:
					serviceRef = service
				if self.currch == serviceRef.toString():
					if self.session.pipshown:
						self.session.pipshown = False
						del self.session.pip
					self.zapFunc(service, bouquet=self.getCurrentBouquet(), preview=False)
					return
				if self.prevch != serviceRef.toString() and currservice != serviceRef.toString():
					self.session.pip.playService(serviceRef)
					self.currch = self.session.pip.getCurrentService() and self.session.pip.getCurrentService().toString()
			else:
				self.zapFunc(service, bouquet=self.getCurrentBouquet(), preview=prev)
				self.currch = self.session.nav.getCurrentlyPlayingServiceReference() and self.session.nav.getCurrentlyPlayingServiceReference().toString()

class EPGServiceNumberSelectionPopup(Screen):
	def __init__(self, session, getServiceByNumber, callback, number):
		Screen.__init__(self, session)
		self.skinName = "EPGServiceNumberSelection"
		self.getServiceByNumber = getServiceByNumber
		self.callback = callback

		helpDescription = _("EPG Commands")
		helpMsg = _("Enter a number to jump to a service/channel")
		self["actions"] = HelpableNumberActionMap(self, "NumberActions", 
			dict([(str(i), (self.keyNumber, helpMsg)) for i in range(0,10)]),
			prio=-1, description=helpDescription)
		self["cancelaction"] = HelpableActionMap(self, "OkCancelActions", {
			"cancel": (self.__cancel, _("Exit channel selection")),
			"OK": (self.__OK, _("Select EPG channel"))
		}, prio=-1, description=helpDescription)

		self["number"] = Label()
		self["service"] = ServiceEvent()
		self["service"].newService(None)

		self.timer = eTimer()
		self.timer.callback.append(self.__OK)
		self.number = ""
		self.keyNumber(number)

	def show(self):
		self["actions"].execBegin()
		self["cancelaction"].execBegin()
		Screen.show(self)

	def hide(self):
		self["actions"].execEnd()
		self["cancelaction"].execEnd()
		Screen.hide(self)

	def keyNumber(self, number):
		if config.misc.zapkey_delay.value > 0:
			self.timer.start(1000*config.misc.zapkey_delay.value, True)
		self.number += str(number)
		service, bouquet = self.getServiceByNumber(int(self.number))
		self["number"].setText(self.number)
		self["service"].newService(service)

		if len(self.number) >= 4:
			self.__OK()

	def __OK(self):
		self.callback(int(self.number))

	def __cancel(self):
		self.callback(None)


class EPGServiceNumberSelection:
	def __init__(self):
		helpMsg = _("Enter a number to jump to a service/channel")
		self["numberactions"] = HelpableNumberActionMap(self, "NumberActions", 
			dict([(str(i), (self.keyNumberGlobal, helpMsg)) for i in range(0,10)]),
			prio=-1, description=_("Service/Channel number zap commands"))

	def keyNumberGlobal(self, number):
		def closed(number):
			self.closePopupDialog()
			if number is not None:
				service, bouquet = self.getServiceByNumber(number)
				if service is not None:
					self.startRef = service
					self.startBouquet = bouquet
					self.setBouquet(bouquet)
					self.bouquetChanged()
					self.moveToService(service)

		self.popupDialog = self.session.instantiateDialog(EPGServiceNumberSelectionPopup, self.getServiceByNumber, closed, number)
		self.showPopupDialog()


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
				self.startRef = EPGBouquetSelection.lastService and EPGBouquetSelection.lastService
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
			return [service for service in servicelist.getContent("R", True) if not (service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker))]
		return []

	def _populateBouquetList(self):
		self["bouquetlist"].recalcEntrySize()
		self["bouquetlist"].fillBouquetList(self.bouquets)
		self.setBouquet(self.startBouquet)

	def toggleBouquetList(self):
		# Do nothing if the skin doesn't contain a bouquetlist
		if not self["bouquetlist"].skinAttributes:
			return
		if not self.bouquetlistActive:
			self.bouquetListShow()
		else:
			self.__cancel()

	def __OK(self):
		self.bouquetListHide()
		self.setBouquetIndex(self["bouquetlist"].instance.getCurrentIndex())
		self.bouquetChanged()

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
		self.bouquetChanged()

	def prevBouquet(self):
		self.setBouquetIndex(self.selectedBouquetIndex - 1)
		self.bouquetChanged()

	def setBouquetIndex(self, index):
		self.selectedBouquetIndex = index % len(self.bouquets)
		self.services = self.getBouquetServices(self.getCurrentBouquet())
		self.selectedServiceIndex = 0 if len(self.services) > 0 else -1

	def setBouquet(self, bouquetRef):
		self.selectedBouquetIndex = 0
		if bouquetRef is not None:
			index = 0
			for bouquet in self.bouquets:
				if bouquet[1] == bouquetRef:
					self.selectedBouquetIndex = index
					break
				index += 1
		self["bouquetlist"].setCurrentIndex(self.selectedBouquetIndex)
		self.services = self.getBouquetServices(bouquetRef)
		self.selectedServiceIndex = 0 if len(self.services) > 0 else -1

	def getServiceByNumber(self, number):
		if config.usage.alternative_number_mode.value:
			for service in self.services:
				if service.getChannelNum() == number:
					return service, self.getCurrentBouquet()
		else:
			for bouquet in self.bouquets:
				services = self.getBouquetServices(bouquet[1])
				for service in services:
					if service.getChannelNum() == number:
						return service, bouquet[1]
		return None, None

class EPGServiceBrowse(EPGBouquetSelection):
	def __init__(self):
		EPGBouquetSelection.__init__(self, False)
		self.selectedServiceIndex = -1

	def _populateBouquetList(self):
		EPGBouquetSelection._populateBouquetList(self)
		if len(self.services) == 0:
			return
		self.setCurrentService(self.startRef)

	def setCurrentService(self, serviceRef):
		if serviceRef is None:
			self.selectedServiceIndex = 0
		else:
			index = 0
			for service in self.services:
				if service == serviceRef:
					self.selectedServiceIndex = index
					break
				index += 1

	def getCurrentService(self):
		return self.services[self.selectedServiceIndex] if self.selectedServiceIndex >= 0 else eServiceReference()

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


class EPGStandardButtons:
	def setActionButtonText(self, actionName, buttonText):
		# only need to cater for green button
		if actionName == "addEditTimer":
			self["key_green"].setText(buttonText)
		elif actionName == "addEditAutoTimer":
			self["key_blue"].setText(buttonText)

	# build a tuple suitable for using in a helpable action
	def helpKeyAction(self, actionName):
		actions = {
			"red": (self.openIMDb, _("IMDB search for current event")),
			"redlong": (self.sortEPG, _("Sort the EPG list")),
			"green": (self.addEditTimer, _("Add/Remove timer for current event")),
			"greenlong": (self.openTimerList, _("Show timer list")),
			"yellow": (self.openEPGSearch, _("Search for similar events")),
			"yellowlong": (lambda _ : None, _("Search for similar events")),
			"blue": (self.addEditAutoTimer, _("Add an autotimer for current event")),
			"bluelong": (self.openAutoTimerList, _("Show autotimer list")),
			"ok": (self.OK, _("Zap to channel/service")),
			"oklong": (self.OKLong, _("Zap to channel/service and close")),
			"rec": (self.addEditTimerMenu, _("Add a record timer for current event")),
			"reclong": (self.addEditZapTimerSilent, _("Add a zap timer for current event"))
		}
		return actions[actionName]

	def _updateButtonText(self):
		pass
