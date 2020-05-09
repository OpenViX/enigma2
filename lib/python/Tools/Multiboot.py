import glob
import shutil
import subprocess
import tempfile

from os import mkdir, path, rmdir, rename, remove, sep, stat

from boxbranding import getMachineBuild, getMachineMtdRoot
from Components.Console import Console
from Components.SystemInfo import SystemInfo

class tmp:
	dir = None

def getMBbootdevice():
	tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
	for device in ('/dev/block/by-name/bootoptions', '/dev/mmcblk0p1', '/dev/mmcblk1p1', '/dev/mmcblk0p3', '/dev/mmcblk0p4'):
		if path.exists(device):
			Console().ePopen("mount %s %s" % (device, tmp.dir))
			if path.isfile(path.join(tmp.dir, "STARTUP")):
				print "[Multiboot] [getMBbootdevices] Bootdevice found: %s" % device
				return device
			Console().ePopen('umount %s' % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)

def getparam(line, param):
	return line.rsplit("%s=" % param, 1)[1].split(" ", 1)[0]

def getMultibootslots():
	bootslots = {}
	if SystemInfo["MBbootdevice"]:
		for file in glob.glob(path.join(tmp.dir, "STARTUP_*")):
			if "STARTUP_RECOVERY" in file:
				SystemInfo["RecoveryMode"] = True
				print "[multiboot] [getMultibootslots] RecoveryMode is set to:%s" % SystemInfo["RecoveryMode"]
			slotnumber = file.rsplit("_", 3 if "BOXMODE" in file else 1)[1]
			if slotnumber.isdigit() and slotnumber not in bootslots:
				slot = {}
				for line in open(file).readlines():
					# print "Multiboot getMultibootslots readlines = %s " %line
					if "root=" in line:
						line = line.rstrip("\n")
						root = getparam(line, "root")
						if path.exists(root):
							slot["root"] = root
							slot["startupfile"] = path.basename(file)
							if "rootsubdir" in line:
								SystemInfo["HasRootSubdir"] = True
								print "[multiboot] [getMultibootslots] HasRootSubdir is set to:%s" % SystemInfo["HasRootSubdir"]
								slot["rootsubdir"] = getparam(line, "rootsubdir")
								slot["kernel"] = getparam(line, "kernel")
							elif "sda" in line:
								slot["kernel"] = getparam(line, "kernel")	# sf8008 SD card slot pairs same as oldsystle MB
								slot["rootsubdir"] = None
							else:
								slot["kernel"] = "%sp%s" % (root.split("p")[0], int(root.split("p")[1]) - 1)	# oldstyle MB kernel = root-1
						break
				if slot:
					bootslots[int(slotnumber)] = slot
		print "[multiboot] [getMultibootslots] Finished bootslots = %s" %bootslots
		Console().ePopen("umount %s" % tmp.dir)
		if not path.ismount(tmp.dir):
			rmdir(tmp.dir)
	print '[Multiboot] Bootslots found:', bootslots
	return bootslots

def GetCurrentImage():
	if SystemInfo["canMultiBoot"]:
		slot = [x[-1] for x in open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read().split() if x.startswith("rootsubdir")]
		if slot:
			return int(slot[0])
		else:
			root = getparam(open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read(), "root")
			for slot in SystemInfo["canMultiBoot"].keys():
				if SystemInfo["canMultiBoot"][slot]["root"] == root:
					return slot
def GetCurrentKern():
	if SystemInfo["HasRootSubdir"]:
		return SystemInfo["HasRootSubdir"] and (int(open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read()[:-1].split("kernel=/dev/mmcblk0p")[1].split(" ")[0]))

def GetCurrentRoot():
	if SystemInfo["HasRootSubdir"]:
		return SystemInfo["HasRootSubdir"] and (int(open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read()[:-1].split("root=/dev/mmcblk0p")[1].split(" ")[0]))

def GetCurrentImageMode():
	return bool(SystemInfo["canMultiBoot"]) and SystemInfo["canMode12"] and int(open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read().replace("\0", "").split("=")[-1])

def GetImagelist():
	Imagelist = {}
	tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
	for slot in sorted(SystemInfo["canMultiBoot"].keys()):
		Console().ePopen('mount %s %s' % (SystemInfo["canMultiBoot"][slot]['root'], tmp.dir))
		BuildVersion = "  "
		Build = " "  # ViX Build No.
		Dev = " "  # ViX Dev No.
		Creator = " "  # Openpli Openvix Openatv etc
		Date = " "
		BuildType = " "  # release etc
		Imagelist[slot] = {"imagename": _("Empty slot")}
		imagedir = sep.join(filter(None, [tmp.dir, SystemInfo["canMultiBoot"][slot].get('rootsubdir', '')]))
		if path.isfile(path.join(imagedir, 'usr/bin/enigma2')):
		# print "[multiboot] [GetImagelist] 2 slot = %s imagedir = %s" % (slot, imagedir)
			Creator = open("%s/etc/issue" % imagedir).readlines()[-2].capitalize().strip()[:-6].replace("-release", " rel")
			if Creator.startswith("Openvix"):
				reader = boxbranding_reader(imagedir)
				BuildType = reader.getImageType()
				Build = reader.getImageBuild()
				Dev = BuildType != "release" and " %s" % reader.getImageDevBuild() or ""
				BuildVersion = "%s %s %s %s" % (Creator, BuildType[0:3], Build, Dev)
			else:
				try:
					from datetime import datetime
					date = datetime.fromtimestamp(stat(path.join(imagedir, "var/lib/opkg/status")).st_mtime).strftime("%Y-%m-%d")
					if date.startswith("1970"):
						date = datetime.fromtimestamp(stat(path.join(imagedir, "usr/share/bootlogo.mvi")).st_mtime).strftime("%Y-%m-%d")
					date = max(date, datetime.fromtimestamp(stat(path.join(imagedir, "usr/bin/enigma2")).st_mtime).strftime("%Y-%m-%d"))
				except Exception:
					date = _("Unknown")
				BuildVersion = "%s Image Date: %s" % (Creator, date)
			Imagelist[slot] = {"imagename": "%s" % BuildVersion}
		Console().ePopen('umount %s' % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	return Imagelist


def EmptySlot(slot):
	tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
	Console().ePopen('mount %s %s' % (SystemInfo["canMultiBoot"][slot]['root'], tmp.dir))
	imagedir = sep.join(filter(None, [tmp.dir, SystemInfo["canMultiBoot"][slot].get('rootsubdir', '')]))
	if path.isfile(path.join(imagedir, 'usr/bin/enigma2')):
		rename((path.join(imagedir, 'usr/bin/enigma2')), (path.join(imagedir, 'usr/bin/enigmax')))
		ret = 0
	else:
		print "[multiboot2] NO enigma2 found to rename"
		ret = 4
	Console().ePopen('umount %s' % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	return	ret

def RestoreSlots(slot):
	for slot in SystemInfo["canMultiBoot"]:
		tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
		Console().ePopen('mount %s %s' % (SystemInfo["canMultiBoot"][slot]['root'], tmp.dir))
		imagedir = sep.join(filter(None, [tmp.dir, SystemInfo["canMultiBoot"][self.slot].get('rootsubdir', '')]))
		if path.isfile(path.join(imagedir, 'usr/bin/enigmax')):
			rename((path.join(imagedir, 'usr/bin/enigmax')), (path.join(imagedir, 'usr/bin/enigma2')))
		Console().ePopen('umount %s' % tmp.dir)
	if not os.path.ismount(tmp.dir):
		os.rmdir(tmp.dir)

class boxbranding_reader:  # Many thanks to Huevos for creating this reader - well beyond my skill levels!
	def __init__(self, OsPath):
		if path.exists("%s/usr/lib64" % OsPath):
			self.branding_path = "%s/usr/lib64/enigma2/python/" % OsPath
		else:
			self.branding_path = "%s/usr/lib/enigma2/python/" % OsPath
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

	def readBrandingFile(self):  # Reads boxbranding.so and updates self.output
		output = eval(subprocess.check_output(["python", path.join(self.tmp_path, self.helper_file)]))
		if output:
			for att in self.output.keys():
				self.output[att] = output[att]

	def addBrandingMethods(self):  # This creates reader.getBoxType(), reader.getImageDevBuild(), etc
		loc = {}
		for att in self.output.keys():
			exec("def %s(self): return self.output[\"%s\"]" % (att, att), None, loc)
		for name, value in loc.items():
			setattr(boxbranding_reader, name, value)

	def createHelperFile(self):
		f = open(path.join(self.tmp_path, self.helper_file), "w+")
		f.write(self.helperFileContent())
		f.close()

	def copyBrandingFile(self):
		shutil.copy2(path.join(self.branding_path, self.branding_file), path.join(self.tmp_path, self.branding_file))

	def removeHelperFile(self):
		self.removeFile(path.join(self.tmp_path, self.helper_file))

	def removeBrandingFile(self):
		self.removeFile(path.join(self.tmp_path, self.branding_file))

	def removeFile(self, toRemove):
		if path.isfile(toRemove):
			remove(toRemove)

	def helperFileContent(self):
		out = []
		out.append("try:")
		out.append("\timport boxbranding")
		out.append("\toutput = {")
		for att in self.output.keys():
			out.append("\t\t\"%s\": boxbranding.%s()," % (att, att))
		out.append("\t}")
		out.append("except Exception:")
		out.append("\t\toutput = None")
		out.append("print output")
		out.append("")
		return "\n".join(out)


class EmptySlot():
	MOUNT = 0
	UNMOUNT = 1

	def __init__(self, Contents, callback):
		self.callback = callback
		self.container = Console()
		self.slot = Contents
		self.tmp_mount = tempfile.mkdtemp(prefix="Multiboot")
		self.phase = self.MOUNT
		self.run()

	def run(self):
		self.container.ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][self.slot]["root"], self.tmp_mount), self.appClosed)

	def appClosed(self, data, retval, extra_args):
		if retval == 0:
			imagedir = sep.join(filter(None, [self.tmp_mount, SystemInfo["canMultiBoot"][self.slot].get('rootsubdir', '')]))
			if path.isfile(path.join(imagedir, 'usr/bin/enigma2')):
				rename((path.join(imagedir, 'usr/bin/enigma2')), (path.join(imagedir, 'usr/bin/enigmax')))
			else:
				print "[multiboot2] NO enigma2 found to rename"
			self.kill()
		else:
			self.kill()

	def kill(self):
			self.container.killAll()
			if not path.ismount(self.tmp_mount):
				rmdir(self.tmp_mount)
			self.callback()
=======
def getCurrentImageMode():
	return bool(SystemInfo["canMultiBoot"]) and SystemInfo["canMode12"] and int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read().replace('\0', '').split('=')[-1])

def deleteImage(slot):
	tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
	Console().ePopen('mount %s %s' % (SystemInfo["canMultiBoot"][slot]['device'], tmp.dir))
	enigma2binaryfile = os.path.join(os.sep.join(filter(None, [tmp.dir, SystemInfo["canMultiBoot"][slot].get('rootsubdir', '')])), 'usr/bin/enigma2')
	os.rename(enigma2binaryfile, '%s.bak' % enigma2binaryfile)
	Console().ePopen('umount %s' % tmp.dir)
	if not os.path.ismount(tmp.dir):
		os.rmdir(tmp.dir)

def restoreImages():
	for slot in SystemInfo["canMultiBoot"]:
		tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
		Console().ePopen('mount %s %s' % (SystemInfo["canMultiBoot"][slot]['device'], tmp.dir))
		enigma2binaryfile = os.path.join(os.sep.join(filter(None, [tmp.dir, SystemInfo["canMultiBoot"][slot].get('rootsubdir', '')])), 'usr/bin/enigma2')
		if not os.path.exists(enigma2binaryfile) and os.path.exists('%s.bak' % enigma2binaryfile):
			os.rename('%s.bak' % enigma2binaryfile, enigma2binaryfile)
		Console().ePopen('umount %s' % tmp.dir)
		if not os.path.ismount(tmp.dir):
			os.rmdir(tmp.dir)

def getImagelist():
	imagelist = {}
	if SystemInfo["canMultiBoot"]:
		tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
		for slot in sorted(SystemInfo["canMultiBoot"].keys()):
			Console().ePopen('mount %s %s' % (SystemInfo["canMultiBoot"][slot]['device'], tmp.dir))
			imagedir = os.sep.join(filter(None, [tmp.dir, SystemInfo["canMultiBoot"][slot].get('rootsubdir', '')]))
			if os.path.isfile(os.path.join(imagedir, 'usr/bin/enigma2')):
				try:
					from datetime import datetime
					date = datetime.fromtimestamp(os.stat(os.path.join(imagedir, "var/lib/opkg/status")).st_mtime).strftime('%Y-%m-%d')
					if date.startswith("1970"):
						date = datetime.fromtimestamp(os.stat(os.path.join(imagedir, "usr/share/bootlogo.mvi")).st_mtime).strftime('%Y-%m-%d')
					date = max(date, datetime.fromtimestamp(os.stat(os.path.join(imagedir, "usr/bin/enigma2")).st_mtime).strftime('%Y-%m-%d'))
				except:
					date = _("Unknown")
				imagelist[slot] = { 'imagename': "%s (%s)" % (open(os.path.join(imagedir, "etc/issue")).readlines()[-2].capitalize().strip()[:-6], date) }
			else:
				imagelist[slot] = { 'imagename': _("Empty slot") }
			Console().ePopen('umount %s' % tmp.dir)
		if not os.path.ismount(tmp.dir):
			os.rmdir(tmp.dir)
	return imagelist
>>>>>>> 84d3c4fa7f... Multiboot: Symplify some code
