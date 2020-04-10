from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile
from Components.Epg.EpgListSingle import EPGListSingle
from Components.Epg.EpgListBase import EPG_TYPE_SINGLE
from EpgSelectionBase import EPGSelectionBase
from Screens.Setup import Setup
from ServiceReference import ServiceReference

class EPGSelectionSingle(EPGSelectionBase):
	def __init__(self, session, service, time_focus = None):
		print "[EPGSelectionSingle] ------- NEW VERSION -------"
		EPGSelectionBase.__init__(self, EPG_TYPE_SINGLE, session, startRef = service)

		self.skinName = 'EPGSelection'
		self['epgactions'] = HelpableActionMap(self, 'EPGSelectActions',
			{
				'info': (self.openEventView, _('Show detailed event info')),
				'epg': (self.openEventView, _('Show detailed event info')),
				'menu': (self.createSetup, _('Setup menu'))
			}, -1)
		self['epgcursoractions'] = HelpableActionMap(self, 'DirectionActions',
			{
				'left': (self.prevPage, _('Move up a page')),
				'right': (self.nextPage, _('Move down a page')),
				'up': (self.moveUp, _('Go to previous channel')),
				'down': (self.moveDown, _('Go to next channel'))
			}, -1)

		self['list'] = EPGListSingle(selChangedCB = self.onSelectionChanged, timer = session.nav.RecordTimer,
			itemsPerPageConfig = config.epgselection.enhanced_itemsperpage,
			eventfsConfig = config.epgselection.enhanced_eventfs,
			time_focus = time_focus)

	def createSetup(self):
		self.closeEventViewDialog()
		self.session.openWithCallback(self.onSetupClose, Setup, 'epgsingle')

	def onSetupClose(self, test = None):
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self['list'].setFontsize()
		self['list'].setItemsPerPage()
		self['list'].recalcEntrySize()

	def onCreate(self):
		self['list'].recalcEntrySize()
		service = ServiceReference(self.startRef)
		self['Service'].newService(service.ref)
		title = service.getServiceName()
		self.setTitle(title)
		self['list'].fillEPG(service)
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self.show()

	def refreshList(self):
		self.refreshTimer.stop()
		index = self['list'].getCurrentIndex()
		self['list'].fillEPG(ServiceReference(self.startRef))
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self['list'].setCurrentIndex(index)

	def eventViewCallback(self, setEvent, setService, val):
		if val == -1:
			self.moveUp()
		elif val == +1:
			self.moveDown()
		event, service = self['list'].getCurrent()[:2]
		setService(service)
		setEvent(event)

	def OK(self):
		self.closeScreen()

	def OKLong(self):
		self.closeScreen()

	def sortEPG(self):
		if config.epgselection.sort.value == '0':
			config.epgselection.sort.setValue('1')
		else:
			config.epgselection.sort.setValue('0')
		config.epgselection.sort.save()
		configfile.save()
		self['list'].sortEPG(int(config.epgselection.sort.value))

	def closeScreen(self):
		self.closeEventViewDialog()
		self.close()
