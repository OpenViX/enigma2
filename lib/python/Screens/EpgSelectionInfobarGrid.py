from Components.config import config
from EpgSelectionGrid import EPGSelectionGrid
from Screens.Setup import Setup

class EPGSelectionInfobarGrid(EPGSelectionGrid):
	def __init__(self, session, zapFunc = None, startBouquet = None, startRef = None, bouquets = None):
		EPGSelectionGrid.__init__(self, session, config.epgselection.infobar, True, zapFunc, startBouquet, startRef, bouquets)
		self.skinName = ['InfoBarGridEPG', 'GraphicalInfoBarEPG']

	def createSetup(self):
		def onSetupClose(test = None):
			self.close('reopeninfobargrid')

		self.closeEventViewDialog()
		self.session.openWithCallback(onSetupClose, Setup, 'epginfobargrid')

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
