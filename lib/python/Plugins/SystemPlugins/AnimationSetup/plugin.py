from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Components.config import config, ConfigYesNo, getConfigListEntry
from Plugins.Plugin import PluginDescriptor

from enigma import setAnimation_current, getEGLVersionString

try:
	from enigma import setAnimation_lists  # EGL list animations, not in every build
except ImportError:
	setAnimation_lists = None

config.misc.window_animation_enabled = ConfigYesNo(default=False)


def applyAnimations():
	# Windows are not animated (the snapshots of a whole window are too slow to read back on some GPUs);
	# only the lists and controls are, with the rules of the skin (skin.ani).
	setAnimation_current(0)
	if getEGLVersionString() and setAnimation_lists is not None:
		setAnimation_lists(1 if config.misc.window_animation_enabled.value else 0)


class AnimationSetupScreen(ConfigListScreen, Screen):
	skin = """
		<screen name="AnimationSetup" position="center,center" size="600,140" title="Animations">
			<widget name="config" position="0,0" size="600,100" scrollbarMode="showOnDemand" />
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,100" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,100" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,100" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" foregroundColor="#ffffff" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,100" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" foregroundColor="#ffffff" backgroundColor="#1f771f" transparent="1" />
		</screen>
			"""

	def __init__(self, session):
		Screen.__init__(self, session)
		ConfigListScreen.__init__(self, [getConfigListEntry(_("Enable animations"), config.misc.window_animation_enabled)])
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
			{
			"ok": self.keyGreen,
			"green": self.keyGreen,
			"red": self.keyRed,
			"cancel": self.keyRed,
			}, -2)  # noqa: E123
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))

	def keyGreen(self):
		config.misc.window_animation_enabled.save()
		applyAnimations()
		self.close()

	def keyRed(self):
		config.misc.window_animation_enabled.cancel()
		self.close()


def animationSetupMain(session, **kwargs):
	session.open(AnimationSetupScreen)


def startAnimationSetup(menuid):
	if menuid != "gui_menu":
		return []

	return [(_("Animations"), animationSetupMain, "animation_setup", 11)]


def sessionAnimationSetup(session, reason, **kwargs):
	applyAnimations()


def Plugins(**kwargs):
	plugin_list = [
		PluginDescriptor(
			name="Animations",
			description="Setup UI animations",
			where=PluginDescriptor.WHERE_MENU,
			needsRestart=False,
			fnc=startAnimationSetup),
		PluginDescriptor(
			where=PluginDescriptor.WHERE_SESSIONSTART,
			needsRestart=False,
			fnc=sessionAnimationSetup),
	]
	return plugin_list
