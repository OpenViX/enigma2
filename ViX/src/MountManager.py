from boxbranding import getMachineBrand, getMachineName, getMachineBuild
from os import mkdir, path, remove, rename, statvfs, system 
import re
from time import sleep

from enigma import eTimer

from . import _

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ConfigList import ConfigListScreen
from Components.config import config, getConfigListEntry, ConfigSelection, NoSave
from Components.Console import Console
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import SystemInfo
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import SCOPE_ACTIVE_SKIN, resolveFilename

def getProcPartitions(List):
	list2 = []
	with open('/proc/partitions', 'r') as f:
		for line in f.readlines():
			parts = line.strip().split()
			if not parts:
				continue
			(devmajor, devminor, blocks, device) = parts
			# print '[MountManager1] device = %s devmajor = %s devminor = %s' %(device, devmajor, devminor)
			if devmajor == "major":
				continue
			if not re.search('8', devmajor) and not re.search('179', devmajor):					# look at disk & mmc(179)
				continue
			if  re.search('179', devmajor):  
				if not SystemInfo["HasSDnomount"]:								# only interested in h9/i55/h9combo(+dups) mmc partitions
					continue										# h9combo(+dups) uses mmcblk1p[0-3] include
				if SystemInfo["HasH9SD"]:
					if not re.search('mmcblk0p1', device):							# h9/i55 only mmcblk0p1 mmc partition
						continue	
					if SystemInfo["HasMMC"]:								# h9/i55 reject mmcblk0p1 mmc partition if root device
						continue
				if SystemInfo["HasSDnomount"][0] == 'Yes' and not re.search('mmcblk1p[0-3]', device):		# h9combo(+dups) uses mmcblk1p[0-3] include
					continue
			if re.search('8', devmajor):
				if not re.search('sd[a-z][1-9]', device):							# if storage use partitions only
					continue
				if SystemInfo["HasHiSi"] and path.exists("/dev/sda4") and re.search('sd[a][1-4]', device):	# sf8008 using SDcard for slots ---> exclude
					continue
			if device in list2:
				continue
			buildDeviceList(device, List)
			list2.append(device)

def buildDeviceList(device, List):
	if re.search('mmcblk[0-1]p[0-3]', device):
		device2 = re.sub('p[0-9]', '', device)
	else:
		device2 = re.sub('[0-9]', '', device)
	devicetype = path.realpath('/sys/block/' + device2 + '/device')

	# print '[MountManager1]MachineBuild: %s' %getMachineBuild()
	# print '[MountManager1]device: %s' %device
	# print '[MountManager1]device2: %s' %device2
	# print '[MountManager1]devicetype:%s' %devicetype
	# print '[MountManager1]Type:%s' %SystemInfo["MountManager"]

	name = _("HARD DISK: ")
	if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_hdd.png")):
		mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_hdd.png")
	else:
		mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_hdd.png'
	if path.exists('/sys/block/' + device2 + '/device/model'):
		model = file('/sys/block/' + device2 + '/device/model').read()
	elif path.exists('/sys/block/' + device2 + '/device/name'):
		model = file('/sys/block/' + device2 + '/device/name').read()
	model = str(model).replace('\n', '')

	if devicetype.find('usb') != -1:
		name = _('USB: ')
		if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_usb.png")):
			mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_usb.png")
		else:
			mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_usb.png'
	elif devicetype.find('mmc') != -1:
		name = _('SDCARD: ')
		if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_sd.png")):
			mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_sd.png")
		else:
			mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_sd.png'
	name += model
	description = ''
	mediamount = _("None")
	devicetype = _("unavailable")
	rw = _("None")

	with open('/proc/mounts', 'r') as f:
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				mediamount = parts[1]		# media mount e.g. /media/xxxxx
				devicetype = parts[2]		# device type e.g. ext4 
				rw = parts[3]			# read/write
				break

	if mediamount == _("None") or mediamount == None:
		description = _("Size: ") + _("unavailable")
	else:
		stat = statvfs(mediamount)
		cap = int(stat.f_blocks * stat.f_bsize)
		size = cap / 1000 / 1000
		if ((float(size) / 1024) / 1024) >= 1:
			description = _("Size: ") + str(round(((float(size) / 1024) / 1024), 2)) + _("TB")
		elif (size / 1024) >= 1:
			description = _("Size: ") + str(round((float(size) / 1024), 2)) + _("GB")
		elif size >= 1:
			description = _("Size: ") + str(size) + _("MB")
		else:
			description = _("Size: ") + _("unavailable")
	if description != '':
		if SystemInfo["MountManager"]:
			if rw.startswith('rw'):
				rw = ' R/W'
			elif rw.startswith('ro'):
				rw = ' R/O'
			else:
				rw = ""
			description += '\t' + _("Mount: ") + mediamount + '\n' + _("Device: ") + '/dev/' + device + '\t' + _("Type: ") + devicetype + rw
			png = LoadPixmap(mypixmap)
			res = (name, description, png)
		else:
			Gmedia=[('/media/' + device, '/media/' + device),
					   ('/media/hdd', '/media/hdd'),
					   ('/media/hdd2', '/media/hdd2'),
					   ('/media/hdd3', '/media/hdd3'),
					   ('/media/usb', '/media/usb'),
					   ('/media/usb2', '/media/usb2'),
					   ('/media/usb3', '/media/usb3'),
					   ('/media/sdcard', '/media/sdcard')]
			item = NoSave(ConfigSelection(default='/media/' + device, choices=Gmedia))
			if devicetype == 'Linux':
				devicetype = 'ext4'
			else:
				devicetype = 'auto'
			item.value = mediamount.strip()
			text = name + ' ' + description + ' /dev/' + device
			res = getConfigListEntry(text, item, device, devicetype)
		List.append(res)


class VIXDevicesPanel(Screen):
	skin = """
	<screen position="center,center" size="640,460">
		<ePixmap pixmap="skin_default/buttons/red.png" position="25,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="175,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="325,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="475,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="25,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="175,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="325,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="475,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget source="list" render="Listbox" position="10,50" size="620,450" scrollbarMode="showOnDemand">
			<convert type="TemplatedMultiContent">
				{"template": [
				 MultiContentEntryText(pos = (90,0), size = (600,30), font=0, text = 0),
				 MultiContentEntryText(pos = (110,30), size = (600,50), font=1, flags = RT_VALIGN_TOP, text = 1),
				 MultiContentEntryPixmapAlphaBlend(pos = (0,0), size = (80,80), png = 2),
				],
				"fonts": [gFont("Regular",24),gFont("Regular",20)],
				"itemHeight":85
				}
			</convert>
		</widget>
		<widget name="lab1" zPosition="2" position="50,90" size="600,40" font="Regular;22" halign="center" transparent="1"/>
	</screen>"""

	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		screentitle =  _("Mount manager")
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

		self['key_red'] = Label(" ")
		self['key_green'] = Label(_("Setup mounts"))
		self['key_yellow'] = Label(_("Un-mount"))
		self['key_blue'] = Label(_("Mount"))
		self['lab1'] = Label()
		self.onChangedEntry = []
		self.list = []
		self['list'] = List(self.list)
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', "MenuActions"], {'back': self.close, 'green': self.SetupMounts, 'red': self.saveMypoints, 'yellow': self.Unmount, 'blue': self.Mount, "menu": self.close})
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updateList2)
		self.updateList()

	def selectionChanged(self):
		if len(self.list) == 0:
			return
		sel = self['list'].getCurrent()
		seldev = sel
		for line in sel:
			try:
				line = line.strip()
				if line.find('Mount') >= 0:
					if line.find('/media/hdd') < 0:
						self["key_red"].setText(_("Use as HDD"))
				else:
					self["key_red"].setText(" ")
			except:
				pass
		name = description = ""
		if sel:
			try:
				name = str(sel[0])
				description = str(sel[1].replace('\t', '  '))
			except:
				pass
		for cb in self.onChangedEntry:
			cb(name, description)

	def updateList(self, result=None, retval=None, extra_args=None):
		scanning = _("Please wait while scanning for devices...")
		self['lab1'].setText(scanning)
		self.activityTimer.start(10)

	def updateList2(self):
		self.activityTimer.stop()
		self.list = []
		SystemInfo["MountManager"] = True
		getProcPartitions(self.list)
		self['list'].list = self.list
		self['lab1'].hide()

	def SetupMounts(self):
		self.session.openWithCallback(self.updateList, VIXDevicePanelConf, self.menu_path)

	def Mount(self):
		sel = self['list'].getCurrent()
		if sel:
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			mountp = parts[1].replace(_("Mount: "), '')
			device = parts[2].replace(_("Device: "), '')
			system('mount ' + device)
			with open('/proc/mounts', 'r') as f:
				for line in f.readlines():
					if line.find(device) == -1:
						self.session.open(MessageBox, _("Mount failed."), MessageBox.TYPE_INFO, timeout=5)
			self.updateList()

	def Unmount(self):
		sel = self['list'].getCurrent()
		if sel:
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			mountp = parts[1].replace(_("Mount: "), '')
			device = parts[2].replace(_("Device: "), '')
			system('umount ' + mountp)
			try:
				with open("/proc/mounts") as f: 
					for line in f.readlines():
						parts = line.strip().split(" ")
						if path.realpath(parts[0]).startswith(device):
							self.session.open(MessageBox, _("Can't un-mount the partition; make sure it is not being used for SWAP or record/timeshift paths."), MessageBox.TYPE_INFO)
			except IOError:
				return -1
			self.updateList()

	def saveMypoints(self):
		sel = self['list'].getCurrent()
		if sel:
			parts = sel[1].split()
			self.device = parts[5]
			self.mountp = parts[3]
			# print '[MountManager1]saveMypoints: device = %s, mountp=%s' %(self.device, self.mountp)
			self.Console.ePopen('umount ' + self.device)
			if self.mountp.find('/media/hdd') < 0:
				self.Console.ePopen('umount /media/hdd')
				self.Console.ePopen("/sbin/blkid | grep " + self.device, self.add_fstab, [self.device, self.mountp])
			else:
				self.session.open(MessageBox, _("This device is already mounted as HDD."), MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)

	def add_fstab(self, result=None, retval=None, extra_args=None):
		self.device = extra_args[0]
		self.mountp = extra_args[1]
		self.device_uuid = 'UUID=' + result.split('UUID=')[1].split(' ')[0].replace('"', '')
		# print '[MountManager1]add_fstab: device = %s, mountp=%s, UUID=%s' %(self.device, self.mountp, self.device_uuid)
		if not path.exists(self.mountp):
			mkdir(self.mountp, 0755)
		file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if '/media/hdd' not in l])
		rename('/etc/fstab.tmp', '/etc/fstab')
		file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device not in l])
		rename('/etc/fstab.tmp', '/etc/fstab')
		file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device_uuid not in l])
		rename('/etc/fstab.tmp', '/etc/fstab')
		with open('/etc/fstab', 'a') as out:
			line = self.device_uuid + '\t/media/hdd\tauto\tdefaults\t0 0\n'
			out.write(line)
		self.Console.ePopen('mount -a', self.updateList)

class VIXDevicePanelConf(Screen, ConfigListScreen):
	skin = """
	<screen position="center,center" size="640,460">
		<ePixmap pixmap="skin_default/buttons/red.png" position="25,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="175,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="25,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="175,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="config" position="30,60" size="580,275" scrollbarMode="showOnDemand"/>
		<widget name="Linconn" position="30,375" size="580,20" font="Regular;18" halign="center" valign="center" backgroundColor="#9f1313"/>
	</screen>"""

	def __init__(self, session, menu_path):
		Screen.__init__(self, session)
		self.list = []
		ConfigListScreen.__init__(self, self.list)
		screentitle =  _("Choose where to mount your devices to:")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self['key_green'] = Label(_("Save"))
		self['key_red'] = Label(_("Cancel"))
		self['Linconn'] = Label()
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'green': self.saveMypoints, 'red': self.close, 'back': self.close})
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updateList2)
		self.updateList()

	def updateList(self, result=None, retval=None, extra_args=None):
		scanning = _("Please wait while scanning your %s %s devices...") % (getMachineBrand(), getMachineName())
		self['Linconn'].setText(scanning)
		self.activityTimer.start(10)

	def updateList2(self):
		self.activityTimer.stop()
		self.list = []
		list2 = []
		SystemInfo["MountManager"] = False
		getProcPartitions(self.list)
		self['config'].list = self.list
		self['config'].l.setList(self.list)
		self['Linconn'].hide()

	def saveMypoints(self):
		mycheck = False
		for x in self['config'].list:
			self.device = x[2]
			self.mountp = x[1].value
			self.type = x[3]
			self.Console.ePopen('umount ' + self.device)
			self.Console.ePopen("/sbin/blkid | grep " + self.device + " && opkg list-installed ntfs-3g", self.add_fstab, [self.device, self.mountp])
		message = _("Updating mount locations...")
		ybox = self.session.openWithCallback(self.delay, MessageBox, message, type=MessageBox.TYPE_INFO, timeout=5, enable_input=False)
		ybox.setTitle(_("Please wait."))

	def delay(self, val):
		message = _("The changes need a system restart to take effect.\nRestart your %s %s now?") % (getMachineBrand(), getMachineName())
		ybox = self.session.openWithCallback(self.restartBox, MessageBox, message, MessageBox.TYPE_YESNO)
		ybox.setTitle(_("Restart %s %s.") % (getMachineBrand(), getMachineName()))

	def add_fstab(self, result=None, retval=None, extra_args=None):
		# print '[MountManager] RESULT:', result
		if result:
			self.device = extra_args[0]
			self.mountp = extra_args[1]
			self.device_uuid = 'UUID=' + result.split('UUID=')[1].split(' ')[0].replace('"', '')
			self.device_type = result.split('TYPE=')[1].split(' ')[0].replace('"', '')

			if self.device_type.startswith('ext'):
				self.device_type = 'auto'
			elif self.device_type.startswith('ntfs') and result.find('ntfs-3g') != -1:
				self.device_type = 'ntfs-3g'
			elif self.device_type.startswith('ntfs') and result.find('ntfs-3g') == -1:
				self.device_type = 'ntfs'

			if not path.exists(self.mountp):
				mkdir(self.mountp, 0755)
			file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device not in l])
			rename('/etc/fstab.tmp', '/etc/fstab')
			file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device_uuid not in l])
			rename('/etc/fstab.tmp', '/etc/fstab')
			with open('/etc/fstab', 'a') as out:
				line = self.device_uuid + '\t' + self.mountp + '\t' + self.device_type + '\tdefaults\t0 0\n'
				out.write(line)

	def restartBox(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.close()

class VIXDevicesPanelSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["entry"] = StaticText("")
		self["desc"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.selectionChanged()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, name, desc):
		self["entry"].text = name
		self["desc"].text = desc
