from time import time
from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile
from Components.EpgListSingle import EPGListSingle
from Screens.EpgSelectionBase import EPGSelectionBase, EPGServiceNumberSelection, EPGServiceBrowse, EPGServiceZap, epgActions, okActions
from Screens.Setup import Setup
from Screens.UserDefinedButtons import UserDefinedButtons


class EPGSelectionSingle(EPGSelectionBase, EPGServiceNumberSelection, EPGServiceBrowse, EPGServiceZap, UserDefinedButtons):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets, timeFocus=None):
		UserDefinedButtons.__init__(self, config.epgselection.single, epgActions, okActions)
		EPGSelectionBase.__init__(self, session, config.epgselection.single, startBouquet, startRef, bouquets)
		EPGServiceNumberSelection.__init__(self)
		EPGServiceZap.__init__(self, zapFunc)

		self.skinName = ["SingleEPG", "EPGSelection"]
		EPGServiceBrowse.__init__(self)

		helpDescription = _("EPG Commands")
		self["epgactions"] = HelpableActionMap(self, "EPGSelectActions", {
			"nextBouquet": (self.nextBouquet, _("Go to next bouquet")),
			"prevBouquet": (self.prevBouquet, _("Go to previous bouquet")),
			"nextService": (self.nextService, _("Go to next channel")),
			"prevService": (self.prevService, _("Go to previous channel")),
			"epg": self.helpKeyAction("epg"),
			"epglong": self.helpKeyAction("epglong"),
			"info": self.helpKeyAction("info"),
			"infolong": self.helpKeyAction("infolong"),
			"tv": (self.toggleBouquetList, _("Toggle between bouquet/epg lists")),
			"timer": (self.openTimerList, _("Show timer list")),
			"timerlong": (self.openAutoTimerList, _("Show autotimer list")),
			"back": (self.goToCurrentTimeOrService, _("Go to current time, then the start service")),
			"menu": (self.createSetup, _("Setup menu"))
		}, prio=-1, description=helpDescription)
		self["epgcursoractions"] = HelpableActionMap(self, "DirectionActions", {
			"left": (self.prevPage, _("Move up a page")),
			"right": (self.nextPage, _("Move down a page")),
			"up": (self.moveUp, _("Go to previous channel")),
			"down": (self.moveDown, _("Go to next channel"))
		}, prio=-1, description=helpDescription)

		self.timeFocus = timeFocus or time()

		self["list"] = EPGListSingle(session, selChangedCB=self.onSelectionChanged, epgConfig=config.epgselection.single)

	def createSetup(self):
		def onClose(test=None):
			self["list"].sortEPG()
			self["list"].setFontsize()
			self["list"].setItemsPerPage()
			self["list"].recalcEntrySize()
			self._updateButtonText()

		self.closeEventViewDialog()
		self.session.openWithCallback(onClose, Setup, "epgsingle")

	def onCreate(self):
		self._populateBouquetList()
		self["list"].recalcEntrySize()
		self.refreshList(self.timeFocus)
		self.show()

	def refreshList(self, selectTime=None):
		self.refreshTimer.stop()
		service = self.getCurrentService()
		self["Service"].newService(service.ref)
		self.setTitle("%s - %s" % (self.getCurrentBouquetName(), service.getServiceName()))
		index = self["list"].getCurrentIndex()
		self["list"].fillEPG(service)
		if selectTime is not None:
			self["list"].selectEventAtTime(selectTime)
		else:
			self["list"].setCurrentIndex(index)

	def moveToService(self, serviceRef):
		self.setCurrentService(serviceRef)
		self.refreshList(self.timeFocus)

	def bouquetChanged(self):
		self.refreshList(self.timeFocus)

	def serviceChanged(self):
		self.refreshList(self.timeFocus)

	def moveUp(self):
		EPGSelectionBase.moveUp(self)
		self.timeFocus = self["list"].getSelectedEventStartTime() or time()

	def moveDown(self):
		EPGSelectionBase.moveDown(self)
		self.timeFocus = self["list"].getSelectedEventStartTime() or time()

	def nextPage(self):
		EPGSelectionBase.nextPage(self)
		self.timeFocus = self["list"].getSelectedEventStartTime() or time()

	def prevPage(self):
		EPGSelectionBase.prevPage(self)
		self.timeFocus = self["list"].getSelectedEventStartTime() or time()

	def toTop(self):
		EPGSelectionBase.toTop(self)
		self.timeFocus = self["list"].getSelectedEventStartTime() or time()

	def toEnd(self):
		EPGSelectionBase.toEnd(self)
		self.timeFocus = self["list"].getSelectedEventStartTime() or time()

	def eventViewCallback(self, setEvent, setService, val):
		if val == -1:
			self.moveUp()
		elif val == +1:
			self.moveDown()
		event, service = self["list"].getCurrent()[:2]
		setService(service)
		setEvent(event)

	def sortEPG(self):
		if config.epgselection.sort.value == "0":
			config.epgselection.sort.setValue("1")
		else:
			config.epgselection.sort.setValue("0")
		config.epgselection.sort.save()
		configfile.save()
		self["list"].sortEPG()

	def goToCurrentTimeOrService(self):
		list = self["list"]
		oldEvent, service = list.getCurrent()
		self.timeFocus = time()
		self.refreshList(self.timeFocus)
		newEvent, service = list.getCurrent()
		if oldEvent and newEvent and oldEvent.getEventId() == newEvent.getEventId():
			if self.startRef and service and service.ref.toString() != self.startRef.toString():
				self.moveToService(self.startRef)

	def forward24Hours(self):
		self.timeFocus = (self["list"].getSelectedEventStartTime() or time()) + 86400
		self.refreshList(self.timeFocus)

	def back24Hours(self):
		self.timeFocus = (self["list"].getSelectedEventStartTime() or time()) - 86400
		self.refreshList(self.timeFocus)
