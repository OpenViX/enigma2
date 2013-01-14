# for localized messages
from . import _

from Screens.Screen import Screen
from Screens.Console import Console
from Components.Sources.StaticText import StaticText
from IPKInstaller import IpkgInstaller
from os import listdir, path, mkdir

class VIXScriptRunner(IpkgInstaller):
	def __init__(self, session, list=[]):
		IpkgInstaller.__init__(self, session, list)
		Screen.setTitle(self, _("Script Runner"))
		self.skinName = "IpkgInstaller"

		if not path.exists('/usr/script'):
			mkdir('/usr/script', 0755)
		f = listdir('/usr/script')
		for line in f:
			parts = line.split()
			pkg = parts[0]
			if pkg.find('.sh') >= 0:
				list.append(pkg)

	def install(self):
		list = self.list.getSelectionsList()
		cmdList = []
		for item in list:
			cmdList.append('chmod +x /usr/script/'+item[0]+' && . ' + '/usr/script/'+str(item[0]))
		print 'CMDLIST',cmdList
		self.session.open(Console, cmdlist = cmdList, closeOnSuccess = False)
