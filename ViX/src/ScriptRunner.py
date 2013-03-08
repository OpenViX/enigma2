# for localized messages
from . import _

from Screens.Screen import Screen
from Screens.Console import Console
from Components.Sources.StaticText import StaticText
from IPKInstaller import IpkgInstaller

class VIXScriptRunner(IpkgInstaller):
	def __init__(self, session, list=[]):
		IpkgInstaller.__init__(self, session, list)
		Screen.setTitle(self, _("Script Runner"))
		self.skinName = "IpkgInstaller"
		self["key_green"] = StaticText(_("Run"))

	def install(self):
		list = self.list.getSelectionsList()
		cmdList = []
		for item in list:
			cmdList.append('chmod +x /usr/script/'+item[0]+' && . ' + '/usr/script/'+str(item[0]))
		if len(cmdList) < 1 and len(self.list.list):
			cmdList.append('chmod +x /usr/script/'+self.list.getCurrent()[0][0]+' && . ' + '/usr/script/'+str(self.list.getCurrent()[0][0]))
		if len(cmdList) > 0:
			self.session.open(Console, cmdlist = cmdList, closeOnSuccess = False)
