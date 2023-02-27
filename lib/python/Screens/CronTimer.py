from os import system, listdir, rename, path, mkdir
from time import sleep

from boxbranding import getImageType
from Components.ActionMap import ActionMap
from Components.config import getConfigListEntry, ConfigText, ConfigSelection, ConfigInteger, ConfigClock
from Components.ConfigList import ConfigListScreen
from Components.Console import Console
from Components.Label import Label
from Components.Sources.List import List
from Components.OnlineUpdateCheck import feedsstatuscheck
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists


class CronTimers(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		if path.exists('/usr/scripts') and not path.exists('/usr/script'):
			rename('/usr/scripts', '/usr/script')
		if not path.exists('/usr/script'):
			mkdir('/usr/script', 0o755)
		self.setTitle(_("Cron Manager"))
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Active")))
		self['labdisabled'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['labrun'].hide()
		self['labactive'].hide()
		self['footnote'] = Label(_("Press OK to show details"))
		self['footnote'].hide()
		self.summary_running = ''
		self['key'] = Label(_("H: = Hourly / D: = Daily / W: = Weekly / M: = Monthly"))
		self.Console = Console()
		self.ConsoleB = Console(binary=True)
		self.my_crond_active = False
		self.my_crond_run = False

		self['key_red'] = Label(_("Delete"))
		self['key_green'] = Label(_("Add"))
		self['key_yellow'] = Label(_("Start"))
		self['key_blue'] = Label(_("Autostart"))
		self.list = []
		self['list'] = List(self.list)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', "MenuActions"], {
			'ok': self.info, 
			'back': self.UninstallCheck, 
			'red': self.delcron, 
			'green': self.addtocron, 
			'yellow': self.CrondStart, 
			'blue': self.autostart,
			})
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)
		self.service_name = 'cronie'
		self.onLayoutFinish.append(self.InstallCheck)

	def InstallCheck(self):
		self.Console.ePopen('/usr/bin/opkg list_installed ' + self.service_name, self.checkNetworkState)

	def checkNetworkState(self, result, retval, extra_args):
		if 'Collected errors' in result:
			self.session.openWithCallback(self.close, MessageBox, _("A background update check is in progress, please wait a few minutes and try again."), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
		elif not result:
			if (getImageType() != 'release' and feedsstatuscheck.getFeedsBool() != 'unknown') or (getImageType() == 'release' and feedsstatuscheck.getFeedsBool() not in ('stable', 'unstable')):
				self.session.openWithCallback(self.InstallPackageFailed, MessageBox, feedsstatuscheck.getFeedsErrorMessage(), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
			else:
				self.session.openWithCallback(self.InstallPackage, MessageBox, _('Ready to install "%s" ?') % self.service_name, MessageBox.TYPE_YESNO)
		else:
			self.updateList()

	def InstallPackage(self, val):
		if val:
			self.doInstall(self.installComplete, self.service_name)
		else:
			self.close()

	def InstallPackageFailed(self, val):
		self.close()

	def doInstall(self, callback, pkgname):
		self.message = self.session.open(MessageBox, _("Please wait..."), MessageBox.TYPE_INFO, enable_input=False)
		self.message.setTitle(_('Installing service'))
		self.ConsoleB.ePopen('/usr/bin/opkg install ' + pkgname, callback)

	def installComplete(self, result=None, retval=None, extra_args=None):
		self.message.close()
		self.updateList()

	def UninstallCheck(self):
		if not self.my_crond_run:
			self.ConsoleB.ePopen('/usr/bin/opkg list_installed ' + self.service_name, self.RemovedataAvail)
		else:
			self.close()

	def RemovedataAvail(self, result, retval, extra_args):
		if result:
			self.session.openWithCallback(self.RemovePackage, MessageBox, _('Ready to remove "%s" ?') % self.service_name)
		else:
			self.close()

	def RemovePackage(self, val):
		if val:
			self.doRemove(self.removeComplete, self.service_name)
		else:
			self.close()

	def doRemove(self, callback, pkgname):
		self.message = self.session.open(MessageBox, _("Please wait..."), MessageBox.TYPE_INFO, enable_input=False)
		self.message.setTitle(_('Removing service'))
		self.ConsoleB.ePopen('/usr/bin/opkg remove ' + pkgname + ' --force-remove --autoremove', callback)

	def removeComplete(self, result=None, retval=None, extra_args=None):
		self.message.close()
		self.close()

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		try:
			if self["list"].getCurrent():
				name = str(self["list"].getCurrent()[0])
			else:
				name = ""
		except:
			name = ""
		desc = _("Current Status:") + ' ' + self.summary_running
		for cb in self.onChangedEntry:
			cb(name, desc)

	def CrondStart(self):
		if not self.my_crond_run:
			self.ConsoleB.ePopen('/etc/init.d/crond start', self.StartStopCallback)
		elif self.my_crond_run:
			self.ConsoleB.ePopen('/etc/init.d/crond stop', self.StartStopCallback)

	def StartStopCallback(self, result=None, retval=None, extra_args=None):
		sleep(3)
		self.updateList()

	def autostart(self):
		if fileExists('/etc/rc2.d/S90crond'):
			self.ConsoleB.ePopen('update-rc.d -f crond remove')
		else:
			self.ConsoleB.ePopen('update-rc.d -f crond defaults 90 60')
		sleep(3)
		self.updateList()

	def addtocron(self):
		self.session.openWithCallback(self.updateList, CronTimersConfig)

	def updateList(self, result=None, retval=None, extra_args=None):
		import process
		p = process.ProcessList()
		crond_process = str(p.named('crond')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].hide()
		self['labdisabled'].hide()
		self.my_crond_active = False
		self.my_crond_run = False
		self['footnote'].hide()
		if path.exists('/etc/rc3.d/S90crond'):
			self['labdisabled'].hide()
			self['labactive'].show()
			self.my_crond_active = True
		else:
			self['labactive'].hide()
			self['labdisabled'].show()
		if crond_process:
			self.my_crond_run = True
		if self.my_crond_run:
			self['labstop'].hide()
			self['labrun'].show()
			self['key_yellow'].setText(_("Stop"))
			self.summary_running = _("Running")
		else:
			self['labstop'].show()
			self['labrun'].hide()
			self['key_yellow'].setText(_("Start"))
			self.summary_running = _("Stopped")

		self.list = []
		if path.exists('/etc/cron/crontabs/root'):
			f = open('/etc/cron/crontabs/root', 'r')
			for line in f.readlines():
				parts = line.strip().split(maxsplit=5)
				if parts and len(parts) == 6:
					if parts[1] == '*':
						line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
					elif parts[2] == '*' and parts[4] == '*':
						line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
					elif parts[3] == '*':
						if parts[4] == "*":
							line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + '\t' + parts[5]
						header = 'W:  '
						day = ""
						if str(parts[4]).find('0') >= 0:
							day = 'Sun '
						if str(parts[4]).find('1') >= 0:
							day += 'Mon '
						if str(parts[4]).find('2') >= 0:
							day += 'Tues '
						if str(parts[4]).find('3') >= 0:
							day += 'Wed '
						if str(parts[4]).find('4') >= 0:
							day += 'Thurs '
						if str(parts[4]).find('5') >= 0:
							day += 'Fri '
						if str(parts[4]).find('6') >= 0:
							day += 'Sat '

						if day:
							line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
			f.close()
		if len(self.list):
			self['footnote'].show()
		self['list'].list = self.list
		self["actions"].setEnabled(True)

	def delcron(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			parts = self.sel[0]
			parts = parts.split('\t')
			message = _("Are you sure you want to delete this:\n ") + parts[1]
			ybox = self.session.openWithCallback(self.doDelCron, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Remove Confirmation"))

	def doDelCron(self, answer):
		if answer:
			mysel = self['list'].getCurrent()
			if mysel:
				myline = mysel[1]
				open('/etc/cron/crontabs/root.tmp', 'w').writelines([l for l in open('/etc/cron/crontabs/root').readlines() if myline not in l])
				rename('/etc/cron/crontabs/root.tmp', '/etc/cron/crontabs/root')
				rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
				self.updateList()

	def info(self):
		mysel = self['list'].getCurrent()
		if mysel:
			myline = mysel[1]
			self.session.open(MessageBox, _(myline), MessageBox.TYPE_INFO)


class CronTimersConfig(Setup):
	def __init__(self, session):
		self.commandtype = ConfigSelection(choices=[('custom', _("Custom")), ('predefined', _("Predefined"))])
		self.cmdtime = ConfigClock(default=(0, 0))
		self.user_command = ConfigText(fixed_size=False)
		self.runwhen = ConfigSelection(default='Daily', choices=[('Hourly', _("Hourly")), ('Daily', _("Daily")), ('Weekly', _("Weekly")), ('Monthly', _("Monthly"))])
		self.dayofweek = ConfigSelection(default='Monday', choices=[('Monday', _("Monday")), ('Tuesday', _("Tuesday")), ('Wednesday', _("Wednesday")), ('Thursday', _("Thursday")), ('Friday', _("Friday")), ('Saturday', _("Saturday")), ('Sunday', _("Sunday"))])
		self.dayofmonth = ConfigInteger(default=1, limits=(1, 31))
		self.createConfig()
		Setup.__init__(self, session, None)
		self.setTitle(_("Cron Manager Setup"))

	def createConfig(self):
		predefinedlist = []
		f = listdir('/usr/script')
		if f:
			for line in f:
				parts = line.split()
				path = "/usr/script/"
				pkg = parts[0]
				description = path + parts[0]
				if pkg.find('.sh') >= 0:
					predefinedlist.append((description, pkg))
			predefinedlist.sort()
		self.predefined_command = ConfigSelection(choices=predefinedlist)

	def createSetup(self):
		self.list = []
		self.list.append(getConfigListEntry(_("Run how often ?"), self.runwhen))
		if self.runwhen.value != 'Hourly':
			self.list.append(getConfigListEntry(_("Time to execute command or script"), self.cmdtime))
		if self.runwhen.value == 'Weekly':
			self.list.append(getConfigListEntry(_("What day of week ?"), self.dayofweek))
		if self.runwhen.value == 'Monthly':
			self.list.append(getConfigListEntry(_("What date of month ?"), self.dayofmonth))
		self.list.append(getConfigListEntry(_("Command type"), self.commandtype))
		if self.commandtype.value == 'custom':
			self.list.append(getConfigListEntry(_("Command to run"), self.user_command))
		else:
			self.list.append(getConfigListEntry(_("Command to run"), self.predefined_command))
		self["config"].list = self.list

	def changedEntry(self):
		if self["config"].getCurrent()[1] in (self.runwhen, self.commandtype):
			self.createSetup()
		ConfigListScreen.changedEntry(self) # update callbacks

	def keySave(self):
		msg = ''
		if (self.commandtype.value == 'predefined' and self.predefined_command.value == '') or self.commandtype.value == 'custom' and self.user_command.value == '':
			msg = 'You must set at least one Command'
		if msg:
			self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
		else:
			self.saveMycron()

	def saveMycron(self):
		hour = '%02d' % self.cmdtime.value[0]
		minutes = '%02d' % self.cmdtime.value[1]
		if self.commandtype.value == 'predefined' and self.predefined_command.value != '':
			command = self.predefined_command.value
		else:
			command = self.user_command.value

		if self.runwhen.value == 'Hourly':
			newcron = minutes + ' ' + ' * * * * ' + command.strip() + '\n'
		elif self.runwhen.value == 'Daily':
			newcron = minutes + ' ' + hour + ' * * * ' + command.strip() + '\n'
		elif self.runwhen.value == 'Weekly':
			if self.dayofweek.value == 'Sunday':
				newcron = minutes + ' ' + hour + ' * * 0 ' + command.strip() + '\n'
			elif self.dayofweek.value == 'Monday':
				newcron = minutes + ' ' + hour + ' * * 1 ' + command.strip() + '\n'
			elif self.dayofweek.value == 'Tuesday':
				newcron = minutes + ' ' + hour + ' * * 2 ' + command.strip() + '\n'
			elif self.dayofweek.value == 'Wednesday':
				newcron = minutes + ' ' + hour + ' * * 3 ' + command.strip() + '\n'
			elif self.dayofweek.value == 'Thursday':
				newcron = minutes + ' ' + hour + ' * * 4 ' + command.strip() + '\n'
			elif self.dayofweek.value == 'Friday':
				newcron = minutes + ' ' + hour + ' * * 5 ' + command.strip() + '\n'
			elif self.dayofweek.value == 'Saturday':
				newcron = minutes + ' ' + hour + ' * * 6 ' + command.strip() + '\n'
		elif self.runwhen.value == 'Monthly':
			newcron = minutes + ' ' + hour + ' ' + str(self.dayofmonth.value) + ' * * ' + command.strip() + '\n'
		else:
			command = self.user_command.value

		out = open('/etc/cron/crontabs/root', 'a')
		out.write(newcron)
		out.close()
		rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
		self.close()
