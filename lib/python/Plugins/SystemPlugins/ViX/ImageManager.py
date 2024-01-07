from urllib.parse import urlparse
from urllib.request import urlopen
import json
import tempfile

from enigma import eTimer, fbClass
from os import path, stat, system, mkdir, makedirs, listdir, remove, rename, rmdir, sep as ossep, statvfs, chmod, walk
from shutil import copy, copyfile, move, rmtree
from time import localtime, time, strftime, mktime

from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.ChoiceList import ChoiceList, ChoiceEntryComponent
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigText, ConfigNumber, NoSave, ConfigClock, configfile
from Components.Console import Console
from Components.Harddisk import harddiskmanager, getProcMounts
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
import Components.Task
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.Standby import TryQuitMainloop
from Screens.TaskView import JobView
from Screens.TextBox import TextBox
from Tools.Directories import fileExists, pathExists, fileHas
import Tools.CopyFiles
from Tools.HardwareInfo import HardwareInfo
from Tools.Multiboot import GetImagelist
from Tools.Notifications import AddPopupWithCallback


def getMountChoices():
	choices = []
	for p in harddiskmanager.getMountedPartitions():
		if path.exists(p.mountpoint):
			d = path.normpath(p.mountpoint)
			entry = (p.mountpoint, d)
			if p.mountpoint != "/" and entry not in choices:
				choices.append(entry)
	choices.sort()
	return choices


def getMountDefault(choices):
	choices = {x[1]: x[0] for x in choices}
	default = choices.get("/media/hdd") or choices.get("/media/usb")
	return default


def __onPartitionChange(*args, **kwargs):
	global choices
	choices = getMountChoices()
	config.imagemanager.backuplocation.setChoices(choices=choices, default=getMountDefault(choices))


defaultprefix = SystemInfo["distro"]
config.imagemanager = ConfigSubsection()
config.imagemanager.autosettingsbackup = ConfigYesNo(default=True)
choices = getMountChoices()
config.imagemanager.backuplocation = ConfigSelection(choices=choices, default=getMountDefault(choices))
config.imagemanager.extensive_location_search = ConfigYesNo(default=False)
harddiskmanager.on_partition_list_change.append(__onPartitionChange)  # to update backuplocation choices on mountpoint change
config.imagemanager.backupretry = ConfigNumber(default=30)
config.imagemanager.backupretrycount = NoSave(ConfigNumber(default=0))
config.imagemanager.folderprefix = ConfigText(default=defaultprefix, fixed_size=False)
config.imagemanager.nextscheduletime = NoSave(ConfigNumber(default=0))
config.imagemanager.repeattype = ConfigSelection(default="daily", choices=[("daily", _("Daily")), ("weekly", _("Weekly")), ("monthly", _("30 Days"))])
config.imagemanager.schedule = ConfigYesNo(default=False)
config.imagemanager.scheduletime = ConfigClock(default=0)  # 1:00
config.imagemanager.query = ConfigYesNo(default=True)
config.imagemanager.lastbackup = ConfigNumber(default=0)
config.imagemanager.number_to_keep = ConfigNumber(default=0)
# Add a method for users to download images directly from their own build servers.
# Script must be able to handle urls in the form http://domain/scriptname/boxname.
# Format of the JSON output from the script must be the same as the official urls above.
# The option will only show once a url has been added.
config.imagemanager.imagefeed_MyBuild = ConfigText(default="", fixed_size=False)
config.imagemanager.login_as_ViX_developer = ConfigYesNo(default=False)
config.imagemanager.developer_username = ConfigText(default="username", fixed_size=False)
config.imagemanager.developer_password = ConfigText(default="password", fixed_size=False)

DISTRO = 0
URL = 1
ACTION = 2

FEED_URLS = [
	("OpenViX", "https://www.openvix.co.uk/json/%s", "getMachineMake"),
	("OpenATV", "https://images.mynonpublic.com/openatv/json/%s", "getMachineMake"),
	("OpenBH", "https://images.openbh.net/json/%s", "getMachineMake"),
	("OpenPLi", "http://downloads.openpli.org/json/%s", "HardwareInfo"),
]


autoImageManagerTimer = None

if path.exists(config.imagemanager.backuplocation.value + "imagebackups/imagerestore"):
	try:
		rmtree(config.imagemanager.backuplocation.value + "imagebackups/imagerestore")
	except Exception:
		pass
TMPDIR = config.imagemanager.backuplocation.value + "imagebackups/" + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-mount"
if path.exists(TMPDIR + "/root") and path.ismount(TMPDIR + "/root"):
	try:
		system("umount " + TMPDIR + "/root")
	except Exception:
		pass


def ImageManagerautostart(reason, session=None, **kwargs):
	"""called with reason=1 to during /sbin/shutdown.sysvinit, with reason=0 at startup?"""
	global autoImageManagerTimer
	global _session
	if reason == 0:
		print("[ImageManager] AutoStart Enabled")
		if session is not None:
			_session = session
			if autoImageManagerTimer is None:
				autoImageManagerTimer = AutoImageManagerTimer(session)
	else:
		if autoImageManagerTimer is not None:
			print("[ImageManager] Stop")
			autoImageManagerTimer.stop()


class tmp:
	dir = None


BackupTime = 0


class VIXImageManager(Screen):
	skin = ["""<screen name="VIXImageManager" position="center,center" size="%d,%d">
		<ePixmap pixmap="skin_default/buttons/red.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="key_red" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<ePixmap pixmap="skin_default/buttons/key_menu.png" position="%d,%d" size="%d,%d" alphatest="blend" transparent="1" zPosition="3" scale="1" />
		<widget name="lab1" position="%d,%d" size="%d,%d" font="Regular; %d" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="%d,%d" size="%d,%d" font="Regular;%d" scrollbarMode="showOnDemand"/>
		<widget name="backupstatus" position="%d,%d" size="%d,%d" font="Regular;%d" zPosition="5"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(%d)
		</applet>
	</screen>""",
		560, 400,  # screen
		0, 0, 140, 40,  # colors
		140, 0, 140, 40,
		280, 0, 140, 40,
		420, 0, 140, 40,
		0, 0, 140, 40, 20,
		140, 0, 140, 40, 20,
		280, 0, 140, 40, 20,
		420, 0, 140, 40, 20,
		0, 45, 35, 25,  # menu key
		0, 50, 560, 50, 18,  # lab1
		10, 105, 540, 260, 20,  # list
		10, 370, 400, 30, 20,  # backupstatus
		26,
			]  # noqa: E124

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Image manager"))

		self["lab1"] = Label()
		self["backupstatus"] = Label()
		self["key_red"] = Button(_("Delete"))
		self["key_green"] = Button(_("New backup"))
		self["key_yellow"] = Button(_("Downloads"))
		self["key_blue"] = Button(_("Flash"))

		self["key_menu"] = StaticText(_("MENU"))
		self["key_info"] = StaticText(_("INFO"))

		self["infoactions"] = ActionMap(["SetupActions"], {
			"info": self.showInfo,
		}, -1)
		self["defaultactions"] = ActionMap(["OkCancelActions", "MenuActions"], {
			"cancel": self.close,
			"menu": self.createSetup,
		}, -1)
		self["mainactions"] = ActionMap(["ColorActions", "OkCancelActions", "DirectionActions", "KeyboardInputActions"], {
			"red": self.keyDelete,
			"green": self.GreenPressed,
			"yellow": self.doDownload,
			"ok": self.keyRestore,
			"blue": self.keyRestore,
			"up": self.refreshUp,
			"down": self.refreshDown,
			"left": self.keyLeft,
			"right": self.keyRight,
			"upRepeated": self.refreshUp,
			"downRepeated": self.refreshDown,
			"leftRepeated": self.keyLeft,
			"rightRepeated": self.keyRight,
		}, -1)
		self["mainactions"].setEnabled(False)
		self.BackupRunning = False
		self.mountAvailable = False
		self.BackupDirectory = " "
		if SystemInfo["canMultiBoot"]:
			self.mtdboot = SystemInfo["MBbootdevice"]
		self.onChangedEntry = []
		if choices:
			self["list"] = MenuList(list=[((_("No images found on the selected download server...if password check validity")), "Waiter")])

		else:
			self["list"] = MenuList(list=[((_(" Press 'Menu' to select a storage device - none available")), "Waiter")])
			self["key_red"].hide()
			self["key_green"].hide()
			self["key_yellow"].hide()
			self["key_blue"].hide()
		self.populate_List()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.backupRunning)
		self.activityTimer.startLongTimer(10)
		self.Console = Console()
		self.ConsoleB = Console(binary=True)

		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next backup: ")
		self["backupstatus"].setText(str(backuptext))
		if self.selectionChanged not in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

	def selectionChanged(self):
		# Where is this used? self.onChangedEntry does not appear to be populated anywhere. Maybe dead code.
		item = self["list"].getCurrent()  # (name, link)
		desc = self["backupstatus"].text
		if item:
			name = item[1]
		else:
			name = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def backupRunning(self):
		self.BackupRunning = False
		if self.mountAvailable:
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Image manager")):
					self.BackupRunning = True
					break
			if self.BackupRunning:
				self["key_green"].setText(_("View progress"))
			else:
				self["key_green"].setText(_("New backup"))
			self["key_green"].show()
		else:
			self["key_green"].hide()
		self.activityTimer.startLongTimer(5)
		self.refreshList()  # display any new images that may have been sent too the box since the list was built

	def refreshUp(self):
		self["list"].moveUp()

	def refreshDown(self):
		self["list"].moveDown()

	def keyLeft(self):
		self["list"].pageUp()
		self.selectionChanged()

	def keyRight(self):
		self["list"].pageDown()
		self.selectionChanged()

	def refreshList(self):
		if self.BackupDirectory == " ":
			return
		imglist = []
		imagesDownloadedList = self.getImagesDownloaded()
		for image in imagesDownloadedList:
			imglist.append((image["name"], image["link"]))
		if imglist:
			self["key_red"].show()
			self["key_blue"].show()
		else:
			self["key_red"].hide()
			self["key_blue"].hide()
		self["list"].setList(imglist)
		self["list"].show()
		self.selectionChanged()

	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100 * job.progress / float(job.end)))

	def showJobView(self, job):
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable=False, backgroundable=True, afterEventChangeable=False, afterEvent="close")

	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def populate_List(self):
		if config.imagemanager.backuplocation.value.endswith("/"):
			mount = config.imagemanager.backuplocation.value, config.imagemanager.backuplocation.value[:-1]
		else:
			mount = config.imagemanager.backuplocation.value + "/", config.imagemanager.backuplocation.value
		hdd = "/media/hdd/", "/media/hdd"
		if mount not in config.imagemanager.backuplocation.choices.choices and hdd not in config.imagemanager.backuplocation.choices.choices:
			self["mainactions"].setEnabled(False)
			self.mountAvailable = False
			self["key_green"].hide()
			self["lab1"].setText(_("Device: None available") + "\n" + _("Press 'Menu' to select a storage device"))
		else:
			if mount not in config.imagemanager.backuplocation.choices.choices:
				self.BackupDirectory = "/media/hdd/imagebackups/"
				config.imagemanager.backuplocation.value = "/media/hdd/"
				config.imagemanager.backuplocation.save()
				self["lab1"].setText(_("The chosen location does not exist, using /media/hdd.") + "\n" + _("Select an image to flash."))
			else:
				self.BackupDirectory = config.imagemanager.backuplocation.value + "imagebackups/"
				s = statvfs(config.imagemanager.backuplocation.value)
				free = (s.f_bsize * s.f_bavail) // (1024 * 1024)
				self["lab1"].setText(_("Device: ") + config.imagemanager.backuplocation.value + " " + _("Free space:") + " " + str(free) + _("MB") + "\n" + _("Select an image to flash."))
			try:
				if not path.exists(self.BackupDirectory):
					mkdir(self.BackupDirectory, 0o755)
				if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup"):
					system("swapoff " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup")
					remove(self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup")
				self.refreshList()
			except Exception:
				self["lab1"].setText(_("Device: ") + config.imagemanager.backuplocation.value + "\n" + _("There is a problem with this device. Please reformat it and try again."))
			self["mainactions"].setEnabled(True)
			self.mountAvailable = True
			self["key_green"].show()

	def createSetup(self):
		self.session.openWithCallback(self.setupDone, ImageManagerSetup)

	def doDownload(self):
		choices = [(x[DISTRO], x) for x in FEED_URLS]
		if config.imagemanager.imagefeed_MyBuild.value.startswith("http"):
			choices.insert(0, ("My build", ("My build", config.imagemanager.imagefeed_MyBuild.value, "getMachineMake")))
		message = _("From which image library do you want to download?")
		self.session.openWithCallback(self.doDownloadCallback, MessageBox, message, list=choices, default=1, simple=True)

	def doDownloadCallback(self, retval):  # retval will be the config element (or False, in the case of aborting the MessageBox).
		if retval:
			self.session.openWithCallback(self.refreshList, ImageManagerDownload, self.BackupDirectory, retval)

	def setupDone(self, retval=None):
		self.populate_List()
		self.doneConfiguring()

	def doneConfiguring(self):
		now = int(time())
		if config.imagemanager.schedule.value:
			if autoImageManagerTimer is not None:
				print("[ImageManager] Backup Schedule Enabled at", strftime("%c", localtime(now)))
				autoImageManagerTimer.backupupdate()
		else:
			if autoImageManagerTimer is not None:
				global BackupTime
				BackupTime = 0
				print("[ImageManager] Backup Schedule Disabled at", strftime("%c", localtime(now)))
				autoImageManagerTimer.backupstop()
		if BackupTime > 0:
			t = localtime(BackupTime)
			backuptext = _("Next backup: ") + strftime(_("%a %e %b  %-H:%M"), t)
		else:
			backuptext = _("Next backup: ")
		self["backupstatus"].setText(str(backuptext))

	def keyDelete(self):
		self.sel = self["list"].getCurrent()  # (name, link)
		if self.sel is not None:
			self["list"].moveToIndex(self["list"].getSelectionIndex() if len(self["list"].list) > self["list"].getSelectionIndex() + 1 else max(len(self["list"].list) - 2, 0))  # hold the selection current possition if the list is long enough, else go to last item
			try:
				# print("[ImageManager][keyDelete] selected image=%s" % (self.sel[1]))
				if self.sel[1].endswith(".zip"):
					remove(self.sel[1])
				else:
					rmtree(self.sel[1])
			except:
				self.session.open(MessageBox, _("Delete failure - check device available."), MessageBox.TYPE_INFO, timeout=10)
			self.refreshList()

	def GreenPressed(self):
		backup = None
		self.BackupRunning = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Image manager")):
				backup = job
				self.BackupRunning = True
		if self.BackupRunning and backup:
			self.showJobView(backup)
		else:
			self.keyBackup()

	def keyBackup(self):
		message = _("Do you want to create a full image backup?\nThis can take about 6 minutes to complete.")
		ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO)
		ybox.setTitle(_("Backup confirmation"))

	def doBackup(self, answer):
		if answer is True:
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			self.BackupRunning = True
			self["key_green"].setText(_("View progress"))
			self["key_green"].show()
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Image manager")):
					break
			self.showJobView(job)

	def getImagesDownloaded(self):
		def getImages(files):
			for file in files:
				imagesFound.append({'link': file, 'name': file.split(ossep)[-1], 'mtime': stat(file).st_mtime})

		def checkMachineNameInFilename(filename):
			return model in filename or "-" + device_name + "-" in filename

		model = SystemInfo["machinebuild"]
		device_name = HardwareInfo().get_device_name()
		imagesFound = []
		if config.imagemanager.extensive_location_search.value:
			mediaList = ['/media/%s' % x for x in listdir('/media')] + (['/media/net/%s' % x for x in listdir('/media/net')] if path.isdir('/media/net') else []) + (['/media/autofs/%s' % x for x in listdir('/media/autofs')] if path.isdir('/media/autofs') else [])
		else:
			mediaList = [config.imagemanager.backuplocation.value]
		for media in mediaList:
			try:  # /media/autofs/xxx will crash listdir if "xxx" is inactive (e.g. dropped network link). os.access reports True for "xxx" so it seems we are forced to try/except here.
				medialist = listdir(media)
			except FileNotFoundError:
				continue
			getImages([path.join(media, x) for x in medialist if path.splitext(x)[1] == ".zip" and checkMachineNameInFilename(x)])
			for folder in ["imagebackups", "downloaded_images", "images"]:
				if folder in medialist:
					media2 = path.join(media, folder)
					if path.isdir(media2) and not path.islink(media2) and not path.ismount(media2):
						getImages([path.join(media2, x) for x in listdir(media2) if path.splitext(x)[1] == ".zip" and checkMachineNameInFilename(x)])
		imagesFound.sort(key=lambda x: x['mtime'], reverse=True)
		# print("[ImageManager][getImagesDownloaded] imagesFound=%s" % imagesFound)
		return imagesFound

	def doSettingsBackup(self):
		from Plugins.SystemPlugins.ViX.BackupManager import BackupFiles
		self.BackupFiles = BackupFiles(self.session, backuptype=BackupFiles.TYPE_IMAGEMANAGER)
		Components.Task.job_manager.AddJob(self.BackupFiles.createBackupJob())
		Components.Task.job_manager.in_background = False
		for job in Components.Task.job_manager.getPendingJobs():
			if job.name.startswith(_("Backup manager")):
				break
		self.session.openWithCallback(self.keyRestore3, JobView, job, cancelable=False, backgroundable=False, afterEventChangeable=False, afterEvent="close")

	def keyRestore(self):
		self.sel = self["list"].getCurrent()  # (name, link)
		if not self.sel:
			return
		print("[ImageManager][keyRestore] self.sel SystemInfo['MultiBootSlot']", self.sel[0], "   ", SystemInfo["MultiBootSlot"])
		if SystemInfo["MultiBootSlot"] == 0 and self.isVuKexecCompatibleImage(self.sel[0]):  # only if Vu multiboot has been enabled and the image is compatible
			message = [_("Are you sure you want to overwrite the Recovery image?")]
			if "VuSlot0" in self.sel[0]:
				callback = self.keyRestoreVuSlot0Image
				message.append(_("This change will overwrite all eMMC slots."))
				choices = None
			else:
				callback = self.keyRestorez0
				message.append(_("We advise flashing the new image to a regular MultiBoot slot and restoring a settings backup."))
				message.append(_("Select 'Flash regular slot' to flash a regular MultiBoot slot or select 'Overwrite Recovery' to overwrite the Recovery image."))
				choices = [(_("Flash regular slot"), False), (_("Overwrite Recovery"), True)]
			ybox = self.session.openWithCallback(callback, MessageBox, "\n".join(message), default=False, list=choices)
			ybox.setTitle(_("Restore confirmation"))
		else:
			self.keyRestore1()

	def keyRestoreVuSlot0Image(self, retval):
		if retval:
			self.keyRestorez1(retval=False)

	def keyRestorez0(self, retval):
		print("[ImageManager][keyRestorez0] retval", retval)
		if retval:
			message = (_("Do you want to backup eMMC slots? This will add from 1 -> 5 minutes per eMMC slot"))
			ybox = self.session.openWithCallback(self.keyRestorez1, MessageBox, message, default=True)
			ybox.setTitle(_("Copy eMMC slots confirmation"))
		else:
			self.keyRestore1()

	def keyRestorez1(self, retval):
		if retval:
			self.VuKexecCopyimage()
		else:
			self.multibootslot = 0												# set slot0 to be flashed
			self.Console.ePopen("umount /proc/cmdline", self.keyRestore3)		# tell ofgwrite not Vu Multiboot

	def keyRestore1(self):
		self.HasSDmmc = False
		self.multibootslot = 1
		self.MTDKERNEL = SystemInfo["mtdkernel"]
		self.MTDROOTFS = SystemInfo["mtdrootfs"]
		if SystemInfo["machinebuild"] == "et8500" and path.exists("/proc/mtd"):
			self.dualboot = self.dualBoot()
		recordings = self.session.nav.getRecordings()
		if not recordings:
			next_rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
		if recordings or (next_rec_time > 0 and (next_rec_time - time()) < 360):
			message = _("Recording(s) are in progress or coming up in few seconds!\nDo you still want to flash image\n%s?") % self.sel[0]
		else:
			message = _("Do you want to flash image\n%s") % self.sel[0]
		if SystemInfo["canMultiBoot"] is False:
			if config.imagemanager.autosettingsbackup.value:
				self.doSettingsBackup()
			else:
				self.keyRestore3()
		if SystemInfo["HasHiSi"]:
			if pathExists("/dev/sda4"):
				self.HasSDmmc = True
		imagedict = GetImagelist()
		choices = []
		currentimageslot = SystemInfo["MultiBootSlot"]
		for x in imagedict.keys():
			choices.append(((_("slot%s %s - %s (current image)") if x == currentimageslot else _("slot%s %s - %s")) % (x, SystemInfo["canMultiBoot"][x]["slotname"], imagedict[x]["imagename"]), (x)))
		self.session.openWithCallback(self.keyRestore2, MessageBox, message, list=choices, default=False, simple=True)

	def keyRestore2(self, retval):
		if retval:
			if SystemInfo["canMultiBoot"]:
				self.multibootslot = retval
				print("ImageManager", retval)
				self.MTDKERNEL = SystemInfo["canMultiBoot"][self.multibootslot]["kernel"].split("/")[2]
				if SystemInfo["HasMultibootMTD"]:
					self.MTDROOTFS = SystemInfo["canMultiBoot"][self.multibootslot]["root"]
				else:
					self.MTDROOTFS = SystemInfo["canMultiBoot"][self.multibootslot]["root"].split("/")[2]
			if SystemInfo["HasHiSi"] and SystemInfo["MultiBootSlot"] > 4 and self.multibootslot < 4:
				self.session.open(MessageBox, _("ImageManager - %s - cannot flash eMMC slot from sd card slot.") % SystemInfo["boxtype"], MessageBox.TYPE_INFO, timeout=10)
				return
			if self.sel:
				if SystemInfo["MultiBootSlot"] != 0 and config.imagemanager.autosettingsbackup.value:
					self.doSettingsBackup()
				else:
					self.keyRestore3()
			else:
				self.session.open(MessageBox, _("There is no image to flash."), MessageBox.TYPE_INFO, timeout=10)

	def keyRestore3(self, *args, **kwargs):
		self.restore_infobox = self.session.open(MessageBox, _("Please wait while the flash prepares."), MessageBox.TYPE_INFO, timeout=240, enable_input=False)
		if "/media/autofs" in config.imagemanager.backuplocation.value or "/media/net" in config.imagemanager.backuplocation.value:
			self.TEMPDESTROOT = tempfile.mkdtemp(prefix="imageRestore")
		else:
			self.TEMPDESTROOT = self.BackupDirectory + "imagerestore"

		if self.sel[1].endswith(".zip"):
			if not path.exists(self.TEMPDESTROOT):
				mkdir(self.TEMPDESTROOT, 0o755)
			self.Console.ePopen("unzip -o %s -d %s" % (self.sel[1], self.TEMPDESTROOT), self.keyRestore4)
		else:
			self.TEMPDESTROOT = self.sel[1]
			self.keyRestore4(0, 0)

	def keyRestore4(self, result, retval, extra_args=None):
		if retval == 0:
			self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("Flash image unzip successful."), MessageBox.TYPE_INFO, timeout=4)
			if SystemInfo["machinebuild"] == "et8500" and self.dualboot:
				message = _("ET8500 Multiboot: Yes to restore OS1 No to restore OS2:\n ") + self.sel[1]
				ybox = self.session.openWithCallback(self.keyRestore5_ET8500, MessageBox, message)
				ybox.setTitle(_("ET8500 Image Restore"))
			else:
				MAINDEST = "%s/%s" % (self.TEMPDESTROOT, SystemInfo["imagedir"])
				if pathExists("%s/SDAbackup" % MAINDEST) and self.multibootslot != 1:
					self.session.open(MessageBox, _("Multiboot only able to restore this backup to mmc slot1"), MessageBox.TYPE_INFO, timeout=20)
					print("[ImageManager] SF8008 mmc restore to SDcard failed:\n", end=' ')
					self.close()
				else:
					self.keyRestore6(0)
		else:
			self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("Unzip error (also sent to any debug log):\n%s") % result, MessageBox.TYPE_INFO, timeout=20)
			print("[ImageManager] unzip failed:\n", result)
			self.close()

	def keyRestore5_ET8500(self, answer):
		if answer:
			self.keyRestore6(0)
		else:
			self.keyRestore6(1)

	def keyRestore6(self, ret):
		MAINDEST = "%s/%s" % (self.TEMPDESTROOT, SystemInfo["imagedir"])
		print("[ImageManager] MAINDEST=%s" % MAINDEST)
		if ret == 0:
			CMD = "/usr/bin/ofgwrite -r -k '%s'" % MAINDEST							# normal non multiboot receiver
			if SystemInfo["canMultiBoot"]:
				if self.multibootslot == 0 and SystemInfo["HasKexecMultiboot"]:		# reset Vu Multiboot slot0
					kz0 = SystemInfo["mtdkernel"]
					rz0 = SystemInfo["mtdrootfs"]
					CMD = "/usr/bin/ofgwrite -k%s -r%s '%s'" % (kz0, rz0, MAINDEST)  # slot0 treat as kernel/root only multiboot receiver
				elif SystemInfo["HasHiSi"] and SystemInfo["canMultiBoot"][self.multibootslot]["rootsubdir"] is None:  # sf8008 type receiver using SD card in multiboot
					CMD = "/usr/bin/ofgwrite -r%s -k%s -m0 '%s'" % (self.MTDROOTFS, self.MTDKERNEL, MAINDEST)
					print("[ImageManager] running commnd:%s slot = %s" % (CMD, self.multibootslot))
					if fileExists("/boot/STARTUP") and fileExists("/boot/STARTUP_6"):
						copyfile("/boot/STARTUP_%s" % self.multibootslot, "/boot/STARTUP")
				elif SystemInfo["HasKexecMultiboot"]:
					if SystemInfo["HasKexecUSB"] and "mmcblk" not in self.MTDROOTFS:
						CMD = "/usr/bin/ofgwrite -r%s -kzImage -s'%s/linuxrootfs' -m%s '%s'" % (self.MTDROOTFS, SystemInfo["boxtype"][2:], self.multibootslot, MAINDEST)
					else:
						CMD = "/usr/bin/ofgwrite -r%s -kzImage -m%s '%s'" % (self.MTDROOTFS, self.multibootslot, MAINDEST)
					print("[ImageManager] running commnd:%s slot = %s" % (CMD, self.multibootslot))
				else:
					CMD = "/usr/bin/ofgwrite -r -k -m%s '%s'" % (self.multibootslot, MAINDEST)  # Normal multiboot
			elif SystemInfo["HasH9SD"]:
				if fileHas("/proc/cmdline", "root=/dev/mmcblk0p1") is True and fileExists("%s/rootfs.tar.bz2" % MAINDEST):  # h9 using SD card
					CMD = "/usr/bin/ofgwrite -rmmcblk0p1 '%s'" % MAINDEST
				elif fileExists("%s/rootfs.ubi" % MAINDEST) and fileExists("%s/rootfs.tar.bz2" % MAINDEST):  # h9 no SD card - build has both roots causes ofgwrite issue
					rename("%s/rootfs.tar.bz2" % MAINDEST, "%s/xx.txt" % MAINDEST)
		else:
			CMD = "/usr/bin/ofgwrite -rmtd4 -kmtd3  %s/" % MAINDEST  # Xtrend ET8500 with OS2 multiboot
		print("[ImageManager] running commnd:", CMD)
		self.Console.ePopen(CMD, self.ofgwriteResult)
		fbClass.getInstance().lock()

	def ofgwriteResult(self, result, retval, extra_args=None):
		fbClass.getInstance().unlock()
		print("[ImageManager] ofgwrite retval :", retval)
		if retval == 0:
			if SystemInfo["HasHiSi"] and SystemInfo["HasRootSubdir"] is False and self.HasSDmmc is False:  # sf8008 receiver 1 eMMC parition, No SD card
				self.session.open(TryQuitMainloop, 2)
			if SystemInfo["canMultiBoot"]:
				print("[ImageManager] slot %s result %s\n" % (self.multibootslot, result))
				tmp_dir = tempfile.mkdtemp(prefix="ImageManagerFlash")
				Console().ePopen("mount %s %s" % (self.mtdboot, tmp_dir))
				if pathExists(path.join(tmp_dir, "STARTUP")):
					copyfile(path.join(tmp_dir, SystemInfo["canMultiBoot"][self.multibootslot]["startupfile"].replace("boxmode=12'", "boxmode=1'")), path.join(tmp_dir, "STARTUP"))
				else:
					self.session.open(MessageBox, _("Multiboot ERROR! - no STARTUP in boot partition."), MessageBox.TYPE_INFO, timeout=20)
				Console().ePopen('umount %s' % tmp_dir)
				if not path.ismount(tmp_dir):
					rmdir(tmp_dir)
				self.session.open(TryQuitMainloop, 2)
			else:
				self.session.open(TryQuitMainloop, 2)
		else:
			self.session.openWithCallback(self.restore_infobox.close, MessageBox, _("ofgwrite error (also sent to any debug log):\n%s") % result, MessageBox.TYPE_INFO, timeout=20)
			print("[ImageManager] OFGWriteResult failed:\n", result)

	def dualBoot(self):
		rootfs2 = False
		kernel2 = False
		with open("/proc/mtd")as f:
			L = f.readlines()
			for x in L:
				if "rootfs2" in x:
					rootfs2 = True
				if "kernel2" in x:
					kernel2 = True
			if rootfs2 and kernel2:
				return True
			else:
				return False

	def isVuKexecCompatibleImage(self, name):
		retval = False
		if "VuSlot0" in name:
			retval = True
		else:
			name_split = name.split("-")
			if len(name_split) > 1 and name_split[0] in ("openbh", "openvix") and name[-8:] == "_usb.zip":  # "_usb.zip" only in build server images
				parts = name_split[1].split(".")
				if len(parts) > 1 and parts[0].isnumeric() and parts[1].isnumeric():
					version = float(parts[0] + "." + parts[1])
					if name_split[0] == "openbh" and version > 5.1:
						retval = True
					if name_split[0] == "openvix" and (version > 6.3 or version == 6.3 and len(parts) > 2 and parts[2].isnumeric() and int(parts[2]) > 2):  # greater than 6.2.002
						retval = True
		return retval

	def VuKexecCopyimage(self):
		installedHDD = False
		with open("/proc/mounts", "r") as fd:
			lines = fd.readlines()
		result = [line.strip().split(" ") for line in lines]
		print("[ImageManager][VuKexecCopyimage] result", result)
		for item in result:
			if '/media/hdd' in item[1] and "/dev/sd" in item[0]:
				installedHDD = True
				break
		if installedHDD and pathExists("/media/hdd"):
			if not pathExists("/media/hdd/%s" % SystemInfo["boxtype"]):
				mkdir("/media/hdd/%s" % SystemInfo["boxtype"])
			for slotnum in range(1, 4):
				if pathExists("/linuxrootfs%s" % slotnum):
					if pathExists("/media/hdd/%s/linuxrootfs%s/" % (SystemInfo["boxtype"], slotnum)):
						rmtree("/media/hdd/%s/linuxrootfs%s" % (SystemInfo["boxtype"], slotnum), ignore_errors=True)
					Console().ePopen("cp -R /linuxrootfs%s . /media/hdd/%s/" % (slotnum, SystemInfo["boxtype"]))
		if not installedHDD:
			self.session.open(MessageBox, _("ImageManager - no HDD unable to backup Vu Multiboot eMMC slots"), MessageBox.TYPE_INFO, timeout=5)
		self.multibootslot = 0												# set slot0 to be flashed
		self.Console.ePopen("umount /proc/cmdline", self.keyRestore3)		# tell ofgwrite not Vu Multiboot

	def infoText(self):
		# add info text sentence by sentence to make translators job easier
		return " ".join([
			_("FULL IMAGE BACKUP"),
			"\n" +
			_("A full image backup can be created at any time."),
			_("The backup creates a snapshot of the image exactly as it is at the current instant."),
			_("It allows making changes to the box with the knowledge that the box can be safely reverted back to a previous known working state."),
			_("To make an image backup select GREEN from Image Manager main screen."),
			"\n\n" +
			_("IMAGE DOWNLOADS"),
			"\n" +
			_("Image Manager allows downloading images from OpenViX image server and from a range of other distros."),
			_("To be able to download any image local storage must already be configured, HDD, USB or SD, and also be selected as the 'Backup location' in Image Manager setup menu."),
			_("To start a download select YELLOW from Image Manager main screen, then select the distro, and finally which image to download."),
			_("The image will then be downloaded to the 'Backup location'."),
			_("Please note, images are large, generally over 100 MB so downloading over a slow or unstable connection is prohibitive."),
			_("Also, instead to downloading, it is possible to send an image to the 'Backup location' by FTP."),
			"\n\n" +
			_("FLASHING"),
			"\n" +
			_("Before flashing an image 'Automatic settings backup' should be enabled in Image Manager setup menu."),
			_("This will make a backup of the current settings and plugins which can be used later when setting up the new image in the First Install Wizard."),
			_("To flash an image first select it from the list of images in the Image Manager main screen (the image will need to have already been downloaded) and then press BLUE."),
			_("After confirming, an automatic backup will be made and then the image will be flashed."),
			_("Upon completion the receiver will reboot and display the First Install Wizard."),
			_("From here the settings backup and plugins can be restored just by selecting that option."),
			"\n\n" +
			_("RECOVERY MODE"),
			"\n" +
			_("This only applies to a handful of Vu+ 4K models."),
			_("Backups of the RECOVERY image will contain a copy of all the client images."),
			_("When flashing from the recovery image it is possible to flash it to the recovery slot."),
			_("The new image will overwrite the previous one including any client images that were also configured, so care needs to be taken to make any full image backups (including client images) before overwriting the recovery image."),
			])

	def showInfo(self):
		self.session.open(TextBox, self.infoText(), self.title + " - " + _("info"))


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
			print("[ImageManager] Backup Schedule Enabled at ", strftime("%c", localtime(now)))
			if now > 1262304000:
				self.backupupdate()
			else:
				print("[ImageManager] Backup Time not yet set.")
				BackupTime = 0
				self.backupactivityTimer.start(36000)
		else:
			BackupTime = 0
			print("[ImageManager] Backup Schedule Disabled at", strftime("(now=%c)", localtime(now)))
			self.backupactivityTimer.stop()

	def backupupdatedelay(self):
		self.backupactivityTimer.stop()
		self.backupupdate()

	def getBackupTime(self):
		backupclock = config.imagemanager.scheduletime.value
		#
		# Work out the time of the *NEXT* backup - which is the configured clock
		# time on the nth relevant day after the last recorded backup day.
		# The last backup time will have been set as 12:00 on the day it
		# happened. All we use is the actual day from that value.
		#
		lastbkup_t = int(config.imagemanager.lastbackup.value)
		if config.imagemanager.repeattype.value == "daily":
			nextbkup_t = lastbkup_t + 24 * 3600
		elif config.imagemanager.repeattype.value == "weekly":
			nextbkup_t = lastbkup_t + 7 * 24 * 3600
		elif config.imagemanager.repeattype.value == "monthly":
			nextbkup_t = lastbkup_t + 30 * 24 * 3600
		nextbkup = localtime(nextbkup_t)
		return int(mktime((nextbkup.tm_year, nextbkup.tm_mon, nextbkup.tm_mday, backupclock[0], backupclock[1], 0, nextbkup.tm_wday, nextbkup.tm_yday, nextbkup.tm_isdst)))

	def backupupdate(self, atLeast=0):
		self.backuptimer.stop()
		global BackupTime
		BackupTime = self.getBackupTime()
		now = int(time())
		if BackupTime > 0:
			if BackupTime < now + atLeast:
				self.backuptimer.startLongTimer(60)  # Backup missed - run it 60s from now
				print("[ImageManager] Backup Time overdue - running in 60s")
			else:
				delay = BackupTime - now  # Backup in future - set the timer...
				self.backuptimer.startLongTimer(delay)
		else:
			BackupTime = -1
		print("[ImageManager] Backup Time set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now)))
		return BackupTime

	def backupstop(self):
		self.backuptimer.stop()

	def BackuponTimer(self):
		self.backuptimer.stop()
		now = int(time())
		wake = self.getBackupTime()
		# If we're close enough, we're okay...
		if wake - now < 60:
			print("[ImageManager] Backup onTimer occured at", strftime("%c", localtime(now)))
			from Screens.Standby import inStandby

			if not inStandby and config.imagemanager.query.value:
				message = _("Your %s %s is about to create a full image backup, this can take about 6 minutes to complete.\nDo you want to allow this?") % (SystemInfo["displaybrand"], SystemInfo["machinename"])
				ybox = self.session.openWithCallback(self.doBackup, MessageBox, message, MessageBox.TYPE_YESNO, timeout=30)
				ybox.setTitle("Scheduled backup.")
			else:
				print("[ImageManager] in Standby or no querying, so just running backup", strftime("%c", localtime(now)))
				self.doBackup(True)
		else:
			print("[ImageManager] We are not close enough", strftime("%c", localtime(now)))
			self.backupupdate(60)

	def doBackup(self, answer):
		now = int(time())
		if answer is False:
			if config.imagemanager.backupretrycount.value < 2:
				print("[ImageManager] Number of retries", config.imagemanager.backupretrycount.value)
				print("[ImageManager] Backup delayed.")
				repeat = config.imagemanager.backupretrycount.value
				repeat += 1
				config.imagemanager.backupretrycount.setValue(repeat)
				BackupTime = now + (int(config.imagemanager.backupretry.value) * 60)
				print("[ImageManager] Backup Time now set to", strftime("%c", localtime(BackupTime)), strftime("(now=%c)", localtime(now)))
				self.backuptimer.startLongTimer(int(config.imagemanager.backupretry.value) * 60)
			else:
				atLeast = 60
				print("[ImageManager] Enough Retries, delaying till next schedule.", strftime("%c", localtime(now)))
				self.session.open(MessageBox, _("Enough retries, delaying till next schedule."), MessageBox.TYPE_INFO, timeout=10)
				config.imagemanager.backupretrycount.setValue(0)
				self.backupupdate(atLeast)
		else:
			print("[ImageManager] Running Backup", strftime("%c", localtime(now)))
			self.ImageBackup = ImageBackup(self.session)
			Components.Task.job_manager.AddJob(self.ImageBackup.createBackupJob())
			#      Note that fact that the job has been *scheduled*.
			#      We do *not* just note successful completion, as that would
			#      result in a loop on issues such as disk-full.
			#      Also all that we actually want to know is the day, not the time, so
			#      we actually remember midday, which avoids problems around DLST changes
			#      for backups scheduled within an hour of midnight.
			#
			sched = localtime(time())
			sched_t = int(mktime((sched.tm_year, sched.tm_mon, sched.tm_mday, 12, 0, 0, sched.tm_wday, sched.tm_yday, sched.tm_isdst)))
			config.imagemanager.lastbackup.value = sched_t
			config.imagemanager.lastbackup.save()
		# self.close()


class ImageBackup(Screen):
	skin = ["""
	<screen name="VIXImageManager" position="center,center" size="%d,%d">
		<ePixmap pixmap="skin_default/buttons/red.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="key_red" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget name="lab1" position="%d,%d" size="%d,%d" font="Regular; %d" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="%d,%d" size="%d,%d" font="Regular;%d" scrollbarMode="showOnDemand"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(%d)
		</applet>
	</screen>""",
		560, 400,  # screen
		0, 0, 140, 40,  # colors
		140, 0, 140, 40,
		280, 0, 140, 40,
		420, 0, 140, 40,
		0, 0, 140, 40, 20,
		140, 0, 140, 40, 20,
		280, 0, 140, 40, 20,
		420, 0, 140, 40, 20,
		0, 50, 560, 50, 18,  # lab1
		10, 105, 540, 260, 20,  # list
		26,
			]  # noqa: E124

	def __init__(self, session, updatebackup=False):
		Screen.__init__(self, session)
		self.Console = Console()
		self.ConsoleB = Console(binary=True)
		self.BackupDevice = config.imagemanager.backuplocation.value
		print("[ImageManager] Device: " + self.BackupDevice)
		self.BackupDirectory = config.imagemanager.backuplocation.value + "imagebackups/"
		print("[ImageManager] Directory: " + self.BackupDirectory)
		self.BackupDate = strftime("%Y%m%d_%H%M%S", localtime())
		self.WORKDIR = self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-temp"
		self.TMPDIR = self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-mount"
		backupType = "-"
		if updatebackup:
			backupType = "-SoftwareUpdate-"
		imageSubBuild = ""
		if SystemInfo["imagetype"] != "release":
			imageSubBuild = ".%s" % SystemInfo["imagedevbuild"]
		self.MAINDESTROOT = self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + backupType + SystemInfo["imageversion"] + "." + SystemInfo["imagebuild"] + imageSubBuild + "-" + self.BackupDate
		self.KERNELFILE = SystemInfo["kernelfile"]
		self.ROOTFSFILE = SystemInfo["rootfile"]
		self.MAINDEST = self.MAINDESTROOT + "/" + SystemInfo["imagedir"] + "/"
		self.MAINDEST2 = self.MAINDESTROOT + "/"
		self.MODEL = SystemInfo["machinebuild"]
		self.MCBUILD = SystemInfo["model"]
		self.IMAGEDISTRO = SystemInfo["distro"]
		self.DISTROVERSION = SystemInfo["imageversion"]
		self.DISTROBUILD = SystemInfo["imagebuild"]
		self.KERNELBIN = SystemInfo["kernelfile"]
		self.UBINIZE_ARGS = SystemInfo["ubinize"]
		self.MKUBIFS_ARGS = SystemInfo["mkubifs"]
		self.ROOTFSTYPE = SystemInfo["imagefs"].strip()
		self.ROOTFSSUBDIR = "none"
		self.VuSlot0 = ""
		self.EMMCIMG = "none"
		self.MTDBOOT = "none"
		if SystemInfo["canBackupEMC"]:
			(self.EMMCIMG, self.MTDBOOT) = SystemInfo["canBackupEMC"]
		print("[ImageManager] canBackupEMC:", SystemInfo["canBackupEMC"])
		self.KERN = "mmc"
		self.rootdir = 0
		if SystemInfo["canMultiBoot"]:
			slot = SystemInfo["MultiBootSlot"]
			print("[ImageManager] slot: ", slot)
			if SystemInfo["HasKexecMultiboot"]:
				self.MTDKERNEL = SystemInfo["mtdkernel"] if slot == 0 else SystemInfo["canMultiBoot"][slot]["kernel"]
				self.MTDROOTFS = SystemInfo["mtdrootfs"] if slot == 0 else SystemInfo["canMultiBoot"][slot]["root"].split("/")[2]
				self.VuSlot0 = "-VuSlot0" if slot == 0 else ""
			else:
				self.MTDKERNEL = SystemInfo["canMultiBoot"][slot]["kernel"].split("/")[2]
			if SystemInfo["HasMultibootMTD"]:
				self.MTDROOTFS = SystemInfo["canMultiBoot"][slot]["root"]  # sfx60xx ubi0:ubifs not mtd=
			elif not SystemInfo["HasKexecMultiboot"]:
				self.MTDROOTFS = SystemInfo["canMultiBoot"][slot]["root"].split("/")[2]
			if SystemInfo["HasRootSubdir"] and slot != 0:
				self.ROOTFSSUBDIR = SystemInfo["canMultiBoot"][slot]["rootsubdir"]
		else:
			self.MTDKERNEL = SystemInfo["mtdkernel"]
			self.MTDROOTFS = SystemInfo["mtdrootfs"]
		if SystemInfo["model"] in ("gb7252", "gbx34k"):
			self.GB4Kbin = "boot.bin"
			self.GB4Krescue = "rescue.bin"
		if "sda" in self.MTDKERNEL:
			self.KERN = "sda"
		print("[ImageManager] HasKexecMultiboot:", SystemInfo["HasKexecMultiboot"])
		print("[ImageManager] Model:", self.MODEL)
		print("[ImageManager] Machine Build:", self.MCBUILD)
		print("[ImageManager] Kernel File:", self.KERNELFILE)
		print("[ImageManager] Root File:", self.ROOTFSFILE)
		print("[ImageManager] MTD Kernel:", self.MTDKERNEL)
		print("[ImageManager] MTD Root:", self.MTDROOTFS)
		print("[ImageManager] ROOTFSSUBDIR:", self.ROOTFSSUBDIR)
		print("[ImageManager] ROOTFSTYPE:", self.ROOTFSTYPE)
		print("[ImageManager] MAINDESTROOT:", self.MAINDESTROOT)
		print("[ImageManager] MAINDEST:", self.MAINDEST)
		print("[ImageManager] MAINDEST2:", self.MAINDEST2)
		print("[ImageManager] WORKDIR:", self.WORKDIR)
		print("[ImageManager] TMPDIR:", self.TMPDIR)
		print("[ImageManager] EMMCIMG:", self.EMMCIMG)
		print("[ImageManager] MTDBOOT:", self.MTDBOOT)
		self.swapdevice = ""
		self.RamChecked = False
		self.SwapCreated = False
		self.Stage1Completed = False
		self.Stage2Completed = False
		self.Stage3Completed = False
		self.Stage4Completed = False
		self.Stage5Completed = False
		self.Stage6Completed = False

	def createBackupJob(self):
		job = Components.Task.Job(_("Image manager"))

		task = Components.Task.PythonTask(job, _("Setting up..."))
		task.work = self.JobStart
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Checking free RAM.."), timeoutCount=10)
		task.check = lambda: self.RamChecked
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating SWAP.."), timeoutCount=120)
		task.check = lambda: self.SwapCreated
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Backing up kernel..."))
		task.work = self.doBackup1
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up kernel..."), timeoutCount=900)
		task.check = lambda: self.Stage1Completed
		task.weighting = 35

		task = Components.Task.PythonTask(job, _("Backing up root file system..."))
		task.work = self.doBackup2
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up root file system..."), timeoutCount=2700)
		task.check = lambda: self.Stage2Completed
		task.weighting = 15

		task = Components.Task.PythonTask(job, _("Backing up eMMC partitions for USB flash ..."))
		task.work = self.doBackup3
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Backing up eMMC partitions for USB flash..."), timeoutCount=900)
		task.check = lambda: self.Stage3Completed
		task.weighting = 15

		task = Components.Task.PythonTask(job, _("Removing temp mounts..."))
		task.work = self.doBackup4
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Removing temp mounts..."), timeoutCount=30)
		task.check = lambda: self.Stage4Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Moving to backup Location..."))
		task.work = self.doBackup5
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Moving to backup Location..."), timeoutCount=30)
		task.check = lambda: self.Stage5Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Creating zip..."))
		task.work = self.doBackup6
		task.weighting = 5

		task = Components.Task.ConditionTask(job, _("Creating zip..."), timeoutCount=900)
		task.check = lambda: self.Stage6Completed
		task.weighting = 5

		task = Components.Task.PythonTask(job, _("Backup complete."))
		task.work = self.BackupComplete
		task.weighting = 5

		return job

	def JobStart(self):
		try:
			if not path.exists(self.BackupDirectory):
				mkdir(self.BackupDirectory, 0o755)
			if path.exists(self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup"):
				system("swapoff " + self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup")
				remove(self.BackupDirectory + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup")
		except Exception as e:
			print(str(e))
			print("[ImageManager] Device: " + config.imagemanager.backuplocation.value + ", i don't seem to have write access to this device.")

		s = statvfs(self.BackupDevice)
		free = (s.f_bsize * s.f_bavail) // (1024 * 1024)
		if int(free) < 200:
			AddPopupWithCallback(
				self.BackupComplete,
				_("The backup location does not have enough free space." + "\n" + self.BackupDevice + "only has " + str(free) + "MB free."),
				MessageBox.TYPE_INFO,
				10,
				"RamCheckFailedNotification"
			)
		else:
			self.MemCheck()

	def MemCheck(self):
		memfree = 0
		swapfree = 0
		with open("/proc/meminfo", "r") as f:
			for line in f.readlines():
				if line.find("MemFree") != -1:
					parts = line.strip().split()
					memfree = int(parts[1])
				elif line.find("SwapFree") != -1:
					parts = line.strip().split()
					swapfree = int(parts[1])
		TotalFree = memfree + swapfree
		print("[ImageManager] Stage1: Free Mem", TotalFree)
		if int(TotalFree) < 3000:
			supported_filesystems = frozenset(("ext4", "ext3", "ext2"))
			candidates = []
			mounts = getProcMounts()
			for partition in harddiskmanager.getMountedPartitions(False, mounts):
				if partition.filesystem(mounts) in supported_filesystems:
					candidates.append((partition.description, partition.mountpoint))
			for swapdevice in candidates:
				self.swapdevice = swapdevice[1]
			if self.swapdevice:
				print("[ImageManager] Stage1: Creating SWAP file.")
				self.RamChecked = True
				self.MemCheck2()
			else:
				print("[ImageManager] Sorry, not enough free RAM found, and no physical devices that supports SWAP attached")
				AddPopupWithCallback(
					self.BackupComplete,
					_("Sorry, not enough free RAM found, and no physical devices that supports SWAP attached. Can't create SWAP file on network or fat32 file-systems, unable to make backup."),
					MessageBox.TYPE_INFO,
					10,
					"RamCheckFailedNotification"
				)
		else:
			print("[ImageManager] Stage1: Found Enough RAM")
			self.RamChecked = True
			self.SwapCreated = True

	def MemCheck2(self):
		self.ConsoleB.ePopen("dd if=/dev/zero of=" + self.swapdevice + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup bs=1024 count=61440", self.MemCheck3)

	def MemCheck3(self, result, retval, extra_args=None):
		if retval == 0:
			self.ConsoleB.ePopen("mkswap " + self.swapdevice + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup", self.MemCheck4)

	def MemCheck4(self, result, retval, extra_args=None):
		if retval == 0:
			self.ConsoleB.ePopen("swapon " + self.swapdevice + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup", self.MemCheck5)

	def MemCheck5(self, result, retval, extra_args=None):
		self.SwapCreated = True

	def doBackup1(self):
		print("[ImageManager] Stage1: Creating tmp folders.", self.BackupDirectory)
		print("[ImageManager] Stage1: Creating backup Folders.")
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		mkdir(self.WORKDIR, 0o644)
		if path.exists(self.TMPDIR + "/root") and path.ismount(self.TMPDIR + "/root"):
			system("umount " + self.TMPDIR + "/root")
		elif path.exists(self.TMPDIR + "/root"):
			rmtree(self.TMPDIR + "/root")
		if path.exists(self.TMPDIR):
			rmtree(self.TMPDIR)
		makedirs(self.TMPDIR, 0o644)
		makedirs(self.TMPDIR + "/root", 0o644)
		makedirs(self.MAINDESTROOT, 0o644)
		self.commands = []
		makedirs(self.MAINDEST, 0o644)
		if SystemInfo["canMultiBoot"]:
			slot = SystemInfo["MultiBootSlot"]
		print("[ImageManager] Stage1: Making Kernel Image.")
		if "bin" or "uImage" in self.KERNELFILE:
			if SystemInfo["HasKexecMultiboot"]:
				# boot = "boot" if slot > 0 and slot < 4 else "dev/%s/%s"  %(self.MTDROOTFS, self.ROOTFSSUBDIR)
				boot = "boot"
				self.command = "dd if=/%s/%s of=%s/vmlinux.bin" % (boot, SystemInfo["canMultiBoot"][slot]["kernel"].rsplit("/", 1)[1], self.WORKDIR) if slot != 0 else "dd if=/dev/%s of=%s/vmlinux.bin" % (self.MTDKERNEL, self.WORKDIR)
			else:
				self.command = "dd if=/dev/%s of=%s/vmlinux.bin" % (self.MTDKERNEL, self.WORKDIR)
		else:
			self.command = "nanddump /dev/%s -f %s/vmlinux.gz" % (self.MTDKERNEL, self.WORKDIR)
		self.ConsoleB.ePopen(self.command, self.Stage1Complete)

	def Stage1Complete(self, result, retval, extra_args=None):
		print("[ImageManager][Stage1Complete]: result, retval", result, retval)
		if retval == 0:
			self.Stage1Completed = True
			print("[ImageManager] Stage1: Complete.")

	def doBackup2(self):
		print("[ImageManager] Stage2: Making Root Image.")
		if "jffs2" in self.ROOTFSTYPE.split():
			print("[ImageManager] Stage2: JFFS2 Detected.")
			self.ROOTFSTYPE = "jffs2"
			if SystemInfo["model"] == "gb800solo":
				JFFS2OPTIONS = " --disable-compressor=lzo -e131072 -l -p125829120"
			else:
				JFFS2OPTIONS = " --disable-compressor=lzo --eraseblock=0x20000 -n -l"
			self.commands.append("mount --bind / %s/root" % self.TMPDIR)
			self.commands.append("mkfs.jffs2 --root=%s/root --faketime --output=%s/rootfs.jffs2 %s" % (self.TMPDIR, self.WORKDIR, JFFS2OPTIONS))
		elif "ubi" in self.ROOTFSTYPE.split() and self.ROOTFSTYPE != "octagonubi":
			print("[ImageManager] Stage2: UBIFS Detected.")
			self.ROOTFSTYPE = "ubifs"
			with open("%s/ubinize.cfg" % self.WORKDIR, "w") as output:
				output.write("[ubifs]\n")
				output.write("mode=ubi\n")
				output.write("image=%s/root.ubi\n" % self.WORKDIR)
				output.write("vol_id=0\n")
				output.write("vol_type=dynamic\n")
				output.write("vol_name=rootfs\n")
				output.write("vol_flags=autoresize\n")

			self.commands.append("mount -o bind,ro / %s/root" % self.TMPDIR)
			if SystemInfo["model"] in ("h9", "i55plus"):
				with open("/proc/cmdline", "r") as z:
					if SystemInfo["HasMMC"] and "root=/dev/mmcblk0p1" in z.read():
						self.ROOTFSTYPE = "tar.bz2"
						self.commands.append("/bin/tar -jcf %s/rootfs.tar.bz2 -C %s/root --exclude ./var/nmbd --exclude ./.resizerootfs --exclude ./.resize-rootfs --exclude ./.resize-linuxrootfs --exclude ./.resize-userdata --exclude ./var/lib/samba/private/msg.sock ." % (self.WORKDIR, self.TMPDIR))
					else:
						self.commands.append("touch %s/root.ubi" % self.WORKDIR)
						self.commands.append("mkfs.ubifs -r %s/root -o %s/root.ubi %s" % (self.TMPDIR, self.WORKDIR, self.MKUBIFS_ARGS))
						self.commands.append("ubinize -o %s/rootfs.ubifs %s %s/ubinize.cfg" % (self.WORKDIR, self.UBINIZE_ARGS, self.WORKDIR))
					self.commands.append("echo \" \"")
					self.commands.append('echo "' + _("Create:") + " fastboot dump" + '"')
					self.commands.append("dd if=/dev/mtd0 of=%s/fastboot.bin" % self.WORKDIR)
					self.commands.append("dd if=/dev/mtd0 of=%s/fastboot.bin" % self.MAINDEST2)
					self.commands.append('echo "' + _("Create:") + " bootargs dump" + '"')
					self.commands.append("dd if=/dev/mtd1 of=%s/bootargs.bin" % self.WORKDIR)
					self.commands.append("dd if=/dev/mtd1 of=%s/bootargs.bin" % self.MAINDEST2)
					self.commands.append('echo "' + _("Create:") + " baseparam dump" + '"')
					self.commands.append("dd if=/dev/mtd2 of=%s/baseparam.bin" % self.WORKDIR)
					self.commands.append('echo "' + _("Create:") + " pq_param dump" + '"')
					self.commands.append("dd if=/dev/mtd3 of=%s/pq_param.bin" % self.WORKDIR)
					self.commands.append('echo "' + _("Create:") + " logo dump" + '"')
					self.commands.append("dd if=/dev/mtd4 of=%s/logo.bin" % self.WORKDIR)
			else:
				if not SystemInfo["model"] in ("h8"):
					self.MKUBIFS_ARGS = "-m 2048 -e 126976 -c 4096 -F"
					self.UBINIZE_ARGS = "-m 2048 -p 128KiB"
				self.commands.append("touch %s/root.ubi" % self.WORKDIR)
				self.commands.append("mkfs.ubifs -r %s/root -o %s/root.ubi %s" % (self.TMPDIR, self.WORKDIR, self.MKUBIFS_ARGS))
				self.commands.append("ubinize -o %s/rootfs.ubifs %s %s/ubinize.cfg" % (self.WORKDIR, self.UBINIZE_ARGS, self.WORKDIR))
		else:
			print("[ImageManager] Stage2: TAR.BZIP Detected.")
			self.ROOTFSTYPE = "tar.bz2"
			if SystemInfo["canMultiBoot"]:
				if SystemInfo["HasMultibootMTD"]:
					self.commands.append("mount -t ubifs %s %s/root" % (self.MTDROOTFS, self.TMPDIR))
				else:
					self.commands.append("mount /dev/%s %s/root" % (self.MTDROOTFS, self.TMPDIR))
			else:
				self.commands.append("mount --bind / %s/root" % self.TMPDIR)
			if SystemInfo["canMultiBoot"] and SystemInfo["MultiBootSlot"] == 0:
				self.commands.append("/bin/tar -jcf %s/rootfs.tar.bz2 -C %s/root --exclude ./var/nmbd --exclude ./.resizerootfs --exclude ./linuxrootfs* --exclude ./.resize-rootfs --exclude ./.resize-linuxrootfs --exclude ./.resize-userdata --exclude ./var/lib/samba/private/msg.sock ." % (self.WORKDIR, self.TMPDIR))
			elif SystemInfo["HasRootSubdir"]:
				self.commands.append("/bin/tar -jcf %s/rootfs.tar.bz2 -C %s/root/%s --exclude ./var/nmbd --exclude ./.resizerootfs --exclude ./.resize-rootfs --exclude ./.resize-linuxrootfs --exclude ./.resize-userdata --exclude ./var/lib/samba/private/msg.sock ." % (self.WORKDIR, self.TMPDIR, self.ROOTFSSUBDIR))
			else:
				self.commands.append("/bin/tar -jcf %s/rootfs.tar.bz2 -C %s/root --exclude ./var/nmbd --exclude ./.resizerootfs --exclude ./.resize-rootfs --exclude ./.resize-linuxrootfs --exclude ./.resize-userdata --exclude ./var/lib/samba/private/msg.sock ." % (self.WORKDIR, self.TMPDIR))
			self.commands.append("sync")
			if SystemInfo["model"] in ("gb7252", "gbx34k"):
				self.commands.append("dd if=/dev/mmcblk0p1 of=%s/boot.bin" % self.WORKDIR)
				self.commands.append("dd if=/dev/mmcblk0p3 of=%s/rescue.bin" % self.WORKDIR)
				print("[ImageManager] Stage2: Create: boot dump boot.bin:", self.MODEL)
				print("[ImageManager] Stage2: Create: rescue dump rescue.bin:", self.MODEL)
		print("[ImageManager] ROOTFSTYPE:", self.ROOTFSTYPE)
		self.ConsoleB.eBatch(self.commands, self.Stage2Complete, debug=False)

	def Stage2Complete(self, extra_args=None):
		if len(self.ConsoleB.appContainers) == 0:
			self.Stage2Completed = True
			print("[ImageManager] Stage2: Complete.")

	def doBackup3(self):
		print("[ImageManager] Stage3: Making eMMC Image.")
		self.commandMB = []
		if self.EMMCIMG == "disk.img":
			print("[ImageManager] hd51/h7: EMMC Detected.")  # hd51 receiver with multiple eMMC partitions in class
			EMMC_IMAGE = "%s/%s" % (self.WORKDIR, self.EMMCIMG)
			BLOCK_SIZE = 512
			BLOCK_SECTOR = 2
			IMAGE_ROOTFS_ALIGNMENT = 1024
			BOOT_PARTITION_SIZE = 3072
			KERNEL_PARTITION_SIZE = 8192
			ROOTFS_PARTITION_SIZE = 1048576
			EMMC_IMAGE_SIZE = 3817472
			KERNEL_PARTITION_OFFSET = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			ROOTFS_PARTITION_OFFSET = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SECOND_KERNEL_PARTITION_OFFSET = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			THIRD_KERNEL_PARTITION_OFFSET = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			FOURTH_KERNEL_PARTITION_OFFSET = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			MULTI_ROOTFS_PARTITION_OFFSET = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			EMMC_IMAGE_SEEK = int(EMMC_IMAGE_SIZE) * int(BLOCK_SECTOR)
			self.commandMB.append("dd if=/dev/zero of=%s bs=%s count=0 seek=%s" % (EMMC_IMAGE, BLOCK_SIZE, EMMC_IMAGE_SEEK))
			self.commandMB.append("parted -s %s mklabel gpt" % EMMC_IMAGE)
			PARTED_END_BOOT = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart boot fat16 %s %s" % (EMMC_IMAGE, IMAGE_ROOTFS_ALIGNMENT, PARTED_END_BOOT))
			PARTED_END_KERNEL1 = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart linuxkernel %s %s" % (EMMC_IMAGE, KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL1))
			PARTED_END_ROOTFS1 = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart linuxrootfs ext4 %s %s" % (EMMC_IMAGE, ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS1))
			PARTED_END_KERNEL2 = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart linuxkernel2 %s %s" % (EMMC_IMAGE, SECOND_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL2))
			PARTED_END_KERNEL3 = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart linuxkernel3 %s %s" % (EMMC_IMAGE, THIRD_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL3))
			PARTED_END_KERNEL4 = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart linuxkernel4 %s %s" % (EMMC_IMAGE, FOURTH_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL4))
			try:
				with open("/proc/swaps", "r") as rd:
					if "mmcblk0p7" in rd.read():
						SWAP_PARTITION_OFFSET = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
						SWAP_PARTITION_SIZE = int(262144)
						MULTI_ROOTFS_PARTITION_OFFSET = int(SWAP_PARTITION_OFFSET) + int(SWAP_PARTITION_SIZE)
						self.commandMB.append("parted -s %s unit KiB mkpart swap linux-swap %s %s" % (EMMC_IMAGE, SWAP_PARTITION_OFFSET, SWAP_PARTITION_OFFSET + SWAP_PARTITION_SIZE))
						self.commandMB.append("parted -s %s unit KiB mkpart userdata ext4 %s 100%%" % (EMMC_IMAGE, MULTI_ROOTFS_PARTITION_OFFSET))
					else:
						self.commandMB.append("parted -s %s unit KiB mkpart userdata ext4 %s 100%%" % (EMMC_IMAGE, MULTI_ROOTFS_PARTITION_OFFSET))
			except Exception:
				self.commandMB.append("parted -s %s unit KiB mkpart userdata ext4 %s 100%%" % (EMMC_IMAGE, MULTI_ROOTFS_PARTITION_OFFSET))

			BOOT_IMAGE_SEEK = int(IMAGE_ROOTFS_ALIGNMENT) * int(BLOCK_SECTOR)
			self.commandMB.append("dd if=%s of=%s seek=%s" % (self.MTDBOOT, EMMC_IMAGE, BOOT_IMAGE_SEEK))
			KERNEL_IMAGE_SEEK = int(KERNEL_PARTITION_OFFSET) * int(BLOCK_SECTOR)
			self.commandMB.append("dd if=/dev/%s of=%s seek=%s" % (self.MTDKERNEL, EMMC_IMAGE, KERNEL_IMAGE_SEEK))
			ROOTFS_IMAGE_SEEK = int(ROOTFS_PARTITION_OFFSET) * int(BLOCK_SECTOR)
			self.commandMB.append("dd if=/dev/%s of=%s seek=%s " % (self.MTDROOTFS, EMMC_IMAGE, ROOTFS_IMAGE_SEEK))
			self.ConsoleB.eBatch(self.commandMB, self.Stage3Complete, debug=False)

		elif self.EMMCIMG == "emmc.img":
			print("[ImageManager] osmio4k: EMMC Detected.")  # osmio4k receiver with multiple eMMC partitions in class
			IMAGE_ROOTFS_ALIGNMENT = 1024
			BOOT_PARTITION_SIZE = 3072
			KERNEL_PARTITION_SIZE = 8192
			ROOTFS_PARTITION_SIZE = 1898496
			EMMC_IMAGE_SIZE = 7634944
			KERNEL_PARTITION_OFFSET = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			ROOTFS_PARTITION_OFFSET = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SECOND_KERNEL_PARTITION_OFFSET = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			SECOND_ROOTFS_PARTITION_OFFSET = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			THIRD_KERNEL_PARTITION_OFFSET = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			THIRD_ROOTFS_PARTITION_OFFSET = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			FOURTH_KERNEL_PARTITION_OFFSET = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			FOURTH_ROOTFS_PARTITION_OFFSET = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			SWAP_PARTITION_OFFSET = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			EMMC_IMAGE = "%s/%s" % (self.WORKDIR, self.EMMCIMG)
			EMMC_IMAGE_SEEK = int(EMMC_IMAGE_SIZE) * 1024
			self.commandMB.append("dd if=/dev/zero of=%s bs=1 count=0 seek=%s" % (EMMC_IMAGE, EMMC_IMAGE_SEEK))
			self.commandMB.append("parted -s %s mklabel gpt" % EMMC_IMAGE)
			PARTED_END_BOOT = int(IMAGE_ROOTFS_ALIGNMENT) + int(BOOT_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart boot fat16 %s %s" % (EMMC_IMAGE, IMAGE_ROOTFS_ALIGNMENT, PARTED_END_BOOT))
			PARTED_END_KERNEL1 = int(KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart kernel1 %s %s" % (EMMC_IMAGE, KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL1))
			PARTED_END_ROOTFS1 = int(ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart rootfs1 ext4 %s %s" % (EMMC_IMAGE, ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS1))
			PARTED_END_KERNEL2 = int(SECOND_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart kernel2 %s %s" % (EMMC_IMAGE, SECOND_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL2))
			PARTED_END_ROOTFS2 = int(SECOND_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart rootfs2 ext4 %s %s" % (EMMC_IMAGE, SECOND_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS2))
			PARTED_END_KERNEL3 = int(THIRD_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart kernel3 %s %s" % (EMMC_IMAGE, THIRD_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL3))
			PARTED_END_ROOTFS3 = int(THIRD_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart rootfs3 ext4 %s %s" % (EMMC_IMAGE, THIRD_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS3))
			PARTED_END_KERNEL4 = int(FOURTH_KERNEL_PARTITION_OFFSET) + int(KERNEL_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart kernel4 %s %s" % (EMMC_IMAGE, FOURTH_KERNEL_PARTITION_OFFSET, PARTED_END_KERNEL4))
			PARTED_END_ROOTFS4 = int(FOURTH_ROOTFS_PARTITION_OFFSET) + int(ROOTFS_PARTITION_SIZE)
			self.commandMB.append("parted -s %s unit KiB mkpart rootfs4 ext4 %s %s" % (EMMC_IMAGE, FOURTH_ROOTFS_PARTITION_OFFSET, PARTED_END_ROOTFS4))

			BOOT_IMAGE_BS = int(IMAGE_ROOTFS_ALIGNMENT) * 1024
			self.commandMB.append("dd conv=notrunc if=%s of=%s seek=1 bs=%s" % (self.MTDBOOT, EMMC_IMAGE, BOOT_IMAGE_BS))
			KERNEL_IMAGE_BS = int(KERNEL_PARTITION_OFFSET) * 1024
			self.commandMB.append("dd conv=notrunc if=/dev/%s of=%s seek=1 bs=%s" % (self.MTDKERNEL, EMMC_IMAGE, KERNEL_IMAGE_BS))
			ROOTFS_IMAGE_BS = int(ROOTFS_PARTITION_OFFSET) * 1024
			self.commandMB.append("dd if=/dev/%s of=%s seek=1 bs=%s" % (self.MTDROOTFS, EMMC_IMAGE, ROOTFS_IMAGE_BS))
			self.ConsoleB.eBatch(self.commandMB, self.Stage3Complete, debug=False)

		elif self.EMMCIMG == "usb_update.bin":
			print("[ImageManager] Trio4K sf8008 bewonwiz: Making emmc_partitions.xml")
			with open("%s/emmc_partitions.xml" % self.WORKDIR, "w") as f:
				f.write('<?xml version="1.0" encoding="GB2312" ?>\n')
				f.write('<Partition_Info>\n')
				f.write('<Part Sel="1" PartitionName="fastboot" FlashType="emmc" FileSystem="none" Start="0" Length="1M" SelectFile="fastboot.bin"/>\n')
				f.write('<Part Sel="1" PartitionName="bootargs" FlashType="emmc" FileSystem="none" Start="1M" Length="1M" SelectFile="bootargs.bin"/>\n')
				f.write('<Part Sel="1" PartitionName="bootoptions" FlashType="emmc" FileSystem="none" Start="2M" Length="1M" SelectFile="boot.img"/>\n')
				f.write('<Part Sel="1" PartitionName="baseparam" FlashType="emmc" FileSystem="none" Start="3M" Length="3M" SelectFile="baseparam.img"/>\n')
				f.write('<Part Sel="1" PartitionName="pqparam" FlashType="emmc" FileSystem="none" Start="6M" Length="4M" SelectFile="pq_param.bin"/>\n')
				f.write('<Part Sel="1" PartitionName="logo" FlashType="emmc" FileSystem="none" Start="10M" Length="4M" SelectFile="logo.img"/>\n')
				f.write('<Part Sel="1" PartitionName="deviceinfo" FlashType="emmc" FileSystem="none" Start="14M" Length="4M" SelectFile="deviceinfo.bin"/>\n')
				f.write('<Part Sel="1" PartitionName="loader" FlashType="emmc" FileSystem="none" Start="26M" Length="32M" SelectFile="apploader.bin"/>\n')
				f.write('<Part Sel="1" PartitionName="kernel" FlashType="emmc" FileSystem="none" Start="66M" Length="32M" SelectFile="vmlinux.bin"/>\n')
				f.write('<Part Sel="1" PartitionName="rootfs" FlashType="emmc" FileSystem="ext3/4" Start="98M" Length="7000M" SelectFile="rootfs.ext4"/>\n')
				f.write('</Partition_Info>\n')

			print('[ImageManager] Trio4K sf8008: Executing', '/usr/bin/mkupdate -s 00000003-00000001-01010101 -f %s/emmc_partitions.xml -d %s/%s' % (self.WORKDIR, self.WORKDIR, self.EMMCIMG))
			self.commandMB.append('echo " "')
			self.commandMB.append('echo "Create: fastboot dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p1 of=%s/fastboot.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: bootargs dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p2 of=%s/bootargs.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: boot dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p3 of=%s/boot.img" % self.WORKDIR)
			self.commandMB.append('echo "Create: baseparam.dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p4 of=%s/baseparam.img" % self.WORKDIR)
			self.commandMB.append('echo "Create: pq_param dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p5 of=%s/pq_param.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: logo dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p6 of=%s/logo.img" % self.WORKDIR)
			self.commandMB.append('echo "Create: deviceinfo dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p7 of=%s/deviceinfo.bin" % self.WORKDIR)
			self.commandMB.append('echo "Create: apploader dump"')
			self.commandMB.append("dd if=/dev/mmcblk0p8 of=%s/apploader.bin" % self.WORKDIR)
			self.commandMB.append('echo "Pickup previous created: kernel dump"')
			self.commandMB.append('echo "Create: rootfs dump"')
			self.commandMB.append("dd if=/dev/zero of=%s/rootfs.ext4 seek=524288 count=0 bs=1024" % self.WORKDIR)
			self.commandMB.append("mkfs.ext4 -F -i 4096 %s/rootfs.ext4 -d %s/root" % (self.WORKDIR, self.TMPDIR))
			self.commandMB.append('echo " "')
			self.commandMB.append('echo "Create: Trio4K Sf8008 Bewonwiz Recovery Fullbackup %s"' % self.EMMCIMG)
			self.commandMB.append('echo " "')
			self.commandMB.append('/usr/sbin/mkupdate -s 00000003-00000001-01010101 -f %s/emmc_partitions.xml -d %s/%s' % (self.WORKDIR, self.WORKDIR, self.EMMCIMG))
			self.ConsoleB.eBatch(self.commandMB, self.Stage3Complete, debug=False)
		else:
			self.Stage3Completed = True
			print("[ImageManager] Stage3 bypassed: Complete.")

	def Stage3Complete(self, extra_args=None):
		self.Stage3Completed = True
		print("[ImageManager] Stage3: Complete.")

	def doBackup4(self):
		print("[ImageManager] Stage4: Unmounting and removing tmp system")
		if path.exists(self.TMPDIR + "/root") and path.ismount(self.TMPDIR + "/root"):
			self.command = "umount " + self.TMPDIR + "/root && rm -rf " + self.TMPDIR
			self.ConsoleB.ePopen(self.command, self.Stage4Complete)
		else:
			if path.exists(self.TMPDIR):
				rmtree(self.TMPDIR)
			self.Stage4Complete("pass", 0)

	def Stage4Complete(self, result, retval, extra_args=None):
		if retval == 0:
			self.Stage4Completed = True
			print("[ImageManager] Stage4: Complete.")

	def doBackup5(self):
		print("[ImageManager] Stage5: Moving from work to backup folders")
		if self.EMMCIMG == "emmc.img" or self.EMMCIMG == "disk.img" and path.exists("%s/%s" % (self.WORKDIR, self.EMMCIMG)):
			move("%s/%s" % (self.WORKDIR, self.EMMCIMG), "%s/%s" % (self.MAINDEST, self.EMMCIMG))

		if self.EMMCIMG == "usb_update.bin":
			move("%s/%s" % (self.WORKDIR, self.EMMCIMG), "%s/%s" % (self.MAINDEST2, self.EMMCIMG))
			system("cp -f /usr/share/fastboot.bin %s/fastboot.bin" % self.MAINDEST2)
			system("cp -f /usr/share/bootargs.bin %s/bootargs.bin" % self.MAINDEST2)
			if fileExists("/usr/share/apploader.bin"):
				system("cp -f /usr/share/apploader.bin %s/apploader.bin" % self.MAINDEST2)

		if "bin" or "uImage" in self.KERNELFILE and path.exists("%s/vmlinux.bin" % self.WORKDIR):
			move("%s/vmlinux.bin" % self.WORKDIR, "%s/%s" % (self.MAINDEST, self.KERNELFILE))
		else:
			move("%s/vmlinux.gz" % self.WORKDIR, "%s/%s" % (self.MAINDEST, self.KERNELFILE))
		self.h9root = False
		if SystemInfo["model"] in ("h9", "i55plus"):
			system("mv %s/fastboot.bin %s/fastboot.bin" % (self.WORKDIR, self.MAINDEST))
			system("mv %s/bootargs.bin %s/bootargs.bin" % (self.WORKDIR, self.MAINDEST))
			system("mv %s/pq_param.bin %s/pq_param.bin" % (self.WORKDIR, self.MAINDEST))
			system("mv %s/baseparam.bin %s/baseparam.bin" % (self.WORKDIR, self.MAINDEST))
			system("mv %s/logo.bin %s/logo.bin" % (self.WORKDIR, self.MAINDEST))
			system("cp -f /usr/share/fastboot.bin %s/fastboot.bin" % self.MAINDEST2)
			system("cp -f /usr/share/bootargs.bin %s/bootargs.bin" % self.MAINDEST2)
			with open("/proc/cmdline", "r") as z:
				if SystemInfo["HasMMC"] and "root=/dev/mmcblk0p1" in z.read():
					self.h9root = True
					move("%s/rootfs.tar.bz2" % self.WORKDIR, "%s/rootfs.tar.bz2" % self.MAINDEST)
				else:
					self.h9root = False
					move("%s/rootfs.%s" % (self.WORKDIR, self.ROOTFSTYPE), "%s/%s" % (self.MAINDEST, self.ROOTFSFILE))
		else:
			move("%s/rootfs.%s" % (self.WORKDIR, self.ROOTFSTYPE), "%s/%s" % (self.MAINDEST, self.ROOTFSFILE))

		if SystemInfo["model"] in ("gb7252", "gbx34k"):
			move("%s/%s" % (self.WORKDIR, self.GB4Kbin), "%s/%s" % (self.MAINDEST, self.GB4Kbin))
			move("%s/%s" % (self.WORKDIR, self.GB4Krescue), "%s/%s" % (self.MAINDEST, self.GB4Krescue))
			system("cp -f /usr/share/gpt.bin %s/gpt.bin" % self.MAINDEST)
			print("[ImageManager] Stage5: Create: gpt.bin:", self.MODEL)

		with open(self.MAINDEST + "/imageversion", "w") as fileout:
			line = defaultprefix + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-backup-" + SystemInfo["imageversion"] + "." + SystemInfo["imagebuild"] + "-" + self.BackupDate
			fileout.write(line)

		if SystemInfo["brand"] == "vuplus":
			if SystemInfo["model"] == "vuzero":
				with open(self.MAINDEST + "/force.update", "w") as fileout:
					line = "This file forces the update."
					fileout.write(line)
					fileout.close()
			else:
				with open(self.MAINDEST + "/reboot.update", "w") as fileout:
					line = "This file forces a reboot after the update."
					fileout.write(line)
		elif SystemInfo["brand"] in ("xtrend", "gigablue", "octagon", "odin", "xp", "ini"):
			if SystemInfo["brand"] in ("xtrend", "octagon", "odin", "ini"):
				with open(self.MAINDEST + "/noforce", "w") as fileout:
					line = "rename this file to 'force' to force an update without confirmation"
					fileout.write(line)
			if SystemInfo["HasHiSi"] and self.KERN == "mmc":
				with open(self.MAINDEST + "/SDAbackup", "w") as fileout:
					line = "SF8008 indicate type of backup %s" % self.KERN
					fileout.write(line)
				self.session.open(MessageBox, _("Multiboot only able to restore this backup to mmc slot1"), MessageBox.TYPE_INFO, timeout=20)
			if path.exists("/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/burn.bat"):
				copy("/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/burn.bat", self.MAINDESTROOT + "/burn.bat")
		elif SystemInfo["HasRootSubdir"]:
			with open(self.MAINDEST + "/force_%s_READ.ME" % self.MCBUILD, "w") as fileout:
				line1 = "Rename the unforce_%s.txt to force_%s.txt and move it to the root of your usb-stick" % (self.MCBUILD, self.MCBUILD)
				line2 = "When you enter the recovery menu then it will force the image to be installed in the linux selection"
				fileout.write(line1)
				fileout.write(line2)
			with open(self.MAINDEST2 + "/unforce_%s.txt" % self.MCBUILD, "w") as fileout:
				line1 = "rename this unforce_%s.txt to force_%s.txt to force an update without confirmation" % (self.MCBUILD, self.MCBUILD)
				fileout.write(line1)

		print("[ImageManager] Stage5: Removing Swap.")
		if path.exists(self.swapdevice + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup"):
			system("swapoff " + self.swapdevice + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup")
			remove(self.swapdevice + config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-" + SystemInfo["imagetype"] + "-swapfile_backup")
		if path.exists(self.WORKDIR):
			rmtree(self.WORKDIR)
		if (path.exists(self.MAINDEST + "/" + self.ROOTFSFILE) and path.exists(self.MAINDEST + "/" + self.KERNELFILE)) or (SystemInfo["model"] in ("h9", "i55plus") and self.h9root):
			for root, dirs, files in walk(self.MAINDEST):
				for momo in dirs:
					chmod(path.join(root, momo), 0o644)
				for momo in files:
					chmod(path.join(root, momo), 0o644)
			print("[ImageManager] Stage5: Image created in " + self.MAINDESTROOT)
			self.Stage5Complete()
		else:
			print("[ImageManager] Stage5: Image creation failed - e. g. wrong backup destination or no space left on backup device")
			self.BackupComplete()

	def Stage5Complete(self):
		self.Stage5Completed = True
		print("[ImageManager] Stage5: Complete.")

	def doBackup6(self):
		self.commands = []
		if SystemInfo["HasRootSubdir"]:
			self.commands.append("7za a -r -bt -bd %s/%s-%s-%s-%s-%s%s_mmc.zip %s/*" % (self.BackupDirectory, self.IMAGEDISTRO, self.DISTROVERSION, self.DISTROBUILD, self.MODEL, self.BackupDate, self.VuSlot0, self.MAINDESTROOT))
		else:
			self.commands.append("cd " + self.MAINDESTROOT + " && zip -r " + self.MAINDESTROOT + ".zip *")
		self.commands.append("rm -rf " + self.MAINDESTROOT)
		self.ConsoleB.eBatch(self.commands, self.Stage6Complete, debug=True)

	def Stage6Complete(self, answer=None):
		self.Stage6Completed = True
		print("[ImageManager] Stage6: Complete.")

	def BackupComplete(self, answer=None):
		#    trim the number of backups kept...
		import fnmatch
		try:
			if config.imagemanager.number_to_keep.value > 0 and path.exists(self.BackupDirectory):  # !?!
				images = listdir(self.BackupDirectory)
				patt = config.imagemanager.folderprefix.value + "-" + SystemInfo["machinebuild"] + "-*.zip"
				emlist = []
				for fil in images:
					if fnmatch.fnmatchcase(fil, patt):
						emlist.append(fil)
				# sort by oldest first...
				emlist.sort(key=lambda fil: path.getmtime(self.BackupDirectory + fil))
				# ...then, if we have too many, remove the <n> newest from the end
				# and delete what is left
				if len(emlist) > config.imagemanager.number_to_keep.value:
					emlist = emlist[0:len(emlist) - config.imagemanager.number_to_keep.value]
					for fil in emlist:
						remove(self.BackupDirectory + fil)
		except Exception:
			pass
		if config.imagemanager.schedule.value:
			atLeast = 60
			autoImageManagerTimer.backupupdate(atLeast)
		else:
			autoImageManagerTimer.backupstop()


class ImageManagerDownload(Screen):
	skin = ["""
	<screen name = "VIXImageManager"  position="center,center" size="%d,%d">
		<ePixmap pixmap="skin_default/buttons/red.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="%d,%d" size="%d,%d" alphatest="blend" scale="1"/>
		<widget name="key_red" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="%d,%d" zPosition="1" size="%d,%d" font="Regular;%d" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget name="lab1" position="%d,%d" size="%d,%d" font="Regular; %d" zPosition="2" transparent="0" halign="center"/>
		<widget name="list" position="%d,%d" size="%d,%d" font="Regular;%d" scrollbarMode="showOnDemand"/>
		<applet type="onLayoutFinish">
			self["list"].instance.setItemHeight(%d)
		</applet>
	</screen>""",
		560, 400,  # screen
		0, 0, 140, 40,  # colors
		140, 0, 140, 40,
		280, 0, 140, 40,
		420, 0, 140, 40,
		0, 0, 140, 40, 20,
		140, 0, 140, 40, 20,
		280, 0, 140, 40, 20,
		420, 0, 140, 40, 20,
		0, 50, 560, 50, 18,  # lab1
		10, 105, 540, 260, 20,  # list
		26,
			]  # noqa: E124

	def __init__(self, session, BackupDirectory, imagefeed):
		Screen.__init__(self, session)
		self.setTitle(_("%s downloads") % imagefeed[DISTRO])
		self.imagefeed = imagefeed
		self.BackupDirectory = BackupDirectory
		self["lab1"] = Label(_("Select an image to download for %s:") % SystemInfo["machinebuild"])
		self["key_red"] = Button(_("Close"))
		self["key_green"] = Button(_("Download"))
		self["ImageDown"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "KeyboardInputActions", "MenuActions"], {
			"cancel": self.close,
			"red": self.close,
			"green": self.keyDownload,
			"ok": self.keyDownload,
			"up": self.keyUp,
			"down": self.keyDown,
			"left": self.keyLeft,
			"right": self.keyRight,
			"upRepeated": self.keyUp,
			"downRepeated": self.keyDown,
			"leftRepeated": self.keyLeft,
			"rightRepeated": self.keyRight,
			"menu": self.close,
		}, -1)
		self.imagesList = {}
		self.setIndex = 0
		self.expanded = []
		self["list"] = ChoiceList(list=[ChoiceEntryComponent("", ((_("No images found on the selected download server...if password check validity")), "Waiter"))])
		self.getImageDistro()

	def showError(self):
		self.session.open(MessageBox, self.msg, MessageBox.TYPE_ERROR)
		self.close()

	def getImageDistro(self):
		if not path.exists(self.BackupDirectory):
			try:
				mkdir(self.BackupDirectory, 0o755)
			except Exception as err:
				self.msg = _("Error creating backup folder:\n%s: %s") % (type(err).__name__, err)
				print("[ImageManagerDownload][getImageDistro] " + self.msg)
				self.pausetimer = eTimer()
				self.pausetimer.callback.append(self.showError)
				self.pausetimer.start(50, True)
				return
		boxtype = SystemInfo["machinebuild"]
		if self.imagefeed[ACTION] == "HardwareInfo":
			boxtype = HardwareInfo().get_device_name()
			print("[ImageManager1] boxtype:%s" % (boxtype))
			if "dm800" in boxtype:
				boxtype = SystemInfo["machinebuild"]

		if not self.imagesList:
			# Legacy: self.imagefeed[URL] didn't contain "%s" where to insert the boxname.
			# So just tag the boxname onto the end of the url like it is a subfolder.
			# Obviously the url needs to exist.
			if "%s" not in self.imagefeed[URL] and "?" not in self.imagefeed[URL]:
				url = path.join(self.imagefeed[URL], boxtype)
			else:  # New style: self.imagefeed[URL] contains "%s" and boxname is inserted there.
				url = self.imagefeed[URL] % boxtype

			# special case for openvix developer downloads using user/pass
			if self.imagefeed[DISTRO].lower() == "openvix" \
				and self.imagefeed[URL].startswith("https") \
				and config.imagemanager.login_as_ViX_developer.value \
				and config.imagemanager.developer_username.value \
				and config.imagemanager.developer_username.value != config.imagemanager.developer_username.default \
				and config.imagemanager.developer_password.value \
				and config.imagemanager.developer_password.value != config.imagemanager.developer_password.default:
				url = path.join(url, config.imagemanager.developer_username.value, config.imagemanager.developer_password.value)
			try:
				self.imagesList = dict(json.load(urlopen(url)))
			except Exception:
				print("[ImageManager] no images available for: the '%s' at '%s'" % (boxtype, url))
				return

		if not self.imagesList:  # Nothing has been found on that server so we might as well give up.
			return

		imglist = []  # this is reset on every "ok" key press of an expandable item so it reflects the current state of expandability of that item
		for categorie in sorted(self.imagesList.keys(), reverse=True):
			if categorie in self.expanded:
				imglist.append(ChoiceEntryComponent("expanded", ((str(categorie)), "Expander")))
				for image in sorted(self.imagesList[categorie].keys(), reverse=True):
					imglist.append(ChoiceEntryComponent("verticalline", ((str(self.imagesList[categorie][image]["name"])), str(self.imagesList[categorie][image]["link"]))))
			else:
				# print("[ImageManager] [GetImageDistro] keys: %s" % list(self.imagesList[categorie].keys()))
				for image in list(self.imagesList[categorie].keys()):
					imglist.append(ChoiceEntryComponent("expandable", ((str(categorie)), "Expander")))
					break
		if imglist:
			# print("[ImageManager] [GetImageDistro] imglist: %s" % imglist)
			self["list"].setList(imglist)
			if self.setIndex:
				self["list"].moveToIndex(self.setIndex if self.setIndex < len(list) else len(list) - 1)
				if self["list"].getCurrent()[0][1] == "Expander":
					self.setIndex -= 1
					if self.setIndex:
						self["list"].moveToIndex(self.setIndex if self.setIndex < len(list) else len(list) - 1)
				self.setIndex = 0
			self.SelectionChanged()

	def SelectionChanged(self):
		currentSelected = self["list"].getCurrent()
		if currentSelected[0][1] == "Waiter":
			self["key_green"].setText("")
		else:
			if currentSelected[0][1] == "Expander":
				self["key_green"].setText(_("Compress") if currentSelected[0][0] in self.expanded else _("Expand"))
			else:
				self["key_green"].setText(_("Download"))

	def keyLeft(self):
		self["list"].pageUp()
		self.SelectionChanged()

	def keyRight(self):
		self["list"].pageDown()
		self.SelectionChanged()

	def keyUp(self):
		self["list"].moveUp()
		self.SelectionChanged()

	def keyDown(self):
		self["list"].moveDown()
		self.SelectionChanged()

	def keyDownload(self):
		currentSelected = self["list"].getCurrent()
		if currentSelected[0][1] == "Expander":
			if currentSelected[0][0] in self.expanded:
				self.expanded.remove(currentSelected[0][0])
			else:
				self.expanded.append(currentSelected[0][0])
			self.getImageDistro()

		elif currentSelected[0][1] != "Waiter":
			self.sel = currentSelected[0][0]
			if self.sel:
				message = _("Are you sure you want to download this image:\n ") + self.sel
				ybox = self.session.openWithCallback(self.doDownloadX, MessageBox, message, MessageBox.TYPE_YESNO)
				ybox.setTitle(_("Download confirmation"))
			else:
				self.close()

	def doDownloadX(self, answer):
		if answer:
			currentSelected = self["list"].getCurrent()
			selectedimage = currentSelected[0][0]
			headers, fileurl = self.processAuthLogin(currentSelected[0][1])
			fileloc = self.BackupDirectory + selectedimage
			Tools.CopyFiles.downloadFile(fileurl, fileloc, selectedimage.replace("_usb", ""), headers=headers)
			for job in Components.Task.job_manager.getPendingJobs():
				if job.name.startswith(_("Downloading")):
					break
			self.showJobView(job)
			self.close()

	def showJobView(self, job):
		Components.Task.job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable=False, backgroundable=True, afterEventChangeable=False, afterEvent="close")

	def JobViewCB(self, in_background):
		Components.Task.job_manager.in_background = in_background

	def processAuthLogin(self, url):
		headers = None
		parsed = urlparse(url)
		scheme = parsed.scheme
		username = parsed.username if parsed.username else ""
		password = parsed.password if parsed.password else ""
		hostname = parsed.hostname
		port = ":%s" % parsed.port if parsed.port else ""
		query = "?%s" % parsed.query if parsed.query else ""
		if username or password:
			import base64
			base64bytes = base64.b64encode(('%s:%s' % (username, password)).encode())
			headers = {("Authorization").encode(): ("Basic %s" % base64bytes.decode()).encode()}
		return headers, scheme + "://" + hostname + port + parsed.path + query


class ImageManagerSetup(Setup):
	def __init__(self, session):
		Setup.__init__(self, session=session, setup="viximagemanager", plugin="SystemPlugins/ViX")

	def keySave(self):
		if config.imagemanager.folderprefix.value == "":
			config.imagemanager.folderprefix.value = defaultprefix
		for configElement in (config.imagemanager.developer_username, config.imagemanager.developer_password):
			if not configElement.value:
				configElement.value = configElement.default
		self.check_URL_format(config.imagemanager.imagefeed_MyBuild)
		for x in self["config"].list:
			x[1].save()
		configfile.save()
		self.close()

	def check_URL_format(self, configElement):
		if configElement.value:
			configElement.value = "%s%s" % (not configElement.value.startswith(("http://", "https://", "ftp://")) and "http://" or "", configElement.value)
			configElement.value = configElement.value.strip("/")  # remove any trailing slash
		else:
			configElement.value = configElement.default
