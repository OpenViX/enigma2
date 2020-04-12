from time import localtime, time, mktime

from enigma import eTimer

from Components.ActionMap import HelpableActionMap
from Components.config import config, configfile
from Components.Epg.EpgListGrid import EPGListGrid, TimelineText, MAX_TIMELINES
from EpgSelectionBase import EPGSelectionBase, EPGBouquetSelection, EPGServiceZap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.Event import Event
from Screens.EventView import EventViewSimple
from Screens.Setup import Setup

class EPGSelectionGrid(EPGSelectionBase, EPGBouquetSelection, EPGServiceZap):
	def __init__(self, session, epgConfig = None, isInfobar = False, zapFunc = None, startBouquet = None, startRef = None, bouquets = None):
		self.isInfobar = isInfobar
		self.epgConfig = epgConfig or config.epgselection.grid
		EPGSelectionBase.__init__(self, session, startBouquet, startRef, bouquets)
		EPGServiceZap.__init__(self, self.epgConfig, zapFunc)

		graphic = self.epgConfig.type_mode.value == "graphics"
		if not config.epgselection.grid.pig.value:
			self.skinName = ['GridEPG', 'GraphicalEPG']
		else:
			self.skinName = ['GridEPGPIG', 'GraphicalEPGPIG']
		self.closeRecursive = False
		EPGBouquetSelection.__init__(self, graphic)

		self['timeline_text'] = TimelineText(self.epgConfig, graphic)
		self['Event'] = Event()
		self['primetime'] = Label(_('PRIMETIME'))
		self['change_bouquet'] = Label(_('CHANGE BOUQUET'))
		self['jump'] = Label(_('JUMP 24 HOURS'))
		self['page'] = Label(_('PAGE UP/DOWN'))
		self.time_lines = []
		for x in range(0, MAX_TIMELINES):
			pm = Pixmap()
			self.time_lines.append(pm)
			self['timeline%d' % x] = pm

		self['timeline_now'] = Pixmap()
		self.updateTimelineTimer = eTimer()
		self.updateTimelineTimer.callback.append(self.moveTimeLines)
		self.updateTimelineTimer.start(60000)

		self['epgcursoractions'] = HelpableActionMap(self, 'DirectionActions',
			{
				'left': (self.leftPressed, _('Go to previous event')),
				'right': (self.rightPressed, _('Go to next event')),
				'up': (self.moveUp, _('Go to previous channel')),
				'down': (self.moveDown, _('Go to next channel'))
			}, -1)

		self['epgactions'] = HelpableActionMap(self, 'EPGSelectActions',
			{
				'nextService': (self.forward24Hours, _('Jump forward 24 hours')),
				'prevService': (self.back24Hours, _('Jump back 24 hours')),
				'nextBouquet': (self.nextBouquet, _('Go to next bouquet')),
				'prevBouquet': (self.prevBouquet, _('Go to previous bouquet')),
				'input_date_time': (self.enterDateTime, _('Go to specific date/time')),
				'epg': (self.openSingleEPG, _('Show single epg for current channel')),
				'info': (self.infoPressed, _('Show detailed event info')),
				'infolong': (self.infoLongPressed, _('Show single epg for current channel')),
				'tv': (self.bouquetList, _('Toggle between bouquet/epg lists')),
				'tvlong': (self.togglePIG, _('Toggle picture In graphics')),
				'timer': (self.openTimerList, _('Show timer list')),
				'timerlong': (self.openAutoTimerList, _('Show autotimer list')),
				'menu': (self.createSetup, _('Setup menu'))
			}, -1)

		self['input_actions'] = HelpableActionMap(self, 'NumberActions',
			{
				'1': (self.reduceTimeScale, _('Reduce time scale')),
				'2': (self.prevPage, _('Page up')),
				'3': (self.increaseTimeScale, _('Increase time scale')),
				'4': (self.pageLeft, _('page left')),
				'5': (self.goToCurrentTime, _('Jump to current time')),
				'6': (self.pageRight, _('Page right')),
				'7': (self.toggleNumberOfRows, _('No of items switch (increase or reduced)')),
				'8': (self.nextPage, _('Page down')),
				'9': (self.goToPrimeTime, _('Jump to prime time')),
				'0': (self.goToCurrentTimeAndTop, _('Move to home of list'))
			}, -1)

		self['list'] = EPGListGrid(isInfobar=self.isInfobar, session=self.session, selChangedCB=self.onSelectionChanged, timer=session.nav.RecordTimer, graphic=graphic)
		self['list'].setTimeFocus(time())

	def createSetup(self):
		def onSetupClose(test = None):
			self.close('reopengrid')

		self.closeEventViewDialog()
		self.session.openWithCallback(onSetupClose, Setup, 'epggrid')

	def onCreate(self):
		self['list'].recalcEventSize()
		self.bouquetRoot = self.startBouquet.toString().startswith('1:7:0')
		self['timeline_text'].setEntries(self['list'], self['timeline_now'], self.time_lines, False)
		self['lab1'].show()
		self.show()
		self.listTimer = eTimer()
		self.listTimer.callback.append(self.loadEPGData)
		self.listTimer.start(1, True)

	def loadEPGData(self):
		self._populateBouquetList()
		self['list'].fillEPGNoRefresh(self.services)
		if self.isInfobar or not config.epgselection.grid.channel1.value:
			self['list'].moveToService(self.startRef)
		self.moveTimeLines()
		self['lab1'].hide()

	def refreshList(self):
		self.refreshTimer.stop()
		self['list'].fillEPG()
		self.moveTimeLines()

	def togglePIG(self):
		if not config.epgselection.grid.pig.value:
			config.epgselection.grid.pig.setValue(True)
		else:
			config.epgselection.grid.pig.setValue(False)
		config.epgselection.grid.pig.save()
		configfile.save()
		self.close('reopengrid')

	def updEvent(self, dir, visible = True):
		if self['list'].selEvent(dir, visible):
			self.moveTimeLines(True)

	def moveTimeLines(self, force = False):
		self.updateTimelineTimer.start((60 - int(time()) % 60) * 1000)
		self['timeline_text'].setEntries(self['list'], self['timeline_now'], self.time_lines, force)
		self['list'].l.invalidate()

	def leftPressed(self):
		self.updEvent(-1)

	def rightPressed(self):
		self.updEvent(+1)

	def infoPressed(self):
		if config.epgselection.grid.btn_info.value == 'openSingleEPG':
			self.openSingleEPG()
		else:
			self.openEventView()

	def infoLongPressed(self):
		if config.epgselection.grid.btn_infolong.value == 'openEventView':
			self.openEventView()
		else:
			self.openSingleEPG()

	def bouquetChanged(self):
		self.bouquetRoot = False
		self.services = self.getBouquetServices(self.getCurrentBouquet())
		l = self['list']
		l.fillEPG(self.services)
		self.moveTimeLines(True)
		l.setCurrentIndex(0)
		self.setTitle(self['bouquetlist'].getCurrentBouquet())

	def nextBouquet(self):
		self.moveBouquetDown()
		self.bouquetChanged()

	def prevBouquet(self):
		self.moveBouquetUp()
		self.bouquetChanged()

	def forward24Hours(self):
		self.updEvent(+24)

	def back24Hours(self):
		self.updEvent(-24)

	def onDateTimeInputClosed(self, ret):
		if len(ret) > 1 and ret[0]:
			self.goToTime(ret[1])

	def onSelectionChanged(self):
		EPGSelectionBase.onSelectionChanged(self)
		if self.eventviewDialog:
			self.eventviewDialog.hide()
			self.openEventViewDialog()
	
	def openEventViewDialog(self):
		event, service = self['list'].getCurrent()[:2]
		if event is not None:
			self.eventviewDialog = self.session.instantiateDialog(EventViewSimple, event, service, skin='InfoBarEventView')
			self.eventviewDialog.show()

	def eventViewCallback(self, setEvent, setService, val):
		l = self['list']
		old = l.getCurrent()
		self.updEvent(val, False)
		cur = l.getCurrent()
		if cur[0] is None and cur[1].ref != old[1].ref:
			self.eventViewCallback(setEvent, setService, val)
		else:
			setService(cur[1])
			setEvent(cur[0])

	def reduceTimeScale(self):
		timeperiod = int(self.epgConfig.prevtimeperiod.value)
		if timeperiod > 60:
			timeperiod -= 30
			self['list'].setTimeEpoch(timeperiod)
			self.epgConfig.prevtimeperiod.setValue(str(timeperiod))
			self.moveTimeLines()
	
	def increaseTimeScale(self):
		timeperiod = int(self.epgConfig.prevtimeperiod.value)
		if timeperiod < 300:
			timeperiod += 30
			self['list'].setTimeEpoch(timeperiod)
			self.epgConfig.prevtimeperiod.setValue(str(timeperiod))
			self.moveTimeLines()

	def pageLeft(self):
		self.updEvent(-2)

	def pageRight(self):
		self.updEvent(+2)

	def goToCurrentTime(self):
		self.goToTime(time())

	def goToPrimeTime(self):
		basetime = localtime(self['list'].getTimeBase())
		basetime = (basetime[0], basetime[1], basetime[2], int(self.epgConfig.primetimehour.value), int(self.epgConfig.primetimemins.value), 0, basetime[6], basetime[7], basetime[8])
		primetime = mktime(basetime)
		if primetime + 3600 < time():
			primetime += 86400
		self.goToTime(primetime)

	def goToCurrentTimeAndTop(self):
		self.toTop()
		self.goToCurrentTime()

	def goToTime(self, time):
		l = self['list']
		# place the entered time halfway across the grid
		l.setTimeFocus(time)
		l.fillEPG()
		self.moveTimeLines(True)

	def toggleNumberOfRows(self):
		if config.epgselection.grid.heightswitch.value:
			config.epgselection.grid.heightswitch.setValue(False)
		else:
			config.epgselection.grid.heightswitch.setValue(True)
		self['list'].setItemsPerPage()
		self['list'].fillEPG()
		self.moveTimeLines()
