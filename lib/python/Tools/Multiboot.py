from datetime import datetime
import glob
import struct
import subprocess
import tempfile
from os import path, rmdir, rename, sep, stat
import re

from Components.SystemInfo import SystemInfo, BoxInfo as BoxInfoRunningInstance, BoxInformation, BOXTYPE, CHKROOTMB, MODEL, MTDROOTFS, UBIMB
from Tools.Directories import copyfile, fileExists, fileHas, fileReadLine, pathExists


def initMultiboot():
	SystemInfo["HasRootSubdir"] = False
	SystemInfo["RecoveryMode"] = False
	SystemInfo["AndroidMode"] = False
	SystemInfo["HasMultibootMTD"] = False
	SystemInfo["resetMBoot"] = False
	SystemInfo["HasKexecUSB"] = False
	SystemInfo["HasMultibootFlags"] = False
	SystemInfo["HasKexecMultiboot"] = fileHas("/proc/cmdline", "kexec=1")
	SystemInfo["HasChkrootMultiboot"] = isFat32("/dev/block/by-name/others") or fileExists("/dev/block/by-name/startup")
	SystemInfo["MBbootdevice"] = ""
	SystemInfo["canchkroot"] = (UBIMB or fileExists("/dev/block/by-name/others")) and not SystemInfo["HasChkrootMultiboot"] and not fileExists("/etc/.disableChkroot")
	SystemInfo["HasHiSi"] = pathExists("/proc/hisi") and BOXTYPE not in ("vipertwin", "viper4kv20", "viper4kv40", "sfx6008", "sfx6018")  # This needs to be for later checks
	SystemInfo["canMultiBoot"] = getMultibootslots()
	SystemInfo["canBackupEMC"] = MODEL in ("hd51", "h7") and ("disk.img", "%s" % SystemInfo["MBbootdevice"]) or MODEL in ("osmio4k", "osmio4kplus", "osmini4k") and ("emmc.img", "%s" % SystemInfo["MBbootdevice"]) or SystemInfo["HasHiSi"] and ("usb_update.bin", "none")
	SystemInfo["CanKexecVu"] = MODEL in ("vusolo4k", "vuduo4k", "vuduo4kse", "vuultimo4k", "vuuno4k", "vuuno4kse", "vuzero4k") and not SystemInfo["HasKexecMultiboot"]  # Was in SystemInfo.py. Seems to be unsed.


def getMultibootslots():
	bootslots = {}
	slotname = ""
	SystemInfo["MultiBootSlot"] = None
	SystemInfo["VuUUIDSlot"] = ""
	SystemInfo["BootDevice"] = ""
	UUID = ""
	UUIDnum = 0
	tmpdir = tempfile.mkdtemp(prefix="getMultibootslots")
	print(f"[multiboot][getMultibootslots]root:{MTDROOTFS} UBIMB:{UBIMB} CHKROOTMB:{CHKROOTMB}")
	if SystemInfo["HasKexecMultiboot"]:
		MbootList = (f"/dev/{MTDROOTFS}", )  # kexec kernel Vu+ multiboot
	else:
		MbootList = ("/dev/mmcblk0p1", "/dev/mmcblk1p1", "/dev/mmcblk0p3", "/dev/mmcblk0p4", "/dev/mtdblock2", "/dev/block/by-name/bootoptions", "/dev/block/by-name/others", "/dev/block/by-name/startup")
	for device in MbootList:
		if bootslots:  # if bootslots is populated, the correct device has already been found so abort search
			break

		print(f"[multiboot][getMultibootslots]device:{device}")
		if not path.exists(device):
			continue

		print(f"[multiboot][getMultibootslots]root:{MTDROOTFS} device:{device} UBIMB:{UBIMB} CHKROOTMB:{CHKROOTMB}")
		_mount(device, tmpdir)

		if not path.isfile(path.join(tmpdir, "STARTUP")):  # Not Multiboot receiver
			_unmount(tmpdir)
			continue

		print(f"[multiboot][getMultibootslots]device:{device} found STARTUP")
		STARTUP = fileReadLine(path.join(tmpdir, "STARTUP"))
		print(f"[multiboot][getMultibootslots] STARTUP:{STARTUP}")
		if SystemInfo["HasKexecMultiboot"] and not path.isfile(dest := path.join(tmpdir, "etc/init.d/kexec-multiboot-recovery")) and path.isfile("/etc/init.d/kexec-multiboot-recovery"):  # check Recovery & slot image for recovery script
			if path.isfile(etc_issue := path.join(tmpdir, "etc/issue")):
				try:
					Creator = open(etc_issue).readlines()[-2].lower().split(maxsplit=1)[0]
				except IndexError:  # /etc/issue non standard file content
					Creator = ""
				if Creator in ("openvix", "openbh"):
					copyfile("/etc/init.d/kexec-multiboot-recovery", dest)
		# print(f"[multiboot][getMultibootslots]1 bootargs?: {path.exists('/sys/firmware/devicetree/base/chosen/bootargs')}")
		SystemInfo["MBbootdevice"] = resolveDevice(device)  # used in SystemInfo
		SystemInfo["BootDevice"] = SystemInfo["MBbootdevice"].rsplit("/", 1)[1]  # used by About
		print(f"[Multiboot][[getMultibootslots]2 *** Bootdevice found: {SystemInfo['BootDevice']} CHKROOTMB:{CHKROOTMB} MBbootdevice:{SystemInfo['MBbootdevice']}")
		if path.exists("/sys/firmware/devicetree/base/chosen/bootargs") or CHKROOTMB:  # check validity for multiboot
			for file in glob.glob(path.join(tmpdir, "STARTUP_*")):
				slotnumber = file.rsplit("_", 3 if "BOXMODE" in file else 1)[1]
				# slotname - WIP
				# slotname = file.rsplit("_", 3 if "BOXMODE" in file else 1)[0]
				# slotname = file.rsplit("/", 1)[1]
				# slotname = slotname if len(slotname) > 1 else ""
				slotname = ""  # nullify for current moment
				if "STARTUP_ANDROID" in file:
					SystemInfo["AndroidMode"] = True
					continue
				if "STARTUP_RECOVERY" in file:
					slotnumber = "0"
					SystemInfo["RecoveryMode"] = BOXTYPE != "gbquad4kpro"
				if "STARTUP_FLASH" in file:
					slotnumber = "0"

				if not slotnumber.isdigit():
					continue

				if int(slotnumber) in bootslots:
					continue

				slot = _parseStartupFile(file)
				print(f"[Multiboot][[getMultibootslots]3 slotnumber:{slotnumber} slot:{slot}")
				if slotnumber == "0":
					slot["slotType"] = "" if not UBIMB else "eMMC"
					slot["startupfile"] = path.basename(file)
				else:
					slot["slotType"] = "eMMC" if "root" in slot and "mmc" in slot["root"] else "USB"  # ("root" in slot) add to protected against possible crash... we dont know "root" was in the START file
				print(f"[Multiboot][[getMultibootslots]4 slotnumber:{slotnumber} slotType:{slot["slotType"]}")
				if SystemInfo["HasKexecMultiboot"] and int(slotnumber) > 3:
					SystemInfo["HasKexecUSB"] = True
				if "root" in slot:
					if "UUID=" in slot["root"]:	 # KexecMultiboot or UBIMB
						UUIDValue = slot["root"]
						slotx = getUUIDtoSD(slot["root"])
						if slotx is not None:
							slot["root"] = slotx
							UUID = slot["root"]
							UUIDnum += 1
						if not UBIMB:
							slot["kernel"] = f"/linuxrootfs{slotnumber}/zImage"
					if not (path.exists(slot["root"]) or slot["root"] in ("ubi0:ubifs", "ubi0:rootfs")):
						continue
					slot["startupfile"] = path.basename(file)
					slot["slotname"] = slotname
					if not UBIMB:
						SystemInfo["HasMultibootMTD"] = slot.get("mtd")
						SystemInfo["HasMultibootFlags"] = path.exists("/dev/block/by-name/flag")
					if not SystemInfo["HasKexecMultiboot"] and not UBIMB and "sda" in slot["root"]:		# Not Kexec Vu+ receiver -- sf8008 type receiver with sd card, reset value as SD card slot has no rootsubdir
						slot["rootsubdir"] = None
						slot["slotType"] = "SDCARD"
					elif "STARTUP_RECOVERY" not in file:
						SystemInfo["HasRootSubdir"] = slot.get("rootsubdir")
					if "kernel" not in slot:
						slot["kernel"] = f"{slot['root'].split('p')[0]}p{int(slot['root'].split('p')[1]) - 1}"  # oldstyle MB kernel = root-1
					bootslots[int(slotnumber)] = slot
				elif slotnumber == "0":
					bootslots[int(slotnumber)] = slot
		else:  # kernel corruption set corruption flag
			# print(f"[multiboot][getMultibootslots]3 bootargs?: {path.exists("/sys/firmware/devicetree/base/chosen/bootargs")}")
			SystemInfo["resetMBoot"] = True
			bootslots = {}
		_unmount(tmpdir)
	_unmountAndRemove(tmpdir)
	if bootslots:
		print(f"[multiboot][getMultibootslots] bootslots: {bootslots}")
		if not CHKROOTMB:
			bootArgs = open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read()
			print(f"[multiboot][getMultibootslots]4 bootArgs: {bootArgs}")
			if SystemInfo["HasKexecMultiboot"] and SystemInfo["HasRootSubdir"]:							# Kexec Vu+ receiver
				rootsubdir = [x for x in bootArgs.split() if x.startswith("rootsubdir")]
				char = "/" if "/" in rootsubdir[0] else "="
				SystemInfo["MultiBootSlot"] = int(rootsubdir[0].rsplit(char, 1)[1][11:])
				SystemInfo["VuUUIDSlot"] = (UUID, UUIDnum) if UUIDnum != 0 else ""
			elif SystemInfo["HasMultibootFlags"]:  # Qviart Dual 4K
				with open('/dev/block/by-name/flag', 'rb') as f:
					struct_fmt = "B"
					flag = f.read(struct.calcsize(struct_fmt))
					slot = struct.unpack(struct_fmt, flag)
					SystemInfo["MultiBootSlot"] = int(slot[0])  # needs to be tested so this comment can be removed.
			elif bootArgs and SystemInfo["HasRootSubdir"] and "root=/dev/sda" not in bootArgs and not UBIMB:							# RootSubdir receiver or sf8008 receiver with root in eMMC slot
				slot = [x[-1] for x in bootArgs.split() if x.startswith("rootsubdir")]
				SystemInfo["MultiBootSlot"] = int(slot[0])
			else:
				root = dict([(x.split("=", 1)[0].strip(), x.split("=", 1)[1].strip()) for x in bootArgs.strip().split(" ") if "=" in x])["root"]  # Broadband receiver (e.g. gbue4k) or sf8008 with sd card as root/kernel pair
				for slot in bootslots:
					if "root" not in bootslots[slot]:
						continue
					if bootslots[slot]["root"] == root:
						SystemInfo["MultiBootSlot"] = slot
						print(f"[Multiboot][MultiBootSlot]2 current slot used:{SystemInfo['MultiBootSlot']}")
						break
		else:
			if UBIMB:
				SystemInfo["VuUUIDSlot"] = (UUID, UUIDnum, UUIDValue) if UUIDnum != 0 else ""
			SystemInfo["MultiBootSlot"] = 0 if "linuxrootfs" not in STARTUP else int(STARTUP.replace("\n", "").replace(" rootfstype=ext4", "").split("linuxrootfs")[1])
	print(f"[multiboot][getMultibootslots] bootslots: {bootslots} Activeslot:{SystemInfo['MultiBootSlot']}")
	return bootslots


def getUUIDtoSD(UUID):  # returns None on failure
	if not fileExists("/sbin/blkid"):
		return None
	try:
		lines = subprocess.check_output(["/sbin/blkid"]).decode(encoding="utf8", errors="ignore").split("\n")
	except subprocess.CalledProcessError as err:
		print(f"[multiboot][getUUIDtoSD] {err}")
		return None
	for line in lines:
		if UUID in line.replace('"', ''):
			return line.split(":")[0].strip()
	return None


def resolveDevice(devicepath):
	if path.islink(devicepath):
		return path.realpath(devicepath)
	else:
		return devicepath


def GetCurrentImageMode():
	if SystemInfo["canMultiBoot"] and SystemInfo["canMode12"]:
		bootargs = open("/sys/firmware/devicetree/base/chosen/bootargs", "r").read()
		if (r := re.search(r"\bboxmode=(\d+)\b", bootargs)):
			return int(r.group(1))


def GetImagelist(Recovery=None):
	Imagelist = {}
	tmpdir = tempfile.mkdtemp(prefix="GetImagelist")
	from Components.config import config		# here to prevent boot loop
	slotRoot = ""
	for slot in sorted(list(SystemInfo["canMultiBoot"].keys())):
		if slot == 0:
			if UBIMB:
				continue
			elif not Recovery:		# called by ImageManager
				continue
			else:					# called by MultiBootSelector
				Imagelist[slot] = {"imagename": _("Recovery Mode")}
				continue
		BuildVersion = "  "
		Imagelist[slot] = {"imagename": _("Empty slot")}
		imagedir = "/"
		if SystemInfo["MultiBootSlot"] != slot or SystemInfo["HasHiSi"]:
			print(f"[multiboot][GetImagelist] SystemInfo['canMultiBoot'][slot]['root']:{SystemInfo['canMultiBoot'][slot]['root']}")
			if SystemInfo['canMultiBoot'][slot]['root'] != slotRoot:
				print(f"[multiboot][GetImagelist] slotRoot]:{slotRoot}")
				_unmount(tmpdir)
				slotRoot = SystemInfo['canMultiBoot'][slot]['root']
				_mount(SystemInfo['canMultiBoot'][slot]['root'], tmpdir, ubifs=SystemInfo["HasMultibootMTD"])
			imagedir = _imageDir(tmpdir, slot)
		print(f"[multiboot][GetImagelist] imagedir:{imagedir}")
		if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
			if path.isfile(path.join(imagedir, "usr/lib/enigma.info")):
				print("[multiboot] [GetImagelist] using enigma.info")
				BuildVersion = createInfo(slot, imagedir=imagedir)
			else:
				print("[multiboot] [GetImagelist] using etc/issue")
				BuildVersion = _legacyImageName(imagedir)
			if SystemInfo["HasKexecMultiboot"] and Recovery and config.usage.bootlogo_identify.value:
				bootmviSlot(imagedir=imagedir, text=BuildVersion, slot=slot)
			Imagelist[slot] = {"imagename": f"{BuildVersion}"}
		elif path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			Imagelist[slot] = {"imagename": _("Deleted image")}
		else:
			Imagelist[slot] = {"imagename": _("Empty slot")}
	_unmountAndRemove(tmpdir)
	return Imagelist


def createInfo(slot, imagedir="/"):
	BoxInfo = BoxInformation(root=imagedir) if SystemInfo["MultiBootSlot"] != slot else BoxInfoRunningInstance
	Creator = (distro := str(BoxInfo.getItem("displaydistro", ""))) and (distro := distro.split()[0]) and distro[:1].upper() + distro[1:] or str(BoxInfo.getItem("distro", "")).capitalize()
	BuildImgVersion = str(BoxInfo.getItem("imgversion", "")).replace("-release", "")  # replace("-release", "") for PLi 9.0
	BuildType = str(BoxInfo.getItem("imagetype", "rel"))
	if BuildType.lower().startswith("dev"):
		BuildType = BuildType[:3]
	BuildDev = str(idb).zfill(3) if Creator.lower().startswith(("openvix", "openpli")) and BuildType and not BuildType.lower().startswith("rel") and (idb := BoxInfo.getItem("imagedevbuild")) else ""
	if BuildType.lower().startswith("rel"):
		BuildType = ""  # don't bother displaying "release" in the interface as this is the default image type
	elif (iv := BoxInfo.getItem("imgversion")) and BoxInfo.getItem("imagetype") == iv:
		BuildType = ""  # do not display anything if "imagetype" and "imgversion" are identical
	BuildVer = str(BoxInfo.getItem("imagebuild", ""))
	CompileDate = str(BoxInfo.getItem("compiledate", ""))

	try:  # checking for valid YYYYMMDD format date in BuildVer, if so, don't display it
		if BuildVer and (CompileDate == BuildVer or len(BuildVer) == 8 and BuildVer.startswith("20") and BuildVer.isnumeric() and datetime.strptime(BuildVer, '%Y%m%d')):
			BuildVer = ""
	except (TypeError, ValueError):
		pass

	if BuildVer and len(BuildVer) == 3 and BuildVer.isnumeric():
		BuildImgVersion = BuildImgVersion + "." + BuildVer
		BuildVer = ""

	if BuildDev and len(BuildDev) == 3 and BuildDev.isnumeric():
		BuildImgVersion = BuildImgVersion + "." + BuildDev
		BuildDev = ""

	try:
		BuildDate = datetime.strptime(CompileDate, '%Y%m%d').strftime("%d-%m-%Y")
	except (TypeError, ValueError):  # sanity for enigma.info containing bad/no entry
		BuildDate = VerDate(imagedir)

	return " ".join([str(x).strip() for x in (Creator, BuildImgVersion, BuildType, BuildVer, BuildDev, f"({BuildDate})") if x and str(x).strip()])


def _legacyImageName(imagedir):
	date = VerDate(imagedir)
	try:
		Creator = open(f"{imagedir}/etc/issue").readlines()[-2].capitalize().strip()[:-6]
	except IndexError:  # /etc/issue no standard file content
		Creator = _("Unknown image")
	if SystemInfo["HasKexecMultiboot"] and path.isfile(path.join(imagedir, "etc/vtiversion.info")):
		Vti = open(path.join(imagedir, "etc/vtiversion.info")).read()
		Creator = Vti[0:3]
		Build = Vti[-8:-1]
		BuildVersion = f"{Creator} {Build} ({date}) "
	else:
		Creator = Creator.replace("-release", " ")
		BuildVersion = f"{Creator} ({date})"
	return BuildVersion


def VerDate(imagedir):
	def mtime(fpath):
		return fileExists(file := path.join(imagedir, fpath)) and int(stat(file).st_mtime) or 0
	return datetime.fromtimestamp(max(mtime("var/lib/opkg/status"), mtime("usr/bin/enigma2"), mtime("usr/share/bootlogo.mvi"))).strftime("%d-%m-%Y")


def emptySlot(slot):
	imagedir, tmpdir = _mountSlot(slot)
	if path.isfile(path.join(imagedir, "usr/bin/enigma2")):
		rename(path.join(imagedir, "usr/bin/enigma2"), path.join(imagedir, "usr/bin/enigmax"))
		ret = 0
	else:
		ret = 4  # NO enigma2 found to rename
	_unmountAndRemove(tmpdir)
	return ret


def bootmviSlot(imagedir="/", text=" ", slot=0):
	inmviPath = path.join(imagedir, "usr/share/bootlogo.mvi")
	outmviPath = path.join(imagedir, "usr/share/enigma2/bootlogo.mvi")
	txtPath = path.join(imagedir, "usr/share/enigma2/bootlogo.txt")
	tmpBootLogo = "/tmp/bootlogo.m1v"
	tmpEditedLogo = "/tmp/mypicture.m1v"
	outpng = "/tmp/out1.png"
	text = f"booting slot {slot} {text}"
	if path.exists(inmviPath):
		if path.exists(outmviPath) and path.exists(txtPath) and open(txtPath).read() == text:
			return

		from PIL import Image, ImageDraw, ImageFont

		_run(["cp", inmviPath, tmpBootLogo])

		_run([
			"ffmpeg",
			"-skip_frame", "nokey",
			"-i", tmpBootLogo,
			"-vsync", "0",
			"-y",
			outpng
		])

		_run(["rm", "-f", tmpEditedLogo])  # remove old junk before using this location

		if path.exists(outpng):
			img = Image.open(outpng)						# Open an Image
		else:
			return
		I1 = ImageDraw.Draw(img)									# Call draw Method to add 2D graphics in an image
		myFont = ImageFont.truetype("/usr/share/fonts/OpenSans-Regular.ttf", 65)		# Custom font style and font size
		I1.text((52, 12), text, font=myFont, fill=(255, 0, 0))		# Add Text to an image
		I1.text((50, 10), text, font=myFont, fill=(255, 255, 255))
		img.save(outpng)									# Save the edited image

		_run([
			"ffmpeg",
			"-i", outpng,
			"-r", "25",
			"-b", "20000",
			"-y",
			tmpEditedLogo
		])

		_run(["cp", tmpEditedLogo, outmviPath])

		with open(txtPath, "w") as f:
			f.write(text)


def restoreSlots():
	for slot in SystemInfo["canMultiBoot"]:
		imagedir, tmpdir = _mountSlot(slot)
		if path.isfile(path.join(imagedir, "usr/bin/enigmax")):
			rename(path.join(imagedir, "usr/bin/enigmax"), path.join(imagedir, "usr/bin/enigma2"))
		_unmountAndRemove(tmpdir)


def isFat32(device):
	try:
		with open(device, "rb") as fd:
			bootSector = fd.read(512)
			fsType = bootSector[82:90].decode("ascii", errors="ignore").strip()
			return fsType == "FAT32" or int.from_bytes(bootSector[36:40], "little") != 0
	except Exception:
		return False


# helper functions
def _parseStartupFile(file):
	line = open(file).read() \
		.replace("'", "") \
		.replace('"', "") \
		.replace("\n", " ") \
		.replace("ubi.mtd", "mtd") \
		.replace("bootargs=", "")

	return {
		x.split("=", 1)[0].strip(): x.split("=", 1)[1].strip()
		for x in line.split()
		if "=" in x
	}


def _run(cmd):
	"""Run cmd via subprocess, logging stderr on non-zero exit."""
	result = subprocess.run(cmd, capture_output=True, check=False)
	if result.returncode != 0:
		print(f"[multiboot] {' '.join(cmd)} failed: {result.stderr.decode(errors='ignore').strip()}")
	return result


def _mount(device, mountpoint, ubifs=False):
	cmd = ["mount"]
	if ubifs:
		cmd += ["-t", "ubifs"]
	cmd += [device, mountpoint]
	_run(cmd)


def _mountSlot(slot):
	mountpoint = tempfile.mkdtemp(prefix="multibootSlot")
	root = SystemInfo['canMultiBoot'][slot]['root']
	_mount(root, mountpoint, ubifs=SystemInfo["HasMultibootMTD"])
	return _imageDir(mountpoint, slot), mountpoint


def _unmount(mountpoint):
	if not mountpoint:
		return
	while path.ismount(mountpoint):
		result = _run(["umount", mountpoint])
		if result.returncode != 0:
			break


def _unmountAndRemove(mountpoint):
	_unmount(mountpoint)
	if mountpoint and not path.ismount(mountpoint):
		rmdir(mountpoint)


def _imageDir(mountroot, slot):
	return sep.join([_f for _f in [mountroot, SystemInfo["canMultiBoot"][slot].get("rootsubdir", "")] if _f])
# end helper functions


#	following added for OpenWebif canMultiBoot getCurrentSlotAndBootCodes getSlotImageList getBootCodeDescription activateSlot
def canMultiBoot():
	# print(f"[multiboot][canMultiBoot] ")
	return bool(SystemInfo["canMultiBoot"])


def getCurrentSlotAndBootCodes():
	bootCode = " "
	# print(f"[MultiBoot][getCurrentSlotAndBootCodes] bootSlot:{SystemInfo['MultiBootSlot']} bootCode:{bootCode}")
	return SystemInfo["MultiBootSlot"], bootCode


def getSlotImageList(callback):
	imageList = GetImagelist()
	# print(f"[MultiBoot][getSlotImageLists] keys:{imageList.keys()} {imageList}")
	callback(imageList)


def getBootCodeDescription(bootCode=None):
	bootCodeDescriptions = {
		"": _("Normal: No boot modes required."),
		"1": _("Mode 1: Supports Kodi but PiP may not work"),
		"12": _("Mode 12: Supports PiP but Kodi may not work")
	}
	if bootCode is None:
		return bootCodeDescriptions
	return bootCodeDescriptions.get(bootCode, "")


def activateSlot(slotCode, bootCode, callback):
	# print(f"[MultiBoot][activateSlot] slotCode:{slotCode} bootCode:{bootCode}")
	slot = int(slotCode)
	tmpdir = tempfile.mkdtemp(prefix="Webif_Multiboot")
	_mount(SystemInfo['MBbootdevice'], tmpdir)
	copyfile(path.join(tmpdir, SystemInfo["canMultiBoot"][slot]["startupfile"]), path.join(tmpdir, "STARTUP"))
	if SystemInfo["HasMultibootMTD"]:
		with open('/dev/block/by-name/flag', 'wb') as f:
			f.write(struct.pack("B", int(slotCode)))
	_unmountAndRemove(tmpdir)
	callback(0, 0)
