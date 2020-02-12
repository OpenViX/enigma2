from boxbranding import getMachineMtdRoot, getMachineBuild
from Components.Console import Console
from Components.SystemInfo import SystemInfo
from Tools.Directories import pathExists
from os import mkdir, path, rmdir, rename, remove, sep, stat
import glob
import shutil
import subprocess

#		#default layout for 				Zgemma H7/Mut@nt HD51						 Giga4K						SF8008/trio4K
# boot								/dev/mmcblk0p1						/dev/mmcblk0p1				/dev/mmcblk0p3
# STARTUP_1 			Image 1: boot emmcflash0.kernel1 'root=/dev/mmcblk0p3 rw rootwait'	boot emmcflash0.kernel1: 'root=/dev/mmcblk0p5		boot emmcflash0.kernel 'root=/dev/mmcblk0p13 
# STARTUP_2 			Image 2: boot emmcflash0.kernel2 'root=/dev/mmcblk0p5 rw rootwait'      boot emmcflash0.kernel2: 'root=/dev/mmcblk0p7		boot usb0.sda1 'root=/dev/sda2
# STARTUP_3		        Image 3: boot emmcflash0.kernel3 'root=/dev/mmcblk0p7 rw rootwait'	boot emmcflash0.kernel3: 'root=/dev/mmcblk0p9		boot usb0.sda3 'root=/dev/sda4
# STARTUP_4		        Image 4: boot emmcflash0.kernel4 'root=/dev/mmcblk0p9 rw rootwait'	NOT IN USE due to Rescue mode in mmcblk0p3		NOT IN USE due to only 4 partitions on SDcard

Imagemount = '/tmp/multibootcheck'

def getMBbootdevice():
	if not path.isdir(Imagemount):
		mkdir(Imagemount)
	for device in ('/dev/block/by-name/bootoptions', '/dev/mmcblk0p1', '/dev/mmcblk1p1', '/dev/mmcblk0p3', '/dev/mmcblk0p4'):
		if path.exists(device):
			Console().ePopen('mount %s %s' % (device, Imagemount))
			if path.isfile(path.join(Imagemount, "STARTUP")):
				return device
			Console().ePopen('umount %s' % Imagemount)
	if not path.ismount(Imagemount):
		rmdir(Imagemount)

def getparam(line, param):
	return line.rsplit('%s=' % param, 1)[1].split(' ', 1)[0]

def getMultibootslots():
	bootslots = {}
	if SystemInfo["MBbootdevice"]:
		if not path.isdir(Imagemount):
			mkdir(Imagemount)
		Console().ePopen('/bin/mount %s %s' % (SystemInfo["MBbootdevice"], Imagemount))
		for file in glob.glob(path.join(Imagemount, 'STARTUP_*')):
			slotnumber = file.rsplit('_', 3 if 'BOXMODE' in file else 1)[1]
			if slotnumber.isdigit() and slotnumber not in bootslots:
				slot = {}
				for line in open(file).readlines():
					if 'root=' in line:
						line = line.rstrip('\n')
						device = getparam(line, 'root')
						if path.exists(device):
							slot['device'] = device
							slot['startupfile'] = path.basename(file)
							if 'rootsubdir' in line:
								slot['rootsubdir'] = getparam(line, 'rootsubdir')
								slot['kernel'] = getparam(line, 'kernel')
							if "sda" in line:
								slot['kernel'] = "/dev/sda%s" %line.split('sda', 1)[1].split(' ', 1)[0]
							else:
								slot['kernel'] = "%sp%s" %(device.split("p")[0], int(device.split("p")[1])-1)
								
						break
				if slot:
					bootslots[int(slotnumber)] = slot
		Console().ePopen('umount %s' % Imagemount)
		if not path.ismount(Imagemount):
			rmdir(Imagemount)
	return bootslots

def GetCurrentImage():
	if SystemInfo["canMultiBoot"]:
		slot = [x[-1] for x in open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read().split() if x.startswith('rootsubdir')]
		if slot:
			return int(slot[0])
		else:
			device = getparam(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read(), 'root')
			for slot in SystemInfo["canMultiBoot"].keys():
				if SystemInfo["canMultiBoot"][slot]['device'] == device:
					return slot
def GetCurrentKern():
	if SystemInfo["HasRootSubdir"]:
		return SystemInfo["HasRootSubdir"] and (int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read()[:-1].split("kernel=/dev/mmcblk0p")[1].split(' ')[0]))

def GetCurrentRoot():
	if SystemInfo["HasRootSubdir"]:
		return SystemInfo["HasRootSubdir"] and (int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read()[:-1].split("root=/dev/mmcblk0p")[1].split(' ')[0]))

def GetCurrentImageMode():
	return bool(SystemInfo["canMultiBoot"]) and SystemInfo["canMode12"] and int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read().replace('\0', '').split('=')[-1])

class GetImagelist():
	MOUNT = 0
	UNMOUNT = 1

	def __init__(self, callback):
		if SystemInfo["canMultiBoot"]:
			self.slots = sorted(SystemInfo["canMultiBoot"].keys())
			self.callback = callback
			self.imagelist = {}
			if not path.isdir(Imagemount):
				mkdir(Imagemount)
			self.container = Console()
			self.phase = self.MOUNT
			self.run()
		else:
			callback({})

	def run(self):
		if self.phase == self.UNMOUNT:
			self.container.ePopen('umount %s' % Imagemount, self.appClosed)
		else:
			self.slot = self.slots.pop(0)
			self.container.ePopen('mount %s %s' % (SystemInfo["canMultiBoot"][self.slot]['device'], Imagemount), self.appClosed)

	def appClosed(self, data="", retval=0, extra_args=None):
		BuildVersion = "  "	
		Build = " "	#ViX Build No.#
		Dev = " "	#ViX Dev No.#
		Creator = " " 	#Openpli Openvix Openatv etc #
		Date = " "	
		BuildType = " "	#release etc #
		if retval:
			self.imagelist[self.slot] = { 'imagename': _("Empty slot") }
		if retval == 0 and self.phase == self.MOUNT:
			if SystemInfo["HasRootSubdir"]:
				imagedir = ('%s/%s' %(Imagemount, SystemInfo["canMultiBoot"][self.slot]['rootsubdir']))
			else:
				imagedir = Imagemount
			if path.isfile('%s/usr/bin/enigma2' %imagedir):
				Creator = open("%s/etc/issue" %imagedir).readlines()[-2].capitalize().strip()[:-6].replace("-release", " rel")
				if Creator.startswith("Openvix"):
					reader = boxbranding_reader(imagedir)
					BuildType = reader.getImageType()
					Build = reader.getImageBuild()
					Dev = BuildType != "release" and " %s" % reader.getImageDevBuild() or ''
					BuildVersion = "%s %s %s %s" % (Creator, BuildType[0:3], Build, Dev)
				else:
					try:
						from datetime import datetime
						date = datetime.fromtimestamp(stat(path.join(imagedir, "var/lib/opkg/status")).st_mtime).strftime('%Y-%m-%d')
						if date.startswith("1970"):
							date = datetime.fromtimestamp(stat(path.join(imagedir, "usr/share/bootlogo.mvi")).st_mtime).strftime('%Y-%m-%d')
						date = max(date, datetime.fromtimestamp(stat(path.join(imagedir, "usr/bin/enigma2")).st_mtime).strftime('%Y-%m-%d'))
					except:
						date = _("Unknown")
					BuildVersion = "%s (%s)" % (open(path.join(imagedir, "etc/issue")).readlines()[-2].capitalize().strip()[:-6], date)
				self.imagelist[self.slot] =  { 'imagename': '%s' %BuildVersion }
			else:
				self.imagelist[self.slot] = { 'imagename': _("Empty slot") }
			if self.slots and SystemInfo["canMultiBoot"][self.slot]['device'] == SystemInfo["canMultiBoot"][self.slots[0]]['device']:
				self.slot = self.slots.pop(0)
				self.appClosed()
			else:
				self.phase = self.UNMOUNT
				self.run()
		elif self.slots:
			self.phase = self.MOUNT
			self.run()
		else:
			self.container.killAll()
			if not path.ismount(Imagemount):
				rmdir(Imagemount)
			self.callback(self.imagelist)


class boxbranding_reader:		# many thanks to Huevos for creating this reader - well beyond my skill levels! 
	def __init__(self, OsPath):
		if pathExists('%s/usr/lib64' %OsPath):
			self.branding_path = "%s/usr/lib64/enigma2/python/" %OsPath
		else:
			self.branding_path = "%s/usr/lib/enigma2/python/" %OsPath
		self.branding_file = "boxbranding.so"
		self.tmp_path = "/tmp/"
		self.helper_file = "helper.py"

		self.output = {
			"getMachineBuild": "",
			"getMachineProcModel": "",
			"getMachineBrand": "",
			"getMachineName": "",
			"getMachineMtdKernel": "",
			"getMachineKernelFile": "",
			"getMachineMtdRoot": "",
			"getMachineRootFile": "",
			"getMachineMKUBIFS": "",
			"getMachineUBINIZE": "",
			"getBoxType": "",
			"getBrandOEM": "",
			"getOEVersion": "",
			"getDriverDate": "",
			"getImageVersion": "",
			"getImageBuild": "",
			"getImageDistro": "",
			"getImageFolder": "",
			"getImageFileSystem": "",
			"getImageDevBuild": "",
			"getImageType": "",
			"getMachineMake": "",
			"getImageArch": "",
			"getFeedsUrl": "",
		}
		self.createHelperFile()
		self.copyBrandingFile()
		self.readBrandingFile()
		self.removeHelperFile()
		self.removeBrandingFile()
		self.addBrandingMethods()

	def readBrandingFile(self): # reads boxbranding.so and updates self.output
		output = eval(subprocess.check_output(['python', self.tmp_path + self.helper_file]))
		if output:
			for att in self.output.keys():
				self.output[att] = output[att]

	def addBrandingMethods(self): # this creates reader.getBoxType(), reader.getImageDevBuild(), etc
		l =  {}                
		for att in self.output.keys():
			exec("def %s(self): return self.output['%s']" % (att, att), None, l)
		for name, value in l.items():
			setattr(boxbranding_reader, name, value)

	def createHelperFile(self):
		f = open(self.tmp_path + self.helper_file, "w+")
		f.write(self.helperFileContent())
		f.close()

	def copyBrandingFile(self):
		shutil.copy2(self.branding_path + self.branding_file, self.tmp_path + self.branding_file)

	def removeHelperFile(self):
		self.removeFile(self.tmp_path + self.helper_file)

	def removeBrandingFile(self):
		self.removeFile(self.tmp_path + self.branding_file)

	def removeFile(self, toRemove):
			if path.isfile(toRemove):
				remove(toRemove)

	def helperFileContent(self):
		eol = "\n"
		out = []
		out.append("try:%s" % eol)
		out.append("\timport boxbranding%s" % eol)
		out.append("\toutput = {%s" % eol)
		for att in self.output.keys():
			out.append('\t\t"%s": boxbranding.%s(),%s' % (att, att, eol))
		out.append("\t}%s" % eol)
		out.append("except:%s" % eol)
		out.append("\t\toutput = None%s" % eol)
		out.append("print output%s" % eol)
		return ''.join(out)


class EmptySlot():
	MOUNT = 0
	UNMOUNT = 1
	def __init__(self, Contents, callback):
		self.callback = callback
		self.container = Console()
		self.slot = Contents
		if not path.isdir('/tmp/testmount'):
			mkdir('/tmp/testmount')
		self.phase = self.MOUNT
		self.run()

	def run(self):
		if SystemInfo["HasRootSubdir"]:
			self.container.ePopen('mount /dev/block/by-name/userdata /tmp/testmount' if self.phase == self.MOUNT else 'umount /tmp/testmount', self.appClosed)
		else:
			self.container.ePopen('mount %s /tmp/testmount' %(SystemInfo["canMultiBoot"][self.slot]['device']) if self.phase == self.MOUNT else 'umount /tmp/testmount', self.appClosed)

	
	def appClosed(self, data, retval, extra_args):
		if retval == 0 and self.phase == self.MOUNT:
			if SystemInfo["HasRootSubdir"]:
				rootsub = SystemInfo["canMultiBoot"][self.slot]['rootsubdir']
				if path.isfile("/tmp/testmount/%s/usr/bin/enigma2" %rootsub):
					rename('/tmp/testmount/%s/usr/bin/enigma2' %rootsub, '/tmp/testmount/%s/usr/bin/enigmax.bin' %rootsub)
			elif path.isfile("/tmp/testmount/usr/bin/enigma2"):
					rename('/tmp/testmount/usr/bin/enigma2', '/tmp/testmount/usr/bin/enigmax.bin')
			else:
				print "[multiboot2] NO enigma2 found to rename"
			self.phase = self.UNMOUNT
			self.run()
		else:
			self.container.killAll()
			if not path.ismount('/tmp/testmount'):
				rmdir('/tmp/testmount')
			self.callback()
