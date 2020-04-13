from time import time
from enigma import eServiceReference, eTimer, eServiceCenter, ePoint

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import ActionMap, HelpableActionMap, HelpableNumberActionMap
from Components.Button import Button
from Components.config import config, configfile, ConfigClock, ConfigDateTime
from Components.EpgBouquetList import EPGBouquetList
from Components.Label import Label
from Components.Sources.ServiceEvent import ServiceEvent
from Components.Sources.Event import Event
from Components.UsageConfig import preferredTimerPath
from Screens.EventView import EventViewEPGSelect
from Screens.TimerEdit import TimerSanityConflict
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.PictureInPicture import PictureInPicture
from Screens.Setup import Setup
from Screens.TimeDateInput import TimeDateInput
from Screens.TimerEntry import TimerEntry, InstantRecordTimerEntry
from RecordTimer import RecordTimerEntry, parseEvent, AFTEREVENT
from ServiceReference import ServiceReference

def ignoreLongKeyPress(action):
	def fn():
		from Screens.InfoBar import InfoBar
		if not InfoBar.instance.LongButtonPressed:
			action()
	return fn

# PiPServiceRelation installed?
try:
	from Plugins.SystemPlugins.PiPServiceRelation.plugin import getRelationDict
	plugin_PiPServiceRelation_installed = True
except:
	plugin_PiPServiceRelation_installed = False

class EPGSelectionBase(Screen, HelpableScreen):
	lastEnteredTime = None
	lastEnteredDate = None
	EMPTY = 0
	ADD_TIMER = 1
	REMOVE_TIMER = 2
	ZAP = 1

	def __init__(self, session, startBouquet = None, startRef = None, bouquets = None):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)

		self.type = type
		self.bouquets = bouquets
		self.originalPlayingServiceOrGroup = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.startBouquet = startBouquet
		self.startRef = startRef
		self.servicelist = None
		self.ChoiceBoxDialog = None
		self.closeRecursive = False
		self.eventviewDialog = None
		self.eventviewWasShown = False
		self.session.pipshown = False
		self.pipServiceRelation = getRelationDict() if plugin_PiPServiceRelation_installed else {}
		self["number"] = Label()
		self["number"].hide()
		self['Service'] = ServiceEvent()
		self['Event'] = Event()
		self['lab1'] = Label(_('Please wait while gathering EPG data...'))
		self['lab1'].hide()
		self['key_red'] = Button(_('IMDb Search'))
		self['key_green'] = Button(_('Add Timer'))
		self['key_yellow'] = Button(_('EPG Search'))
		self['key_blue'] = Button(_('Add AutoTimer'))
		self['dialogactions'] = HelpableActionMap(self, 'WizardActions',
			{
				'back': (self.closeChoiceBoxDialog, _('Close dialog')),
			}, -1)
		self["dialogactions"].setEnabled(False)

		self['okactions'] = HelpableActionMap(self, 'OkCancelActions',
			{
				'cancel': (self.closeScreen, _('Exit EPG')),
				'OK': (ignoreLongKeyPress(self.OK), _('Zap to channel (setup in menu)')),
				'OKLong': (self.OKLong, _('Zap to channel and close (setup in menu)'))
			}, -1)
		self['colouractions'] = HelpableActionMap(self, 'ColorActions',
			{
				'red': (ignoreLongKeyPress(self.openIMDb), _('IMDB search for current event')),
				'redlong': (self.sortEPG, _('Sort EPG list')),
				'green': (ignoreLongKeyPress(self.addEditTimer), _('Add/Remove timer for current event')),
				'greenlong': (self.openTimerList, _('Show timer list')),
				'yellow': (ignoreLongKeyPress(self.openEPGSearch), _('Search for similar events')),
				'blue': (ignoreLongKeyPress(self.addAutoTimer), _('Add an autotimer for current event')),
				'bluelong': (self.openAutoTimerList, _('Show autotimer list'))
			}, -1)
		self['recordingactions'] = HelpableActionMap(self, 'InfobarInstantRecord',
			{
				'ShortRecord': (self.recordTimerQuestion, _('Add a record timer for current event')),
				'LongRecord': (self.doZapTimer, _('Add a zap timer for current event'))
			}, -1)
		self['epgactions'] = HelpableActionMap(self, 'EPGSelectActions', {}, -1)

		self.refreshTimer = eTimer()
		self.refreshTimer.timeout.get().append(self.refreshList)
		self.onLayoutFinish.append(self.onCreate)

	def getBouquetServices(self, bouquet):
		servicelist = eServiceCenter.getInstance().list(bouquet)
		if servicelist:
			# Use getContent() instead of getNext() so
			# That the list is sorted according to the "ORDER BY"
			# mechanism
			return [ServiceReference(service) for service in servicelist.getContent("R", True) if not (service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker))]
		else:
			return []

	def moveUp(self):
		self['list'].moveTo(self['list'].instance.moveUp)

	def moveDown(self):
		self['list'].moveTo(self['list'].instance.moveDown)

	def nextPage(self):
		self['list'].moveTo(self['list'].instance.pageDown)

	def prevPage(self):
		self['list'].moveTo(self['list'].instance.pageUp)

	def toTop(self):
		self['list'].moveTo(self['list'].instance.moveTop)

	def toEnd(self):
		self['list'].moveTo(self['list'].instance.moveEnd)

	def openEventView(self):
		def openSimilarList(eventid, refstr):
			from Screens.EpgSelectionSimilar import EPGSelectionSimilar
			self.session.open(EPGSelectionSimilar, refstr, eventid)
		event, service = self['list'].getCurrent()[:2]
		if event is not None:
			self.session.open(EventViewEPGSelect, event, service, callback=self.eventViewCallback, similarEPGCB=openSimilarList)

	def sortEPG(self):
		self.closeEventViewDialog()

	def addEditTimer(self):
		self.closeEventViewDialog()
		self.recordTimerQuestion(True)

	def enterDateTime(self):
		if not EPGSelectionBase.lastEnteredTime:
			# the stored date and time is shared by all EPG types
			EPGSelectionBase.lastEnteredTime = ConfigClock(default=time())
			EPGSelectionBase.lastEnteredDate = ConfigDateTime(default=time(), formatstring=config.usage.date.full.value, increment=86400)
		self.session.openWithCallback(self.onDateTimeInputClosed, TimeDateInput, EPGSelectionBase.lastEnteredTime, EPGSelectionBase.lastEnteredDate)

	def openSingleEPG(self):
		from Screens.EpgSelectionChannel import EPGSelectionChannel
		event, service = self['list'].getCurrent()[:2]
		if service is not None and service.ref is not None:
			self.session.open(EPGSelectionChannel, service.ref, time() if event is None else event.getBeginTime())

	def openIMDb(self):
		self.closeEventViewDialog()
		try:
			from Plugins.Extensions.IMDb.plugin import IMDB, IMDBEPGSelection
			try:
				event = self['list'].getCurrent()[0]
				if event is None:
					return
				name = event.getEventName()
			except:
				name = ''

			self.session.open(IMDB, name, False)
		except ImportError:
			self.session.open(MessageBox, _('The IMDb plugin is not installed!\nPlease install it.'), type=MessageBox.TYPE_INFO, timeout=10)

	def openEPGSearch(self):
		self.closeEventViewDialog()
		try:
			from Plugins.Extensions.EPGSearch.EPGSearch import EPGSearch
			try:
				event = self['list'].getCurrent()[0]
				if event is None:
					return
				name = event.getEventName()
			except:
				name = ''
			self.session.open(EPGSearch, name, False)
		except ImportError:
			self.session.open(MessageBox, _('The EPGSearch plugin is not installed!\nPlease install it.'), type=MessageBox.TYPE_INFO, timeout=10)

	def addAutoTimer(self):
		self.closeEventViewDialog()
		try:
			from Plugins.Extensions.AutoTimer.AutoTimerEditor import addAutotimerFromEvent
			event, service = self['list'].getCurrent()[:2]
			if event is None:
				return
			addAutotimerFromEvent(self.session, evt=event, service=service)
			self.refreshTimer.start(3000)
		except ImportError:
			self.session.open(MessageBox, _('The AutoTimer plugin is not installed!\nPlease install it.'), type=MessageBox.TYPE_INFO, timeout=10)

	def addAutoTimerSilent(self):
		try:
			from Plugins.Extensions.AutoTimer.AutoTimerEditor import addAutotimerFromEventSilent
			event, service = self['list'].getCurrent()[:2]
			if event is None:
				return
			addAutotimerFromEventSilent(self.session, evt=event, service=service)
			self.refreshTimer.start(3000)
		except ImportError:
			self.session.open(MessageBox, _('The AutoTimer plugin is not installed!\nPlease install it.'), type=MessageBox.TYPE_INFO, timeout=10)

	def openTimerList(self):
		self.closeEventViewDialog()
		from Screens.TimerEdit import TimerEditList
		self.session.open(TimerEditList)

	def openAutoTimerList(self):
		self.closeEventViewDialog()
		global autopoller
		global autotimer
		try:
			from Plugins.Extensions.AutoTimer.plugin import main, autostart
			from Plugins.Extensions.AutoTimer.AutoTimer import AutoTimer
			from Plugins.Extensions.AutoTimer.AutoPoller import AutoPoller
			autopoller = AutoPoller()
			autotimer = AutoTimer()
			try:
				autotimer.readXml()
			except SyntaxError as se:
				self.session.open(MessageBox, _('Your config file is not well formed:\n%s') % str(se), type=MessageBox.TYPE_ERROR, timeout=10)
				return

			if autopoller is not None:
				autopoller.stop()
			from Plugins.Extensions.AutoTimer.AutoTimerOverview import AutoTimerOverview
			self.session.openWithCallback(self.editCallback, AutoTimerOverview, autotimer)
		except ImportError:
			self.session.open(MessageBox, _('The AutoTimer plugin is not installed!\nPlease install it.'), type=MessageBox.TYPE_INFO, timeout=10)

	def editCallback(self, session):
		global autopoller
		global autotimer
		if session is not None:
			autotimer.writeXml()
			autotimer.parseEPG()
		if config.plugins.autotimer.autopoll.value:
			if autopoller is None:
				from Plugins.Extensions.AutoTimer.AutoPoller import AutoPoller
				autopoller = AutoPoller()
			autopoller.start()
		else:
			autopoller = None
			autotimer = None

	def timerAdd(self):
		self.recordTimerQuestion(True)

	def editTimer(self, timer):
		self.session.open(TimerEntry, timer)

	def removeTimer(self, timer):
		self.closeChoiceBoxDialog()
		timer.afterEvent = AFTEREVENT.NONE
		self.session.nav.RecordTimer.removeEntry(timer)
		self["key_green"].setText(_('Add Timer'))
		self.refreshList()

	def disableTimer(self, timer):
		self.closeChoiceBoxDialog()
		timer.disable()
		self.session.nav.RecordTimer.timeChanged(timer)
		self["key_green"].setText(_('Add Timer'))
		self.refreshList()

	def recordTimerQuestion(self, manual=False):
		event, serviceref = self['list'].getCurrent()[:2]
		if event is None:
			return
		eventid = event.getEventId()
		refstr = ':'.join(serviceref.ref.toString().split(':')[:11])
		title = None
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventid and ':'.join(timer.service_ref.ref.toString().split(':')[:11]) == refstr:
				cb_func1 = lambda ret: self.removeTimer(timer)
				cb_func2 = lambda ret: self.editTimer(timer)
				cb_func3 = lambda ret: self.disableTimer(timer)
				menu = [(_("Delete Timer"), 'CALLFUNC', self.RemoveChoiceBoxCB, cb_func1), (_("Edit Timer"), 'CALLFUNC', self.RemoveChoiceBoxCB, cb_func2), (_("Disable Timer"), 'CALLFUNC', self.RemoveChoiceBoxCB, cb_func3)]
				title = _("Select action for timer %s:") % event.getEventName()
				break
		else:
			if not manual:
				menu = [(_("Add Timer"), 'CALLFUNC', self.ChoiceBoxCB, self.doRecordTimer), (_("Add AutoTimer"), 'CALLFUNC', self.ChoiceBoxCB, self.addAutoTimerSilent)]
				title = "%s?" % event.getEventName()
			else:
				newEntry = RecordTimerEntry(serviceref, checkOldTimers=True, dirname=preferredTimerPath(), *parseEvent(event))
				self.session.openWithCallback(self.finishedAdd, TimerEntry, newEntry)
		if title:
			self.ChoiceBoxDialog = self.session.instantiateDialog(ChoiceBox, title=title, list=menu, keys=['green', 'blue'], skin_name="RecordTimerQuestion")
			posy = self['list'].getSelectionPosition()
			self.ChoiceBoxDialog.instance.move(ePoint(posy[0]-self.ChoiceBoxDialog.instance.size().width(),self.instance.position().y()+posy[1]))
			self.showChoiceBoxDialog()

	def RemoveChoiceBoxCB(self, choice):
		self.closeChoiceBoxDialog()
		if choice:
			choice(self)

	def ChoiceBoxCB(self, choice):
		self.closeChoiceBoxDialog()
		if choice:
			try:
				choice()
			except:
				choice

	def showChoiceBoxDialog(self):
		self['okactions'].setEnabled(False)
		if self.has_key('epgcursoractions'):
			self['epgcursoractions'].setEnabled(False)
		self['colouractions'].setEnabled(False)
		self['recordingactions'].setEnabled(False)
		self['epgactions'].setEnabled(False)
		self["dialogactions"].setEnabled(True)
		self.ChoiceBoxDialog['actions'].execBegin()
		self.ChoiceBoxDialog.show()
		if self.has_key('input_actions'):
			self['input_actions'].setEnabled(False)

	def closeChoiceBoxDialog(self):
		self["dialogactions"].setEnabled(False)
		if self.ChoiceBoxDialog:
			self.ChoiceBoxDialog['actions'].execEnd()
			self.session.deleteDialog(self.ChoiceBoxDialog)
		self['okactions'].setEnabled(True)
		if self.has_key('epgcursoractions'):
			self['epgcursoractions'].setEnabled(True)
		self['colouractions'].setEnabled(True)
		self['recordingactions'].setEnabled(True)
		self['epgactions'].setEnabled(True)
		if self.has_key('input_actions'):
			self['input_actions'].setEnabled(True)

	def doRecordTimer(self):
		self.doInstantTimer(0)

	def doZapTimer(self):
		self.doInstantTimer(1)

	def doInstantTimer(self, zap):
		event, service = self['list'].getCurrent()[:2]
		if event is None:
			return
		eventid = event.getEventId()
		refstr = service.ref.toString()
		newEntry = RecordTimerEntry(service, checkOldTimers=True, *parseEvent(event))
		self.InstantRecordDialog = self.session.instantiateDialog(InstantRecordTimerEntry, newEntry, zap)
		retval = [True, self.InstantRecordDialog.retval()]
		self.session.deleteDialogWithCallback(self.finishedAdd, self.InstantRecordDialog, retval)

	def finishedAdd(self, answer):
		if answer[0]:
			entry = answer[1]
			simulTimerList = self.session.nav.RecordTimer.record(entry)
			if simulTimerList is not None:
				for x in simulTimerList:
					if x.setAutoincreaseEnd(entry):
						self.session.nav.RecordTimer.timeChanged(x)
				simulTimerList = self.session.nav.RecordTimer.record(entry)
				if simulTimerList is not None:
					if not entry.repeated and not config.recording.margin_before.value and not config.recording.margin_after.value and len(simulTimerList) > 1:
						change_time = False
						conflict_begin = simulTimerList[1].begin
						conflict_end = simulTimerList[1].end
						if conflict_begin == entry.end:
							entry.end -= 30
							change_time = True
						elif entry.begin == conflict_end:
							entry.begin += 30
							change_time = True
						if change_time:
							simulTimerList = self.session.nav.RecordTimer.record(entry)
					if simulTimerList is not None:
						self.session.openWithCallback(self.finishSanityCorrection, TimerSanityConflict, simulTimerList)
			self["key_green"].setText(_("Change Timer"))
		else:
			self["key_green"].setText(_("Add Timer"))
		self.refreshList()

	def finishSanityCorrection(self, answer):
		self.finishedAdd(answer)

	def onSelectionChanged(self):
		event, service = self['list'].getCurrent()[:2]
		self['Event'].newEvent(event)
		if service is None:
			self['Service'].newService(None)
		else:
			self['Service'].newService(service.ref)
		if service is None or service.getServiceName() == '':
			self['key_green'].setText('')
			return
		if event is None:
			self['key_green'].setText('')
			return
		eventid = event.getEventId()
		refstr = ':'.join(service.ref.toString().split(':')[:11])
		isRecordEvent = False
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventid and ':'.join(timer.service_ref.ref.toString().split(':')[:11]) == refstr:
				isRecordEvent = True
				break
		self["key_green"].setText(_("Change Timer") if isRecordEvent else _('Add Timer'))

	def setServicelistSelection(self, bouquet, service):
		if self.servicelist:
			if self.servicelist.getRoot() != bouquet:
				self.servicelist.clearPath()
				self.servicelist.enterPath(self.servicelist.bouquet_root)
				self.servicelist.enterPath(bouquet)
			self.servicelist.setCurrentSelection(service)

	def closeEventViewDialog(self):
		if self.eventviewDialog:
			self.eventviewDialog.hide()
			del self.eventviewDialog
			self.eventviewDialog = None

class EPGServiceZap:
	def __init__(self, epgConfig, zapFunc):
		self.prevch = None
		self.currch = None
		self.epgConfig = epgConfig
		self.zapFunc = zapFunc

	def OK(self):
		if self.epgConfig.btn_ok.value == 'zap':
			self.zap()
		else:
			self.zapExit()

	def OKLong(self):
		if self.epgConfig.btn_oklong.value == 'zap':
			self.zap()
		else:
			self.zapExit()

	def zapExit(self):
		self.zapSelectedService()
		self.closeEventViewDialog()
		self.close('close')

	def zap(self):
		if self.session.nav.getCurrentlyPlayingServiceOrGroup() and '0:0:0:0:0:0:0:0:0' in self.session.nav.getCurrentlyPlayingServiceOrGroup().toString():
			from Screens.InfoBarGenerics import setResumePoint
			setResumePoint(self.session)
		self.zapSelectedService(True)
		self.refreshTimer.start(1)
		if not self.currch or self.currch == self.prevch:
			self.zapFunc(None, False)
			self.closeEventViewDialog()
			self.close('close')

	def closeScreen(self):
		# when exiting, restore the previous service/playback if a channel has been previewed
		closeParam = True
		if self.originalPlayingServiceOrGroup and self.session.nav.getCurrentlyPlayingServiceOrGroup() and self.session.nav.getCurrentlyPlayingServiceOrGroup().toString() != self.originalPlayingServiceOrGroup.toString():
			if self.epgConfig.preview_mode.value:
				if '0:0:0:0:0:0:0:0:0' in self.originalPlayingServiceOrGroup.toString():
					# restart movie playback. MoviePlayer screen is still active
					from Screens.InfoBar import MoviePlayer
					if MoviePlayer.instance:
						MoviePlayer.instance.forceNextResume()
				self.session.nav.playService(self.originalPlayingServiceOrGroup)
			else:
				if '0:0:0:0:0:0:0:0:0' in self.originalPlayingServiceOrGroup.toString():
					# previously we were in playback, so we'll need to close the movie player
					closeParam = 'close'
				# Not preview mode and service has been changed before exiting, record it with the zap history
				self.zapFunc(None, False)
		if self.session.pipshown:
			self.session.pipshown = False
			del self.session.pip
		self.closeEventViewDialog()
		self.close(closeParam)

	def zapSelectedService(self, prev=False):
		currservice = self.session.nav.getCurrentlyPlayingServiceReference() and str(self.session.nav.getCurrentlyPlayingServiceReference().toString()) or None
		if self.session.pipshown:
			self.prevch = self.session.pip.getCurrentService() and str(self.session.pip.getCurrentService().toString()) or None
		else:
			self.prevch = self.session.nav.getCurrentlyPlayingServiceReference() and str(self.session.nav.getCurrentlyPlayingServiceReference().toString()) or None
		service = self["list"].getCurrent()[1]
		if service is not None:
			if self.epgConfig.preview_mode.value == '2':
				if not prev:
					if self.session.pipshown:
						self.session.pipshown = False
						del self.session.pip
					self.zapFunc(service.ref, bouquet = self.getCurrentBouquet(), preview = False)
					return
				if not self.session.pipshown:
					self.session.pip = self.session.instantiateDialog(PictureInPicture)
					self.session.pip.show()
					self.session.pipshown = True
				n_service = self.pipServiceRelation.get(str(service.ref), None)
				if n_service is not None:
					serviceRef = eServiceReference(n_service)
				else:
					serviceRef = service.ref
				if self.currch == serviceRef.toString():
					if self.session.pipshown:
						self.session.pipshown = False
						del self.session.pip
					self.zapFunc(service.ref, bouquet = self.getCurrentBouquet(), preview = False)
					return
				if self.prevch != serviceRef.toString() and currservice != serviceRef.toString():
					self.session.pip.playService(serviceRef)
					self.currch = self.session.pip.getCurrentService() and str(self.session.pip.getCurrentService().toString())
			else:
				self.zapFunc(service.ref, bouquet = self.getCurrentBouquet(), preview = prev)
				self.currch = self.session.nav.getCurrentlyPlayingServiceReference() and str(self.session.nav.getCurrentlyPlayingServiceReference().toString())

class EPGServiceNumberSelection:
	def __init__(self):
		self.zapNumberStarted = False
		self.numberZapTimer = eTimer()
		self.numberZapTimer.callback.append(self.doNumberZap)
		self.numberZapField = None

		self['numberzapokactions'] = HelpableActionMap(self, 'OkCancelActions',
			{
				'cancel': (self.__cancel, _('Close number zap.')),
				'OK': (self.__OK, _('Change to service')),
			}, -1)
		self['numberzapokactions'].setEnabled(False)

		self['input_actions'] = HelpableNumberActionMap(self, 'NumberActions',
			{
				'0': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'1': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'2': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'3': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'4': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'5': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'6': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'7': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'8': (self.keyNumberGlobal, _('enter number to jump to channel.')),
				'9': (self.keyNumberGlobal, _('enter number to jump to channel.'))
			}, -1)

	def keyNumberGlobal(self, number):
		self.zapNumberStarted = True
		self["epgcursoractions"].setEnabled(False)
		self["okactions"].setEnabled(False)
		self["numberzapokactions"].setEnabled(True)
		self.numberZapTimer.start(5000, True)
		if not self.numberZapField:
			self.numberZapField = str(number)
		else:
			self.numberZapField += str(number)
		self.handleServiceName()
		self["number"].setText(self.zaptoservicename+'\n'+self.numberZapField)
		self["number"].show()
		if len(self.numberZapField) >= 4:
			self.doNumberZap()

	def __OK(self):
		from Screens.InfoBar import InfoBar
		InfoBarInstance = InfoBar.instance
		if not InfoBarInstance.LongButtonPressed:
			if self.zapNumberStarted:
				self.doNumberZap()
				return True

	def __cancel(self):
		self.zapNumberStarted = False
		self.numberZapField = None
		self["epgcursoractions"].setEnabled(True)
		self["okactions"].setEnabled(True)
		self["numberzapokactions"].setEnabled(False)
		self["number"].hide()

	def doNumberZap(self):
		if self.service is not None:
			self.zapToNumber(self.service, self.bouquet)
		self.__cancel()

	def handleServiceName(self):
		self.service, self.bouquet = self.searchNumber(int(self.numberZapField))
		self.zaptoservicename = ServiceReference(self.service).getServiceName()

	def zapToNumber(self, service, bouquet):
		if service is not None:
			self.setServicelistSelection(bouquet, service)
		self.onCreate()

	def searchNumberHelper(self, serviceHandler, num, bouquet):
		servicelist = serviceHandler.list(bouquet)
		if servicelist is not None:
			serviceIterator = servicelist.getNext()
			while serviceIterator.valid():
				if num == serviceIterator.getChannelNum():
					return serviceIterator
				serviceIterator = servicelist.getNext()
		return None

	def searchNumber(self, number):
		bouquet = self.servicelist.getRoot()
		serviceHandler = eServiceCenter.getInstance()
		service = self.searchNumberHelper(serviceHandler, number, bouquet)
		if config.usage.multibouquet.value:
			service = self.searchNumberHelper(serviceHandler, number, bouquet)
			if service is None:
				bouquet = self.servicelist.bouquet_root
				bouquetlist = serviceHandler.list(bouquet)
				if bouquetlist is not None:
					bouquet = bouquetlist.getNext()
					while bouquet.valid():
						if bouquet.flags & eServiceReference.isDirectory:
							service = self.searchNumberHelper(serviceHandler, number, bouquet)
							if service is not None:
								playable = not service.flags & (eServiceReference.isMarker | eServiceReference.isDirectory) or service.flags & eServiceReference.isNumberedMarker
								if not playable:
									service = None
								break
							if config.usage.alternative_number_mode.value:
								break
						bouquet = bouquetlist.getNext()
		return service, bouquet

class EPGBouquetSelection:
	def __init__(self, graphic):
		self['bouquetlist'] = EPGBouquetList(graphic)
		self['bouquetlist'].hide()
		self.bouquetlist_active = False

		self['bouquetokactions'] = ActionMap(['OkCancelActions'],
			{
				'cancel': self.bouquetListHide,
				'OK': self.bouquetListOK,
			}, -1)
		self["bouquetokactions"].setEnabled(False)

		self['bouquetcursoractions'] = ActionMap(['DirectionActions'],
			{
				'left': self.moveBouquetPageUp,
				'right': self.moveBouquetPageDown,
				'up': self.moveBouquetUp,
				'down': self.moveBouquetDown
			}, -1)
		self["bouquetcursoractions"].setEnabled(False)

	def _populateBouquetList(self):
		self['bouquetlist'].recalcEntrySize()
		self['bouquetlist'].fillBouquetList(self.bouquets)
		self['bouquetlist'].moveToService(self.startBouquet)
		self['bouquetlist'].setCurrentBouquet(self.startBouquet)
		self.setTitle(self['bouquetlist'].getCurrentBouquet())
		self.services = self.getBouquetServices(self.startBouquet)

	def getCurrentBouquet(self):
		cur = self['bouquetlist'].l.getCurrentSelection()
		return cur and cur[1]

	def bouquetList(self):
		if not self.bouquetlist_active:
			self.bouquetListShow()
		else:
			self.bouquetListHide()
			self['bouquetlist'].setCurrentIndex(self.curindex)

	def bouquetListOK(self):
		self.bouquetChanged()
		self.bouquetListHide()

	def bouquetListShow(self):
		self.curindex = self['bouquetlist'].l.getCurrentSelectionIndex()
		self['epgcursoractions'].setEnabled(False)
		self['okactions'].setEnabled(False)
		self['bouquetlist'].show()
		self['bouquetokactions'].setEnabled(True)
		self['bouquetcursoractions'].setEnabled(True)
		self.bouquetlist_active = True

	def bouquetListHide(self):
		self['bouquetokactions'].setEnabled(False)
		self['bouquetcursoractions'].setEnabled(False)
		self['bouquetlist'].hide()
		self['okactions'].setEnabled(True)
		self['epgcursoractions'].setEnabled(True)
		self.bouquetlist_active = False

	def moveBouquetUp(self):
		self['bouquetlist'].moveTo(self['bouquetlist'].instance.moveUp)
		self['bouquetlist'].fillBouquetList(self.bouquets)

	def moveBouquetDown(self):
		self['bouquetlist'].moveTo(self['bouquetlist'].instance.moveDown)
		self['bouquetlist'].fillBouquetList(self.bouquets)

	def moveBouquetPageUp(self):
		self['bouquetlist'].moveTo(self['bouquetlist'].instance.pageUp)
		self['bouquetlist'].fillBouquetList(self.bouquets)

	def moveBouquetPageDown(self):
		self['bouquetlist'].moveTo(self['bouquetlist'].instance.pageDown)
		self['bouquetlist'].fillBouquetList(self.bouquets)
