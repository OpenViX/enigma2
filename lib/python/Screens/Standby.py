from os import path
from gettext import dgettext
from time import localtime, time
from enigma import eDVBVolumecontrol, eTimer, eDVBLocalTimeHandler, eServiceReference, eStreamServer
from boxbranding import getMachineBrand, getMachineName, getBoxType, getBrandOEM, getMachineBuild
from GlobalActions import globalActionMap

from Components.ActionMap import ActionMap
from Components.AVSwitch import AVSwitch
from Components.config import config
from Components.Console import Console
import Components.ParentalControl
from Components.SystemInfo import SystemInfo
from Components.Sources.StaticText import StaticText
from Components.Sources.StreamService import StreamServiceList
import Screens.InfoBar
from Screens.Screen import Screen
from Tools import Notifications

inStandby = None

QUIT_SHUTDOWN = 1
QUIT_REBOOT = 2
QUIT_RESTART = 3
QUIT_UPGRADE_FP = 4
QUIT_ERROR_RESTART = 5
QUIT_ANDROID = 12
QUIT_MAINT = 16
QUIT_UPGRADE_PROGRAM = 42
QUIT_IMAGE_RESTORE = 43

def setLCDMiniTVMode(value):
	try:
		f = open("/proc/stb/lcd/mode", "w")
		f.write(value)
		f.close()
	except:
		pass

class Standby2(Screen):
	def Power(self):
		if getBrandOEM() in ('dinobot') or SystemInfo["HasHiSi"]:
			try:
				open("/proc/stb/hdmi/output", "w").write("on")
			except:
				pass
		print "[Standby] leave standby"
		self.close(True)

	def setMute(self):
		self.wasMuted = eDVBVolumecontrol.getInstance().isMuted()
		if not self.wasMuted:
			eDVBVolumecontrol.getInstance().volumeMute()

	def leaveMute(self):
		if not self.wasMuted:
			eDVBVolumecontrol.getInstance().volumeUnMute()

	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "Standby"
		self.avswitch = AVSwitch()

		print "[Standby] enter standby"

		if path.exists("/usr/scripts/standby_enter.sh"):
			Console().ePopen("/usr/scripts/standby_enter.sh")

		self["actions"] = ActionMap( [ "StandbyActions" ],
		{
			"power": self.Power,
			"discrete_on": self.Power
		}, -1)

		globalActionMap.setEnabled(False)

		from Screens.InfoBar import InfoBar
		self.infoBarInstance = InfoBar.instance
		self.standbyStopServiceTimer = eTimer()
		self.standbyStopServiceTimer.callback.append(self.stopService)
		self.timeHandler = None

		self.setMute()

		if SystemInfo["Display"] and SystemInfo["LCDMiniTV"]:
			# set LCDminiTV off
			setLCDMiniTVMode("0")

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
		if getBrandOEM() in ('dinobot') or SystemInfo["HasHiSi"]:
			try:
				open("/proc/stb/hdmi/output", "w").write("off")
			except:
				pass

		self.onFirstExecBegin.append(self.__onFirstExecBegin)
		self.onClose.append(self.__onClose)

	def __onClose(self):
		global inStandby
		inStandby = None
		self.standbyStopServiceTimer.stop()
		self.timeHandler and self.timeHandler.m_timeUpdated.get().remove(self.stopService)
		if self.paused_service:
			self.paused_action and self.paused_service.unPauseService()
		elif self.prev_running_service:
			service = self.prev_running_service.toString()
			if config.servicelist.startupservice_onstandby.value:
				self.session.nav.playService(eServiceReference(config.servicelist.startupservice.value))
				from Screens.InfoBar import InfoBar
				InfoBar.instance and InfoBar.instance.servicelist.correctChannelNumber()
			else:
				self.session.nav.playService(self.prev_running_service)
		self.session.screen["Standby"].boolean = False
		globalActionMap.setEnabled(True)
		self.avswitch.setInput("ENCODER")
		self.leaveMute()
		if path.exists("/usr/scripts/standby_leave.sh"):
			Console().ePopen("/usr/scripts/standby_leave.sh")

	def __onFirstExecBegin(self):
		global inStandby
		inStandby = self
		self.session.screen["Standby"].boolean = True
		config.misc.standbyCounter.value += 1

	def createSummary(self):
		return StandbySummary

	def stopService(self):
		self.prev_running_service = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		if Components.ParentalControl.parentalControl.isProtected(self.prev_running_service):
			self.prev_running_service = eServiceReference(config.tv.lastservice.value)
		self.session.nav.stopService()

class Standby(Standby2):
	def __init__(self, session, menu_path=""):
		screentitle = _("Standby")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		if Screens.InfoBar.InfoBar and Screens.InfoBar.InfoBar.instance and Screens.InfoBar.InfoBar.ptsGetTimeshiftStatus(Screens.InfoBar.InfoBar.instance):
			self.skin = """<screen position="0,0" size="0,0"/>"""
			Screen.__init__(self, session)
			self.onFirstExecBegin.append(self.showMessageBox)
			self.onHide.append(self.close)
		else:
			Standby2.__init__(self, session)
		Screen.setTitle(self, title)

	def showMessageBox(self):
		Screens.InfoBar.InfoBar.checkTimeshiftRunning(Screens.InfoBar.InfoBar.instance, self.showMessageBoxcallback)

	def showMessageBoxcallback(self, answer):
		if answer:
			self.onClose.append(self.doStandby)

	def doStandby(self):
		Notifications.AddNotification(Screens.Standby.Standby2)

class StandbySummary(Screen):
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

from enigma import quitMainloop, iRecordableService
from Screens.MessageBox import MessageBox
from time import time
from Components.Task import job_manager

class QuitMainloopScreen(Screen):
	def __init__(self, session, retvalue=1):
		self.skin = """<screen name="QuitMainloopScreen" position="fill" flags="wfNoBorder">
				<ePixmap pixmap="icons/input_info.png" position="c-27,c-60" size="53,53" alphatest="on" />
				<widget name="text" position="center,c+5" size="720,100" font="Regular;22" halign="center" />
			</screen>"""
		Screen.__init__(self, session)
		from Components.Label import Label
		text = {
			QUIT_SHUTDOWN: _("Your %s %s is shutting down") % (getMachineBrand(), getMachineName()),
			QUIT_REBOOT: _("Your %s %s is rebooting") % (getMachineBrand(), getMachineName()),
			QUIT_RESTART: _("The user interface of your %s %s is restarting") % (getMachineBrand(), getMachineName()),
			QUIT_ANDROID: _("Your %s %s is rebooting into Android Mode") % (getMachineBrand(), getMachineName()),
			QUIT_MAINT: _("Your %s %s is rebooting into Recovery Mode") % (getMachineBrand(), getMachineName()),
			QUIT_UPGRADE_FP: _("Your frontprocessor will be upgraded\nPlease wait until your %s %s reboots\nThis may take a few minutes") % (getMachineBrand(), getMachineName()),
			QUIT_ERROR_RESTART: _("The user interface of your %s %s is restarting\ndue to an error in mytest.py") % (getMachineBrand(), getMachineName()),
			QUIT_UPGRADE_PROGRAM: _("Upgrade in progress\nPlease wait until your %s %s reboots\nThis may take a few minutes") % (getMachineBrand(), getMachineName()),
			QUIT_IMAGE_RESTORE: _("Reflash in progress\nPlease wait until your %s %s reboots\nThis may take a few minutes") % (getMachineBrand(), getMachineName())
		}.get(retvalue)
		self["text"] = Label(text)

inTryQuitMainloop = False

class TryQuitMainloop(MessageBox):
	def __init__(self, session, retvalue=1, timeout=-1, default_yes = True):
		self.retval = retvalue
		self.ptsmainloopvalue = retvalue
		recordings = session.nav.getRecordings()
		jobs = []
		for job in job_manager.getPendingJobs():
			if job.name != dgettext('vix', 'SoftcamCheck'):
				jobs.append(job)

		inTimeshift = Screens.InfoBar.InfoBar and Screens.InfoBar.InfoBar.instance and Screens.InfoBar.InfoBar.ptsGetTimeshiftStatus(Screens.InfoBar.InfoBar.instance)
		self.connected = False
		reason = ""
		next_rec_time = -1
		if not recordings:
			next_rec_time = session.nav.RecordTimer.getNextRecordingTime()
		if config.usage.task_warning.value and len(jobs):
			reason = (ngettext("%d job is running in the background!", "%d jobs are running in the background!", len(jobs)) % len(jobs)) + '\n'
			if len(jobs) == 1:
				job = jobs[0]
				reason += "%s: %s (%d%%)\n" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end)))
			else:
				reason += (_("%d jobs are running in the background!") % len(jobs)) + '\n'
		if inTimeshift:
			reason = _("You seem to be in timeshift!") + '\n'
		if recordings or (next_rec_time > 0 and (next_rec_time - time()) < 360):
			default_yes = False
			reason = _("Recording(s) are in progress or coming up in few seconds!") + '\n'
		if eStreamServer.getInstance().getConnectedClients() or StreamServiceList:
			reason += _("A client is streaming from this box!") + '\n'

		if reason and inStandby:
			session.nav.record_event.append(self.getRecordEvent)
			self.skinName = ""
		elif reason and not inStandby:
			text = {
				QUIT_SHUTDOWN: _("Really shutdown now?"),
				QUIT_REBOOT: _("Really reboot now?"),
				QUIT_RESTART: _("Really restart now?"),
				QUIT_ANDROID: _("Really reboot into Android Mode?"),
				QUIT_MAINT: _("Really reboot into Recovery Mode?"),
				QUIT_UPGRADE_FP: _("Really upgrade the frontprocessor and reboot now?"),
				QUIT_UPGRADE_PROGRAM: _("Really upgrade your %s %s and reboot now?") % (getMachineBrand(), getMachineName()),
				QUIT_IMAGE_RESTORE: _("Really reflash your %s %s and reboot now?") % (getMachineBrand(), getMachineName())
			}.get(retvalue)
			if text:
				MessageBox.__init__(self, session, "%s\n%s" % (reason, text), type = MessageBox.TYPE_YESNO, timeout = timeout, default = default_yes)
				self.skinName = "MessageBoxSimple"
				session.nav.record_event.append(self.getRecordEvent)
				self.connected = True
				self.onShow.append(self.__onShow)
				self.onHide.append(self.__onHide)
				return
		self.skin = """<screen position="1310,0" size="0,0"/>"""
		Screen.__init__(self, session)
		self.close(True)

	def getRecordEvent(self, recservice, event):
		if event == iRecordableService.evEnd and config.timeshift.isRecording.value:
			return
		else:
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
			self.connected=False
			self.session.nav.record_event.remove(self.getRecordEvent)
		if value:
			self.hide()
			if self.retval == 1:
				config.misc.DeepStandby.value = True
				if path.exists("/usr/scripts/standby_enter.sh"):
					Console().ePopen("/usr/scripts/standby_enter.sh")
			self.session.nav.stopService()
			self.quitScreen = self.session.instantiateDialog(QuitMainloopScreen,retvalue=self.retval)
			self.quitScreen.show()
			print "[Standby] quitMainloop #1"
			quitMainloopCode = self.retval
			if SystemInfo["Display"] and SystemInfo["LCDMiniTV"]:
				# set LCDminiTV off / fix a deep-standby-crash on some boxes / gb4k
				print "[Standby] LCDminiTV off"
				setLCDMiniTVMode("0")
			if getBoxType() == "vusolo4k":  #workaround for white display flash
				f = open("/proc/stb/fp/oled_brightness", "w")
				f.write("0")
				f.close()
			quitMainloop(self.retval)
		else:
			MessageBox.close(self, True)

	def __onShow(self):
		global inTryQuitMainloop
		inTryQuitMainloop = True

	def __onHide(self):
		global inTryQuitMainloop
		inTryQuitMainloop = False
