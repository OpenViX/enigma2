from time import localtime, mktime, time

from enigma import eTimer

from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile
from Components.EpgListGrid import EPGListGrid, MAX_TIMELINES, TimelineText
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.Event import Event
from Components.Sources.StaticText import StaticText
from Screens.EpgSelectionBase import EPGSelectionBase, EPGBouquetSelection, EPGServiceNumberSelection, EPGServiceZap, epgActions, infoActions, okActions
from Screens.EventView import EventViewSimple
from Screens.Setup import Setup
from Screens.UserDefinedButtons import UserDefinedButtons


class EPGSelectionGrid(EPGSelectionBase, EPGBouquetSelection, EPGServiceNumberSelection, EPGServiceZap, UserDefinedButtons):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets, timeFocus=None, isInfobar=False):
		self.epgConfig = config.epgselection.infobar if isInfobar else config.epgselection.grid
		UserDefinedButtons.__init__(self, self.epgConfig, epgActions, okActions, infoActions)
		EPGSelectionBase.__init__(self, session, self.epgConfig, startBouquet, startRef, bouquets)
		EPGServiceNumberSelection.__init__(self)
		EPGServiceZap.__init__(self, zapFunc)

		graphic = self.epgConfig.type_mode.value == "graphics"
		if not config.epgselection.grid.pig.value:
			self.skinName = ["GridEPG", "GraphicalEPG"]
		else:
			self.skinName = ["GridEPGPIG", "GraphicalEPGPIG"]
		self.closeRecursive = False
		EPGBouquetSelection.__init__(self, graphic)

		self["timeline_text"] = TimelineText(self.epgConfig, graphic)
		self["Event"] = Event()
		self["primetime"] = Label(_("PRIMETIME"))
		self["change_bouquet"] = Label(_("CHANGE BOUQUET"))
		self["jump"] = Label(_("JUMP 24 HOURS"))
		self["page"] = Label(_("PAGE UP/DOWN"))
		self["key_text"] = StaticText(_("TEXT"))
		self.timeLines = []
		for x in range(0, MAX_TIMELINES):
			pm = Pixmap()
			self.timeLines.append(pm)
			self["timeline%d" % x] = pm

		self["timeline_now"] = Pixmap()
		self.updateTimelineTimer = eTimer()
		self.updateTimelineTimer.callback.append(self.moveTimeLines)
		self.updateTimelineTimer.start(60000)

		helpDescription = _("EPG Commands")
		self["epgcursoractions"] = HelpableActionMap(self, "DirectionActions", {
			"left": (self.leftPressed, _("Go to previous event")),
			"right": (self.rightPressed, _("Go to next event")),
			"up": (self.moveUp, _("Go to previous channel")),
			"down": (self.moveDown, _("Go to next channel"))
		}, prio=-1, description=helpDescription)

		self["epgactions"] = HelpableActionMap(self, "EPGSelectActions", {
			"nextService": self.helpKeyAction("channelup"),
			"prevService": self.helpKeyAction("channeldown"),
			"nextBouquet": (self.nextBouquet, _("Go to next bouquet")),
			"prevBouquet": (self.prevBouquet, _("Go to previous bouquet")),
			"input_date_time": (self.enterDateTime, _("Go to specific date/time")),
			"epg": self.helpKeyAction("epg"),
			"epglong": self.helpKeyAction("epglong"),
			"info": self.helpKeyAction("info"),
			"infolong": self.helpKeyAction("infolong"),
			"tv": (self.toggleBouquetList, _("Toggle between bouquet/epg lists")),
			"tvlong": (self.togglePIG, _("Toggle picture In graphics")),
			"timer": (self.openTimerList, _("Show timer list")),
			"timerlong": (self.openAutoTimerList, _("Show autotimer list")),
			"back": (self.goToCurrentTimeOrServiceOrTop, _("Go to current time, then the start service, then home of list")),
			"menu": (self.createSetup, _("Setup menu"))
		}, prio=-1, description=helpDescription)

		if config.epgselection.grid.number_buttons_mode.value == "paging":
			self["numberactions"] = HelpableActionMap(self, "NumberActions", {
				"1": (self.reduceTimeScale, _("Reduce time scale")),
				"2": (self.prevPage, _("Page up")),
				"3": (self.increaseTimeScale, _("Increase time scale")),
				"4": (self.pageLeft, _("page left")),
				"5": (self.goToCurrentTime, _("Jump to current time")),
				"6": (self.pageRight, _("Page right")),
				"7": (self.toggleNumberOfRows, _("No of items switch (increase or reduced)")),
				"8": (self.nextPage, _("Page down")),
				"9": (self.goToPrimeTime, _("Jump to prime time")),
				"0": (self.goToCurrentTimeAndTop, _("Move to home of list"))
			}, prio=-1, description=helpDescription)
		self["list"] = EPGListGrid(session, isInfobar=isInfobar, selChangedCB=self.onSelectionChanged)
		self["list"].setTimeFocus(timeFocus or time())

	def createSetup(self):
		oldPIG = config.epgselection.grid.pig.value
		oldNumberButtonsMode = config.epgselection.grid.number_buttons_mode.value

		def onClose(test=None):
			if oldPIG != config.epgselection.grid.pig.value or oldNumberButtonsMode != config.epgselection.grid.number_buttons_mode.value:
				# skin needs changing - we have to reopen
				self.close("reopengrid")
			else:
				self.reloadConfig()
				self._updateButtonText()

		self.closeEventViewDialog()
		self.session.openWithCallback(onClose, Setup, "epggrid")

	def reloadConfig(self):
		graphic = self.epgConfig.type_mode.value == "graphics"
		self["list"].loadConfig()
		self["list"].setFontsize()
		self["list"].setItemsPerPage()
		self["list"].fillEPG()
		self["bouquetlist"].graphic = graphic
		self["bouquetlist"].setFontsize()
		self._populateBouquetList()
		self["timeline_text"].graphic = graphic
		self["timeline_text"].setFontsize()
		self["timeline_text"].setEntries(self["list"], self["timeline_now"], self.timeLines, True)

	def onCreate(self):
		self._populateBouquetList()
		self["list"].recalcEventSize()
		self["timeline_text"].setEntries(self["list"], self["timeline_now"], self.timeLines, False)
		self["lab1"].show()
		self.setTitle(self.getCurrentBouquetName())
		self.show()
		self.listTimer = eTimer()
		self.listTimer.callback.append(self.loadEPGData)
		self.listTimer.start(1, True)

	def loadEPGData(self):
		self["list"].fillEPGNoRefresh(self.services)
		if self.epgConfig.browse_mode.value != "firstservice":
			self["list"].moveToService(self.startRef)
		self.moveTimeLines()
		self["lab1"].hide()

	def refreshList(self):
		self.refreshTimer.stop()
		self["list"].fillEPG()
		self.moveTimeLines()

	def moveToService(self, serviceRef):
		self["list"].moveToService(serviceRef)

	def getCurrentService(self):
		service = self["list"].getCurrent()[1]
		return service

	def togglePIG(self):
		config.epgselection.grid.pig.setValue(not config.epgselection.grid.pig.value)
		config.epgselection.grid.pig.save()
		configfile.save()
		self.close("reopengrid")

	def updEvent(self, dir, visible=True):
		if self["list"].selEvent(dir, visible):
			self.moveTimeLines(True)

	def moveTimeLines(self, force=False):
		self.updateTimelineTimer.start((60 - int(time()) % 60) * 1000)
		self["timeline_text"].setEntries(self["list"], self["timeline_now"], self.timeLines, force)
		self["list"].l.invalidate()

	def leftPressed(self):
		self.updEvent(-1)

	def rightPressed(self):
		self.updEvent(+1)

	def bouquetChanged(self):
		self.setTitle(self.getCurrentBouquetName())
		list = self["list"]
		list.fillEPG(self.services)
		self.moveTimeLines(True)
		list.setCurrentIndex(0)

	def forward24Hours(self):
		self.updEvent(+24)

	def back24Hours(self):
		self.updEvent(-24)

	def onDateTimeInputClosed(self, ret):
		if len(ret) > 1 and ret[0]:
			self.goToTime(ret[1])

	def onSelectionChanged(self):
		EPGSelectionBase.onSelectionChanged(self)
		if self.eventviewDialog:
			self.eventviewDialog.hide()
			self.openEventViewDialog()

	def openEventViewDialog(self):
		event, service = self["list"].getCurrent()[:2]
		if event is not None:
			self.eventviewDialog = self.session.instantiateDialog(EventViewSimple, event, service, skin="InfoBarEventView")
			self.eventviewDialog.show()

	def eventViewCallback(self, setEvent, setService, val):
		list = self["list"]
		old = list.getCurrent()
		self.updEvent(val, False)
		cur = list.getCurrent()
		if cur[0] is None and cur[1].ref != old[1].ref:
			self.eventViewCallback(setEvent, setService, val)
		else:
			setService(cur[1])
			setEvent(cur[0])

	def reduceTimeScale(self):
		timeperiod = int(self.epgConfig.prevtimeperiod.value)
		if timeperiod > 60:
			timeperiod -= 30
			self["list"].setTimeEpoch(timeperiod)
			self.epgConfig.prevtimeperiod.setValue(str(timeperiod))
			self.moveTimeLines()

	def increaseTimeScale(self):
		timeperiod = int(self.epgConfig.prevtimeperiod.value)
		if timeperiod < 300:
			timeperiod += 30
			self["list"].setTimeEpoch(timeperiod)
			self.epgConfig.prevtimeperiod.setValue(str(timeperiod))
			self.moveTimeLines()

	def pageLeft(self):
		self.updEvent(-2)

	def pageRight(self):
		self.updEvent(+2)

	def goToCurrentTimeOrServiceOrTop(self):
		list = self["list"]
		oldEvent, service = list.getCurrent()
		self.goToTime(time())
		newEvent, service = list.getCurrent()
		if oldEvent and newEvent and oldEvent.getEventId() == newEvent.getEventId():
			if self.startRef and service and service.ref.toString() != self.startRef.toString():
				self.moveToService(self.startRef)
			else:
				self.toTop()

	def goToCurrentTime(self):
		self.goToTime(time())

	def goToPrimeTime(self):
		basetime = localtime(self["list"].getTimeBase())
		basetime = (basetime[0], basetime[1], basetime[2], self.epgConfig.primetime.value[0], self.epgConfig.primetime.value[1], 0, basetime[6], basetime[7], basetime[8])
		primetime = mktime(basetime)
		if primetime + 3600 < time():
			primetime += 86400
		self.goToTime(primetime)

	def goToCurrentTimeAndTop(self):
		self.toTop()
		self.goToCurrentTime()

	def goToTime(self, time):
		list = self["list"]
		# Place the entered time halfway across the grid.
		list.setTimeFocus(time)
		list.fillEPG()
		self.moveTimeLines(True)

	def toggleNumberOfRows(self):
		config.epgselection.grid.heightswitch.setValue(not config.epgselection.grid.heightswitch.value)
		self["list"].setItemsPerPage()
		self["list"].fillEPG()
		self.moveTimeLines()
