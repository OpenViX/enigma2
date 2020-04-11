from enigma import eServiceReference

from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile
from Components.Epg.EpgListSingle import EPGListSingle
from EpgSelectionBase import EPGSelectionBase, EPGServiceZap
from Components.Sources.Event import Event
from Screens.Setup import Setup
from ServiceReference import ServiceReference

class EPGSelectionInfobarSingle(EPGSelectionBase, EPGServiceZap):
	def __init__(self, session, servicelist, zapFunc):
		EPGSelectionBase.__init__(self, session)
		EPGServiceZap.__init__(self, config.epgselection.infobar, zapFunc)

		self.skinName = ['InfobarSingleEPG', 'QuickEPG']
		self['epgactions'] = HelpableActionMap(self, 'EPGSelectActions',
			{
				'nextBouquet': (self.nextBouquet, _('Go to next bouquet')),
				'prevBouquet': (self.prevBouquet, _('Go to previous bouquet')),
				'nextService': (self.nextPage, _('Move down a page')),
				'prevService': (self.prevPage, _('Move up a page')),
				'epg': (self.openSingleEPG, _('Show single epg for current channel')),
				'info': (self.openEventView, _('Show detailed event info')),
				'infolong': (self.openSingleEPG, _('Show single epg for current channel')),
				'menu': (self.createSetup, _('Setup menu'))
			}, -1)
		self['epgcursoractions'] = HelpableActionMap(self, 'DirectionActions',
			{
				'left': (self.prevService, _('Go to previous channel')),
				'right': (self.nextService, _('Go to next channel')),
				'up': (self.moveUp, _('Go to previous channel')),
				'down': (self.moveDown, _('Go to next channel'))
			}, -1)
		self.servicelist = servicelist

		self['list'] = EPGListSingle(selChangedCB=self.onSelectionChanged, timer=session.nav.RecordTimer, 
			epgConfig=config.epgselection.infobar)

	def createSetup(self):
		self.closeEventViewDialog()
		self.session.openWithCallback(self.onSetupClose, Setup, 'epginfobarsingle')

	def onSetupClose(self, test = None):
		self.close('reopeninfobarsingle')

	def onCreate(self):
		self['list'].recalcEntrySize()
		service = ServiceReference(self.servicelist.getCurrentSelection())
		title = ServiceReference(self.servicelist.getRoot()).getServiceName()
		self['Service'].newService(service.ref)
		if title:
			title = title + ' - ' + service.getServiceName()
		else:
			title = service.getServiceName()
		self.setTitle(title)
		self['list'].fillEPG(service)
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self['lab1'].show()
		self.show()

	def refreshList(self):
		self.refreshTimer.stop()
		service = ServiceReference(self.servicelist.getCurrentSelection())
		index = self['list'].getCurrentIndex()
		self['list'].fillEPG(service)
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self['list'].setCurrentIndex(index)

	def bouquetChanged(self):
		self.bouquetRoot = False
		now = time() - int(config.epg.histminutes.value) * SECS_IN_MIN
		self.services = self.getBouquetServices(self.getCurrentBouquet())
		self['list'].instance.moveSelectionTo(0)
		self.setTitle(self['bouquetlist'].getCurrentBouquet())
		self.bouquetListHide()

	def nextBouquet(self):
		if config.usage.multibouquet.value:
			self.servicelist.nextBouquet()
			self.onCreate()

	def prevBouquet(self):
		if config.usage.multibouquet.value:
			self.servicelist.prevBouquet()
			self.onCreate()

	def nextService(self):
		self['list'].instance.moveSelectionTo(0)
		if self.servicelist.inBouquet():
			prev = self.servicelist.getCurrentSelection()
			if prev:
				prev = prev.toString()
				while True:
					if config.usage.quickzap_bouquet_change.value and self.servicelist.atEnd():
						self.servicelist.nextBouquet()
					else:
						self.servicelist.moveDown()
					cur = self.servicelist.getCurrentSelection()
					if not cur or (not (cur.flags & 64)) or cur.toString() == prev:
						break
		else:
			self.servicelist.moveDown()
		if self.isPlayable():
			self.onCreate()
			if not self['list'].getCurrent()[1] and config.epgselection.overjump.value:
				self.nextService()
		else:
			self.nextService()

	def isPlayable(self):
		current = ServiceReference(self.servicelist.getCurrentSelection())
		return not current.ref.flags & (eServiceReference.isMarker | eServiceReference.isDirectory)

	def prevService(self):
		self['list'].instance.moveSelectionTo(0)
		if self.servicelist.inBouquet():
			prev = self.servicelist.getCurrentSelection()
			if prev:
				prev = prev.toString()
				while True:
					if config.usage.quickzap_bouquet_change.value:
						if self.servicelist.atBegin():
							self.servicelist.prevBouquet()
					self.servicelist.moveUp()
					cur = self.servicelist.getCurrentSelection()
					if not cur or (not (cur.flags & 64)) or cur.toString() == prev:
						break
		else:
			self.servicelist.moveUp()
		if self.isPlayable():
			self.onCreate()
			if not self['list'].getCurrent()[1] and config.epgselection.overjump.value:
				self.prevService()
		else:
			self.prevService()

	def eventViewCallback(self, setEvent, setService, val):
		if val == -1:
			self.moveUp()
		elif val == +1:
			self.moveDown()
		event, service = self['list'].getCurrent()[:2]
		setService(service)
		setEvent(event)

	def sortEPG(self):
		if config.epgselection.sort.value == '0':
			config.epgselection.sort.setValue('1')
		else:
			config.epgselection.sort.setValue('0')
		config.epgselection.sort.save()
		configfile.save()
		self['list'].sortEPG(int(config.epgselection.sort.value))
