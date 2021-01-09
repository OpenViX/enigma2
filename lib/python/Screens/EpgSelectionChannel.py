from time import time
from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile
from Components.EpgListSingle import EPGListSingle
from Screens.EpgSelectionBase import EPGSelectionBase, EPGStandardButtons
from Screens.Setup import Setup


class EPGSelectionChannel(EPGSelectionBase, EPGStandardButtons):
	def __init__(self, session, service, timeFocus=None):
		EPGSelectionBase.__init__(self, session, config.epgselection.single, startRef=service)

		self.skinName = ["SingleEPG", "EPGSelection"]

		helpDescription = _("EPG Commands")
		self["okactions"] = HelpableActionMap(self, "OkCancelActions", {
			"cancel": (self.closeScreen, _("Exit EPG")),
			"OK": (self.OK, _("Close")),
			"OKLong": (self.OKLong, _("Close"))
		}, prio=-1, description=helpDescription)
		self["epgactions"] = HelpableActionMap(self, "EPGSelectActions", {
			"info": (self.openEventView, _("Show detailed event info")),
			"epg": (self.openEventView, _("Show detailed event info")),
			"menu": (self.createSetup, _("Setup menu"))
		}, prio=-1, description=helpDescription)
		self["epgcursoractions"] = HelpableActionMap(self, "DirectionActions", {
			"left": (self.prevPage, _("Move up a page")),
			"right": (self.nextPage, _("Move down a page")),
			"up": (self.moveUp, _("Go to previous channel")),
			"down": (self.moveDown, _("Go to next channel"))
		}, prio=-1, description=helpDescription)

		self.timeFocus = timeFocus or time()
		self["list"] = EPGListSingle(session, config.epgselection.single, self.onSelectionChanged)

	def createSetup(self):
		def onClose(test=None):
			self["list"].sortEPG()
			self["list"].setFontsize()
			self["list"].setItemsPerPage()
			self["list"].recalcEntrySize()

 		self.closeEventViewDialog()
		self.session.openWithCallback(onClose, Setup, "epgsingle")

	def onCreate(self):
		self["list"].recalcEntrySize()
		service = self.startRef
		self["Service"].newService(service.ref)
		title = service.getServiceName()
		self.setTitle(title)
		self["list"].fillEPG(service)
		self["list"].selectEventAtTime(self.timeFocus)
		self.show()

	def refreshList(self):
		self.refreshTimer.stop()
		index = self["list"].getCurrentIndex()
		self["list"].fillEPG(self.startRef)
		self["list"].setCurrentIndex(index)

	def eventViewCallback(self, setEvent, setService, val):
		if val == -1:
			self.moveUp()
		elif val == +1:
			self.moveDown()
		event, service = self["list"].getCurrent()[:2]
		setService(service)
		setEvent(event)

	def OK(self):
		self.closeScreen()

	def OKLong(self):
		self.closeScreen()

	def sortEPG(self):
		if config.epgselection.sort.value == "0":
			config.epgselection.sort.setValue("1")
		else:
			config.epgselection.sort.setValue("0")
		config.epgselection.sort.save()
		configfile.save()
		self["list"].sortEPG()

	def closeScreen(self):
		self.closeEventViewDialog()
		self.close()
