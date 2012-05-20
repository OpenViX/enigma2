# for localized messages
from . import _

from Components.ActionMap import NumberActionMap
from Components.Button import Button
from Components.config import config, getConfigListEntry, ConfigYesNo, ConfigClock, ConfigNumber, NoSave
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop, Standby
from time import localtime, time, strftime, mktime
from enigma import eTimer

config.vixsettings.powermanager = ConfigYesNo(default = False)
config.vixsettings.powermanager_standby = ConfigYesNo(default = False)
config.vixsettings.powermanager_standbytime = ConfigClock(default = 0) # 1:00
config.vixsettings.powermanager_standbyretry = ConfigNumber(default = 30)
config.vixsettings.powermanager_standbyretrycount = NoSave(ConfigNumber(default = 0))
config.vixsettings.powermanager_deepstandby = ConfigYesNo(default = False)
config.vixsettings.powermanager_deepstandbytime = ConfigClock(default = 0) # 1:00
config.vixsettings.powermanager_deepstandbyretry = ConfigNumber(default = 30)
config.vixsettings.powermanager_deepstandbyretrycount = NoSave(ConfigNumber(default = 0))
config.vixsettings.powermanager_guirestart = ConfigYesNo(default = False)
config.vixsettings.powermanager_guirestarttime = ConfigClock(default = 0) # 1:00
config.vixsettings.powermanager_guirestartretry = ConfigNumber(default = 30)
config.vixsettings.powermanager_guirestartretrycount = NoSave(ConfigNumber(default = 0))
config.vixsettings.powermanager_reboot = ConfigYesNo(default = False)
config.vixsettings.powermanager_reboottime = ConfigClock(default = 0) # 1:00
config.vixsettings.powermanager_rebootretry = ConfigNumber(default = 30)
config.vixsettings.powermanager_rebootretrycount = NoSave(ConfigNumber(default = 0))

autoPowerManagerTimer = None

def PowerManagerautostart(reason, session=None, **kwargs):
	"called with reason=1 to during shutdown, with reason=0 at startup?"
	global autoPowerManagerTimer
	global _session
	now = int(time())
	if reason == 0:
		print "[PowerManager] AutoStart Enabled"
		if session is not None:
			_session = session
			if autoPowerManagerTimer is None:
				autoPowerManagerTimer = AutoPowerManagerTimer(session)
	else:
		print "[PowerManager] Stop"
		autoPowerManagerTimer.stop()

def PowerManagerNextWakeup():
	"returns timestamp of next time when autostart should be called"
	if autoPowerManagerTimer:
		if config.vixsettings.powermanager.value:
			if config.vixsettings.powermanager_standby.value:
				print "[PowerManager] set to wake up"
				return autoPowerManagerTimer.standbyupdate()
	return -1

class VIXPowerManager(ConfigListScreen, Screen):
	skin = """
		<screen name="VIXPowerManager" position="center,center" size="540,450" title="Power Manager">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget name="config" position="10,45" size="480,250" scrollbarMode="showOnDemand" />
			<widget name="standbystatus" position="10,350" size="480,55" font="Regular;20" zPosition="5" />
			<widget name="deepstandbystatus" position="10,400" size="480,55" font="Regular;20" zPosition="5" />
			<widget name="guirestartstatus" position="280,350" size="480,55" font="Regular;20" zPosition="5" />
			<widget name="rebootstatus" position="280,400" size="480,55" font="Regular;20" zPosition="5" />
		</screen>"""

	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Power Manager"))
		self["standbystatus"] = Label()
		self["deepstandbystatus"] = Label()
		self["guirestartstatus"] = Label()
		self["rebootstatus"] = Label()
		self.skin = VIXPowerManager.skin
		self.onChangedEntry = [ ]
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.selectionChanged)
		self.createSetup()

		self["actions"] = NumberActionMap(["SetupActions", "MenuActions"],
		{
		  "cancel": self.keyCancel,
		  "save": self.keySaveNew,
		  "menu": self.closeRecursive,
		}, -2)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))
		self["config"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["config"].getCurrent()
		if item:
			name = self["config"].getCurrent()[0]
			desc = str(self["config"].getCurrent()[1].getText())
		else:
			name = ""
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def createSetup(self):
		self.editListEntry = None
		self.list = []
		self.list.append(getConfigListEntry(_("Enable Power Manager"), config.vixsettings.powermanager))
		if config.vixsettings.powermanager.value:
			self.list.append(getConfigListEntry(_("Enable Standby"), config.vixsettings.powermanager_standby))
			if config.vixsettings.powermanager_standby.value:
				self.list.append(getConfigListEntry(_("Standby Time"), config.vixsettings.powermanager_standbytime))
				self.list.append(getConfigListEntry(_("Retry after cancel (mins)"), config.vixsettings.powermanager_standbyretry))
			self.list.append(getConfigListEntry(_("Enable Deep Standby"), config.vixsettings.powermanager_deepstandby))
			if config.vixsettings.powermanager_deepstandby.value:
				self.list.append(getConfigListEntry(_("Deep Standby Time"), config.vixsettings.powermanager_deepstandbytime))
				self.list.append(getConfigListEntry(_("Retry after cancel (mins)"), config.vixsettings.powermanager_deepstandbyretry))
			self.list.append(getConfigListEntry(_("Enable GUI Restart"), config.vixsettings.powermanager_guirestart))
			if config.vixsettings.powermanager_guirestart.value:
				self.list.append(getConfigListEntry(_("GUI Restart Time"), config.vixsettings.powermanager_guirestarttime))
				self.list.append(getConfigListEntry(_("Retry after cancel (mins)"), config.vixsettings.powermanager_guirestartretry))
			self.list.append(getConfigListEntry(_("Enable Reboot"), config.vixsettings.powermanager_reboot))
			if config.vixsettings.powermanager_reboot.value:
				self.list.append(getConfigListEntry(_("Reboot Time"), config.vixsettings.powermanager_reboottime))
				self.list.append(getConfigListEntry(_("Retry after cancel (mins)"), config.vixsettings.powermanager_rebootretry))
		self["config"].list = self.list
		self["config"].setList(self.list)
		if StandbyTime > 0:
			t = localtime(StandbyTime)
			standbytext = _("Next Standby: \n") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			standbytext = _("Next Standby: \n")
		self["standbystatus"].setText(str(standbytext))

		if DeepStandbyTime > 0:
			t = localtime(DeepStandbyTime)
			deepstandbytext = _("Next Deep Standby: \n") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			deepstandbytext = _("Next Deep Standby: \n")
		self["deepstandbystatus"].setText(str(deepstandbytext))

		if GuiRestartTime > 0:
			t = localtime(GuiRestartTime)
			guirestarttext = _("Next GUI Restart: \n") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			guirestarttext = _("Next GUI Restart: \n")
		self["guirestartstatus"].setText(str(guirestarttext))

		if RebootTime > 0:
			t = localtime(RebootTime)
			reboottext = _("Next Reboot: \n") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			reboottext = _("Next Reboot: \n")
		self["rebootstatus"].setText(str(reboottext))

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		print "current selection:", self["config"].l.getCurrentSelection()
		self.createSetup()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		print "current selection:", self["config"].l.getCurrentSelection()
		self.createSetup()

	def doneConfiguring(self):
		now = int(time())
		if config.vixsettings.powermanager.value:
			if config.vixsettings.powermanager_standby.value:
				if autoPowerManagerTimer is not None:
					print "[PowerManager] Standby Enabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.standbyupdate()
			else:
				if autoPowerManagerTimer is not None:
					global StandbyTime
					StandbyTime = 0
					print "[PowerManager] Standby Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.standbystop()

			if config.vixsettings.powermanager_deepstandby.value:
				if autoPowerManagerTimer is not None:
					print "[PowerManager] Deep Standby Enabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.deepstandbyupdate()
			else:
				if autoPowerManagerTimer is not None:
					global DeepStandbyTime
					DeepStandbyTime = 0
					print "[PowerManager] Deep Standby Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.deepstandbystop()

			if config.vixsettings.powermanager_guirestart.value:
				if autoPowerManagerTimer is not None:
					print "[PowerManager] GUI Restart Enabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.guirestartupdate()
			else:
				if autoPowerManagerTimer is not None:
					global GuiRestartTime
					GuiRestartTime = 0
					print "[PowerManager] GUI Restart Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.guirestartstop()

			if config.vixsettings.powermanager_reboot.value:
				if autoPowerManagerTimer is not None:
					print "[PowerManager] Reboot Enabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.rebootupdate()
			else:
				if autoPowerManagerTimer is not None:
					global RebootTime
					RebootTime = 0
					print "[PowerManager] Reboot Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.rebootstop()
		else:
				if autoPowerManagerTimer is not None:
					global StandbyTime
					StandbyTime = 0
					print "[PowerManager] Standby Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.standbystop()

					global DeepStandbyTime
					DeepStandbyTime = 0
					print "[PowerManager] Deep Standby Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.deepstandbystop()

					global GuiRestartTime
					GuiRestartTime = 0
					print "[PowerManager] GUI Restart Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.guirestartstop()

					global RebootTime
					RebootTime = 0
					print "[PowerManager] Reboot Disabled at", strftime("%c", localtime(now))
					autoPowerManagerTimer.rebootstop()

	def keySaveNew(self):
		for x in self["config"].list:
			x[1].save()
		self.doneConfiguring()
		self.close()

class AutoPowerManagerTimer:
	def __init__(self, session):
		self.session = session
		self.standbytimer = eTimer()
		self.standbytimer.callback.append(self.StandbyonTimer)
		self.standbyactivityTimer = eTimer()
		self.standbyactivityTimer.timeout.get().append(self.standbyupdatedelay)
		self.deepstandbytimer = eTimer()
		self.deepstandbytimer.callback.append(self.DeepStandbyonTimer)
		self.deepstandbyactivityTimer = eTimer()
		self.deepstandbyactivityTimer.timeout.get().append(self.deepstandbyupdatedelay)
		self.guirestarttimer = eTimer()
		self.guirestarttimer.callback.append(self.GuiRestartonTimer)
		self.guirestartactivityTimer = eTimer()
		self.guirestartactivityTimer.timeout.get().append(self.guirestartupdatedelay)
		self.reboottimer = eTimer()
		self.reboottimer.callback.append(self.RebootonTimer)
		self.rebootactivityTimer = eTimer()
		self.rebootactivityTimer.timeout.get().append(self.rebootupdatedelay)
		now = int(time())
		global StandbyTime
		global DeepStandbyTime
		global GuiRestartTime
		global RebootTime
		if config.vixsettings.powermanager.value:
			if config.vixsettings.powermanager_standby.value:
				print "[PowerManager] Standby Enabled at ", strftime("%c", localtime(now))
				if now > 1262304000:
					self.standbyupdate()
				else:
					print "[PowerManager] Standby Time not yet set."
					StandbyTime = 0
					self.standbyactivityTimer.start(36000)
			else:
				StandbyTime = 0
				print "[PowerManager] Standby Disabled at", strftime("(now=%c)", localtime(now))
				self.standbyactivityTimer.stop()

			if config.vixsettings.powermanager_deepstandby.value:
				print "[PowerManager] DeepStandby Enabled at ", strftime("%c", localtime(now))
				if now > 1262304000:
					self.deepstandbyupdate()
				else:
					print "[PowerManager] DeepStandby Time not yet set."
					DeepStandbyTime = 0
					self.deepstandbyactivityTimer.start(36000)
			else:
				DeepStandbyTime = 0
				print "[PowerManager] DeepStandby Disabled at", strftime("(now=%c)", localtime(now))
				self.deepstandbyactivityTimer.stop()

			if config.vixsettings.powermanager_guirestart.value:
				print "[PowerManager] GUI Restart Enabled at ", strftime("%c", localtime(now))
				if now > 1262304000:
					self.guirestartupdate()
				else:
					print "[PowerManager] GUI Restart Time not yet set."
					GuiRestartTime = 0
					self.guirestartactivityTimer.start(36000)
			else:
				GuiRestartTime = 0
				print "[PowerManager] GUI Restart Disabled at", strftime("(now=%c)", localtime(now))
				self.guirestartactivityTimer.stop()

			if config.vixsettings.powermanager_reboot.value:
				print "[PowerManager] Reboot Enabled at ", strftime("%c", localtime(now))
				if now > 1262304000:
					self.rebootupdate()
				else:
					print "[PowerManager] Reboot Time not yet set."
					GuiRestartTime = 0
					self.rebootactivityTimer.start(36000)
			else:
				RebootTime = 0
				print "[PowerManager] Reboot Disabled at", strftime("(now=%c)", localtime(now))
				self.rebootactivityTimer.stop()
		else:
			StandbyTime = 0
			DeepStandbyTime = 0
			GuiRestartTime = 0
			RebootTime = 0

	def standbyupdatedelay(self):
		self.standbyactivityTimer.stop()
		self.standbyupdate()

	def getStandbyTime(self):
		standbyclock = config.vixsettings.powermanager_standbytime.value
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, standbyclock[0], standbyclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def standbyupdate(self, atLeast = 0):
		self.standbytimer.stop()
		global StandbyTime
		StandbyTime = self.getStandbyTime()
		now = int(time())
		if StandbyTime > 0:
			if StandbyTime < now + atLeast:
				StandbyTime += 24*3600
			next = StandbyTime - now
			self.standbytimer.startLongTimer(next)
		else:
		    	StandbyTime = -1
		print "[PowerManager] Standby Time set to", strftime("%c", localtime(StandbyTime)), strftime("(now=%c)", localtime(now))
		return StandbyTime

	def standbystop(self):
	    self.standbytimer.stop()

	def StandbyonTimer(self):
		self.standbytimer.stop()
		now = int(time())
		print "[PowerManager] Standby onTimer occured at", strftime("%c", localtime(now))
		from Screens.Standby import inStandby
		if not inStandby:
			message = _("Your STB_BOX is going for nightly standby,\ndo you want to allow this?")
			ybox = self.session.openWithCallback(self.doStandby, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
			ybox.setTitle(_("Standby"))
		else:
			print "[PowerManager] Already in Standby", strftime("%c", localtime(now))
			atLeast = 60
			self.standbyupdate(atLeast)

	def doStandby(self, answer):
		now = int(time())
		if answer is False:
			print "[PowerManager] Standby delayed."
			repeat = config.vixsettings.powermanager_standbyretrycount.value
			repeat += 1
			config.vixsettings.powermanager_standbyretrycount.value = repeat
			StandbyTime = now + (int(config.vixsettings.powermanager_standbyretry.value) * 60)
			print "[PowerManager] Standby Time now set to", strftime("%c", localtime(StandbyTime)), strftime("(now=%c)", localtime(now))
			self.standbytimer.startLongTimer(int(config.vixsettings.powermanager_standbyretry.value) * 60)
		else:
			atLeast = 60
			print "[PowerManager] Going to Standby occured at", strftime("%c", localtime(now))
			self.standbyupdate(atLeast)
			from Tools import Notifications
			Notifications.AddNotification(Standby)

	def deepstandbyupdatedelay(self):
		self.deepstandbyactivityTimer.stop()
		self.deepstandbyupdate()

	def getDeepStandbyTime(self):
		deepstandbyclock = config.vixsettings.powermanager_deepstandbytime.value
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, deepstandbyclock[0], deepstandbyclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def deepstandbyupdate(self, atLeast = 0):
		self.deepstandbytimer.stop()
		global DeepStandbyTime
		DeepStandbyTime = self.getDeepStandbyTime()
		now = int(time())
		if DeepStandbyTime > 0:
			if DeepStandbyTime < now + atLeast:
				DeepStandbyTime += 24*3600
			next = DeepStandbyTime - now
			self.deepstandbytimer.startLongTimer(next)
		else:
		    	DeepStandbyTime = -1
		print "[PowerManager] Deep Standby Time now set to", strftime("%c", localtime(DeepStandbyTime)), strftime("(now=%c)", localtime(now))
		return DeepStandbyTime

	def deepstandbystop(self):
	    self.deepstandbytimer.stop()

	def DeepStandbyonTimer(self):
		self.deepstandbytimer.stop()
		now = int(time())
		print "[PowerManager] DeepStandby onTimer occured at", strftime("%c", localtime(now))
		if self.session.nav.RecordTimer.isRecording() or abs(self.session.nav.RecordTimer.getNextRecordingTime() - time()) <= 900 or abs(self.session.nav.RecordTimer.getNextZapTime() - time()) <= 900:
			print "[PowerManager] A recording is in progress, can not go to Deep Standby try occured at", strftime("%c", localtime(now))
			repeat = config.vixsettings.powermanager_deepstandbyretrycount.value
			repeat += 1
			config.vixsettings.powermanager_deepstandbyretrycount.value = repeat
			DeepStandbyTime = now + (int(config.vixsettings.powermanager_deepstandbyretry.value) * 60)
			print "[PowerManager] Deep Standby Time now set to", strftime("%c", localtime(DeepStandbyTime)), strftime("(now=%c)", localtime(now))
			self.deepstandbytimer.startLongTimer(int(config.vixsettings.powermanager_deepstandbyretry.value) * 60)
		else:
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("Your STB_BOX is going for nightly shut-down,\ndo you want to allow this?")
				ybox = self.session.openWithCallback(self.doDeepStandby, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle(_("Shut-down."))
			else:
				self.doDeepStandby(answer=True)

	def doDeepStandby(self, answer):
		now = int(time())
		if answer is False:
			print "[PowerManager] DeepStandby delayed."
			repeat = config.vixsettings.powermanager_deepstandbyretrycount.value
			repeat += 1
			config.vixsettings.powermanager_deepstandbyretrycount.value = repeat
			DeepStandbyTime = now + (int(config.vixsettings.powermanager_deepstandbyretry.value) * 60)
			print "[PowerManager] Deep Standby Time now set to", strftime("%c", localtime(DeepStandbyTime)), strftime("(now=%c)", localtime(now))
			self.deepstandbytimer.startLongTimer(int(config.vixsettings.powermanager_deepstandbyretry.value) * 60)
		else:
			atLeast = 60
			print "[PowerManager] Going to Deep Standby occured at", strftime("%c", localtime(now))
			self.deepstandbyupdate(atLeast)
			from Screens.Standby import TryQuitMainloop
			self.session.open(TryQuitMainloop, 1)

	def guirestartupdatedelay(self):
		self.guirestartactivityTimer.stop()
		self.guirestartupdate()

	def getGuiRestartTime(self):
		guirestartclock = config.vixsettings.powermanager_guirestarttime.value
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, guirestartclock[0], guirestartclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def guirestartupdate(self, atLeast = 0):
		self.guirestarttimer.stop()
		global GuiRestartTime
		GuiRestartTime = self.getGuiRestartTime()
		now = int(time())
		if GuiRestartTime > 0:
			if GuiRestartTime < now + atLeast:
				GuiRestartTime += 24*3600
			next = GuiRestartTime - now
			self.guirestarttimer.startLongTimer(next)
		else:
		    	GuiRestartTime = -1
		print "[PowerManager] GuiRestart Time set to", strftime("%c", localtime(GuiRestartTime)), strftime("(now=%c)", localtime(now))
		return GuiRestartTime

	def guirestartstop(self):
	    self.guirestarttimer.stop()

	def GuiRestartonTimer(self):
		self.guirestarttimer.stop()
		now = int(time())
		print "[PowerManager] GuiRestart onTimer occured at", strftime("%c", localtime(now))
		if self.session.nav.RecordTimer.isRecording() or abs(self.session.nav.RecordTimer.getNextRecordingTime() - time()) <= 900 or abs(self.session.nav.RecordTimer.getNextZapTime() - time()) <= 900:
			repeat = config.vixsettings.powermanager_guirestartretrycount.value
			repeat += 1
			config.vixsettings.powermanager_guirestartretrycount.value = repeat
			GuiRestartTime = now + (int(config.vixsettings.powermanager_guirestartretry.value) * 60)
			print "[PowerManager] Gui Restart Time now set to", strftime("%c", localtime(GuiRestartTime)), strftime("(now=%c)", localtime(now))
			self.guirestarttimer.startLongTimer(int(config.vixsettings.powermanager_guirestartretry.value) * 60)
		else:
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("Your STB_BOX is going for nightly GUI Restart,\ndo you want to allow this?")
				ybox = self.session.openWithCallback(self.doGuiRestart, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle(_("Restart Enigma2."))
			else:
				self.doGuiRestart(answer=True)

	def doGuiRestart(self, answer):
		now = int(time())
		if answer is False:
			print "[PowerManager] GuiRestart delayed."
			repeat = config.vixsettings.powermanager_guirestartretrycount.value
			repeat += 1
			config.vixsettings.powermanager_guirestartretrycount.value = repeat
			GuiRestartTime = now + (int(config.vixsettings.powermanager_guirestartretry.value) * 60)
			print "[PowerManager] Gui Restart Time now set to", strftime("%c", localtime(GuiRestartTime)), strftime("(now=%c)", localtime(now))
			self.guirestarttimer.startLongTimer(int(config.vixsettings.powermanager_guirestartretry.value) * 60)
		else:
			atLeast = 60
			print "[PowerManager] Gui Restart occured at", strftime("%c", localtime(now))
			self.guirestartupdate(atLeast)
			from Screens.Standby import TryQuitMainloop
			self.session.open(TryQuitMainloop, 3)


	def rebootupdatedelay(self):
		self.rebootactivityTimer.stop()
		self.rebootupdate()

	def getRebootTime(self):
		rebootclock = config.vixsettings.powermanager_reboottime.value
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, rebootclock[0], rebootclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def rebootupdate(self, atLeast = 0):
		self.reboottimer.stop()
		global RebootTime
		RebootTime = self.getRebootTime()
		now = int(time())
		if RebootTime > 0:
			if RebootTime < now + atLeast:
				RebootTime += 24*3600
			next = RebootTime - now
			self.reboottimer.startLongTimer(next)
		else:
			RebootTime = -1
		print "[PowerManager] Reboot Time set to", strftime("%c", localtime(RebootTime)), strftime("(now=%c)", localtime(now))
		return RebootTime

	def rebootstop(self):
	    self.reboottimer.stop()

	def RebootonTimer(self):
		self.reboottimer.stop()
		now = int(time())
		print "[PowerManager] Reboot onTimer occured at", strftime("%c", localtime(now))
		if self.session.nav.RecordTimer.isRecording() or abs(self.session.nav.RecordTimer.getNextRecordingTime() - time()) <= 900 or abs(self.session.nav.RecordTimer.getNextZapTime() - time()) <= 900:
			repeat = config.vixsettings.powermanager_rebootretrycount.value
			repeat += 1
			config.vixsettings.powermanager_rebootretrycount.value = repeat
			RebootTime = now + (int(config.vixsettings.powermanager_rebootretry.value) * 60)
			print "[PowerManager] Reboot Time now set to", strftime("%c", localtime(RebootTime)), strftime("(now=%c)", localtime(now))
			self.reboottimer.startLongTimer(int(config.vixsettings.powermanager_rebootretry.value) * 60)
		else:
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("Your STB_BOX is going for a nightly Reboot,\ndo you want to allow this?")
				ybox = self.session.openWithCallback(self.doReboot, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle(_("Reboot"))
			else:
				self.doReboot(answer=True)

	def doReboot(self, answer):
		now = int(time())
		if answer is False:
			print "[PowerManager] Reboot delayed."
			repeat = config.vixsettings.powermanager_rebootretrycount.value
			repeat += 1
			config.vixsettings.powermanager_rebootretrycount.value = repeat
			RebootTime = now + (int(config.vixsettings.powermanager_rebootretry.value) * 60)
			print "[PowerManager] Reboot Time now set to", strftime("%c", localtime(RebootTime)), strftime("(now=%c)", localtime(now))
			self.reboottimer.startLongTimer(int(config.vixsettings.powermanager_rebootretry.value) * 60)
		else:
			atLeast = 60
			print "[PowerManager] Reboot occured at", strftime("%c", localtime(now))
			self.rebootupdate(atLeast)
			from Screens.Standby import TryQuitMainloop
			self.session.open(TryQuitMainloop, 2)

