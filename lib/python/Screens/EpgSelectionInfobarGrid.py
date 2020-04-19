from Components.config import config
from Screens.EpgSelectionGrid import EPGSelectionGrid
from Screens.Setup import Setup


class EPGSelectionInfobarGrid(EPGSelectionGrid):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets):
		EPGSelectionGrid.__init__(self, session, zapFunc, startBouquet, startRef, bouquets, isInfobar=True)
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
		self.openEventView()

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
