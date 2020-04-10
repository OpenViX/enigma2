from time import localtime, time, strftime, mktime

from enigma import eServiceReference, eTimer, eServiceCenter, ePoint

from Screens.HelpMenu import HelpableScreen
from Components.About import about
from Components.ActionMap import HelpableActionMap, HelpableNumberActionMap
from Components.Button import Button
from Components.config import config, configfile, ConfigClock
from Components.Epg.EpgListSingle import EPGListSingle
from Components.Epg.EpgListBase import EPG_TYPE_ENHANCED
from EpgSelectionBase import EPGSelectionBase, EPGServiceNumberSelection, EPGServiceZap
from Screens.Setup import Setup
from ServiceReference import ServiceReference

class EPGSelectionEnhanced(EPGSelectionBase, EPGServiceNumberSelection, EPGServiceZap):
	def __init__(self, session, servicelist, zapFunc, startBouquet, startRef, bouquets):
		print "[EPGSelectionEnhanced] ------- NEW VERSION -------"
		EPGSelectionBase.__init__(self, EPG_TYPE_ENHANCED, session, zapFunc, None, None, startBouquet, startRef, bouquets)
		EPGServiceNumberSelection.__init__(self)
		EPGServiceZap.__init__(self, config.epgselection.enhanced_preview_mode, config.epgselection.enhanced_ok, config.epgselection.enhanced_oklong)

		self.skinName = 'EPGSelection'

		self['epgactions'] = HelpableActionMap(self, 'EPGSelectActions',
			{
				'nextBouquet': (self.nextBouquet, _('Go to next bouquet')),
				'prevBouquet': (self.prevBouquet, _('Go to previous bouquet')),
				'nextService': (self.nextService, _('Go to next channel')),
				'prevService': (self.prevService, _('Go to previous channel')),
				'info': (self.openEventView, _('Show detailed event info')),
				'infolong': (self.openSingleEPG, _('Show single epg for current channel')),
				'menu': (self.createSetup, _('Setup menu'))
			}, -1)
		self['epgcursoractions'] = HelpableActionMap(self, 'DirectionActions',
			{
				'left': (self.prevPage, _('Move up a page')),
				'right': (self.nextPage, _('Move down a page')),
				'up': (self.moveUp, _('Go to previous channel')),
				'down': (self.moveDown, _('Go to next channel'))
			}, -1)
			
		self.list = []
		self.servicelist = servicelist

		self['list'] = EPGListSingle(selChangedCB=self.onSelectionChanged, timer=session.nav.RecordTimer,
			itemsPerPageConfig = config.epgselection.enhanced_itemsperpage,
			eventfsConfig = config.epgselection.enhanced_eventfs)

	def createSetup(self):
		self.closeEventViewDialog()
		self.session.openWithCallback(self.onSetupClose, Setup, 'epgenhanced')

	def onSetupClose(self, test = None):
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self['list'].setFontsize()
		self['list'].setItemsPerPage()
		self['list'].recalcEntrySize()

	def onCreate(self):
		self['list'].recalcEntrySize()
		service = ServiceReference(self.servicelist.getCurrentSelection())
		self['Service'].newService(service.ref)
		title = ServiceReference(self.servicelist.getRoot()).getServiceName() + ' - ' + service.getServiceName()
		self.setTitle(title)
		self['list'].fillEPG(service)
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self.show()

	def refreshList(self):
		self.refreshTimer.stop()
		service = ServiceReference(self.servicelist.getCurrentSelection())
		index = self['list'].getCurrentIndex()
		self['list'].fillEPG(service)
		self['list'].sortEPG(int(config.epgselection.sort.value))
		self['list'].setCurrentIndex(index)

	def nextBouquet(self):
		self.servicelist.nextBouquet()
		self.onCreate()

	def prevBouquet(self):
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
