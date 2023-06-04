from Components.config import config, ConfigBoolean, ConfigClock, ConfigEnableDisable, ConfigNumber, ConfigSelection, ConfigSelectionNumber, ConfigSubDict, ConfigSubsection, ConfigYesNo, NoSave
from Components.NimManager import nimmanager
from Components.SystemInfo import SystemInfo

from Plugins.Plugin import PluginDescriptor

from Screens.Setup import Setup

from .providers import providers

config.plugins.opentvzapper = ConfigSubsection()
config.plugins.opentvzapper.enabled = ConfigYesNo(default=False)
config.plugins.opentvzapper.providers = ConfigSelection(default="Astra 28.2", choices=list(providers.keys()))
config.plugins.opentvzapper.update_interval = ConfigSelectionNumber(min=3, max=24, stepwidth=3, default=6, wraparound=True) # auto schedule
config.plugins.opentvzapper.extensions = ConfigYesNo(default=True)
config.plugins.opentvzapper.notifications = ConfigYesNo(default=False)
config.plugins.opentvzapper.use_pip_adapter = ConfigYesNo(default=True)

# user defined schedule
config.plugins.opentvzapper.schedule = ConfigBoolean(default=False, descriptions={False: _("Auto"), True: _("Custom")}, graphic=False)
config.plugins.opentvzapper.scheduletime = ConfigClock(default=0) # 1:00
config.plugins.opentvzapper.retry = ConfigNumber(default=30)
config.plugins.opentvzapper.retrycount = NoSave(ConfigNumber(default=0))
config.plugins.opentvzapper.nextscheduletime = ConfigNumber(default=0)
config.plugins.opentvzapper.schedulewakefromdeep = ConfigYesNo(default=True)
config.plugins.opentvzapper.scheduleshutdown = ConfigYesNo(default=True)
config.plugins.opentvzapper.dayscreen = NoSave(ConfigSelection(choices=[("1", _("Press OK"))], default="1"))
config.plugins.opentvzapper.days = ConfigSubDict()
for i in range(7):
	config.plugins.opentvzapper.days[i] = ConfigEnableDisable(default=True)

# This import must be after "config" variables are set.
if nimmanager.hasNimType("DVB-S"):
	from .opentv_zapper import opentv_zapper, startSession, AutoScheduleTimer

description = _("Zaps to EPG download transponder for EPG fetch.")


class OpentvZapper_Setup(Setup):
	def __init__(self, session):
		self.config = config.plugins.opentvzapper
		Setup.__init__(self, session, setup=None)
		self.title = _('OpentvZapper')

	def keySave(self):
		if self.config.enabled.value:
			config.epg.opentv.value = True
			config.epg.opentv.save()
		provider_changed = self.config.providers.isChanged()
		enabled_changed = self.config.enabled.isChanged()
		schedule_changed = self.config.schedule.isChanged()
		self.saveAll()
		if enabled_changed or provider_changed or schedule_changed:
			opentv_zapper.config_changed()
		AutoScheduleTimer.instance.doneConfiguring()
		self.close()

	def keySelect(self):
		if self.getCurrentItem() == self.config.dayscreen:
			self.session.open(OpentvZapperDaysScreen)
		else:
			Setup.keySelect(self)

	def createSetup(self):
		indent = "- "
		setupList = []
		setupList.append((_("Enable OpenTV download"), config.plugins.opentvzapper.enabled, _("Enable automated downloading of OpenTV EPG data. If only one tuner is available the download will be done when the reciever is in standby.")))
		if config.plugins.opentvzapper.enabled.value:
			setupList.append((_("Provider"), config.plugins.opentvzapper.providers, _("Select provider")))
			setupList.append((_("Schedule scan"), config.plugins.opentvzapper.schedule, _("Allows you to set a schedule to perform an EPG update.")))
			if config.plugins.opentvzapper.schedule.value:
				setupList.append((indent + _("Schedule time of day"), config.plugins.opentvzapper.scheduletime, _("Set the time of day to perform an EPG download.")))
				setupList.append((indent + _("Schedule days of the week"), config.plugins.opentvzapper.dayscreen, _("Press OK to select which days to perform an EPG download.")))
				setupList.append((indent + _("Schedule wake from deep standby"), config.plugins.opentvzapper.schedulewakefromdeep, _("Select 'yes' to wake up the receiver from deep standby, or select 'no' to skip the import.")))
				if config.plugins.opentvzapper.schedulewakefromdeep.value:
					setupList.append((indent + _("Schedule return to deep standby"), config.plugins.opentvzapper.scheduleshutdown, _("If the receiver was woken from 'Deep Standby' and is currently in 'Standby' and no recordings are in progress return it to 'Deep Standby' once the EPG download has completed.")))
			else:
				setupList.append((indent + _("Automatic update interval"), config.plugins.opentvzapper.update_interval, _("Set automatic update interval (in hours).")))
			setupList.append((_("Show in extensions"), config.plugins.opentvzapper.extensions, _("When enabled a forced download will be possible from the extensions menu (blue button). Shows after next restart.")))
			setupList.append((_("Show notifications"), config.plugins.opentvzapper.notifications, _("Show on-screen notifications (pop up) to warn the OpenTV download is in progress.")))
			if SystemInfo.get("PIPAvailable", False):
				setupList.append((_("Use PiP for download"), config.plugins.opentvzapper.use_pip_adapter, _("If enabled and PiP is available, PiP will be used for the download. If disabled or Pip is unavailable the download will be done as a fake recording.")))
		self["config"].list = setupList


class OpentvZapperDaysScreen(Setup):
	def __init__(self, session, args=0):
		self.config = config.plugins.opentvzapper
		Setup.__init__(self, session, setup=None)
		self.title = _('OpentvZapper') + " - " + _("Select days")

	def createSetup(self):
		days = (_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"), _("Friday"), _("Saturday"), _("Sunday"))
		self["config"].list = [(days[i], self.config.days[i]) for i in sorted(list(self.config.days.keys()))]

	def keySave(self):
		if not any([self.config.days[i].value for i in self.config.days]):
			info = self.session.open(MessageBox, _("At least one day of the week must be selected"), MessageBox.TYPE_ERROR, timeout=30)
			info.setTitle(_('OpentvZapper') + " - " + _("Select days"))
			return
		Setup.keySave(self)


def startdownload(session, **kwargs): # Called from extensions menu if this option is active
	opentv_zapper.force_download()


def OpentvZapperStart(menuid, **kwargs): # Menu position of plugin setup screen
	if menuid == "epg":
		return [(_("OpenTV EPG downloader"), OpentvZapperMain, "OpentvZapper_Setup", None)]
	return []


def OpentvZapperMain(session, **kwargs): # calls setup screen
	session.open(OpentvZapper_Setup)


def OpentvZapperWakeupTime(): # Called on shutdown (going into deep standby) to tell the box when to wake from deep
	print("[OpentvZapper] next wake up due %d" % (config.plugins.opentvzapper.schedule.value and config.plugins.opentvzapper.schedulewakefromdeep.value and config.plugins.opentvzapper.nextscheduletime.value > 0 and config.plugins.opentvzapper.nextscheduletime.value or -1))
	return config.plugins.opentvzapper.schedule.value and config.plugins.opentvzapper.schedulewakefromdeep.value and config.plugins.opentvzapper.nextscheduletime.value > 0 and config.plugins.opentvzapper.nextscheduletime.value or -1


def Plugins(**kwargs):
	plist = []
	if nimmanager.hasNimType("DVB-S"):
		plist.append(PluginDescriptor(name=_("OpentvZapper"), description=description, where=PluginDescriptor.WHERE_MENU, needsRestart=True, fnc=OpentvZapperStart))
		plist.append(PluginDescriptor(name="OpentvZapperScheduler", where=[PluginDescriptor.WHERE_AUTOSTART, PluginDescriptor.WHERE_SESSIONSTART], fnc=startSession, wakeupfnc=OpentvZapperWakeupTime, needsRestart=True))
		if config.plugins.opentvzapper.enabled.value and config.plugins.opentvzapper.extensions.value:
			plist.append(PluginDescriptor(name=_("OpenTV EPG forced download"), description=description, where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=startdownload, needsRestart=True))
	return plist
