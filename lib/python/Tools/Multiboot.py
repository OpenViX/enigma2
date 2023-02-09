from datetime import datetime
import glob
import shutil
import subprocess
import tempfile
from os import mkdir, path, rmdir, rename, remove, sep, stat

from boxbranding import getMachineBuild, getMachineMtdRoot
from Components.Console import Console
from Components.SystemInfo import SystemInfo, BoxInfo as BoxInfoRunningInstance, BoxInformation
from Tools.Directories import fileHas, fileExists

MbootList1 = ("/dev/mmcblk0p1", "/dev/mmcblk1p1", "/dev/mmcblk0p3", "/dev/mmcblk0p4", "/dev/mtdblock2", "/dev/block/by-name/bootoptions")
MbootList2 = ("/dev/%s" % getMachineMtdRoot(), )	# kexec kernel Vu+ multiboot

class tmp:
	dir = None

def getMultibootslots():
	bootslots = {}
	slotname = ""
	SystemInfo["MultiBootSlot"] = False	
	BoxInfo = BoxInfoRunningInstance
	tmp.dir = tempfile.mkdtemp(prefix="getMultibootslots")
	tmpname = tmp.dir
	MbootList = MbootList2 if fileHas("/proc/cmdline", "kexec=1") else MbootList1
	for device in MbootList:
		print("[multiboot*****][getMultibootslots]00 device, bootslots", device, "   ", bootslots)
		if len(bootslots) != 0:
			break
#		print("[multiboot*****][getMultibootslots]0 device = ", device)
		if path.exists(device):
			Console(binary=True).ePopen("mount %s %s" % (device, tmpname))
			if path.isfile(path.join(tmpname, "STARTUP")):
				SystemInfo["MBbootdevice"] = device
				device2 = device.rsplit("/", 1)[1]
				print("[Multiboot][[getMultibootslots]1 Bootdevice found: %s" % device2)
				BoxInfo.setItem("mtdbootfs", device2, forceOverride=True)
				for file in glob.glob(path.join(tmpname, "STARTUP_*")):
#					print("[multiboot*****] [getMultibootslots]2 tmpname = %s" % (tmpname))
					if "STARTUP_ANDROID" in file:
						SystemInfo["AndroidMode"] = True
					if "STARTUP_RECOVERY" in file:
						SystemInfo["RecoveryMode"] = True
#						print("[multiboot] [getMultibootslots]3 RecoveryMode is set to:%s" % SystemInfo["RecoveryMode"])
#					print("[multiboot] [getMultibootslots]4 file = ", file)
					slotnumber = file.rsplit("_", 3 if "BOXMODE" in file else 1)[1]
					slotname = file.rsplit("_", 3 if "BOXMODE" in file else 1)[0]
					slotname = file.rsplit("/", 1)[1]
					slotname = slotname if len(slotname) > 1 else ""
					slotname = ""	# nullify for current moment
#					print("[multiboot] [getMultibootslots3] slot = %s file = %s" % (slotnumber, slotname))
					if slotnumber.isdigit() and slotnumber not in bootslots:
						if fileHas("/proc/cmdline", "kexec=1") and int(slotnumber) > 3:
							SystemInfo["HasKexecUSB"] = True
						line = open(file).read().replace("'", "").replace('"', "").replace("\n", " ").replace("ubi.mtd", "mtd").replace("bootargs=", "")						
#						print("[Multiboot][getMultibootslots]6 readlines = %s " % line)
						slot = dict([(x.split("=", 1)[0].strip(), x.split("=", 1)[1].strip()) for x in line.strip().split(" ") if "=" in x])
						print("[Multiboot][getMultibootslots]6a slot", slot)
						if 	"UUID=" in slot["root"]:
							slotx = getUUIDtoSD(slot["root"])
							print("[Multiboot][getMultibootslots]6a slotx slot['root']", slotx, slot["root"])
							if slotx is not None:
								slot["root"] = slotx
							slot["kernel"] = "/linuxrootfs%s/zImage" %slotnumber
						if path.exists(slot["root"]) or slot["root"] == "ubi0:ubifs":
							slot["startupfile"] = path.basename(file)
							slot["slotname"] = slotname
							SystemInfo["HasMultibootMTD"] = slot.get("mtd")
							if not fileHas("/proc/cmdline", "kexec=1") and "sda" in slot["root"]:		# Not Kexec Vu+ receiver -- sf8008 type receiver with sd card, reset value as SD card slot has no rootsubdir
								slot["rootsubdir"] = None
							else:
								SystemInfo["HasRootSubdir"] = slot.get("rootsubdir")
																		 
							if "kernel" not in slot.keys():
								slot["kernel"] = "%sp%s" % (slot["root"].split("p")[0], int(slot["root"].split("p")[1]) - 1)	# oldstyle MB kernel = root-1								
#							print("[multiboot] [getMultibootslots]7a HasMultibootMTD, kernel, root, SystemInfo['HasRootSubdir'] ", SystemInfo["HasMultibootMTD"], "   ", slot["kernel"], "   ", slot["root"], "   ", SystemInfo["HasRootSubdir"])
						else:
							continue
						bootslots[int(slotnumber)] = slot
#			print("[multiboot] [getMultibootslots] Finished bootslots = %s" % bootslots)
			Console(binary=True).ePopen("umount %s" % tmpname)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	if bootslots:
#		print("[Multiboot] Bootslots found:", bootslots)
		bootArgs = open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read()
		print("[Multiboot][MultiBootSlot] bootArgs:", bootArgs)
		if fileHas("/proc/cmdline", "kexec=1") and SystemInfo["HasRootSubdir"]:							# Kexec Vu+ receiver
			slot = [x[-1] for x in bootArgs.split() if x.startswith("rootsubdir")]
			SystemInfo["MultiBootSlot"] = int(slot[0])
			print("[Multiboot][MultiBootSlot]0 current slot used:", SystemInfo["MultiBootSlot"])				
		elif SystemInfo["HasRootSubdir"] and "root=/dev/sda" not in bootArgs:							# RootSubdir receiver or sf8008 receiver with root in eMMC slot 
			slot = [x[-1] for x in bootArgs.split() if x.startswith("rootsubdir")]
			SystemInfo["MultiBootSlot"] = int(slot[0])
			print("[Multiboot][MultiBootSlot]1 current slot used:", SystemInfo["MultiBootSlot"])			
		else:
			root = dict([(x.split("=", 1)[0].strip(), x.split("=", 1)[1].strip()) for x in bootArgs.strip().split(" ") if "=" in x])["root"]	# Broadband receiver (e.g. gbue4k) or sf8008 with sd card as root/kernel pair
			for slot in bootslots.keys():
				if bootslots[slot]["root"] == root:
					SystemInfo["MultiBootSlot"] = slot
					print("[Multiboot][MultiBootSlot]2 current slot used:", SystemInfo["MultiBootSlot"])
	return bootslots

def getUUIDtoSD(UUID): # returns None on failure
#	print("[multiboot][getUUIDtoSD2] UUID = ", UUID)
	check = "/sbin/blkid"
	if fileExists(check):
		lines = subprocess.check_output([check]).decode(encoding="utf8", errors="ignore").split("\n")
		for line in lines:
#			print("[Multiboot][getUUIDtoSD2] line", line)
			if UUID in line.replace('"', ''):
				return line.split(":")[0].strip()
	else:
		return None

def GetCurrentImageMode():
	return bool(SystemInfo["canMultiBoot"]) and SystemInfo["canMode12"] and int(open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read().replace("\0", "").split("=")[-1])


def GetImagelist():
	Imagelist = {}
	tmp.dir = tempfile.mkdtemp(prefix="GetImagelist")
	tmpname = tmp.dir
#	print("[multiboot] [GetImagelist] tmpname = %s" % (tmpname))
	for slot in sorted(list(SystemInfo["canMultiBoot"].keys())):
		BuildVersion = "  "
		Build = " "  # ViX Build No.
		Dev = " "  # ViX Dev No.
		Creator = " "  # Openpli Openvix Openatv etc
		Date = " "
		BuildType = " "  # release etc
		Imagelist[slot] = {"imagename": _("Empty slot")}
		imagedir = "/"
		if SystemInfo["MultiBootSlot"] != slot or SystemInfo["HasHiSi"] or fileHas("/proc/cmdline", "kexec=1"):
			if SystemInfo["HasMultibootMTD"]:
				Console(binary=True).ePopen("mount -t ubifs %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmpname))
			else:
				Console(binary=True).ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmpname))
			imagedir = sep.join([_f for _f in [tmpname, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
#		print("[multiboot] [GetImagelist]0 isfile = %s" % (path.join(imagedir, "usr/bin/enigma2")))
		if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
#			print("[multiboot] [GetImagelist]1 Slot = %s imagedir = %s" % (slot, imagedir))
			if path.isfile(path.join(imagedir, "usr/lib/enigma.info")):
#				print("[multiboot] [BoxInfo] using BoxInfo")
				BoxInfo = BoxInformation(root=imagedir) if SystemInfo["MultiBootSlot"] != slot else BoxInfoRunningInstance
				Creator = BoxInfo.getItem("distro")
				BuildImgVersion = BoxInfo.getItem("imgversion")
				BuildType = BoxInfo.getItem("imagetype")[0:3]
				BuildVer = BoxInfo.getItem("imagebuild")
				BuildDate = str(BoxInfo.getItem("compiledate"))
				BuildDate = datetime.strptime(BuildDate, '%Y%m%d').strftime("%Y-%m-%d")
				BuildDev = str(BoxInfo.getItem("imagedevbuild")).zfill(3) if BuildType != "rel" else ""
				BuildVersion = "%s %s %s %s %s %s" % (Creator, BuildImgVersion, BuildType, BuildVer, BuildDev, BuildDate)
#				print("[multiboot] [BoxInfo]  slot=%s, Creator=%s, BuildType=%s, BuildImgVersion=%s, BuildDate=%s, BuildDev=%s" % (slot, Creator, BuildType, BuildImgVersion, BuildDate, BuildDev))
			else:
#				print("[multiboot] [BoxInfo] using BoxBranding")
#				print("[multiboot] [GetImagelist] 2 slot = %s imagedir = %s" % (slot, imagedir))
				Creator = open("%s/etc/issue" % imagedir).readlines()[-2].capitalize().strip()[:-6]
#				print("[multiboot] [GetImagelist] Creator = %s imagedir = %s" % (Creator, imagedir))
				if Creator.startswith("Openvix"):
					reader = boxbranding_reader(imagedir)
					BuildType = reader.getImageType()
					Build = reader.getImageBuild()
					Creator = Creator.replace("-release", " rel")
#					print("[multiboot] [GetImagelist]5 Slot = %s Creator = %s BuildType = %s Build = %s" % (slot, Creator, BuildType, Build))
					Dev = BuildType != "release" and " %s" % reader.getImageDevBuild() or ""
					date = VerDate(imagedir)
					BuildVersion = "%s %s %s %s %s" % (Creator, BuildType[0:3], Build, Dev, date)
#					print("[BootInfo]6 slot = %s BuildVersion = %s" % (slot, BuildVersion))
				else:
					date = VerDate(imagedir)
					Creator = Creator.replace("-release", " ")
					BuildVersion = "%s Image Date: %s" % (Creator, date)
			Imagelist[slot] = {"imagename": "%s" % BuildVersion}
		elif path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			Imagelist[slot] = {"imagename": _("Deleted image")}
		else:
			Imagelist[slot] = {"imagename": _("Empty slot")}
		if SystemInfo["MultiBootSlot"] != slot:
			Console(binary=True).ePopen("umount %s" % tmpname)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	return Imagelist


def VerDate(imagedir):
	try:
		date = datetime.fromtimestamp(stat(path.join(imagedir, "var/lib/opkg/status")).st_mtime).strftime("%Y-%m-%d")
		if date.startswith("1970"):
			date = datetime.fromtimestamp(stat(path.join(imagedir, "usr/share/bootlogo.mvi")).st_mtime).strftime("%Y-%m-%d")
		date = max(date, datetime.fromtimestamp(stat(path.join(imagedir, "usr/bin/enigma2")).st_mtime).strftime("%Y-%m-%d"))
#		print("[multiboot] date = %s" % date)
	except Exception:
		date = _("Unknown")
	return date


def emptySlot(slot):
	tmp.dir = tempfile.mkdtemp(prefix="emptySlot")
	if SystemInfo["HasMultibootMTD"]:
		Console(binary=True).ePopen("mount -t ubifs %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmp.dir))
	else:
		Console(binary=True).ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmp.dir))
	imagedir = sep.join([_f for _f in [tmp.dir, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
	if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
		rename((path.join(imagedir, "usr/bin/enigma2")), (path.join(imagedir, "usr/bin/enigmax")))
		ret = 0
	else:
		print("[multiboot2] NO enigma2 found to rename")
		ret = 4
	Console(binary=True).ePopen("umount %s" % tmp.dir)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	return ret


def restoreSlots():
	for slot in SystemInfo["canMultiBoot"]:
		tmp.dir = tempfile.mkdtemp(prefix="restoreSlot")
		if SystemInfo["HasMultibootMTD"]:
			Console(binary=True).ePopen("mount -t ubifs %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmp.dir))
		else:
			Console(binary=True).ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmp.dir))
		imagedir = sep.join([_f for _f in [tmp.dir, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
		if path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			rename((path.join(imagedir, "usr/bin/enigmax")), (path.join(imagedir, "usr/bin/enigma2")))
		Console(binary=True).ePopen("umount %s" % tmp.dir)
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
