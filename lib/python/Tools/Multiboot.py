from datetime import datetime
import glob
import subprocess
import tempfile
from os import path, rmdir, rename, sep, stat

from Components.Console import Console
from Components.SystemInfo import SystemInfo, BoxInfo as BoxInfoRunningInstance, BoxInformation
from Tools.Directories import fileHas, fileExists

if fileHas("/proc/cmdline", "kexec=1"):
	from PIL import Image
	from PIL import ImageDraw
	from PIL import ImageFont

MbootList1 = ("/dev/mmcblk0p1", "/dev/mmcblk1p1", "/dev/mmcblk0p3", "/dev/mmcblk0p4", "/dev/mtdblock2", "/dev/block/by-name/bootoptions")
MbootList2 = ("/dev/%s" % SystemInfo["mtdrootfs"], )  # kexec kernel Vu+ multiboot


class tmp:
	dir = None


def getMultibootslots():
	bootslots = {}
	slotname = ""
	SystemInfo["MultiBootSlot"] = None
	SystemInfo["VuUUIDSlot"] = ""
	SystemInfo["BootDevice"] = ""
	UUID = ""
	UUIDnum = 0
	tmp.dir = tempfile.mkdtemp(prefix="getMultibootslots")
	tmpname = tmp.dir
	MbootList = MbootList2 if fileHas("/proc/cmdline", "kexec=1") else MbootList1
	for device in MbootList:
		print("[multiboot*****][getMultibootslots]00 device, bootslots", device, "   ", bootslots)
		if len(bootslots) != 0:
			break
		# print("[multiboot*****][getMultibootslots]0 device = ", device)
		if path.exists(device):
			print("[multiboot*****][getMultibootslots]path found for device = ", device)
			Console(binary=True).ePopen("mount %s %s" % (device, tmpname))
			if path.isfile(path.join(tmpname, "STARTUP")):
				SystemInfo["MBbootdevice"] = device
				device2 = device.rsplit("/", 1)[1]
				print("[Multiboot][[getMultibootslots]1 Bootdevice found: %s" % device2)
				SystemInfo["BootDevice"] = device2
				for file in glob.glob(path.join(tmpname, "STARTUP_*")):
					print("[multiboot*****] [getMultibootslots]2 tmpname = %s" % (tmpname))
					print("[multiboot] [getMultibootslots]4 file = ", file)
					slotnumber = file.rsplit("_", 3 if "BOXMODE" in file else 1)[1]
					slotname = file.rsplit("_", 3 if "BOXMODE" in file else 1)[0]
					slotname = file.rsplit("/", 1)[1]
					slotname = slotname if len(slotname) > 1 else ""
					slotname = ""  # nullify for current moment
					if "STARTUP_ANDROID" in file:
						SystemInfo["AndroidMode"] = True
						continue
					if "STARTUP_RECOVERY" in file:
						SystemInfo["RecoveryMode"] = True
						slotnumber = "0"
					print("[multiboot] [getMultibootslots3] slot = %s file = %s" % (slotnumber, slotname))
					if slotnumber.isdigit() and slotnumber not in bootslots:
						line = open(file).read().replace("'", "").replace('"', "").replace("\n", " ").replace("ubi.mtd", "mtd").replace("bootargs=", "")
						# print("[Multiboot][getMultibootslots]6 readlines = %s " % line)
						slot = dict([(x.split("=", 1)[0].strip(), x.split("=", 1)[1].strip()) for x in line.strip().split(" ") if "=" in x])
						if slotnumber == "0":
							slot["slotType"] = ""
							slot["startupfile"] = path.basename(file)
						else:
							slot["slotType"] = "eMMC" if "mmc" in slot["root"] else "USB"
						if fileHas("/proc/cmdline", "kexec=1") and int(slotnumber) > 3:
							SystemInfo["HasKexecUSB"] = True
						print("[Multiboot][getMultibootslots]6a slot", slot)
						if "root" in slot.keys():
							if "UUID=" in slot["root"]:
								slotx = getUUIDtoSD(slot["root"])
								UUID = slot["root"]
								UUIDnum += 1
								print("[Multiboot][getMultibootslots]6a slotx slot['root']", slotx, slot["root"])
								if slotx is not None:
									slot["root"] = slotx
								slot["kernel"] = "/linuxrootfs%s/zImage" % slotnumber
							if path.exists(slot["root"]) or slot["root"] == "ubi0:ubifs":
								slot["startupfile"] = path.basename(file)
								slot["slotname"] = slotname
								SystemInfo["HasMultibootMTD"] = slot.get("mtd")
								if not fileHas("/proc/cmdline", "kexec=1") and "sda" in slot["root"]:		# Not Kexec Vu+ receiver -- sf8008 type receiver with sd card, reset value as SD card slot has no rootsubdir
									slot["rootsubdir"] = None
									slot["slotType"] = "SDCARD"
								else:
									SystemInfo["HasRootSubdir"] = slot.get("rootsubdir")

								if "kernel" not in slot.keys():
									slot["kernel"] = "%sp%s" % (slot["root"].split("p")[0], int(slot["root"].split("p")[1]) - 1)  # oldstyle MB kernel = root-1
									# print("[multiboot] [getMultibootslots]7a HasMultibootMTD, kernel, root, SystemInfo['HasRootSubdir'] ", SystemInfo["HasMultibootMTD"], "   ", slot["kernel"], "   ", slot["root"], "   ", SystemInfo["HasRootSubdir"])
							else:
								continue
							bootslots[int(slotnumber)] = slot
						elif slotnumber == "0":
							bootslots[int(slotnumber)] = slot
						else:
							continue
			print("[multiboot] [getMultibootslots] Finished bootslots = %s" % bootslots)
			Console(binary=True).ePopen("umount %s" % tmpname)
	if not path.ismount(tmp.dir):
		rmdir(tmp.dir)
	if bootslots:
		# print("[Multiboot] Bootslots found:", bootslots)
		bootArgs = open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read()
		print("[Multiboot][MultiBootSlot] bootArgs:", bootArgs)
		if fileHas("/proc/cmdline", "kexec=1") and SystemInfo["HasRootSubdir"]:							# Kexec Vu+ receiver
			rootsubdir = [x for x in bootArgs.split() if x.startswith("rootsubdir")]
			char = "/" if "/" in rootsubdir[0] else "="
			SystemInfo["MultiBootSlot"] = int(rootsubdir[0].rsplit(char, 1)[1][11:])
			SystemInfo["VuUUIDSlot"] = (UUID, UUIDnum) if UUIDnum != 0 else ""
			print("[Multiboot][MultiBootSlot]0 current slot used:", SystemInfo["MultiBootSlot"])
			# print("[Multiboot][MultiBootSlot]0 UID, UUIDnum:", SystemInfo["VuUUIDSlot"], "   ", SystemInfo["VuUUIDSlot"][0], "   ", SystemInfo["VuUUIDSlot"][1])
		elif SystemInfo["HasRootSubdir"] and "root=/dev/sda" not in bootArgs:							# RootSubdir receiver or sf8008 receiver with root in eMMC slot
			slot = [x[-1] for x in bootArgs.split() if x.startswith("rootsubdir")]
			SystemInfo["MultiBootSlot"] = int(slot[0])
			print("[Multiboot][MultiBootSlot]1 current slot used:", SystemInfo["MultiBootSlot"])
		else:
			root = dict([(x.split("=", 1)[0].strip(), x.split("=", 1)[1].strip()) for x in bootArgs.strip().split(" ") if "=" in x])["root"]  # Broadband receiver (e.g. gbue4k) or sf8008 with sd card as root/kernel pair
			for slot in bootslots.keys():
				if "root" not in bootslots[slot].keys():
					continue
				if bootslots[slot]["root"] == root:
					SystemInfo["MultiBootSlot"] = slot
					print("[Multiboot][MultiBootSlot]2 current slot used:", SystemInfo["MultiBootSlot"])
					break
	return bootslots


def getUUIDtoSD(UUID):  # returns None on failure
	# print("[multiboot][getUUIDtoSD2] UUID = ", UUID)
	check = "/sbin/blkid"
	if fileExists(check):
		lines = subprocess.check_output([check]).decode(encoding="utf8", errors="ignore").split("\n")
		for line in lines:
			# print("[Multiboot][getUUIDtoSD2] line", line)
			if UUID in line.replace('"', ''):
				return line.split(":")[0].strip()
	else:
		return None


def GetCurrentImageMode():
	return bool(SystemInfo["canMultiBoot"]) and SystemInfo["canMode12"] and int(open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read().replace("\0", "").split("=")[-1])


def GetImagelist(Recovery=None):
	Imagelist = {}
	tmp.dir = tempfile.mkdtemp(prefix="GetImagelist")
	tmpname = tmp.dir
	from Components.config import config		# here to prevent boot loop
	for slot in sorted(list(SystemInfo["canMultiBoot"].keys())):
		if slot == 0:
			if not Recovery:		# called by ImageManager
				continue
			else:					# called by MultiBootSelector
				Imagelist[slot] = {"imagename": _("Recovery Mode")}
				continue
		print("[multiboot] [GetImagelist] slot = ", slot)
		BuildVersion = "  "
		Build = " "  # ViX Build No.
		Creator = " "  # Openpli Openvix Openatv etc
		Imagelist[slot] = {"imagename": _("Empty slot")}
		imagedir = "/"
		if SystemInfo["MultiBootSlot"] != slot or SystemInfo["HasHiSi"]:
			if SystemInfo["HasMultibootMTD"]:
				Console(binary=True).ePopen("mount -t ubifs %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmpname))
			else:
				Console(binary=True).ePopen("mount %s %s" % (SystemInfo["canMultiBoot"][slot]["root"], tmpname))
			imagedir = sep.join([_f for _f in [tmpname, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
		# print("[multiboot] [GetImagelist]0 isfile = %s" % (path.join(imagedir, "usr/bin/enigma2")))
		if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
			# print("[multiboot] [GetImagelist]1 Slot = %s imagedir = %s" % (slot, imagedir))
			if path.isfile(path.join(imagedir, "usr/lib/enigma.info")):
				print("[multiboot] [GetImagelist] using enigma.info")
				BuildVersion = createInfo(slot, imagedir=imagedir)
				# print("[multiboot] [GetImagelist]  slot=%s, BuildVersion=%s" % (slot, BuildVersion))
			else:
				# print("[multiboot] [GetImagelist] using BoxBranding")
				print("[multiboot] [GetImagelist]2 slot = %s imagedir = %s" % (slot, imagedir))
				Creator = open("%s/etc/issue" % imagedir).readlines()[-2].capitalize().strip()[:-6]
				print("[multiboot] [GetImagelist] Creator = %s imagedir = %s" % (Creator, imagedir))
				if fileHas("/proc/cmdline", "kexec=1") and path.isfile(path.join(imagedir, "etc/vtiversion.info")):
					Vti = open(path.join(imagedir, "etc/vtiversion.info")).read()
					# print("[BootInfo]6 vti = ", Vti)
					date = VerDate(imagedir)
					Creator = Vti[0:3]
					Build = Vti[-8:-1]
					BuildVersion = "%s %s (%s) " % (Creator, Build, date)
					# print("[BootInfo]8 BuildVersion  = ", BuildVersion )
				else:
					date = VerDate(imagedir)
					Creator = Creator.replace("-release", " ")
					BuildVersion = "%s (%s)" % (Creator, date)
			if fileHas("/proc/cmdline", "kexec=1") and Recovery and config.usage.bootlogo_identify.value:
				bootmviSlot(imagedir=imagedir, text=BuildVersion, slot=slot)
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


def createInfo(slot, imagedir="/"):
	BoxInfo = BoxInformation(root=imagedir) if SystemInfo["MultiBootSlot"] != slot else BoxInfoRunningInstance
	Creator = BoxInfo.getItem("distro", " ").capitalize()
	BuildImgVersion = BoxInfo.getItem("imgversion")
	BuildType = BoxInfo.getItem("imagetype", " ")[0:3]
	BuildVer = BoxInfo.getItem("imagebuild")
	BuildDate = VerDate(imagedir)
	BuildDev = str(BoxInfo.getItem("imagedevbuild")).zfill(3) if BuildType != "rel" else ""
	return " ".join([str(x) for x in (Creator, BuildImgVersion, BuildType, BuildVer, BuildDev, "(%s)" % BuildDate) if x])


def VerDate(imagedir):
	date1 = date2 = date3 = "00000000"
	if fileExists(path.join(imagedir, "var/lib/opkg/status")):
		date1 = datetime.fromtimestamp(stat(path.join(imagedir, "var/lib/opkg/status")).st_mtime).strftime("%Y-%m-%d")
	date2 = datetime.fromtimestamp(stat(path.join(imagedir, "usr/bin/enigma2")).st_mtime).strftime("%Y-%m-%d")
	if fileExists(path.join(imagedir, "usr/share/bootlogo.mvi")):
		date3 = datetime.fromtimestamp(stat(path.join(imagedir, "usr/share/bootlogo.mvi")).st_mtime).strftime("%Y-%m-%d")
	print("[multiboot][VerDate]1 date1, date2, date3", date1, "   ", date2, "   ", date3)
	date = max(date1, date2, date3)  # this is comparing strings
	print("[multiboot][VerDate]2 date = %s" % date)
	date = datetime.strptime(date, '%Y-%m-%d').strftime("%d-%m-%Y")
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


def bootmviSlot(imagedir="/", text=" ", slot=0):
	inmviPath = path.join(imagedir, "usr/share/bootlogo.mvi")
	outmviPath = path.join(imagedir, "usr/share/enigma2/bootlogo.mvi")
	txtPath = path.join(imagedir, "usr/share/enigma2/bootlogo.txt")
	text = "booting slot %s %s" % (slot, text)
	print("[multiboot][bootmviSlot] inPath, outpath ", inmviPath, "   ", outmviPath)
	if path.exists(inmviPath):
		if path.exists(outmviPath) and path.exists(txtPath) and open(txtPath).read() == text:
			return
		print("[multiboot][bootmviSlot] Copy /usr/share/bootlogo.mvi to /tmp/bootlogo.m1v")
		Console(binary=True).ePopen("cp %s /tmp/bootlogo.m1v" % inmviPath)
		print("[multiboot][bootmviSlot] Dump iframe to png")
		Console(binary=True).ePopen("ffmpeg -skip_frame nokey -i /tmp/bootlogo.m1v -vsync 0  -y  /tmp/out1.png 2>/dev/null")
		Console(binary=True).ePopen("rm -f /tmp/mypicture.m1v")
		if path.exists("/tmp/out1.png"):
			img = Image.open("/tmp/out1.png")						# Open an Image
		else:
			print("[multiboot][bootmviSlot] unable to create new bootlogo cannot open out1.png")
			return
		I1 = ImageDraw.Draw(img)									# Call draw Method to add 2D graphics in an image
		myFont = ImageFont.truetype("/usr/share/fonts/OpenSans-Regular.ttf", 65)		# Custom font style and font size
		print("[multiboot][bootmviSlot] Write text to png")
		I1.text((52, 12), text, font=myFont, fill=(255, 0, 0))		# Add Text to an image
		I1.text((50, 10), text, font=myFont, fill=(255, 255, 255))
		img.save("/tmp/out1.png")									# Save the edited image
		print("[multiboot][bootmviSlot] Repack bootlogo")
		Console(binary=True).ePopen("ffmpeg -i /tmp/out1.png -r 25 -b 20000 -y /tmp/mypicture.m1v  2>/dev/null")
		Console(binary=True).ePopen("cp /tmp/mypicture.m1v %s" % outmviPath)
		with open(txtPath, "w") as f:
			f.write(text)


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
