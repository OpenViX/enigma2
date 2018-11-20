from Components.ActionMap import ActionMap
from Components.config import getConfigListEntry, config, ConfigSubsection, ConfigText, ConfigSelection, ConfigInteger, ConfigClock, NoSave
from Components.ConfigList import ConfigListScreen
from Components.Console import Console
from Components.Label import Label
from Components.Sources.List import List
from Components.Pixmap import Pixmap
from Components.OnlineUpdateCheck import feedsstatuscheck
from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists
from os import system, listdir, rename, path, mkdir
from time import sleep
from boxbranding import getMachineBrand, getMachineName, getImageType

class CronTimers(Screen):
	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		if path.exists('/usr/scripts'):
			rename('/usr/scripts', '/usr/script')
		if not path.exists('/usr/script'):
			mkdir('/usr/script', 0755)
		screentitle = _("Cron manager")
		menu_path += screentitle
		if config.usage.show_menupath.value == 'large':
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			print 'menu_path:',menu_path
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)
		self.onChangedEntry = [ ]
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Active")))
		self['labdisabled'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['labrun'].hide()
		self['labactive'].hide()
		self.summary_running = ''
		self['key'] = Label(_("H: = Hourly / D: = Daily / W: = Weekly / M: = Monthly"))
		self.Console = Console()
		self.my_crond_active = False
		self.my_crond_run = False

		self['key_red'] = Label(_("Delete"))
		self['key_green'] = Label(_("Add"))
		self['key_yellow'] = Label(_("Start"))
		self['key_blue'] = Label(_("Autostart"))
		self.list = []
		self['list'] = List(self.list)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', "MenuActions"], {'ok': self.info, 'back': self.UninstallCheck, 'red': self.delcron, 'green': self.addtocron, 'yellow': self.CrondStart, 'blue': self.autostart})
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)
		self.service_name = 'cronie'
		self.onLayoutFinish.append(self.InstallCheck)

	def InstallCheck(self):
		self.Console.ePopen('/usr/bin/opkg list_installed ' + self.service_name, self.checkNetworkState)

	def checkNetworkState(self, str, retval, extra_args):
		if 'Collected errors' in str:
			self.session.openWithCallback(self.close, MessageBox, _("A background update check is in progress, please wait a few minutes and try again."), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
		elif not str:
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
		self.message = self.session.open(MessageBox,_("Please wait..."), MessageBox.TYPE_INFO, enable_input = False)
		self.message.setTitle(_('Installing service'))
		self.Console.ePopen('/usr/bin/opkg install ' + pkgname, callback)

	def installComplete(self,result = None, retval = None, extra_args = None):
		self.message.close()
		self.updateList()

	def UninstallCheck(self):
		if not self.my_crond_run:
			self.Console.ePopen('/usr/bin/opkg list_installed ' + self.service_name, self.RemovedataAvail)
		else:
			self.close()

	def RemovedataAvail(self, str, retval, extra_args):
		if str:
			self.session.openWithCallback(self.RemovePackage, MessageBox, _('Ready to remove "%s" ?') % self.service_name)
		else:
			self.close()

	def RemovePackage(self, val):
		if val:
			self.doRemove(self.removeComplete, self.service_name)
		else:
			self.close()

	def doRemove(self, callback, pkgname):
		self.message = self.session.open(MessageBox,_("Please wait..."), MessageBox.TYPE_INFO, enable_input = False)
		self.message.setTitle(_('Removing service'))
		self.Console.ePopen('/usr/bin/opkg remove ' + pkgname + ' --force-remove --autoremove', callback)

	def removeComplete(self, result = None, retval = None, extra_args = None):
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
		desc = _("Current Status:") + ' ' +self.summary_running
		for cb in self.onChangedEntry:
			cb(name, desc)

	def CrondStart(self):
		if not self.my_crond_run:
			self.Console.ePopen('/etc/init.d/crond start', self.StartStopCallback)
		elif self.my_crond_run:
			self.Console.ePopen('/etc/init.d/crond stop', self.StartStopCallback)

	def StartStopCallback(self, result = None, retval = None, extra_args = None):
		sleep(3)
		self.updateList()

	def autostart(self):
		if fileExists('/etc/rc2.d/S90crond'):
			self.Console.ePopen('update-rc.d -f crond remove')
		else:
			self.Console.ePopen('update-rc.d -f crond defaults 90 60')
		sleep(3)
		self.updateList()

	def addtocron(self):
		self.session.openWithCallback(self.updateList, CronTimersConfig)

	def updateList(self, result = None, retval = None, extra_args = None):
		import process
		p = process.ProcessList()
		crond_process = str(p.named('crond')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].hide()
		self['labdisabled'].hide()
		self.my_crond_active = False
		self.my_crond_run = False
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
				parts = line.strip().split()
				if parts:
					if parts[1] == '*':
						try:
							line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
						except:
							try:
								line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
							except:
								try:
									line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
								except:
									try:
										line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
									except:
										line2 = 'H: 00:' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
					elif parts[2] == '*' and parts[4] == '*':
						try:
							line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
						except:
							try:
								line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
							except:
								try:
									line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
								except:
									try:
										line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
									except:
										line2 = 'D: ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
					elif parts[3] == '*':
						if parts[4] == "*":
							try:
								line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
							except:
								try:
									line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
								except:
									try:
										line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
									except:
										try:
											line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
										except:
											line2 = 'M:  Day ' + parts[2] + '  ' + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
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
							try:
								line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8] + parts[9]
							except:
								try:
									line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7] + parts[8]
								except:
									try:
										line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6] + parts[7]
									except:
										try:
											line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5] + parts[6]
										except:
											line2 = header + day + parts[1].zfill(2) + ':' + parts[0].zfill(2) + '\t' + parts[5]
						res = (line2, line)
						self.list.append(res)
			f.close()
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
				file('/etc/cron/crontabs/root.tmp', 'w').writelines([l for l in file('/etc/cron/crontabs/root').readlines() if myline not in l])
				rename('/etc/cron/crontabs/root.tmp','/etc/cron/crontabs/root')
				rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
				self.updateList()

	def info(self):
		mysel = self['list'].getCurrent()
		if mysel:
			myline = mysel[1]
			self.session.open(MessageBox, _(myline), MessageBox.TYPE_INFO)

config.crontimers = ConfigSubsection()
config.crontimers.commandtype = NoSave(ConfigSelection(choices = [ ('custom',_("Custom")),('predefined',_("Predefined")) ]))
config.crontimers.cmdtime = NoSave(ConfigClock(default=0))
config.crontimers.cmdtime.value, mytmpt = ([0, 0], [0, 0])
config.crontimers.user_command = NoSave(ConfigText(fixed_size=False))
config.crontimers.runwhen = NoSave(ConfigSelection(default='Daily', choices = [('Hourly', _("Hourly")),('Daily', _("Daily")),('Weekly', _("Weekly")),('Monthly', _("Monthly"))]))
config.crontimers.dayofweek = NoSave(ConfigSelection(default='Monday', choices = [('Monday', _("Monday")),('Tuesday', _("Tuesday")),('Wednesday', _("Wednesday")),('Thursday', _("Thursday")),('Friday', _("Friday")),('Saturday', _("Saturday")),('Sunday', _("Sunday"))]))
config.crontimers.dayofmonth = NoSave(ConfigInteger(default=1, limits=(1, 31)))

class CronTimersConfig(Screen, ConfigListScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Cron Manager"))
		self.skinName = "Setup"
		self.onChangedEntry = [ ]
		self.list = []
		ConfigListScreen.__init__(self, self.list, session = self.session, on_change = self.changedEntry)
		self['key_red'] = Label(_("Close"))
		self['key_green'] = Label(_("Save"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', "MenuActions"], 
		{
			'red': self.close,
			'green': self.checkentry,
			'back': self.close,
			'showVirtualKeyboard': self.KeyText,
		})
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self["VKeyIcon"] = Boolean(False)
		self.createSetup()

	def createSetup(self):
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
		config.crontimers.predefined_command = NoSave(ConfigSelection(choices = predefinedlist))
		self.editListEntry = None

		self.list = []
		self.list.append(getConfigListEntry(_("Run how often ?"), config.crontimers.runwhen))
		if config.crontimers.runwhen.value != 'Hourly':
			self.list.append(getConfigListEntry(_("Time to execute command or script"), config.crontimers.cmdtime))
		if config.crontimers.runwhen.value == 'Weekly':
			self.list.append(getConfigListEntry(_("What day of week ?"), config.crontimers.dayofweek))
		if config.crontimers.runwhen.value == 'Monthly':
			self.list.append(getConfigListEntry(_("What date of month ?"), config.crontimers.dayofmonth))
		self.list.append(getConfigListEntry(_("Command type"), config.crontimers.commandtype))
		if config.crontimers.commandtype.value == 'custom':
			self.list.append(getConfigListEntry(_("Command to run"), config.crontimers.user_command))
		else:
			self.list.append(getConfigListEntry(_("Command to run"), config.crontimers.predefined_command))
		self["config"].list = self.list
		self["config"].setList(self.list)

	# for summary:
	def changedEntry(self):
		ConfigListScreen.changedEntry(self)
		if self["config"].getCurrent()[1] in (config.crontimers.runwhen, config.crontimers.commandtype):
			self.createSetup()

	def checkentry(self):
		msg = ''
		if (config.crontimers.commandtype.value == 'predefined' and config.crontimers.predefined_command.value == '') or config.crontimers.commandtype.value == 'custom' and config.crontimers.user_command.value == '':
			msg = 'You must set at least one Command'
		if msg:
			self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
		else:
			self.saveMycron()

	def saveMycron(self):
		hour = '%02d' % config.crontimers.cmdtime.value[0]
		minutes = '%02d' % config.crontimers.cmdtime.value[1]
		if config.crontimers.commandtype.value == 'predefined' and config.crontimers.predefined_command.value != '':
			command = config.crontimers.predefined_command.value
		else:
			command = config.crontimers.user_command.value

		if config.crontimers.runwhen.value == 'Hourly':
			newcron = minutes + ' ' + ' * * * * ' + command.strip() + '\n'
		elif config.crontimers.runwhen.value == 'Daily':
			newcron = minutes + ' ' + hour + ' * * * ' + command.strip() + '\n'
		elif config.crontimers.runwhen.value == 'Weekly':
			if config.crontimers.dayofweek.value == 'Sunday':
				newcron = minutes + ' ' + hour + ' * * 0 ' + command.strip() + '\n'
			elif config.crontimers.dayofweek.value == 'Monday':
				newcron = minutes + ' ' + hour + ' * * 1 ' + command.strip() + '\n'
			elif config.crontimers.dayofweek.value == 'Tuesday':
				newcron = minutes + ' ' + hour + ' * * 2 ' + command.strip() + '\n'
			elif config.crontimers.dayofweek.value == 'Wednesday':
				newcron = minutes + ' ' + hour + ' * * 3 ' + command.strip() + '\n'
			elif config.crontimers.dayofweek.value == 'Thursday':
				newcron = minutes + ' ' + hour + ' * * 4 ' + command.strip() + '\n'
			elif config.crontimers.dayofweek.value == 'Friday':
				newcron = minutes + ' ' + hour + ' * * 5 ' + command.strip() + '\n'
			elif config.crontimers.dayofweek.value == 'Saturday':
				newcron = minutes + ' ' + hour + ' * * 6 ' + command.strip() + '\n'
		elif config.crontimers.runwhen.value == 'Monthly':
			newcron = minutes + ' ' + hour + ' ' + str(config.crontimers.dayofmonth.value) + ' * * ' + command.strip() + '\n'
		else:
			command = config.crontimers.user_command.value

		out = open('/etc/cron/crontabs/root', 'a')
		out.write(newcron)
		out.close()
		rc = system('crontab /etc/cron/crontabs/root -c /etc/cron/crontabs')
		config.crontimers.predefined_command.value = 'None'
		config.crontimers.user_command.value = 'None'
		config.crontimers.runwhen.value = 'Daily'
		config.crontimers.dayofweek.value = 'Monday'
		config.crontimers.dayofmonth.value = 1
		config.crontimers.cmdtime.value, mytmpt = ([0, 0], [0, 0])
		self.close()
