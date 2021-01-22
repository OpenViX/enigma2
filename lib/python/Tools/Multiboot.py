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
	if SystemInfo["MBbootdevice"]:
		for file in glob.glob(path.join(tmp.dir, "STARTUP_*")):
			if "STARTUP_RECOVERY" in file:
				SystemInfo["RecoveryMode"] = True
				# print("[multiboot] [getMultibootslots] RecoveryMode is set to:%s" % SystemInfo["RecoveryMode"])
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
		# print("[multiboot] [getMultibootslots] Finished bootslots = %s" %bootslots)
		Console().ePopen("umount %s" % tmp.dir)
		if not path.ismount(tmp.dir):
			rmdir(tmp.dir)
	# print("[Multiboot] Bootslots found:", bootslots)
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
	tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
	for slot in sorted(list(SystemInfo["canMultiBoot"].keys())):
		Console().ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmp.dir))
		BuildVersion = "  "
		Build = " "  # ViX Build No.
		Dev = " "  # ViX Dev No.
		Creator = " "  # Openpli Openvix Openatv etc
		Date = " "
		BuildType = " "  # release etc
		Imagelist[slot] = {"imagename": _("Empty slot")}
		imagedir = sep.join([_f for _f in [tmp.dir, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
		if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
			#	print("[multiboot] [GetImagelist] 2 slot = %s imagedir = %s" % (slot, imagedir))
			Creator = open("%s/etc/issue" % imagedir).readlines()[-2].capitalize().strip()[:-6]
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
			else:
				date = VerDate(imagedir)
				Creator = Creator.replace("-release", " ")
				BuildVersion = "%s Image Date: %s" % (Creator, date)
			Imagelist[slot] = {"imagename": "%s" % BuildVersion}
		elif path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			Imagelist[slot] = { "imagename": _("Deleted image") }
		Console().ePopen("umount %s" % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	return Imagelist

def VerDate(imagedir):
	try:
		from datetime import datetime
		date = datetime.fromtimestamp(stat(path.join(imagedir, "var/lib/opkg/status")).st_mtime).strftime("%Y-%m-%d")
		if date.startswith("1970"):
			date = datetime.fromtimestamp(stat(path.join(imagedir, "usr/share/bootlogo.mvi")).st_mtime).strftime("%Y-%m-%d")
		date = max(date, datetime.fromtimestamp(stat(path.join(imagedir, "usr/bin/enigma2")).st_mtime).strftime("%Y-%m-%d"))
		print("[multiboot] date = %s" % date)
	except Exception:
		date = _("Unknown")
	return date

def emptySlot(slot):
	tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
	Console().ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmp.dir))
	imagedir = sep.join([_f for _f in [tmp.dir, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
	if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
		rename((path.join(imagedir, "usr/bin/enigma2")), (path.join(imagedir, "usr/bin/enigmax")))
		ret = 0
	else:
		print("[multiboot2] NO enigma2 found to rename")
		ret = 4
	Console().ePopen("umount %s" % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	return	ret

def restoreSlots():
	for slot in SystemInfo["canMultiBoot"]:
		tmp.dir = tempfile.mkdtemp(prefix="Multiboot")
		Console().ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmp.dir))
		imagedir = sep.join([_f for _f in [tmp.dir, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
		if path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			rename((path.join(imagedir, "usr/bin/enigmax")), (path.join(imagedir, "usr/bin/enigma2")))
		Console().ePopen("umount %s" % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)

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

	def __init__(self, OsPath = None):
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
			print("[readImageIdentifier][self.file_content] %s" % (self.file_content))
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

	

# just for testing
#if __name__ == "__main__":
#	filepath = "" # path to image folder
#	reader = readImageIdentifier(filepath)
#	print("reader.getBoxType() %s" % (reader.getBoxType(),))#
