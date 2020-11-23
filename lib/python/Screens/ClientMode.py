from Components.config import config, configfile, ConfigSubList, ConfigSubsection
from Screens.MessageBox import MessageBox
from Screens.Setup import Setup
from Screens.Standby import TryQuitMainloop, QUIT_RESTART


class ClientModeScreen(Setup):
	def __init__(self, session):
		Setup.__init__(self, session=session, setup=None)
		self.title = _("Client Mode")

	def createSetup(self):
		self.list = []
		self.list.append((_("Enable client mode"), config.clientmode.enabled,_('Client mode sets up this receiver to stream from another receiver. In this mode no local tuners will be available and channel lists, EPG, etc, will come from the remote receiver. All tuner settings will be cleared.')))
		if config.clientmode.enabled.value:
			self.list.append((_("Host receiver address type"), config.clientmode.serverAddressType,_('Select between entering an IP address or a domain.')))
			if config.clientmode.serverAddressType.value == "ip":
				self.list.append((_("Host receiver IP address"), config.clientmode.serverIP,_('Enter the IP address of the host receiver.')))
			else:
				self.list.append((_("Host domain"), config.clientmode.serverDomain,_("Enter the domain of the host receiver. Do not include 'http://' or port number.")))
			self.list.append((_("Host receiver streaming port"), config.clientmode.serverStreamingPort,_("Enter the streaming port of the host receiver (normally '8001').")))
			self.list.append((_("Host receiver FTP username"), config.clientmode.serverFTPusername,_("Enter the FTP username of the host receiver (normally 'root').")))
			self.list.append((_("Host receiver FTP password"), config.clientmode.serverFTPpassword,_("Enter the FTP password of the host receiver (normally just leave empty).")))
			self.list.append((_("Host receiver FTP port"), config.clientmode.serverFTPPort,_("Enter the FTP port of the host receiver (normally '21').")))
			self.list.append((_("FTP passive mode"), config.clientmode.passive,_("Should the FTP connection to the remote receiver be established in passive mode (normally 'no')?")))
			self.list.append((_("Schedule EPG and channel list import"), config.clientmode.enableSchedule,_("Allows you to set a schedule to import the EPG and channels list. The EPG and channels list will always be imported on reboot or GUI restart.")))
			if config.clientmode.enableSchedule.value:
				self.list.append((_("Repeat how often"), config.clientmode.scheduleRepeatInterval,_("Set the repeat interval of the schedule.")))
				if config.clientmode.scheduleRepeatInterval.value in ("daily",):
					self.list.append((_("Time import should start"), config.clientmode.scheduletime,_("Set the time of day to perform the import.")))

		currentItem = self["config"].getCurrent()
		self["config"].setList(self.list)
		self.moveToItem(currentItem)

	def run(self): # for start wizard
		self.saveconfig()

	def keySave(self):
		if config.clientmode.enabled.value and not self.checkFTPconnection():
			mbox = self.session.open(MessageBox, _("Connection using the supplied FTP parameters failed. Please recheck the details and try again."), MessageBox.TYPE_ERROR)
			mbox.setTitle(_("FTP connection failure"))
			return
		if config.clientmode.enabled.isChanged():
			restartbox = self.session.openWithCallback(self.restartGUI, MessageBox,_("GUI needs a restart to switch modes\nDo you want to restart the GUI now?"), MessageBox.TYPE_YESNO)
			restartbox.setTitle(_("Restart GUI now?"))
		else:
			self.saveconfig()
			self.close()

	def saveconfig(self):
		nim_config_list = []
		if config.clientmode.enabled.isChanged() and config.clientmode.enabled.value:  # switching to client mode
			# save normal mode config so it can be reinsated when returning to normal mode
			nim_config_list = []
			for x in config.Nims:
				nim_config_list.append(x.getSavedValue())
			import json
			config.clientmode.nim_cache.value = json.dumps(nim_config_list)
			config.clientmode.remote_fallback_enabled_cache.value = config.usage.remote_fallback_enabled.value
			config.clientmode.remote_fallback_cache.value = config.usage.remote_fallback.value
			# normal mode config values saved
		if config.clientmode.enabled.value:
			config.usage.remote_fallback_enabled.value = True
			config.usage.remote_fallback.value = "http://%s:%d" % (self.getRemoteAddress(), config.clientmode.serverStreamingPort.value)
		elif config.clientmode.enabled.isChanged(): # switching back to normal mode
			# load nim config from config.clientmode.nimcache
			import json
			nim_config_list = json.loads(config.clientmode.nim_cache.value)
			config.clientmode.nim_cache.value = ""
			config.Nims = ConfigSubList()
			for x in nim_config_list:
				tuner = ConfigSubsection()
				tuner.setSavedValue(x)
				config.Nims.append(tuner)
			config.Nims.save()
			# nim config loaded... but needs restart
			# reinstate normal mode values
			config.usage.remote_fallback_enabled.value = config.clientmode.remote_fallback_enabled_cache.value
			config.usage.remote_fallback.value = config.clientmode.remote_fallback_cache.value
			# reset some client mode settings
			config.clientmode.remote_fallback_enabled_cache.value = False
			config.clientmode.remote_fallback_cache.value = ""
		config.usage.save()
		config.clientmode.save()
		configfile.save()

	def getRemoteAddress(self):
		if config.clientmode.serverAddressType.value == "ip":
			return '%d.%d.%d.%d' % (config.clientmode.serverIP.value[0], config.clientmode.serverIP.value[1], config.clientmode.serverIP.value[2], config.clientmode.serverIP.value[3])
		else:
			return config.clientmode.serverDomain.value

	def checkFTPconnection(self):
		print "[ClientMode][checkFTPconnection] Testing FTP connection..."
		try:
			from ftplib import FTP
			ftp = FTP()
			ftp.set_pasv(config.clientmode.passive.value)
			ftp.connect(host=self.getRemoteAddress(), port=config.clientmode.serverFTPPort.value, timeout=5)
			result = ftp.login(user=config.clientmode.serverFTPusername.value, passwd=config.clientmode.serverFTPpassword.value)
			ftp.quit()
			if result.startswith("230"):
				print "[ClientMode][checkFTPconnection] FTP connection success:", result
				return True
			print "[ClientMode][checkFTPconnection] FTP connection failure:", result
			return False
		except Exception, err:
			print "[ChannelsImporter][checkFTPconnection] Error:", err
			return False

	def restartGUI(self, answer):
		if answer is True:
			self.saveconfig()
			self.session.open(TryQuitMainloop, QUIT_RESTART)
