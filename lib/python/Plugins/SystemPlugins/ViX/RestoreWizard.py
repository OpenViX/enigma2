from os import listdir, path, stat

from Components.config import config
from Components.Console import Console
from Components.Pixmap import Pixmap
from Components.SystemInfo import SystemInfo, DISPLAYBRAND, MACHINENAME
from Screens.MessageBox import MessageBox
from Screens.Rc import Rc
from Screens.WizardLanguage import WizardLanguage
from Tools.Directories import fileHas, resolveFilename, SCOPE_PLUGINS
from Tools.Multiboot import bootmviSlot, createInfo


class RestoreWizard(WizardLanguage, Rc):
	def __init__(self, session):
		self.xmlfile = resolveFilename(SCOPE_PLUGINS, "SystemPlugins/ViX/restorewizard.xml")
		WizardLanguage.__init__(self, session, showSteps=False, showStepSlider=False)
		Rc.__init__(self)
		self.session = session
		self.skinName = "StartWizard"
		self.skin = "StartWizard.skin"
		self["wizard"] = Pixmap()
		self.selectedAction = None
		self.NextStep = None
		self.Text = None
		self.buildListRef = None
		self.didSettingsRestore = False
		self.didPluginRestore = False
		self.PluginsRestore = False
		self.fullbackupfilename = None
		self.delaymess = None
		self.selectedDevice = None
		self.Console = Console()
		self.ConsoleB = Console(binary=True)

	def getTranslation(self, text):
		return _(text).replace("%s %s", "%s %s" % (DISPLAYBRAND, MACHINENAME))

	def listDevices(self):
		devmounts = []
		list = []
		files = []
		mtimes = []
		defaultprefix = SystemInfo["distro"][4:]

		for dir in ["/media/%s/backup" % media for media in listdir("/media/") if path.isdir(path.join("/media/", media))]:  # noqa: F821
			devmounts.append(dir)
		if len(devmounts):
			for devpath in devmounts:
				if path.exists(devpath):
					try:
						files = listdir(devpath)
					except:
						files = []
				else:
					files = []
				if len(files):
					for file in files:
						if file.endswith(".tar.gz") and "vix" in file.lower() or file.startswith("%s" % defaultprefix):
							mtimes.append((path.join(devpath, file), stat(path.join(devpath, file)).st_mtime))  # (filname, mtime)
		for file in [x[0] for x in sorted(mtimes, key=lambda x: x[1], reverse=True)]:  # sort by mtime
			list.append((file, file))
		return list

	def settingsdeviceSelectionMade(self, index):
		self.selectedAction = index
		self.settingsdeviceSelect(index)

	def settingsdeviceSelect(self, index):
		self.selectedDevice = index
		self.fullbackupfilename = index
		self.NextStep = "settingrestorestarted"

	def settingsdeviceSelectionMoved(self):
		self.settingsdeviceSelect(self.selection)

	def pluginsdeviceSelectionMade(self, index):
		self.selectedAction = index
		self.pluginsdeviceSelect(index)

	def pluginsdeviceSelect(self, index):
		self.selectedDevice = index
		self.fullbackupfilename = index
		self.NextStep = "plugindetection"

	def pluginsdeviceSelectionMoved(self):
		self.pluginsdeviceSelect(self.selection)

	def markDone(self):
		pass

	def listAction(self):
		list = [(_("OK, to perform a restore"), "settingsquestion"), (_("Exit the restore wizard"), "end")]
		return list

	def listAction2(self):
		list = [(_("YES, to restore settings"), "settingsrestore"), (_("NO, do not restore settings"), "pluginsquestion")]
		return list

	def listAction3(self):
		list = []
		if self.didSettingsRestore:
			list.append((_("YES, to restore plugins"), "pluginrestore"))
			list.append((_("NO, do not restore plugins"), "reboot"))
		else:
			list.append((_("YES, to restore plugins"), "pluginsrestoredevice"))
			list.append((_("NO, do not restore plugins"), "end"))
		return list

	def rebootAction(self):
		list = [(_("OK"), "reboot")]
		return list

	def ActionSelectionMade(self, index):
		self.selectedAction = index
		self.ActionSelect(index)

	def ActionSelect(self, index):
		self.NextStep = index

	def ActionSelectionMoved(self):
		self.ActionSelect(self.selection)

	def buildList(self, action):
		if self.NextStep == "reboot":
			if fileHas("/proc/cmdline", "kexec=1") and config.usage.bootlogo_identify.value:
				slot = SystemInfo["MultiBootSlot"]
				text = createInfo(slot)
				bootmviSlot(text=text, slot=slot)
			if self.didSettingsRestore:
				self.Console.ePopen("tar -xzvf " + self.fullbackupfilename + " -C /" + " etc/enigma2/settings")
			self.Console.ePopen("killall -9 enigma2 && init 6")
		elif self.NextStep == "settingsquestion" or self.NextStep == "settingsrestore" or self.NextStep == "pluginsquestion" or self.NextStep == "pluginsrestoredevice" or self.NextStep == "end" or self.NextStep == "noplugins":
			self.buildListfinishedCB(False)
		elif self.NextStep == "settingrestorestarted":
			self.Console.ePopen("tar -xzvf " + self.fullbackupfilename + " -C / tmp/ExtraInstalledPlugins", self.settingsRestore_Started)
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Please wait while the system gathers information..."), type=MessageBox.TYPE_INFO, enable_input=False, wizard=True)
			self.buildListRef.setTitle(_("Restore wizard"))
		elif self.NextStep == "plugindetection":
			print("[RestoreWizard] Stage 2: Restoring plugins")
			self.Console.ePopen("tar -xzvf " + self.fullbackupfilename + "  -C / tmp/ExtraInstalledPlugins", self.pluginsRestore_Started)
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Please wait while the system gathers information..."), type=MessageBox.TYPE_INFO, enable_input=False, wizard=True)
			self.buildListRef.setTitle(_("Restore wizard"))
		elif self.NextStep == "pluginrestore":
			if self.feeds == "OK":
				print("[RestoreWizard] Stage 6: Feeds OK, Restoring Plugins")
				self.index = 0
				self.pluginslistcombined = self.pluginslist + self.pluginslist2
				print(f"[RestoreWizard] Stage 6: Plugins:{self.pluginslistcombined}")
				self.installNextPackage()
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Please wait while plugins restore completes..."), type=MessageBox.TYPE_INFO, enable_input=False, wizard=True)
				self.buildListRef.setTitle(_("Restore wizard"))
			elif self.feeds == "DOWN":
				print("[RestoreWizard] Stage 6: Feeds Down")
				self.didPluginRestore = True
				self.NextStep = "reboot"
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Sorry the feeds are down for maintenance. Please try using Backup manager to restore plugins later."), type=MessageBox.TYPE_INFO, timeout=30, wizard=True)
				self.buildListRef.setTitle(_("Restore wizard"))
			elif self.feeds == "BAD":
				print("[RestoreWizard] Stage 6: No Network")
				self.didPluginRestore = True
				self.NextStep = "reboot"
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Your %s %s is not connected to the Internet. Please try using Backup manager to restore plugins later.") % (DISPLAYBRAND, MACHINENAME), type=MessageBox.TYPE_INFO, timeout=30, wizard=True)
				self.buildListRef.setTitle(_("Restore wizard"))
			elif self.feeds == "ERROR":
				self.NextStep = "pluginrestore"
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("A background update check is in progress, please try again."), type=MessageBox.TYPE_INFO, timeout=10, wizard=True)
				self.buildListRef.setTitle(_("Restore wizard"))

	def buildListfinishedCB(self, data):
		# self.buildListRef = None
		if data is True:
			self.currStep = self.getStepWithID(self.NextStep)
			self.afterAsyncCode()
		else:
			self.currStep = self.getStepWithID(self.NextStep)
			self.afterAsyncCode()

	def settingsRestore_Started(self, result, retval, extra_args=None):
		print("[RestoreWizard] Stage 2: Restoring settings")
		self.Console.ePopen("tar -xzvf " + self.fullbackupfilename + " -C /", self.settingRestore_Finished)
		self.pleaseWait = self.session.open(MessageBox, _("Please wait while settings restore completes..."), type=MessageBox.TYPE_INFO, enable_input=False, wizard=True)
		self.pleaseWait.setTitle(_("Restore wizard"))

	def settingRestore_Finished(self, result, retval, extra_args=None):
		self.didSettingsRestore = True
		# network = [x.split(" ")[3] for x in open("/etc/network/interfaces").read().splitlines() if x.startswith("iface eth0")]  # what is this?
		self.pleaseWait.close()
		self.doRestorePluginsTest()

	def pluginsRestore_Started(self, result, retval, extra_args=None):
		self.doRestorePluginsTest()

	def pluginsRestore_Finished(self):
		self.didPluginRestore = True
		self.NextStep = "reboot"
		self.buildListRef.close(True)

	def installNextPackage(self):
		cmd = "opkg install " + self.pluginslistcombined[self.index]
		print(f"[RestoreWizard][installNextPackage] Console command:{cmd} index:{self.index}")
		self.ConsoleB.ePopen(cmd, self.packageInstalled)

	def packageInstalled(self, result, retval, extra_args):
		if result:
			print("[RestoreWizard][packageInstalled] opkg install result:\n", result.decode(errors="ignore"))
		self.index += 1
		if self.index < len(self.pluginslistcombined):
			self.installNextPackage()
		else:
			print("[RestoreWwizard][packageInstalled] Plugin restore finished")
			self.pluginsRestore_Finished()

	def doRestorePluginsTest(self):
		if self.delaymess:
			self.delaymess.close()
		print("[RestoreWizard] Stage 4: Feeds Test")
		self.Console.ePopen("opkg update", self.doRestorePluginsTestComplete)

	def doRestorePluginsTestComplete(self, result='', retval=None, extra_args=None):
		print("[RestoreWizard] Stage 4: Feeds Test Result", result)
		if result.find("wget returned 4") != -1:
			self.NextStep = "reboot"
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Your %s %s is not connected to a network. Please try using the Backup manager to restore plugins later when a network connection is available.") % (DISPLAYBRAND, MACHINENAME), type=MessageBox.TYPE_INFO, timeout=30, wizard=True)
			self.buildListRef.setTitle(_("Restore wizard"))
		elif result.find("wget returned 8") != -1:
			self.NextStep = "reboot"
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Your %s %s could not connect to the plugin feeds at this time. Please try using the Backup manager to restore plugins later.") % (DISPLAYBRAND, MACHINENAME), type=MessageBox.TYPE_INFO, timeout=30, wizard=True)
			self.buildListRef.setTitle(_("Restore wizard"))
		elif result.find("bad address") != -1:
			self.NextStep = "reboot"
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Your %s %s is not connected to the Internet. Please try using the Backup manager to restore plugins later.") % (DISPLAYBRAND, MACHINENAME), type=MessageBox.TYPE_INFO, timeout=30, wizard=True)
			self.buildListRef.setTitle(_("Restore wizard"))
		elif result.find("wget returned 1") != -1 or result.find("wget returned 255") != -1 or result.find("404 Not Found") != -1:
			self.NextStep = "reboot"
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Sorry the feeds are down for maintenance. Please try using the Backup manager to restore plugins later."), type=MessageBox.TYPE_INFO, timeout=30, wizard=True)
			self.buildListRef.setTitle(_("Restore wizard"))
		elif result.find("Collected errors") != -1:
			print("[RestoreWizard] Stage 4: Update is in progress, delaying")
			self.delaymess = self.session.openWithCallback(self.doRestorePluginsTest, MessageBox, _("A background update check is in progress, please try again."), type=MessageBox.TYPE_INFO, timeout=10, wizard=True)
			self.delaymess.setTitle(_("Restore wizard"))
		else:
			print("[RestoreWizard] Stage 4: Feeds OK")
			self.feeds = "OK"
			self.doListPlugins()

	def doListPlugins(self):
		print("[RestoreWizard] Stage 4: Feeds Test")
		self.Console.ePopen("opkg list", self.doListPlugins2)

	def doListPlugins2(self, result, retval, extra_args):
		self.opkg_available_packages = {p.split()[0] for line in result.split("\n") if (p := line.strip())}  # list of all packages available from the feeds
		self.Console.ePopen("opkg list-installed", self.doRestorePlugins2)

	def doRestorePlugins2(self, result, retval, extra_args):
		print("[RestoreWizard] Stage 5: Build list of plugins to restore")
		self.pluginslist = []
		self.pluginslist2 = []
		opkg_installed_packages = {p.split()[0] for line in result.split("\n") if (p := line.strip())}
		if path.exists("/tmp/ExtraInstalledPlugins"):
			with open("/tmp/ExtraInstalledPlugins", "r") as fd:
				self.pluginslist = [p for line in fd.readlines() if (p := line.strip()) and p in self.opkg_available_packages and p not in opkg_installed_packages]
		# print(f"[RestoreWizard] self.pluginslist:{self.pluginslist}")
		if path.exists("/tmp/3rdPartyPlugins"):
			thirdpartyPluginsLocation = ""
			if path.exists("/tmp/3rdPartyPluginsLocation"):
				with open("/tmp/3rdPartyPluginsLocation", "r") as fd:
					thirdpartyPluginsLocation = fd.readline().strip()
					# print("[RestoreWizard] Restoring Stage 3: thirdpartyPluginsLocation from file", "'%s'" % thirdpartyPluginsLocation)
			thirdpartyPluginsLocation = thirdpartyPluginsLocation.replace(" ", "%20")  # What is this replace for?
			with open("/tmp/3rdPartyPlugins", "r") as fd:
				tmppluginslist2 = [package.split("_")[0] for line in fd.readlines() if (package := line.strip())]  # ".split("_")[0]" should be redundant if the input is correct
			relative_path = len(x := thirdpartyPluginsLocation.split("/", 3)) > 3 and x[3] or None  # expects thirdpartyPluginsLocation to be in the format /media/something/myFolder
			devmounts = relative_path and ["/media/%s/%s" % (media, relative_path) for media in listdir("/media/") if media not in ("autofs", "net") and path.isdir(path.join("/media/", media)) and path.exists("/media/%s/%s" % (media, relative_path))]
			print("[RestoreWizard] search dir = %s" % str(devmounts))
			for ipk in tmppluginslist2:
				available = []
				if ipk not in opkg_installed_packages:
					if thirdpartyPluginsLocation and path.exists(thirdpartyPluginsLocation):
						available = sorted([y for y in listdir(thirdpartyPluginsLocation) if y.startswith(ipk)], reverse=True)  # sort for most recent by name if multiple versions
					elif devmounts:
						for x in devmounts:
							try:  # Why is this try/except needed? What exception is it protecting against?
								available = sorted([y for y in listdir(x) if y.startswith(ipk)], reverse=True)  # sort for most recent by name if multiple versions
								print("[RestoreWizard] Restoring Stage 3: 3rdPartyPlugin found", x, available)
								thirdpartyPluginsLocation = x
								break
							except Exception as e:
								print("[RestoreWizard] Restoring Stage 3: exception trying to access 3rdPartyPlugin location:", x, "\n", e)
								continue
					if available:
						self.pluginslist2.append(path.join(thirdpartyPluginsLocation, available[0]))
						if ipk in self.pluginslist:
							self.pluginslist.remove(ipk)  # local version takes priority
		# print(f"[RestoreWizard] self.pluginslist:{self.pluginslist} self.pluginslist2:{self.pluginslist2}")
		if self.pluginslist or self.pluginslist2:
			self.doRestorePluginsQuestion()
		else:
			if self.didSettingsRestore:
				self.NextStep = "reboot"
			else:
				self.NextStep = "noplugins"
			self.buildListRef.close(True)

	def doRestorePluginsQuestion(self):
		if self.pluginslist or self.pluginslist2:
			print("[RestoreWizard] Stage 6: Plugins to restore in feeds", self.pluginslist)
			print("[RestoreWizard] Stage 6: Plugins to restore in extra location", self.pluginslist2)
			if self.didSettingsRestore:
				print("[RestoreWizard] Stage 6: proceed to question")
				self.NextStep = "pluginsquestion"
				self.buildListRef.close(True)
			else:
				print("[RestoreWizard] Stage 6: proceed to restore")
				self.NextStep = "pluginrestore"
				self.buildListRef.close(True)
		else:
			print("[RestoreWizard] Stage 6: NO Plugins to restore")
			if self.didSettingsRestore:
				self.NextStep = "reboot"
			else:
				self.NextStep = "noplugins"
		self.buildListRef.close(True)
