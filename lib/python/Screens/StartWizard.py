from Wizard import wizardManager
from Screens.MessageBox import MessageBox
from Screens.WizardLanguage import WizardLanguage
from Screens.Rc import Rc
from Tools.HardwareInfo import HardwareInfo
from Components.Language import language
try:
	from Plugins.SystemPlugins.OSDPositionSetup.overscanwizard import OverscanWizard
except:
	OverscanWizard = None

from boxbranding import getBoxType

from Components.About import about
from Components.Pixmap import Pixmap
from Components.config import config, ConfigBoolean, configfile
from Components.SystemInfo import SystemInfo
from LanguageSelection import LanguageWizard

config.misc.firstrun = ConfigBoolean(default=True)
config.misc.languageselected = ConfigBoolean(default=True)
config.misc.ask_languagedeletion = ConfigBoolean(default=True)
config.misc.do_deletelanguage = ConfigBoolean(default=False)

if OverscanWizard:
	#config.misc.do_overscanwizard = ConfigBoolean(default = OverscanWizard and config.skin.primary_skin.value == "PLi-FullNightHD/skin.xml")
	config.misc.do_overscanwizard = ConfigBoolean(default=True)
else:
	config.misc.do_overscanwizard = ConfigBoolean(default=False)
config.misc.check_developimage = ConfigBoolean(default=True)


class StartWizard(WizardLanguage, Rc):
	def __init__(self, session, silent=True, showSteps=False, neededTag=None):
		self.xmlfile = ["startwizard.xml"]
		WizardLanguage.__init__(self, session, showSteps=False)
		Rc.__init__(self)
		self["wizard"] = Pixmap()

	def markDone(self):
		# setup remote control, all stb have same settings except dm8000 which uses a different settings
		if HardwareInfo().get_device_name() == 'dm8000':
			config.misc.rcused.value = 0
		else:
			config.misc.rcused.value = 1
		config.misc.rcused.save()

		config.misc.firstrun.value = 0
		config.misc.firstrun.save()
		configfile.save()


def checkForDevelopImage():
	if "DEV" in about.getImageTypeString() or "beta" in about.getImageTypeString():
		return config.misc.check_developimage.value
	elif not config.misc.check_developimage.value:
		config.misc.check_developimage.value = True
		config.misc.check_developimage.save()


class DevelopWizard(MessageBox):
	def __init__(self, session):
		MessageBox.__init__(self, session, _("This image is intended for developers and testers.\nNo support will be provided!\nDo you understand this?"), type=MessageBox.TYPE_YESNO, timeout=20, default=False, simple=True)

	def close(self, value):
		if value:
			config.misc.check_developimage.value = False
			config.misc.check_developimage.save()
		MessageBox.close(self)


class LanguageDeleteWizard(MessageBox):
	def __init__(self, session):
            MessageBox.__init__(self, session, _("Do you want to remove all unused translations?"), type=MessageBox.TYPE_YESNO, timeout=20, default=False, simple=True)

	def close(self, value):
		if value:
			language.delLanguage()
			config.misc.do_deletelanguage.value = True
			config.misc.do_deletelanguage.save()
                config.misc.ask_languagedeletion.value = False
                config.misc.ask_languagedeletion.save()
		configfile.save()
		MessageBox.close(self)


wizardManager.registerWizard(DevelopWizard, checkForDevelopImage(), priority=0)
wizardManager.registerWizard(LanguageWizard, config.misc.languageselected.value, priority=10)
wizardManager.registerWizard(LanguageDeleteWizard, config.misc.ask_languagedeletion.value, priority=10)
if OverscanWizard:
	wizardManager.registerWizard(OverscanWizard, config.misc.do_overscanwizard.value, priority=20)
wizardManager.registerWizard(StartWizard, config.misc.firstrun.value, priority=25)
