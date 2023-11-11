from enigma import eTimer


from Components.ActionMap import HelpableActionMap
from Components.config import config
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Screens.MessageBox import MessageBox
from Screens.Setup import Setup
from Tools.camcontrol import CamControl
from Tools.Directories import fileExists
from Tools.GetEcmInfo import GetEcmInfo


class SoftcamScript(Setup):
	def __init__(self, session):
		self.softcam = CamControl("softcam")
		self.ecminfo = GetEcmInfo()
		config.misc.softcams.value == ""
		Setup.__init__(self, session=session, setup="softcamscriptsetup")
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["restartActions"] = HelpableActionMap(self, ["ColorActions"], {
			"yellow": (self.restart, _("Immediately restart selected cams."))
		}, prio=0, description=_("Softcam Actions"))
		self["restartActions"].setEnabled(False)
		self["infoActions"] = HelpableActionMap(self, ["ColorActions"], {
			"blue": (self.softcamInfo, _("Display oscam information."))
		}, prio=0, description=_("Softcam Actions"))
		self["infoActions"].setEnabled(False)
		(newEcmFound, ecmInfo) = self.ecminfo.getEcm()
		self["info"] = ScrollLabel("".join(ecmInfo))
		self.EcmInfoPollTimer = eTimer()
		self.EcmInfoPollTimer.callback.append(self.setEcmInfo)
		self.EcmInfoPollTimer.start(1000)
		self.onShown.append(self.updateButtons)

	def selectionChanged(self):
		self.updateButtons()
		Setup.selectionChanged(self)

	def changedEntry(self):
		self.updateButtons()
		Setup.changedEntry(self)

	def keySave(self):
		camtype = ""
		print("[SoftcamSetup][keySave] self.softcam.current=%s config.misc.softcams.value=%s" % (self.softcam.current(), config.misc.softcams.value))
		if config.misc.softcams.value != self.softcam.current():
			camtype = "s"
		if camtype:
			self.restart(camtype="e%s" % camtype)
		else:
			Setup.keySave(self)

	def keyCancel(self):
		Setup.keyCancel(self)

	def updateButtons(self):
		if config.misc.softcamrestarts.value:
			self["key_yellow"].setText(_("Restart"))
			self["restartActions"].setEnabled(True)
		else:
			self["key_yellow"].setText("")
			self["restartActions"].setEnabled(False)
		self["key_blue"].setText("")
		self["infoActions"].setEnabled(False)
		if self["config"].getCurrent() == config.misc.softcams and config.misc.softcams.value and config.misc.softcams.value.lower() != "none":
			self["key_blue"].setText(_("Info"))
			self["infoActions"].setEnabled(True)

	def softcamInfo(self):
		if "oscam" in config.misc.softcams.value.lower() and fileExists('/usr/lib/enigma2/python/Screens/OScamInfo.py'):
			from Screens.OScamInfo import OscamInfoMenu
			self.session.open(OscamInfoMenu)
		elif "cccam" in config.misc.softcams.lower() and fileExists('/usr/lib/enigma2/python/Screens/CCcamInfo.py'):
			from Screens.CCcamInfo import CCcamInfoMain
			self.session.open(CCcamInfoMain)

	def setEcmInfo(self):
		(newEcmFound, ecmInfo) = self.ecminfo.getEcm()
		if newEcmFound:
			self["info"].setText("".join(ecmInfo))

	def restart(self, camtype=None):
		print("[SoftcamSetup][restart] config.misc.softcamrestarts.value=%s camtype=%s" % (config.misc.softcamrestarts.value, camtype))
		self.camtype = config.misc.softcamrestarts.value if camtype is None else camtype
		print("[SoftcamSetup][restart] self.camtype=%s" % self.camtype)
		msg = []
		if "s" in self.camtype:
			msg.append(_("softcam"))
		msg = (" %s " % _("and")).join(msg)
		self.mbox = self.session.open(MessageBox, _("Please wait, initialising %s.") % msg, MessageBox.TYPE_INFO)
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.doStop)
		self.activityTimer.start(100, False)

	def doStop(self):
		self.activityTimer.stop()
		self.softcam.command("stop")
		self.oldref = self.session.nav.getCurrentlyPlayingServiceOrGroup()
		self.session.nav.stopService()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.doStart)
		self.activityTimer.start(1000, False)

	def doStart(self):
		self.activityTimer.stop()
		print("[SoftcamSetup][doStart1] self.camtype=%s config.misc.softcams.value=%s" % (self.camtype, config.misc.softcams.value))
		configs = self.softcam.getConfigs(config.misc.softcams.value)
		if len(configs) < 4 and config.misc.softcams.value != "None":
			msg = _("No configs for specifies softcam %s." % config.misc.softcams.value)
			self.mbox = self.session.open(MessageBox, msg, MessageBox.TYPE_INFO)
			self.camtype = "None"
		self.softcam.select(config.misc.softcams.value)
		if config.misc.softcams.value != "None":
			self.softcam.command("start")
			print("[SoftcamSetup][doStart2] self.camtype=%s config.misc.softcams.value=%s" % (self.camtype, config.misc.softcams.value))
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.dofinish)
		self.activityTimer.start(1000, False)

	def dofinish(self):
		self.activityTimer.stop()
		del self.activityTimer
		if self.mbox:
			self.mbox.close()
		self.session.nav.playService(self.oldref, adjust=False)
		if self.camtype == "None" or "e" in self.camtype:
			Setup.keySave(self)

	def restartSoftcam(self):
		self.restart(device="s")
