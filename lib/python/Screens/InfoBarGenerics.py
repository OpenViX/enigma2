# -*- coding: utf-8 -*-
from Components.ActionMap import ActionMap, HelpableActionMap, NumberActionMap
from Components.Harddisk import harddiskmanager, findMountPoint
from Components.Input import Input
from Components.Label import Label
from Components.MovieList import AUDIO_EXTENSIONS, MOVIE_EXTENSIONS, DVD_EXTENSIONS
from Components.PluginComponent import plugins
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Sources.Boolean import Boolean
from Components.config import config, configfile, ConfigBoolean, ConfigClock
from Components.SystemInfo import SystemInfo
from Components.UsageConfig import preferredInstantRecordPath, defaultMoviePath, preferredTimerPath, ConfigSelection
from Components.VolumeControl import VolumeControl
from Components.Pixmap import MovingPixmap, MultiPixmap
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Plugins.Plugin import PluginDescriptor

from Components.Timeshift import InfoBarTimeshift

from Screens.Screen import Screen
from Screens import ScreenSaver
from Screens.ChannelSelection import ChannelSelection, PiPZapSelection, BouquetSelector, EpgBouquetSelector
from Screens.ChoiceBox import ChoiceBox
from Screens.Dish import Dish
from Screens.EventView import EventViewEPGSelect, EventViewSimple
from Screens.EpgSelection import EPGSelection
from Screens.InputBox import InputBox
from Screens.MessageBox import MessageBox
from Screens.MinuteInput import MinuteInput
from Screens.TimerSelection import TimerSelection
from Screens.PictureInPicture import PictureInPicture
from Screens.PVRState import PVRState, TimeshiftState
from Screens.SubtitleDisplay import SubtitleDisplay
from Screens.RdsDisplay import RdsInfoDisplay, RassInteractive
from Screens.TimeDateInput import TimeDateInput
from Screens.TimerEdit import TimerEditList
from Screens.UnhandledKey import UnhandledKey
from ServiceReference import ServiceReference, isPlayableForCur

from RecordTimer import RecordTimerEntry, parseEvent, AFTEREVENT, findSafeRecordPath
from Screens.TimerEntry import TimerEntry as TimerEntry

from Tools import Notifications
from Tools.Directories import pathExists, fileExists
from Tools.KeyBindings import getKeyDescription

import NavigationInstance

from enigma import eTimer, eServiceCenter, eDVBServicePMTHandler, iServiceInformation, iPlayableService, iRecordableService, eServiceReference, eEPGCache, eActionMap, getDesktop, eDVBDB
from boxbranding import getBrandOEM, getMachineBuild

from time import time, localtime, strftime
from bisect import insort

import os, cPickle

# hack alert!
from Screens.Menu import MainMenu, Menu, mdom
from Screens.Setup import Setup
import Screens.Standby

# sys.maxint on 64bit (2**63-1) fails with OverflowError on eActionMap.bindAction use 32bit value (2**31-1)
maxint = 2147483647

def isStandardInfoBar(self):
	return self.__class__.__name__ == "InfoBar"

def isMoviePlayerInfoBar(self):
	return self.__class__.__name__ == "MoviePlayer"

def setResumePoint(session):
	global resumePointCache, resumePointCacheLast
	service = session.nav.getCurrentService()
	ref = session.nav.getCurrentlyPlayingServiceOrGroup()
	if (service is not None) and (ref is not None): # and (ref.type != 1):
		# ref type 1 has its own memory...
		seek = service.seek()
		if seek:
			pos = seek.getPlayPosition()
			if not pos[0]:
				key = ref.toString()
				lru = int(time())
				l = seek.getLength()
				if l:
					l = l[1]
				else:
					l = None
				resumePointCache[key] = [lru, pos[1], l]
				for k, v in resumePointCache.items():
					if v[0] < lru:
						candidate = k
						filepath = os.path.realpath(candidate.split(':')[-1])
						mountpoint = findMountPoint(filepath)
						if os.path.ismount(mountpoint) and not os.path.exists(filepath):
							del resumePointCache[candidate]
				saveResumePoints()

def delResumePoint(ref):
	global resumePointCache, resumePointCacheLast
	try:
		del resumePointCache[ref.toString()]
	except KeyError:
		pass
	saveResumePoints()

def getResumePoint(session):
	global resumePointCache
	ref = session.nav.getCurrentlyPlayingServiceOrGroup()
	if (ref is not None) and (ref.type != 1):
		try:
			entry = resumePointCache[ref.toString()]
			entry[0] = int(time()) # update LRU timestamp
			return entry[1]
		except KeyError:
			return None

def saveResumePoints():
	global resumePointCache, resumePointCacheLast
	try:
		f = open('/etc/enigma2/resumepoints.pkl', 'wb')
		cPickle.dump(resumePointCache, f, cPickle.HIGHEST_PROTOCOL)
		f.close()
	except Exception, ex:
		print "[InfoBarGenerics] Failed to write resumepoints:", ex
	resumePointCacheLast = int(time())

def loadResumePoints():
	try:
		file = open('/etc/enigma2/resumepoints.pkl', 'rb')
		PickleFile = cPickle.load(file)
		file.close()
		return PickleFile
	except Exception, ex:
		print "[InfoBarGenerics] Failed to load resumepoints:", ex
		return {}

def updateresumePointCache():
	global resumePointCache
	resumePointCache = loadResumePoints()

resumePointCache = loadResumePoints()
resumePointCacheLast = int(time())

whitelist_vbi = None
def reload_whitelist_vbi():
	global whitelist_vbi
	whitelist_vbi = [line.strip() for line in open('/etc/enigma2/whitelist_vbi', 'r').readlines()] if os.path.isfile('/etc/enigma2/whitelist_vbi') else []
reload_whitelist_vbi()

class InfoBarDish:
	def __init__(self):
		self.dishDialog = self.session.instantiateDialog(Dish)
		self.dishDialog.setAnimationMode(0)

class InfoBarLongKeyDetection:
	def __init__(self):
		eActionMap.getInstance().bindAction('', -maxint -1, self.detection) #highest prio
		self.LongButtonPressed = False

	#this function is called on every keypress!
	def detection(self, key, flag):
		if flag == 3:
			self.LongButtonPressed = True
		elif flag == 0:
			self.LongButtonPressed = False

class InfoBarUnhandledKey:
	def __init__(self):
		self.unhandledKeyDialog = self.session.instantiateDialog(UnhandledKey)
		self.unhandledKeyDialog.setAnimationMode(0)
		self.hideUnhandledKeySymbolTimer = eTimer()
		self.hideUnhandledKeySymbolTimer.callback.append(self.unhandledKeyDialog.hide)
		self.checkUnusedTimer = eTimer()
		self.checkUnusedTimer.callback.append(self.checkUnused)
		self.onLayoutFinish.append(self.unhandledKeyDialog.hide)
		eActionMap.getInstance().bindAction('', -maxint -1, self.actionA) #highest prio
		eActionMap.getInstance().bindAction('', maxint, self.actionB) #lowest prio
		self.flags = (1<<1)
		self.uflags = 0

	#this function is called on every keypress!
	def actionA(self, key, flag):
		try:
			print '[InfoBarGenerics] KEY: %s %s' % (key,getKeyDescription(key)[0])
		except:
			print '[InfoBarGenerics] KEY: %s' % key
		self.unhandledKeyDialog.hide()
		if self.closeSIB(key) and self.secondInfoBarScreen and self.secondInfoBarScreen.shown:
			self.secondInfoBarScreen.hide()
			self.secondInfoBarWasShown = False

		if flag != 4:
			if self.flags & (1<<1):
				self.flags = self.uflags = 0
			self.flags |= (1<<flag)
			if flag == 1: # break
				self.checkUnusedTimer.start(0, True)
		return 0

	def closeSIB(self, key):
		if key >= 12 and key not in (114, 115, 352, 103, 108, 402, 403, 407, 412):
			return True
		else:
			return False

	#this function is only called when no other action has handled this key
	def actionB(self, key, flag):
		if flag != 4:
			self.uflags |= (1<<flag)

	def checkUnused(self):
		if self.flags == self.uflags:
			self.unhandledKeyDialog.show()
			self.hideUnhandledKeySymbolTimer.start(2000, True)

class InfoBarScreenSaver:
	def __init__(self):
		self.onExecBegin.append(self.__onExecBegin)
		self.onExecEnd.append(self.__onExecEnd)
		self.screenSaverTimer = eTimer()
		self.screenSaverTimer.callback.append(self.screensaverTimeout)
		self.screensaver = self.session.instantiateDialog(ScreenSaver.Screensaver)
		self.onLayoutFinish.append(self.__layoutFinished)

	def __layoutFinished(self):
		self.screensaver.hide()

	def __onExecBegin(self):
		self.ScreenSaverTimerStart()

	def __onExecEnd(self):
		if self.screensaver.shown:
			self.screensaver.hide()
			eActionMap.getInstance().unbindAction('', self.keypressScreenSaver)
		self.screenSaverTimer.stop()

	def ScreenSaverTimerStart(self):
		time = int(config.usage.screen_saver.value)
		flag = self.seekstate[0]
		if not flag:
			ref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
			if ref and not (hasattr(self.session, "pipshown") and self.session.pipshown):
				ref = ref.toString().split(":")
				flag = ref[2] == "2" or os.path.splitext(ref[10])[1].lower() in AUDIO_EXTENSIONS
		if time and flag:
			self.screenSaverTimer.startLongTimer(time)
		else:
			self.screenSaverTimer.stop()

	def screensaverTimeout(self):
		if self.execing and not Screens.Standby.inStandby and not Screens.Standby.inTryQuitMainloop:
			self.hide()
			if hasattr(self, "pvrStateDialog"):
				self.pvrStateDialog.hide()
			self.screensaver.show()
			eActionMap.getInstance().bindAction('', -maxint - 1, self.keypressScreenSaver)

	def keypressScreenSaver(self, key, flag):
		if flag:
			self.screensaver.hide()
			self.show()
			self.ScreenSaverTimerStart()
			eActionMap.getInstance().unbindAction('', self.keypressScreenSaver)

class HideVBILine(Screen):
	def __init__(self, session):
		self.skin = """<screen position="0,0" size="%s,%s" flags="wfNoBorder" zPosition="1"/>""" % (getDesktop(0).size().width(), getDesktop(0).size().height() / 360 + 1)
		Screen.__init__(self, session)

class SecondInfoBar(Screen):
	ADD_TIMER = 0
	REMOVE_TIMER = 1

	def __init__(self, session):
		Screen.__init__(self, session)
		self["epg_description"] = ScrollLabel()
		self["channel"] = Label()
		self["key_red"] = Label()
		self["key_green"] = Label()
		self["key_yellow"] = Label()
		self["key_blue"] = Label()
		self["SecondInfoBar"] = ActionMap(["2ndInfobarActions"],
			{
				"prevPage": self.pageUp,
				"nextPage": self.pageDown,
				"prevEvent": self.prevEvent,
				"nextEvent": self.nextEvent,
				"timerAdd": self.timerAdd,
				"openSimilarList": self.openSimilarList,
			}, -1)

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedEventInfo: self.getEvent
			})

		self.onShow.append(self.__Show)
		self.onHide.append(self.__Hide)

	def pageUp(self):
		self["epg_description"].pageUp()

	def pageDown(self):
		self["epg_description"].pageDown()

	def __Show(self):
		if config.vixsettings.ColouredButtons.value:
			self["key_yellow"].setText(_("Search"))
		self["key_red"].setText(_("Similar"))
		self["key_blue"].setText(_("Extensions"))
		self["SecondInfoBar"].doBind()
		self.getEvent()

	def __Hide(self):
		if self["SecondInfoBar"].bound:
			self["SecondInfoBar"].doUnbind()

	def getEvent(self):
		self["epg_description"].setText("")
		self["channel"].setText("")
		ref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.getNowNext()
		epglist = self.epglist
		if not epglist:
			self.is_now_next = False
			epg = eEPGCache.getInstance()
			ptr = ref and ref.valid() and epg.lookupEventTime(ref, -1)
			if ptr:
				epglist.append(ptr)
				ptr = epg.lookupEventTime(ref, ptr.getBeginTime(), +1)
				if ptr:
					epglist.append(ptr)
		else:
			self.is_now_next = True
		if epglist:
			Event = self.epglist[0]
			Ref = ServiceReference(ref)
			callback = self.eventViewCallback
			self.cbFunc = callback
			self.currentService = Ref
			self.isRecording = (not Ref.ref.flags & eServiceReference.isGroup) and Ref.ref.getPath()
			self.event = Event
			self.key_green_choice = self.ADD_TIMER
			if self.isRecording:
				self["key_green"].setText("")
			else:
				self["key_green"].setText(_("Add timer"))
			self.setEvent(self.event)

	def getNowNext(self):
		epglist = [ ]
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		ptr = info and info.getEvent(0)
		if ptr:
			epglist.append(ptr)
		ptr = info and info.getEvent(1)
		if ptr:
			epglist.append(ptr)
		self.epglist = epglist

	def eventViewCallback(self, setEvent, setService, val): #used for now/next displaying
		epglist = self.epglist
		if len(epglist) > 1:
			tmp = epglist[0]
			epglist[0] = epglist[1]
			epglist[1] = tmp
			setEvent(epglist[0])

	def prevEvent(self):
		if self.cbFunc is not None:
			self.cbFunc(self.setEvent, self.setService, -1)

	def nextEvent(self):
		if self.cbFunc is not None:
			self.cbFunc(self.setEvent, self.setService, +1)

	def removeTimer(self, timer):
		timer.afterEvent = AFTEREVENT.NONE
		self.session.nav.RecordTimer.removeEntry(timer)
		self["key_green"].setText(_("Add timer"))
		self.key_green_choice = self.ADD_TIMER

	def timerAdd(self):
		self.hide()
		self.secondInfoBarWasShown = False
		if self.isRecording:
			return
		event = self.event
		serviceref = self.currentService
		if event is None:
			return
		eventid = event.getEventId()
		refstr = serviceref.ref.toString()
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventid and timer.service_ref.ref.toString() == refstr:
				cb_func = lambda ret : not ret or self.removeTimer(timer)
				self.session.openWithCallback(cb_func, MessageBox, _("Do you really want to delete %s?") % event.getEventName())
				break
		else:
			newEntry = RecordTimerEntry(self.currentService, checkOldTimers = True, dirname = preferredTimerPath(), *parseEvent(self.event))
			self.session.openWithCallback(self.finishedAdd, TimerEntry, newEntry)

	def finishedAdd(self, answer):
		# print "finished add"
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
			self["key_green"].setText(_("Remove timer"))
			self.key_green_choice = self.REMOVE_TIMER
		else:
			self["key_green"].setText(_("Add timer"))
			self.key_green_choice = self.ADD_TIMER
			# print "Timeredit aborted"

	def finishSanityCorrection(self, answer):
		self.finishedAdd(answer)

	def setService(self, service):
		self.currentService=service
		if self.isRecording:
			self["channel"].setText(_("Recording"))
		else:
			name = self.currentService.getServiceName()
			if name is not None:
				self["channel"].setText(name)
			else:
				self["channel"].setText(_("unknown service"))

	def sort_func(self,x,y):
		if x[1] < y[1]:
			return -1
		elif x[1] == y[1]:
			return 0
		else:
			return 1

	def setEvent(self, event):
		if event is None:
			return
		self.event = event
		try:
			name = event.getEventName()
			self["channel"].setText(name)
		except:
			pass
		description = event.getShortDescription()
		extended = event.getExtendedDescription()
		if description and extended:
			description += '\n'
		text = description + extended
		self.setTitle(event.getEventName())
		self["epg_description"].setText(text)
		serviceref = self.currentService
		eventid = self.event.getEventId()
		refstr = serviceref.ref.toString()
		isRecordEvent = False
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.eit == eventid and timer.service_ref.ref.toString() == refstr:
				isRecordEvent = True
				break
		if isRecordEvent and self.key_green_choice != self.REMOVE_TIMER:
			self["key_green"].setText(_("Remove timer"))
			self.key_green_choice = self.REMOVE_TIMER
		elif not isRecordEvent and self.key_green_choice != self.ADD_TIMER:
			self["key_green"].setText(_("Add timer"))
			self.key_green_choice = self.ADD_TIMER

	def openSimilarList(self):
		id = self.event and self.event.getEventId()
		refstr = str(self.currentService)
		if id is not None:
			self.hide()
			self.secondInfoBarWasShown = False
			self.session.open(EPGSelection, refstr, None, id)

class InfoBarShowHide(InfoBarScreenSaver):
	""" InfoBar show/hide control, accepts toggleShow and hide actions, might start
	fancy animations. """
	STATE_HIDDEN = 0
	STATE_HIDING = 1
	STATE_SHOWING = 2
	STATE_SHOWN = 3
	FLAG_CENTER_DVB_SUBS = 2048

	def __init__(self):
		self["ShowHideActions"] = ActionMap( ["InfobarShowHideActions"] ,
			{
				"LongOKPressed": self.toggleShowLong,
				"toggleShow": self.toggleShow,
				"hide": self.keyHide,
			}, 1) # lower prio to make it possible to override ok and cancel..

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.serviceStarted,
			})

		InfoBarScreenSaver.__init__(self)
		self.__state = self.STATE_SHOWN
		self.__locked = 0

		self.hideTimer = eTimer()
		self.hideTimer.callback.append(self.doTimerHide)
		self.hideTimer.start(5000, True)

		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

		self.onShowHideNotifiers = []

		self.standardInfoBar = False
		self.lastResetAlpha = True
		self.secondInfoBarScreen = ""
		if isStandardInfoBar(self):
			self.secondInfoBarScreen = self.session.instantiateDialog(SecondInfoBar)
			self.secondInfoBarScreen.show()

		from Screens.InfoBar import InfoBar
		InfoBarInstance = InfoBar.instance
		if InfoBarInstance:
			InfoBarInstance.hideVBILineScreen.hide()
		self.hideVBILineScreen = self.session.instantiateDialog(HideVBILine)
		self.hideVBILineScreen.show()

		self.onLayoutFinish.append(self.__layoutFinished)
		self.onExecBegin.append(self.__onExecBegin)

	def __onExecBegin(self):
		self.showHideVBI()

	def __layoutFinished(self):
		if self.secondInfoBarScreen:
			self.secondInfoBarScreen.hide()
			self.standardInfoBar = True
		self.secondInfoBarWasShown = False
		self.hideVBILineScreen.hide()
		self.EventViewIsShown = False

	def __onShow(self):
		self.__state = self.STATE_SHOWN
		for x in self.onShowHideNotifiers:
			x(True)
		self.startHideTimer()
		VolumeControl.instance and VolumeControl.instance.showMute()

	def doDimming(self):
		if config.usage.show_infobar_do_dimming.value:
			self.dimmed = self.dimmed-1
		else:
			self.dimmed = 0
		self.DimmingTimer.stop()
		self.doHide()

	def unDimming(self):
		self.unDimmingTimer.stop()
		self.doWriteAlpha(config.av.osd_alpha.value)

	def doWriteAlpha(self, value):
		if fileExists("/proc/stb/video/alpha"):
			f=open("/proc/stb/video/alpha","w")
			f.write("%i" % (value))
			f.close()
			if value == config.av.osd_alpha.value:
				self.lastResetAlpha = True
			else:
				self.lastResetAlpha = False

	def __onHide(self):
		self.__state = self.STATE_HIDDEN
		self.resetAlpha()
		for x in self.onShowHideNotifiers:
			x(False)

	def resetAlpha(self):
		if config.usage.show_infobar_do_dimming.value and self.lastResetAlpha is False:
			self.unDimmingTimer = eTimer()
			self.unDimmingTimer.callback.append(self.unDimming)
			self.unDimmingTimer.start(300, True)

	def keyHide(self):
		if self.__state == self.STATE_HIDDEN:
			if config.vixsettings.InfoBarEpg_mode.value == "2":
				self.openInfoBarEPG()
			else:
				self.hide()
				if self.secondInfoBarScreen and self.secondInfoBarScreen.shown:
					self.secondInfoBarScreen.hide()
					self.secondInfoBarWasShown = False
			if self.session.pipshown and "popup" in config.usage.pip_hideOnExit.value:
				if config.usage.pip_hideOnExit.value == "popup":
					self.session.openWithCallback(self.hidePipOnExitCallback, MessageBox, _("Disable Picture in Picture"), simple=True)
				else:
					self.hidePipOnExitCallback(True)
		else:
			self.hide()
			if hasattr(self, "pvrStateDialog"):
				self.pvrStateDialog.hide()

	def hidePipOnExitCallback(self, answer):
		if answer:
			self.showPiP()

	def connectShowHideNotifier(self, fnc):
		if not fnc in self.onShowHideNotifiers:
			self.onShowHideNotifiers.append(fnc)

	def disconnectShowHideNotifier(self, fnc):
		if fnc in self.onShowHideNotifiers:
			self.onShowHideNotifiers.remove(fnc)

	def serviceStarted(self):
		if self.execing:
			if config.usage.show_infobar_on_zap.value:
				self.doShow()
		self.showHideVBI()

	def startHideTimer(self):
		if self.__state == self.STATE_SHOWN and not self.__locked:
			self.hideTimer.stop()
			idx = config.usage.infobar_timeout.index
			if idx:
				self.hideTimer.start(idx*1000, True)
		elif (self.secondInfoBarScreen and self.secondInfoBarScreen.shown) or ((not config.usage.show_second_infobar.value or isMoviePlayerInfoBar(self)) and self.EventViewIsShown):
			self.hideTimer.stop()
			idx = config.usage.show_second_infobar.index - 1
			if idx:
				self.hideTimer.start(idx*1000, True)
		elif hasattr(self, "pvrStateDialog"):
			self.hideTimer.stop()
			idx = config.usage.infobar_timeout.index
			if idx:
				self.hideTimer.start(idx*1000, True)

	def doShow(self):
		self.show()
		self.startHideTimer()

	def doTimerHide(self):
		self.hideTimer.stop()
		self.DimmingTimer = eTimer()
		self.DimmingTimer.callback.append(self.doDimming)
		self.DimmingTimer.start(70, True)
		self.dimmed = config.usage.show_infobar_dimming_speed.value

	def doHide(self):
		if self.__state != self.STATE_HIDDEN:
			if self.dimmed > 0:
				self.doWriteAlpha((config.av.osd_alpha.value*self.dimmed/config.usage.show_infobar_dimming_speed.value))
				self.DimmingTimer.start(5, True)
			else:
				self.DimmingTimer.stop()
				self.hide()
		elif self.__state == self.STATE_HIDDEN and self.secondInfoBarScreen and self.secondInfoBarScreen.shown:
			if self.dimmed > 0:
				self.doWriteAlpha((config.av.osd_alpha.value*self.dimmed/config.usage.show_infobar_dimming_speed.value))
				self.DimmingTimer.start(5, True)
			else:
				self.DimmingTimer.stop()
				self.secondInfoBarScreen.hide()
				self.secondInfoBarWasShown = False
				self.resetAlpha()
		elif self.__state == self.STATE_HIDDEN and self.EventViewIsShown:
			try:
				self.eventView.close()
			except:
				pass
			self.EventViewIsShown = False
#		elif hasattr(self, "pvrStateDialog"):
#			if self.dimmed > 0:
#				self.doWriteAlpha((config.av.osd_alpha.value*self.dimmed/config.usage.show_infobar_dimming_speed.value))
#				self.DimmingTimer.start(5, True)
#			else:
#				self.DimmingTimer.stop()
#				try:
#					self.pvrStateDialog.hide()
#				except:
#					pass

	def toggleShow(self):
		if not hasattr(self, "LongButtonPressed"):
			self.LongButtonPressed = False
		if not self.LongButtonPressed:
			if self.__state == self.STATE_HIDDEN:
				if not self.secondInfoBarWasShown:
					self.show()
				if self.secondInfoBarScreen:
					self.secondInfoBarScreen.hide()
				self.secondInfoBarWasShown = False
				self.EventViewIsShown = False
			elif isStandardInfoBar(self) and config.usage.show_second_infobar.value == "EPG":
				self.showDefaultEPG()
			elif isStandardInfoBar(self) and config.usage.show_second_infobar.value == "INFOBAREPG":
				self.openInfoBarEPG()
			elif self.secondInfoBarScreen and config.usage.show_second_infobar.value != "none" and not self.secondInfoBarScreen.shown:
				self.hide()
				self.secondInfoBarScreen.show()
				self.secondInfoBarWasShown = True
				self.startHideTimer()
			elif isMoviePlayerInfoBar(self) and not self.EventViewIsShown and config.usage.show_second_infobar.value:
				self.hide()
				try:
					self.openEventView(True)
				except:
					pass
				self.EventViewIsShown = True
				self.startHideTimer()
			else:
				self.hide()
				if self.secondInfoBarScreen and self.secondInfoBarScreen.shown:
					self.secondInfoBarScreen.hide()
				elif self.EventViewIsShown:
					try:
						self.eventView.close()
					except:
						pass
					self.EventViewIsShown = False

	def toggleShowLong(self):
		if self.LongButtonPressed:
			if isinstance(self, InfoBarEPG):
				if config.vixsettings.InfoBarEpg_mode.value == "1":
					self.openInfoBarEPG()

	def lockShow(self):
		self.__locked += 1
		if self.execing:
			self.show()
			self.hideTimer.stop()

	def unlockShow(self):
		if config.usage.show_infobar_do_dimming.value and self.lastResetAlpha is False:
			self.doWriteAlpha(config.av.osd_alpha.value)
		try:
			self.__locked -= 1
		except:
			self.__locked = 0

		if self.__locked  <0:
			self.__locked = 0
		if self.execing:
			self.startHideTimer()

	def checkHideVBI(self, service = None):
		service = service or self.session.nav.getCurrentlyPlayingServiceReference()
		servicepath = service and service.getPath()
		if servicepath:
			if servicepath.startswith("/"):
				if service.toString().startswith("1:"):
					info = eServiceCenter.getInstance().info(service)
					service = info and info.getInfoString(service, iServiceInformation.sServiceref)
					service = service and eServiceReference(service)
					if service:
						print service, service and service.toString()
					return service and ":".join(service.toString().split(":")[:11]) in whitelist_vbi
				else:
					return ".hidevbi." in servicepath.lower()
		return service and service.toString() in whitelist_vbi

	def showHideVBI(self):
		if self.checkHideVBI():
			self.hideVBILineScreen.show()
		else:
			self.hideVBILineScreen.hide()

	def ToggleHideVBI(self, service = None):
		service = service or self.session.nav.getCurrentlyPlayingServiceReference()
		if service:
			service = service.toString()
			global whitelist_vbi
			if service in whitelist_vbi:
				whitelist_vbi.remove(service)
			else:
				whitelist_vbi.append(service)
			open('/etc/enigma2/whitelist_vbi', 'w').write('\n'.join(whitelist_vbi))
			self.showHideVBI()

class BufferIndicator(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self["status"] = Label()
		self.mayShow = False
		self.mayShowTimer = eTimer()
		self.mayShowTimer.callback.append(self.mayShowEndTimer)
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evBuffering: self.bufferChanged,
				iPlayableService.evStart: self.__evStart,
				iPlayableService.evGstreamerPlayStarted: self.__evGstreamerPlayStarted,
			})

	def bufferChanged(self):
		if self.mayShow:
			value = self.getBufferValue()
			if value and value != 100:
				self["status"].setText(_("Buffering %d%%") % value)
				if not self.shown:
					self.show()

	def __evStart(self):
		self.hide()
		self.mayShow = False
		self.mayShowTimer.start(1000, True)

	def __evGstreamerPlayStarted(self):
		self.mayShow = False
		self.mayShowTimer.stop()
		self.hide()

	def	mayShowEndTimer(self):
		self.mayShow = True
		if self.getBufferValue() == 0:
			self["status"].setText(_("No data received yet"))
			self.show()

	def getBufferValue(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		return info and info.getInfo(iServiceInformation.sBuffer)

class InfoBarBuffer():
	def __init__(self):
		self.bufferScreen = self.session.instantiateDialog(BufferIndicator)
		self.bufferScreen.hide()

class NumberZap(Screen):
	def quit(self):
		self.Timer.stop()
		self.close()

	def keyOK(self):
		self.Timer.stop()
		self.close(self.service, self.bouquet)

	def handleServiceName(self):
		if self.searchNumber:
			self.service, self.bouquet = self.searchNumber(int(self["number"].getText()))
			self["servicename"].setText(ServiceReference(self.service).getServiceName())
			if not self.startBouquet:
				self.startBouquet = self.bouquet

	def keyBlue(self):
		self.Timer.start(5000, True)
		if self.searchNumber:
			if self.startBouquet == self.bouquet:
				self.service, self.bouquet = self.searchNumber(int(self["number"].getText()), firstBouquetOnly = True)
			else:
				self.service, self.bouquet = self.searchNumber(int(self["number"].getText()))
			self["servicename"].setText(ServiceReference(self.service).getServiceName())

	def keyNumberGlobal(self, number):
		self.Timer.start(5000, True)
		self.numberString += str(number)
		self["number"].setText(self.numberString)
		self["number_summary"].setText(self.numberString)

		self.handleServiceName()

		if len(self.numberString) >= 4:
			self.keyOK()

	def __init__(self, session, number, searchNumberFunction = None):
		Screen.__init__(self, session)
		self.onChangedEntry = [ ]
		self.numberString = str(number)
		self.searchNumber = searchNumberFunction
		self.startBouquet = None

		self["channel"] = Label(_("Channel:"))
		self["channel_summary"] = StaticText(_("Channel:"))

		self["number"] = Label(self.numberString)
		self["number_summary"] = StaticText(self.numberString)
		self["servicename"] = Label()

		self.handleServiceName()

		self["actions"] = NumberActionMap( [ "SetupActions", "ShortcutActions" ],
			{
				"cancel": self.quit,
				"ok": self.keyOK,
				"blue": self.keyBlue,
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
				"0": self.keyNumberGlobal
			})

		self.Timer = eTimer()
		self.Timer.callback.append(self.keyOK)
		self.Timer.start(5000, True)

class InfoBarNumberZap:
	""" Handles an initial number for NumberZapping """
	def __init__(self):
		self["NumberActions"] = NumberActionMap( [ "NumberActions"],
			{
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
				"0": self.keyNumberGlobal,
			})

	def keyNumberGlobal(self, number):
		if self.pvrStateDialog.has_key("PTSSeekPointer") and self.timeshiftEnabled() and self.isSeekable():
			# noinspection PyProtectedMember
			InfoBarTimeshiftState._mayShow(self)
			self.pvrStateDialog["PTSSeekPointer"].setPosition((self.pvrStateDialog["PTSSeekBack"].instance.size().width()-4)/2, self.pvrStateDialog["PTSSeekPointer"].position[1])
			if self.seekstate != self.SEEK_STATE_PLAY:
				self.setSeekState(self.SEEK_STATE_PLAY)
			self.ptsSeekPointerOK()
			return

		if self.pts_blockZap_timer.isActive():
			return

		# if self.save_current_timeshift and self.timeshiftEnabled():
		# 	InfoBarTimeshift.saveTimeshiftActions(self)
		# 	return

		if number == 0:
			if isinstance(self, InfoBarPiP) and self.pipHandles0Action():
				self.pipDoHandle0Action()
			elif len(self.servicelist.history) > 1:
				self.checkTimeshiftRunning(self.recallPrevService)
		else:
			if "TimeshiftActions" in self and self.timeshiftEnabled():
				ts = self.getTimeshift()
				if ts and ts.isTimeshiftActive():
					return
			self.session.openWithCallback(self.numberEntered, NumberZap, number, self.searchNumber)

	def recallPrevService(self, reply):
		if reply:
			if config.usage.panicbutton.value:
				if self.session.pipshown:
					del self.session.pip
					self.session.pipshown = False
				self.servicelist.history_tv = []
				self.servicelist.history_radio = []
				self.servicelist.history = self.servicelist.history_tv
				self.servicelist.history_pos = 0
				self.servicelist2.history_tv = []
				self.servicelist2.history_radio = []
				self.servicelist2.history = self.servicelist.history_tv
				self.servicelist2.history_pos = 0
				if config.usage.multibouquet.value:
					bqrootstr = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'
				else:
					bqrootstr = '%s FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet'% self.service_types
				serviceHandler = eServiceCenter.getInstance()
				rootbouquet = eServiceReference(bqrootstr)
				bouquet = eServiceReference(bqrootstr)
				bouquetlist = serviceHandler.list(bouquet)
				if not bouquetlist is None:
					while True:
						bouquet = bouquetlist.getNext()
						if not bouquet.valid(): break
						if bouquet.flags & eServiceReference.isDirectory:
							self.servicelist.clearPath()
							self.servicelist.setRoot(bouquet)
							servicelist = serviceHandler.list(bouquet)
							if not servicelist is None:
								serviceIterator = servicelist.getNext()
								while serviceIterator.valid():
									service, bouquet2 = self.searchNumber(1)
									if service == serviceIterator: break
									serviceIterator = servicelist.getNext()
								if serviceIterator.valid() and service == serviceIterator: break
					self.servicelist.enterPath(rootbouquet)
					self.servicelist.enterPath(bouquet)
					self.servicelist.saveRoot()
					self.servicelist2.enterPath(rootbouquet)
					self.servicelist2.enterPath(bouquet)
					self.servicelist2.saveRoot()
				self.selectAndStartService(service, bouquet)
			else:
				self.servicelist.recallPrevService()

	def numberEntered(self, service = None, bouquet = None):
		if service:
			self.selectAndStartService(service, bouquet)

	def searchNumberHelper(self, serviceHandler, num, bouquet):
		servicelist = serviceHandler.list(bouquet)
		if servicelist:
			serviceIterator = servicelist.getNext()
			while serviceIterator.valid():
				if num == serviceIterator.getChannelNum():
					return serviceIterator
				serviceIterator = servicelist.getNext()
		return None

	def searchNumber(self, number, firstBouquetOnly=False, bouquet=None):
		bouquet = bouquet or self.servicelist.getRoot()
		service = None
		serviceHandler = eServiceCenter.getInstance()
		if not firstBouquetOnly:
			service = self.searchNumberHelper(serviceHandler, number, bouquet)
		if config.usage.multibouquet.value and not service:
			bouquet = self.servicelist.bouquet_root
			bouquetlist = serviceHandler.list(bouquet)
			if bouquetlist:
				bouquet = bouquetlist.getNext()
				while bouquet.valid():
					if bouquet.flags & eServiceReference.isDirectory and not bouquet.flags & eServiceReference.isInvisible:
						service = self.searchNumberHelper(serviceHandler, number, bouquet)
						if service:
							playable = not (service.flags & (eServiceReference.isMarker|eServiceReference.isDirectory)) or (service.flags & eServiceReference.isNumberedMarker)
							if not playable:
								service = None
							break
						if config.usage.alternative_number_mode.value or firstBouquetOnly:
							break
					bouquet = bouquetlist.getNext()
		return service, bouquet

	def selectAndStartService(self, service, bouquet):
		if service:
			if self.servicelist.getRoot() != bouquet: #already in correct bouquet?
				self.servicelist.clearPath()
				if self.servicelist.bouquet_root != bouquet:
					self.servicelist.enterPath(self.servicelist.bouquet_root)
				self.servicelist.enterPath(bouquet)
			self.servicelist.setCurrentSelection(service) #select the service in servicelist
			self.servicelist.zap(enable_pipzap = True)
			self.servicelist.correctChannelNumber()
			self.servicelist.startRoot = None

	def zapToNumber(self, number):
		service, bouquet = self.searchNumber(number)
		self.selectAndStartService(service, bouquet)

config.misc.initialchannelselection = ConfigBoolean(default = True)

class InfoBarChannelSelection:
	""" ChannelSelection - handles the channelSelection dialog and the initial
	channelChange actions which open the channelSelection dialog """
	def __init__(self):
		#instantiate forever
		self.servicelist = self.session.instantiateDialog(ChannelSelection)
		self.servicelist2 = self.session.instantiateDialog(PiPZapSelection)
		self.tscallback = None

		self["ChannelSelectActions"] = HelpableActionMap(self, "InfobarChannelSelection",
			{
				"switchChannelUp": (self.switchChannelUp, _("Open service list and select the previous channel")),
				"switchChannelDown": (self.switchChannelDown, _("Open service list and select the next channel")),
				"switchChannelUpLong": (self.switchChannelUp, _("Open service list and select the previous channel for PiP")),
				"switchChannelDownLong": (self.switchChannelDown, _("Open service list and select the next channel for PiP")),
				"zapUp": (self.zapUp, _("Switch to the previous channel")),
				"zapDown": (self.zapDown, _("Switch to the next channel")),
				"historyBack": (self.historyBack, _("Switch to the previous channel in history")),
				"historyNext": (self.historyNext, _("Switch to the next channel in history")),
				"openServiceList": (self.openServiceList, _("Open the service list")),
				"openSatellites": (self.openSatellites, _("Open the satellites list")),
				"openBouquets": (self.openBouquets, _("Open the favourites list")),
				"LeftPressed": self.LeftPressed,
				"RightPressed": self.RightPressed,
				"ChannelPlusPressed": self.ChannelPlusPressed,
				"ChannelMinusPressed": self.ChannelMinusPressed,
				"ChannelPlusPressedLong": self.ChannelPlusPressed,
				"ChannelMinusPressedLong": self.ChannelMinusPressed,
			})

	def LeftPressed(self):
		if config.vixsettings.InfoBarEpg_mode.value == "3" and config.usage.show_second_infobar.value != "INFOBAREPG":
			self.openInfoBarEPG()
		else:
			self.zapUp()

	def RightPressed(self):
		if config.vixsettings.InfoBarEpg_mode.value == "3" and config.usage.show_second_infobar.value != "INFOBAREPG":
			self.openInfoBarEPG()
		else:
			self.zapDown()

	def ChannelPlusPressed(self):
		if config.usage.channelbutton_mode.value == "0" or config.usage.show_second_infobar.value == "INFOBAREPG":
			self.zapDown()
		elif config.usage.channelbutton_mode.value == "1":
			self.openServiceList()
		elif config.usage.channelbutton_mode.value == "2":
			self.serviceListType = "Norm"
			self.servicelist.showFavourites()
			self.session.execDialog(self.servicelist)

	def ChannelMinusPressed(self):
		if config.usage.channelbutton_mode.value == "0" or config.usage.show_second_infobar.value == "INFOBAREPG":
			self.zapUp()
		elif config.usage.channelbutton_mode.value == "1":
			self.openServiceList()
		elif config.usage.channelbutton_mode.value == "2":
			self.serviceListType = "Norm"
			self.servicelist.showFavourites()
			self.session.execDialog(self.servicelist)

	def showTvChannelList(self, zap=False):
		self.servicelist.setModeTv()
		if zap:
			self.servicelist.zap()
		if config.usage.show_servicelist.value:
			self.session.execDialog(self.servicelist)

	def showRadioChannelList(self, zap=False):
		self.servicelist.setModeRadio()
		if zap:
			self.servicelist.zap()
		if config.usage.show_servicelist.value:
			self.session.execDialog(self.servicelist)

	def historyBack(self):
		if config.usage.historymode.value == "0":
			self.servicelist.historyBack()
		else:
			self.servicelist.historyZap(-1)

	def historyNext(self):
		if config.usage.historymode.value == "0":
			self.servicelist.historyNext()
		else:
			self.servicelist.historyZap(+1)

	def switchChannelUp(self):
		if not self.secondInfoBarScreen.shown:
			self.keyHide()
			if not self.LongButtonPressed or SystemInfo.get("NumVideoDecoders", 1) <= 1:
				if not config.usage.show_bouquetalways.value:
					if "keep" not in config.usage.servicelist_cursor_behavior.value:
						self.servicelist.moveUp()
					self.session.execDialog(self.servicelist)
				else:
					self.servicelist.showFavourites()
					self.session.execDialog(self.servicelist)
			elif self.LongButtonPressed:
				if not config.usage.show_bouquetalways.value:
					if "keep" not in config.usage.servicelist_cursor_behavior.value:
						self.servicelist2.moveUp()
					self.session.execDialog(self.servicelist2)
				else:
					self.servicelist2.showFavourites()
					self.session.execDialog(self.servicelist2)

	def switchChannelDown(self):
		if not self.secondInfoBarScreen.shown:
			self.keyHide()
			if not self.LongButtonPressed or SystemInfo.get("NumVideoDecoders", 1) <= 1:
				if not config.usage.show_bouquetalways.value:
					if "keep" not in config.usage.servicelist_cursor_behavior.value:
						self.servicelist.moveDown()
					self.session.execDialog(self.servicelist)
				else:
					self.servicelist.showFavourites()
					self.session.execDialog(self.servicelist)
			elif self.LongButtonPressed:
				if not config.usage.show_bouquetalways.value:
					if "keep" not in config.usage.servicelist_cursor_behavior.value:
						self.servicelist2.moveDown()
					self.session.execDialog(self.servicelist2)
				else:
					self.servicelist2.showFavourites()
					self.session.execDialog(self.servicelist2)

	def openServiceList(self):
		self.session.execDialog(self.servicelist)

	def openServiceListPiP(self):
		self.session.execDialog(self.servicelist2)

	def openSatellites(self):
		self.servicelist.showSatellites()
		self.session.execDialog(self.servicelist)

	def openBouquets(self):
		self.servicelist.showFavourites()
		self.session.execDialog(self.servicelist)

	def zapUp(self):
		if not self.LongButtonPressed or SystemInfo.get("NumVideoDecoders", 1) <= 1:
			if self.pts_blockZap_timer.isActive():
				return

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
						if cur:
							if self.servicelist.dopipzap:
								isPlayable = self.session.pip.isPlayableForPipService(cur)
							else:
								isPlayable = isPlayableForCur(cur)
						if cur and (cur.toString() == prev or isPlayable):
							break
			else:
				self.servicelist.moveUp()
			self.servicelist.zap(enable_pipzap = True)

		elif self.LongButtonPressed:
			if not hasattr(self.session, 'pip') and not self.session.pipshown:
				self.session.open(MessageBox, _("Please open Picture in Picture first"), MessageBox.TYPE_ERROR)
				return

			from Screens.ChannelSelection import ChannelSelection
			ChannelSelectionInstance = ChannelSelection.instance
			ChannelSelectionInstance.dopipzap = True
			if self.servicelist2.inBouquet():
				prev = self.servicelist2.getCurrentSelection()
				if prev:
					prev = prev.toString()
					while True:
						if config.usage.quickzap_bouquet_change.value:
							if self.servicelist2.atBegin():
								self.servicelist2.prevBouquet()
						self.servicelist2.moveUp()
						cur = self.servicelist2.getCurrentSelection()
						if cur:
							if ChannelSelectionInstance.dopipzap:
								isPlayable = self.session.pip.isPlayableForPipService(cur)
							else:
								isPlayable = isPlayableForCur(cur)
						if cur and (cur.toString() == prev or isPlayable):
							break
			else:
				self.servicelist2.moveUp()
			self.servicelist2.zap(enable_pipzap = True)
			ChannelSelectionInstance.dopipzap = False

	def openFavouritesList(self):
		self.servicelist.showFavourites()
		self.openServiceList()

	def zapDown(self):
		if not self.LongButtonPressed or SystemInfo.get("NumVideoDecoders", 1) <= 1:
			if self.pts_blockZap_timer.isActive():
				return

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
						if cur:
							if self.servicelist.dopipzap:
								isPlayable = self.session.pip.isPlayableForPipService(cur)
							else:
								isPlayable = isPlayableForCur(cur)
						if cur and (cur.toString() == prev or isPlayable):
							break
			else:
				self.servicelist.moveDown()
			self.servicelist.zap(enable_pipzap = True)
		elif self.LongButtonPressed:
			if not hasattr(self.session, 'pip') and not self.session.pipshown:
				self.session.open(MessageBox, _("Please open Picture in Picture first"), MessageBox.TYPE_ERROR)
				return

			from Screens.ChannelSelection import ChannelSelection
			ChannelSelectionInstance = ChannelSelection.instance
			ChannelSelectionInstance.dopipzap = True
			if self.servicelist2.inBouquet():
				prev = self.servicelist2.getCurrentSelection()
				if prev:
					prev = prev.toString()
					while True:
						if config.usage.quickzap_bouquet_change.value and self.servicelist2.atEnd():
							self.servicelist2.nextBouquet()
						else:
							self.servicelist2.moveDown()
						cur = self.servicelist2.getCurrentSelection()
						if cur:
							if ChannelSelectionInstance.dopipzap:
								isPlayable = self.session.pip.isPlayableForPipService(cur)
							else:
								isPlayable = isPlayableForCur(cur)
						if cur and (cur.toString() == prev or isPlayable):
							break
			else:
				self.servicelist2.moveDown()
			self.servicelist2.zap(enable_pipzap = True)
			ChannelSelectionInstance.dopipzap = False

class InfoBarMenu:
	""" Handles a menu action, to open the (main) menu """
	def __init__(self):
		self["MenuActions"] = HelpableActionMap(self, "InfobarMenuActions",
			{
				"mainMenu": (self.mainMenu, _("Enter main menu...")),
				"showNetworkSetup": (self.showNetworkMounts, _("Show network mounts ...")),
				"showSystemSetup": (self.showSystemMenu, _("Show network mounts ...")),
				"showRFmod": (self.showRFSetup, _("Show RFmod setup...")),
				"toggleAspectRatio": (self.toggleAspectRatio, _("Toggle aspect ratio...")),
			})
		self.session.infobar = None

	def mainMenu(self):
		# print "loading mainmenu XML..."
		menu = mdom.getroot()
		assert menu.tag == "menu", "root element in menu must be 'menu'!"

		self.session.infobar = self
		# so we can access the currently active infobar from screens opened from within the mainmenu
		# at the moment used from the SubserviceSelection

		self.session.openWithCallback(self.mainMenuClosed, MainMenu, menu)

	def mainMenuClosed(self, *val):
		self.session.infobar = None

	def toggleAspectRatio(self):
		ASPECT = [ "auto", "16_9", "4_3" ]
		ASPECT_MSG = { "auto":"Auto", "16_9":"16:9", "4_3":"4:3" }
		if config.av.aspect.value in ASPECT:
			index = ASPECT.index(config.av.aspect.value)
			config.av.aspect.value = ASPECT[(index+1)%3]
		else:
			config.av.aspect.value = "auto"
		config.av.aspect.save()
		self.session.open(MessageBox, _("AV aspect is %s." % ASPECT_MSG[config.av.aspect.value]), MessageBox.TYPE_INFO, timeout=5)

	def showSystemMenu(self):
		menulist = mdom.getroot().findall('menu')
		for item in menulist:
			if item.attrib['entryID'] == 'setup_selection':
				menulist = item.findall('menu')
				for item in menulist:
					if item.attrib['entryID'] == 'system_selection':
						menu = item
		assert menu.tag == "menu", "root element in menu must be 'menu'!"
		self.session.openWithCallback(self.mainMenuClosed, Menu, menu)

	def showNetworkMounts(self):
		menulist = mdom.getroot().findall('menu')
		for item in menulist:
			if item.attrib['entryID'] == 'setup_selection':
				menulist = item.findall('menu')
				for item in menulist:
					if item.attrib['entryID'] == 'network_menu':
						menu = item
		assert menu.tag == "menu", "root element in menu must be 'menu'!"
		self.session.openWithCallback(self.mainMenuClosed, Menu, menu)

	def showRFSetup(self):
		self.session.openWithCallback(self.mainMenuClosed, Setup, 'RFmod')


class InfoBarSimpleEventView:
	def __init__(self):
		pass

class SimpleServicelist:
	def __init__(self, services):
		self.services = services
		self.length = len(services)
		self.current = 0

	def selectService(self, service):
		if not self.length:
			self.current = -1
			return False
		else:
			self.current = 0
			while self.services[self.current].ref != service:
				self.current += 1
				if self.current >= self.length:
					return False
		return True

	def nextService(self):
		if not self.length:
			return
		if self.current+1 < self.length:
			self.current += 1
		else:
			self.current = 0

	def prevService(self):
		if not self.length:
			return
		if self.current-1 > -1:
			self.current -= 1
		else:
			self.current = self.length - 1

	def currentService(self):
		if not self.length or self.current >= self.length:
			return None
		return self.services[self.current]


class InfoBarEPG:
	""" EPG - Opens an EPG list when the showEPGList action fires """
	def __init__(self):
		self.is_now_next = False
		self.dlg_stack = []
		self.bouquetSel = None
		self.eventView = None
		self.epglist = []
		self.defaultEPGType = self.getDefaultEPGtype()
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedEventInfo: self.__evEventInfoChanged,
			})

		self["EPGActions"] = HelpableActionMap(self, "InfobarEPGActions",
			{
				"RedPressed": (self.RedPressed, _("Show epg")),
				"IPressed": (self.IPressed, _("Show program information...")),
				"InfoPressed": (self.InfoPressed, _("Show program information...")),
				"showEventInfoPlugin": (self.showEventInfoPlugins, _("List EPG functions...")),
				"EPGPressed":  (self.showDefaultEPG, _("Show EPG...")),
				"showEventGuidePlugin": (self.showEventGuidePlugins, _("List EPG functions...")),
				"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
			})

	def getEPGPluginList(self):
		pluginlist = [(p.name, boundFunction(self.runPlugin, p)) for p in plugins.getPlugins(where = PluginDescriptor.WHERE_EVENTINFO)]
		if pluginlist:
			pluginlist.append((_("Event Info"), self.openEventView))
			pluginlist.append((_("Graphical EPG"), self.openGraphEPG))
			pluginlist.append((_("Infobar EPG"), self.openInfoBarEPG))
			pluginlist.append((_("Multi EPG"), self.openMultiServiceEPG))
			pluginlist.append((_("Show EPG for current channel..."), self.openSingleServiceEPG))
		return pluginlist

	def getDefaultEPGtype(self):
		pluginlist = self.getEPGPluginList()
		config.usage.defaultEPGType=ConfigSelection(default = "None", choices = pluginlist)
		for plugin in pluginlist:
			if plugin[0] == config.usage.defaultEPGType.value:
				return plugin[1]
		return None

	def showEventInfoPlugins(self):
		if isStandardInfoBar(self):
			if getBrandOEM() not in ('xtrend', 'odin', 'ini', 'dags' ,'gigablue', 'xp'):
				pluginlist = self.getEPGPluginList()
				if pluginlist:
#					pluginlist.append((_("Select default EPG type..."), self.SelectDefaultInfoPlugin))
					self.session.openWithCallback(self.EventInfoPluginChosen, ChoiceBox, title=_("Please choose an extension..."), list=pluginlist, skin_name="EPGExtensionsList", reorderConfig="eventinfo_order")
				else:
					self.openSingleServiceEPG()
			else:
				self.openEventView()
		elif isMoviePlayerInfoBar(self):
			self.openEventView()

	def showEventGuidePlugins(self):
		if isMoviePlayerInfoBar(self):
			self.openEventView()
		else:
			pluginlist = self.getEPGPluginList()
			if pluginlist:
#				pluginlist.append((_("Select default EPG type..."), self.SelectDefaultInfoPlugin))
				self.session.openWithCallback(self.EventInfoPluginChosen, ChoiceBox, title=_("Please choose an extension..."), list = pluginlist, skin_name = "EPGExtensionsList")
			else:
				self.openSingleServiceEPG()

	def SelectDefaultInfoPlugin(self):
		self.session.openWithCallback(self.DefaultInfoPluginChosen, ChoiceBox, title=_("Please select a default EPG type..."), list = self.getEPGPluginList(), skin_name = "EPGExtensionsList")

	def DefaultInfoPluginChosen(self, answer):
		if answer is not None:
			self.defaultEPGType = answer[1]
			config.usage.defaultEPGType.value = answer[0]
			config.usage.defaultEPGType.save()
			configfile.save()

	def runPlugin(self, plugin):
		plugin(session = self.session, servicelist=self.servicelist)

	def EventInfoPluginChosen(self, answer):
		if answer is not None:
			answer[1]()

	def RedPressed(self):
		if isStandardInfoBar(self) or isMoviePlayerInfoBar(self):
			if config.usage.defaultEPGType.value != _("Graphical EPG") and config.usage.defaultEPGType.value != _("None"):
					self.openGraphEPG()
			else:
				self.openSingleServiceEPG()

	def InfoPressed(self):
		if isStandardInfoBar(self) or isMoviePlayerInfoBar(self):
			if SystemInfo['HasInfoButton']:
				self.openEventView()
			else:
				self.showDefaultEPG()

	def IPressed(self):
		if isStandardInfoBar(self) or isMoviePlayerInfoBar(self):
			self.openEventView()

	def EPGPressed(self):
		if isStandardInfoBar(self) or isMoviePlayerInfoBar(self):
			self.openGraphEPG()

	def showEventInfoWhenNotVisible(self):
		if self.shown:
			self.openEventView()
		else:
			self.toggleShow()
			return 1

	def zapToService(self, service, bouquet = None, preview = False, zapback = False):
		if self.servicelist.startServiceRef is None:
			self.servicelist.startServiceRef = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.servicelist.currentServiceRef = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if service is not None:
			if self.servicelist.getRoot() != bouquet: #already in correct bouquet?
				self.servicelist.clearPath()
				if self.servicelist.bouquet_root != bouquet:
					self.servicelist.enterPath(self.servicelist.bouquet_root)
				self.servicelist.enterPath(bouquet)
			self.servicelist.setCurrentSelection(service) #select the service in servicelist
		if not zapback or preview:
			self.servicelist.zap(preview_zap = preview)
		if (self.servicelist.dopipzap or zapback) and not preview:
			self.servicelist.zapBack()
		if not preview:
			self.servicelist.startServiceRef = None
			self.servicelist.startRoot = None

	def getBouquetServices(self, bouquet):
		services = []
		servicelist = eServiceCenter.getInstance().list(bouquet)
		if not servicelist is None:
			while True:
				service = servicelist.getNext()
				if not service.valid(): #check if end of list
					break
				if service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker): #ignore non playable services
					continue
				services.append(ServiceReference(service))
		return services

	def openBouquetEPG(self, bouquet = None, bouquets = None):
		if bouquet:
			self.StartBouquet = bouquet
		self.dlg_stack.append(self.session.openWithCallback(self.closed, EPGSelection, zapFunc=self.zapToService, EPGtype=self.EPGtype, StartBouquet=self.StartBouquet, StartRef=self.StartRef, bouquets = bouquets))

	def closed(self, ret=False):
		if not self.dlg_stack:
			return
		closedScreen = self.dlg_stack.pop()
		if self.bouquetSel and closedScreen == self.bouquetSel:
			self.bouquetSel = None
		elif self.eventView and closedScreen == self.eventView:
			self.eventView = None
		if ret == True or ret == 'close':
			dlgs=len(self.dlg_stack)
			if dlgs > 0:
				self.dlg_stack[dlgs-1].close(dlgs > 1)
		self.reopen(ret)

	def MultiServiceEPG(self):
		bouquets = self.servicelist.getBouquetList()
		if bouquets is None:
			cnt = 0
		else:
			cnt = len(bouquets)
		if (self.EPGtype == "multi" and config.epgselection.multi_showbouquet.value) or (self.EPGtype == "graph" and config.epgselection.graph_showbouquet.value):
			if cnt > 1: # show bouquet list
				self.bouquetSel = self.session.openWithCallback(self.closed, EpgBouquetSelector, bouquets, self.openBouquetEPG, enableWrapAround=True)
				self.dlg_stack.append(self.bouquetSel)
			elif cnt == 1:
				self.openBouquetEPG(bouquets=bouquets)
		else:
			self.openBouquetEPG(bouquets=bouquets)

	def openMultiServiceEPG(self):
		if self.servicelist is None:
			return
		self.EPGtype = "multi"
		self.StartBouquet = self.servicelist.getRoot()
		if isMoviePlayerInfoBar(self):
			self.StartRef = self.lastservice
		else:
			self.StartRef = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.MultiServiceEPG()

	def openGraphEPG(self, reopen=False):
		if self.servicelist is None:
			return
		self.EPGtype = "graph"
		if not reopen:
			self.StartBouquet = self.servicelist.getRoot()
			self.StartRef = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.MultiServiceEPG()

	def openSingleServiceEPG(self, reopen=False):
		if self.servicelist is None:
			return
		self.EPGtype = "enhanced"
		self.SingleServiceEPG()

	def openInfoBarEPG(self, reopen=False):
		if self.servicelist is None:
			return
		if not reopen:
			self.StartBouquet = self.servicelist.getRoot()
			self.StartRef = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if config.epgselection.infobar_type_mode.value == 'single':
			self.EPGtype = "infobar"
			self.SingleServiceEPG()
		else:
			self.EPGtype = "infobargraph"
			self.MultiServiceEPG()

	def showCoolTVGuide(self):
		if self.servicelist is None:
			return
		if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/CoolTVGuide/plugin.pyo"):
			for plugin in plugins.getPlugins([PluginDescriptor.WHERE_EXTENSIONSMENU, PluginDescriptor.WHERE_EVENTINFO]):
				if plugin.name == _("Cool TV Guide"):
					self.runPlugin(plugin)
					break
		else:
			self.session.open(MessageBox, _("The Cool TV Guide plugin is not installed!\nDont bother with it and use the default ViX EPG guide instead."), type = MessageBox.TYPE_INFO,timeout = 10 )

	def SingleServiceEPG(self):
		self.StartBouquet = self.servicelist.getRoot()
		self.StartRef = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if isMoviePlayerInfoBar(self):
			ref = self.lastservice
		else:
			ref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if ref:
			services = self.getBouquetServices(self.StartBouquet)
			self.serviceSel = SimpleServicelist(services)
			if self.serviceSel.selectService(ref):
				self.session.openWithCallback(self.SingleServiceEPGClosed,EPGSelection, self.servicelist, zapFunc=self.zapToService, serviceChangeCB = self.changeServiceCB, EPGtype=self.EPGtype, StartBouquet=self.StartBouquet, StartRef=self.StartRef)
			else:
				self.session.openWithCallback(self.SingleServiceEPGClosed, EPGSelection, ref)

	def changeServiceCB(self, direction, epg):
		if self.serviceSel:
			if direction > 0:
				self.serviceSel.nextService()
			else:
				self.serviceSel.prevService()
			epg.setService(self.serviceSel.currentService())

	def SingleServiceEPGClosed(self, ret=False):
		self.serviceSel = None
		self.reopen(ret)

	def reopen(self, answer):
		if answer == 'reopengraph':
			self.openGraphEPG(True)
		elif answer == 'reopeninfobargraph' or answer == 'reopeninfobar':
			self.openInfoBarEPG(True)
		elif answer == 'close' and isMoviePlayerInfoBar(self):
			self.lastservice = self.session.nav.getCurrentlyPlayingServiceOrGroup()
			self.close()

	def openSimilarList(self, eventid, refstr):
		self.session.open(EPGSelection, refstr, eventid=eventid)

	def getNowNext(self):
		epglist = [ ]
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		ptr = info and info.getEvent(0)
		if ptr:
			epglist.append(ptr)
		ptr = info and info.getEvent(1)
		if ptr:
			epglist.append(ptr)
		self.epglist = epglist

	def __evEventInfoChanged(self):
		if self.is_now_next and len(self.dlg_stack) == 1:
			self.getNowNext()
			if self.eventView and self.epglist:
				self.eventView.setEvent(self.epglist[0])

	def showDefaultEPG(self):
		if self.defaultEPGType is not None:
			self.defaultEPGType()
			return
		self.EPGPressed()

	def openEventView(self, simple=False):
		if self.servicelist is None:
			return
		ref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.getNowNext()
		epglist = self.epglist
		if not epglist:
			self.is_now_next = False
			epg = eEPGCache.getInstance()
			ptr = ref and ref.valid() and epg.lookupEventTime(ref, -1)
			if ptr:
				epglist.append(ptr)
				ptr = epg.lookupEventTime(ref, ptr.getBeginTime(), +1)
				if ptr:
					epglist.append(ptr)
		else:
			self.is_now_next = True
		if epglist:
			if not simple:
				self.eventView = self.session.openWithCallback(self.closed, EventViewEPGSelect, epglist[0], ServiceReference(ref), self.eventViewCallback, self.openSingleServiceEPG, self.openMultiServiceEPG, self.openSimilarList)
			else:
				self.eventView = self.session.openWithCallback(self.closed, EventViewSimple, epglist[0], ServiceReference(ref))
			self.dlg_stack.append(self.eventView)

	def eventViewCallback(self, setEvent, setService, val): #used for now/next displaying
		epglist = self.epglist
		if len(epglist) > 1:
			tmp = epglist[0]
			epglist[0]=epglist[1]
			epglist[1]=tmp
			setEvent(epglist[0])

class InfoBarRdsDecoder:
	"""provides RDS and Rass support/display"""
	def __init__(self):
		self.rds_display = self.session.instantiateDialog(RdsInfoDisplay)
		self.session.instantiateSummaryDialog(self.rds_display)
		self.rds_display.setAnimationMode(0)
		self.rass_interactive = None

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evEnd: self.__serviceStopped,
				iPlayableService.evUpdatedRassSlidePic: self.RassSlidePicChanged
			})

		self["RdsActions"] = ActionMap(["InfobarRdsActions"],
		{
			"startRassInteractive": self.startRassInteractive
		},-1)

		self["RdsActions"].setEnabled(False)

		self.onLayoutFinish.append(self.rds_display.show)
		self.rds_display.onRassInteractivePossibilityChanged.append(self.RassInteractivePossibilityChanged)

	def RassInteractivePossibilityChanged(self, state):
		self["RdsActions"].setEnabled(state)

	def RassSlidePicChanged(self):
		if not self.rass_interactive:
			service = self.session.nav.getCurrentService()
			decoder = service and service.rdsDecoder()
			if decoder:
				decoder.showRassSlidePicture()

	def __serviceStopped(self):
		if self.rass_interactive is not None:
			rass_interactive = self.rass_interactive
			self.rass_interactive = None
			rass_interactive.close()

	def startRassInteractive(self):
		self.rds_display.hide()
		self.rass_interactive = self.session.openWithCallback(self.RassInteractiveClosed, RassInteractive)

	def RassInteractiveClosed(self, *val):
		if self.rass_interactive is not None:
			self.rass_interactive = None
			self.RassSlidePicChanged()
		self.rds_display.show()

class Seekbar(Screen):
	def __init__(self, session, fwd):
		Screen.__init__(self, session)
		self.setTitle(_("Seek"))
		self.session = session
		self.fwd = fwd
		self.percent = 0.0
		self.length = None
		service = session.nav.getCurrentService()
		if service:
			self.seek = service.seek()
			if self.seek:
				self.length = self.seek.getLength()
				position = self.seek.getPlayPosition()
				if self.length and position and int(self.length[1]) > 0:
					if int(position[1]) > 0:
						self.percent = float(position[1]) * 100.0 / float(self.length[1])
				else:
					self.close()

		self["cursor"] = MovingPixmap()
		self["PositionGauge"] = Label()
		self["time"] = Label()

		self["actions"] = ActionMap(["WizardActions", "DirectionActions"], {"back": self.exit, "ok": self.keyOK, "left": self.keyLeft, "right": self.keyRight}, -1)

		self.cursorTimer = eTimer()
		self.cursorTimer.callback.append(self.updateCursor)
		self.cursorTimer.start(200, False)

		self.onLayoutFinish.append(self.__layoutFinished)

	def __layoutFinished(self):
		self.cursor_y = self["cursor"].instance.position().y()
		if hasattr(self["PositionGauge"].instance, "position") and self["PositionGauge"].instance.position().x() > 0:
			self.PositionGauge_x = self["PositionGauge"].instance.position().x()
		else:
			self.PositionGauge_x = 145
		if hasattr(self["PositionGauge"].instance, "size") and self["PositionGauge"].instance.size().width() > 0:
			self.PositionGauge_w = self["PositionGauge"].instance.size().width()
			self.PositionGauge_w = float(self.PositionGauge_w) / 100.0 - 0.2
		else:
			self.PositionGauge_w = 2.7

	def updateCursor(self):
		if self.length:
			x = self.PositionGauge_x + int(self.PositionGauge_w * self.percent)
			self["cursor"].moveTo(x, self.cursor_y, 1)
			self["cursor"].startMoving()
			pts = int(float(self.length[1]) / 100.0 * self.percent)
			self["time"].setText("%d:%02d" % ((pts/60/90000), ((pts/90000)%60)))

	def exit(self):
		self.cursorTimer.stop()
		self.close()

	def keyOK(self):
		if self.length:
			self.seek.seekTo(int(float(self.length[1]) / 100.0 * self.percent))
			self.exit()

	def keyLeft(self):
		self.percent -= float(config.seek.sensibility.value) / 10.0
		if self.percent < 0.0:
			self.percent = 0.0

	def keyRight(self):
		self.percent += float(config.seek.sensibility.value) / 10.0
		if self.percent > 100.0:
			self.percent = 100.0

	def keyNumberGlobal(self, number):
		sel = self["config"].getCurrent()[1]
		if sel == self.positionEntry:
			self.percent = float(number) * 10.0
		else:
			ConfigListScreen.keyNumberGlobal(self, number)

class InfoBarSeek:
	"""handles actions like seeking, pause"""

	SEEK_STATE_PLAY = (0, 0, 0, ">")
	SEEK_STATE_PAUSE = (1, 0, 0, "||")
	SEEK_STATE_EOF = (1, 0, 0, "END")

	def __init__(self, actionmap = "InfobarSeekActions"):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evEOF: self.__evEOF,
				iPlayableService.evSOF: self.__evSOF,
			})
		self.fast_winding_hint_message_showed = False

		class InfoBarSeekActionMap(HelpableActionMap):
			def __init__(self, screen, *args, **kwargs):
				HelpableActionMap.__init__(self, screen, *args, **kwargs)
				self.screen = screen

			def action(self, contexts, action):
				# print "action:", action
				if action[:5] == "seek:":
					time = int(action[5:])
					self.screen.doSeekRelative(time * 90000)
					return 1
				elif action[:8] == "seekdef:":
					key = int(action[8:])
					time = (-config.seek.selfdefined_13.value, False, config.seek.selfdefined_13.value,
						-config.seek.selfdefined_46.value, False, config.seek.selfdefined_46.value,
						-config.seek.selfdefined_79.value, False, config.seek.selfdefined_79.value)[key-1]
					self.screen.doSeekRelative(time * 90000)
					return 1
				else:
					return HelpableActionMap.action(self, contexts, action)

		self["SeekActions"] = InfoBarSeekActionMap(self, actionmap,
			{
				"playpauseService": (self.playpauseService, _("Pause/Continue playback")),
				"pauseService": (self.pauseService, _("Pause playback")),
				"unPauseService": (self.unPauseService, _("Continue playback")),
				"okButton": (self.okButton, _("Continue playback")),
				"seekFwd": (self.seekFwd, _("Seek forward")),
				"seekFwdManual": (self.seekFwdManual, _("Seek forward (enter time)")),
				"seekBack": (self.seekBack, _("Seek backward")),
				"seekBackManual": (self.seekBackManual, _("Seek backward (enter time)")),

				"SeekbarFwd": self.seekFwdSeekbar,
				"SeekbarBack": self.seekBackSeekbar
			}, prio=-1) # give them a little more priority to win over color buttons
		self["SeekActions"].setEnabled(False)

		self["SeekActionsPTS"] = InfoBarSeekActionMap(self, "InfobarSeekActionsPTS",
			{
				"playpauseService": self.playpauseService,
				"pauseService": (self.pauseService, _("Pause playback")),
				"unPauseService": (self.unPauseService, _("Continue playback")),

				"seekFwd": (self.seekFwd, _("skip forward")),
				"seekFwdManual": (self.seekFwdManual, _("skip forward (enter time)")),
				"seekBack": (self.seekBack, _("skip backward")),
				"seekBackManual": (self.seekBackManual, _("skip backward (enter time)")),
			}, prio=-1) # give them a little more priority to win over color buttons
		self["SeekActionsPTS"].setEnabled(False)

		self.activity = 0
		self.activityTimer = eTimer()
		self.activityTimer.callback.append(self.doActivityTimer)
		self.seekstate = self.SEEK_STATE_PLAY
		self.lastseekstate = self.SEEK_STATE_PLAY

		self.onPlayStateChanged = [ ]

		self.lockedBecauseOfSkipping = False

		self.__seekableStatusChanged()

	def makeStateForward(self, n):
		return 0, n, 0, ">> %dx" % n

	def makeStateBackward(self, n):
		return 0, -n, 0, "<< %dx" % n

	def makeStateSlowMotion(self, n):
		return 0, 0, n, "/%d" % n

	def isStateForward(self, state):
		return state[1] > 1

	def isStateBackward(self, state):
		return state[1] < 0

	def isStateSlowMotion(self, state):
		return state[1] == 0 and state[2] > 1

	def getHigher(self, n, lst):
		for x in lst:
			if x > n:
				return x
		return False

	def getLower(self, n, lst):
		lst = lst[:]
		lst.reverse()
		for x in lst:
			if x < n:
				return x
		return False

	def showAfterSeek(self):
		if isinstance(self, InfoBarShowHide):
			self.doShow()

	def up(self):
		pass

	def down(self):
		pass

	def getSeek(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None

		seek = service.seek()

		if seek is None or not seek.isCurrentlySeekable():
			return None

		return seek

	def isSeekable(self):
		if self.getSeek() is None or (isStandardInfoBar(self) and not self.timeshiftEnabled()):
			return False
		return True

	def __seekableStatusChanged(self):
		if isStandardInfoBar(self) and self.timeshiftEnabled():
			pass
		elif not self.isSeekable():
#			print "not seekable, return to play"
			self["SeekActions"].setEnabled(False)
			self.setSeekState(self.SEEK_STATE_PLAY)
		else:
#			print "seekable"
			self["SeekActions"].setEnabled(True)
			self.activityTimer.start(200, False)
			for c in self.onPlayStateChanged:
				c(self.seekstate)

	def doActivityTimer(self):
		if self.isSeekable():
			self.activity += 16
			hdd = 1
			if self.activity >= 100:
				self.activity = 0
		else:
			self.activityTimer.stop()
			self.activity = 0
			hdd = 0
		if os.path.exists("/proc/stb/lcd/symbol_hdd"):
			file = open("/proc/stb/lcd/symbol_hdd", "w")
			file.write('%d' % int(hdd))
			file.close()
		if os.path.exists("/proc/stb/lcd/symbol_hddprogress"):
			file = open("/proc/stb/lcd/symbol_hddprogress", "w")
			file.write('%d' % int(self.activity))
			file.close()

	def __serviceStarted(self):
		self.fast_winding_hint_message_showed = False
		self.setSeekState(self.SEEK_STATE_PLAY)
		self.__seekableStatusChanged()

	def setSeekState(self, state):
		service = self.session.nav.getCurrentService()

		if service is None:
			return False

		if not self.isSeekable():
			if state not in (self.SEEK_STATE_PLAY, self.SEEK_STATE_PAUSE):
				state = self.SEEK_STATE_PLAY

		pauseable = service.pause()

		if pauseable is None:
#			print "[InfoBarGenerics] not pauseable."
			state = self.SEEK_STATE_PLAY

		self.seekstate = state

		if pauseable is not None:
			if self.seekstate[0] and self.seekstate[3] == '||':
#				print "[InfoBarGenerics] resolved to PAUSE"
				self.activityTimer.stop()
				pauseable.pause()
			elif self.seekstate[0] and self.seekstate[3] == 'END':
#				print "[InfoBarGenerics] resolved to STOP"
				self.activityTimer.stop()
			elif self.seekstate[1]:
				if not pauseable.setFastForward(self.seekstate[1]):
					pass
					# print "[InfoBarGenerics] resolved to FAST FORWARD"
				else:
					self.seekstate = self.SEEK_STATE_PLAY
					# print "[InfoBarGenerics] FAST FORWARD not possible: resolved to PLAY"
			elif self.seekstate[2]:
				if not pauseable.setSlowMotion(self.seekstate[2]):
					pass
					# print "[InfoBarGenerics] resolved to SLOW MOTION"
				else:
					self.seekstate = self.SEEK_STATE_PAUSE
					# print "[InfoBarGenerics] SLOW MOTION not possible: resolved to PAUSE"
			else:
#				print "[InfoBarGenerics] resolved to PLAY"
				self.activityTimer.start(200, False)
				pauseable.unpause()

		for c in self.onPlayStateChanged:
			c(self.seekstate)

		self.checkSkipShowHideLock()

		if hasattr(self, "ScreenSaverTimerStart"):
			self.ScreenSaverTimerStart()

		return True

	def okButton(self):
		if self.seekstate == self.SEEK_STATE_PLAY:
			return 0
		elif self.seekstate == self.SEEK_STATE_PAUSE:
			self.pauseService()
		else:
			self.unPauseService()

	def playpauseService(self):
		if self.seekstate == self.SEEK_STATE_PLAY:
			self.pauseService()
		else:
			if self.seekstate == self.SEEK_STATE_PAUSE:
				if config.seek.on_pause.value == "play":
					self.unPauseService()
				elif config.seek.on_pause.value == "step":
					self.doSeekRelative(1)
				elif config.seek.on_pause.value == "last":
					self.setSeekState(self.lastseekstate)
					self.lastseekstate = self.SEEK_STATE_PLAY
			else:
				self.unPauseService()

	def pauseService(self):
		if self.seekstate != self.SEEK_STATE_EOF:
			self.lastseekstate = self.seekstate
		self.setSeekState(self.SEEK_STATE_PAUSE)

	def unPauseService(self):
		if self.seekstate == self.SEEK_STATE_PLAY:
			return 0
		self.setSeekState(self.SEEK_STATE_PLAY)

	def doSeek(self, pts):
		seekable = self.getSeek()
		if seekable is None:
			return
		seekable.seekTo(pts)

	def doSeekRelative(self, pts):
		seekable = self.getSeek()
		if seekable is None:
			return
		prevstate = self.seekstate

		if self.seekstate == self.SEEK_STATE_EOF:
			if prevstate == self.SEEK_STATE_PAUSE:
				self.setSeekState(self.SEEK_STATE_PAUSE)
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		seekable.seekRelative(pts<0 and -1 or 1, abs(pts))
		if abs(pts) > 100 and config.usage.show_infobar_on_skip.value:
			self.showAfterSeek()

	def seekFwd(self):
		seek = self.getSeek()
		if seek and not (seek.isCurrentlySeekable() & 2):
			if not self.fast_winding_hint_message_showed and (seek.isCurrentlySeekable() & 1):
				self.session.open(MessageBox, _("No fast winding possible yet.. but you can use the number buttons to skip forward/backward!"), MessageBox.TYPE_INFO, timeout=10)
				self.fast_winding_hint_message_showed = True
				return
			return 0 # trade as unhandled action
		if self.seekstate == self.SEEK_STATE_PLAY:
			self.setSeekState(self.makeStateForward(int(config.seek.enter_forward.value)))
		elif self.seekstate == self.SEEK_STATE_PAUSE:
			if len(config.seek.speeds_slowmotion.value):
				self.setSeekState(self.makeStateSlowMotion(config.seek.speeds_slowmotion.value[-1]))
			else:
				self.setSeekState(self.makeStateForward(int(config.seek.enter_forward.value)))
		elif self.seekstate == self.SEEK_STATE_EOF:
			pass
		elif self.isStateForward(self.seekstate):
			speed = self.seekstate[1]
			if self.seekstate[2]:
				speed /= self.seekstate[2]
			speed = self.getHigher(speed, config.seek.speeds_forward.value) or config.seek.speeds_forward.value[-1]
			self.setSeekState(self.makeStateForward(speed))
		elif self.isStateBackward(self.seekstate):
			speed = -self.seekstate[1]
			if self.seekstate[2]:
				speed /= self.seekstate[2]
			speed = self.getLower(speed, config.seek.speeds_backward.value)
			if speed:
				self.setSeekState(self.makeStateBackward(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		elif self.isStateSlowMotion(self.seekstate):
			speed = self.getLower(self.seekstate[2], config.seek.speeds_slowmotion.value) or config.seek.speeds_slowmotion.value[0]
			self.setSeekState(self.makeStateSlowMotion(speed))

	def seekBack(self):
		seek = self.getSeek()
		if seek and not (seek.isCurrentlySeekable() & 2):
			if not self.fast_winding_hint_message_showed and (seek.isCurrentlySeekable() & 1):
				self.session.open(MessageBox, _("No fast winding possible yet.. but you can use the number buttons to skip forward/backward!"), MessageBox.TYPE_INFO, timeout=10)
				self.fast_winding_hint_message_showed = True
				return
			return 0 # trade as unhandled action
		seekstate = self.seekstate
		if seekstate == self.SEEK_STATE_PLAY:
			self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))
		elif seekstate == self.SEEK_STATE_EOF:
			self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))
			self.doSeekRelative(-6)
		elif seekstate == self.SEEK_STATE_PAUSE:
			self.doSeekRelative(-1)
		elif self.isStateForward(seekstate):
			speed = seekstate[1]
			if seekstate[2]:
				speed /= seekstate[2]
			speed = self.getLower(speed, config.seek.speeds_forward.value)
			if speed:
				self.setSeekState(self.makeStateForward(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		elif self.isStateBackward(seekstate):
			speed = -seekstate[1]
			if seekstate[2]:
				speed /= seekstate[2]
			speed = self.getHigher(speed, config.seek.speeds_backward.value) or config.seek.speeds_backward.value[-1]
			self.setSeekState(self.makeStateBackward(speed))
		elif self.isStateSlowMotion(seekstate):
			speed = self.getHigher(seekstate[2], config.seek.speeds_slowmotion.value)
			if speed:
				self.setSeekState(self.makeStateSlowMotion(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PAUSE)
		self.pts_lastseekspeed = self.seekstate[1]

	def seekFwdManual(self, fwd=True):
		if config.seek.baractivation.value == "leftright":
			self.session.open(Seekbar, fwd)
		else:
			self.session.openWithCallback(self.fwdSeekTo, MinuteInput)

	def seekBackManual(self, fwd=False):
		if config.seek.baractivation.value == "leftright":
			self.session.open(Seekbar, fwd)
		else:
			self.session.openWithCallback(self.rwdSeekTo, MinuteInput)

	def seekFwdSeekbar(self, fwd=True):
		if not config.seek.baractivation.value == "leftright":
			self.session.open(Seekbar, fwd)
		else:
			self.session.openWithCallback(self.rwdSeekTo, MinuteInput)

	def seekFwdVod(self, fwd=True):
		seekable = self.getSeek()
		if seekable is None:
			return
		else:
			if config.seek.baractivation.value == "leftright":
				self.session.open(Seekbar, fwd)
			else:
				self.session.openWithCallback(self.fwdSeekTo, MinuteInput)

	def seekFwdSeekbar(self, fwd=True):
		if not config.seek.baractivation.value == "leftright":
			self.session.open(Seekbar, fwd)
		else:
			self.session.openWithCallback(self.fwdSeekTo, MinuteInput)

	def fwdSeekTo(self, minutes):
		self.doSeekRelative(minutes * 60 * 90000)

	def seekBackSeekbar(self, fwd=False):
		if not config.seek.baractivation.value == "leftright":
			self.session.open(Seekbar, fwd)
		else:
			self.session.openWithCallback(self.rwdSeekTo, MinuteInput)

	def rwdSeekTo(self, minutes):
#		print "rwdSeekTo"
			self.doSeekRelative(-minutes * 60 * 90000)

	def checkSkipShowHideLock(self):
		if self.seekstate == self.SEEK_STATE_PLAY or self.seekstate == self.SEEK_STATE_EOF:
			self.lockedBecauseOfSkipping = False
			self.unlockShow()
		else:
			wantlock = self.seekstate != self.SEEK_STATE_PLAY
			if config.usage.show_infobar_on_skip.value:
				if self.lockedBecauseOfSkipping and not wantlock:
					self.unlockShow()
					self.lockedBecauseOfSkipping = False

				if wantlock and not self.lockedBecauseOfSkipping:
					self.lockShow()
					self.lockedBecauseOfSkipping = True

	def calcRemainingTime(self):
		seekable = self.getSeek()
		if seekable is not None:
			len = seekable.getLength()
			try:
				tmp = self.cueGetEndCutPosition()
				if tmp:
					len = (False, tmp)
			except:
				pass
			pos = seekable.getPlayPosition()
			speednom = self.seekstate[1] or 1
			speedden = self.seekstate[2] or 1
			if not len[0] and not pos[0]:
				if len[1] <= pos[1]:
					return 0
				time = (len[1] - pos[1])*speedden/(90*speednom)
				return time
		return False

	def __evEOF(self):
		if self.seekstate == self.SEEK_STATE_EOF:
			return

		# if we are seeking forward, we try to end up ~1s before the end, and pause there.
		seekstate = self.seekstate
		if self.seekstate != self.SEEK_STATE_PAUSE:
			self.setSeekState(self.SEEK_STATE_EOF)

		if seekstate not in (self.SEEK_STATE_PLAY, self.SEEK_STATE_PAUSE): # if we are seeking
			seekable = self.getSeek()
			if seekable is not None:
				seekable.seekTo(-1)
				self.doEofInternal(True)
		if seekstate == self.SEEK_STATE_PLAY: # regular EOF
			self.doEofInternal(True)
		else:
			self.doEofInternal(False)

	def doEofInternal(self, playing):
		pass		# Defined in subclasses

	def __evSOF(self):
		self.setSeekState(self.SEEK_STATE_PLAY)
		self.doSeek(0)

class InfoBarPVRState:
	def __init__(self, screen=PVRState, force_show = False):
		self.onChangedEntry = [ ]
		self.onPlayStateChanged.append(self.__playStateChanged)
		self.pvrStateDialog = self.session.instantiateDialog(screen)
		self.pvrStateDialog.setAnimationMode(0)
		self.onShow.append(self._mayShow)
		self.onHide.append(self.pvrStateDialog.hide)
		self.force_show = force_show

	def createSummary(self):
		return InfoBarMoviePlayerSummary

	def _mayShow(self):
		if self.has_key("state") and not config.usage.movieplayer_pvrstate.value:
			self["state"].setText("")
			self["statusicon"].setPixmapNum(6)
			self["speed"].setText("")
		if self.shown and self.seekstate != self.SEEK_STATE_EOF and not config.usage.movieplayer_pvrstate.value:
			self.pvrStateDialog.show()
			self.startHideTimer()

	def __playStateChanged(self, state):
		playstateString = state[3]
		state_summary = playstateString
		self.pvrStateDialog["state"].setText(playstateString)
		if playstateString == '>':
			self.pvrStateDialog["statusicon"].setPixmapNum(0)
			self.pvrStateDialog["speed"].setText("")
			speed_summary = self.pvrStateDialog["speed"].text
			statusicon_summary = 0
			if self.has_key("state") and config.usage.movieplayer_pvrstate.value:
				self["state"].setText(playstateString)
				self["statusicon"].setPixmapNum(0)
				self["speed"].setText("")
		elif playstateString == '||':
			self.pvrStateDialog["statusicon"].setPixmapNum(1)
			self.pvrStateDialog["speed"].setText("")
			speed_summary = self.pvrStateDialog["speed"].text
			statusicon_summary = 1
			if self.has_key("state") and config.usage.movieplayer_pvrstate.value:
				self["state"].setText(playstateString)
				self["statusicon"].setPixmapNum(1)
				self["speed"].setText("")
		elif playstateString == 'END':
			self.pvrStateDialog["statusicon"].setPixmapNum(2)
			self.pvrStateDialog["speed"].setText("")
			speed_summary = self.pvrStateDialog["speed"].text
			statusicon_summary = 2
			if self.has_key("state") and config.usage.movieplayer_pvrstate.value:
				self["state"].setText(playstateString)
				self["statusicon"].setPixmapNum(2)
				self["speed"].setText("")
		elif playstateString.startswith('>>'):
			speed = state[3].split()
			self.pvrStateDialog["statusicon"].setPixmapNum(3)
			self.pvrStateDialog["speed"].setText(speed[1])
			speed_summary = self.pvrStateDialog["speed"].text
			statusicon_summary = 3
			if self.has_key("state") and config.usage.movieplayer_pvrstate.value:
				self["state"].setText(playstateString)
				self["statusicon"].setPixmapNum(3)
				self["speed"].setText(speed[1])
		elif playstateString.startswith('<<'):
			speed = state[3].split()
			self.pvrStateDialog["statusicon"].setPixmapNum(4)
			self.pvrStateDialog["speed"].setText(speed[1])
			speed_summary = self.pvrStateDialog["speed"].text
			statusicon_summary = 4
			if self.has_key("state") and config.usage.movieplayer_pvrstate.value:
				self["state"].setText(playstateString)
				self["statusicon"].setPixmapNum(4)
				self["speed"].setText(speed[1])
		elif playstateString.startswith('/'):
			self.pvrStateDialog["statusicon"].setPixmapNum(5)
			self.pvrStateDialog["speed"].setText(playstateString)
			speed_summary = self.pvrStateDialog["speed"].text
			statusicon_summary = 5
			if self.has_key("state") and config.usage.movieplayer_pvrstate.value:
				self["state"].setText(playstateString)
				self["statusicon"].setPixmapNum(5)
				self["speed"].setText(playstateString)

		for cb in self.onChangedEntry:
			cb(state_summary, speed_summary, statusicon_summary)

		# if we return into "PLAY" state, ensure that the dialog gets hidden if there will be no infobar displayed
		if not config.usage.show_infobar_on_skip.value and self.seekstate == self.SEEK_STATE_PLAY and not self.force_show:
			self.pvrStateDialog.hide()
		else:
			self._mayShow()

class InfoBarTimeshiftState(InfoBarPVRState):
	def __init__(self):
		InfoBarPVRState.__init__(self, screen=TimeshiftState, force_show = True)
		self.onPlayStateChanged.append(self.__timeshiftEventName)
		self.onHide.append(self.__hideTimeshiftState)

	def _mayShow(self):
		if self.shown and self.timeshiftEnabled() and self.isSeekable():
			# noinspection PyCallByClass
			InfoBarTimeshift.ptsSeekPointerSetCurrentPos(self)
			if config.timeshift.showinfobar.value:
				self["TimeshiftSeekPointerActions"].setEnabled(True)
			self.pvrStateDialog.show()
			self.startHideTimer()

	def __hideTimeshiftState(self):
		self["TimeshiftSeekPointerActions"].setEnabled(False)
		self.pvrStateDialog.hide()

	def __timeshiftEventName(self,state):
		if os.path.exists("%spts_livebuffer_%s.meta" % (config.usage.timeshift_path.value,self.pts_currplaying)):
			readmetafile = open("%spts_livebuffer_%s.meta" % (config.usage.timeshift_path.value,self.pts_currplaying), "r")
			servicerefname = readmetafile.readline()[0:-1]
			eventname = readmetafile.readline()[0:-1]
			readmetafile.close()
			self.pvrStateDialog["eventname"].setText(eventname)
		else:
			self.pvrStateDialog["eventname"].setText("")

class InfoBarShowMovies:
	# i don't really like this class.
	# it calls a not further specified "movie list" on up/down/movieList,
	# so this is not more than an action map
	def __init__(self):
		self["MovieListActions"] = HelpableActionMap(self, "InfobarMovieListActions",
			{
				"movieList": (self.showMovies, _("Open the movie list")),
				"up": (self.up, _("Open the movie list")),
				"down": (self.down, _("Open the movie list"))
			})

from Screens.PiPSetup import PiPSetup
class InfoBarExtensions:
	EXTENSION_SINGLE = 0
	EXTENSION_LIST = 1

	def __init__(self):
		self.list = []

		if config.vixsettings.ColouredButtons.value:
			self["InstantExtensionsActions"] = HelpableActionMap(self, "InfobarExtensions",
				{
					"extensions": (self.showExtensionSelection, _("Show extensions...")),
					"showPluginBrowser": (self.showPluginBrowser, _("Show the plugin browser..")),
					"openTimerList": (self.showTimerList, _("Show the list of timers.")),
					"openAutoTimerList": (self.showAutoTimerList, _("Show the list of autotimers.")),
					"openEPGSearch": (self.showEPGSearch, _("Search the epg for the current event.")),
					"openIMDB": (self.showIMDB, _("Search IMDb for information about the current event.")),
					"openDreamPlex": (self.showDreamPlex, _("Show the DreamPlex player...")),
				}, 1) # lower priority
		else:
			self["InstantExtensionsActions"] = HelpableActionMap(self, "InfobarExtensions",
				{
					"extensions": (self.showExtensionSelection, _("View extensions...")),
					"showPluginBrowser": (self.showPluginBrowser, _("Show the plugin browser..")),
					"showDreamPlex": (self.showDreamPlex, _("Show the DreamPlex player...")),
				}, 1) # lower priority

		for p in plugins.getPlugins(PluginDescriptor.WHERE_EXTENSIONSINGLE):
			p(self)

		self.addExtension(extension = self.getLogManager, type = InfoBarExtensions.EXTENSION_LIST)
		self.addExtension(extension = self.getOsd3DSetup, type = InfoBarExtensions.EXTENSION_LIST)
		self.addExtension(extension = self.getCCcamInfo, type = InfoBarExtensions.EXTENSION_LIST)
		self.addExtension(extension = self.getOScamInfo, type = InfoBarExtensions.EXTENSION_LIST)

	def getLMname(self):
		return _("Log Manager")

	def getLogManager(self):
		if config.logmanager.showinextensions.value:
			return [((boundFunction(self.getLMname), boundFunction(self.openLogManager), lambda: True), None)]
		else:
			return []

	def get3DSetupname(self):
		return _("OSD 3D Setup")

	def getOsd3DSetup(self):
		if config.osd.show3dextensions .value:
			return [((boundFunction(self.get3DSetupname), boundFunction(self.open3DSetup), lambda: True), None)]
		else:
			return []

	def getCCname(self):
		return _("CCcam Info")

	def getCCcamInfo(self):
		if pathExists('/usr/softcams/'):
			softcams = os.listdir('/usr/softcams/')
		for softcam in softcams:
			if softcam.lower().startswith('cccam') and config.cccaminfo.showInExtensions.value:
				return [((boundFunction(self.getCCname), boundFunction(self.openCCcamInfo), lambda: True), None)] or []
		else:
			return []

	def getOSname(self):
		return _("OScam Info")

	def getOScamInfo(self):
		if pathExists('/usr/softcams/'):
			softcams = os.listdir('/usr/softcams/')
		for softcam in softcams:
			if softcam.lower().startswith('oscam') and config.oscaminfo.showInExtensions.value:
				return [((boundFunction(self.getOSname), boundFunction(self.openOScamInfo), lambda: True), None)] or []
		else:
			return []

	def addExtension(self, extension, key = None, type = EXTENSION_SINGLE):
		self.list.append((type, extension, key))

	def updateExtension(self, extension, key = None):
		self.extensionsList.append(extension)
		if key is not None and key in self.extensionKeys:
			key = None

		if key is None:
			for x in self.availableKeys:
				if x not in self.extensionKeys:
					key = x
					break

		if key is not None:
			self.extensionKeys[key] = len(self.extensionsList) - 1

	def updateExtensions(self):
		self.extensionsList = []
		self.availableKeys = [ "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "red", "green", "yellow", "blue" ]
		self.extensionKeys = {}
		for x in self.list:
			if x[0] == self.EXTENSION_SINGLE:
				self.updateExtension(x[1], x[2])
			else:
				for y in x[1]():
					self.updateExtension(y[0], y[1])

	def showExtensionSelection(self):
		self.updateExtensions()
		extensionsList = self.extensionsList[:]
		keys = []
		list = []
		for x in self.availableKeys:
			if x in self.extensionKeys:
				entry = self.extensionKeys[x]
				extension = self.extensionsList[entry]
				if extension[2]():
					name = str(extension[0]())
					list.append((extension[0](), extension))
					keys.append(x)
					extensionsList.remove(extension)
				else:
					extensionsList.remove(extension)
		list.extend([(x[0](), x) for x in extensionsList])

		keys += [""] * len(extensionsList)
		self.session.openWithCallback(self.extensionCallback, ChoiceBox, title=_("Please choose an extension..."), list=list, keys=keys, skin_name="ExtensionsList", reorderConfig="extension_order")

	def extensionCallback(self, answer):
		if answer is not None:
			answer[1][1]()

	def showPluginBrowser(self):
		from Screens.PluginBrowser import PluginBrowser
		self.session.open(PluginBrowser)

	def openCCcamInfo(self):
		from Screens.CCcamInfo import CCcamInfoMain
		self.session.open(CCcamInfoMain)

	def openOScamInfo(self):
		from Screens.OScamInfo import OscamInfoMenu
		self.session.open(OscamInfoMenu)

	def showTimerList(self):
		self.session.open(TimerEditList)

	def openLogManager(self):
		from Screens.LogManager import LogManager
		self.session.open(LogManager)

	def open3DSetup(self):
		from Screens.UserInterfacePositioner import OSD3DSetupScreen
		self.session.open(OSD3DSetupScreen)

	@staticmethod
	def _getAutoTimerPluginFunc():
		# Use the WHERE_MENU descriptor because it's the only
		# AutoTimer plugin descriptor that opens the AotoTimer
		# overview and is always present.

		for l in plugins.getPlugins(PluginDescriptor.WHERE_MENU):
			if l.name == _("Auto Timers"):  # Must use translated name
				menuEntry = l("timermenu")
				if menuEntry and len(menuEntry[0]) > 1 and callable(menuEntry[0][1]):
					return menuEntry[0][1]
		return None

	def showAutoTimerList(self):
		autotimerFunc = self._getAutoTimerPluginFunc()
		if autotimerFunc is not None:
			autotimerFunc(self.session)
		else:
			self.session.open(MessageBox, _("The AutoTimer plugin is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )

	def showEPGSearch(self):
		from Plugins.Extensions.EPGSearch.EPGSearch import EPGSearch
		s = self.session.nav.getCurrentService()
		if s:
			info = s.info()
			event = info.getEvent(0) # 0 = now, 1 = next
			if event:
				name = event and event.getEventName() or ''
			else:
				name = self.session.nav.getCurrentlyPlayingServiceOrGroup().toString()
				name = name.split('/')
				name = name[-1]
				name = name.replace('.',' ')
				name = name.split('-')
				name = name[0]
				if name.endswith(' '):
					name = name[:-1]
			if name:
				self.session.open(EPGSearch, name, False)
			else:
				self.session.open(EPGSearch)
		else:
			self.session.open(EPGSearch)

	def showIMDB(self):
		if os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/IMDb/plugin.pyo"):
			from Plugins.Extensions.IMDb.plugin import IMDB
			s = self.session.nav.getCurrentService()
			if s:
				info = s.info()
				event = info.getEvent(0) # 0 = now, 1 = next
				name = event and event.getEventName() or ''
				self.session.open(IMDB, name)
		else:
			self.session.open(MessageBox, _("The IMDb plugin is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )

	def showDreamPlex(self):
		if os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/DreamPlex/plugin.pyo"):
			from Plugins.Extensions.DreamPlex.plugin import DPS_MainMenu
			self.session.open(DPS_MainMenu)
		else:
			self.session.open(MessageBox, _("The DreamPlex plugin is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )

from Tools.BoundFunction import boundFunction
import inspect

# depends on InfoBarExtensions
class InfoBarPlugins:
	def __init__(self):
		self.addExtension(extension = self.getPluginList, type = InfoBarExtensions.EXTENSION_LIST)

	def getPluginName(self, name):
		return name

	def getPluginList(self):
		l = []
		for p in plugins.getPlugins(where = PluginDescriptor.WHERE_EXTENSIONSMENU):
			args = inspect.getargspec(p.__call__)[0]
			if len(args) == 1 or len(args) == 2 and isinstance(self, InfoBarChannelSelection):
				l.append(((boundFunction(self.getPluginName, p.name), boundFunction(self.runPlugin, p), lambda: True), None, p.name))
		l.sort(key = lambda e: e[2]) # sort by name
		return l

	def runPlugin(self, plugin):
		if isinstance(self, InfoBarChannelSelection):
			plugin(session = self.session, servicelist = self.servicelist)
		else:
			plugin(session = self.session)

from Components.Task import job_manager
class InfoBarJobman:
	def __init__(self):
		self.addExtension(extension = self.getJobList, type = InfoBarExtensions.EXTENSION_LIST)

	def getJobList(self):
		if config.usage.jobtaskextensions.value:
			return [((boundFunction(self.getJobName, job), boundFunction(self.showJobView, job), lambda: True), None) for job in job_manager.getPendingJobs()]
		else:
			return []

	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end)))

	def showJobView(self, job):
		from Screens.TaskView import JobView
		job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job)

	def JobViewCB(self, in_background):
		job_manager.in_background = in_background

# depends on InfoBarExtensions
class InfoBarPiP:
	def __init__(self):
		try:
			self.session.pipshown
		except:
			self.session.pipshown = False

		self.lastPiPService = None

		if SystemInfo["PIPAvailable"] and isinstance(self, InfoBarEPG):
			self["PiPActions"] = HelpableActionMap(self, "InfobarPiPActions",
				{
					"activatePiP": (self.activePiP, self.activePiPName),
				})
			if self.allowPiP:
				self.addExtension((self.getShowHideName, self.showPiP, lambda: True), "blue")
				self.addExtension((self.getMoveName, self.movePiP, self.pipShown), "green")
				self.addExtension((self.getSwapName, self.swapPiP, self.pipShown), "yellow")
				self.addExtension((self.getTogglePipzapName, self.togglePipzap, self.pipShown), "red")
			else:
				self.addExtension((self.getShowHideName, self.showPiP, self.pipShown), "blue")
				self.addExtension((self.getMoveName, self.movePiP, self.pipShown), "green")

		self.lastPiPServiceTimeout = eTimer()
		self.lastPiPServiceTimeout.callback.append(self.clearLastPiPService)

	def pipShown(self):
		return self.session.pipshown

	def pipHandles0Action(self):
		return self.pipShown() and config.usage.pip_zero_button.value != "standard"

	def getShowHideName(self):
		if self.session.pipshown:
			return _("Disable Picture in Picture")
		else:
			return _("Activate Picture in Picture")

	def getSwapName(self):
		return _("Swap services")

	def getMoveName(self):
		return _("Move Picture in Picture")

	def getTogglePipzapName(self):
		slist = self.servicelist
		if slist and slist.dopipzap:
			return _("Zap focus to main screen")
		return _("Zap focus to Picture in Picture")

	def togglePipzap(self):
		if not self.session.pipshown:
			self.showPiP()
		slist = self.servicelist
		if slist and self.session.pipshown:
			slist.togglePipzap()
			if slist.dopipzap:
				currentServicePath = slist.getCurrentServicePath()
				self.servicelist.setCurrentServicePath(self.session.pip.servicePath, doZap=False)
				self.session.pip.servicePath = currentServicePath

	def showPiP(self):
		if self.session.pipshown:
			slist = self.servicelist
			if slist and slist.dopipzap:
				self.togglePipzap()
			if self.session.pipshown:
				self.lastPiPService = self.session.pip.getCurrentServiceReference()
				self.lastPiPServiceTimeout.startLongTimer(60)
				del self.session.pip
				if SystemInfo["LCDMiniTVPiP"] and int(config.lcd.minitvpipmode.value) >= 1:
						print '[LCDMiniTV] disable PIP'
						f = open("/proc/stb/lcd/mode", "w")
						f.write(config.lcd.minitvmode.value)
						f.close()
				self.session.pipshown = False
			if hasattr(self, "ScreenSaverTimerStart"):
				self.ScreenSaverTimerStart()
		else:
			service = self.session.nav.getCurrentService()
			info = service and service.info()
			if info:
				xres = str(info.getInfo(iServiceInformation.sVideoWidth))
			if info and int(xres) <= 720 or getMachineBuild() != 'blackbox7405':
				self.session.pip = self.session.instantiateDialog(PictureInPicture)
				self.session.pip.setAnimationMode(0)
				self.session.pip.show()
				newservice = self.lastPiPService or self.session.nav.getCurrentlyPlayingServiceReference() or self.servicelist.servicelist.getCurrent()
				if self.session.pip.playService(newservice):
					self.session.pipshown = True
					self.session.pip.servicePath = self.servicelist.getCurrentServicePath()
					if SystemInfo["LCDMiniTVPiP"] and int(config.lcd.minitvpipmode.value) >= 1:
						print '[LCDMiniTV] enable PIP'
						f = open("/proc/stb/lcd/mode", "w")
						f.write(config.lcd.minitvpipmode.value)
						f.close()
						f = open("/proc/stb/vmpeg/1/dst_width", "w")
						f.write("0")
						f.close()
						f = open("/proc/stb/vmpeg/1/dst_height", "w")
						f.write("0")
						f.close()
						f = open("/proc/stb/vmpeg/1/dst_apply", "w")
						f.write("1")
						f.close()
				else:
					newservice = self.session.nav.getCurrentlyPlayingServiceReference() or self.servicelist.servicelist.getCurrent()
					if self.session.pip.playService(newservice):
						self.session.pipshown = True
						self.session.pip.servicePath = self.servicelist.getCurrentServicePath()
						if SystemInfo["LCDMiniTVPiP"] and int(config.lcd.minitvpipmode.value) >= 1:
							print '[LCDMiniTV] enable PIP'
							f = open("/proc/stb/lcd/mode", "w")
							f.write(config.lcd.minitvpipmode.value)
							f.close()
							f = open("/proc/stb/vmpeg/1/dst_width", "w")
							f.write("0")
							f.close()
							f = open("/proc/stb/vmpeg/1/dst_height", "w")
							f.write("0")
							f.close()
							f = open("/proc/stb/vmpeg/1/dst_apply", "w")
							f.write("1")
							f.close()
					else:
						self.lastPiPService = None
						self.session.pipshown = False
						del self.session.pip
			elif info:
				self.session.open(MessageBox, _("Your %s %s does not support PiP HD") % (getMachineBrand(), getMachineName()), type = MessageBox.TYPE_INFO,timeout = 5 )
			else:
				self.session.open(MessageBox, _("No active channel found."), type = MessageBox.TYPE_INFO,timeout = 5 )
		if self.session.pipshown and hasattr(self, "screenSaverTimer"):
			self.screenSaverTimer.stop()

	def clearLastPiPService(self):
		self.lastPiPService = None

	def activePiP(self):
		if self.servicelist and self.servicelist.dopipzap or not self.session.pipshown:
			self.showPiP()
		else:
			self.togglePipzap()

	def activePiPName(self):
		if self.servicelist and self.servicelist.dopipzap:
			return _("Disable Picture in Picture")
		if self.session.pipshown:
			return _("Zap focus to Picture in Picture")
		else:
			return _("Activate Picture in Picture")

	def swapPiP(self):
		if self.pipShown():
			swapservice = self.session.nav.getCurrentlyPlayingServiceOrGroup()
			pipref = self.session.pip.getCurrentService()
			if swapservice and pipref and pipref.toString() != swapservice.toString():
				currentServicePath = self.servicelist.getCurrentServicePath()
				currentBouquet = self.servicelist and self.servicelist.getRoot()
				self.servicelist.setCurrentServicePath(self.session.pip.servicePath, doZap=False)
				self.session.pip.playService(swapservice)
				self.session.nav.playService(pipref, checkParentalControl=False, adjust=False)
				self.session.pip.servicePath = currentServicePath
				self.session.pip.servicePath[1] = currentBouquet
				if self.servicelist.dopipzap:
					# This unfortunately won't work with subservices
					self.servicelist.setCurrentSelection(self.session.pip.getCurrentService())

	def movePiP(self):
		if self.pipShown():
			self.session.open(PiPSetup, pip = self.session.pip)

	def pipDoHandle0Action(self):
		use = config.usage.pip_zero_button.value
		if "swap" == use:
			self.swapPiP()
		elif "swapstop" == use:
			self.swapPiP()
			self.showPiP()
		elif "stop" == use:
			self.showPiP()

class InfoBarInstantRecord:
	"""Instant Record - handles the instantRecord action in order to
	start/stop instant records"""
	def __init__(self):
		self["InstantRecordActions"] = HelpableActionMap(self, "InfobarInstantRecord",
			{
				"instantRecord": (self.instantRecord, _("Instant recording...")),
			})
		self.SelectedInstantServiceRef = None
		if isStandardInfoBar(self):
			self.recording = []
		else:
			from Screens.InfoBar import InfoBar
			InfoBarInstance = InfoBar.instance
			if InfoBarInstance:
				self.recording = InfoBarInstance.recording

	def moveToTrash(self, entry):
		print "[InfoBarGenerics] instantRecord stop and delete recording: ", entry.name
		import Tools.Trashcan
		trash = Tools.Trashcan.createTrashFolder(entry.Filename)
		from MovieSelection import moveServiceFiles
# Don't crash on errors...the sub-handlers trap and re-raise errors...
		try:
			moveServiceFiles(entry.Filename, trash, entry.name, allowCopy=False)
		except:
			pass

	def stopCurrentRecording(self, entry = -1):
		def confirm(answer=False):
			if answer:
				self.session.nav.RecordTimer.removeEntry(self.recording[entry])
				if self.deleteRecording:
					self.moveToTrash(self.recording[entry])
				self.recording.remove(self.recording[entry])
		if entry is not None and entry != -1:
			msg =  _("Stop recording:")
			if self.deleteRecording:
				msg = _("Stop and delete recording:")
			msg += "\n"
			msg += " - " + self.recording[entry].name + "\n"
			self.session.openWithCallback(confirm, MessageBox, msg, MessageBox.TYPE_YESNO)

	def stopAllCurrentRecordings(self, list):
		def confirm(answer=False):
			if answer:
				for entry in list:
					self.session.nav.RecordTimer.removeEntry(entry[0])
					self.recording.remove(entry[0])
					if self.deleteRecording:
						self.moveToTrash(entry[0])
		msg =  _("Stop recordings:")
		if self.deleteRecording:
			msg = _("Stop and delete recordings:")
		msg += "\n"
		for entry in list:
			msg += " - " + entry[0].name + "\n"
		self.session.openWithCallback(confirm, MessageBox, msg, MessageBox.TYPE_YESNO)

	def getProgramInfoAndEvent(self, info, name):
		info["serviceref"] = hasattr(self, "SelectedInstantServiceRef") and self.SelectedInstantServiceRef or self.session.nav.getCurrentlyPlayingServiceOrGroup()

		# try to get event info
		event = None
		try:
			epg = eEPGCache.getInstance()
			event = epg.lookupEventTime(info["serviceref"], -1, 0)
			if event is None:
				if hasattr(self, "SelectedInstantServiceRef") and self.SelectedInstantServiceRef:
					service_info = eServiceCenter.getInstance().info(self.SelectedInstantServiceRef)
					event = service_info and service_info.getEvent(self.SelectedInstantServiceRef)
				else:
					service = self.session.nav.getCurrentService()
					event = service and service.info().getEvent(0)
		except:
			pass

		info["event"] = event
		info["name"]  = name
		info["description"] = ""
		info["eventid"] = None

		if event is not None:
			curEvent = parseEvent(event)
			info["name"] = curEvent[2]
			info["description"] = curEvent[3]
			info["eventid"] = curEvent[4]
			info["end"] = curEvent[1]

	def startInstantRecording(self, limitEvent = False):
		begin = int(time())
		end = begin + 3600 # dummy
		name = "instant record"
		info = { }

		self.getProgramInfoAndEvent(info, name)
		serviceref = info["serviceref"]
		event = info["event"]

		if event is not None:
			if limitEvent:
				end = info["end"]
		else:
			if limitEvent:
				self.session.open(MessageBox, _("No event info found, recording indefinitely."), MessageBox.TYPE_INFO)

		if isinstance(serviceref, eServiceReference):
			serviceref = ServiceReference(serviceref)

		recording = RecordTimerEntry(serviceref, begin, end, info["name"], info["description"], info["eventid"], dirname = preferredInstantRecordPath())
		recording.dontSave = True

		if event is None or limitEvent == False:
			recording.autoincrease = True
			recording.setAutoincreaseEnd()

		simulTimerList = self.session.nav.RecordTimer.record(recording)

		if simulTimerList is None:	# no conflict
			recording.autoincrease = False
			self.recording.append(recording)
		else:
			if len(simulTimerList) > 1: # with other recording
				name = simulTimerList[1].name
				name_date = ' '.join((name, strftime('%F %T', localtime(simulTimerList[1].begin))))
				# print "[TIMER] conflicts with", name_date
				recording.autoincrease = True	# start with max available length, then increment
				if recording.setAutoincreaseEnd():
					self.session.nav.RecordTimer.record(recording)
					self.recording.append(recording)
					self.session.open(MessageBox, _("Record time limited due to conflicting timer %s") % name_date, MessageBox.TYPE_INFO)
				else:
					self.session.open(MessageBox, _("Could not record due to a conflicting timer %s") % name, MessageBox.TYPE_INFO)
			else:
				self.session.open(MessageBox, _("Could not record due to an invalid service %s") % serviceref, MessageBox.TYPE_INFO)
			recording.autoincrease = False

	def isInstantRecordRunning(self):
#		print "self.recording:", self.recording
		if self.recording:
			for x in self.recording:
				if x.isRunning():
					return True
		return False

	def recordQuestionCallback(self, answer):
		# print 'recordQuestionCallback'
#		print "pre:\n", self.recording

		# print 'test1'
		if answer is None or answer[1] == "no":
			# print 'test2'
			return
		list = []
		recording = self.recording[:]
		for x in recording:
			if not x in self.session.nav.RecordTimer.timer_list:
				self.recording.remove(x)
			elif x.dontSave and x.isRunning():
				list.append((x, False))

		self.deleteRecording = False
		if answer[1] == "changeduration":
			if len(self.recording) == 1:
				self.changeDuration(0)
			else:
				self.session.openWithCallback(self.changeDuration, TimerSelection, list)
		elif answer[1] == "addrecordingtime":
			if len(self.recording) == 1:
				self.addRecordingTime(0)
			else:
				self.session.openWithCallback(self.addRecordingTime, TimerSelection, list)
		elif answer[1] == "changeendtime":
			if len(self.recording) == 1:
				self.setEndtime(0)
			else:
				self.session.openWithCallback(self.setEndtime, TimerSelection, list)
		elif answer[1] == "timer":
			import TimerEdit
			self.session.open(TimerEdit.TimerEditList)
		elif answer[1] == "stop":
			if len(self.recording) == 1:
				self.stopCurrentRecording(0)
			else:
				self.session.openWithCallback(self.stopCurrentRecording, TimerSelection, list)
		elif answer[1] == "stopdelete":
			self.deleteRecording = True
			if len(self.recording) == 1:
				self.stopCurrentRecording(0)
			else:
				self.session.openWithCallback(self.stopCurrentRecording, TimerSelection, list)
		elif answer[1] == "stopall":
			self.stopAllCurrentRecordings(list)
		elif answer[1] == "stopdeleteall":
			self.deleteRecording = True
			self.stopAllCurrentRecordings(list)
		elif answer[1] in ( "indefinitely" , "manualduration", "manualendtime", "event"):
			self.startInstantRecording(limitEvent = answer[1] in ("event", "manualendtime") or False)
			if answer[1] == "manualduration":
				self.changeDuration(len(self.recording)-1)
			elif answer[1] == "manualendtime":
				self.setEndtime(len(self.recording)-1)
		elif answer[1] == "savetimeshift":
			# print 'test1'
			if self.isSeekable() and self.pts_eventcount != self.pts_currplaying:
				# print 'test2'
				# noinspection PyCallByClass
				InfoBarTimeshift.SaveTimeshift(self, timeshiftfile="pts_livebuffer_%s" % self.pts_currplaying)
			else:
				# print 'test3'
				Notifications.AddNotification(MessageBox,_("Timeshift will get saved at the end of an event!"), MessageBox.TYPE_INFO, timeout=5)
				self.save_current_timeshift = True
				config.timeshift.isRecording.value = True
		elif answer[1] == "savetimeshiftEvent":
			# print 'test4'
			# noinspection PyCallByClass
			InfoBarTimeshift.saveTimeshiftEventPopup(self)

		elif answer[1].startswith("pts_livebuffer") is True:
			# print 'test2'
			# noinspection PyCallByClass
			InfoBarTimeshift.SaveTimeshift(self, timeshiftfile=answer[1])

	def setEndtime(self, entry):
		if entry is not None and entry >= 0:
			self.selectedEntry = entry
			self.endtime=ConfigClock(default = self.recording[self.selectedEntry].end)
			dlg = self.session.openWithCallback(self.TimeDateInputClosed, TimeDateInput, self.endtime)
			dlg.setTitle(_("Please change the recording end time"))

	def TimeDateInputClosed(self, ret):
		if len(ret) > 1:
			if ret[0]:
#				print "[InfoBarGenerics] stopping recording at", strftime("%F %T", localtime(ret[1]))
				if self.recording[self.selectedEntry].end != ret[1]:
					self.recording[self.selectedEntry].autoincrease = False
				self.recording[self.selectedEntry].end = ret[1]
		else:
			if self.recording[self.selectedEntry].end != int(time()):
				self.recording[self.selectedEntry].autoincrease = False
			self.recording[self.selectedEntry].end = int(time())
		self.session.nav.RecordTimer.timeChanged(self.recording[self.selectedEntry])

	def changeDuration(self, entry):
		if entry is not None and entry >= 0:
			self.selectedEntry = entry
			self.session.openWithCallback(self.inputCallback, InputBox, title=_("How many minutes do you want to record for?"), text="5  ", maxSize=True, type=Input.NUMBER)

	def addRecordingTime(self, entry):
		if entry is not None and entry >= 0:
			self.selectedEntry = entry
			self.session.openWithCallback(self.inputAddRecordingTime, InputBox, title=_("How many minutes do you want add to the recording?"), text="5  ", maxSize=True, type=Input.NUMBER)

	def inputAddRecordingTime(self, value):
		if value:
			print "[InfoBarGenerics] added", int(value), "minutes for recording."
			entry = self.recording[self.selectedEntry]
			if int(value) != 0:
				entry.autoincrease = False
			entry.end += 60 * int(value)
			self.session.nav.RecordTimer.timeChanged(entry)

	def inputCallback(self, value):
		entry = self.recording[self.selectedEntry]
		if value is not None:
			print "[InfoBarGenerics] stopping recording after", int(value), "minutes."
			if int(value) != 0:
				entry.autoincrease = False
			entry.end = int(time()) + 60 * int(value)
		else:
			if entry.end != int(time()):
				entry.autoincrease = False
			entry.end = int(time())
		self.session.nav.RecordTimer.timeChanged(entry)

	def isTimerRecordRunning(self):
		identical = timers = 0
		for timer in self.session.nav.RecordTimer.timer_list:
			if timer.isRunning() and not timer.justplay:
				timers += 1
				if self.recording:
					for x in self.recording:
						if x.isRunning() and x == timer:
							identical += 1
		return timers > identical

	def instantRecord(self, serviceRef=None):
		self.SelectedInstantServiceRef = serviceRef
		pirr = preferredInstantRecordPath()
		if not findSafeRecordPath(pirr) and not findSafeRecordPath(defaultMoviePath()):
			if not pirr:
				pirr = ""
			self.session.open(MessageBox, _("Missing ") + "\n" + pirr +
						 "\n" + _("No HDD found or HDD not initialized!"), MessageBox.TYPE_ERROR)
			return

		if isStandardInfoBar(self):
			common = ((_("Add recording (stop after current event)"), "event"),
				(_("Add recording (indefinitely)"), "indefinitely"),
				(_("Add recording (enter recording duration)"), "manualduration"),
				(_("Add recording (enter recording endtime)"), "manualendtime"),)

			timeshiftcommon = ((_("Timeshift save recording (stop after current event)"), "savetimeshift"),
				(_("Timeshift save recording (Select event)"), "savetimeshiftEvent"),)
		else:
			common = ()
			timeshiftcommon = ()

		if self.isInstantRecordRunning():
			title =_("A recording is currently in progress.\nWhat do you want to do?")
			list = common + \
				((_("Change recording (duration)"), "changeduration"),
				(_("Change recording (add time)"), "addrecordingtime"),
				(_("Change recording (end time)"), "changeendtime"),)
			list += ((_("Stop recording"), "stop"),)
			if config.usage.movielist_trashcan.value:
				list += ((_("Stop and delete recording"), "stopdelete"),)
			if len(self.recording) > 1:
				list += ((_("Stop all current recordings"), "stopall"),)
				if config.usage.movielist_trashcan.value:
					list += ((_("Stop and delete all current recordings"), "stopdeleteall"),)
			if self.isTimerRecordRunning():
				list += ((_("Stop timer recording"), "timer"),)
		else:
			title=_("Start recording?")
			list = common

			if self.isTimerRecordRunning():
				list += ((_("Stop timer recording"), "timer"),)
		if isStandardInfoBar(self) and self.timeshiftEnabled():
			list = list + timeshiftcommon

		if isStandardInfoBar(self):
			list = list + ((_("Do not record"), "no"),)

		if list:
			self.session.openWithCallback(self.recordQuestionCallback, ChoiceBox,title=title,list=list)
		else:
			return 0


class InfoBarAudioSelection:
	def __init__(self):
		self["AudioSelectionAction"] = HelpableActionMap(self, "InfobarAudioSelectionActions",
			{
				"audioSelection": (self.audioSelection, _("Audio options...")),
				"audioSelectionLong": (self.audioSelectionLong, _("Toggle Digital downmix...")),
			})

	def audioSelection(self):
		from Screens.AudioSelection import AudioSelection
		self.session.openWithCallback(self.audioSelected, AudioSelection, infobar=self)

	def audioSelected(self, ret=None):
		print "[InfoBarGenerics][audioSelected] ", ret

	def audioSelectionLong(self):
		if SystemInfo["CanDownmixAC3"]:
			if config.av.downmix_ac3.value:
				message = _("Dobly Digital downmix is now") + " " + _("disabled")
				print '[InfoBarGenerics] [Audio] Dobly Digital downmix is now disabled'
				config.av.downmix_ac3.setValue(False)
			else:
				config.av.downmix_ac3.setValue(True)
				message = _("Dobly Digital downmix is now") + " " + _("enabled")
				print '[InfoBarGenerics] [Audio] Dobly Digital downmix is now enabled'
			Notifications.AddPopup(text = message, type = MessageBox.TYPE_INFO, timeout = 5, id = "DDdownmixToggle")


class InfoBarSubserviceSelection:
	def __init__(self):
		self["SubserviceSelectionAction"] = HelpableActionMap(self, "InfobarSubserviceSelectionActions",
			{
				"GreenPressed": self.GreenPressed,
			})

		self["SubserviceQuickzapAction"] = HelpableActionMap(self, "InfobarSubserviceQuickzapActions",
			{
				"nextSubservice": (self.nextSubservice, _("Switch to next sub service")),
				"prevSubservice": (self.prevSubservice, _("Switch to previous sub service"))
			}, -1)
		self["SubserviceQuickzapAction"].setEnabled(False)

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedEventInfo: self.checkSubservicesAvail
			})
		self.onClose.append(self.__removeNotifications)

		self.bsel = None

	def GreenPressed(self):
		if not config.vixsettings.Subservice.value:
			self.openTimerList()
		else:
			self.subserviceSelection()

	def __removeNotifications(self):
		self.session.nav.event.remove(self.checkSubservicesAvail)

	def checkSubservicesAvail(self):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		if not subservices or subservices.getNumberOfSubservices() == 0:
			self["SubserviceQuickzapAction"].setEnabled(False)

	def nextSubservice(self):
		self.changeSubservice(+1)

	def prevSubservice(self):
		self.changeSubservice(-1)

	def changeSubservice(self, direction):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		n = subservices and subservices.getNumberOfSubservices()
		if n and n > 0:
			selection = -1
			ref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
			idx = 0
			while idx < n:
				if subservices.getSubservice(idx).toString() == ref.toString():
					selection = idx
					break
				idx += 1
			if selection != -1:
				selection += direction
				if selection >= n:
					selection=0
				elif selection < 0:
					selection=n-1
				newservice = subservices.getSubservice(selection)
				if newservice.valid():
					del subservices
					del service
					self.session.nav.playService(newservice, False)

	def subserviceSelection(self):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		self.bouquets = self.servicelist.getBouquetList()
		n = subservices and subservices.getNumberOfSubservices()
		selection = 0
		if n and n > 0:
			ref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
			tlist = []
			idx = 0
			while idx < n:
				i = subservices.getSubservice(idx)
				if i.toString() == ref.toString():
					selection = idx
				tlist.append((i.getName(), i))
				idx += 1

			if self.bouquets and len(self.bouquets):
				keys = ["red", "blue", "", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" ] + [""] * n
				if config.usage.multibouquet.value:
					tlist = [(_("Quick zap"), "quickzap", service.subServices()), (_("Add to bouquet"), "CALLFUNC", self.addSubserviceToBouquetCallback), ("--", "")] + tlist
				else:
					tlist = [(_("Quick zap"), "quickzap", service.subServices()), (_("Add to favourites"), "CALLFUNC", self.addSubserviceToBouquetCallback), ("--", "")] + tlist
				selection += 3
			else:
				tlist = [(_("Quick zap"), "quickzap", service.subServices()), ("--", "")] + tlist
				keys = ["red", "", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" ] + [""] * n
				selection += 2

			self.session.openWithCallback(self.subserviceSelected, ChoiceBox, title=_("Please select a sub service..."), list = tlist, selection = selection, keys = keys, skin_name = "SubserviceSelection")

	def subserviceSelected(self, service):
		del self.bouquets
		if not service is None:
			if isinstance(service[1], str):
				if service[1] == "quickzap":
					from Screens.SubservicesQuickzap import SubservicesQuickzap
					self.session.open(SubservicesQuickzap, service[2])
			else:
				self["SubserviceQuickzapAction"].setEnabled(True)
				self.session.nav.playService(service[1], False)

	def addSubserviceToBouquetCallback(self, service):
		if service and len(service) > 1 and isinstance(service[1], eServiceReference):
			self.selectedSubservice = service
			if self.bouquets is None:
				cnt = 0
			else:
				cnt = len(self.bouquets)
			if cnt > 1: # show bouquet list
				self.bsel = self.session.openWithCallback(self.bouquetSelClosed, BouquetSelector, self.bouquets, self.addSubserviceToBouquet)
			elif cnt == 1: # add to only one existing bouquet
				self.addSubserviceToBouquet(self.bouquets[0][1])
				self.session.open(MessageBox, _("The service has been added to the favourites."), MessageBox.TYPE_INFO)

	def bouquetSelClosed(self, confirmed):
		self.bsel = None
		del self.selectedSubservice
		if confirmed:
			self.session.open(MessageBox, _("The service has been added to the selected bouquet."), MessageBox.TYPE_INFO)

	def addSubserviceToBouquet(self, dest):
		self.servicelist.addServiceToBouquet(dest, self.selectedSubservice[1])
		if self.bsel:
			self.bsel.close(True)
		else:
			del self.selectedSubservice

	def openTimerList(self):
		self.session.open(TimerEditList)

class InfoBarRedButton:
	def __init__(self):
		self["RedButtonActions"] = HelpableActionMap(self, "InfobarRedButtonActions",
			{
				"activateRedButton": (self.activateRedButton, _("Red button...")),
			})
		self.onHBBTVActivation = [ ]
		self.onRedButtonActivation = [ ]

	def activateRedButton(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		if info and info.getInfoString(iServiceInformation.sHBBTVUrl) != "":
			for x in self.onHBBTVActivation:
				x()
		elif False: # TODO: other red button services
			for x in self.onRedButtonActivation:
				x()

class InfoBarTimerButton:
	def __init__(self):
		self["TimerButtonActions"] = HelpableActionMap(self, "InfobarTimerButtonActions",
			{
				"timerSelection": (self.timerSelection, _("Timer selection...")),
			})

	def timerSelection(self):
		from Screens.TimerEdit import TimerEditList
		self.session.open(TimerEditList)

class InfoBarVmodeButton:
	def __init__(self):
		self["VmodeButtonActions"] = HelpableActionMap(self, "InfobarVmodeButtonActions",
			{
				"vmodeSelection": (self.vmodeSelection, _("Letterbox zoom")),
			})

	def vmodeSelection(self):
		self.session.open(VideoMode)

class VideoMode(Screen):
	def __init__(self,session):
		Screen.__init__(self, session)
		self["videomode"] = Label()

		self["actions"] = NumberActionMap( [ "InfobarVmodeButtonActions" ],
			{
				"vmodeSelection": self.selectVMode
			})

		self.Timer = eTimer()
		self.Timer.callback.append(self.quit)
		self.selectVMode()

	def selectVMode(self):
		policy = config.av.policy_43
		if self.isWideScreen():
			policy = config.av.policy_169
		idx = policy.choices.index(policy.value)
		idx = (idx + 1) % len(policy.choices)
		policy.value = policy.choices[idx]
		self["videomode"].setText(policy.value)
		self.Timer.start(1000, True)

	def isWideScreen(self):
		from Components.Converter.ServiceInfo import WIDESCREEN
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		return info.getInfo(iServiceInformation.sAspect) in WIDESCREEN

	def quit(self):
		self.Timer.stop()
		self.close()

class InfoBarAdditionalInfo:
	def __init__(self):
		self["RecordingPossible"] = Boolean(fixed=harddiskmanager.HDDCount() > 0)
		self["TimeshiftPossible"] = self["RecordingPossible"]
		self["ExtensionsAvailable"] = Boolean(fixed=1)
		# TODO: these properties should be queried from the input device keymap
		self["ShowTimeshiftOnYellow"] = Boolean(fixed=0)
		self["ShowAudioOnYellow"] = Boolean(fixed=0)
		self["ShowRecordOnRed"] = Boolean(fixed=0)

class InfoBarNotifications:
	def __init__(self):
		self.onExecBegin.append(self.checkNotifications)
		Notifications.notificationAdded.append(self.checkNotificationsIfExecing)
		self.onClose.append(self.__removeNotification)

	def __removeNotification(self):
		Notifications.notificationAdded.remove(self.checkNotificationsIfExecing)

	def checkNotificationsIfExecing(self):
		if self.execing:
			self.checkNotifications()

	def checkNotifications(self):
		notifications = Notifications.notifications
		if notifications:
			n = notifications[0]

			del notifications[0]
			cb = n[0]

			if "onSessionOpenCallback" in n[3]:
				n[3]["onSessionOpenCallback"]()
				del n[3]["onSessionOpenCallback"]

			if cb:
				dlg = self.session.openWithCallback(cb, n[1], *n[2], **n[3])
			elif not Notifications.current_notifications and n[4] == "ZapError":
				if "timeout" in n[3]:
					del n[3]["timeout"]
				n[3]["enable_input"] = False
				dlg = self.session.instantiateDialog(n[1], *n[2], **n[3])
				self.hide()
				dlg.show()
				self.notificationDialog = dlg
				eActionMap.getInstance().bindAction('', -maxint - 1, self.keypressNotification)
			else:
				dlg = self.session.open(n[1], *n[2], **n[3])

			# remember that this notification is currently active
			d = (n[4], dlg)
			Notifications.current_notifications.append(d)
			dlg.onClose.append(boundFunction(self.__notificationClosed, d))

	def closeNotificationInstantiateDialog(self):
		if hasattr(self, "notificationDialog"):
			self.session.deleteDialog(self.notificationDialog)
			del self.notificationDialog
			eActionMap.getInstance().unbindAction('', self.keypressNotification)

	def keypressNotification(self, key, flag):
		if flag:
			self.closeNotificationInstantiateDialog()

	def __notificationClosed(self, d):
		Notifications.current_notifications.remove(d)

class InfoBarServiceNotifications:
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evEnd: self.serviceHasEnded
			})

	def serviceHasEnded(self):
#		print "service end!"
		try:
			self.setSeekState(self.SEEK_STATE_PLAY)
		except:
			pass

class InfoBarCueSheetSupport:
	CUT_TYPE_IN = 0
	CUT_TYPE_OUT = 1
	CUT_TYPE_MARK = 2
	CUT_TYPE_LAST = 3

	ENABLE_RESUME_SUPPORT = False

	def __init__(self, actionmap = "InfobarCueSheetActions"):
		self["CueSheetActions"] = HelpableActionMap(self, actionmap,
			{
				"jumpPreviousMark": (self.jumpPreviousMark, _("Jump to the previous marked position")),
				"jumpNextMark": (self.jumpNextMark, _("Jump to the next marked position")),
				"toggleMark": (self.toggleMark, _("Toggle a cut mark at the current position"))
			}, prio=1)

		self.cut_list = [ ]
		self.is_closing = False
		self.resume_point = None
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evCuesheetChanged: self.downloadCuesheet,
			iPlayableService.evStopped: self.__evStopped,
			})

		self.__blockDownloadCuesheet = False
		self.__recording = None
		self.__recordingCuts = []

	def __evStopped(self):
		if isMoviePlayerInfoBar(self):
			if self.__recording and self.__recordingCuts:
				# resume mark may have been added...

				self.downloadCuesheet()

				# Clear marks added from the recording,
				# They will be added to the .cuts file when the
				# recording finishes.

				self.__clearRecordingCuts()
				self.uploadCuesheet()

	def __onClose(self):
		if self.__gotRecordEvent in NavigationInstance.instance.record_event:
			NavigationInstance.instance.record_event.remove(self.__gotRecordEvent)
		self.__recording = None

	__endEvents = (
		iRecordableService.evEnd,
		iRecordableService.evRecordStopped,
		iRecordableService.evRecordFailed,
		iRecordableService.evRecordWriteError,
		iRecordableService.evRecordAborted,
		iRecordableService.evGstRecordEnded,
	)

	def __gotRecordEvent(self, record, event):
		if record.getPtrString() != self.__recording.getPtrString():
			return
		if event in self.__endEvents:
			if self.__gotRecordEvent in NavigationInstance.instance.record_event:
				NavigationInstance.instance.record_event.remove(self.__gotRecordEvent)

			# When the recording ends, the mapping of
			# cut points from time to file offset changes
			# slightly. Upload the recording cut marks to
			# catch these changes.

			self.updateFromRecCuesheet()

			self.__recording = None
		elif event == iRecordableService.evNewEventInfo:
			self.updateFromRecCuesheet()

	def __serviceStarted(self):
		if self.is_closing:
			return

		self.__findRecording()

#		print "new service started! trying to download cuts!"
		self.downloadCuesheet()

		self.resume_point = None
		if self.ENABLE_RESUME_SUPPORT:
			for (pts, what) in self.cut_list:
				if what == self.CUT_TYPE_LAST:
					last = pts
					break
			else:
				last = getResumePoint(self.session)
			if last is None:
				return
			# only resume if at least 10 seconds ahead, or <10 seconds before the end.
			seekable = self.__getSeekable()
			if seekable is None:
				return # Should not happen?
			length = seekable.getLength() or (None,0)
#			print "seekable.getLength() returns:", length
			# Hmm, this implies we don't resume if the length is unknown...
			if (last > 900000) and (not length[1]  or (last < length[1] - 900000)):
				self.resume_point = last
				l = last / 90000
				if "ask" in config.usage.on_movie_start.value or not length[1]:
					Notifications.AddNotificationWithCallback(self.playLastCB, MessageBox, _("Do you want to resume playback?") + "\n" + (_("Resume position at %s") % ("%d:%02d:%02d" % (l/3600, l%3600/60, l%60))), timeout=30, default="yes" in config.usage.on_movie_start.value)
				elif config.usage.on_movie_start.value == "resume":
					Notifications.AddNotificationWithCallback(self.playLastCB, MessageBox, _("Resuming playback"), timeout=2, type=MessageBox.TYPE_INFO)

	def __findRecording(self):
		if isMoviePlayerInfoBar(self):
			playing = self.session.nav.getCurrentlyPlayingServiceOrGroup()
			navInstance = NavigationInstance.instance
			for timer in navInstance.RecordTimer.timer_list:
				if timer.isRunning() and not timer.justplay and timer.record_service:
					if playing and playing.getPath() == timer.Filename + timer.record_service.getFilenameExtension():
						if self.__gotRecordEvent not in navInstance.record_event:
							navInstance.record_event.append(self.__gotRecordEvent)
						self.__recording = timer.record_service
						self.onClose.append(self.__onClose)
						break

	def playLastCB(self, answer):
# This can occasionally get called with an empty (new?) self!?!
# So avoid the inevitable crash that will follow if we don't check.
#
		if answer == True and not hasattr(self, "resume_point"):
			Notifications.AddPopup(text = _("Playback information missing\nPlayback aborted to avoid crash\nPlease retry"), type = MessageBox.TYPE_WARNING, timeout = 8)
			return
		if answer == True and self.resume_point:
			self.doSeek(self.resume_point)
		self.hideAfterResume()

	def hideAfterResume(self):
		if isinstance(self, InfoBarShowHide):
			self.hide()

	def __getSeekable(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		return service.seek()

	def cueGetCurrentPosition(self):
		seek = self.__getSeekable()
		if seek is None:
			return None
		r = seek.getPlayPosition()
		if r[0]:
			return None
		return long(r[1])

	def cueGetEndCutPosition(self):
		ret = False
		isin = True
		for cp in self.cut_list:
			if cp[1] == self.CUT_TYPE_OUT:
				if isin:
					isin = False
					ret = cp[0]
			elif cp[1] == self.CUT_TYPE_IN:
				isin = True
		return ret

	def jumpPreviousNextMark(self, cmp, start=False):
		current_pos = self.cueGetCurrentPosition()
		if current_pos is None:
			return False
		mark = self.getNearestCutPoint(current_pos, cmp=cmp, start=start)
		if mark is not None:
			pts = mark[0]
		else:
			return False

		self.doSeek(pts)
		return True

	def jumpPreviousMark(self):
		# we add 5 seconds, so if the play position is <5s after
		# the mark, the mark before will be used
		self.jumpPreviousNextMark(lambda x: -x-5*90000, start=True)

	def jumpNextMark(self):
		if not self.jumpPreviousNextMark(lambda x: x-90000):
			self.doSeek(-1)

	def getNearestCutPoint(self, pts, cmp=abs, start=False):
		# can be optimized
		beforecut = True
		nearest = None
		bestdiff = -1
		instate = True
		if start:
			bestdiff = cmp(0 - pts)
			if bestdiff >= 0:
				nearest = [0, False]
		for cp in self.cut_list:
			if beforecut and cp[1] in (self.CUT_TYPE_IN, self.CUT_TYPE_OUT):
				beforecut = False
				if cp[1] == self.CUT_TYPE_IN:  # Start is here, disregard previous marks
					diff = cmp(cp[0] - pts)
					if start and diff >= 0:
						nearest = cp
						bestdiff = diff
					else:
						nearest = None
						bestdiff = -1
			if cp[1] == self.CUT_TYPE_IN:
				instate = True
			elif cp[1] == self.CUT_TYPE_OUT:
				instate = False
			elif cp[1] in (self.CUT_TYPE_MARK, self.CUT_TYPE_LAST):
				diff = cmp(cp[0] - pts)
				if instate and diff >= 0 and (nearest is None or bestdiff > diff):
					nearest = cp
					bestdiff = diff
		return nearest

	def toggleMark(self, onlyremove=False, onlyadd=False, tolerance=5*90000, onlyreturn=False):
		current_pos = self.cueGetCurrentPosition()
		if current_pos is None:
#			print "not seekable"
			return

		nearest_cutpoint = self.getNearestCutPoint(current_pos)

		if nearest_cutpoint is not None and abs(nearest_cutpoint[0] - current_pos) < tolerance:
			if onlyreturn:
				return nearest_cutpoint
			if not onlyadd:
				self.removeMark(nearest_cutpoint)
		elif not onlyremove and not onlyreturn:
			self.addMark((current_pos, self.CUT_TYPE_MARK))

		if onlyreturn:
			return None

	def addMark(self, point):
		insort(self.cut_list, point)
		self.uploadCuesheet()
		self.showAfterCuesheetOperation()

	def removeMark(self, point):
		self.cut_list.remove(point)
		self.uploadCuesheet()
		self.showAfterCuesheetOperation()

	def showAfterCuesheetOperation(self):
		if isinstance(self, InfoBarShowHide):
			self.doShow()

	def __getCuesheet(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		return service.cueSheet()

	def __clearRecordingCuts(self):
		if self.__recordingCuts:
			cut_list = []
			for point in self.cut_list:
				if point in self.__recordingCuts:
					self.__recordingCuts.remove(point)
				else:
					cut_list.append(point)
			self.__recordingCuts = []
			self.cut_list = cut_list

	def uploadCuesheet(self):
		cue = self.__getCuesheet()

		if cue is None:
#			print "upload failed, no cuesheet interface"
			return
		self.__blockDownloadCuesheet = True
		cue.setCutList(self.cut_list)
		self.__blockDownloadCuesheet = False

	def downloadCuesheet(self):
		# Stop cuesheet uploads from causing infinite recursion
		# through evCuesheetChanged if updateFromRecCuesheet()
		# does an uploadCuesheet()

		if self.__blockDownloadCuesheet:
			return

		cue = self.__getCuesheet()

		if cue is None:
#			print "download failed, no cuesheet interface"
			self.cut_list = [ ]
		else:
			self.cut_list = cue.getCutList()
		self.updateFromRecCuesheet()

	def updateFromRecCuesheet(self):
		if self.__recording:
			self.__clearRecordingCuts()
			rec_cuts = self.__recording.getCutList()
			for point in rec_cuts:
				if point not in self.cut_list:
					insort(self.cut_list, point)
					self.__recordingCuts.append(point)
			if self.__recordingCuts:
				self.uploadCuesheet()

class InfoBarSummary(Screen):
	skin = """
	<screen position="0,0" size="132,64">
		<widget source="global.CurrentTime" render="Label" position="62,46" size="82,18" font="Regular;16" >
			<convert type="ClockToText">WithSeconds</convert>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text=" " position="62,46" size="82,18" zPosition="1" >
			<convert type="ConfigEntryTest">config.usage.blinking_display_clock_during_recording,True,CheckSourceBoolean</convert>
			<convert type="ConditionalShowHide">Blink</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="6,4" size="120,42" font="Regular;18" >
			<convert type="ServiceName">Name</convert>
		</widget>
		<widget source="session.Event_Now" render="Progress" position="6,46" size="46,18" borderWidth="1" >
			<convert type="EventTime">Progress</convert>
		</widget>
	</screen>"""

# for picon:  (path="piconlcd" will use LCD picons)
#		<widget source="session.CurrentService" render="Picon" position="6,0" size="120,64" path="piconlcd" >
#			<convert type="ServiceName">Reference</convert>
#		</widget>

class InfoBarSummarySupport:
	def __init__(self):
		pass

	def createSummary(self):
		return InfoBarSummary

class InfoBarMoviePlayerSummary(Screen):
	skin = """
	<screen position="0,0" size="132,64">
		<widget source="global.CurrentTime" render="Label" position="62,46" size="64,18" font="Regular;16" halign="right" >
			<convert type="ClockToText">WithSeconds</convert>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text=" " position="62,46" size="64,18" zPosition="1" >
			<convert type="ConfigEntryTest">config.usage.blinking_display_clock_during_recording,True,CheckSourceBoolean</convert>
			<convert type="ConditionalShowHide">Blink</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="6,4" size="120,42" font="Regular;18" >
			<convert type="ServiceName">Name</convert>
		</widget>
		<widget source="session.CurrentService" render="Progress" position="6,46" size="56,18" borderWidth="1" >
			<convert type="ServicePosition">Position</convert>
		</widget>
	</screen>"""
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent = parent)
		self["state_summary"] = StaticText("")
		self["speed_summary"] = StaticText("")
		self["statusicon_summary"] = MultiPixmap()
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, state_summary, speed_summary, statusicon_summary):
		self["state_summary"].setText(state_summary)
		self["speed_summary"].setText(speed_summary)
		self["statusicon_summary"].setPixmapNum(int(statusicon_summary))

class InfoBarMoviePlayerSummarySupport:
	def __init__(self):
		pass

	def createSummary(self):
		return InfoBarMoviePlayerSummary

class InfoBarTeletextPlugin:
	def __init__(self):
		self.teletext_plugin = None
		for p in plugins.getPlugins(PluginDescriptor.WHERE_TELETEXT):
			self.teletext_plugin = p

		if self.teletext_plugin is not None:
			self["TeletextActions"] = HelpableActionMap(self, "InfobarTeletextActions",
				{
					"startTeletext": (self.startTeletext, _("View teletext..."))
				})
		else:
			print "[InfoBarGenerics] no teletext plugin found!"

	def startTeletext(self):
		self.teletext_plugin and self.teletext_plugin(session=self.session, service=self.session.nav.getCurrentService())

class InfoBarSubtitleSupport(object):
	def __init__(self):
		object.__init__(self)
		self["SubtitleSelectionAction"] = HelpableActionMap(self, "InfobarSubtitleSelectionActions",
			{
				"subtitleSelection": (self.subtitleSelection, _("Subtitle selection...")),
			})

		self.selected_subtitle = None

		if isStandardInfoBar(self):
			self.subtitle_window = self.session.instantiateDialog(SubtitleDisplay)
			self.subtitle_window.setAnimationMode(0)
		else:
			from Screens.InfoBar import InfoBar
			self.subtitle_window = InfoBar.instance.subtitle_window

		self.subtitle_window.hide()

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.__serviceChanged,
				iPlayableService.evEnd: self.__serviceChanged,
				iPlayableService.evUpdatedInfo: self.__updatedInfo
			})

	def getCurrentServiceSubtitle(self):
		service = self.session.nav.getCurrentService()
		return service and service.subtitle()

	def subtitleSelection(self):
		service = self.session.nav.getCurrentService()
		subtitle = service and service.subtitle()
		subtitlelist = subtitle and subtitle.getSubtitleList()
		if self.selected_subtitle or subtitlelist and len(subtitlelist)>0:
			from Screens.AudioSelection import SubtitleSelection
			self.session.open(SubtitleSelection, self)
		else:
			return 0

	def doCenterDVBSubs(self):
		service = self.session.nav.getCurrentlyPlayingServiceReference()
		servicepath = service and service.getPath()
		if servicepath and servicepath.startswith("/"):
			if service.toString().startswith("1:"):
				info = eServiceCenter.getInstance().info(service)
				service = info and info.getInfoString(service, iServiceInformation.sServiceref)
				config.subtitles.dvb_subtitles_centered.value = service and eDVBDB.getInstance().getFlag(eServiceReference(service)) & self.FLAG_CENTER_DVB_SUBS and True
				return
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		config.subtitles.dvb_subtitles_centered.value = info and info.getInfo(iServiceInformation.sCenterDVBSubs) and True

	def __serviceChanged(self):
		if self.selected_subtitle:
			self.selected_subtitle = None
			self.subtitle_window.hide()

	def __updatedInfo(self):
		if not self.selected_subtitle:
			subtitle = self.getCurrentServiceSubtitle()
			cachedsubtitle = subtitle and subtitle.getCachedSubtitle()
			if cachedsubtitle:
				self.enableSubtitle(cachedsubtitle)
				self.doCenterDVBSubs()

	def enableSubtitle(self, selectedSubtitle):
		subtitle = self.getCurrentServiceSubtitle()
		self.selected_subtitle = selectedSubtitle
		if subtitle and self.selected_subtitle:
			subtitle.enableSubtitles(self.subtitle_window.instance, self.selected_subtitle)
			self.subtitle_window.show()
			self.doCenterDVBSubs()
		else:
			if subtitle:
				subtitle.disableSubtitles(self.subtitle_window.instance)
			self.subtitle_window.hide()

	def restartSubtitle(self):
		if self.selected_subtitle:
			self.enableSubtitle(self.selected_subtitle)

class InfoBarServiceErrorPopupSupport:
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evTuneFailed: self.__tuneFailed,
				iPlayableService.evTunedIn: self.__serviceStarted,
				iPlayableService.evStart: self.__serviceStarted
			})
		self.__serviceStarted()

	def __serviceStarted(self):
		self.closeNotificationInstantiateDialog()
		self.last_error = None
		Notifications.RemovePopup(id = "ZapError")

	def __tuneFailed(self):
		if not config.usage.hide_zap_errors.value or not config.usage.remote_fallback_enabled.value:
			service = self.session.nav.getCurrentService()
			info = service and service.info()
			error = info and info.getInfo(iServiceInformation.sDVBState)
			if not config.usage.remote_fallback_enabled.value and (error == eDVBServicePMTHandler.eventMisconfiguration or error == eDVBServicePMTHandler.eventNoResources):
				self.session.nav.currentlyPlayingServiceReference = None
				self.session.nav.currentlyPlayingServiceOrGroup = None

			if error == self.last_error:
				error = None
			else:
				self.last_error = error

			error = {
				eDVBServicePMTHandler.eventNoResources: _("No free tuner!"),
				eDVBServicePMTHandler.eventTuneFailed: _("Tune failed!"),
				eDVBServicePMTHandler.eventNoPAT: _("No data on transponder!\n(Timeout reading PAT)"),
				eDVBServicePMTHandler.eventNoPATEntry: _("Service not found!\n(SID not found in PAT)"),
				eDVBServicePMTHandler.eventNoPMT: _("Service invalid!\n(Timeout reading PMT)"),
				eDVBServicePMTHandler.eventNewProgramInfo: None,
				eDVBServicePMTHandler.eventTuned: None,
				eDVBServicePMTHandler.eventSOF: None,
				eDVBServicePMTHandler.eventEOF: None,
				eDVBServicePMTHandler.eventMisconfiguration: _("Service unavailable!\nCheck tuner configuration!"),
			}.get(error) #this returns None when the key not exist in the dict

			if error and not config.usage.hide_zap_errors.value:
				self.closeNotificationInstantiateDialog()
				if hasattr(self, "dishDialog") and not self.dishDialog.dishState():
					Notifications.AddPopup(text = error, type = MessageBox.TYPE_ERROR, timeout = 5, id = "ZapError")

class InfoBarZoom:
	def __init__(self):
		self.zoomrate=0
		self.zoomin=1

		self["ZoomActions"] = HelpableActionMap(self, "InfobarZoomActions",
			{
				"ZoomInOut":(self.ZoomInOut, _("Zoom In/Out TV...")),
				"ZoomOff":(self.ZoomOff, _("Zoom Off...")),
			}, prio=2)

	def ZoomInOut(self):
		zoomval=0
		if self.zoomrate > 3:
			self.zoomin = 0
		elif self.zoomrate < -9:
			self.zoomin = 1

		if self.zoomin == 1:
			self.zoomrate += 1
		else:
			self.zoomrate -= 1

		if self.zoomrate < 0:
			zoomval=abs(self.zoomrate)+10
		else:
			zoomval=self.zoomrate
		# print "zoomRate:", self.zoomrate
		# print "zoomval:", zoomval
		file = open("/proc/stb/vmpeg/0/zoomrate", "w")
		file.write('%d' % int(zoomval))
		file.close()

	def ZoomOff(self):
		self.zoomrate = 0
		self.zoomin = 1
		f = open("/proc/stb/vmpeg/0/zoomrate", "w")
		f.write(str(0))
		f.close()

class InfoBarHdmi:
	def __init__(self):
		self.hdmi_enabled_full = False
		self.hdmi_enabled_pip = False

		if SystemInfo['HasHDMIin']:
			if not self.hdmi_enabled_full:
				self.addExtension((self.getHDMIInFullScreen, self.HDMIInFull, lambda: True), "blue")
			if not self.hdmi_enabled_pip:
				self.addExtension((self.getHDMIInPiPScreen, self.HDMIInPiP, lambda: True), "green")

		self["HDMIActions"] = HelpableActionMap(self, "InfobarHDMIActions",
			{
				"HDMIin":(self.HDMIIn, _("Switch to HDMI in mode")),
				"HDMIinLong":(self.HDMIInLong, _("Switch to HDMI in mode")),
			}, prio=2)

	def HDMIInLong(self):
		if self.LongButtonPressed:
			if not hasattr(self.session, 'pip') and not self.session.pipshown:
				self.session.pip = self.session.instantiateDialog(PictureInPicture)
				self.session.pip.playService(eServiceReference('8192:0:1:0:0:0:0:0:0:0:'))
				self.session.pip.show()
				self.session.pipshown = True
			else:
				curref = self.session.pip.getCurrentService()
				if curref and curref.type != 8192:
					self.session.pip.playService(eServiceReference('8192:0:1:0:0:0:0:0:0:0:'))
				else:
					self.session.pipshown = False
					del self.session.pip

	def HDMIIn(self):
		if not self.LongButtonPressed:
			slist = self.servicelist
			curref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
			if curref and curref.type != 8192:
				self.session.nav.playService(eServiceReference('8192:0:1:0:0:0:0:0:0:0:'))
			else:
				self.session.nav.playService(slist.servicelist.getCurrent())

	def getHDMIInFullScreen(self):
		if not self.hdmi_enabled_full:
			return _("Turn on HDMI-IN full screen mode")
		else:
			return _("Turn off HDMI-IN full screen mode")

	def getHDMIInPiPScreen(self):
		if not self.hdmi_enabled_pip:
			return _("Turn on HDMI-IN PiP mode")
		else:
			return _("Turn off HDMI-IN PiP mode")

	def HDMIInPiP(self):
		if not hasattr(self.session, 'pip') and not self.session.pipshown:
			self.hdmi_enabled_pip = True
			self.session.pip = self.session.instantiateDialog(PictureInPicture)
			self.session.pip.playService(eServiceReference('8192:0:1:0:0:0:0:0:0:0:'))
			self.session.pip.show()
			self.session.pipshown = True
			self.session.pip.servicePath = self.servicelist.getCurrentServicePath()
		else:
			curref = self.session.pip.getCurrentService()
			if curref and curref.type != 8192:
				self.hdmi_enabled_pip = True
				self.session.pip.playService(eServiceReference('8192:0:1:0:0:0:0:0:0:0:'))
			else:
				self.hdmi_enabled_pip = False
				self.session.pipshown = False
				del self.session.pip

	def HDMIInFull(self):
		slist = self.servicelist
		curref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if curref and curref.type != 8192:
			self.hdmi_enabled_full = True
			self.session.nav.playService(eServiceReference('8192:0:1:0:0:0:0:0:0:0:'))
		else:
			self.hdmi_enabled_full = False
			self.session.nav.playService(slist.servicelist.getCurrent())
