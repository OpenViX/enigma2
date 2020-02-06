from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.EpgListSingle import EPGListSingle
from EpgSelectionBase import EPGSelectionBase

class EPGSelectionSimilar(EPGSelectionBase):
	def __init__(self, session, service, eventId):
		EPGSelectionBase.__init__(self, session)

		self.skinName = ['SingleEPG', 'EPGSelection']
		self.currentService = service
		self.eventId = eventId

		self['list'] = EPGListSingle(selChangedCB=self.onSelectionChanged, timer=session.nav.RecordTimer,
			epgConfig = config.epgselection.single)

	def onCreate(self):
		self['list'].recalcEntrySize()
		self['list'].fillSimilarList(self.currentService, self.eventId)
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
