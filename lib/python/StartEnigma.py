from os.path import exists as osexists
import sys  # don't change import
from time import localtime, strftime, time
from datetime import datetime
from traceback import print_exc

from Tools.Profile import profile, profile_final
import Tools.RedirectOutput  # noqa: F401 # Don't remove this line. It may seem to do nothing, but if removed it will break output redirection for crash logs.
import eConsoleImpl
import eBaseImpl
import enigma
enigma.eTimer = eBaseImpl.eTimer
enigma.eSocketNotifier = eBaseImpl.eSocketNotifier
enigma.eConsoleAppContainer = eConsoleImpl.eConsoleAppContainer


class Session:

	#  Session.open:
	# 	 * push current active dialog ("current_dialog") onto stack
	# 	 * call execEnd for this dialog
	# 	   * clear in_exec flag
	# 	   * hide screen
	# 	 * instantiate new dialog into "current_dialog"
	# 	   * create screens, components
	# 	   * read, apply skin
	# 	   * create GUI for screen
	# 	 * call execBegin for new dialog
	# 	   * set in_exec
	# 	   * show gui screen
	# 	   * call components' / screen's onExecBegin
	#  ... screen is active, until it calls "close"...
	#  Session.close:
	# 	 * assert in_exec
	# 	 * save return value
	# 	 * start deferred close handler ("onClose")
	# 	 * execEnd
	# 	   * clear in_exec
	# 	   * hide screen
	#  .. a moment later:
	#  Session.doClose:
	# 	 * destroy screen

	def __init__(self, desktop=None, summary_desktop=None, navigation=None):
		self.desktop = desktop
		self.summary_desktop = summary_desktop
		self.nav = navigation
		self.delay_timer = enigma.eTimer()
		self.delay_timer.callback.append(self.processDelay)
		self.current_dialog = None
		self.dialog_stack = []
		self.summary_stack = []
		self.summary = None
		self.in_exec = False
		self.screen = SessionGlobals(self)
		for p in plugins.getPlugins(PluginDescriptor.WHERE_SESSIONSTART):
			try:
				p(reason=0, session=self)
			except Exception:
				print("[StartEnigma] Plugin raised exception at WHERE_SESSIONSTART")
				print_exc()

	def processDelay(self):
		callback = self.current_dialog.callback
		retval = self.current_dialog.returnValue
		if self.current_dialog.isTmp:
			self.current_dialog.doClose()
			del self.current_dialog
		else:
			del self.current_dialog.callback
		self.popCurrent()
		if callback is not None:
			callback(*retval)

	def execBegin(self, first=True, do_show=True):
		assert not self.in_exec
		self.in_exec = True
		currentDialog = self.current_dialog
		# When this is an execbegin after a execEnd of a "higher" dialog,
		# popSummary already did the right thing.
		if first:
			self.instantiateSummaryDialog(currentDialog)
		currentDialog.saveKeyboardMode()
		currentDialog.execBegin()
		# When execBegin opened a new dialog, don't bother showing the old one.
		if currentDialog == self.current_dialog and do_show:
			currentDialog.show()

	def execEnd(self, last=True):
		assert self.in_exec
		self.in_exec = False
		self.current_dialog.execEnd()
		self.current_dialog.restoreKeyboardMode()
		self.current_dialog.hide()
		if last and self.summary is not None:
			self.current_dialog.removeSummary(self.summary)
			self.popSummary()

	def instantiateDialog(self, screen, *arguments, **kwargs):
		return self.doInstantiateDialog(screen, arguments, kwargs, self.desktop)

	def deleteDialog(self, screen):
		screen.hide()
		screen.doClose()

	def deleteDialogWithCallback(self, callback, screen, *retval):
		screen.hide()
		screen.doClose()
		if callback is not None:
			callback(*retval)

	def instantiateSummaryDialog(self, screen, **kwargs):
		if self.summary_desktop is not None:
			self.pushSummary()
			summary = screen.createSummary() or ScreenSummary
			arguments = (screen,)
			self.summary = self.doInstantiateDialog(summary, arguments, kwargs, self.summary_desktop)
			self.summary.show()
			screen.addSummary(self.summary)

	def doInstantiateDialog(self, screen, arguments, kwargs, desktop):
		dialog = screen(self, *arguments, **kwargs)  # Create dialog.
		if dialog is None:
			return
		readSkin(dialog, None, dialog.skinName, desktop)  # Read skin data.
		dialog.setDesktop(desktop)  # Create GUI view of this dialog.
		dialog.applySkin()
		return dialog

	def pushCurrent(self):
		if self.current_dialog is not None:
			self.dialog_stack.append((self.current_dialog, self.current_dialog.shown))
			self.execEnd(last=False)

	def popCurrent(self):
		if self.dialog_stack:
			(self.current_dialog, do_show) = self.dialog_stack.pop()
			self.execBegin(first=False, do_show=do_show)
		else:
			self.current_dialog = None

	def execDialog(self, dialog):
		self.pushCurrent()
		self.current_dialog = dialog
		self.current_dialog.isTmp = False
		self.current_dialog.callback = None  # would cause re-entrancy problems.
		self.execBegin()

	def openWithCallback(self, callback, screen, *arguments, **kwargs):
		dialog = self.open(screen, *arguments, **kwargs)
		dialog.callback = callback
		return dialog

	def open(self, screen, *arguments, **kwargs):
		if self.dialog_stack and not self.in_exec:
			raise RuntimeError("[StartEnigma] Error: Modal open are allowed only from a screen which is modal!")  # ...unless it's the very first screen.
		self.pushCurrent()
		dialog = self.current_dialog = self.instantiateDialog(screen, *arguments, **kwargs)
		dialog.isTmp = True
		dialog.callback = None
		self.execBegin()
		return dialog

	def close(self, screen, *retval):
		if not self.in_exec:
			print("[StartEnigma] Close after exec!")
			return

		# Be sure that the close is for the right dialog!
		# If it's not, you probably closed after another dialog was opened.
		# This can happen if you open a dialog onExecBegin, and forget to do this only once.
		#
		# After close of the top dialog, the underlying dialog will gain focus again (for a short time),
		# thus triggering the onExec, which opens the dialog again, closing the loop.
		#
		assert screen == self.current_dialog

		self.current_dialog.returnValue = retval
		self.delay_timer.start(0, 1)
		self.execEnd()

	def pushSummary(self):
		if self.summary is not None:
			self.summary.hide()
			self.summary_stack.append(self.summary)
			self.summary = None

	def popSummary(self):
		if self.summary is not None:
			self.summary.doClose()
		if not self.summary_stack:
			self.summary = None
		else:
			self.summary = self.summary_stack.pop()
		if self.summary is not None:
			self.summary.show()

	def reloadSkin(self):
		from Screens.MessageBox import MessageBox
		reloadNotification = self.instantiateDialog(MessageBox, _("Loading skin"), MessageBox.TYPE_INFO,
			simple=True, picon=False, title=_("Please wait"))
		reloadNotification.show()

		# empty any cached resolve lists remaining in Directories.py as these may not relate to the skin being loaded
		from Tools.Directories import clearResolveLists
		clearResolveLists()

		# close all open dialogs by emptying the dialog stack
		# remove any return values and callbacks for a swift exit
		while self.current_dialog is not None and type(self.current_dialog) is not InfoBar.InfoBar:
			print("[SkinReloader] closing %s" % type(self.current_dialog))
			self.current_dialog.returnValue = None
			self.current_dialog.callback = None
			self.execEnd()
			self.processDelay()
		# need to close the infobar outside the loop as its exit causes a new infobar to be created
		print("[SkinReloader] closing InfoBar")
		InfoBar.InfoBar.instance.close("reloadskin", reloadNotification)


class PowerKey:
	""" PowerKey - handles the powerkey press and powerkey release actions"""

	def __init__(self, session):
		self.session = session
		globalActionMap.actions["power_down"] = self.powerdown
		globalActionMap.actions["power_up"] = self.powerup
		globalActionMap.actions["power_long"] = self.powerlong
		globalActionMap.actions["deepstandby"] = self.shutdown  # frontpanel long power button press
		globalActionMap.actions["discrete_off"] = self.standby
		self.standbyblocked = 1

	def MenuClosed(self, *val):
		self.session.infobar = None

	def shutdown(self):
		wasRecTimerWakeup = False
		recordings = self.session.nav.getRecordings()
		if not recordings:
			next_rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
		if recordings or (next_rec_time > 0 and (next_rec_time - time()) < 360):
			if osexists("/tmp/was_rectimer_wakeup") and not self.session.nav.RecordTimer.isRecTimerWakeup():
				f = open("/tmp/was_rectimer_wakeup", "r")
				file = f.read()
				f.close()
				wasRecTimerWakeup = int(file) and True or False
			if self.session.nav.RecordTimer.isRecTimerWakeup() or wasRecTimerWakeup:
				print("[StartEnigma] PowerOff (timer wakewup) - Recording in progress or a timer about to activate, entering standby!")
				self.standby()
			else:
				print("[StartEnigma] PowerOff - Now!")
				self.session.open(Screens.Standby.TryQuitMainloop, 1)
		elif not Screens.Standby.inTryQuitMainloop and self.session.current_dialog and self.session.current_dialog.ALLOW_SUSPEND:
			print("[StartEnigma] PowerOff - Now!")
			self.session.open(Screens.Standby.TryQuitMainloop, 1)

	def powerlong(self):
		if Screens.Standby.inTryQuitMainloop or (self.session.current_dialog and not self.session.current_dialog.ALLOW_SUSPEND):
			return
		self.doAction(action=config.usage.on_long_powerpress.value)

	def doAction(self, action):
		self.standbyblocked = 1
		if action == "shutdown":
			self.shutdown()
		elif action == "show_menu":
			print("[StartEnigma] Show shutdown Menu")
			root = mdom.getroot()
			for x in root.findall("menu"):
				if x.get("key") == "shutdown":
					self.session.infobar = self
					menu_screen = self.session.openWithCallback(self.MenuClosed, MainMenu, x)
					menu_screen.setTitle(_("Standby / restart"))
					return
		elif action == "standby":
			self.standby()

	def powerdown(self):
		self.standbyblocked = 0

	def powerup(self):
		if self.standbyblocked == 0:
			self.doAction(action=config.usage.on_short_powerpress.value)

	def standby(self):
		if not Screens.Standby.inStandby and self.session.current_dialog and self.session.current_dialog.ALLOW_SUSPEND and self.session.in_exec:
			self.session.open(Screens.Standby.Standby)


class AutoScartControl:
	def __init__(self, session):
		self.force = False
		self.current_vcr_sb = enigma.eAVSwitch.getInstance().getVCRSlowBlanking()
		if self.current_vcr_sb and config.av.vcrswitch.value:
			self.scartDialog = session.instantiateDialog(Scart, True)
		else:
			self.scartDialog = session.instantiateDialog(Scart, False)
		config.av.vcrswitch.addNotifier(self.recheckVCRSb)
		enigma.eAVSwitch.getInstance().vcr_sb_notifier.get().append(self.VCRSbChanged)

	def recheckVCRSb(self, configElement):
		self.VCRSbChanged(self.current_vcr_sb)

	def VCRSbChanged(self, value):
		# print("vcr sb changed to", value)
		self.current_vcr_sb = value
		if config.av.vcrswitch.value or value > 2:
			if value:
				self.scartDialog.showMessageBox()
			else:
				self.scartDialog.switchToTV()


def runScreenTest():
	config.misc.startCounter.value += 1
	config.misc.startCounter.save()

	profile("readPluginList")
	enigma.pauseInit()
	plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
	enigma.resumeInit()

	profile("Init:Session")
	nav = Navigation(config.misc.isNextRecordTimerAfterEventActionAuto.value, config.misc.isNextPowerTimerAfterEventActionAuto.value)
	session = Session(desktop=enigma.getDesktop(0), summary_desktop=enigma.getDesktop(1), navigation=nav)
	from Session import SessionObject
	so = SessionObject()
	so.session = session

	profile("Init:Trashcan")
	import Tools.Trashcan
	Tools.Trashcan.init(session)
	if not VuRecovery:
		CiHandler.setSession(session)

	screensToRun = [p.fnc for p in plugins.getPlugins(PluginDescriptor.WHERE_WIZARD)]
	profile("wizards")
	screensToRun += wizardManager.getWizards()  # noqa: F405
	screensToRun.append((100, InfoBar.InfoBar))
	screensToRun.sort()

	enigma.ePythonConfigQuery.setQueryFunc(configfile.getResolvedKey)

	def runNextScreen(session, screensToRun, *result):
		if result:
			if result[0] == "reloadskin":
				InitSkins(False)
				session.openWithCallback(boundFunction(runNextScreen, session, []), InfoBar.InfoBar)
				if result[1]:
					session.deleteDialog(result[1])
			else:
				enigma.quitMainloop(*result)
		else:
			screen = screensToRun[0][1]
			args = screensToRun[0][2:]
			session.openWithCallback(boundFunction(runNextScreen, session, screensToRun[1:]), screen, *args)

	runNextScreen(session, screensToRun)

	if not VuRecovery:
		profile("Init:VolumeControl")
		vol = VolumeControl(session)  # noqa: F841
		profile("Init:PowerKey")
		power = PowerKey(session)  # noqa: F841

		if enigma.eAVSwitch.getInstance().haveScartSwitch():
			# we need session.scart to access it from within menu.xml
			session.scart = AutoScartControl(session)

		profile("Init:AutoVideoMode")
		import Screens.VideoMode
		Screens.VideoMode.autostart(session)

	profile("RunReactor")
	profile_final()
	runReactor()

	if not VuRecovery:
		profile("wakeup")
		# get currentTime
		nowTime = time()
		wakeupList = [x for x in (
			(session.nav.RecordTimer.getNextRecordingTime(), 0, session.nav.RecordTimer.isNextRecordAfterEventActionAuto()),
			(session.nav.RecordTimer.getNextZapTime(), 1),
			(plugins.getNextWakeupTime(), 2, plugins.getNextWakeupName()),
			(session.nav.PowerTimer.getNextPowerManagerTime(), 3, session.nav.PowerTimer.isNextPowerManagerAfterEventActionAuto())
		) if x[0] != -1]
		wakeupList.sort()
		recordTimerWakeupAuto = False
		if wakeupList and wakeupList[0][1] != 3:
			startTime = wakeupList[0]
			if (startTime[0] - nowTime) < 270:  # no time to switch box back on
				wptime = nowTime + 30  # so switch back on in 30 seconds
			else:
				wptime = startTime[0] - 240
			if wakeupList[0][1] == 2 and wakeupList[0][2] is not None:
				config.misc.pluginWakeupName.value = wakeupList[0][2]
				print("[StartEnigma] next wakeup will be plugin", wakeupList[0][2])
			else:
				config.misc.pluginWakeupName.value = ""  # next wakeup not a plugin
			config.misc.pluginWakeupName.save()
			if not config.misc.SyncTimeUsing.value == "dvb":
				print("[StartEnigma] dvb time sync disabled... so set RTC now to current linux time!", strftime("%Y/%m/%d %H:%M", localtime(nowTime)))
				setRTCtime(nowTime)
			print("[StartEnigma] set wakeup time to", strftime("%Y/%m/%d %H:%M", localtime(wptime)))
			setFPWakeuptime(wptime)
			recordTimerWakeupAuto = startTime[1] == 0 and startTime[2]
			print("[StartEnigma] recordTimerWakeupAuto", recordTimerWakeupAuto)
		config.misc.isNextRecordTimerAfterEventActionAuto.value = recordTimerWakeupAuto
		config.misc.isNextRecordTimerAfterEventActionAuto.save()

		PowerTimerWakeupAuto = False
		if wakeupList and wakeupList[0][1] == 3:
			startTime = wakeupList[0]
			if (startTime[0] - nowTime) < 60:  # no time to switch box back on
				wptime = nowTime + 30  # so switch back on in 30 seconds
			else:
				wptime = startTime[0]
			if not config.misc.SyncTimeUsing.value == "dvb":
				print("[StartEnigma] dvb time sync disabled... so set RTC now to current linux time!", strftime("%Y/%m/%d %H:%M", localtime(nowTime)))
				setRTCtime(nowTime)
			print("[StartEnigma] set wakeup time to", strftime("%Y/%m/%d %H:%M", localtime(wptime + 60)))
			setFPWakeuptime(wptime)
			PowerTimerWakeupAuto = startTime[1] == 3 and startTime[2]
			print("[StartEnigma] PowerTimerWakeupAuto", PowerTimerWakeupAuto)
			config.misc.pluginWakeupName.value = ""  # next wakeup not a plugin
			config.misc.pluginWakeupName.save()
		config.misc.isNextPowerTimerAfterEventActionAuto.value = PowerTimerWakeupAuto
		config.misc.isNextPowerTimerAfterEventActionAuto.save()
	profile("stopService")
	session.nav.stopService()
	profile("nav shutdown")
	session.nav.shutdown()
	profile("configfile.save")
	configfile.save()
	if not VuRecovery:
		from Screens import InfoBarGenerics
		InfoBarGenerics.saveResumePoints()
	return 0


profile("PYTHON_START")
from Components.SystemInfo import SystemInfo  # noqa: E402  don't move this import

print("[StartEnigma]  Starting Python Level Initialisation.")
print("[StartEnigma]  Image Type -> '%s'" % SystemInfo["imagetype"])
print("[StartEnigma]  Image Version -> '%s'" % SystemInfo["imageversion"])
print("[StartEnigma]  Image Build -> '%s'" % SystemInfo["imagebuild"])
if SystemInfo["imagetype"] != "release":
	print("[StartEnigma]  Image DevBuild -> '%s'" % SystemInfo["imagedevbuild"])


# SetupDevices sets up defaults:- language, keyboard, parental & expert config.
# Moving further down will break translation.
# Moving further up will break imports in config.py
profile("SetupDevices")
print("[StartEnigma]  Initialising SetupDevices.")
from Components.SetupDevices import InitSetupDevices  # noqa: E402
InitSetupDevices()

if SystemInfo["architecture"] in ("aarch64"):  # something not right here
	from usb.backend import libusb1  # noqa: E402
	libusb1.get_backend(find_library=lambda x: "/lib64/libusb-1.0.so.0")


profile("ClientMode")
print("[StartEnigma]  Initialising ClientMode.")
from Components.ClientMode import InitClientMode  # noqa: E402
InitClientMode()

profile("InfoBar")
print("[StartEnigma]  Initialising InfoBar.")
from Screens import InfoBar  # noqa: E402

# from Components.SystemInfo import SystemInfo  # noqa: E402  don't move this import
VuRecovery = SystemInfo["HasKexecMultiboot"] and SystemInfo["MultiBootSlot"] == 0
# print("[StartEnigma]  Is this VuRecovery?. Recovery = ", VuRecovery)

from Components.config import config, configfile, ConfigInteger, ConfigSelection, ConfigText, ConfigYesNo, NoSave  # noqa: E402
if not VuRecovery:
	profile("Bouquets")
	print("[StartEnigma]  Initialising Bouquets.")
	config.misc.load_unlinked_userbouquets = ConfigYesNo(default=False)

	def setLoadUnlinkedUserbouquets(configElement):
		enigma.eDVBDB.getInstance().setLoadUnlinkedUserbouquets(configElement.value)

	config.misc.load_unlinked_userbouquets.addNotifier(setLoadUnlinkedUserbouquets)
	if config.clientmode.enabled.value is False:
		enigma.eDVBDB.getInstance().reloadBouquets()

profile("ParentalControl")
print("[StartEnigma]  Initialising ParentalControl.")
import Components.ParentalControl  # noqa: E402
Components.ParentalControl.InitParentalControl()

profile("LOAD:Navigation")
print("[StartEnigma]  Initialising Navigation.")
from Navigation import Navigation  # noqa: E402

profile("LOAD:skin")
print("[StartEnigma]  Initialising Skin.")
from skin import readSkin  # noqa: E402

profile("LOAD:Tools")
print("[StartEnigma]  Initialising FallbackFiles.")

from Tools.Directories import InitFallbackFiles, resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN  # noqa: E402
InitFallbackFiles()

profile("config.misc")
print("[StartEnigma]  Initialising Misc Config Variables.")
config.misc.radiopic = ConfigText(default=resolveFilename(SCOPE_CURRENT_SKIN, "radio.mvi"))
config.misc.blackradiopic = ConfigText(default=resolveFilename(SCOPE_CURRENT_SKIN, "black.mvi"))
config.misc.isNextRecordTimerAfterEventActionAuto = ConfigYesNo(default=False)
config.misc.isNextPowerTimerAfterEventActionAuto = ConfigYesNo(default=False)
config.misc.pluginWakeupName = ConfigText(default="")
config.misc.SyncTimeUsing = ConfigSelection(default="dvb", choices=[("dvb", _("Transponder Time")), ("ntp", _("NTP"))])
config.misc.NTPserver = ConfigText(default='pool.ntp.org', fixed_size=False)
config.misc.useNTPminutes = ConfigSelection(default="30", choices=[("30", "30" + " " + _("minutes")), ("60", _("Hour")), ("1440", _("Once per day"))])

config.misc.startCounter = ConfigInteger(default=0)  # number of e2 starts..
config.misc.startCounter = ConfigInteger(default=0)  # number of e2 starts...
config.misc.standbyCounter = NoSave(ConfigInteger(default=0))  # number of standby
config.misc.DeepStandby = NoSave(ConfigYesNo(default=False))  # detect deepstandby


profile("Twisted")
print("[StartEnigma]  Initialising Twisted.")
try:
	import twisted.python.runtime  # noqa: E402
	twisted.python.runtime.platform.supportsThreads = lambda: True
	import e2reactor  # noqa: E402
	e2reactor.install()
	from twisted.internet import reactor  # noqa: E402

	def runReactor():
		reactor.run(installSignalHandlers=False)

except ImportError:
	print("[StartEnigma] Error: Twisted not available!")

	def runReactor():
		enigma.runMainloop()

profile("Twisted Log")
print("[StartEnigma]  Initialising Twisted Log.")
try:
	from twisted.python import log, util  # noqa: E402

	def quietEmit(self, eventDict):
		text = log.textFromEventDict(eventDict)
		if text is None:
			return
		if "/api/statusinfo" in text:  # Do not log OpenWebif status info.
			return
		formatDict = {
			"text": text.replace("\n", "\n\t")
		}
		msg = log._safeFormat("%(text)s\n", formatDict)
		util.untilConcludes(self.write, msg)
		util.untilConcludes(self.flush)

	logger = log.FileLogObserver(sys.stdout)		# do not change or no crashlog
	log.FileLogObserver.emit = quietEmit
	backup_stdout = sys.stdout		# backup stdout and stderr redirections
	backup_stderr = sys.stderr
	log.startLoggingWithObserver(logger.emit)
	sys.stdout = backup_stdout		# restore stdout and stderr redirections because of twisted redirections
	sys.stderr = backup_stderr
except ImportError:
	print("[StartEnigma] Error: Twisted not available!")


profile("Init:NTPSync")
print("[StartEnigma]  Initialising NTPSync.")
from Components.NetworkTime import AutoNTPSync  # noqa: E402
AutoNTPSync()

profile("LOAD:Wizard")
print("[StartEnigma]  Initialising Wizards.")
from Screens.StartWizard import *  # noqa: F403,E402

profile("LOAD:Plugin")
print("[StartEnigma]  Initialising Plugins.")
# initialize autorun plugins and plugin menu entries
from Components.PluginComponent import plugins  # noqa: E402

import Screens.Rc  # noqa: E402
from Tools.BoundFunction import boundFunction  # noqa: E402
from Plugins.Plugin import PluginDescriptor  # noqa: E402

if config.misc.firstrun.value and not osexists('/etc/install'):
	with open("/etc/install", "w") as f:
		now = datetime.now()
		flashdate = now.strftime("%Y%m%d")
		print("[StartEnigma][Setting Flash date]", flashdate)
		f.write(flashdate)

profile("misc")
had = dict()

profile("LOAD:ScreenGlobals")
print("[StartEnigma]  Initialising ScreenGlobals.")
from Screens.Globals import Globals  # noqa: E402
from Screens.SessionGlobals import SessionGlobals  # noqa: E402
from Screens.Screen import Screen, ScreenSummary  # noqa: E402

profile("Screen")
Screen.globalScreen = Globals()


# must be above skins and InputDevices
config.misc.RCSource = ConfigSelection(default="branding", choices=[("branding", _("OE-A-Branding")), ("hardware", _("OE-A-Remotes"))])


def RCSelectionChanged(configelement):
	from Components.SystemInfo import setRCFile  # noqa: E402
	setRCFile(configelement.value)


config.misc.RCSource.addNotifier(RCSelectionChanged, immediate_feedback=False)

profile("Standby")
import Screens.Standby  # noqa: E402

from Screens.Menu import MainMenu, mdom  # noqa: E402
from GlobalActions import globalActionMap  # noqa: E402

if enigma.eAVSwitch.getInstance().haveScartSwitch():
	profile("Scart")
	print("[StartEnigma]  Initialising Scart.")
	from Screens.Scart import Scart  # noqa: E402

if not VuRecovery:
	profile("Load:CI")
	print("[StartEnigma]  Initialising CommonInterface.")
	from Screens.Ci import CiHandler  # noqa: E402

	profile("Load:VolumeControl")
	print("[StartEnigma]  Initialising VolumeControl.")
	from Components.VolumeControl import VolumeControl  # noqa: E402
	from Tools.StbHardware import setFPWakeuptime, setRTCtime  # noqa: E402

profile("Init:skin")
print("[StartEnigma]  Initialising Skins.")
from skin import InitSkins  # noqa: E402
InitSkins()
print("[StartEnigma]  Initialisation of Skins complete.")

profile("InputDevice")
print("[StartEnigma]  Initialising InputDevice.")
from Components.InputDevice import InitInputDevices  # noqa: E402
InitInputDevices()
import Components.InputHotplug  # noqa: E402

profile("UserInterface")
print("[StartEnigma]  Initialising UserInterface.")
from Screens.UserInterfacePositioner import InitOsd  # noqa: E402
InitOsd()

profile("AVSwitch")
print("[StartEnigma]  Initialising AVSwitch.")
from Components.AVSwitch import InitAVSwitch, InitiVideomodeHotplug  # noqa: E402
InitAVSwitch()
InitiVideomodeHotplug()

profile("EpgConfig")
from Components.EpgConfig import InitEPGConfig  # noqa: E402
InitEPGConfig()

if not VuRecovery:
	profile("RecordingConfig")
	print("[StartEnigma]  Initialising RecordingConfig.")
	from Components.RecordingConfig import InitRecordingConfig  # noqa: E402
	InitRecordingConfig()

profile("UsageConfig")
print("[StartEnigma]  Initialising UsageConfig.")
from Components.UsageConfig import InitUsageConfig  # noqa: E402
InitUsageConfig()

profile("TimeZones")
print("[StartEnigma]  Initialising Timezones.")
from Components.Timezones import InitTimeZones  # noqa: E402
InitTimeZones()

profile("Init:DebugLogCheck")
print("[StartEnigma]  Initialising DebugLogCheck.")
from Screens.LogManager import AutoLogManager  # noqa: E402
AutoLogManager()

profile("keymapparser")
print("[StartEnigma]  Initialising KeymapParser.")
from keymapparser import readKeymap  # noqa: E402
readKeymap(config.usage.keymap.value)
if osexists(config.usage.keytrans.value):
	readKeymap(config.usage.keytrans.value)

if VuRecovery:
	SystemInfo["Display"] = False
else:
	profile("Init:OnlineCheckState")
	print("[StartEnigma]  Initialising OnlineCheckState.")
	from Components.OnlineUpdateCheck import OnlineUpdateCheck  # noqa: E402
	OnlineUpdateCheck()

	profile("Network")
	print("[StartEnigma]  Initialising Network.")
	from Components.Network import InitNetwork  # noqa: E402
	InitNetwork()

	profile("HdmiCec")
	print("[StartEnigma]  Initialising hdmiCEC.")
	from Components.HdmiCec import HdmiCec  # noqa: E402
	HdmiCec()

	profile("LCD")
	print("[StartEnigma]  Initialising LCD / FrontPanel.")
	from Components.Lcd import InitLcd  # noqa: E402
	InitLcd()

	profile("UserInterface")
	print("[StartEnigma]  Initialising UserInterface.")
	from Screens.UserInterfacePositioner import InitOsdPosition  # noqa: E402
	InitOsdPosition()

	profile("EpgCacheSched")
	print("[StartEnigma]  Initialising EPGCacheScheduler.")
	from Components.EpgLoadSave import EpgCacheLoadCheck, EpgCacheSaveCheck  # noqa: E402
	EpgCacheSaveCheck()
	EpgCacheLoadCheck()

	profile("RFMod")
	print("[StartEnigma]  Initialising RFMod.")
	from Components.RFmod import InitRFmod  # noqa: E402
	InitRFmod()

	profile("Init:CI")
	print("[StartEnigma]  Initialising CommonInterface.")
	from Screens.Ci import InitCiConfig  # noqa: E402
	InitCiConfig()

	if config.clientmode.enabled.value:
		import Components.ChannelsImporter  # noqa: E402
		Components.ChannelsImporter.autostart()


print("[StartEnigma]  Starting User Interface.")  # first, setup a screen

try:
	runScreenTest()
	plugins.shutdown()
	if not VuRecovery:
		Components.ParentalControl.parentalControl.save()
except Exception:
	print("[StartEnigma] EXCEPTION IN PYTHON STARTUP CODE:")
	print("-" * 60)
	print_exc(file=sys.stdout)
	enigma.quitMainloop(5)
	print("-" * 60)
