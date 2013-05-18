# for localized messages
from . import _

import Components.Task
from Components.About import about
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.MenuList import MenuList
from Components.Sources.List import List
from Components.Pixmap import Pixmap
from Components.config import configfile, config, getConfigListEntry, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigText, ConfigNumber, NoSave, ConfigClock
from Components.ConfigList import ConfigListScreen
from Components.Harddisk import harddiskmanager, getProcMounts
from Screens.Screen import Screen
from Screens.Setup import Setup
from Components.Console import Console
from Screens.Console import Console as RestareConsole
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.Standby import TryQuitMainloop
from Tools.Notifications import AddPopupWithCallback
from enigma import eTimer, getDesktop, getBoxType, getImageVersionString, getBuildVersionString

from os import path, system, mkdir, makedirs, listdir, remove, statvfs, chmod, walk
from shutil import rmtree, move, copy
from time import localtime, time, strftime, mktime

RAMCHEKFAILEDID = 'RamCheckFailedNotification'

hddchoises = []
for p in harddiskmanager.getMountedPartitions():
	d = path.normpath(p.mountpoint)
	if path.exists(p.mountpoint):
		if p.mountpoint != '/':
			hddchoises.append((d + '/', p.mountpoint))
config.imagemanager = ConfigSubsection()
config.imagemanager.folderprefix = ConfigText(default=getBoxType(), fixed_size=False)
config.imagemanager.backuplocation = ConfigSelection(choices = hddchoises)
config.imagemanager.schedule = ConfigYesNo(default = False)
config.imagemanager.scheduletime = ConfigClock(default = 0) # 1:00
config.imagemanager.repeattype = ConfigSelection(default = "daily", choices = [("daily", _("Daily")), ("weekly", _("Weekly")), ("monthly", _("30 Days"))])
config.imagemanager.backupretry = ConfigNumber(default = 30)
config.imagemanager.backupretrycount = NoSave(ConfigNumber(default = 0))
config.imagemanager.nextscheduletime = NoSave(ConfigNumber(default = 0))
config.imagemanager.restoreimage = NoSave(ConfigText(default=getBoxType(), fixed_size=False))


autoImageManagerTimer = None

def ImageManagerautostart(reason, session=None, **kwargs):
	"called with reason=1 to during /sbin/shutdown.sysvinit, with reason=0 at startup?"
	global autoImageManagerTimer
	global _session
	now = int(time())
	if reason == 0:
		print "[ImageManager] AutoStart Enabled"
		if session is not None:
			_session = session
			if autoImageManagerTimer is None:
				autoImageManagerTimer = AutoImageManagerTimer(session)
	else:
		print "[ImageManager] Stop"
		autoImageManagerTimer.stop()

class VIXImageManager(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Image Manager"))

		self['lab1'] = Label()
		self["backupstatus"] = Label()
		self["key_blue"] = Button(_("Restore"))
		self["key_green"] = Button()
		self["key_yellow"] = Button(_("Downloads"))
		self["key_red"] = Button(_("Delete"))

		self.BackupRunning = False
		self.onChangedEntry = [ ]
		self.emlist = []
		self['list'] = MenuList(self.emlist)
		self.populate_List()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.backupRunning)
		self.activityTimer.start(10)

		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next Backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next Backup: ")
		self["backupstatus"].setText(str(backuptext))
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["list"].getCurrent()
		desc = self["backupstatus"].text
		if item:
			name = item
		else:
			name = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def backupRunning(self):
		self.populate_List()
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Image Manager")):
				self.BackupRunning = True
		if self.BackupRunning:
			self["key_green"].setText(_("View Progress"))
		else:
			self["key_green"].setText(_("New Backup"))
		self.activityTimer.startLongTimer(5)

	def refreshUp(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		for fil in images:
			if not fil.endswith('swapfile_backup') and not fil.endswith('bi'):
				self.emlist.append(fil)
		self.emlist.sort()
		self["list"].setList(self.emlist)
		self["list"].show()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveUp)

	def refreshDown(self):
		images = listdir(self.BackupDirectory)
		self.oldlist = images
		del self.emlist[:]
		for fil in images:
			if not fil.endswith('swapfile_backup') and not fil.endswith('bi'):
				self.emlist.append(fil)
		self.emlist.sort()
		self["list"].setList(self.emlist)
		self["list"].show()
		if self['list'].getCurrent():
			self["list"].instance.moveSelection(self["list"].instance.moveDown)

	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end)))

	def showJobView(self, job):
		from Screens.TaskView import JobView
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable = False, backgroundable = False, afterEventChangeable = False, afterEvent="close")

	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def populate_List(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if path.exists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.imagemanager.backuplocation.setChoices(imparts)

		if config.imagemanager.backuplocation.value.startswith('/media/net/'):
			mount1 = config.imagemanager.backuplocation.value.replace('/','')
			mount1 = mount1.replace('medianet','/media/net/')
			mount = config.imagemanager.backuplocation.value, mount1
		else:
			mount = config.imagemanager.backuplocation.value, config.imagemanager.backuplocation.value
		hdd = '/media/hdd/','/media/hdd/'
		if mount not in config.imagemanager.backuplocation.choices.choices:
			if hdd in config.imagemanager.backuplocation.choices.choices:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "HelpActions"],
					{
						"ok": self.keyResstore,
						'cancel': self.close,
						'red': self.keyDelete,
						'green': self.GreenPressed,
						'yellow': self.doDownload,
						'blue': self.keyResstore,
						"menu": self.createSetup,
						"up": self.refreshUp,
						"down": self.refreshDown,
						"displayHelp": self.doDownload,
					}, -1)

				self.BackupDirectory = '/media/hdd/imagebackups/'
				config.imagemanager.backuplocation.value = '/media/hdd/'
				config.imagemanager.backuplocation.save
				self['lab1'].setText(_("The chosen location does not exist, using /media/hdd") + "\n" + _("Select an image to delete:"))
			else:
				self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions"],
					{
						'cancel': self.close,
						"menu": self.createSetup,
					}, -1)

				self['lab1'].setText(_("Device: None available") + "\n" + _("Select an image to delete:"))
		else:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions', "MenuActions", "HelpActions"],
				{
					'cancel': self.close,
					'red': self.keyDelete,
					'green': self.GreenPressed,
					'yellow': self.doDownload,
					'blue': self.keyResstore,
					"menu": self.createSetup,
					"up": self.refreshUp,
					"down": self.refreshDown,
					"displayHelp": self.doDownload,
					"ok": self.keyResstore,
				}, -1)

			self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
			s = statvfs(config.imagemanager.backuplocation.value)
			free = (s.f_bsize * s.f_bavail)/(1024*1024)
			self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + ' ' + _('Free space:') + ' ' + str(free) + _('MB') + "\n" + _("Select an image to delete:"))

		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup'):
				system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + '-swapfile_backup')
			images = listdir(self.BackupDirectory)
			del self.emlist[:]
			for fil in images:
				if not fil.endswith('swapfile_backup') and not fil.endswith('bi'):
					self.emlist.append(fil)
			self.emlist.sort()
			self["list"].setList(self.emlist)
			self["list"].show()
		except:
 			self['lab1'].setText(_("Device: ") + config.imagemanager.backuplocation.value + "\n" + _("there was a problem with this device, please reformat and try again."))

	def createSetup(self):
		self.session.openWithCallback(self.setupDone, Setup, 'viximagemanager', 'SystemPlugins/ViX')

	def doDownload(self):
		self.session.openWithCallback(self.populate_List, ImageManagerDownload, self.BackupDirectory)

	def setupDone(self, test=None):
		self.populate_List()
		self.doneConfiguring()

	def doneConfiguring(self):
		now = int(time())
		if config.imagemanager.schedule.value:
			if autoImageManagerTimer is not None:
				print "[ImageManager] Backup Schedule Enabled at", strftime("%c", localtime(now))
				autoImageManagerTimer.backupupdate()
		else:
			if autoImageManagerTimer is not None:
				global BackupTime
				BackupTime = 0
				print "[ImageManager] Backup Schedule Disabled at", strftime("%c", localtime(now))
				autoImageManagerTimer.backupstop()
		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next Backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next Backup: ")
		self["backupstatus"].setText(str(backuptext))

	def keyDelete(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to delete this backup:\n ") + self.sel
			ybox = self.session.openWithCallback(self.doDelete, MessageBox, message, MessageBox.TYPE_YESNO, default = False)
			ybox.setTitle(_("Remove Confirmation"))
		else:
			self.session.open(MessageBox, _("You have no image to delete."), MessageBox.TYPE_INFO, timeout = 10)

	def doDelete(self, answer):
		if answer is True:
			self.sel = self['list'].getCurrent()
			self["list"].instance.moveSelectionTo(0)
			rmtree(self.BackupDirectory + self.sel)
		self.populate_List()

	def GreenPressed(self):
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Image Manager")):
				backup = job
				self.BackupRunning = True
		if self.BackupRunning:
			self.showJobView(backup)
		else:
			self.keyBackup()

	def keyBackup(self):
		if getBoxType().startswith('vu') or getBoxType().startswith('et') or getBoxType().startswith('tm') or getBoxType().startswith('odin') or getBoxType().startswith('venton') or getBoxType().startswith('gb') or getBoxType().startswith('xp') or getBoxType().startswith('iqon'):
			message = _("Are you ready to create a backup image ?")
			ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Backup Confirmation"))
		else:
			self.session.open(MessageBox, _("Sorry you STB_BOX is not yet compatible."), MessageBox.TYPE_INFO, timeout = 10)

	def doBackup(self,answer):
		if answer is True:
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			self.BackupRunning = True
			self["key_green"].setText(_("View Progress"))
			self["key_green"].show()
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Image Manager")):
					backup = job
			self.showJobView(backup)

	def keyResstore(self):
		self.sel = self['list'].getCurrent()
		self.MAINDESTROOT = self.BackupDirectory + self.sel
		if getBoxType().startswith('vu'):
			self.MAINDEST = self.MAINDESTROOT + '/vuplus/' + getBoxType().replace('vu','') + '/'
		elif getBoxType() == 'tmtwin':
			self.MAINDEST = self.MAINDESTROOT + '/update/tmtwinoe/cfe/'
		elif getBoxType() == 'tm2t':
			self.MAINDEST = self.MAINDESTROOT + '/update/tm2toe/cfe/'
		elif getBoxType() == 'tmsingle':
			self.MAINDEST = self.MAINDESTROOT + '/update/tmsingle/cfe/'
		elif getBoxType() == 'iqonios100hd':
			self.MAINDEST = self.MAINDESTROOT + '/update/ios100/cfe/'
		elif getBoxType() == 'iqoniso200hd':
			self.MAINDEST = self.MAINDESTROOT + '/update/ios200/cfe/'
		elif getBoxType() == 'iqoniso300hd':
			self.MAINDEST = self.MAINDESTROOT + '/update/ios300/cfe/'
		elif getBoxType() == 'gb800solo':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/solo/'
		elif getBoxType() == 'gb800se':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/se/'
		elif getBoxType() == 'gb800ue':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/ue/'
		elif getBoxType() == 'gbquad':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/quad/'
		elif getBoxType().startswith('venton'):
			self.MAINDEST = self.MAINDESTROOT + '/' + getBoxType().replace('-','') + '/'
		else:
			self.MAINDEST = self.MAINDESTROOT + '/' + getBoxType() + '/'
		if not self.BackupRunning:
			if getBoxType().startswith('vu') or getBoxType().startswith('et') or getBoxType().startswith('tm') or getBoxType().startswith('odin') or getBoxType().startswith('venton') or getBoxType().startswith('gb') or getBoxType().startswith('iqon'):
				if path.exists(self.MAINDEST):
					if self.sel:
						message = _("Are you sure you want to restore this image:\n ") + self.sel
						ybox = self.session.openWithCallback(self.doRestore, MessageBox, message, MessageBox.TYPE_YESNO)
						ybox.setTitle(_("Restore Confirmation"))
					else:
						self.session.open(MessageBox, _("You have no image to restore."), MessageBox.TYPE_INFO, timeout = 10)
				else:
					self.session.open(MessageBox, _("Sorry the image " + self.sel + " is not compatible with this STB_BOX."), MessageBox.TYPE_INFO, timeout = 10)
			else:
				self.session.open(MessageBox, _("Sorry Image Restore is not supported on the" + ' ' + getBoxType() + ', ' + _("Please copy the folder") + ' ' + self.BackupDirectory + self.sel +  ' \n' + _("to a USB stick, place in front USB port of reciver and power on")), MessageBox.TYPE_INFO, timeout = 30)
		else:
			self.session.open(MessageBox, _("Backup in progress,\nPlease for it to finish, before trying again"), MessageBox.TYPE_INFO, timeout = 10)


	def doRestore(self,answer):
		if answer:
			config.imagemanager.restoreimage.value = self.sel
			if not path.exists('/tmp/sync'):
				copy('/bin/sync','/tmp')
			if not path.exists('/tmp/nandwrite'):
				copy('/usr/sbin/nandwrite','/tmp')
			if not path.exists('/tmp/flash_erase'):
				copy('/usr/sbin/flash_erase','/tmp')
			if not path.exists('/tmp/reboot'):
				copy('/sbin/reboot','/tmp')
			if not path.exists('/tmp/tee'):
				copy('/usr/bin/tee','/tmp')

		if getBoxType().startswith('gb'):
			kernelMTD = "mtd2"
			kernelFILE = "kernel.bin"
			rootMTD = "mtd4"
			rootFILE = "rootfs.bin"
		elif getBoxType().startswith('et') or getBoxType().startswith('venton') or getBoxType().startswith('xp'):
			kernelMTD = "mtd1"
			kernelFILE = "kernel.bin"
			rootMTD = "mtd2"
			rootFILE = "rootfs.bin"
		elif getBoxType().startswith('odin'):
			kernelMTD = "mtd2"
			kernelFILE = "kernel.bin"
			rootMTD = "mtd3"
			rootFILE = "rootfs.bin"
		elif getBoxType().startswith('tm') or getBoxType().startswith('iqon'):
			kernelMTD = "mtd6"
			kernelFILE = "oe_kernel.bin"
			rootMTD = "mtd4"
			rootFILE = "oe_rootfs.bin"
		elif getBoxType() == 'vusolo' or getBoxType() == 'vuduo' or getBoxType() == 'vuuno' or getBoxType() == 'vuultimo':
			kernelMTD = "mtd1"
			kernelFILE = "kernel_cfe_auto.bin"
			rootMTD = "mtd0"
			rootFILE = "root_cfe_auto.jffs2"
		elif getBoxType() == 'vusolo2' or getBoxType() == 'vuduo2':
			kernelMTD = "mtd2"
			kernelFILE = "kernel_cfe_auto.bin"
			rootMTD = "mtd0"
			rootFILE = "root_cfe_auto.bin"

		output = open('/tmp/image_restore.sh','w')
		output.write('#!/bin/sh\n\n/tmp/sync > /media/hdd/restore.log 2>&1 && mount -no remount,ro / >> /media/hdd/restore.log 2>&1 && /tmp/flash_erase /dev/' + kernelMTD + ' 0 0 >> /media/hdd/restore.log 2>&1 && /tmp/nandwrite -p /dev/' + kernelMTD + ' ' + self.MAINDEST + kernelFILE + ' >> /media/hdd/restore.log 2>&1 && /tmp/flash_erase /dev/' + rootMTD + ' 0 0 >> /media/hdd/restore.log 2>&1 && /tmp/nandwrite -p /dev/' + rootMTD + ' ' + self.MAINDEST + rootFILE + ' >> /media/hdd/restore.log 2>&1 && /tmp/reboot -fn')
		output.close()
		chmod('/tmp/image_restore.sh', 0755)
		self.session.open(TryQuitMainloop,retvalue=43)
		self.close()

class AutoImageManagerTimer:
	def __init__(self, session):
		self.session = session
		self.backuptimer = eTimer()
		self.backuptimer.callback.append(self.BackuponTimer)
		self.backupactivityTimer = eTimer()
		self.backupactivityTimer.timeout.get().append(self.backupupdatedelay)
		now = int(time())
		global BackupTime
		if config.imagemanager.schedule.value:
			print "[ImageManager] Backup Schedule Enabled at ", strftime("%c", localtime(now))
			if now > 1262304000:
				self.backupupdate()
			else:
				print "[ImageManager] Backup Time not yet set."
				BackupTime = 0
				self.backupactivityTimer.start(36000)
		else:
			BackupTime = 0
			print "[ImageManager] Backup Schedule Disabled at", strftime("(now=%c)", localtime(now))
			self.backupactivityTimer.stop()

	def backupupdatedelay(self):
		self.backupactivityTimer.stop()
		self.backupupdate()

	def getBackupTime(self):
		backupclock = config.imagemanager.scheduletime.value
		nowt = time()
		now = localtime(nowt)
		return int(mktime((now.tm_year, now.tm_mon, now.tm_mday, backupclock[0], backupclock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

	def backupupdate(self, atLeast = 0):
		self.backuptimer.stop()
		global BackupTime
		BackupTime = self.getBackupTime()
		now = int(time())
		#print '[ImageManager] BACKUP TIME',BackupTime
		#print '[ImageManager] NOW TIME',now
		#print '[ImageManager] ATLEAST',atLeast
		#print '[ImageManager] NOW + ATLEAST', (now + atLeast)
		#print '[ImageManager] BACKUP TIME - NOW', (BackupTime - now)
		if BackupTime > 0:
			if BackupTime < now + atLeast:
				if config.imagemanager.repeattype.value == "daily":
					BackupTime += 24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 24*3600
					#BackupTime += 8*60
					#print '[ImageManager] BACKUP TIME 2:',BackupTime
					#print '[ImageManager] NOW 2:',now
					#while (int(BackupTime)-30) < now:
						#print '[ImageManager] YES BT is Less Now'
						#BackupTime += 8*60
						#print '[ImageManager] BACKUP TIME 2:',BackupTime
				elif config.imagemanager.repeattype.value == "weekly":
					BackupTime += 7*24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 7*24*3600
				elif config.imagemanager.repeattype.value == "monthly":
					BackupTime += 30*24*3600
					while (int(BackupTime)-30) < now:
						BackupTime += 30*24*3600
			next = BackupTime - now
			self.backuptimer.startLongTimer(next)
		else:
		    	BackupTime = -1
		print "[ImageManager] Backup Time set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
		return BackupTime

	def backupstop(self):
	    self.backuptimer.stop()

	def BackuponTimer(self):
		self.backuptimer.stop()
		now = int(time())
		wake = self.getBackupTime()
		# If we're close enough, we're okay...
		atLeast = 0
		if wake - now < 60:
			print "[ImageManager] Backup onTimer occured at", strftime("%c", localtime(now))
			from Screens.Standby import inStandby
			if not inStandby:
				message = _("Your STB_BOX is about to run a full image backup, this can take about 6 minutes to complete,\ndo you want to allow this?")
				ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO, timeout = 30)
				ybox.setTitle('Scheduled Backup.')
			else:
				print "[ImageManager] in Standby, so just running backup", strftime("%c", localtime(now))
				self.doBackup(True)
		else:
			print '[ImageManager] Where are not close enough', strftime("%c", localtime(now))
			self.backupupdate(60)

	def doBackup(self, answer):
		now = int(time())
		if answer is False:
			if config.imagemanager.backupretrycount.value < 2:
				print '[ImageManager] Number of retries',config.imagemanager.backupretrycount.value
				print "[ImageManager] Backup delayed."
				repeat = config.imagemanager.backupretrycount.value
				repeat += 1
				config.imagemanager.backupretrycount.value = repeat
				BackupTime = now + (int(config.imagemanager.backupretry.value) * 60)
				print "[ImageManager] Backup Time now set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now))
				self.backuptimer.startLongTimer(int(config.imagemanager.backupretry.value) * 60)
			else:
				atLeast = 60
				print "[ImageManager] Enough Retries, delaying till next schedule.", strftime("%c", localtime(now))
				self.session.open(MessageBox, _("Enough Retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout = 10)
				config.imagemanager.backupretrycount.value = 0
				self.backupupdate(atLeast)
		else:
			print "[ImageManager] Running Backup", strftime("%c", localtime(now))
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			#self.close()

class ImageBackup(Screen):
	def __init__(self, session, updatebackup=False):
		Screen.__init__(self, session)
		self.updatebackup = updatebackup
		self.swapdevice = ""
		self.RamChecked = False
		self.SwapCreated = False
		self.Stage1Completed = False
		self.Stage2Completed = False
		self.Stage3Completed = False

	def createBackupJob(self):
		job = Components.Task.Job(_("Image Manager"))

		task = Components.Task.PythonTask(job, _("Setting Up..."))
		task.work = self.JobStart
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Checking Free RAM.."), timeoutCount=10)
		task.check = lambda: self.RamChecked
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating Swap.."), timeoutCount=120)
		task.check = lambda: self.SwapCreated
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Creating Backup Files..."))
		task.work = self.doBackup1
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating Backup Files..."), timeoutCount=900)
		task.check = lambda: self.Stage1Completed
		task.weighting = 35

		task = Components.Task.PythonTask(job, _("Creating Backup Files..."))
		task.work = self.doBackup2
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating Backup Files..."), timeoutCount=900)
		task.check = lambda: self.Stage2Completed
		task.weighting = 15

		task = Components.Task.PythonTask(job, _("Removing temp mounts..."))
		task.work = self.doBackup3
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Removing temp mounts..."), timeoutCount=900)
		task.check = lambda: self.Stage3Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Moving to Backup Location..."))
		task.work = self.doBackup4
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Moving to Backup Location..."), timeoutCount=900)
		task.check = lambda: self.Stage4Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Backup Complete..."))
		task.work = self.BackupComplete
		task.weighting = 5

		return job

	def JobStart(self):
		imparts = []
		for p in harddiskmanager.getMountedPartitions():
			if path.exists(p.mountpoint):
				d = path.normpath(p.mountpoint)
				m = d + '/', p.mountpoint
				if p.mountpoint != '/':
					imparts.append((d + '/', p.mountpoint))

		config.imagemanager.backuplocation.setChoices(imparts)

		if config.imagemanager.backuplocation.value.startswith('/media/net/'):
			mount1 = config.imagemanager.backuplocation.value.replace('/','')
			mount1 = mount1.replace('medianet','/media/net/')
			mount = config.imagemanager.backuplocation.value, mount1
		else:
			mount = config.imagemanager.backuplocation.value, config.imagemanager.backuplocation.value
		hdd = '/media/hdd/','/media/hdd/'
		if mount not in config.imagemanager.backuplocation.choices.choices:
			if hdd in config.imagemanager.backuplocation.choices.choices:
				config.imagemanager.backuplocation.value = '/media/hdd/'
				config.imagemanager.backuplocation.save
				self.BackupDevice = config.imagemanager.backuplocation.value
				print "[ImageManager] Device: " + self.BackupDevice
				self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
				print "[ImageManager] Directory: " + self.BackupDirectory
				print "The chosen location does not exist, using /media/hdd"
			else:
				print "Device: None available"
		else:
			self.BackupDevice = config.imagemanager.backuplocation.value
			print "[ImageManager] Device: " + self.BackupDevice
			self.BackupDirectory = config.imagemanager.backuplocation.value + 'imagebackups/'
			print "[ImageManager] Directory: " + self.BackupDirectory

		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup"):
				system('swapoff ' + self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup")
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + "-swapfile_backup")
		except Exception,e:
			print str(e)
			print "Device: " + config.imagemanager.backuplocation.value + ", i don't seem to have write access to this device."

		s = statvfs(self.BackupDevice)
		free = (s.f_bsize * s.f_bavail)/(1024*1024)
		if int(free) < 200:
			AddPopupWithCallback(self.BackupComplete,
				_("The backup location does not have enough freespace." + "\n" + self.BackupDevice + "only has " + str(free) + "MB free."),
				MessageBox.TYPE_INFO,
				10,
				'RamCheckFailedNotification'
			)
		else:
			self.MemCheck()

	def MemCheck(self):
		f = open('/proc/meminfo', 'r')
		for line in f.readlines():
			if line.find('MemFree') != -1:
				parts = line.strip().split()
				memfree = int(parts[1])
			elif line.find('SwapFree') != -1:
				parts = line.strip().split()
				swapfree = int(parts[1])
		f.close()
		TotalFree = memfree + swapfree
		print '[ImageManager] Stage1: Free Mem',TotalFree
		if int(TotalFree) < 3000:
			self.MemCheckConsole = Console()
			supported_filesystems = frozenset(('ext4', 'ext3', 'ext2'))
			candidates = []
			mounts = getProcMounts()
			for partition in harddiskmanager.getMountedPartitions(False, mounts):
				if partition.filesystem(mounts) in supported_filesystems:
					candidates.append((partition.description, partition.mountpoint))
			for swapdevice in candidates:
				self.swapdevice = swapdevice[1]
			if self.swapdevice:
				print '[ImageManager] Stage1: Creating Swapfile.'
				self.RamChecked = True
				self.MemCheck2()
			else:
				print '[ImageManager] Sorry, not enough free ram found, and no physical devices that supports SWAP attached'
				AddPopupWithCallback(self.BackupComplete,
					_("Sorry, not enough free ram found, and no physical devices that supports SWAP attached. Can't create Swapfile on network or fat32 filesystems, unable to make backup"),
					MessageBox.TYPE_INFO,
					10,
					'RamCheckFailedNotification'
				)
		else:
			print '[ImageManager] Stage1: Found Enough Ram'
			self.RamChecked = True
			self.SwapCreated = True

	def MemCheck2(self):
		self.MemCheckConsole.ePopen("dd if=/dev/zero of=" + self.swapdevice + config.imagemanager.folderprefix.value + "-swapfile_backup bs=1024 count=61440", self.MemCheck3)

	def MemCheck3(self, result, retval, extra_args = None):
		if retval == 0:
			self.MemCheckConsole = Console()
			self.MemCheckConsole.ePopen("mkswap " + self.swapdevice + config.imagemanager.folderprefix.value + "-swapfile_backup", self.MemCheck4)

	def MemCheck4(self, result, retval, extra_args = None):
		if retval == 0:
			self.MemCheckConsole = Console()
			self.MemCheckConsole.ePopen("swapon " + self.swapdevice + config.imagemanager.folderprefix.value + "-swapfile_backup", self.MemCheck5)

	def MemCheck5(self, result, retval, extra_args = None):
		self.SwapCreated = True

	def doBackup1(self):
		f = open('/proc/mounts')
		filesystem = f.read()
		f.close()
		if filesystem.find('ubifs') != -1:
			self.ROOTFSTYPE = 'ubifs'
		else:
			self.ROOTFSTYPE= 'jffs2'
		self.BackupConsole = Console()
		print '[ImageManager] Stage1: Creating tmp folders.',self.BackupDirectory
		self.BackupDate = getImageVersionString() + '.' + getBuildVersionString() + '-' + strftime('%Y%m%d_%H%M%S', localtime())
		self.WORKDIR=self.BackupDirectory + config.imagemanager.folderprefix.value + '-temp'
		self.TMPDIR=self.BackupDirectory + config.imagemanager.folderprefix.value + '-mount'
		if self.updatebackup:
			self.MAINDESTROOT=self.BackupDirectory + config.imagemanager.folderprefix.value + '-SoftwareUpdate-' + self.BackupDate
		else:
			self.MAINDESTROOT=self.BackupDirectory + config.imagemanager.folderprefix.value + '-' + self.BackupDate
		MKFS='mkfs.' + self.ROOTFSTYPE
		if getBoxType() =='gb800solo':
			JFFS2OPTIONS=" --disable-compressor=lzo -e131072 -l -p125829120"
		else:
			JFFS2OPTIONS=" --disable-compressor=lzo --eraseblock=0x20000 -n -l"
		UBINIZE='ubinize'
		UBINIZE_ARGS="-m 2048 -p 128KiB"
		print '[ImageManager] Stage1: Creating backup Folders.'
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		mkdir(self.WORKDIR, 0644)
		if path.exists(self.TMPDIR + '/root'):
			system('umount ' + self.TMPDIR + '/root')
		if path.exists(self.TMPDIR):
			rmtree(self.TMPDIR)
		makedirs(self.TMPDIR + '/root', 0644)
		makedirs(self.MAINDESTROOT, 0644)
		self.commands = []
		print '[ImageManager] Stage1: Making Root Image.'
		if getBoxType().startswith('vu'):
			self.MAINDEST = self.MAINDESTROOT + '/vuplus/' + getBoxType().replace('vu','')
		elif getBoxType() == 'tmtwin':
			self.MAINDEST = self.MAINDESTROOT + '/update/tmtwinoe/cfe'
		elif getBoxType() == 'tm2t':
			self.MAINDEST = self.MAINDESTROOT + '/update/tm2toe/cfe'
		elif getBoxType() == 'tmsingle':
			self.MAINDEST = self.MAINDESTROOT + '/update/tmsingle/cfe'
		elif getBoxType() == 'iqonios100hd':
			self.MAINDEST = self.MAINDESTROOT + '/update/ios100/cfe'
		elif getBoxType() == 'iqoniso200hd':
			self.MAINDEST = self.MAINDESTROOT + '/update/ios200/cfe'
		elif getBoxType() == 'iqoniso300hd':
			self.MAINDEST = self.MAINDESTROOT + '/update/ios300/cfe'
		elif getBoxType() == 'gb800solo':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/solo'
		elif getBoxType() == 'gb800se':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/se'
		elif getBoxType() == 'gb800ue':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/ue'
		elif getBoxType() == 'gbquad':
			self.MAINDEST = self.MAINDESTROOT + '/gigablue/quad'
		elif getBoxType().startswith('venton'):
			self.MAINDEST = self.MAINDESTROOT + '/' + getBoxType().replace('-','')
		else:
			self.MAINDEST = self.MAINDESTROOT + '/' + getBoxType()
		makedirs(self.MAINDEST, 0644)
		if self.ROOTFSTYPE == 'jffs2':
			print '[ImageManager] Stage1: JFFS2 Detected.'
			self.commands.append('mount --bind / ' + self.TMPDIR + '/root')
			self.commands.append(MKFS + ' --root=' + self.TMPDIR + '/root --faketime --output=' + self.WORKDIR + '/root.jffs2' + JFFS2OPTIONS)
		elif self.ROOTFSTYPE == 'ubifs':
			print '[ImageManager] Stage1: UBIFS Detected.'
			if getBoxType().startswith('vu'):
				MKUBIFS_ARGS="-m 2048 -e 126976 -c 4096 -F"
			elif getBoxType().startswith('tm') or getBoxType().startswith('iqon'):
				MKUBIFS_ARGS="-m 2048 -e 126976 -c 4096 -F"
			elif getBoxType().startswith('gb'):
				MKUBIFS_ARGS="-m 2048 -e 126976 -c 4096"
			elif getBoxType().startswith('et') or getBoxType().startswith('odin') or getBoxType().startswith('xp'):
				MKUBIFS_ARGS="-m 2048 -e 126976 -c 4096"
			elif getBoxType().startswith('venton'):
				MKUBIFS_ARGS="-m 2048 -e 126976 -c 4096"
			output = open(self.WORKDIR + '/ubinize.cfg','w')
			output.write('[ubifs]\n')
			output.write('mode=ubi\n')
			output.write('image=' + self.WORKDIR + '/root.ubi\n')
			output.write('vol_id=0\n')
			output.write('vol_type=dynamic\n')
			output.write('vol_name=rootfs\n')
			output.write('vol_flags=autoresize\n')
			output.close()
			self.commands.append('mount --bind / ' + self.TMPDIR + '/root')
			self.commands.append('touch ' + self.WORKDIR + '/root.ubi')
			self.commands.append(MKFS + ' -r ' + self.TMPDIR + '/root -o ' + self.WORKDIR + '/root.ubi ' + MKUBIFS_ARGS)
			self.commands.append('ubinize -o ' + self.WORKDIR + '/root.ubifs ' + UBINIZE_ARGS + ' ' + self.WORKDIR + '/ubinize.cfg')
		self.BackupConsole.eBatch(self.commands, self.Stage1Complete, debug=True)

	def Stage1Complete(self, extra_args = None):
		if len(self.BackupConsole.appContainers) == 0:
			self.Stage1Completed = True
			print '[ImageManager] Stage1: Complete.'

	def doBackup2(self):
		print '[ImageManager] Stage2: Making Kernel Image.'
		if getBoxType().startswith('tm') or getBoxType().startswith('iqon'):
			self.command = 'cat /dev/mtd6 > ' + self.WORKDIR + '/vmlinux.gz'
		elif getBoxType().startswith('et') or getBoxType().startswith('venton') or getBoxType().startswith('xp') or getBoxType() == 'vusolo' or getBoxType() == 'vuduo' or getBoxType() == 'vuuno' or getBoxType() == 'vuultimo':
			self.command = 'cat /dev/mtd1 > ' + self.WORKDIR + '/vmlinux.gz'
		elif getBoxType().startswith('odin') or getBoxType().startswith('gb') or getBoxType() == 'vusolo2' or getBoxType() == 'vuduo2':
			self.command = 'cat /dev/mtd2 > ' + self.WORKDIR + '/vmlinux.gz'
		self.BackupConsole.ePopen(self.command, self.Stage2Complete)

	def Stage2Complete(self, result, retval, extra_args = None):
		if retval == 0:
			self.Stage2Completed = True
			print '[ImageManager] Stage2: Complete.'

	def doBackup3(self):
		print '[ImageManager] Stage3: Unmounting and removing tmp system'
		if path.exists(self.TMPDIR + '/root'):
			self.command = 'umount ' + self.TMPDIR + '/root && rm -rf ' + self.TMPDIR
			self.BackupConsole.ePopen(self.command, self.Stage3Complete)

	def Stage3Complete(self, result, retval, extra_args = None):
		if retval == 0:
			self.Stage3Completed = True
			print '[ImageManager] Stage3: Complete.'

	def doBackup4(self):
		imagecreated = False
		print '[ImageManager] Stage4: Moving from work to backup folders'
		if getBoxType() == 'vusolo' or getBoxType() == 'vuduo' or getBoxType() == 'vuuno' or getBoxType() == 'vuultimo':
			move(self.WORKDIR + '/root.' + self.ROOTFSTYPE, self.MAINDEST + '/root_cfe_auto.jffs2')
			move(self.WORKDIR + '/vmlinux.gz', self.MAINDEST + '/kernel_cfe_auto.bin')
			fileout = open(self.MAINDEST + '/reboot.update', 'w')
			line = "This file forces a reboot after the update."
			fileout.write(line)
			fileout.close()
			fileout = open(self.MAINDEST + '/imageversion', 'w')
			line = "openvix-" + self.BackupDate
			fileout.write(line)
			fileout.close()
			imagecreated = True
		elif getBoxType() == 'vusolo2' or getBoxType() == 'vuduo2':
			move(self.WORKDIR + '/root.' + self.ROOTFSTYPE, self.MAINDEST + '/root_cfe_auto.bin')
			move(self.WORKDIR + '/vmlinux.gz', self.MAINDEST + '/kernel_cfe_auto.bin')
			fileout = open(self.MAINDEST + '/reboot.update', 'w')
			line = "This file forces a reboot after the update."
			fileout.write(line)
			fileout.close()
			fileout = open(self.MAINDEST + '/imageversion', 'w')
			line = "openvix-" + self.BackupDate
			fileout.write(line)
			fileout.close()
			imagecreated = True
		elif getBoxType().startswith('et') or getBoxType().startswith('odin') or getBoxType().startswith('venton') or getBoxType().startswith('gb') or getBoxType().startswith('xp'):
			move(self.WORKDIR + '/root.' + self.ROOTFSTYPE, self.MAINDEST + '/rootfs.bin')
			move(self.WORKDIR + '/vmlinux.gz', self.MAINDEST + '/kernel.bin')
			if getBoxType().startswith('et') or getBoxType().startswith('odin'):
				fileout = open(self.MAINDEST + '/noforce', 'w')
				line = "rename this file to 'force' to force an update without confirmation"
				fileout.write(line)
				fileout.close()
				fileout = open(self.MAINDEST + '/imageversion', 'w')
				line = "openvix-" + self.BackupDate
				fileout.write(line)
				fileout.close()
			if getBoxType() == 'gb800solo' or getBoxType() == 'gb800se':
				copy('/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/burn.bat', self.MAINDESTROOT + '/burn.bat')
			imagecreated = True
		elif getBoxType().startswith('tm') or getBoxType().startswith('iqon'):
			move(self.WORKDIR + '/root.' + self.ROOTFSTYPE, self.MAINDEST + '/oe_rootfs.bin')
			move(self.WORKDIR + '/vmlinux.gz', self.MAINDEST + '/oe_kernel.bin')
			imagecreated = True
		print '[ImageManager] Stage4: Removing Swap.'
		if path.exists(self.swapdevice + config.imagemanager.folderprefix.value + "-swapfile_backup"):
			system('swapoff ' + self.swapdevice + config.imagemanager.folderprefix.value + "-swapfile_backup")
			remove(self.swapdevice + config.imagemanager.folderprefix.value + "-swapfile_backup")
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		if imagecreated:
			for root, dirs, files in walk(self.MAINDEST):
				for momo in dirs:
					chmod(path.join(root, momo), 0644)
				for momo in files:
					chmod(path.join(root, momo), 0644)
			print '[ImageManager] Stage4: Image created in ' + self.MAINDESTROOT
			self.Stage4Complete()
		else:
			print "[ImageManager] Stage4: Image creation failed - e. g. wrong backup destination or no space left on backup device"
			self.Stage3Complete()

	def Stage4Complete(self):
		self.Stage4Completed = True
		print '[ImageManager] Stage4: Complete.'

	def BackupComplete(self, anwser=None):
		if config.imagemanager.schedule.value:
			atLeast = 60
			autoImageManagerTimer.backupupdate(atLeast)
		else:
			autoImageManagerTimer.backupstop()

class ImageManagerDownload(Screen):
	def __init__(self, session, BackupDirectory):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Image Manager"))
		self.BackupDirectory = BackupDirectory
		self['lab1'] = Label(_("Select an image to Download:"))
		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button(_("Download"))
		self["key_yellow"] = Button()
		self["key_blue"] = Button()

		self.onChangedEntry = [ ]
		self.emlist = []
		self['list'] = MenuList(self.emlist)
		self.populate_List()

		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def selectionChanged(self):
		for x in self.onChangedEntry:
			x()

	def populate_List(self):
		try:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions'],
				{
					'cancel': self.close,
					'red': self.close,
					'green': self.keyDownload,
				}, -1)

			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0755)
			from ftplib import FTP
			import urllib, zipfile, base64
			wos_user = 'vixlogs@world-of-satellite.com'
			wos_pwd = base64.b64decode('NDJJWnojMEpldUxX')
			ftp = FTP('world-of-satellite.com')
			ftp.login(wos_user,wos_pwd)
			if getBoxType() == 'vuuno':
				ftp.cwd('openvix-builds/Vu+Uno')
			elif getBoxType() == 'vuultimo':
				ftp.cwd('openvix-builds/Vu+Ultimo')
			elif getBoxType() == 'vusolo':
				ftp.cwd('openvix-builds/Vu+Solo')
			elif getBoxType() == 'vuduo':
				ftp.cwd('openvix-builds/Vu+Duo')
			elif getBoxType() == 'et4x00':
				ftp.cwd('openvix-builds/ET-4x00')
			elif getBoxType() == 'et5x00':
				ftp.cwd('openvix-builds/ET-5x00')
			elif getBoxType() == 'et6x00':
				ftp.cwd('openvix-builds/ET-6x00')
			elif getBoxType() == 'et9x00':
				ftp.cwd('openvix-builds/ET-9x00')
			elif getBoxType() == 'tmtwin':
				ftp.cwd('openvix-builds/TM-Twin-OE')
			elif getBoxType() == 'tm2t':
				ftp.cwd('openvix-builds/TM-2T-OE')
			elif getBoxType() == 'tmsingle':
				ftp.cwd('openvix-builds/TM-Single')
			elif getBoxType() == 'iqonios100hd':
				ftp.cwd('openvix-builds/iqon-IOS-100HD')
			elif getBoxType() == 'iqonios200hd':
				ftp.cwd('openvix-builds/iqon-IOS-200HD')
			elif getBoxType() == 'iqonios300hd':
				ftp.cwd('openvix-builds/iqon-IOS-300HD')
			elif getBoxType() == 'odinm9':
				ftp.cwd('openvix-builds/Odin-M9')
			elif getBoxType() == 'xp1000':
				ftp.cwd('openvix-builds/XP1000')
			elif getBoxType() == 'qb800solo':
				ftp.cwd('openvix-builds/GiGaBlue-HD800Solo')
			elif getBoxType() == 'gb800se':
				ftp.cwd('openvix-builds/GiGaBlue-HD800SE')
			elif getBoxType() == 'gb800ue':
				ftp.cwd('openvix-builds/GiGaBlue-HD800UE')
			elif getBoxType() == 'gbqad':
				ftp.cwd('openvix-builds/GiGaBlue-HD-QUAD')
			elif getBoxType() == 'ventonhdx':
				ftp.cwd('openvix-builds/Venton-Unibox-HDx')
			elif getBoxType() == 'ventonhde':
				ftp.cwd('openvix-builds/Venton-Unibox-HDe')

			del self.emlist[:]
			for fil in ftp.nlst():
				if not fil.endswith('.') and fil.find(getBoxType()) != -1:
					self.emlist.append(fil)
			self.emlist.sort()
		except:
			self['myactions'] = ActionMap(['ColorActions', 'OkCancelActions', 'DirectionActions'],
				{
					'cancel': self.close,
					'red': self.close,
				}, -1)
			self.emlist.append(" ")
		self["list"].setList(self.emlist)
		self["list"].show()

	def keyDownload(self):
		self.sel = self['list'].getCurrent()
		if self.sel:
			message = _("Are you sure you want to download this image:\n ") + self.sel
			ybox = self.session.openWithCallback(self.doDownload, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_("Download Confirmation"))
		else:
			self.session.open(MessageBox, _("You have no image to download."), MessageBox.TYPE_INFO, timeout = 10)

	def doDownload(self,answer):
		if answer is True:
			self.selectedimage = self['list'].getCurrent()
			file = self.BackupDirectory + self.selectedimage
			dir =  self.BackupDirectory + self.selectedimage.replace('.zip','')
			if not path.exists(dir):
				mkdir(dir, 0777)
			from Screens.Console import Console as RestareConsole
			mycmd1 = _("echo 'Downloading Image.'")
			if getBoxType() == 'vuuno':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/Vu+Uno/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'vuultimo':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/Vu+Ultimo/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'vusolo':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/Vu+Solo/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'vuduo':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/Vu+Duo/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'et4x00':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/ET-4x00/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'et5x00':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/ET-5x00/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'et6x00':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/ET-6x00/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'et9x00':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/ET-9x00/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'tmtwin':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/TM-Twin/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'tm2t':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/TM-2T-OE/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'tmsingle':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/TM-Single/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'iqonios100hd':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/iqon-IOS-100HD/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'iqonios200hd':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/iqon-IOS-200HD/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'iqonios300hd':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/iqon-IOS-300HD/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'odinm9':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/Odin-M9/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'qb800solo':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/GiGaBlue-HD800Solo/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'gb800se':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/GiGaBlue-HD800SE/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'gb800ue':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/GiGaBlue-HD800UE/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'gbquad':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/GiGaBlue-HD-QUAD/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'xp1000':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/XP1000/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'ventonhdx':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/Venton-Unibox-HDx/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			elif getBoxType() == 'ventonhde':
				mycmd2 = "wget http://enigma2.world-of-satellite.com//openvix/openvix-builds/Venton-Unibox-HDe/" + self.selectedimage + " -O " + self.BackupDirectory + "image.zip"
			mycmd3 = "mv " + self.BackupDirectory + "image.zip " + file
			mycmd4 = _("echo 'Expanding Image.'")
			mycmd5 = 'unzip -o ' + file + ' -d ' + dir
			mycmd6 = 'rm ' + file
			self.session.open(RestareConsole, title=_('Downloading Image...'), cmdlist=[mycmd1, mycmd2, mycmd3, mycmd4, mycmd5, mycmd6],closeOnSuccess = True)

	def myclose(self, result, retval, extra_args):
 		remove(self.BackupDirectory + self.selectedimage)
		self.close()
