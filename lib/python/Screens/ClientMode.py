from Components.config import config, configfile, ConfigSubList, ConfigSubsection
from Screens.MessageBox import MessageBox
from Screens.Setup import Setup
from Screens.Standby import TryQuitMainloop, QUIT_RESTART


class ClientModeScreen(Setup):
	def __init__(self, session):
		Setup.__init__(self, session=session, setup="clientmode")

	def run(self): # for start wizard
		self.saveconfig()

	def keySave(self):
		if config.clientmode.enabled.value and not self.checkFTPconnection():
			mbox = self.session.open(MessageBox, _("Connection using the supplied FTP parameters failed. Please recheck the details and try again."), MessageBox.TYPE_ERROR)
			mbox.setTitle(_("FTP connection failure"))
			return
		if config.clientmode.enabled.isChanged():
			restartbox = self.session.openWithCallback(self.restartGUI, MessageBox, _("GUI needs a restart to switch modes\nDo you want to restart the GUI now?"), MessageBox.TYPE_YESNO)
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
