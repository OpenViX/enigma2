from time import time

from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile
from Components.EpgListSingle import EPGListSingle
from Screens.EpgSelectionBase import EPGSelectionBase, EPGServiceZap, EPGServiceBrowse, epgActions, okActions
from Screens.Setup import Setup
from Screens.UserDefinedButtons import UserDefinedButtons


class EPGSelectionInfobarSingle(EPGSelectionBase, EPGServiceZap, EPGServiceBrowse, UserDefinedButtons):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets):
		UserDefinedButtons.__init__(self, config.epgselection.infobar, epgActions, okActions)
		EPGSelectionBase.__init__(self, session, config.epgselection.infobar, startBouquet, startRef, bouquets)
		EPGServiceZap.__init__(self, zapFunc)

		self.skinName = ["InfobarSingleEPG", "QuickEPG"]

		EPGServiceBrowse.__init__(self)

		helpDescription = _("EPG Commands")
		self["epgactions"] = HelpableActionMap(self, "EPGSelectActions", {
			"nextBouquet": (self.nextBouquet, _("Go to next bouquet")),
			"prevBouquet": (self.prevBouquet, _("Go to previous bouquet")),
			"nextService": (self.nextPage, _("Move down a page")),
			"prevService": (self.prevPage, _("Move up a page")),
			"epg": (self.openSingleEPG, _("Show single epg for current channel")),
			"info": (self.openEventView, _("Show detailed event info")),
			"infolong": (self.openSingleEPG, _("Show single epg for current channel")),
			"timer": (self.openTimerList, _("Show timer list")),
			"timerlong": (self.openAutoTimerList, _("Show autotimer list")),
			"menu": (self.createSetup, _("Setup menu"))
		}, prio=-1, description=helpDescription)
		self["epgcursoractions"] = HelpableActionMap(self, "DirectionActions", {
			"left": (self.prevService, _("Go to previous channel")),
			"right": (self.nextService, _("Go to next channel")),
			"up": (self.moveUp, _("Go to previous channel")),
			"down": (self.moveDown, _("Go to next channel"))
		}, prio=-1, description=helpDescription)

		self["list"] = EPGListSingle(session, epgConfig=config.epgselection.infobar, selChangedCB=self.onSelectionChanged)

	def createSetup(self):
		def onClose(test=None):
			if config.epgselection.infobar.type_mode.value != "single":
				# switching to other infobar EPG type
				self.close("reopeninfobar")
			else:
				self._updateButtonText()
				self["list"].sortEPG()
				self["list"].setFontsize()
				self["list"].setItemsPerPage()
				self["list"].recalcEntrySize()

		self.closeEventViewDialog()
		self.session.openWithCallback(onClose, Setup, "epginfobarsingle")

	def onCreate(self):
		self._populateBouquetList()
		self["list"].recalcEntrySize()
		self.refreshList()
		self["list"].selectEventAtTime(time())
		self.show()

	def refreshList(self):
		self.refreshTimer.stop()
		service = self.getCurrentService()
		self["Service"].newService(service.ref)
		self.setTitle("%s - %s" % (self.getCurrentBouquetName(), service.getServiceName()))
		index = self["list"].getCurrentIndex()
		self["list"].fillEPG(service)
		self["list"].setCurrentIndex(index)

	def bouquetChanged(self):
		self.refreshList()

	def serviceChanged(self):
		self.refreshList()

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
