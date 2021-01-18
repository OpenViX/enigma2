from boxbranding import getImageVersion, getImageType, getMachineBrand, getMachineName
import os
from enigma import eConsoleAppContainer, eDVBDB, eTimer
from Components.ActionMap import ActionMap, NumberActionMap
from Components.Button import Button
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigText
from Components.Harddisk import harddiskmanager
from Components import Ipkg
from Components.Label import Label
from Components.Language import language
from Components.OnlineUpdateCheck import feedsstatuscheck, kernelMismatch
from Components.PluginComponent import plugins
from Components.PluginList import PluginList, PluginEntryComponent, PluginCategoryComponent, PluginDownloadComponent
from Components.Sources.StaticText import StaticText
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.Console import Console
from Screens.MessageBox import MessageBox
from Screens.ParentalControlSetup import ProtectedScreen
from Screens.Screen import Screen, ScreenSummary
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_ACTIVE_SKIN
from Tools.LoadPixmap import LoadPixmap
from time import time


config.misc.pluginbrowser = ConfigSubsection()
config.misc.pluginbrowser.bootlogos = ConfigYesNo(default = True)
config.misc.pluginbrowser.display = ConfigYesNo(default = True)
config.misc.pluginbrowser.drivers = ConfigYesNo(default = True)
config.misc.pluginbrowser.extensions = ConfigYesNo(default = True)
config.misc.pluginbrowser.kernel = ConfigYesNo(default = False)
config.misc.pluginbrowser.m2k = ConfigYesNo(default = True)
config.misc.pluginbrowser.picons = ConfigYesNo(default = True)
config.misc.pluginbrowser.po = ConfigYesNo(default = True)
config.misc.pluginbrowser.security = ConfigYesNo(default = True)
config.misc.pluginbrowser.settings = ConfigYesNo(default = True)
config.misc.pluginbrowser.skin = ConfigYesNo(default = True)
config.misc.pluginbrowser.softcams = ConfigYesNo(default = True)
config.misc.pluginbrowser.systemplugins = ConfigYesNo(default = True)
config.misc.pluginbrowser.weblinks = ConfigYesNo(default = True)
config.misc.pluginbrowser.plugin_order = ConfigText(default="")

def languageChanged():
	plugins.clearPluginList()
	plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))

class PluginBrowserSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self["entry"] = StaticText("")
		self["desc"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.selectionChanged()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, name, desc):
		self["entry"].text = name
		self["desc"].text = desc


class PluginBrowser(Screen, ProtectedScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Plugin Browser"))
		ProtectedScreen.__init__(self)

		self.firsttime = True

		self["key_red"] = Button(_("Remove plugins"))
		self["key_green"] = Button(_("Download plugins"))
		self["key_menu"] = StaticText(_("MENU"))

		self.list = []
		self["list"] = PluginList(self.list)
		if config.usage.sort_pluginlist.value:
			self["list"].list.sort()

		self["actions"] = ActionMap(["WizardActions", "MenuActions"],
		{
			"ok": self.save,
			"back": self.close,
			"menu": self.openSetup,
		})
		self["PluginDownloadActions"] = ActionMap(["ColorActions"],
		{
			"red": self.delete,
			"green": self.download
		})
		self["DirectionActions"] = ActionMap(["DirectionActions"],
		{
			"shiftUp": self.moveUp,
			"shiftDown": self.moveDown
		})
		self["NumberActions"] = NumberActionMap(["NumberActions"],
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
			"0": self.keyNumberGlobal
		})

		self.number = 0
		self.nextNumberTimer = eTimer()
		self.nextNumberTimer.callback.append(self.okbuttonClick)

		self.onFirstExecBegin.append(self.checkWarnings)
		self.onShown.append(self.updateList)
		self.onChangedEntry = []
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self.onLayoutFinish.append(self.saveListsize)

	def openSetup(self):
		from Screens.Setup import Setup
		self.session.open(Setup, "pluginbrowsersetup")

	def isProtected(self):
		return config.ParentalControl.setuppinactive.value and (not config.ParentalControl.config_sections.main_menu.value or hasattr(self.session, 'infobar') and self.session.infobar is None) and config.ParentalControl.config_sections.plugin_browser.value

	def saveListsize(self):
		listsize = self["list"].instance.size()
		self.listWidth = listsize.width()
		self.listHeight = listsize.height()

	def createSummary(self):
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["list"].getCurrent()
		if item:
			p = item[0]
			name = p.name
			desc = p.description
		else:
			name = "-"
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def checkWarnings(self):
		if len(plugins.warnings):
			text = _("Some plugins are not available:\n")
			for (pluginname, error) in plugins.warnings:
				text += _("%s (%s)\n") % (pluginname, error)
			plugins.resetWarnings()
			self.session.open(MessageBox, text = text, type = MessageBox.TYPE_WARNING)

	def save(self):
		self.run()

	def run(self):
		plugin = self["list"].l.getCurrentSelection()[0]
		plugin(session=self.session)

	def setDefaultList(self, answer):
		if answer:
			config.misc.pluginbrowser.plugin_order.value = ""
			config.misc.pluginbrowser.plugin_order.save()
			self.updateList()

	def keyNumberGlobal(self, number):
		if number == 0 and self.number == 0:
			if len(self.list) > 0 and config.misc.pluginbrowser.plugin_order.value != "":
				self.session.openWithCallback(self.setDefaultList, MessageBox, _("Sort plugins list to default?"), MessageBox.TYPE_YESNO)
		else:
			self.number = self.number * 10 + number
			if self.number and self.number <= len(self.list):
				if number * 10 > len(self.list) or self.number >= 10:
					self.okbuttonClick()
				else:
					self.nextNumberTimer.start(1400, True)
			else:
				self.resetNumberKey()

	def okbuttonClick(self):
		self["list"].moveToIndex(self.number - 1)
		self.resetNumberKey()
		self.run()

	def resetNumberKey(self):
		self.nextNumberTimer.stop()
		self.number = 0

	def moveUp(self):
		self.move(-1)

	def moveDown(self):
		self.move(1)

	def move(self, direction):
		if len(self.list) > 1:
			currentIndex = self["list"].getSelectionIndex()
			swapIndex = (currentIndex + direction) % len(self.list)
			if currentIndex == 0 and swapIndex != 1:
				self.list = self.list[1:] + [self.list[0]]
			elif swapIndex == 0 and currentIndex != 1:
				self.list = [self.list[-1]] + self.list[:-1]
			else:
				self.list[currentIndex], self.list[swapIndex] = self.list[swapIndex], self.list[currentIndex]
			self["list"].l.setList(self.list)
			if direction == 1:
				self["list"].down()
			else:
				self["list"].up()
			plugin_order = []
			for x in self.list:
				plugin_order.append(x[0].path[24:])
			config.misc.pluginbrowser.plugin_order.value = ",".join(plugin_order)
			config.misc.pluginbrowser.plugin_order.save()

	def updateList(self):
		self.list = []
		pluginlist = plugins.getPlugins(PluginDescriptor.WHERE_PLUGINMENU)[:]
		for x in config.misc.pluginbrowser.plugin_order.value.split(","):
			plugin = list(plugin for plugin in pluginlist if plugin.path[24:] == x)
			if plugin:
				self.list.append(PluginEntryComponent(plugin[0], self.listWidth))
				pluginlist.remove(plugin[0])
		self.list = self.list + [PluginEntryComponent(plugin, self.listWidth) for plugin in pluginlist]
		self["list"].l.setList(self.list)

	def delete(self):
		config.misc.pluginbrowser.po.value = False
		self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginDownloadBrowser, PluginDownloadBrowser.REMOVE, True)

	def download(self):
		config.misc.pluginbrowser.po.value = True
		if not (feedsstatuscheck.adapterAvailable() and feedsstatuscheck.NetworkUp()):
			self.session.openWithCallback(self.close, MessageBox,  _("Your %s %s has no %s access, please check your network settings and make sure you have network cable connected and try again.") % (getMachineBrand(), getMachineName(), feedsstatuscheck.adapterAvailable() and 'internet' or 'network'), type=MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			return
		if kernelMismatch():
			self.session.openWithCallback(self.close, MessageBox, _("The Linux kernel has changed, plugins are not compatible. \nInstall latest image using USB stick or Image Manager."), type=MessageBox.TYPE_INFO, timeout=30, close_on_any_key=True)
			return
		self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginDownloadBrowser, PluginDownloadBrowser.DOWNLOAD, self.firsttime)
		self.firsttime = False

	def PluginDownloadBrowserClosed(self):
		self.updateList()
		self.checkWarnings()

	def openExtensionmanager(self):
		if fileExists(resolveFilename(SCOPE_PLUGINS, "SystemPlugins/SoftwareManager/plugin.py")):
			try:
				from Plugins.SystemPlugins.SoftwareManager.plugin import PluginManager
			except ImportError:
				self.session.open(MessageBox, _("The software management extension is not installed!\nPlease install it."), type = MessageBox.TYPE_INFO,timeout = 10 )
			else:
				self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginManager)

class PluginDownloadBrowser(Screen):
	DOWNLOAD = 0
	REMOVE = 1
	UPDATE = 2
	PLUGIN_PREFIX = 'enigma2-plugin-'
	PLUGIN_PREFIX2 = []
	lastDownloadDate = None

	def __init__(self, session, type=0, needupdate=True, skin_name=None):
		Screen.__init__(self, session)
		self.type = type
		self.needupdate = needupdate
		self.skinName = ["PluginDownloadBrowser"]
		if isinstance(skin_name, str):
			self.skinName.insert(0,skin_name)

		if self.type == self.DOWNLOAD:
			config.misc.pluginbrowser.po.value = True
			self.setTitle(_("Install Plugins"))
		elif self.type == self.REMOVE:
			config.misc.pluginbrowser.po.value = False
			self.setTitle(_("Remove Plugins"))
		self.createPluginFilter()
		self.LanguageList = language.getLanguageListSelection()
		self.container = eConsoleAppContainer()
		self.container.appClosed.append(self.runFinished)
		self.container.dataAvail.append(self.dataAvail)
		self.onLayoutFinish.append(self.startRun)

		self.list = []
		self["list"] = PluginList(self.list)
		self.pluginlist = []
		self.expanded = []
		self.installedplugins = []
		self.plugins_changed = False
		self.reload_settings = False
		self.check_settings = False
		self.check_bootlogo = False
		self.install_settings_name = ''
		self.remove_settings_name = ''
		self.onChangedEntry = []
		self["list"].onSelectionChanged.append(self.selectionChanged)

		if self.type == self.DOWNLOAD:
			self["text"] = Label(_("Downloading plugin information. Please wait..."))
		elif self.type == self.REMOVE:
			self["text"] = Label(_("Getting plugin information. Please wait..."))

		self.run = 0
		self.remainingdata = ""
		self["actions"] = ActionMap(["WizardActions"],
		{
			"ok": self.go,
			"back": self.requestClose,
		})
		if os.path.isfile('/usr/bin/opkg'):
			self.ipkg = '/usr/bin/opkg'
			self.ipkg_install = self.ipkg + ' install'
			self.ipkg_remove =  self.ipkg + ' remove --autoremove'
		else:
			self.ipkg = 'ipkg'
			self.ipkg_install = 'ipkg install -force-defaults'
			self.ipkg_remove =  self.ipkg + ' remove'

	def createSummary(self):
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["list"].getCurrent()
		try:
			if isinstance(item[0], str): # category
				name = item[0]
				desc = ""
			else:
				p = item[0]
				name = item[1][0:8][7]
				desc = p.description
		except:
			name = ""
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def createPluginFilter(self):
		#Create Plugin Filter
		self.PLUGIN_PREFIX2 = []
		if config.misc.pluginbrowser.bootlogos.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'bootlogos')
		if config.misc.pluginbrowser.drivers.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'drivers')
		if config.misc.pluginbrowser.extensions.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'extensions')
		if config.misc.pluginbrowser.m2k.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'm2k')
		if config.misc.pluginbrowser.picons.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'picons')
		if config.misc.pluginbrowser.security.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'security')
		if config.misc.pluginbrowser.settings.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'settings')
		if config.misc.pluginbrowser.skin.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'skin')
		if config.misc.pluginbrowser.display.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'display')
		if config.misc.pluginbrowser.softcams.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'softcams')
		if config.misc.pluginbrowser.systemplugins.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'systemplugins')
		if config.misc.pluginbrowser.weblinks.value:
			self.PLUGIN_PREFIX2.append(self.PLUGIN_PREFIX + 'weblinks')
		if config.misc.pluginbrowser.kernel.value:
			self.PLUGIN_PREFIX2.append('kernel-module-')
		if config.misc.pluginbrowser.po.value:
			self.PLUGIN_PREFIX2.append('enigma2-locale-')

	def go(self):
		sel = self["list"].l.getCurrentSelection()

		if sel is None:
			return

		sel = sel[0]
		if isinstance(sel, str): # category
			if sel in self.expanded:
				self.expanded.remove(sel)
			else:
				self.expanded.append(sel)
			self.updateList()
		else:
			if self.type == self.DOWNLOAD:
				mbox=self.session.openWithCallback(self.runInstall, MessageBox, _("Do you really want to download the plugin \"%s\"?") % sel.name)
				mbox.setTitle(_("Download plugins"))
			elif self.type == self.REMOVE:
				mbox=self.session.openWithCallback(self.runInstall, MessageBox, _("Do you really want to remove the plugin \"%s\"?") % sel.name, default = False)
				mbox.setTitle(_("Remove plugins"))

	def requestClose(self):
		if self.plugins_changed:
			plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
		if self.reload_settings:
			self["text"].setText(_("Reloading bouquets and services..."))
			eDVBDB.getInstance().reloadBouquets()
			eDVBDB.getInstance().reloadServicelist()
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
		self.container.appClosed.remove(self.runFinished)
		self.container.dataAvail.remove(self.dataAvail)
		self.close()

	def resetPostInstall(self):
		try:
			del self.postInstallCall
		except:
			pass

	def installDestinationCallback(self, result):
		if result is not None:
			dest = result[1]
			if dest.startswith('/'):
				# Custom install path, add it to the list too
				dest = os.path.normpath(dest)
				extra = '--add-dest %s:%s -d %s' % (dest,dest,dest)
				Ipkg.opkgAddDestination(dest)
			else:
				extra = '-d ' + dest
			self.doInstall(self.installFinished, self["list"].l.getCurrentSelection()[0].name + ' ' + extra)
		else:
			self.resetPostInstall()

	def runInstall(self, val):
		if val:
			if self.type == self.DOWNLOAD:
				if self["list"].l.getCurrentSelection()[0].name.startswith("picons-"):
					supported_filesystems = frozenset(('ext4', 'ext3', 'ext2', 'reiser', 'reiser4', 'jffs2', 'ubifs', 'rootfs'))
					candidates = []
					import Components.Harddisk
					mounts = Components.Harddisk.getProcMounts()
					for partition in harddiskmanager.getMountedPartitions(False, mounts):
						if partition.filesystem(mounts) in supported_filesystems:
							candidates.append((partition.description, partition.mountpoint))
					if candidates:
						from Components.Renderer import Picon
						self.postInstallCall = Picon.initPiconPaths
						self.session.openWithCallback(self.installDestinationCallback, ChoiceBox, title=_("Install picons on"), list=candidates)
					return
				elif self["list"].l.getCurrentSelection()[0].name.startswith("display-picon"):
					supported_filesystems = frozenset(('ext4', 'ext3', 'ext2', 'reiser', 'reiser4', 'jffs2', 'ubifs', 'rootfs'))
					candidates = []
					import Components.Harddisk
					mounts = Components.Harddisk.getProcMounts()
					for partition in harddiskmanager.getMountedPartitions(False, mounts):
						if partition.filesystem(mounts) in supported_filesystems:
							candidates.append((partition.description, partition.mountpoint))
					if candidates:
						from Components.Renderer import LcdPicon
						self.postInstallCall = LcdPicon.initLcdPiconPaths
						self.session.openWithCallback(self.installDestinationCallback, ChoiceBox, title=_("Install lcd picons on"), list=candidates)
					return
				self.install_settings_name = self["list"].l.getCurrentSelection()[0].name
				self.install_bootlogo_name = self["list"].l.getCurrentSelection()[0].name
				if self["list"].l.getCurrentSelection()[0].name.startswith('settings-'):
					self.check_settings = True
					self.startIpkgListInstalled(self.PLUGIN_PREFIX + 'settings-*')
				elif self["list"].l.getCurrentSelection()[0].name.startswith('bootlogos-'):
					self.check_bootlogo = True
					self.startIpkgListInstalled(self.PLUGIN_PREFIX + 'bootlogos-*')
				else:
					self.runSettingsInstall()
			elif self.type == self.REMOVE:
				self.doRemove(self.installFinished, self["list"].l.getCurrentSelection()[0].name + " --force-remove --force-depends")

	def doRemove(self, callback, pkgname):
		if pkgname.startswith('kernel-module-') or pkgname.startswith('enigma2-locale-'):
			self.session.openWithCallback(callback, Console, cmdlist = [self.ipkg_remove + Ipkg.opkgExtraDestinations() + " " + pkgname, "sync"], closeOnSuccess = True)
		else:
			self.session.openWithCallback(callback, Console, cmdlist = [self.ipkg_remove + Ipkg.opkgExtraDestinations() + " " + self.PLUGIN_PREFIX + pkgname, "sync"], closeOnSuccess = True)

	def doInstall(self, callback, pkgname):
		if pkgname.startswith('kernel-module-') or pkgname.startswith('enigma2-locale-'):
			self.session.openWithCallback(callback, Console, cmdlist = [self.ipkg_install + " " + pkgname, "sync"], closeOnSuccess = True)
		else:
			self.session.openWithCallback(callback, Console, cmdlist = [self.ipkg_install + " " + self.PLUGIN_PREFIX + pkgname, "sync"], closeOnSuccess = True)

	def runSettingsRemove(self, val):
		if val:
			self.doRemove(self.runSettingsInstall, self.remove_settings_name)

	def runBootlogoRemove(self, val):
		if val:
			self.doRemove(self.runSettingsInstall, self.remove_bootlogo_name + " --force-remove --force-depends")

	def runSettingsInstall(self):
		self.doInstall(self.installFinished, self.install_settings_name)

	def startIpkgListInstalled(self, pkgname = PLUGIN_PREFIX + '*'):
		self.container.execute(self.ipkg + Ipkg.opkgExtraDestinations() + " list_installed")

	def startIpkgListAvailable(self):
		self.container.execute(self.ipkg + Ipkg.opkgExtraDestinations() + " list")

	def startRun(self):
		listsize = self["list"].instance.size()
		self["list"].instance.hide()
		self.listWidth = listsize.width()
		self.listHeight = listsize.height()
		if self.type == self.DOWNLOAD:
			self.type = self.UPDATE
			if (getImageType() != 'release' and feedsstatuscheck.getFeedsBool() != 'unknown') or (getImageType() == 'release' and feedsstatuscheck.getFeedsBool() not in ('stable', 'unstable')):
				self["text"].setText(feedsstatuscheck.getFeedsErrorMessage())
			elif getImageType() != 'release' or (config.softwareupdate.updateisunstable.value == '1' and config.softwareupdate.updatebeta.value):
				self["text"].setText(_("WARNING: feeds may be unstable.") + '\n' + _("Downloading plugin information. Please wait..."))
				self.container.execute(self.ipkg + " update")
			elif config.softwareupdate.updateisunstable.value == '1' and not config.softwareupdate.updatebeta.value:
				self["text"].setText(_("Sorry feeds seem be in an unstable state, if you wish to use them please enable 'Allow unstable (experimental) updates' in \"Software update settings\"."))
			else:
				self.container.execute(self.ipkg + " update")
		elif self.type == self.REMOVE:
			self.run = 1
			self.startIpkgListInstalled()

	def installFinished(self):
		if hasattr(self, 'postInstallCall'):
			try:
				self.postInstallCall()
			except Exception, ex:
				print "[PluginBrowser] postInstallCall failed:", ex
			self.resetPostInstall()
		try:
			os.unlink('/tmp/opkg.conf')
		except:
			pass
		for plugin in self.pluginlist:
			if plugin[3] == self["list"].l.getCurrentSelection()[0].name or plugin[0] == self["list"].l.getCurrentSelection()[0].name:
				self.pluginlist.remove(plugin)
				break
		self.plugins_changed = True
		if self["list"].l.getCurrentSelection()[0].name.startswith("settings-"):
			self.reload_settings = True
		self.expanded = []
		self.updateList()
		self["list"].moveToIndex(0)

	def runFinished(self, retval):
		if self.check_settings:
			self.check_settings = False
			self.runSettingsInstall()
			return
		if self.check_bootlogo:
			self.check_bootlogo = False
			self.runSettingsInstall()
			return
		self.remainingdata = ""
		if self.run == 0:
			self.run = 1
			if self.type == self.UPDATE:
				self.type = self.DOWNLOAD
				self.startIpkgListInstalled()
		elif self.run == 1 and self.type == self.DOWNLOAD:
			self.run = 2
			self.startIpkgListAvailable()
		else:
			if len(self.pluginlist) > 0:
				self.updateList()
				self["list"].instance.show()
			else:
				if self.type == self.DOWNLOAD:
					self["text"].setText(_("Sorry the feeds are down for maintenance"))

	def dataAvail(self, str):
		if self.type == self.DOWNLOAD and ('wget returned 1' or 'wget returned 255' or '404 Not Found') in str:
			self.run = 3
			return
		#prepend any remaining data from the previous call
		str = self.remainingdata + str
		#split in lines
		lines = str.split('\n')
		#'str' should end with '\n', so when splitting, the last line should be empty. If this is not the case, we received an incomplete line
		if len(lines[-1]):
			#remember this data for next time
			self.remainingdata = lines[-1]
			lines = lines[0:-1]
		else:
			self.remainingdata = ""

		if self.check_settings:
			self.check_settings = False
			self.remove_settings_name = str.split(' - ')[0].replace(self.PLUGIN_PREFIX, '')
			self.session.openWithCallback(self.runSettingsRemove, MessageBox, _('You already have a channel list installed,\nwould you like to remove\n"%s"?') % self.remove_settings_name)
			return

		if self.check_bootlogo:
			self.check_bootlogo = False
			self.remove_bootlogo_name = str.split(' - ')[0].replace(self.PLUGIN_PREFIX, '')
			self.session.openWithCallback(self.runBootlogoRemove, MessageBox, _('You already have a bootlogo installed,\nwould you like to remove\n"%s"?') % self.remove_bootlogo_name)
			return

		for x in lines:
			plugin = x.split(" - ", 2)
			# 'opkg list_installed' only returns name + version, no description field
			if len(plugin) >= 1:
				if not plugin[0].endswith('-dev') and not plugin[0].endswith('-staticdev') and not plugin[0].endswith('-dbg') and not plugin[0].endswith('-doc') and not plugin[0].endswith('-common') and not plugin[0].endswith('-meta') and plugin[0] not in self.installedplugins and ((not config.pluginbrowser.po.value and not plugin[0].endswith('-po')) or config.pluginbrowser.po.value) and ((not config.pluginbrowser.src.value and not plugin[0].endswith('-src')) or config.pluginbrowser.src.value):
					# Plugin filter
					for s in self.PLUGIN_PREFIX2:
						if plugin[0].startswith(s):
							if self.run == 1 and self.type == self.DOWNLOAD:
								self.installedplugins.append(plugin[0])
							else:
								if len(plugin) == 2:
									# 'opkg list_installed' does not return descriptions, append empty description
									if plugin[0].startswith('enigma2-locale-'):
										lang = plugin[0].split('-')
										if len(lang) > 3:
											plugin.append(lang[2] + '-' + lang[3])
										else:
											plugin.append(lang[2])
									else:
										plugin.append('')
								plugin.append(plugin[0][15:])
								self.pluginlist.append(plugin)
			self.pluginlist.sort()

	def updateList(self):
		list = []
		expandableIcon = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/expandable-plugins.png"))
		expandedIcon = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/expanded-plugins.png"))
		verticallineIcon = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "icons/verticalline-plugins.png"))

		self.plugins = {}

		if self.type == self.UPDATE:
			self.list = list
			self["list"].l.setList(list)
			return

		for x in self.pluginlist:
			split = x[3].split('-', 1)
			if x[0][0:14] == 'kernel-module-':
				split[0] = "kernel modules"
			elif x[0][0:15] == 'enigma2-locale-':
				split[0] = "languages"

			if not self.plugins.has_key(split[0]):
				self.plugins[split[0]] = []

			if split[0] == "kernel modules":
				self.plugins[split[0]].append((PluginDescriptor(name = x[0], description = x[2], icon = verticallineIcon), x[0][14:], x[1]))
			elif split[0] == "languages":
				for t in self.LanguageList:
					if len(x[2])>2:
						tmpT = t[0].lower()
						tmpT = tmpT.replace('_','-')
						if tmpT == x[2]:
							countryIcon = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "countries/" + t[0] + ".png"))
							if countryIcon is None:
								countryIcon = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "countries/missing.png"))
							self.plugins[split[0]].append((PluginDescriptor(name = x[0], description = x[2], icon = countryIcon), t[1], x[1]))
							break
					else:
						if t[0][:2] == x[2] and t[0][3:] != 'GB':
							countryIcon = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "countries/" + t[0] + ".png"))
							if countryIcon is None:
								countryIcon = LoadPixmap(resolveFilename(SCOPE_ACTIVE_SKIN, "countries/missing.png"))
							self.plugins[split[0]].append((PluginDescriptor(name = x[0], description = x[2], icon = countryIcon), t[1], x[1]))
							break

			else:
				if len(split) < 2:
					continue
				self.plugins[split[0]].append((PluginDescriptor(name = x[3], description = x[2], icon = verticallineIcon), split[1], x[1]))

		temp = self.plugins.keys()
		if config.usage.sort_pluginlist.value:
			temp.sort()
		for x in temp:
			if x in self.expanded:
				list.append(PluginCategoryComponent(x, expandedIcon, self.listWidth))
				list.extend([PluginDownloadComponent(plugin[0], plugin[1], plugin[2], self.listWidth) for plugin in self.plugins[x]])
			else:
				list.append(PluginCategoryComponent(x, expandableIcon, self.listWidth))
		self.list = list
		self["list"].l.setList(list)

language.addCallback(languageChanged)
