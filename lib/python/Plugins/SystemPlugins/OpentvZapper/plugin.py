from __future__ import absolute_import

from Components.config import config, ConfigSelection, ConfigSubsection, ConfigYesNo, ConfigSelectionNumber
from Components.NimManager import nimmanager

from Plugins.Plugin import PluginDescriptor

from Screens.Setup import Setup

from .providers import providers

config.plugins.opentvzapper = ConfigSubsection()
config.plugins.opentvzapper.enabled = ConfigYesNo(default = False)
config.plugins.opentvzapper.providers = ConfigSelection(default="Astra 28.2", choices=list(providers.keys()))
config.plugins.opentvzapper.update_interval = ConfigSelectionNumber(min = 3, max = 24, stepwidth = 3, default = 6, wraparound = True)
config.plugins.opentvzapper.extensions = ConfigYesNo(default = True)
config.plugins.opentvzapper.notifications = ConfigYesNo(default = False)

# This import must be after "config" variables are set. 
from .opentv_zapper import opentv_zapper, startSession

description = _("Zaps to EPG download transponder for EPG fetch.")

class OpentvZapper_Setup(Setup):
	def __init__(self, session):
		Setup.__init__(self, session, setup="opentvzapper", plugin="SystemPlugins/OpentvZapper")

	def keySave(self):
		if config.plugins.opentvzapper.enabled.value:
			config.epg.opentv.value = True
			config.epg.opentv.save()
		provider_changed = config.plugins.opentvzapper.providers.isChanged()
		enabled_changed = config.plugins.opentvzapper.enabled.isChanged()
		self.saveAll()
		if provider_changed:
			opentv_zapper.initialize(config.plugins.opentvzapper.providers.value)
		if enabled_changed or provider_changed:
			opentv_zapper.config_changed()
		self.close()
		

def startdownload(session, **kwargs): # Called from extensions menu if this option is active
	opentv_zapper.force_download()

def OpentvZapperStart(menuid, **kwargs): # Menu position of plugin setup screen
	if menuid == "epg":
		return [(_("OpenTV EPG downloader"), OpentvZapperMain, "OpentvZapper_Setup", None)]
	return []

def OpentvZapperMain(session, **kwargs): # calls setup screen
	session.open(OpentvZapper_Setup)

def OpentvZapperWakeupTime(): # Called on shutdown (going into deep standby) to tell the box when to wake from deep
	return -1 # never

def Plugins(**kwargs):
	plist = []
	if nimmanager.hasNimType("DVB-S"):
		plist.append(PluginDescriptor(name=_("OpentvZapper"), description=description, where = PluginDescriptor.WHERE_MENU, needsRestart = True, fnc=OpentvZapperStart) )
		plist.append(PluginDescriptor(name="OpentvZapperScheduler", where=[ PluginDescriptor.WHERE_AUTOSTART, PluginDescriptor.WHERE_SESSIONSTART ], fnc=startSession, wakeupfnc=OpentvZapperWakeupTime, needsRestart=True))
		if config.plugins.opentvzapper.enabled.value and config.plugins.opentvzapper.extensions.value:
			plist.append(PluginDescriptor(name=_("OpenTV EPG forced download"), description=description, where = PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=startdownload, needsRestart=True))
	return plist
