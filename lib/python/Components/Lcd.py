from boxbranding import getBoxType, getDisplayType
from sys import maxint

from twisted.internet import threads
from enigma import eDBoxLCD, eTimer, eActionMap

from config import config, ConfigSubsection, ConfigSelection, ConfigSlider, ConfigYesNo, ConfigNothing
from Components.SystemInfo import SystemInfo
from Tools.Directories import fileExists
from Screens.InfoBar import InfoBar
from Screens.Screen import Screen
import Screens.Standby
import usb


class dummyScreen(Screen):
	skin = """<screen position="0,0" size="0,0" transparent="1">
	<widget source="session.VideoPicture" render="Pig" position="0,0" size="0,0" backgroundColor="transparent" zPosition="1"/>
	</screen>"""
	def __init__(self, session, args=None):
		Screen.__init__(self, session)
		self.close()

def IconCheck(session=None, **kwargs):
	if fileExists("/proc/stb/lcd/symbol_network") or fileExists("/proc/stb/lcd/symbol_usb"):
		global networklinkpoller
		networklinkpoller = IconCheckPoller()
		networklinkpoller.start()

class IconCheckPoller:
	def __init__(self):
		self.timer = eTimer()

	def start(self):
		if self.iconcheck not in self.timer.callback:
			self.timer.callback.append(self.iconcheck)
		self.timer.startLongTimer(0)

	def stop(self):
		if self.iconcheck in self.timer.callback:
			self.timer.callback.remove(self.iconcheck)
		self.timer.stop()

	def iconcheck(self):
		threads.deferToThread(self.JobTask)
		self.timer.startLongTimer(30)

	def JobTask(self):
		LinkState = 0
		if fileExists('/sys/class/net/wlan0/operstate'):
			LinkState = open('/sys/class/net/wlan0/operstate').read()
			if LinkState != 'down':
				LinkState = open('/sys/class/net/wlan0/operstate').read()
		elif fileExists('/sys/class/net/eth0/operstate'):
			LinkState = open('/sys/class/net/eth0/operstate').read()
			if LinkState != 'down':
				LinkState = open('/sys/class/net/eth0/carrier').read()
		LinkState = LinkState[:1]
		if fileExists("/proc/stb/lcd/symbol_network") and config.lcd.mode.value == '1':
			f = open("/proc/stb/lcd/symbol_network", "w")
			f.write(str(LinkState))
			f.close()
		elif fileExists("/proc/stb/lcd/symbol_network") and config.lcd.mode.value == '0':
			f = open("/proc/stb/lcd/symbol_network", "w")
			f.write('0')
			f.close()

		USBState = 0
		busses = usb.busses()
		for bus in busses:
			devices = bus.devices
			for dev in devices:
				if dev.deviceClass != 9 and dev.deviceClass != 2 and dev.idVendor > 0:
					# print ' '
					# print "Device:", dev.filename
					# print "  Number:", dev.deviceClass
					# print "  idVendor: %d (0x%04x)" % (dev.idVendor, dev.idVendor)
					# print "  idProduct: %d (0x%04x)" % (dev.idProduct, dev.idProduct)
					USBState = 1
		if fileExists("/proc/stb/lcd/symbol_usb") and config.lcd.mode.value == '1':
			f = open("/proc/stb/lcd/symbol_usb", "w")
			f.write(str(USBState))
			f.close()
		elif fileExists("/proc/stb/lcd/symbol_usb") and config.lcd.mode.value == '0':
			f = open("/proc/stb/lcd/symbol_usb", "w")
			f.write('0')
			f.close()

		self.timer.startLongTimer(30)

class LCD:
	def __init__(self):
		eActionMap.getInstance().bindAction('', -maxint -1, self.DimUpEvent)
		self.autoDimDownLCDTimer = eTimer()
		self.autoDimDownLCDTimer.callback.append(self.autoDimDownLCD)
		self.autoDimUpLCDTimer = eTimer()
		self.autoDimUpLCDTimer.callback.append(self.autoDimUpLCD)
		self.currBrightness = self.dimBrightness = self.Brightness = None
		self.dimDelay = 0
		config.misc.standbyCounter.addNotifier(self.standbyCounterChanged, initial_call = False)

	def standbyCounterChanged(self, configElement):
		Screens.Standby.inStandby.onClose.append(self.leaveStandby)
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		eActionMap.getInstance().unbindAction('', self.DimUpEvent)

	def leaveStandby(self):
		eActionMap.getInstance().bindAction('', -maxint -1, self.DimUpEvent)

	def DimUpEvent(self, key, flag):
		self.autoDimDownLCDTimer.stop()
		if not Screens.Standby.inTryQuitMainloop:
			if self.Brightness is not None and not self.autoDimUpLCDTimer.isActive():
				self.autoDimUpLCDTimer.start(10, True)

	def autoDimDownLCD(self):
		if not Screens.Standby.inTryQuitMainloop:
			if self.dimBrightness is not None and  self.currBrightness > self.dimBrightness:
				self.currBrightness = self.currBrightness - 1
				eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
				self.autoDimDownLCDTimer.start(10, True)

	def autoDimUpLCD(self):
		if not Screens.Standby.inTryQuitMainloop:
			self.autoDimDownLCDTimer.stop()
			if self.currBrightness < self.Brightness:
				self.currBrightness = self.currBrightness + 5
				if self.currBrightness >= self.Brightness:
					self.currBrightness = self.Brightness
				eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
				self.autoDimUpLCDTimer.start(10, True)
			else:
				if self.dimBrightness is not None and self.currBrightness > self.dimBrightness and self.dimDelay is not None and self.dimDelay > 0:
					self.autoDimDownLCDTimer.startLongTimer(self.dimDelay)

	def setBright(self, value):
		value *= 255
		value /= 10
		if value > 255:
			value = 255
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		self.currBrightness = self.Brightness = value
		eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
		if self.dimBrightness is not None and  self.currBrightness > self.dimBrightness:
			if self.dimDelay is not None and self.dimDelay > 0:
				self.autoDimDownLCDTimer.startLongTimer(self.dimDelay)

	def setStandbyBright(self, value):
		value *= 255
		value /= 10
		if value > 255:
			value = 255
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		self.Brightness = value
		if self.dimBrightness is None:
			self.dimBrightness = value
		if self.currBrightness is None:
			self.currBrightness = value
		eDBoxLCD.getInstance().setLCDBrightness(self.Brightness)

	def setDimBright(self, value):
		value *= 255
		value /= 10
		if value > 255:
			value = 255
		self.dimBrightness = value

	def setDimDelay(self, value):
		self.dimDelay = int(value)

	def setContrast(self, value):
		value *= 63
		value /= 20
		if value > 63:
			value = 63
		eDBoxLCD.getInstance().setLCDContrast(value)

	def setInverted(self, value):
		if value:
			value = 255
		eDBoxLCD.getInstance().setInverted(value)

	def setFlipped(self, value):
		eDBoxLCD.getInstance().setFlipped(value)

	def isOled(self):
		return eDBoxLCD.getInstance().isOled()

	def setMode(self, value):
		print 'setLCDMode',value
		f = open("/proc/stb/lcd/show_symbols", "w")
		f.write(value)
		f.close()

	def setPower(self, value):
		print 'setLCDPower',value
		f = open("/proc/stb/power/vfd", "w")
		f.write(value)
		f.close()

	def setLEDNormalState(self, value):
		eDBoxLCD.getInstance().setLED(value, 0)

	def setLEDDeepStandbyState(self, value):
		eDBoxLCD.getInstance().setLED(value, 1)

	def setLEDBlinkingTime(self, value):
		eDBoxLCD.getInstance().setLED(value, 2)

	def setLEDStandby(self, value):
		file = open("/proc/stb/power/standbyled", "w")
		file.write(value and "on" or "off")
		file.close()

	def setLCDMiniTVMode(self, value):
		print 'setLCDMiniTVMode',value
		f = open('/proc/stb/lcd/mode', "w")
		f.write(value)
		f.close()

	def setLCDMiniTVPIPMode(self, value):
		print 'setLCDMiniTVPIPMode',value

	def setLCDMiniTVFPS(self, value):
		print 'setLCDMiniTVFPS',value
		f = open('/proc/stb/lcd/fps', "w")
		f.write("%d \n" % value)
		f.close()

def leaveStandby():
	config.lcd.bright.apply()
	if SystemInfo["LEDButtons"]:
		config.lcd.ledbrightness.apply()
		config.lcd.ledbrightnessdeepstandby.apply()

def standbyCounterChanged(dummy):
	from Screens.Standby import inStandby
	inStandby.onClose.append(leaveStandby)
	config.lcd.standby.apply()
	if SystemInfo["LEDButtons"]:
		config.lcd.ledbrightnessstandby.apply()
		config.lcd.ledbrightnessdeepstandby.apply()

def InitLcd():
	if getBoxType() in ('et4x00', 'et5x00', 'et6x00', 'gb800se', 'gb800solo', 'iqonios300hd', 'mbmicro', 'sf128', 'sf138', 'tmsingle', 'tmnano2super', 'tmnanose', 'tmnanoseplus', 'tmnanosem2', 'tmnanosem2plus', 'tmnanosecombo', 'vusolo'):
		detected = False
	else:
		detected = eDBoxLCD.getInstance().detected()

	ilcd = LCD()

	SystemInfo["Display"] = detected
	config.lcd = ConfigSubsection()

	if fileExists("/proc/stb/lcd/mode"):
		f = open("/proc/stb/lcd/mode", "r")
		can_lcdmodechecking = f.read().strip().split(" ")
		print 'LCDMiniTV',can_lcdmodechecking
		f.close()
	else:
		can_lcdmodechecking = False

 	if SystemInfo["StandbyLED"]:
		def setLEDstandby(configElement):
			ilcd.setLEDStandby(configElement.value)
		config.usage.standbyLED = ConfigYesNo(default = True)
		config.usage.standbyLED.addNotifier(setLEDstandby)

	if SystemInfo["LEDButtons"]:
		def setLEDnormalstate(configElement):
			ilcd.setLEDNormalState(configElement.value)

		def setLEDdeepstandby(configElement):
			ilcd.setLEDDeepStandbyState(configElement.value)

		def setLEDblinkingtime(configElement):
			ilcd.setLEDBlinkingTime(configElement.value)

		config.lcd.ledblinkingtime = ConfigSlider(default = 5, increment = 1, limits = (0,15))
		config.lcd.ledblinkingtime.addNotifier(setLEDblinkingtime)
		config.lcd.ledbrightnessdeepstandby = ConfigSlider(default = 1, increment = 1, limits = (0,15))
		config.lcd.ledbrightnessdeepstandby.addNotifier(setLEDnormalstate)
		config.lcd.ledbrightnessdeepstandby.addNotifier(setLEDdeepstandby)
		config.lcd.ledbrightnessdeepstandby.apply = lambda : setLEDdeepstandby(config.lcd.ledbrightnessdeepstandby)
		config.lcd.ledbrightnessstandby = ConfigSlider(default = 1, increment = 1, limits = (0,15))
		config.lcd.ledbrightnessstandby.addNotifier(setLEDnormalstate)
		config.lcd.ledbrightnessstandby.apply = lambda : setLEDnormalstate(config.lcd.ledbrightnessstandby)
		config.lcd.ledbrightness = ConfigSlider(default = 3, increment = 1, limits = (0,15))
		config.lcd.ledbrightness.addNotifier(setLEDnormalstate)
		config.lcd.ledbrightness.apply = lambda : setLEDnormalstate(config.lcd.ledbrightness)
		config.lcd.ledbrightness.callNotifiersOnSaveAndCancel = True

	if detected:
		config.lcd.scroll_speed = ConfigSelection(default = "300", choices = [
			("500", _("slow")),
			("300", _("normal")),
			("100", _("fast"))])
		config.lcd.scroll_delay = ConfigSelection(default = "10000", choices = [
			("10000", "10 " + _("seconds")),
			("20000", "20 " + _("seconds")),
			("30000", "30 " + _("seconds")),
			("60000", "1 " + _("minute")),
			("300000", "5 " + _("minutes")),
			("noscrolling", _("off"))])

		def setLCDbright(configElement):
			ilcd.setBright(configElement.value);

		def setLCDstandbybright(configElement):
			ilcd.setStandbyBright(configElement.value);

		def setLCDdimbright(configElement):
			ilcd.setDimBright(configElement.value);

		def setLCDdimdelay(configElement):
			ilcd.setDimDelay(configElement.value);

		def setLCDcontrast(configElement):
			ilcd.setContrast(configElement.value)

		def setLCDinverted(configElement):
			ilcd.setInverted(configElement.value)

		def setLCDflipped(configElement):
			ilcd.setFlipped(configElement.value)

		def setLCDmode(configElement):
			ilcd.setMode(configElement.value)

		def setLCDpower(configElement):
			ilcd.setPower(configElement.value);

		def setLCDminitvmode(configElement):
			ilcd.setLCDMiniTVMode(configElement.value)

		def setLCDminitvpipmode(configElement):
			ilcd.setLCDMiniTVPIPMode(configElement.value)

		def setLCDminitvfps(configElement):
			ilcd.setLCDMiniTVFPS(configElement.value)

		standby_default = 0

		if not ilcd.isOled():
			config.lcd.contrast = ConfigSlider(default=5, limits=(0, 20))
			config.lcd.contrast.addNotifier(setLCDcontrast)
		else:
			config.lcd.contrast = ConfigNothing()
			standby_default = 1

		config.lcd.standby = ConfigSlider(default=standby_default, limits=(0, 10))
		config.lcd.standby.addNotifier(setLCDbright)
		config.lcd.standby.apply = lambda : setLCDbright(config.lcd.standby)

		config.lcd.bright = ConfigSlider(default=5, limits=(0, 10))
		config.lcd.bright.addNotifier(setLCDbright)
		config.lcd.bright.apply = lambda : setLCDbright(config.lcd.bright)
		config.lcd.bright.callNotifiersOnSaveAndCancel = True

		config.lcd.dimbright = ConfigSlider(default=standby_default, limits=(0, 10))
		config.lcd.dimbright.addNotifier(setLCDdimbright);
		config.lcd.dimbright.apply = lambda : setLCDdimbright(config.lcd.dimbright)
		config.lcd.dimdelay = ConfigSelection(default = "0", choices = [
			("5", "5 " + _("seconds")),
			("10", "10 " + _("seconds")),
			("15", "15 " + _("seconds")),
			("20", "20 " + _("seconds")),
			("30", "30 " + _("seconds")),
			("60", "1 " + _("minute")),
			("120", "2 " + _("minutes")),
			("300", "5 " + _("minutes")),
			("0", _("off"))])
		config.lcd.dimdelay.addNotifier(setLCDdimdelay);

		config.lcd.invert = ConfigYesNo(default=False)
		config.lcd.invert.addNotifier(setLCDinverted)

		def PiconPackChanged(configElement):
			configElement.save()
		config.lcd.picon_pack = ConfigYesNo(default=False)
		config.lcd.picon_pack.addNotifier(PiconPackChanged)

		config.lcd.flip = ConfigYesNo(default=False)
		config.lcd.flip.addNotifier(setLCDflipped)

		if SystemInfo["LcdLiveTV"]:
			def lcdLiveTvChanged(configElement):
				setLCDLiveTv(configElement.value)
				configElement.save()
			config.lcd.showTv = ConfigYesNo(default = False)
			config.lcd.showTv.addNotifier(lcdLiveTvChanged)

			if "live_enable" in SystemInfo["LcdLiveTV"]:
				config.misc.standbyCounter.addNotifier(standbyCounterChangedLCDLiveTV, initial_call = False)

		if SystemInfo["LCDMiniTV"] and getBoxType() not in ('gbquad4k', 'gbue4k'):
			config.lcd.minitvmode = ConfigSelection([("0", _("normal")), ("1", _("MiniTV")), ("2", _("OSD")), ("3", _("MiniTV with OSD"))], "0")
			config.lcd.minitvmode.addNotifier(setLCDminitvmode)
			config.lcd.minitvpipmode = ConfigSelection([("0", _("off")), ("5", _("PIP")), ("7", _("PIP with OSD"))], "0")
			config.lcd.minitvpipmode.addNotifier(setLCDminitvpipmode)
			config.lcd.minitvfps = ConfigSlider(default=30, limits=(0, 30))
			config.lcd.minitvfps.addNotifier(setLCDminitvfps)
		elif can_lcdmodechecking and getBoxType() in ('gbquad4k', 'gbue4k'):
			#  (0:normal, 1:video0, 2:fb, 3:vide0+fb, 4:video1, 5:vide0+video1, 6:video1+fb, 7:video0+video1+fb)
			config.lcd.minitvmode = ConfigSelection(default = "0", choices=[
					("0", _("normal")),
					("1", _("MiniTV") + _(" - video0")),
					("3", _("MiniTV with OSD") + _(" - video0")),
					("2", _("OSD")),
					("4", _("MiniTV") + _(" - video1")),
					("6", _("MiniTV with OSD") + _(" - video1")),
					("5", _("MiniTV") + _(" - video0+video1")),
					("7", _("MiniTV with OSD") + _(" - video0+video1"))])
			config.lcd.minitvmode.addNotifier(setLCDminitvmode)
			config.lcd.minitvpipmode = ConfigSelection(default = "0", choices=[
					("0", _("off")),
					("4", _("PIP")),
					("6", _("PIP with OSD"))])
			config.lcd.minitvpipmode.addNotifier(setLCDminitvpipmode)
			config.lcd.minitvfps = ConfigSlider(default=30, limits=(0, 30))
			config.lcd.minitvfps.addNotifier(setLCDminitvfps)
		else:
			config.lcd.minitvmode = ConfigNothing()
			config.lcd.minitvpipmode = ConfigNothing()
			config.lcd.minitvfps = ConfigNothing()

		if SystemInfo["VFD_scroll_repeats"] and getDisplayType() not in ('7segment'):
			def scroll_repeats(el):
				open(SystemInfo["VFD_scroll_repeats"], "w").write(el.value)
			choicelist = [("0", _("None")), ("1", _("1X")), ("2", _("2X")), ("3", _("3X")), ("4", _("4X")), ("500", _("Continues"))]
			config.usage.vfd_scroll_repeats = ConfigSelection(default = "3", choices = choicelist)
			config.usage.vfd_scroll_repeats.addNotifier(scroll_repeats, immediate_feedback = False)

		if SystemInfo["VFD_scroll_delay"] and getDisplayType() not in ('7segment'):
			def scroll_delay(el):
				open(SystemInfo["VFD_scroll_delay"], "w").write(str(el.value))
			config.usage.vfd_scroll_delay = ConfigSlider(default = 150, increment = 10, limits = (0, 500))
			config.usage.vfd_scroll_delay.addNotifier(scroll_delay, immediate_feedback = False)

		if SystemInfo["VFD_initial_scroll_delay"] and getDisplayType() not in ('7segment'):
			def initial_scroll_delay(el):
				open(SystemInfo["VFD_initial_scroll_delay"], "w").write(el.value)
			choicelist = [
			("10000", "10 " + _("seconds")),
			("20000", "20 " + _("seconds")),
			("30000", "30 " + _("seconds")),
			("0", _("no delay"))]
			config.usage.vfd_initial_scroll_delay = ConfigSelection(default = "1000", choices = choicelist)
			config.usage.vfd_initial_scroll_delay.addNotifier(initial_scroll_delay, immediate_feedback = False)

		if SystemInfo["VFD_final_scroll_delay"] and getDisplayType() not in ('7segment'):
			def final_scroll_delay(el):
				open(SystemInfo["VFD_final_scroll_delay"], "w").write(el.value)
			choicelist = [
			("10000", "10 " + _("seconds")),
			("20000", "20 " + _("seconds")),
			("30000", "30 " + _("seconds")),
			("0", _("no delay"))]
			config.usage.vfd_final_scroll_delay = ConfigSelection(default = "1000", choices = choicelist)
			config.usage.vfd_final_scroll_delay.addNotifier(final_scroll_delay, immediate_feedback = False)

		if fileExists("/proc/stb/lcd/show_symbols"):
			config.lcd.mode = ConfigSelection([("0", _("no")), ("1", _("yes"))], "1")
			config.lcd.mode.addNotifier(setLCDmode)
		else:
			config.lcd.mode = ConfigNothing()

		if fileExists("/proc/stb/power/vfd"):
			config.lcd.power = ConfigSelection([("0", _("off")), ("1", _("on"))], "1")
			config.lcd.power.addNotifier(setLCDpower);
		else:
			config.lcd.power = ConfigNothing()

	else:
		def doNothing():
			pass
		config.lcd.contrast = ConfigNothing()
		config.lcd.bright = ConfigNothing()
		config.lcd.standby = ConfigNothing()
		config.lcd.bright.apply = lambda : doNothing()
		config.lcd.standby.apply = lambda : doNothing()
		config.lcd.mode = ConfigNothing()
		config.lcd.power = ConfigNothing()
		config.lcd.ledbrightness = ConfigNothing()
		config.lcd.ledbrightness.apply = lambda : doNothing()
		config.lcd.ledbrightnessstandby = ConfigNothing()
		config.lcd.ledbrightnessstandby.apply = lambda : doNothing()
		config.lcd.ledbrightnessdeepstandby = ConfigNothing()
		config.lcd.ledbrightnessdeepstandby.apply = lambda : doNothing()
		config.lcd.ledblinkingtime = ConfigNothing()
		config.lcd.picon_pack = ConfigNothing()

	config.misc.standbyCounter.addNotifier(standbyCounterChanged, initial_call = False)

def setLCDLiveTv(value):
	if "live_enable" in SystemInfo["LcdLiveTV"]:
		open(SystemInfo["LcdLiveTV"], "w").write(value and "enable" or "disable")
	else:
		open(SystemInfo["LcdLiveTV"], "w").write(value and "0" or "1")
	try:
		InfoBarInstance = InfoBar.instance
		InfoBarInstance and InfoBarInstance.session.open(dummyScreen)
	except:
		pass

def leaveStandbyLCDLiveTV():
	if config.lcd.showTv.value:
		setLCDLiveTv(True)

def standbyCounterChangedLCDLiveTV(dummy):
	if config.lcd.showTv.value:
		from Screens.Standby import inStandby
		if leaveStandbyLCDLiveTV not in inStandby.onClose:
			inStandby.onClose.append(leaveStandbyLCDLiveTV)
		setLCDLiveTv(False)
