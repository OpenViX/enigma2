import os
import RecordTimer
import Components.ParentalControl
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.config import config
from Components.AVSwitch import AVSwitch
from Components.Console import Console
from Components.ImportChannels import ImportChannels
from Components.SystemInfo import SystemInfo
from Components.Sources.StreamService import StreamServiceList
from boxbranding import getMachineBrand, getMachineName, getBoxType
from Components.Task import job_manager
from Tools.Directories import mediafilesInUse
from Tools import Notifications
from time import time, localtime
from GlobalActions import globalActionMap
from enigma import eDVBVolumecontrol, eTimer, eDVBLocalTimeHandler, eServiceReference, eStreamServer, quitMainloop, iRecordableService
from Tools.Directories import resolveFilename, SCOPE_LCDSKIN

inStandby = None
infoBarInstance = None

MACHINEBRAND = getMachineBrand()
MACHINENAME = getMachineName()
BOXTYPE = getBoxType()

QUIT_SHUTDOWN = 1
QUIT_REBOOT = 2
QUIT_RESTART = 3
QUIT_UPGRADE_FP = 4
QUIT_ERROR_RESTART = 5
QUIT_DEBUG_RESTART = 6
QUIT_MAINT = 16
QUIT_UPGRADE_PROGRAM = 42
QUIT_IMAGE_RESTORE = 43
GB_ENTER_WOL = 44

def setLCDModeMinitTV(value):
	try:
		f = open("/proc/stb/lcd/mode", "w")
		f.write(value)
		f.close()
	except:
		pass

def isInfoBarInstance():
	global infoBarInstance
	if infoBarInstance is None:
		from Screens.InfoBar import InfoBar
		if InfoBar.instance:
			infoBarInstance = InfoBar.instance
	return infoBarInstance

def checkTimeshiftRunning():
	infobar_instance = isInfoBarInstance()
	return config.usage.check_timeshift.value and infobar_instance and infobar_instance.timeshiftEnabled() and infobar_instance.timeshift_was_activated


class StandbyScreen(Screen):
	def __init__(self, session, StandbyCounterIncrease=True):
		Screen.__init__(self, session)
		self.skinName = "Standby"
		self.avswitch = AVSwitch()

		print "[Standby] enter standby"

		self["actions"] = ActionMap(["StandbyActions"],
		{
			"power": self.Power,
			"discrete_on": self.Power
		}, -1)

		globalActionMap.setEnabled(False)

		self.infoBarInstance = isInfoBarInstance()
		from Screens.SleepTimerEdit import isNextWakeupTime
		self.StandbyCounterIncrease = StandbyCounterIncrease
		self.standbyTimeoutTimer = eTimer()
		self.standbyTimeoutTimer.callback.append(self.standbyTimeout)
		self.standbyStopServiceTimer = eTimer()
		self.standbyStopServiceTimer.callback.append(self.stopService)
		self.standbyWakeupTimer = eTimer()
		self.standbyWakeupTimer.callback.append(self.standbyWakeup)
		self.timeHandler = None

		self.setMute()

		# set LCDminiTV off
		if SystemInfo["Display"] and SystemInfo["LCDMiniTV"]:
			setLCDModeMinitTV("0")

		self.paused_service = self.paused_action = False

		self.prev_running_service = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if Components.ParentalControl.parentalControl.isProtected(self.prev_running_service):
			self.prev_running_service = eServiceReference(config.tv.lastservice.value)
		service = self.prev_running_service and self.prev_running_service.toString()
		if service:
			if service.rsplit(":", 1)[1].startswith("/"):
				self.paused_service = hasattr(self.session.current_dialog, "pauseService") and hasattr(self.session.current_dialog, "unPauseService") and self.session.current_dialog or self.infoBarInstance
				self.paused_action = hasattr(self.paused_service, "seekstate") and hasattr(self.paused_service, "SEEK_STATE_PLAY") and self.paused_service.seekstate == self.paused_service.SEEK_STATE_PLAY
				self.paused_action and self.paused_service.pauseService()
		if not self.paused_service:
			self.timeHandler =  eDVBLocalTimeHandler.getInstance()
			if self.timeHandler.ready():
				if self.session.nav.getCurrentlyPlayingServiceOrGroup():
					self.stopService()
				else:
					self.standbyStopServiceTimer.startLongTimer(5)
				self.timeHandler = None
			else:
				self.timeHandler.m_timeUpdated.get().append(self.stopService)

		if self.session.pipshown:
			self.infoBarInstance and hasattr(self.infoBarInstance, "showPiP") and self.infoBarInstance.showPiP()

		if SystemInfo["ScartSwitch"]:
			self.avswitch.setInput("SCART")
		else:
			self.avswitch.setInput("AUX")
		if os.path.exists("/proc/stb/hdmi/output"):
			open("/proc/stb/hdmi/output", "w").write("off")

		gotoShutdownTime = int(config.usage.standby_to_shutdown_timer.value)
		if gotoShutdownTime:
			self.standbyTimeoutTimer.startLongTimer(gotoShutdownTime)

		gotoWakeupTime = isNextWakeupTime(True)
		if gotoWakeupTime != -1:
			curtime = localtime(time())
			if curtime.tm_year > 1970:
				wakeup_time = int(gotoWakeupTime - time())
				if wakeup_time > 0:
					self.standbyWakeupTimer.startLongTimer(wakeup_time)

		self.onFirstExecBegin.append(self.__onFirstExecBegin)
		self.onClose.append(self.__onClose)

	def __onClose(self):
		global inStandby
		inStandby = None
		self.standbyTimeoutTimer.stop()
		self.standbyStopServiceTimer.stop()
		self.standbyWakeupTimer.stop()
		self.timeHandler and self.timeHandler.m_timeUpdated.get().remove(self.stopService)
		if self.paused_service:
			self.paused_action and self.paused_service.unPauseService()
		elif self.prev_running_service:
			service = self.prev_running_service.toString()
			if config.servicelist.startupservice_onstandby.value:
				self.session.nav.playService(eServiceReference(config.servicelist.startupservice.value))
				self.infoBarInstance and self.infoBarInstance.servicelist.correctChannelNumber()
			else:
				self.session.nav.playService(self.prev_running_service)
		self.session.screen["Standby"].boolean = False
		globalActionMap.setEnabled(True)
		if RecordTimer.RecordTimerEntry.receiveRecordEvents:
			RecordTimer.RecordTimerEntry.stopTryQuitMainloop()
		self.avswitch.setInput("ENCODER")
		self.leaveMute()
		if os.path.exists("/proc/stb/hdmi/output"):
			open("/proc/stb/hdmi/output", "w").write("on")
		if config.usage.remote_fallback_import_standby.value:
			ImportChannels()

	def __onFirstExecBegin(self):
		global inStandby
		inStandby = self
		self.session.screen["Standby"].boolean = True
		if self.StandbyCounterIncrease:
			config.misc.standbyCounter.value += 1

	def Power(self):
		print "[Standby] leave standby"
		self.close(True)

	def setMute(self):
		self.wasMuted = eDVBVolumecontrol.getInstance().isMuted()
		if not self.wasMuted:
			eDVBVolumecontrol.getInstance().volumeMute()

	def leaveMute(self):
		if not self.wasMuted:
			eDVBVolumecontrol.getInstance().volumeUnMute()

	def stopService(self):
		self.prev_running_service = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if Components.ParentalControl.parentalControl.isProtected(self.prev_running_service):
			self.prev_running_service = eServiceReference(config.tv.lastservice.value)
		self.session.nav.stopService()

	def standbyTimeout(self):
		if config.usage.standby_to_shutdown_timer_blocktime.value:
			curtime = localtime(time())
			if curtime.tm_year > 1970: #check if the current time is valid
				curtime = (curtime.tm_hour, curtime.tm_min, curtime.tm_sec)
				begintime = tuple(config.usage.standby_to_shutdown_timer_blocktime_begin.value)
				endtime = tuple(config.usage.standby_to_shutdown_timer_blocktime_end.value)
				if begintime <= endtime and (curtime >= begintime and curtime < endtime) or begintime > endtime and (curtime >= begintime or curtime < endtime):
					duration = (endtime[0]*3600 + endtime[1]*60) - (curtime[0]*3600 + curtime[1]*60 + curtime[2])
					if duration:
						if duration < 0:
							duration += 24*3600
						self.standbyTimeoutTimer.startLongTimer(duration)
						return
		if self.session.screen["TunerInfo"].tuner_use_mask or mediafilesInUse(self.session):
			self.standbyTimeoutTimer.startLongTimer(600)
		else:
			RecordTimer.RecordTimerEntry.TryQuitMainloop()

	def standbyWakeup(self):
		self.Power()

	def createSummary(self):
		return StandbySummary

class Standby(StandbyScreen):
	def __init__(self, session, StandbyCounterIncrease=True):
		if checkTimeshiftRunning():
			self.skin = """<screen position="0,0" size="0,0"/>"""
			Screen.__init__(self, session)
			self.infoBarInstance = isInfoBarInstance()
			self.StandbyCounterIncrease = StandbyCounterIncrease
			self.onFirstExecBegin.append(self.showCheckTimeshiftRunning)
			self.onHide.append(self.close)
		else:
			StandbyScreen.__init__(self, session, StandbyCounterIncrease)

	def showCheckTimeshiftRunning(self):
		self.infoBarInstance.checkTimeshiftRunning(self.showCheckTimeshiftRunningCallback, timeout=20)

	def showCheckTimeshiftRunningCallback(self, answer=False):
		if answer:
			self.onClose.append(self.goStandby)

	def goStandby(self):
		Notifications.AddNotification(StandbyScreen, self.StandbyCounterIncrease)

class StandbySummary(Screen):
	if getBoxType() in ('gbquad4k', 'gbue4k', 'gbquadplus', 'gbquad', 'gbultraue', 'gbultraueh', 'gb800ueplus', 'gb800ue'):
                def __init__(self, session, what=None):
			Screen.__init__(self, session)
	else:
		skin = """
		<screen position="0,0" size="132,64">
			<widget source="global.CurrentTime" render="Label" position="0,0" size="132,64" font="Regular;40" halign="center">
				<convert type="ClockToText" />
			</widget>
			<widget source="session.RecordState" render="FixedLabel" text=" " position="0,0" size="132,64" zPosition="1" >
				<convert type="ConfigEntryTest">config.usage.blinking_display_clock_during_recording,True,CheckSourceBoolean</convert>
				<convert type="ConditionalShowHide">Blink</convert>
			</widget>
		</screen>"""

class QuitMainloopScreen(Screen):
	def __init__(self, session, retvalue=QUIT_SHUTDOWN):
		self.skin = """<screen name="QuitMainloopScreen" position="fill" flags="wfNoBorder">
				<ePixmap pixmap="icons/input_info.png" position="c-27,c-60" size="53,53" alphatest="on" />
				<widget name="text" position="center,c+5" size="720,100" font="Regular;22" halign="center" />
			</screen>"""
		Screen.__init__(self, session)
		from Components.Label import Label
		text = {
			QUIT_SHUTDOWN: _("Your %s %s is shutting down") % (MACHINEBRAND, MACHINENAME),
			QUIT_REBOOT: _("Your %s %s is rebooting") % (MACHINEBRAND, MACHINENAME),
			QUIT_RESTART: _("The user interface of your %s %s is restarting") % (MACHINEBRAND, MACHINENAME),
			QUIT_UPGRADE_FP: _("Your frontprocessor will be updated\nPlease wait until your %s %s reboots\nThis may take a few minutes") % (MACHINEBRAND, MACHINENAME),
			QUIT_UPGRADE_PROGRAM: _("Unattended update in progress\nPlease wait until your %s %s reboots\nThis may take a few minutes") % (MACHINEBRAND, MACHINENAME),
			GB_ENTER_WOL: _("Your %s %s goes to WOL") % (MACHINEBRAND, MACHINENAME)
		}.get(retvalue)
		self["text"] = Label(text)

inTryQuitMainloop = False

def getReasons(session, retvalue=QUIT_SHUTDOWN):
	recordings = session.nav.getRecordings()
	jobs = len(job_manager.getPendingJobs())
	reasons = []
	next_rec_time = -1
	if not recordings:
		next_rec_time = session.nav.RecordTimer.getNextRecordingTime()
	if recordings or (next_rec_time > 0 and (next_rec_time - time()) < 360):
		reasons.append(_("Recording(s) are in progress or coming up in few seconds!"))
	if jobs:
		if jobs == 1:
			job = job_manager.getPendingJobs()[0]
			reasons.append("%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end))))
		else:
			reasons.append((ngettext("%d job is running in the background!", "%d jobs are running in the background!", jobs) % jobs))
	if checkTimeshiftRunning():
		reasons.append(_("You seem to be in timeshift!"))
	if eStreamServer.getInstance().getConnectedClients() or StreamServiceList:
		reasons.append(_("Client is streaming from this box!"))
	if not reasons and mediafilesInUse(session) and retvalue in (QUIT_SHUTDOWN, QUIT_REBOOT, QUIT_UPGRADE_FP, QUIT_UPGRADE_PROGRAM, GB_ENTER_WOL):
		reasons.append(_("A file from media is in use!"))
	return "\n".join(reasons)

class TryQuitMainloop(MessageBox):
	def __init__(self, session, retvalue=QUIT_SHUTDOWN, timeout=-1, default_yes=False, check_reasons=True):
		self.retval = retvalue
		self.connected = False
		reason = check_reasons and getReasons(session, retvalue)
		if reason:
			text = {
				QUIT_SHUTDOWN: _("Really shutdown your %s %s now?") % (MACHINEBRAND, MACHINENAME),
				QUIT_REBOOT: _("Really reboot your %s %s now?") % (MACHINEBRAND, MACHINENAME),
				QUIT_RESTART: _("Really restart your %s %s now?") % (MACHINEBRAND, MACHINENAME),
				QUIT_UPGRADE_FP: _("Really update the frontprocessor and reboot now?"),
				QUIT_UPGRADE_PROGRAM: _("Really update your %s %s and reboot now?") % (MACHINEBRAND, MACHINENAME),
				GB_ENTER_WOL: _("Really WOL now?")
			}.get(retvalue, None)
			if text:
				MessageBox.__init__(self, session, "%s\n%s" % (reason, text), type=MessageBox.TYPE_YESNO, timeout=timeout, default=default_yes)
				self.skinName = "MessageBoxSimple"
				session.nav.record_event.append(self.getRecordEvent)
				self.connected = True
				self.onShow.append(self.__onShow)
				self.onHide.append(self.__onHide)
				return
		self.skin = """<screen position="0,0" size="0,0"/>"""
		Screen.__init__(self, session)
		self.close(True)

	def getRecordEvent(self, recservice, event):
		#if event == iRecordableService.evEnd and checkTimeshiftRunning:
		#	return
		#else:
		if event == iRecordableService.evEnd:
			recordings = self.session.nav.getRecordings()
			if not recordings: # no more recordings exist
				rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
				if rec_time > 0 and (rec_time - time()) < 360:
					self.initTimeout(360) # wait for next starting timer
					self.startTimer()
				else:
					self.close(True) # immediate shutdown
		elif event == iRecordableService.evStart:
			self.stopTimer()

	def close(self, value):
		if self.connected:
			self.connected = False
			self.session.nav.record_event.remove(self.getRecordEvent)
		if value:
			self.hide()
			if self.retval == QUIT_SHUTDOWN:
				config.misc.DeepStandby.value = True
				if not inStandby:
					if SystemInfo["HasHDMI-CEC"] and config.hdmicec.enabled.value and config.hdmicec.control_tv_standby.value and config.hdmicec.next_boxes_detect.value:
						import Components.HdmiCec
						Components.HdmiCec.hdmi_cec.secondBoxActive()
						self.delay = eTimer()
						self.delay.timeout.callback.append(self.quitMainloop)
						self.delay.start(1500, True)
						return
			elif not inStandby:
				config.misc.RestartUI.value = True
				config.misc.RestartUI.save()
			self.quitMainloop()
		else:
			MessageBox.close(self, True)

	def quitMainloop(self):
		if self.retval == QUIT_RESTART:
			config.misc.RestartUI.value = True
		config.misc.RestartUI.save()
		self.session.nav.stopService()
		self.quitScreen = self.session.instantiateDialog(QuitMainloopScreen, retvalue=self.retval)
		self.quitScreen.show()
		quitMainloop(self.retval)

	def __onShow(self):
		global inTryQuitMainloop
		inTryQuitMainloop = True

	def __onHide(self):
		global inTryQuitMainloop
		inTryQuitMainloop = False
