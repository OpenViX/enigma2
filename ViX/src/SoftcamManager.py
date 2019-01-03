# for localized messages
import re
from os import path, makedirs, remove, rename, symlink, mkdir, listdir
from datetime import datetime
from time import time, sleep

from enigma import eTimer

from . import _, PluginLanguageDomain
import Components.Task
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.ScrollLabel import ScrollLabel
from Components.Pixmap import MultiPixmap
from Components.config import configfile, config, ConfigSubsection, ConfigYesNo, ConfigNumber, ConfigLocations
from Components.Console import Console
from Components.FileList import MultiFileSelectList
from Components.PluginComponent import plugins
from Components.Sources.StaticText import StaticText
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.SystemInfo import SystemInfo


config.softcammanager = ConfigSubsection()
config.softcammanager.softcams_autostart = ConfigLocations(default='')
config.softcammanager.softcamtimerenabled = ConfigYesNo(default=True)
config.softcammanager.softcamtimer = ConfigNumber(default=6)
config.softcammanager.showinextensions = ConfigYesNo(default=True)

softcamautopoller = None


def updateExtensions(configElement):
	plugins.clearPluginList()
	plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
config.softcammanager.showinextensions.addNotifier(updateExtensions, initial_call=False)


def SoftcamAutostart(reason, session=None, **kwargs):
	"""called with reason=1 to during shutdown, with reason=0 at startup?"""
	global softcamautopoller
	if reason == 0:
		print "[SoftcamManager] AutoStart Enabled"
		if path.exists('/tmp/SoftcamsDisableCheck'):
			remove('/tmp/SoftcamsDisableCheck')
		softcamautopoller = SoftcamAutoPoller()
		softcamautopoller.start()
	elif reason == 1:
		# Stop Poller
		if softcamautopoller is not None:
			softcamautopoller.stop()
			softcamautopoller = None

class VIXSoftcamManager(Screen):
	skin = """
	<screen name="VIXSoftcamManager" position="center,center" size="560,400">
		<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="lab1" position="40,60" size="170,20" font="Regular; 22" halign="right" zPosition="2" transparent="0"/>
		<widget name="list" position="225,60" size="240,100" transparent="0" scrollbarMode="showOnDemand"/>
		<widget name="lab2" position="40,165" size="170,30" font="Regular; 22" halign="right" zPosition="2" transparent="0"/>
		<widget name="activecam" position="225,166" size="240,100" font="Regular; 20" halign="left" zPosition="2" transparent="0" noWrap="1"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(25)
		</applet>
	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		screentitle =  _("Softcam manager")
		self.menu_path = _('Main menu')+' / '+_('Setup')+' / '+_('Softcam')+' / '
		if config.usage.show_menupath.value == 'large':
			self.menu_path += screentitle
			title = self.menu_path
			self["menu_path_compressed"] = StaticText("")
			self.menu_path += ' / '
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(self.menu_path + " >" if not self.menu_path.endswith(' / ') else self.menu_path[:-3] + " >" or "")
			self.menu_path += " / " + screentitle
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self['lab1'] = Label(_('Select:'))
		self['lab2'] = Label(_('Active:'))
		self['activecam'] = Label()
		self.onChangedEntry = []

		self.sentsingle = ""
		self.selectedFiles = config.softcammanager.softcams_autostart.value
		self.defaultDir = '/usr/softcams/'
		self.emlist = MultiFileSelectList(self.selectedFiles, self.defaultDir, showDirectories=False)
		self["list"] = self.emlist

		self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "TimerEditActions", "MenuActions"],
									  {
									  'ok': self.keyStart,
									  'cancel': self.close,
									  'red': self.close,
									  'green': self.keyStart,
									  'yellow': self.getRestartPID,
									  'blue': self.changeSelectionState,
									  'log': self.showLog,
									  'menu': self.createSetup,
									  }, -1)

		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button("")
		self["key_yellow"] = Button("")
		self["key_blue"] = Button(_("Autostart"))

		self.currentactivecam = ""
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.getActivecam)
		self.Console = Console()
		self.showActivecam()
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def createSetup(self):
		from Screens.Setup import Setup
		self.session.open(Setup, 'vixsoftcammanager', 'SystemPlugins/ViX', self.menu_path, PluginLanguageDomain)

	def selectionChanged(self):
		cams = []
		if path.exists('/usr/softcams/'):
			cams = listdir('/usr/softcams')
		SystemInfo["CCcamInstalled"] = False
		SystemInfo["OScamInstalled"] = False
		for softcam in cams:
			if softcam.lower().startswith('cccam'):
				SystemInfo["CCcamInstalled"] = True
			elif softcam.lower().startswith('oscam'):
				SystemInfo["OScamInstalled"] = True
		selcam = ''
		if cams:
			current = self["list"].getCurrent()[0]
			selcam = current[0]
			print '[SoftcamManager] Selectedcam: ' + str(selcam)
			if self.currentactivecam.find(selcam) < 0:
				self["key_green"].setText(_("Start"))
			else:
				self["key_green"].setText(_("Stop"))
			if self.currentactivecam.find(selcam) < 0:
				self["key_yellow"].setText(" ")
			else:
				self["key_yellow"].setText(_("Restart"))

			if current[2] is True:
				self["key_blue"].setText(_("Disable startup"))
			else:
				self["key_blue"].setText(_("Enable startup"))
			self.saveSelection()
		desc = _('Active:') + ' ' + self['activecam'].text
		for cb in self.onChangedEntry:
			cb(selcam, desc)

	def changeSelectionState(self):
		cams = []
		if path.exists('/usr/softcams/'):
			cams = listdir('/usr/softcams')
		if cams:
			self["list"].changeSelectionState()
			self.selectedFiles = self["list"].getSelectedList()

	def saveSelection(self):
		self.selectedFiles = self["list"].getSelectedList()
		config.softcammanager.softcams_autostart.value = self.selectedFiles
		config.softcammanager.softcams_autostart.save()
		configfile.save()

	def showActivecam(self):
		scanning = _("Wait please while scanning\nfor softcam's...")
		self['activecam'].setText(scanning)
		self.activityTimer.start(10)

	def getActivecam(self):
		self.activityTimer.stop()
		active = []
		for x in self["list"].list:
			active.append(x[0][0])
		activelist = ",".join(active)
		if activelist:
			self.Console.ePopen("ps.procps -C " + activelist + " | grep -v 'CMD' | sed 's/</ /g' | awk '{print $4}' | awk '{a[$1] = $0} END { for (x in a) { print a[x] } }'", self.showActivecam2)
		else:
			self['activecam'].setText('')
			self['activecam'].show()
		# self.Console.ePopen("ps.procps | grep softcams | grep -v 'grep' | sed 's/</ /g' | awk '{print $5}' | awk '{a[$1] = $0} END { for (x in a) { print a[x] } }' | awk -F'[/]' '{print $4}'", self.showActivecam2)

	def showActivecam2(self, result, retval, extra_args):
		if retval == 0:
			self.currentactivecamtemp = result
			self.currentactivecam = "".join([s for s in self.currentactivecamtemp.splitlines(True) if s.strip("\r\n")])
			self.currentactivecam = self.currentactivecam.replace('\n', ', ')
			print '[SoftcamManager] Active: ' + self.currentactivecam.replace("\n", ", ")
			if path.exists('/tmp/SoftcamsScriptsRunning'):
				file = open('/tmp/SoftcamsScriptsRunning')
				SoftcamsScriptsRunning = file.read()
				file.close()
				SoftcamsScriptsRunning = SoftcamsScriptsRunning.replace('\n', ', ')
				self.currentactivecam += SoftcamsScriptsRunning
			self['activecam'].setText(self.currentactivecam)
			self['activecam'].show()
		else:
			print '[SoftcamManager] RESULT FAILED: ' + str(result)
		self.selectionChanged()

	def keyStart(self):
		cams = []
		if path.exists('/usr/softcams/'):
			cams = listdir('/usr/softcams')
		if cams:
			self.sel = self['list'].getCurrent()[0]
			selcam = self.sel[0]
			if self.currentactivecam.find(selcam) < 0:
				if selcam.lower().startswith('cccam'):
					if not path.exists('/etc/CCcam.cfg'):
						self.session.open(MessageBox, _("No config files found, please setup CCcam first\nin /etc/CCcam.cfg."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
					else:
						if self.currentactivecam.lower().find('mgcam') < 0:
							self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
						else:
							self.session.open(MessageBox, _("CCcam can't run whilst MGcamd is running"), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
				elif selcam.lower().startswith('hypercam'):
					if not path.exists('/etc/hypercam.cfg'):
						self.session.open(MessageBox, _("No config files found, please setup Hypercam first\nin /etc/hypercam.cfg."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
					else:
						self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				elif selcam.lower().startswith('oscam'):
					if not path.exists('/etc/tuxbox/config/oscam.conf') and not path.exists('/etc/tuxbox/config/oscam/oscam.conf'):
						self.session.open(MessageBox, _("No config files found, please setup Oscam first\nin /etc/tuxbox/config or in /etc/tuxbox/config/oscam."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
					else:
						self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				elif selcam.lower().startswith('mgcam'):
					if not path.exists('/var/keys/mg_cfg'):
						if self.currentactivecam.lower().find('cccam') < 0:
							self.session.open(MessageBox, _("No config files found, please setup MGcamd first\nin /usr/keys."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
						else:
							self.session.open(MessageBox, _("MGcamd can't run whilst CCcam is running."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
					else:
						self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				elif selcam.lower().startswith('scam'):
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				else:
					self.session.open(MessageBox, _("Found non-standard softcam, trying to start, this may fail."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
			else:
				self.session.openWithCallback(self.showActivecam, VIXStopCam, self.sel[0])

	def getRestartPID(self):
		cams = []
		if path.exists('/usr/softcams/'):
			cams = listdir('/usr/softcams')
		if cams:
			self.sel = self['list'].getCurrent()[0]
			selectedcam = self.sel[0]
			self.Console.ePopen("pidof " + selectedcam, self.keyRestart, selectedcam)

	def keyRestart(self, result, retval, extra_args):
		selectedcam = extra_args
		strpos = self.currentactivecam.find(selectedcam)
		if strpos < 0:
			return
		else:
			if retval == 0:
				stopcam = str(result)
				print '[SoftcamManager] Stopping ' + selectedcam + ' PID ' + stopcam.replace("\n", "")
				output = open('/tmp/cam.check.log', 'a')
				now = datetime.now()
				output.write(now.strftime("%Y-%m-%d %H:%M") + ": Stopping: " + selectedcam + "\n")
				output.close()
				self.Console.ePopen("kill -9 " + stopcam.replace("\n", ""))
				sleep(4)
			else:
				print '[SoftcamManager] RESULT FAILED: ' + str(result)
			if selectedcam.lower().startswith('cccam') and path.exists('/etc/CCcam.cfg') == True:
				if self.currentactivecam.lower().find('mgcam') < 0:
					self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
				else:
					self.session.open(MessageBox, _("CCcam can't run whilst MGcamd is running."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
			elif selectedcam.lower().startswith('cccam') and path.exists('/etc/CCcam.cfg') == False:
				self.session.open(MessageBox, _("No config files found, please setup CCcam first\nin /etc/CCcam.cfg."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
			elif selectedcam.lower().startswith('oscam') and path.exists('/etc/tuxbox/config/oscam.conf') == True:
				self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
			elif selectedcam.lower().startswith('oscam') and path.exists('/etc/tuxbox/config/oscam.conf') == False:
				if not path.exists('/etc/tuxbox/config'):
					makedirs('/etc/tuxbox/config')
				self.session.open(MessageBox, _("No config files found, please setup Oscam first\nin /etc/tuxbox/config."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
			elif selectedcam.lower().startswith('mgcam') and path.exists('/var/keys/mg_cfg') == True:
				self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
			elif selectedcam.lower().startswith('mgcam') and path.exists('/var/keys/mg_cfg') == False:
				if self.currentactivecam.lower().find('cccam') < 0:
					self.session.open(MessageBox, _("No config files found, please setup MGcamd first\nin /usr/keys."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
				else:
					self.session.open(MessageBox, _("MGcamd can't run whilst CCcam is running."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
			elif selectedcam.lower().startswith('scam'):
				self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])
			elif not selectedcam.lower().startswith('cccam') or selectedcam.lower().startswith('oscam') or selectedcam.lower().startswith('mgcamd'):
				self.session.open(MessageBox, _("Found non-standard softcam, trying to start, this may fail."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
				self.session.openWithCallback(self.showActivecam, VIXStartCam, self.sel[0])

	def showLog(self):
		self.session.open(VIXSoftcamLog, self.menu_path)

	def myclose(self):
		self.close()

class VIXStartCam(Screen):
	skin = """
	<screen name="VIXStartCam" position="center,center" size="484, 150" title="Starting Softcam">
		<widget name="connect" position="217, 0" size="64,64" zPosition="2" pixmaps="ViX_HD_Common/busy/busy1.png,ViX_HD_Common/busy/busy2.png,ViX_HD_Common/busy/busy3.png,ViX_HD_Common/busy/busy4.png,ViX_HD_Common/busy/busy5.png,ViX_HD_Common/busy/busy6.png,ViX_HD_Common/busy/busy7.png,ViX_HD_Common/busy/busy8.png,ViX_HD_Common/busy/busy9.png,ViX_HD_Common/busy/busy9.png,ViX_HD_Common/busy/busy10.png,ViX_HD_Common/busy/busy11.png,ViX_HD_Common/busy/busy12.png,ViX_HD_Common/busy/busy13.png,ViX_HD_Common/busy/busy14.png,ViX_HD_Common/busy/busy15.png,ViX_HD_Common/busy/busy17.png,ViX_HD_Common/busy/busy18.png,ViX_HD_Common/busy/busy19.png,ViX_HD_Common/busy/busy20.png,ViX_HD_Common/busy/busy21.png,ViX_HD_Common/busy/busy22.png,ViX_HD_Common/busy/busy23.png,ViX_HD_Common/busy/busy24.png"  transparent="1" alphatest="blend"/>
		<widget name="lab1" position="10, 80" halign="center" size="460, 60" zPosition="1" font="Regular;20" valign="top" transparent="1"/>
	</screen>"""

	def __init__(self, session, selectedcam):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Softcam starting..."))
		self['connect'] = MultiPixmap()
		self['lab1'] = Label(_("Please wait while starting\n") + selectedcam + '...')
		global startselectedcam
		startselectedcam = selectedcam
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updatepix)
		self.onShow.append(self.startShow)
		self.onClose.append(self.delTimer)

	def startShow(self):
		self.curpix = 0
		self.count = 0
		self['connect'].setPixmapNum(0)
		if startselectedcam.endswith('.sh'):
			if path.exists('/tmp/SoftcamsScriptsRunning'):
				file = open('/tmp/SoftcamsScriptsRunning')
				data = file.read()
				file.close()
				if data.find(startselectedcam) >= 0:
					filewrite = open('/tmp/SoftcamsScriptsRunning.tmp', 'w')
					fileread = open('/tmp/SoftcamsScriptsRunning')
					filewrite.writelines([l for l in fileread.readlines() if startselectedcam not in l])
					fileread.close()
					filewrite.close()
					rename('/tmp/SoftcamsScriptsRunning.tmp', '/tmp/SoftcamsScriptsRunning')
				elif data.find(startselectedcam) < 0:
					fileout = open('/tmp/SoftcamsScriptsRunning', 'a')
					line = startselectedcam + '\n'
					fileout.write(line)
					fileout.close()
			else:
				fileout = open('/tmp/SoftcamsScriptsRunning', 'w')
				line = startselectedcam + '\n'
				fileout.write(line)
				fileout.close()
			print '[SoftcamManager] Starting ' + startselectedcam
			output = open('/tmp/cam.check.log', 'a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Starting " + startselectedcam + "\n")
			output.close()
			self.Console.ePopen('/usr/softcams/' + startselectedcam + ' start')
		else:
			if path.exists('/tmp/SoftcamsDisableCheck'):
				file = open('/tmp/SoftcamsDisableCheck')
				data = file.read()
				file.close()
				if data.find(startselectedcam) >= 0:
					output = open('/tmp/cam.check.log', 'a')
					now = datetime.now()
					output.write(now.strftime("%Y-%m-%d %H:%M") + ": Initialised timed check for " + stopselectedcam + "\n")
					output.close()
					fileread = open('/tmp/SoftcamsDisableCheck')
					filewrite = open('/tmp/SoftcamsDisableCheck.tmp', 'w')
					filewrite.writelines([l for l in fileread.readlines() if startselectedcam not in l])
					fileread.close()
					filewrite.close()
					rename('/tmp/SoftcamsDisableCheck.tmp', '/tmp/SoftcamsDisableCheck')
			print '[SoftcamManager] Starting ' + startselectedcam
			output = open('/tmp/cam.check.log', 'a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Starting " + startselectedcam + "\n")
			output.close()
			if startselectedcam.lower().startswith('hypercam'):
				self.Console.ePopen('ulimit -s 512;/usr/softcams/' + startselectedcam + ' -c /etc/hypercam.cfg')
			elif startselectedcam.lower().startswith('oscam'):
				self.Console.ePopen('ulimit -s 512;/usr/softcams/' + startselectedcam + ' -b')
			elif startselectedcam.lower().startswith('gbox'):
				self.Console.ePopen('ulimit -s 512;/usr/softcams/' + startselectedcam)
				sleep(3)
				self.Console.ePopen('start-stop-daemon --start --quiet --background --exec /usr/bin/gbox')
			else:
				self.Console.ePopen('ulimit -s 512;/usr/softcams/' + startselectedcam)
		self.activityTimer.start(1)

	def updatepix(self):
		self.activityTimer.stop()
		if startselectedcam.lower().startswith('cccam'):
			if self.curpix > 23:
				self.curpix = 0
			if self.count > 120:
				self.curpix = 23
			self['connect'].setPixmapNum(self.curpix)
			if self.count == 120:  # timer on screen
				self.hide()
				self.close()
			self.activityTimer.start(120)  # cycle speed
			self.curpix += 1
			self.count += 1
		else:
			if self.curpix > 23:
				self.curpix = 0
			if self.count > 23:
				self.curpix = 0
			self['connect'].setPixmapNum(self.curpix)
			if self.count == 25:  # timer on screen
				self.hide()
				self.close()
			self.activityTimer.start(120)  # cycle speed
			self.curpix += 1
			self.count += 1

	def delTimer(self):
		del self.activityTimer

class VIXStopCam(Screen):
	skin = """
	<screen name="VIXStopCam" position="center,center" size="484, 150">
		<widget name="connect" position="217, 0" size="64,64" zPosition="2" pixmaps="ViX_HD_Common/busy/busy1.png,ViX_HD_Common/busy/busy2.png,ViX_HD_Common/busy/busy3.png,ViX_HD_Common/busy/busy4.png,ViX_HD_Common/busy/busy5.png,ViX_HD_Common/busy/busy6.png,ViX_HD_Common/busy/busy7.png,ViX_HD_Common/busy/busy8.png,ViX_HD_Common/busy/busy9.png,ViX_HD_Common/busy/busy9.png,ViX_HD_Common/busy/busy10.png,ViX_HD_Common/busy/busy11.png,ViX_HD_Common/busy/busy12.png,ViX_HD_Common/busy/busy13.png,ViX_HD_Common/busy/busy14.png,ViX_HD_Common/busy/busy15.png,ViX_HD_Common/busy/busy17.png,ViX_HD_Common/busy/busy18.png,ViX_HD_Common/busy/busy19.png,ViX_HD_Common/busy/busy20.png,ViX_HD_Common/busy/busy21.png,ViX_HD_Common/busy/busy22.png,ViX_HD_Common/busy/busy23.png,ViX_HD_Common/busy/busy24.png"  transparent="1" alphatest="blend"/>
		<widget name="lab1" position="10, 80" halign="center" size="460, 60" zPosition="1" font="Regular;20" valign="top" transparent="1"/>
	</screen>"""

	def __init__(self, session, selectedcam):
		Screen.__init__(self, session)
		global stopselectedcam
		stopselectedcam = selectedcam
		Screen.setTitle(self, _("Softcam stopping..."))
		self['connect'] = MultiPixmap()
		self['lab1'] = Label(_("Please wait while stopping\n") + selectedcam + '...')
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updatepix)
		self.onShow.append(self.getStopPID)
		self.onClose.append(self.delTimer)

	def getStopPID(self):
		if stopselectedcam.endswith('.sh'):
			self.curpix = 0
			self.count = 0
			self['connect'].setPixmapNum(0)
			print '[SoftcamManager] Stopping ' + stopselectedcam
			output = open('/tmp/cam.check.log', 'a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Stopping " + stopselectedcam + "\n")
			output.close()
			self.Console.ePopen('/usr/softcams/' + stopselectedcam + ' stop')
			if path.exists('/tmp/SoftcamsScriptsRunning'):
				remove('/tmp/SoftcamsScriptsRunning')
			if path.exists('/etc/SoftcamsAutostart'):
				file = open('/etc/SoftcamsAutostart')
				data = file.read()
				file.close()
				finddata = data.find(stopselectedcam)
				if data.find(stopselectedcam) >= 0:
					print '[SoftcamManager] Temporarily disabled timed check for ' + stopselectedcam
					output = open('/tmp/cam.check.log', 'a')
					now = datetime.now()
					output.write(now.strftime("%Y-%m-%d %H:%M") + ": Temporarily disabled timed check for " + stopselectedcam + "\n")
					output.close()
					fileout = open('/tmp/SoftcamsDisableCheck', 'a')
					line = stopselectedcam + '\n'
					fileout.write(line)
					fileout.close()
			self.activityTimer.start(1)
		else:
			self.Console.ePopen("pidof " + stopselectedcam, self.startShow)

	def startShow(self, result, retval, extra_args):
		if retval == 0:
			self.curpix = 0
			self.count = 0
			self['connect'].setPixmapNum(0)
			stopcam = str(result)
			if path.exists('/etc/SoftcamsAutostart'):
				file = open('/etc/SoftcamsAutostart')
				data = file.read()
				file.close()
				finddata = data.find(stopselectedcam)
				if data.find(stopselectedcam) >= 0:
					print '[SoftcamManager] Temporarily disabled timed check for ' + stopselectedcam
					output = open('/tmp/cam.check.log', 'a')
					now = datetime.now()
					output.write(now.strftime("%Y-%m-%d %H:%M") + ": Temporarily disabled timed check for " + stopselectedcam + "\n")
					output.close()
					fileout = open('/tmp/SoftcamsDisableCheck', 'a')
					line = stopselectedcam + '\n'
					fileout.write(line)
					fileout.close()
			print '[SoftcamManager] Stopping ' + stopselectedcam + ' PID ' + stopcam.replace("\n", "")
			output = open('/tmp/cam.check.log', 'a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Stopping " + stopselectedcam + "\n")
			output.close()
			self.Console.ePopen("kill -9 " + stopcam.replace("\n", ""))
			self.activityTimer.start(1)

	def updatepix(self):
		self.activityTimer.stop()
		if self.curpix > 23:
			self.curpix = 0
		if self.count > 23:
			self.curpix = 0
		self['connect'].setPixmapNum(self.curpix)
		if self.count == 25:  # timer on screen
			self.hide()
			self.close()
		self.activityTimer.start(120)  # cycle speed
		self.curpix += 1
		self.count += 1

	def delTimer(self):
		del self.activityTimer

class VIXSoftcamLog(Screen):
	skin = """
<screen name="VIXSoftcamLog" position="center,center" size="560,400">
	<widget name="list" position="0,0" size="560,400" font="Regular;14"/>
</screen>"""

	def __init__(self, session, menu_path):
		self.session = session
		Screen.__init__(self, session)
		screentitle =  _("Logs")
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
		Screen.setTitle(self, title)

		if path.exists('/var/volatile/tmp/cam.check.log'):
			file = open('/var/volatile/tmp/cam.check.log')
			softcamlog = file.read()
			file.close()
		else:
			softcamlog = ""
		self["list"] = ScrollLabel(str(softcamlog))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions", "DirectionActions"],
										 {
										 "cancel": self.cancel,
										 "ok": self.cancel,
										 "up": self["list"].pageUp,
										 "down": self["list"].pageDown
										 }, -2)

	def cancel(self):
		self.close()

class SoftcamAutoPoller:
	"""Automatically Poll SoftCam"""

	def __init__(self):
		# Init Timer
		if not path.exists('/usr/softcams'):
			mkdir('/usr/softcams', 0755)
		if not path.exists('/etc/scce'):
			mkdir('/etc/scce', 0755)
		if not path.exists('/etc/tuxbox/config'):
			mkdir('/etc/tuxbox/config', 0755)
		if not path.islink('/var/tuxbox'):
			symlink('/etc/tuxbox', '/var/tuxbox')
		if not path.exists('/usr/keys'):
			mkdir('/usr/keys', 0755)
		if not path.islink('/var/keys'):
			symlink('/usr/keys', '/var/keys')
		if not path.islink('/etc/keys'):
			symlink('/usr/keys', '/etc/keys')
		if not path.islink('/var/scce'):
			symlink('/etc/scce', '/var/scce')
		self.timer = eTimer()

	def start(self):
		if self.softcam_check not in self.timer.callback:
			self.timer.callback.append(self.softcam_check)
		self.timer.startLongTimer(10)

	def stop(self):
		if self.softcam_check in self.timer.callback:
			self.timer.callback.remove(self.softcam_check)
		self.timer.stop()

	def softcam_check(self):
		now = int(time())
		if path.exists('/tmp/SoftcamRuningCheck.tmp'):
			remove('/tmp/SoftcamRuningCheck.tmp')

		if config.softcammanager.softcams_autostart:
			Components.Task.job_manager.AddJob(self.createCheckJob())

		if config.softcammanager.softcamtimerenabled.value:
			# 			print "[SoftcamManager] Timer Check Enabled"
			output = open('/tmp/cam.check.log', 'a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Timer Check Enabled\n")
			output.close()
			self.timer.startLongTimer(config.softcammanager.softcamtimer.value * 60)
		else:
			output = open('/tmp/cam.check.log', 'a')
			now = datetime.now()
			output.write(now.strftime("%Y-%m-%d %H:%M") + ": Timer Check Disabled\n")
			output.close()
			# 			print "[SoftcamManager] Timer Check Disabled"
			softcamautopoller.stop()

	def createCheckJob(self):
		job = Components.Task.Job(_("SoftcamCheck"))

		task = Components.Task.PythonTask(job, _("Checking softcams..."))
		task.work = self.JobStart
		task.weighting = 1

		return job

	def JobStart(self):
		self.autostartcams = config.softcammanager.softcams_autostart.value
		self.Console = Console()
		if path.exists('/tmp/cam.check.log'):
			if path.getsize('/tmp/cam.check.log') > 40000:
				fh = open('/tmp/cam.check.log', 'rb+')
				fh.seek(-40000, 2)
				data = fh.read()
				fh.seek(0)  # rewind
				fh.write(data)
				fh.truncate()
				fh.close()

		if path.exists('/etc/CCcam.cfg'):
			f = open('/etc/CCcam.cfg', 'r')
			logwarn = ""
			for line in f.readlines():
				if line.find('LOG WARNINGS') != -1:
					parts = line.strip().split()
					logwarn = parts[2]
					if logwarn.find(':') >= 0:
						logwarn = logwarn.replace(':', '')
					if logwarn == '':
						logwarn = parts[3]
				else:
					logwarn = ""
			if path.exists(logwarn):
				if path.getsize(logwarn) > 40000:
					fh = open(logwarn, 'rb+')
					fh.seek(-40000, 2)
					data = fh.read()
					fh.seek(0)  # rewind
					fh.write(data)
					fh.truncate()
					fh.close()
			f.close()

		for softcamcheck in self.autostartcams:
			softcamcheck = softcamcheck.replace("/usr/softcams/", "")
			softcamcheck = softcamcheck.replace("\n", "")
			if softcamcheck.endswith('.sh'):
				if path.exists('/tmp/SoftcamsDisableCheck'):
					file = open('/tmp/SoftcamsDisableCheck')
					data = file.read()
					file.close()
				else:
					data = ''
				if data.find(softcamcheck) < 0:
					if path.exists('/tmp/SoftcamsScriptsRunning'):
						file = open('/tmp/SoftcamsScriptsRunning')
						data = file.read()
						file.close()
						if data.find(softcamcheck) < 0:
							fileout = open('/tmp/SoftcamsScriptsRunning', 'a')
							line = softcamcheck + '\n'
							fileout.write(line)
							fileout.close()
							print '[SoftcamManager] Starting ' + softcamcheck
							self.Console.ePopen('/usr/softcams/' + softcamcheck + ' start')
					else:
						fileout = open('/tmp/SoftcamsScriptsRunning', 'w')
						line = softcamcheck + '\n'
						fileout.write(line)
						fileout.close()
						print '[SoftcamManager] Starting ' + softcamcheck
						self.Console.ePopen('/usr/softcams/' + softcamcheck + ' start')
			else:
				if path.exists('/tmp/SoftcamsDisableCheck'):
					file = open('/tmp/SoftcamsDisableCheck')
					data = file.read()
					file.close()
				else:
					data = ''
				if data.find(softcamcheck) < 0:
					import process

					p = process.ProcessList()
					softcamcheck_process = str(p.named(softcamcheck)).strip('[]')
					if softcamcheck_process != "":
						if path.exists('/tmp/frozen'):
							remove('/tmp/frozen')
						if path.exists('/tmp/status.html'):
							remove('/tmp/status.html')
						if path.exists('/tmp/index.html'):
							remove('/tmp/index.html')
						print '[SoftcamManager] ' + softcamcheck + ' already running'
						output = open('/tmp/cam.check.log', 'a')
						now = datetime.now()
						output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " running OK\n")
						output.close()
						if softcamcheck.lower().startswith('oscam'):
							if path.exists('/tmp/status.html'):
								remove('/tmp/status.html')
							port = ''
							if path.exists('/etc/tuxbox/config/oscam.conf'):
								oscamconf = '/etc/tuxbox/config/oscam.conf'
							elif path.exists('/etc/tuxbox/config/oscam/oscam.conf'):
								oscamconf = '/etc/tuxbox/config/oscam/oscam.conf'
							f = open(oscamconf, 'r')
							for line in f.readlines():
								if line.find('httpport') != -1:
									port = re.sub("\D", "", line)
							f.close()
							print '[SoftcamManager] Checking if ' + softcamcheck + ' is frozen'
							if port == "":
								port = "16000"
							self.Console.ePopen("wget -T 1 http://127.0.0.1:" + port + "/status.html -O /tmp/status.html &> /tmp/frozen")
							sleep(2)
							f = open('/tmp/frozen')
							frozen = f.read()
							f.close()
							if frozen.find('Unauthorized') != -1 or frozen.find('Authorization Required') != -1 or frozen.find('Forbidden') != -1 or frozen.find('Connection refused') != -1 or frozen.find('100%') != -1 or path.exists('/tmp/status.html'):
								print '[SoftcamManager] ' + softcamcheck + ' is responding like it should'
								output = open('/tmp/cam.check.log', 'a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is responding like it should\n")
								output.close()
							else:
								print '[SoftcamManager] ' + softcamcheck + ' is frozen, Restarting...'
								output = open('/tmp/cam.check.log', 'a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is frozen, Restarting...\n")
								output.close()
								print '[SoftcamManager] Stopping ' + softcamcheck
								output = open('/tmp/cam.check.log', 'a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStopping: " + softcamcheck + "\n")
								output.close()
								self.Console.ePopen("killall -9 " + softcamcheck)
								sleep(1)
								self.Console.ePopen("ps.procps | grep softcams | grep -v grep | awk 'NR==1' | awk '{print $5}'| awk  -F'[/]' '{print $4}' > /tmp/oscamRuningCheck.tmp")
								sleep(2)
								file = open('/tmp/oscamRuningCheck.tmp')
								cccamcheck_process = file.read()
								file.close()
								cccamcheck_process = cccamcheck_process.replace("\n", "")
								if cccamcheck_process.lower().find('cccam') != -1:
									try:
										print '[SoftcamManager] Stopping ', cccamcheck_process
										output = open('/tmp/cam.check.log', 'a')
										now = datetime.now()
										output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStopping: " + cccamcheck_process + "\n")
										output.close()
										self.Console.ePopen("killall -9 /usr/softcams/" + str(cccamcheck_process))
									except:
										pass
								print '[SoftcamManager] Starting ' + softcamcheck
								output = open('/tmp/cam.check.log', 'a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStarting: " + softcamcheck + "\n")
								output.close()
								self.Console.ePopen('ulimit -s 512;/usr/softcams/' + softcamcheck + ' -b')
								sleep(10)

						elif softcamcheck.lower().startswith('cccam'):
							if path.exists('/tmp/index.html'):
								remove('/tmp/index.html')
							allow = 'no'
							port = ''
							f = open('/etc/CCcam.cfg', 'r')
							for line in f.readlines():
								if line.find('ALLOW WEBINFO') != -1:
									if not line.startswith('#'):
										parts = line.replace('ALLOW WEBINFO', '')
										parts = parts.replace(':', '')
										parts = parts.replace(' ', '')
										parts = parts.strip().split()
										if parts[0].startswith('yes'):
											allow = parts[0]
								if line.find('WEBINFO LISTEN PORT') != -1:
									port = re.sub("\D", "", line)
							f.close()
							if allow.lower().find('yes') != -1:
								print '[SoftcamManager] Checking if ' + softcamcheck + ' is frozen'
								if port == "":
									port = "16001"
								self.Console.ePopen("wget -T 1 http://127.0.0.1:" + port + " -O /tmp/index.html &> /tmp/frozen")
								sleep(2)
								f = open('/tmp/frozen')
								frozen = f.read()
								f.close()
								if frozen.find('Unauthorized') != -1 or frozen.find('Authorization Required') != -1 or frozen.find('Forbidden') != -1 or frozen.find('Connection refused') != -1 or frozen.find('100%') != -1 or path.exists('/tmp/index.html'):
									print '[SoftcamManager] ' + softcamcheck + ' is responding like it should'
									output = open('/tmp/cam.check.log', 'a')
									now = datetime.now()
									output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is responding like it should\n")
									output.close()
								else:
									print '[SoftcamManager] ' + softcamcheck + ' is frozen, Restarting...'
									output = open('/tmp/cam.check.log', 'a')
									now = datetime.now()
									output.write(now.strftime("%Y-%m-%d %H:%M") + ": " + softcamcheck + " is frozen, Restarting...\n")
									output.close()
									print '[SoftcamManager] Stopping ' + softcamcheck
									self.Console.ePopen("killall -9 " + softcamcheck)
									sleep(1)
									print '[SoftcamManager] Starting ' + softcamcheck
									self.Console.ePopen('ulimit -s 512;/usr/softcams/' + softcamcheck)
							elif allow.lower().find('no') != -1:
								print '[SoftcamManager] Telnet info not allowed, can not check if frozen'
								output = open('/tmp/cam.check.log', 'a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ":  Webinfo info not allowed, can not check if frozen,\n\tplease enable 'ALLOW WEBINFO: YES'\n")
								output.close()
							else:
								print "[SoftcamManager] Webinfo info not setup, please enable 'ALLOW WEBINFO= YES'"
								output = open('/tmp/cam.check.log', 'a')
								now = datetime.now()
								output.write(now.strftime("%Y-%m-%d %H:%M") + ":  Telnet info not setup, can not check if frozen,\n\tplease enable 'ALLOW WEBINFO: YES'\n")
								output.close()

					elif softcamcheck_process == "":
						print "[SoftcamManager] Couldn't find " + softcamcheck + " running, Starting " + softcamcheck
						output = open('/tmp/cam.check.log', 'a')
						now = datetime.now()
						output.write(now.strftime("%Y-%m-%d %H:%M") + ": Couldn't find " + softcamcheck + " running, Starting " + softcamcheck + "\n")
						output.close()
						if softcamcheck.lower().startswith('oscam'):
							self.Console.ePopen("ps.procps | grep softcams | grep -v grep | awk 'NR==1' | awk '{print $5}'| awk  -F'[/]' '{print $4}' > /tmp/softcamRuningCheck.tmp")
							sleep(2)
							file = open('/tmp/softcamRuningCheck.tmp')
							cccamcheck_process = file.read()
							cccamcheck_process = cccamcheck_process.replace("\n", "")
							file.close()
							if cccamcheck_process.find('cccam') >= 0 or cccamcheck_process.find('CCcam') >= 0:
								try:
									print '[SoftcamManager] Stopping ', cccamcheck_process
									output = open('/tmp/cam.check.log', 'a')
									now = datetime.now()
									output.write(now.strftime("%Y-%m-%d %H:%M") + ": AutoStopping: " + cccamcheck_process + "\n")
									output.close()
									self.Console.ePopen("killall -9 /usr/softcams/" + str(cccamcheck_process))
								except:
									pass
							self.Console.ePopen('ulimit -s 512;/usr/softcams/' + softcamcheck + " -b")
							sleep(10)
							remove('/tmp/softcamRuningCheck.tmp')
						elif softcamcheck.lower().startswith('sbox'):
							self.Console.ePopen('ulimit -s 512;/usr/softcams/' + softcamcheck)
							sleep(7)
						elif softcamcheck.lower().startswith('gbox'):
							self.Console.ePopen('ulimit -s 512;/usr/softcams/' + softcamcheck)
							sleep(3)
							self.Console.ePopen('start-stop-daemon --start --quiet --background --exec /usr/bin/gbox')
						else:
							self.Console.ePopen('ulimit -s 512;/usr/softcams/' + softcamcheck)
