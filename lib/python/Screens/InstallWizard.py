from Screens.Screen import Screen
from Components.ConfigList import ConfigListScreen, ConfigList
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.config import config, ConfigSubsection, ConfigBoolean, getConfigListEntry, ConfigSelection, ConfigYesNo, ConfigIP
from Components.Network import iNetwork
from Components.Opkg import OpkgComponent
from enigma import eDVBDB

config.misc.installwizard = ConfigSubsection()
config.misc.installwizard.hasnetwork = ConfigBoolean(default=False)
config.misc.installwizard.opkgloaded = ConfigBoolean(default=False)
config.misc.installwizard.channellistdownloaded = ConfigBoolean(default=False)


class InstallWizard(Screen, ConfigListScreen):

	STATE_UPDATE = 0
	STATE_CHOICE_CHANNELLIST = 1
	INSTALL_PLUGINS = 2

	def __init__(self, session, args=None):
		Screen.__init__(self, session)

		self.index = args
		self.list = []
		ConfigListScreen.__init__(self, self.list)

		if self.index == self.STATE_UPDATE:
			config.misc.installwizard.hasnetwork.value = False
			config.misc.installwizard.opkgloaded.value = False
			modes = {0: " "}
			self.enabled = ConfigSelection(choices=modes, default=0)
			self.adapters = [adapter for adapter in iNetwork.getAdapterList() if adapter in ('eth0', 'eth1')]
			self.checkNetwork()
		elif self.index == self.STATE_CHOICE_CHANNELLIST:
			self.enabled = ConfigYesNo(default=True, graphic=False)
			modes = {
								"19e": "Astra 19.2e",
								"19e-13e": "Astra 19.2e Hotbird 13.0e",
								"kabel-bw": "Kabel BW",
								"kabeldeutschland": " Kabel Deutschland",
								"unity-media": "Kabel Unitymedia"
							}
			self.channellist_type = ConfigSelection(choices=modes, default="19e-13e")
			self.createMenu()
#		elif self.index == self.STATE_CHOICE_SOFTCAM:
#			self.enabled = ConfigYesNo(default = False)
#			self.createMenu()
		elif self.index == self.INSTALL_PLUGINS:
			self.enabled = ConfigYesNo(default=True)
			self.createMenu()

	def checkNetwork(self):
		if self.adapters:
			self.adapter = self.adapters.pop(0)
			if iNetwork.getAdapterAttribute(self.adapter, 'up'):
				iNetwork.checkNetworkState(self.checkNetworkStateCallback)
			else:
				iNetwork.restartNetwork(self.restartNetworkCallback)
		else:
			self.createMenu()

	def checkNetworkStateCallback(self, data):
		if data < 3:
			config.misc.installwizard.hasnetwork.value = True
			self.createMenu()
		else:
			self.checkNetwork()

	def restartNetworkCallback(self, retval):
		if retval:
			iNetwork.checkNetworkState(self.checkNetworkStateCallback)
		else:
			self.checkNetwork()

	def createMenu(self):
		try:
			test = self.index
		except:
			return
		self.list = []
		if self.index == self.STATE_UPDATE:
			if config.misc.installwizard.hasnetwork.value:
				ip = ".".join([str(x) for x in iNetwork.getAdapterAttribute(self.adapter, "ip")])
				self.list.append(getConfigListEntry(_("Your internet connection is working (ip: %s)") % ip, self.enabled))
			else:
				self.list.append(getConfigListEntry(_("Your receiver does not have an internet connection"), self.enabled))
		elif self.index == self.STATE_CHOICE_CHANNELLIST:
			self.list.append(getConfigListEntry(_("Install channel list"), self.enabled))
			if self.enabled.value:
				self.list.append(getConfigListEntry(_("Channel list type"), self.channellist_type))
#		elif self.index == self.STATE_CHOICE_SOFTCAM:
#			self.list.append(getConfigListEntry(_("Install softcam support"), self.enabled))
		elif self.index == self.INSTALL_PLUGINS:
			self.list.append(getConfigListEntry(_("Do you want to install plugins"), self.enabled))
		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def keyLeft(self):
		if self.index == 0:
			return
		ConfigListScreen.keyLeft(self)
		self.createMenu()

	def keyRight(self):
		if self.index == 0:
			return
		ConfigListScreen.keyRight(self)
		self.createMenu()

	def run(self):
		if self.index == self.STATE_UPDATE:
			if config.misc.installwizard.hasnetwork.value:
				self.session.open(InstallWizardOpkgUpdater, self.index, _('Please wait (updating packages)'), OpkgComponent.CMD_UPDATE)
		elif self.index == self.STATE_CHOICE_CHANNELLIST and self.enabled.value:
			self.session.open(InstallWizardOpkgUpdater, self.index, _('Please wait (downloading channel list)'), OpkgComponent.CMD_REMOVE, {'package': 'enigma2-plugin-settings-gigablue-' + self.channellist_type.value})
#		elif self.index == self.STATE_CHOICE_SOFTCAM and self.enabled.value:
#			self.session.open(InstallWizardOpkgUpdater, self.index, _('Please wait (downloading softcam support)'), OpkgComponent.CMD_INSTALL, {'package': 'om-softcam-support'})
		elif self.index == self.INSTALL_PLUGINS and self.enabled.value:
			from PluginBrowser import PluginDownloadBrowser
			self.session.open(PluginDownloadBrowser, 0)
		return


class InstallWizardOpkgUpdater(Screen):
	skin = """
	<screen position="c-300,c-25" size="600,50" title=" ">
		<widget source="statusbar" render="Label" position="10,5" zPosition="10" size="e-10,30" halign="center" valign="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
	</screen>"""

	def __init__(self, session, index, info, cmd, pkg=None):
		self.skin = InstallWizardOpkgUpdater.skin
		Screen.__init__(self, session)

		self["statusbar"] = StaticText(info)

		self.pkg = pkg
		self.index = index
		self.state = 0

		self.opkg = OpkgComponent()
		self.opkg.addCallback(self.opkgCallback)

		if self.index == InstallWizard.STATE_CHOICE_CHANNELLIST:
			self.opkg.startCmd(cmd, {'package': 'enigma2-plugin-settings-*'})
		else:
			self.opkg.startCmd(cmd, pkg)

	def opkgCallback(self, event, param):
		if event == OpkgComponent.EVENT_DONE:
			if self.index == InstallWizard.STATE_UPDATE:
				config.misc.installwizard.opkgloaded.value = True
			elif self.index == InstallWizard.STATE_CHOICE_CHANNELLIST:
				if self.state == 0:
					self.opkg.startCmd(OpkgComponent.CMD_INSTALL, self.pkg)
					self.state = 1
					return
				else:
					config.misc.installwizard.channellistdownloaded.value = True
					eDVBDB.getInstance().reloadBouquets()
					eDVBDB.getInstance().reloadServicelist()
			self.close()
