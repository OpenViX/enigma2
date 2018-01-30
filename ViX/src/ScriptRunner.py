# for localized messages
from . import _, PluginLanguageDomain

from Screens.Screen import Screen
from Screens.Console import Console
from Screens.Setup import Setup
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.config import config, ConfigSubsection, ConfigYesNo
from IPKInstaller import IpkgInstaller
from Components.PluginComponent import plugins
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from os import path, mkdir, listdir

config.scriptrunner = ConfigSubsection()
config.scriptrunner.close = ConfigYesNo(default=False)
config.scriptrunner.showinextensions = ConfigYesNo(default=False)

def updateExtensions(configElement):
	plugins.clearPluginList()
	plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
config.scriptrunner.showinextensions.addNotifier(updateExtensions, initial_call=False)


def ScriptRunnerAutostart(reason, session=None, **kwargs):
	pass

class VIXScriptRunner(IpkgInstaller):
	def __init__(self, session, list=None, menu_path=""):
		if not list:
			list = []
			if not path.exists('/usr/scripts'):
				mkdir('/usr/scripts', 0755)
			f = listdir('/usr/scripts')
			for line in f:
				parts = line.split()
				pkg = parts[0]
				if pkg.find('.sh') >= 0:
					list.append(pkg)
		IpkgInstaller.__init__(self, session, list)
		screentitle =  _("Script runner")
		self.menu_path = menu_path
		if config.usage.show_menupath.value == 'large':
			self.menu_path += screentitle
			title = self.menu_path
			self["menu_path_compressed"] = StaticText("")
			self.menu_path += ' / '
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			condtext = ""
			if self.menu_path and not self.menu_path.endswith(' / '):
				condtext = self.menu_path + " >"
			elif self.menu_path:
				condtext = self.menu_path[:-3] + " >"
			self["menu_path_compressed"] = StaticText(condtext)
			self.menu_path += screentitle + ' / '
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self.skinName = ["VIXScriptRunner", "IpkgInstaller"]
		self["key_green"] = StaticText(_("Run"))

		self['myactions'] = ActionMap(["MenuActions"],
									  {
									  "menu": self.createSetup,
									  }, -1)

	def createSetup(self):
		self.session.open(Setup, 'vixscriptrunner', 'SystemPlugins/ViX', self.menu_path, PluginLanguageDomain)

	def install(self):
		list = self.list.getSelectionsList()
		cmdList = []
		for item in list:
			cmdList.append('chmod +x /usr/scripts/' + item[0] + ' && . ' + '/usr/scripts/' + str(item[0]))
		if len(cmdList) < 1 and len(self.list.list):
			cmdList.append('chmod +x /usr/scripts/' + self.list.getCurrent()[0][0] + ' && . ' + '/usr/scripts/' + str(self.list.getCurrent()[0][0]))
		if len(cmdList) > 0:
			self.session.open(Console, cmdlist=cmdList, closeOnSuccess=config.scriptrunner.close.value)
