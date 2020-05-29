from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.EpgListSingle import EPGListSingle
from Screens.EpgSelectionBase import EPGSelectionBase, EPGStandardButtons


class EPGSelectionSimilar(EPGSelectionBase, EPGStandardButtons):
	def __init__(self, session, service, eventId):
		EPGSelectionBase.__init__(self, session, config.epgselection.single)

		self.skinName = ["SingleEPG", "EPGSelection"]
		self.currentService = service
		self.eventId = eventId

		self["list"] = EPGListSingle(session, selChangedCB=self.onSelectionChanged, epgConfig=config.epgselection.single)

	def onCreate(self):
		self["list"].recalcEntrySize()
		self["list"].fillSimilarList(self.currentService, self.eventId)
		self.show()

	def refreshList(self):
		self.refreshTimer.stop()

	def OK(self):
		self.closeScreen()

	def OKLong(self):
		self.closeScreen()

	def closeScreen(self):
		self.closeEventViewDialog()
		self.close()
