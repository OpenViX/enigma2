from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.Epg.EpgListSingle import EPGListSingle
from Components.Epg.EpgListBase import EPG_TYPE_SIMILAR
from EpgSelectionBase import EPGSelectionBase

class EPGSelectionSimilar(EPGSelectionBase):
	def __init__(self, session, service, eventid):
		print "[EPGSelectionSimilar] ------- NEW VERSION -------"
		EPGSelectionBase.__init__(self, EPG_TYPE_SIMILAR, session)

		self.skinName = 'EPGSelection'
		self.currentService = service
		self.eventid = eventid

		self['list'] = EPGListSingle(selChangedCB=self.onSelectionChanged, timer=session.nav.RecordTimer,
			itemsPerPageConfig = config.epgselection.enhanced_itemsperpage,
			eventfsConfig = config.epgselection.enhanced_eventfs)

	def onCreate(self):
		self['list'].recalcEntrySize()
		self['list'].fillSimilarList(self.currentService, self.eventid)
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
