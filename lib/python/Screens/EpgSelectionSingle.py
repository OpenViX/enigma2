from time import localtime, mktime, strftime, time

from enigma import ePoint, eServiceCenter, eServiceReference, eTimer

from ServiceReference import ServiceReference
from Components.About import about
from Components.ActionMap import HelpableActionMap, HelpableNumberActionMap
from Components.Button import Button
from Components.config import ConfigClock, config, configfile
from Components.EpgListSingle import EPGListSingle
from Screens.EpgSelectionBase import EPGSelectionBase, EPGServiceNumberSelection, EPGServiceBrowse, EPGServiceZap
from Screens.HelpMenu import HelpableScreen
from Screens.Setup import Setup


class EPGSelectionSingle(EPGSelectionBase, EPGServiceNumberSelection, EPGServiceBrowse, EPGServiceZap):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets, timeFocus=None):
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
			"info": (self.openEventView, _("Show detailed event info")),
			"infolong": (self.openSingleEPG, _("Show single epg for current channel")),
			"tv": (self.toggleBouquetList, _("Toggle between bouquet/epg lists")),
			"timer": (self.openTimerList, _("Show timer list")),
			"timerlong": (self.openAutoTimerList, _("Show autotimer list")),
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

	def bouquetChanged(self):
		self.refreshList(time())

	def serviceChanged(self):
		self.refreshList(time())

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
