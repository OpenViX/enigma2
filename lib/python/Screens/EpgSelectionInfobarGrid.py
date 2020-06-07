from Components.config import config
from Screens.EpgSelectionBase import epgActions, infoActions, okActions
from Screens.EpgSelectionGrid import EPGSelectionGrid
from Screens.EventView import EventViewSimple
from Screens.Setup import Setup


class EPGSelectionInfobarGrid(EPGSelectionGrid):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets):
		EPGSelectionGrid.__init__(self, session, zapFunc, startBouquet, startRef, bouquets, None, True)
		self.skinName = ["InfoBarGridEPG", "GraphicalInfoBarEPG"]

	def createSetup(self):
		def onClose(test=None):
			if config.epgselection.infobar.type_mode.value == "single":
				# switching to other infobar EPG type
				self.close("reopeninfobar")
			else:
				self.reloadConfig()

		self.closeEventViewDialog()
		self.session.openWithCallback(onClose, Setup, "epginfobargrid")

	def infoPressed(self):
		event, service = self["list"].getCurrent()[:2]
		if event is not None:
			self.eventviewDialog = self.session.instantiateDialog(EventViewSimple, event, service, skin='InfoBarEventView')
			self.eventviewDialog.show()

	def infoLongPressed(self):
		self.openSingleEPG()

	def openEventView(self):
		if self.eventviewDialog:
			self.eventviewDialog.hide()
			del self.eventviewDialog
			self.eventviewDialog = None
		else:
			self.openEventViewDialog()

	def toggleNumberOfRows(self):
		pass
