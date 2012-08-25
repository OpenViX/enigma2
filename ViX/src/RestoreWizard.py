# for localized messages
from . import _
from Components.About import about
from Components.Console import Console
from Components.config import config, configfile
from Components.Pixmap import Pixmap, MovingPixmap, MultiPixmap
from Components.Harddisk import harddiskmanager
from Screens.Wizard import wizardManager, WizardSummary
from Screens.WizardLanguage import WizardLanguage
from Screens.Rc import Rc
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists, pathExists, resolveFilename, SCOPE_PLUGINS
from os import mkdir, listdir, path

class RestoreWizard(WizardLanguage, Rc):
	def __init__(self, session):
		self.xmlfile = resolveFilename(SCOPE_PLUGINS, "SystemPlugins/ViX/restorewizard.xml")
		WizardLanguage.__init__(self, session, showSteps = False, showStepSlider = False)
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
		self.Console = Console()

	def listDevices(self):
		devices = [ (r.description, r.mountpoint) for r in harddiskmanager.getMountedPartitions(onlyhotplug = False)]
		list = []
		for x in devices:
			if x[1] == '/':
				devices.remove(x)
		if len(devices):
			for x in devices:
				images = ""
				if path.exists(path.join(x[1],'backup')):
					images = listdir(path.join(x[1],'backup'))
				print '[Restorewizard] FILES:', images
				if len(images):
					for fil in images:
						if fil.endswith('.tar.gz'):
							dir = path.join(x[1],'backup')
							list.append((path.join(dir,fil),path.join(dir,fil)))
				print '[Restorewizard] LIST:', list
		if len(list):
			list.sort()
			list.reverse()
		return list

	def settingsdeviceSelectionMade(self, index):
		self.selectedAction = index
		self.settingsdeviceSelect(index)

	def settingsdeviceSelect(self, index):
		self.selectedDevice = index
		self.fullbackupfilename = index
 		self.NextStep = 'settingrestorestarted'

	def settingsdeviceSelectionMoved(self):
		self.settingsdeviceSelect(self.selection)

	def pluginsdeviceSelectionMade(self, index):
		self.selectedAction = index
		self.pluginsdeviceSelect(index)

	def pluginsdeviceSelect(self, index):
		self.selectedDevice = index
		self.fullbackupfilename = index
 		self.NextStep = 'plugindetection'

	def pluginsdeviceSelectionMoved(self):
		self.pluginsdeviceSelect(self.selection)

	def markDone(self):
		pass

	def listAction(self):
		list = []
		list.append((_("OK, to perform a restore"), "settingsquestion"))
		list.append((_("Exit the restore wizard"), "end"))
		return list

	def listAction2(self):
		list = []
		list.append((_("YES, to restore settings"), "settingsrestore"))
		list.append((_("NO, do not restore settings"), "pluginsquestion"))
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
		list = []
		list.append((_("OK"), "reboot"))
		return list

	def ActionSelectionMade(self, index):
		self.selectedAction = index
		self.ActionSelect(index)

	def ActionSelect(self, index):
		self.NextStep = index

	def ActionSelectionMoved(self):
		self.ActionSelect(self.selection)

	def buildList(self,action):
		print 'self.NextStep ',self.NextStep
		if self.NextStep is 'reboot':
			if not self.Console:
				self.Console = Console()
			self.Console.ePopen("init 4 && reboot")
		elif self.NextStep is 'settingsquestion' or self.NextStep is 'settingsrestore' or self.NextStep is 'pluginsquestion' or self.NextStep is 'pluginsrestoredevice' or self.NextStep is 'end' or self.NextStep is 'noplugins':
			self.buildListfinishedCB(False)
		elif self.NextStep is 'settingrestorestarted':
			if not self.Console:
				self.Console = Console()
			self.Console.ePopen("tar -xzvf " + self.fullbackupfilename + " -C /", self.settingRestore_Finished)
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Please wait while settings restore completes..."), type = MessageBox.TYPE_INFO, enable_input = False)
			self.buildListRef.setTitle(_("Restore Wizard"))
		elif self.NextStep is 'plugindetection':
			if not self.Console:
				self.Console = Console()
			print '[RestoreWizard] Stage 1: Restoring settings'
			self.Console.ePopen("tar -xzvf " + self.fullbackupfilename + " tmp/ExtraInstalledPlugins tmp/backupkernelversion -C /", self.pluginsRestore_Started)
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Please wait while gathers infomation..."), type = MessageBox.TYPE_INFO, enable_input = False)
			self.buildListRef.setTitle(_("Restore Wizard"))
		elif self.NextStep is 'pluginrestore':
			print '[RestoreWizard] Stage 2: Restoring plugins'
			if not self.Console:
				self.Console = Console()
			plugintmp = file('/tmp/trimedExtraInstalledPlugins').read()
			pluginslist = plugintmp.replace('\n',' ')
			if self.feeds == 'OK':
				print '[RestoreWizard] Stage 6: Feeds OK, Restoring Plugins'
				self.Console.ePopen("opkg install " + pluginslist, self.pluginsRestore_Finished)
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Please wait while plugins restore completes..."), type = MessageBox.TYPE_INFO, enable_input = False)
				self.buildListRef.setTitle(_("Restore Wizard"))
			elif self.feeds == 'DOWN':
				print '[RestoreWizard] Stage 6: Feeds Down'
				config.misc.restorewizardrun.setValue(True)
				config.misc.restorewizardrun.save()
				configfile.save()
				self.didPluginRestore = True
				self.NextStep = 'reboot'
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Sorry feeds are down for maintenance, Please try using Backup Manager to restore plugins later."), type = MessageBox.TYPE_INFO, timeout = 30)
				self.buildListRef.setTitle(_("Restore Wizard"))
			elif self.feeds == 'BAD':
				print '[RestoreWizard] Stage 6: No Network'
				config.misc.restorewizardrun.setValue(True)
				config.misc.restorewizardrun.save()
				configfile.save()
				self.didPluginRestore = True
				self.NextStep = 'reboot'
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Your STB_BOX is not connected to the internet, Please try using Backup Manager to restore plugins later."), type = MessageBox.TYPE_INFO, timeout = 30)
				self.buildListRef.setTitle(_("Restore Wizard"))
			elif self.feeds == 'ERROR':
				self.NextStep = 'pluginrestore'
				self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("A background update check is is progress, please wait for retry."), type = MessageBox.TYPE_INFO, timeout = 10)
				self.buildListRef.setTitle(_("Restore Wizard"))


	def settingRestore_Finished(self, result, retval, extra_args = None):
		fstabfile = file('/etc/fstab').readlines()
		for mountfolder in fstabfile:
			parts = mountfolder.strip().split()
			if parts and str(parts[0]).startswith('UUID'):
				if not fileExists(parts[1]):
					mkdir(parts[1], 0755)

		self.didSettingsRestore = True
		configfile.load()
		self.doRestorePlugins1()

	def pluginsRestore_Started(self, result, retval, extra_args = None):
		self.doRestorePlugins1()

	def pluginsRestore_Finished(self, result, retval, extra_args = None):
		config.misc.restorewizardrun.setValue(True)
		config.misc.restorewizardrun.save()
		configfile.save()
		self.didPluginRestore = True
		self.NextStep = 'reboot'
		self.buildListRef.close(True)

	def buildListfinishedCB(self,data):
		self.buildListRef = None
		if data is True:
			self.currStep = self.getStepWithID(self.NextStep)
			self.afterAsyncCode()
		else:
			self.currStep = self.getStepWithID(self.NextStep)
			self.afterAsyncCode()

	def doRestorePlugins1(self):
		print '[RestoreWizard] Stage 2: Check Kernel'
		if fileExists('/tmp/backupkernelversion'):
			kernelversion = file('/tmp/backupkernelversion').read()
			print kernelversion
			print about.getKernelVersionString()
			if kernelversion == about.getKernelVersionString():
				print '[RestoreWizard] Stage 2: Kernel OK'
				self.doRestorePluginsTest()
		else:
			print '[RestoreWizard] Stage 2: Kernel Differant'
			if self.didSettingsRestore:
				self.NextStep = 'reboot'
			else:
				self.NextStep = 'noplugins'
			self.buildListRef.close(True)

	def doRestorePluginsTest(self):
		if self.delaymess not None:
			self.delaymess.close()
		if not self.Console:
			self.Console = Console()
		print '[RestoreWizard] Stage 3: Feeds Test'
		self.Console.ePopen('opkg update', self.doRestorePluginsTestComplete)

	def doRestorePluginsTestComplete(self, result = None, retval = None, extra_args = None):
		print '[RestoreWizard] Stage 4: Feeds Test Result',result
		if (float(about.getImageVersionString()) < 3.0 and result.find('mipsel/Packages.gz, wget returned 1') != -1) or (float(about.getImageVersionString()) >= 3.0 and result.find('mips32el/Packages.gz, wget returned 1') != -1):
			self.NextStep = 'reboot'
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Sorry feeds are down for maintenance, Please try using Backup Manager to restore plugins later."), type = MessageBox.TYPE_INFO, timeout = 30)
			self.buildListRef.setTitle(_("Restore Wizard"))
		elif result.find('bad address') != -1:
			self.NextStep = 'reboot'
			self.buildListRef = self.session.openWithCallback(self.buildListfinishedCB, MessageBox, _("Your STB_BOX is not connected to the internet, Please try using Backup Manager to restore plugins later."), type = MessageBox.TYPE_INFO, timeout = 30)
			self.buildListRef.setTitle(_("Restore Wizard"))
		elif result.find('Collected errors') != -1:
			print '[RestoreWizard] Stage 4: Update is in progress, delaying'
			self.delaymess = self.session.openWithCallback(self.doRestorePluginsTest, MessageBox, _("A background update check is is progress, please wait for retry."), type = MessageBox.TYPE_INFO, timeout = 10)
			self.delaymess.setTitle(_("Restore Wizard"))
		else:
			print '[RestoreWizard] Stage 4: Feeds OK'
			self.feeds = 'OK'
			self.doListPlugins()

	def doListPlugins(self):
		print '[RestoreWizard] Stage 4: Feeds Test'
		self.Console.ePopen('opkg list-installed', self.doRestorePlugins2)

	def doRestorePlugins2(self, result, retval, extra_args):
		print '[RestoreWizard] Stage 3: Restore Plugins'
		if fileExists('/tmp/ExtraInstalledPlugins'):
			plugins = []
			for line in result.split('\n'):
				if line:
					parts = line.strip().split()
					plugins.append(parts[0])
			output = open('/tmp/trimedExtraInstalledPlugins','w')
			pluginlist = file('/tmp/ExtraInstalledPlugins').readlines()
			for line in pluginlist:
				if line:
					parts = line.strip().split()
					if parts[0] not in plugins:
						output.write(parts[0] + ' ')
			output.close()
			self.doRestorePluginsQuestion()
		else:
			if self.didSettingsRestore:
				self.NextStep = 'reboot'
			else:
				self.NextStep = 'noplugins'
			self.buildListRef.close(True)

	def doRestorePluginsQuestion(self):
 		pluginslist = file('/tmp/trimedExtraInstalledPlugins').read()
		if pluginslist:
			print '[RestoreWizard] Stage 5: Plugins to restore',pluginslist
			if self.didSettingsRestore:
				print '[RestoreWizard] Stage 5: proceed to question'
				self.NextStep = 'pluginsquestion'
				self.buildListRef.close(True)
			else:
				print '[RestoreWizard] Stage 5: proceed to restore'
				self.NextStep = 'pluginrestore'
				self.buildListRef.close(True)
		else:
			print '[RestoreWizard] Stage 5: NO Plugins to restore'
			if self.didSettingsRestore:
				self.NextStep = 'reboot'
			else:
				self.NextStep = 'noplugins'
		self.buildListRef.close(True)
