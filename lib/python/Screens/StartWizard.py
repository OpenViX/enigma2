from Components.config import config, ConfigBoolean, configfile
from Components.Pixmap import Pixmap
from Screens.LanguageSelection import LanguageWizard  # noqa: F401
from Screens.Rc import Rc
from Screens.WizardLanguage import WizardLanguage
from Screens.WizardUserInterfacePositioner import UserInterfacePositionerWizard
from Screens.Wizard import wizardManager
from Screens.VideoWizard import VideoWizard
from Screens.VuWizard import VuWizard
from Tools.Directories import fileExists, fileHas

config.misc.firstrun = ConfigBoolean(default=True)
config.misc.languageselected = ConfigBoolean(default=True)
config.misc.videowizardenabled = ConfigBoolean(default=True)
config.misc.networkenabled = ConfigBoolean(default=False)
config.misc.Vuwizardenabled = ConfigBoolean(default=False)
config.misc.restorewizardrun = ConfigBoolean(default=False)

if fileExists("/usr/bin/kernel_auto.bin") and fileExists("/usr/bin/STARTUP.cpio.gz") and not fileHas("/proc/cmdline", "kexec=1") and config.misc.firstrun.value:
	config.misc.Vuwizardenabled.value = True
print("[StartWizard][import] import.......")


class StartWizard(WizardLanguage, Rc):
	def __init__(self, session, silent=True, showSteps=False, neededTag=None):
		self.xmlfile = ["startwizard.xml"]
		WizardLanguage.__init__(self, session, showSteps=False)
		Rc.__init__(self)
		self["wizard"] = Pixmap()

	def markDone(self):
		config.misc.rcused.value = 1  # setup remote control, all stb have same settings
		config.misc.rcused.save()

		config.misc.firstrun.value = 0
		config.misc.firstrun.save()
		configfile.save()


# wizardManager.registerWizard(VideoWizard, config.misc.Vuwizardenabled.value, priority=2)
wizardManager.registerWizard(VuWizard, config.misc.Vuwizardenabled.value, priority=3)
wizardManager.registerWizard(VideoWizard, config.misc.videowizardenabled.value, priority=10)
wizardManager.registerWizard(UserInterfacePositionerWizard, config.misc.firstrun.value, priority=20)
wizardManager.registerWizard(StartWizard, config.misc.firstrun.value, priority=25)
