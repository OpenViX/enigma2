from __future__ import print_function
import six

from datetime import datetime
import glob
import shutil
import subprocess
import tempfile

from os import mkdir, path, rmdir, rename, remove, sep, stat

from boxbranding import getMachineBuild, getMachineMtdRoot
from Components.Console import Console
from Components.SystemInfo import SystemInfo
from Tools.BoxConfig import BoxConfig


class tmp:
	dir = None


def getMBbootdevice():
	tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
	for device in ("/dev/block/by-name/bootoptions", "/dev/mmcblk0p1", "/dev/mmcblk1p1", "/dev/mmcblk0p3", "/dev/mmcblk0p4"):
		if path.exists(device):
			Console().ePopen("mount %s %s" % (device, tmp.dir))
			if path.isfile(path.join(tmp.dir, "STARTUP")):
				# print("[Multiboot] [getMBbootdevices] Bootdevice found: %s" % device)
				return device
			Console().ePopen("umount %s" % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)


def getparam(line, param):
	return line.replace("userdataroot", "rootuserdata").rsplit("%s=" % param, 1)[1].split(" ", 1)[0]


def getMultibootslots():
	bootslots = {}
	slotname = ""
	BoxInfo = SystemInfo["BoxInfo"]
	tmp.dir = tempfile.TemporaryDirectory(prefix="Multiboot")
	tmpname = tmp.dir.name 
	for device in ("/dev/mmcblk0p1", "/dev/mmcblk1p1", "/dev/mmcblk0p3", "/dev/mmcblk0p4", "/dev/block/by-name/bootoptions" ):
		if bootslots and device == "/dev/block/by-name/bootoptions":
			continue 
		if path.exists(device):
			Console().ePopen("mount %s %s" % (device, tmpname))
			if path.isfile(path.join(tmpname, "STARTUP")):
				SystemInfo["MBbootdevice"] = device
				device2 = device.rsplit("/", 1)[1]
				print("[Multiboot] [getMBbootdevices] Bootdevice found: %s" % device2)				
				BoxInfo.setItem("mtdbootfs", device2)
				for file in glob.glob(path.join(tmpname, "STARTUP_*")):
					# print("[multiboot*****] [getMultibootslots0] tmpname = %s" % (tmpname))
					if "STARTUP_RECOVERY" in file:
						SystemInfo["RecoveryMode"] = True
						print("[multiboot] [getMultibootslots] RecoveryMode is set to:%s" % SystemInfo["RecoveryMode"])
					# print("[multiboot] [getMultibootslots0] file = %s" % (file))
					slotnumber = file.rsplit("_", 3 if "BOXMODE" in file else 1)[1][0]
					slotname = file.rsplit("_", 3 if "BOXMODE" in file else 1)[0]
					slotname = file.rsplit("/", 1)[1]
					slotname = slotname if len(slotname) > 1 else ""
					# print("[multiboot] [getMultibootslots3] slot = %s file = %s" % (slotnumber, slotname))
					if slotnumber.isdigit() and slotnumber not in bootslots:
						slot = {}
						for line in open(file).readlines():
							# print("Multiboot getMultibootslots readlines = %s " % line)
							if "root=" in line:
								line = line.rstrip("\n")
								root = getparam(line, "root")
								if path.exists(root):
									slot["root"] = root
									slot["startupfile"] = path.basename(file)
									slot["slotname"] = slotname
									if "rootsubdir" in line:
										SystemInfo["HasRootSubdir"] = True
										# print("[multiboot] [getMultibootslots] HasRootSubdir is set to:%s" % SystemInfo["HasRootSubdir"])
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
			(print("[multiboot] [getMultibootslots] Finished bootslots = %s" % bootslots))
			Console().ePopen("umount %s" % tmpname)
	tmp.dir.cleanup()
	if bootslots:	
		print("[Multiboot] Bootslots found:", bootslots)
	return bootslots


def GetCurrentImage():
	if SystemInfo["canMultiBoot"]:
		slot = [x[-1] for x in open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read().split() if x.startswith("rootsubdir")]
		if slot:
			return int(slot[0])
		else:
			root = getparam(open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read(), "root")
			for slot in list(SystemInfo["canMultiBoot"].keys()):
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
	tmp.dir = tempfile.TemporaryDirectory(prefix="GetImagelist")
	tmpname = tmp.dir.name 
	# print("[multiboot] [GetImagelist] tmpname = %s" % (tmpname))	
	for slot in sorted(list(SystemInfo["canMultiBoot"].keys())):
		BuildVersion = "  "
		Build = " "  # ViX Build No.
		Dev = " "  # ViX Dev No.
		Creator = " "  # Openpli Openvix Openatv etc
		Date = " "
		BuildType = " "  # release etc
		Imagelist[slot] = {"imagename": _("Empty slot")}
		imagedir = "/"	
		if SystemInfo["MultiBootSlot"] != slot or SystemInfo["HasHiSi"]:
			Console().ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmpname))		
			imagedir = sep.join([_f for _f in [tmpname, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
		print("[multiboot] [GetImagelist] isfile = %s" % (path.join(imagedir, "usr/bin/enigma2")))			
		if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
			# print("[multiboot] [GetImagelist] Slot = %s imagedir = %s" % (slot, imagedir))		
			if path.isfile(path.join(imagedir, "usr/lib/enigma.info")):
				BoxInfo = BoxConfig(root=imagedir) if SystemInfo["MultiBootSlot"] != slot else SystemInfo["BoxInfo"]
				Creator = BoxInfo.getItem("distro").title()
				BuildImgVersion = BoxInfo.getItem("imgversion")
				BuildType = BoxInfo.getItem("imagetype")[0:3]
				BuildVer = BoxInfo.getItem("imagebuild")												
				BuildDate = str(BoxInfo.getItem("compiledate"))
				BuildDate = datetime.strptime(BuildDate, '%Y%m%d').strftime("%Y-%m-%d")
				BuildDev = str(BoxInfo.getItem("imagedevbuild")).zfill(3) if BuildType != "rel" else ""
				BuildVersion = "%s %s %s %s %s %s" % (Creator, BuildImgVersion, BuildType, BuildVer, BuildDev, BuildDate)
				print("[multiboot] [BoxInfo]  slot=%s, Creator=%s, BuildType=%s, BuildImgVersion=%s, BuildDate=%s, BuildDev=%s" % (slot, Creator, BuildType, BuildImgVersion, BuildDate, BuildDev))
			else:				
				#	print("[multiboot] [GetImagelist] 2 slot = %s imagedir = %s" % (slot, imagedir))
				Creator = open("%s/etc/issue" % imagedir).readlines()[-2].capitalize().strip()[:-6]
				#	print("[multiboot] [GetImagelist] Creator = %s imagedir = %s" % (Creator, imagedir))
				if Creator.startswith("Openvix"):
					reader = boxbranding_reader(imagedir)
					# print("[multiboot] [GetImagelist]1 slot = %s imagedir = %s" % (slot, imagedir))
					if path.isfile(path.join(imagedir, "usr/lib/enigma2/python/ImageIdentifier.py")):
						print("[multiboot] [GetImagelist]2 slot = %s imagedir = %s" % (slot, imagedir))
						reader = readImageIdentifier(imagedir)
					BuildType = reader.getImageType()
					Build = reader.getImageBuild()
					Creator = Creator.replace("-release", " rel")
					# print("[multiboot] [GetImagelist] Slot = %s Creator = %s BuildType = %s Build = %s" % (slot, Creator, BuildType, Build))
					Dev = BuildType != "release" and " %s" % reader.getImageDevBuild() or ""
					date = VerDate(imagedir)
					BuildVersion = "%s %s %s %s %s" % (Creator, BuildType[0:3], Build, Dev, date)
					print("[BootInfo] slot = %s BuildVersion = %s" % (slot, BuildVersion))
				else:
					date = VerDate(imagedir)
					Creator = Creator.replace("-release", " ")
					BuildVersion = "%s Image Date: %s" % (Creator, date)
			Imagelist[slot] = {"imagename": "%s" % BuildVersion}
		elif path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			Imagelist[slot] = {"imagename": _("Deleted image")}
		if SystemInfo["MultiBootSlot"] != slot:			
			Console().ePopen("umount %s" % tmpname)
	tmp.dir.cleanup()
	return Imagelist


def VerDate(imagedir):
	try:
		date = datetime.fromtimestamp(stat(path.join(imagedir, "var/lib/opkg/status")).st_mtime).strftime("%Y-%m-%d")
		if date.startswith("1970"):
			date = datetime.fromtimestamp(stat(path.join(imagedir, "usr/share/bootlogo.mvi")).st_mtime).strftime("%Y-%m-%d")
		date = max(date, datetime.fromtimestamp(stat(path.join(imagedir, "usr/bin/enigma2")).st_mtime).strftime("%Y-%m-%d"))
		print("[multiboot] date = %s" % date)
	except Exception:
		date = _("Unknown")
	return date


def emptySlot(slot):
	tmp.dir = tempfile.TemporaryDirectory(prefix="emptySlot")
	tmpname = tmp.dir.name 
	Console().ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmpname))
	imagedir = sep.join([_f for _f in [tmpname, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
	if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
		rename((path.join(imagedir, "usr/bin/enigma2")), (path.join(imagedir, "usr/bin/enigmax")))
		ret = 0
	else:
		print("[multiboot2] NO enigma2 found to rename")
		ret = 4
	Console().ePopen("umount %s" % tmpname)
	tmp.dir.cleanup()
	return ret


def restoreSlots():
	for slot in SystemInfo["canMultiBoot"]:
		tmp.dir = tempfile.TemporaryDirectory(prefix="restoreSlot")
		tmpname = tmp.dir.name 	
		Console().ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmpname))
		imagedir = sep.join([_f for _f in [tmpname, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
		if path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			rename((path.join(imagedir, "usr/bin/enigmax")), (path.join(imagedir, "usr/bin/enigma2")))
		Console().ePopen("umount %s" % tmpname)
	tmp.dir.cleanup()

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
			for att in list(self.output.keys()):
				self.output[att] = output[att]
			# print("[readBrandingFile1] self.output = %s" % self.output)

	def addBrandingMethods(self):  # This creates reader.getBoxType(), reader.getImageDevBuild(), etc
		loc = {}
		for att in list(self.output.keys()):
			exec("def %s(self): return self.output[\"%s\"]" % (att, att), None, loc)
		for name, value in list(loc.items()):
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
		for att in list(self.output.keys()):
			out.append("\t\t\"%s\": boxbranding.%s()," % (att, att))
		out.append("\t}")
		out.append("except Exception:")
		out.append("\t\toutput = None")
		out.append("print(output)")
		out.append("")
		return "\n".join(out)


class readImageIdentifier():

	#
	# typical use...
	#
	# from readImageIdentifier import readImageIdentifier
	# reader = readImageIdentifier()
	# boxtype = reader.getBoxType()
	#

	def __init__(self, OsPath=None):
		if OsPath is None:
			OsPath = ""

		if path.exists("%s/usr/lib64" % OsPath):
			self.filepath = "%s/usr/lib64/enigma2/python/" % OsPath
		else:
			self.filepath = "%s/usr/lib/enigma2/python/" % OsPath
		self.filename = "ImageIdentifier.py"

		self.methods = {
			"getBoxType": "",
			"getImageDistro": "",
			"getImageVersion": "",
			"getImageBuild": "",
			"getImageDevBuild": "",
			"getImageType": "",
			"getMachineBrand": "",
			"getImageBuildDate": "",
		}

		self.__getfile()
		self.__readfile()

	def __getfile(self):
		self.file_content = ""
		try:
			self.file_content = open("%s%s" % (self.filepath, self.filename)).read()
			# print("[readImageIdentifier][self.file_content] %s" % (self.file_content))
		except:
			print("[readImageIdentifier][getfile] Could not read %s%s" % (self.filepath, self.filename))

	def __readfile(self):
		try:
			exec(self.file_content)
		except Exception as e:
			print("[readImageIdentifier][readfile] failed to exec")
			print(e)

		for key in list(self.methods.keys()):
			try:
				exec("global m;m = %s()" % (key,))
				self.methods[key] = m
			except Exception as e:
				print("[readImageIdentifier][readfile] failed to exec %s" % (key,))

	def getBoxType(self):
		return self.methods["getBoxType"]

	def getImageDistro(self):
		return self.methods["getImageDistro"]

	def getImageVersion(self):
		return self.methods["getImageVersion"]

	def getImageBuild(self):
		return self.methods["getImageBuild"]

	def getImageDevBuild(self):
		return self.methods["getImageDevBuild"]

	def getImageType(self):
		return self.methods["getImageType"]

	def getMachineBrand(self):
		return self.methods["getMachineBrand"]

	def getImageBuildDate(self):
		return self.methods["getImageBuildDate"]
