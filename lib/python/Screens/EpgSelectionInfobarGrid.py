from Components.config import config
from Screens.EpgSelectionBase import EPGServiceZap
from Screens.EpgSelectionGrid import EPGSelectionGrid
from Screens.EventView import EventViewSimple
from Screens.PictureInPicture import openPip, closePip
from Screens.Setup import Setup


# PiPServiceRelation installed?
try:
	from Plugins.SystemPlugins.PiPServiceRelation.plugin import getRelationDict
	plugin_PiPServiceRelation_installed = True
except ImportError:
	plugin_PiPServiceRelation_installed = False


class EPGSelectionInfobarGrid(EPGSelectionGrid):
	def __init__(self, session, zapFunc, startBouquet, startRef, bouquets):
		EPGSelectionGrid.__init__(self, session, zapFunc, startBouquet, startRef, bouquets, None, True)
		self.skinName = ["InfoBarGridEPG", "GraphicalInfoBarEPG"]
		self.__openedPip = False
		self.pipServiceRelation = getRelationDict() if plugin_PiPServiceRelation_installed else {}

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

	def closeScreen(self):
		EPGServiceZap.closeScreen(self)
		# be nice and only close the PiP if we actually opened a preview PiP 
		if self.__openedPip:
			closePip()

	def zapSelectedService(self, preview=False):
		if self.epgConfig.preview_mode.value != "2" or not preview:
			EPGServiceZap.zapSelectedService(self)
			return
		# Preview mode is set to PiP
		currentService = self.session.nav.getCurrentlyPlayingServiceReference() and self.session.nav.getCurrentlyPlayingServiceReference().toString() or None
		selectedService = self["list"].getCurrent()[1]
		if selectedService is None:
			return
		if self.session.pipshown:
			self.prevch = self.session.pip.getCurrentService() and self.session.pip.getCurrentService().toString() or None
		pipPluginService = self.pipServiceRelation.get(selectedService.toString(), None)
		serviceRef = pipPluginService or selectedService
		if self.currch == serviceRef.toString():
			closePip()
			self.zapFunc(selectedService, bouquet=self.getCurrentBouquet(), preview=False)
			return
		if self.prevch != serviceRef.toString() and currentService != serviceRef.toString():
			if openPip(serviceRef):
				self.__openedPip = True
			self.currch = self.session.pip.getCurrentService() and self.session.pip.getCurrentService().toString()
