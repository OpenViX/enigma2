import errno
from os import listdir, major, path as ospath, rmdir, sep as ossep, stat, statvfs, system as ossystem, unlink  # minor
from fcntl import ioctl
from time import sleep, time

from enigma import eTimer
from Components.SystemInfo import SystemInfo
import Components.Task
from Tools.CList import CList

# DEBUG: REMINDER: This comment needs to be expanded for the benefit of readers.
# Removable if 1 --> With motor
# Internal if 1 --> SATA disk
# Rotational if 0 --> SSD or MMC, 1 --> HDD
# SDMMC if True --> MMC/CF

# List of Linux major device numbers for devices that will not be handled
# by Enigma2.
#
blacklistedDisks = [
	1,  # RAM disk (/dev/ram0=0, /dev/initrd=250 [250=Initial RAM disk for old systems, new systems use 0])
	7,  # Loopback devices (/dev/loop0=0)
	31,  # ROM/flash memory card (/dev/rom0=0, /dev/rrom0=8, /dev/flash0=16, /dev/rflash0=24 [r=Read Only])
	240,  # ROM/flash memory card (/dev/rom0=0, /dev/rrom0=8, /dev/flash0=16, /dev/rflash0=24 [r=Read Only])
	253,  # LOCAL/EXPERIMENTAL USE
	254,  # LOCAL/EXPERIMENTAL USE
	259  # MMC block devices (/dev/mmcblk0=0, /dev/mmcblk0p1=1, /dev/mmcblk1=8)
]

# List of Linux major device numbers that represent optical drives.
#
opticalDisks = [
	3,  # First MFM, RLL and IDE hard disk/CD-ROM interface
	11,  # SCSI CD-ROM devices
	15,  # Sony CDU-31A/CDU-33A CD-ROM
	16,  # GoldStar CD-ROM
	17,  # Optics Storage CD-ROM
	18,  # Sanyo CD-ROM
	20,  # Hitachi CD-ROM (under development)
	22,  # Second IDE hard disk/CD-ROM interface
	23,  # Mitsumi proprietary CD-ROM
	24,  # Sony CDU-535 CD-ROM
	25,  # First Matsushita (Panasonic/SoundBlaster) CD-ROM
	26,  # Second Matsushita (Panasonic/SoundBlaster) CD-ROM
	27,  # Third Matsushita (Panasonic/SoundBlaster) CD-ROM
	28,  # Fourth Matsushita (Panasonic/SoundBlaster) CD-ROM
	29,  # Aztech/Orchid/Okano/Wearnes CD-ROM
	30,  # Philips LMS CM-205 CD-ROM
	32,  # Philips LMS CM-206 CD-ROM
	33,  # Third IDE hard disk/CD-ROM interface
	34,  # Fourth IDE hard disk/CD-ROM interface
	46,  # Parallel port ATAPI CD-ROM devices
	56,  # Fifth IDE hard disk/CD-ROM interface
	57,  # Sixth IDE hard disk/CD-ROM interface
	88,  # Seventh IDE hard disk/CD-ROM interface
	89,  # Eighth IDE hard disk/CD-ROM interface
	90,  # Ninth IDE hard disk/CD-ROM interface
	91,  # Tenth IDE hard disk/CD-ROM interface
	113  # IBM iSeries virtual CD-ROM
]


def readFile(filename):
	try:
		with open(filename, "r") as fd:
			data = fd.read().strip()
	except (IOError, OSError) as err:
		if err.errno != errno.ENOENT:  # No such file or directory.
			print("[Harddisk] Error: Failed to read file! ", err)
		data = None
	return data


def runCommand(command):
	print("[Harddisk] Command: '%s'." % command)
	exitStatus = ossystem(command)
	exitStatus = exitStatus >> 8
	if exitStatus:
		print("[Harddisk] Error: Command '%s' returned error code %d!" % (command, exitStatus))
	return exitStatus


def getProcMounts():
	try:
		with open("/proc/mounts", "r") as fd:
			lines = fd.readlines()
	except (IOError, OSError) as err:
		print("[Harddisk][getProcMounts] Error: Failed to open '/proc/mounts':", err)
		return []
	result = [line.strip().split(" ") for line in lines]
	for item in result:
		item[1] = item[1].replace("\\040", " ")  # Spaces are encoded as \040 in mounts.
		# Also, map any fuseblk fstype to the real file-system behind it...
		# Use blkid to get the info we need....
		#
		if item[2] == 'fuseblk':
			import subprocess
			res = subprocess.run(['blkid', '-sTYPE', '-ovalue', item[0]], capture_output=True)
			if res.returncode == 0:
				# print("[Harddisk][getProcMounts] fuseblk", res.stdout)
				item[2] = res.stdout.strip().decode()
	# print("[Harddisk][getProcMounts] ProcMounts", result)
	return result


def findMountPoint(path):
	'Example: findMountPoint("/media/hdd/some/file") returns "/media/hdd"'
	path = ospath.abspath(path)
	while not ospath.ismount(path):
		path = ospath.dirname(path)
	return path


def internalHDDNotSleeping():
	if harddiskmanager.HDDCount():
		for hdd in harddiskmanager.HDDList():
			if ("sata" in hdd[1].phys_path or "pci" in hdd[1].phys_path or "ahci" in hdd[1].phys_path) and hdd[1].max_idle_time and not hdd[1].isSleeping():
				return True
	return False


def addInstallTask(job, package):
	task = Components.Task.LoggingTask(job, _("Update packages..."))
	task.setTool("opkg")
	task.args.append("update")
	task = Components.Task.LoggingTask(job, _("Install '%s'") % package)
	task.setTool("opkg")
	task.args.append("install")
	task.args.append(package)


def bytesToHumanReadable(size_bytes, binary=False):
	# input is bytes, convert from KB, MB before use.
	size_units = ("B", "kB", "MB", "GB", "TB")
	base = 1024 if binary else 1000
	i = 0
	L = len(size_units) - 1
	while i < L and size_bytes >= base:
		size_bytes /= base
		i += 1
	return ("%.2f %s" if i != 0 and size_bytes < 10 else "%.0f %s") % (size_bytes, size_units[i])


class Harddisk:
	def __init__(self, device, removable=False):
		self.device = device
		self.removable = removable
		self.sdmmc = False
		self.max_idle_time = 0
		self.idle_running = False
		self.last_access = time()
		self.last_stat = 0
		self.timer = None
		self.is_sleeping = False
		self.dev_path = ""
		self.disk_path = ""
		self.mount_path = None
		self.mount_device = None
		self.phys_path = ospath.realpath(self.sysfsPath("device"))
		data = readFile(ospath.join("/sys/block", device, "queue/rotational"))
		self.rotational = True if data is None else int(data)  # Rotational if 0 --> SSD or MMC, 1 --> HDD.
		(self.internal, self.busType) = self.deviceState(device)
		self.dev_path = ospath.join("/dev", self.device)
		self.disk_path = self.dev_path
		self.sdmmc = "MMC" in self.busType
		# print("[Harddisk] self.sdmmc1", self.sdmmc)

		if (self.internal or not removable) and not self.sdmmc:
			msg = " (Start Idle)"
			self.startIdle()
		else:
			msg = ""
		print("[Harddisk] Device '%s' (%s - %s) -> '%s' -> '%s'%s." % (self.device, self.bus(), self.model(), self.dev_path, self.disk_path, msg))

	def __str__(self):
		return "Harddisk(device=%s, devPath=%s, diskPath=%s, physPath=%s, internal=%s, rotational=%s, removable=%s)" % (self.device, self.dev_path, self.disk_path, self.phys_path, self.internal, self.rotational, self.removable)

	def __lt__(self, ob):
		return self.device < ob.device

	def sysfsPath(self, filename):
		return ospath.join("/sys/block", self.device, filename)

	def partitionPath(self, n):
		if self.dev_path.startswith("/dev/mmcblk"):
			return "%sp%s" % (self.dev_path, n)
		else:
			return "%s%s" % (self.dev_path, n)

	def stop(self):
		if self.timer:
			self.timer.stop()
			self.timer.callback.remove(self.runIdle)

	def bus(self):
		if self.internal:
			busName = _("Internal")
			if self.rotational == 0:
				busName = "%s%s" % (busName, " (SSD)")
			else:
				busName = "%s%s" % (busName, " (HDD)")
		else:
			busName = _("External")
			busName = "%s (%s)" % (busName, self.busType)
		return busName

	def diskSize(self):
		# output in MB
		dev = self.findMount()
		if dev:
			try:
				stat = statvfs(dev)
				print("[Harddisk] [diskSize]: stat.f_blocks: %s stat.f_bsize: %s" % (stat.f_blocks, stat.f_bsize))
				cap = int((stat.f_blocks * stat.f_bsize) / 1000 / 1000)
			except (IOError, OSError) as err:
				print("[Harddisk] Error: Failed to get disk size for '%s':" % dev, err)
				cap = 0
		else:
			data = readFile(self.sysfsPath("size"))
			if data is not None:
				cap = int(int(data) / 1000 * 512 / 1024)
			else:
				cap = 0
		return cap

	def capacity(self):
		cap = self.diskSize()  # cap is in MB
		cap *= 1000000  # convert to MB to bytes
		return bytesToHumanReadable(cap)

	def model(self):
		data = None
		msg = ""
		if self.device[:2] == "hd":
			data = readFile(ospath.join("/proc/ide", self.device, "model"))
		elif self.device[:2] == "sd":
			vendor = readFile(ospath.join(self.phys_path, "vendor"))
			model = readFile(ospath.join(self.phys_path, "model"))
			if vendor or model and vendor != model:
				data = "%s (%s)" % (vendor, model)
		elif self.device.startswith("mmcblk"):
			data = readFile(self.sysfsPath("device/name"))
		else:
			msg = "  Device not hdX or sdX or mmcX."
		if data is None:
			print("[Harddisk] Error: Failed to get model!%s:" % msg)
			return "Unknown"
		return data

	def free(self, dev=None):
		if dev is None:
			dev = self.findMount()
		print("[Harddisk][free]dev:", dev)
		if dev:
			try:
				stat = statvfs(dev)
				return (stat.f_bfree / 1000) * (stat.f_bsize / 1000)
			except (IOError, OSError) as err:
				print("[Harddisk] Error: Failed to get free space for '%s' %s:" % dev, err)
		return -1

	def totalFree(self):
		# output in MB
		mediapath = []
		freetot = 0
		print("[Harddisk][totalFree]self.dev_path:", self.dev_path)
		for parts in getProcMounts():
			if ospath.realpath(parts[0]).startswith(self.dev_path):
				mediapath.append(parts[1])
		print("[Harddisk][totalFree]mediapath:", mediapath)
		for mpath in mediapath:
			print("[Harddisk][totalFree]mpath:", mpath)
			if mpath == "/" and SystemInfo["HasKexecMultiboot"]:
				continue
			free = self.free(mpath)
			if free > 0:
				freetot += free
		return int(freetot)

	def Totalfree(self):
		return self.totalFree()

	def numPartitions(self):
		numPart = -1
		try:
			for filename in listdir("/dev"):
				if filename.startswith(self.device):
					numPart += 1
		except (IOError, OSError):
			return -1
		return numPart

	def mountDevice(self):
		for parts in getProcMounts():
			if ospath.realpath(parts[0]).startswith(self.dev_path):
				self.mount_device = parts[0]
				self.mount_path = parts[1]
				print("[Harddisk][mountDevice]device, path", parts[0], "   ", parts[1])
				return parts[1]
		return None

	def enumMountDevices(self):
		for parts in getProcMounts():
			if ospath.realpath(parts[0]).startswith(self.dev_path):
				yield parts[1]

	def findMount(self):
		if self.mount_path is None:
			return self.mountDevice()
		return self.mount_path

	def unmount(self):
		dev = self.mountDevice()
		if dev is None:
			return 0  # Not mounted, return OK.
		return runCommand("umount %s" % dev)

	def createPartition(self):
		return runCommand("printf \"8,\n;0,0\n;0,0\n;0,0\ny\n\" | sfdisk -f -uS %s" % self.disk_path)

	def mount(self):
		if self.mount_device is None:  # Try mounting through fstab first.
			dev = self.partitionPath("1")
		else:
			dev = self.mount_device  # If previously mounted, use the same spot.
		try:
			with open("/etc/fstab", "r") as fd:
				for line in fd.readlines():
					parts = line.strip().split(" ")
					fspath = ospath.realpath(parts[0])
					if fspath == dev:
						return runCommand("mount -t auto %s" % fspath)
		except (IOError, OSError):
			return -1
		exitCode = -1  # Device is not in fstab.
		exitCode = runCommand("hdparm -z %s" % self.disk_path)  # We can let udev do the job, re-read the partition table.
		sleep(3)  # Give udev some time to make the mount, which it will do asynchronously.
		return exitCode

	def killPartitionTable(self):
		zero = 512 * b"\0"
		try:
			with open(self.dev_path, "wb") as fd:
				for i in range(9):  # Delete first 9 sectors, which will likely kill the first partition too.
					fd.write(zero)
		except (IOError, OSError) as err:
			print("[Harddisk] Error: Failed to wipe partition table on '%s':" % self.dev_path, err)

	def killPartition(self, n):
		zero = 512 * b"\0"
		partition = self.partitionPath(n)
		try:
			with open(partition, "wb") as fd:
				for i in range(3):
					fd.write(zero)
		except (IOError, OSError) as err:
			print("[Harddisk] Error: Failed to wipe partition on '%s':" % partition, err)

	def createInitializeJob(self):
		print("[Harddisk] Initializing storage device...")
		job = Components.Task.Job(_("Initializing storage device..."))
		size = self.diskSize()
		print("[Harddisk] Disk size: %s MB." % size)
		task = UnmountTask(job, self)
		task = Components.Task.PythonTask(job, _("Removing partition table."))
		task.work = self.killPartitionTable
		task.weighting = 1
		task = Components.Task.LoggingTask(job, _("Rereading partition table."))
		task.weighting = 1
		task.setTool("hdparm")
		task.args.append("-z")
		task.args.append(self.disk_path)
		task = Components.Task.ConditionTask(job, _("Waiting for partition."), timeoutCount=20)
		task.check = lambda: not ospath.exists(self.partitionPath("1"))
		task.weighting = 1
		task = Components.Task.LoggingTask(job, _("Creating partition."))
		task.weighting = 5
		task.setTool("parted")
		if size < 1024:
			alignment = "min"  # On very small devices, align to block only.
		else:
			alignment = "opt"  # Prefer optimal alignment for performance.
		task.args += ["-a", alignment, "-s", self.disk_path, "mklabel", "gpt", "mkpart", "primary", "0%", "100%"]
		task = Components.Task.ConditionTask(job, _("Waiting for partition."))
		task.check = lambda: ospath.exists(self.partitionPath("1"))
		task.weighting = 1
		task = UnmountTask(job, self)
		print("[Harddisk] Creating filesystem.")
		task = MkfsTask(job, _("Creating filesystem."))
		big_o_options = ["dir_index"]
		task.setTool("mkfs.ext4")
		if size > 250000:
			task.args += ["-T", "largefile", "-N", "262144"]  # No more than 256k i-nodes (prevent problems with fsck memory requirements).
			big_o_options.append("sparse_super")
		elif size > 16384:
			task.args += ["-T", "largefile"]  # Between 16GB and 250GB: 1 i-node per megabyte.
			big_o_options.append("sparse_super")
		elif size > 2048:
			task.args += ["-T", "largefile", "-N", str(int(size * 32))]  # Over 2GB: 32 i-nodes per megabyte.
		task.args += ["-F", "-F", "-m0", "-O ^metadata_csum", "-O", ",".join(big_o_options), self.partitionPath("1")]
		task = MountTask(job, self)
		task.weighting = 3
		print("[Harddisk] Mounting storage device.")
		task = Components.Task.ConditionTask(job, _("Waiting for mount."), timeoutCount=20)
		task.check = self.mountDevice
		task.weighting = 1
		print("[Harddisk] Initialization complete.")
		return job

	def createCheckJob(self):
		print("[Harddisk] Checking filesystem...")
		job = Components.Task.Job(_("Checking filesystem..."))
		if self.findMount():
			task = UnmountTask(job, self)  # Create unmount task if it was not mounted.
			dev = self.mount_device
		else:
			dev = self.partitionPath("1")  # Otherwise, assume there is one partition.
		for parts in getProcMounts():
			if ospath.realpath(parts[0]).startswith(dev):
				partType = parts[2]
		if partType not in ("ext3", "ext4", "vfat", "nfs"):
			partType = "ext4"
		print("[Harddisk] Filesystem type is '%s'." % partType)
		task = Components.Task.LoggingTask(job, _("Checking disk."))  # "fsck"
		task.setTool("fsck.%s" % partType)
		task.args.append("-f")
		task.args.append("-p")
		task.args.append(dev)
		task = MountTask(job, self)
		task.weighting = 3
		task = Components.Task.ConditionTask(job, _("Waiting for mount."))
		task.check = self.mountDevice
		task.weighting = 1
		print("[Harddisk] Check complete.")
		return job

	def getDeviceDir(self):
		return self.dev_path

	def getDeviceName(self):
		return self.disk_path

	# HDD idle poll daemon.
	# As some harddrives have a buggy standby timer, we are doing this
	# by hand here.  First, we disable the hardware timer. then, we check
	# every now and then if any access has been made to the disc.  If
	# there has been no access over a specifed time, we set the hdd into
	# standby.
	#
	# The /sys/block/<dev>/stat file provides several statistics about the
	# state of block device <dev>.  It consists of a single line of text
	# containing 11 decimal values separated by whitespace:
	#
	# Name            units         description
	# ----            -----         -----------
	# read I/Os       requests      number of read I/Os processed
	# read merges     requests      number of read I/Os merged with in-queue I/O
	# read sectors    sectors       number of sectors read
	# read ticks      milliseconds  total wait time for read requests
	# write I/Os      requests      number of write I/Os processed
	# write merges    requests      number of write I/Os merged with in-queue I/O
	# write sectors   sectors       number of sectors written
	# write ticks     milliseconds  total wait time for write requests
	# in_flight       requests      number of I/Os currently in flight
	# io_ticks        milliseconds  total time this block device has been active
	# time_in_queue   milliseconds  total wait time for all requests
	# These additional values appear in some documentation!
	# discard I/Os    requests      number of discard I/Os processed
	# discard merges  requests      number of discard I/Os merged with in-queue I/O
	# discard sectors sectors       number of sectors discarded
	# discard ticks   milliseconds  total wait time for discard requests
	#
	def readStats(self):
		filename = ospath.join("/sys/block", self.device, "stat")
		data = readFile(filename)
		if data is None:
			print("[Harddisk] Error: Failed to read '%s' stats!" % filename)
			return -1, -1
		data = data.split()
		return int(data[0]), int(data[4])  # Return read I/O's, write I/O's.

	def startIdle(self):
		# Disable HDD standby timer.
		if self.internal:
			runCommand("hdparm -S0 %s" % self.disk_path)
		else:
			exitCode = runCommand("sdparm --set=SCT=0 %s" % self.disk_path)
			if exitCode:
				runCommand("hdparm -S0 %s" % self.disk_path)
		self.timer = eTimer()
		self.timer.callback.append(self.runIdle)
		self.idle_running = True
		self.setIdleTime(self.max_idle_time)  # Kick the idle polling loop.

	def runIdle(self):
		if not self.max_idle_time:
			return
		now = time()
		idle_time = now - self.last_access
		stats = sum(self.readStats())
		if stats != self.last_stat and stats >= 0:  # There has been disk access.
			self.last_stat = stats
			self.last_access = now
			idle_time = 0
			self.is_sleeping = False
		if idle_time >= self.max_idle_time and not self.is_sleeping:
			self.setSleep()
			self.is_sleeping = True

	def setSleep(self):
		if self.internal:
			runCommand("hdparm -y %s" % self.disk_path)
		else:
			exitCode = runCommand("sdparm --flexible --readonly --command=stop %s" % self.disk_path)
			if exitCode:
				runCommand("hdparm -y %s" % self.disk_path)

	def setIdleTime(self, idle):
		self.max_idle_time = idle
		if self.idle_running:
			if not idle:
				self.timer.stop()
			else:
				self.timer.start(idle * 100, False)  # Poll 10 times per period.

	def isSleeping(self):
		return self.is_sleeping

	def deviceState(self, device):
		hotplugBuses = ("usb", "mmc", "pcmcia", "ieee1394", "firewire")
		if not self.phys_path.startswith("/sys/devices/"):
			return (False, "ERROR")
		match = None
		for bus in hotplugBuses:
			if "/%s" % bus in self.phys_path:
				match = bus
				break

		if SystemInfo["HasHiSi"] and match == bus and ("usb1/1-1/1-1.1/1-1.1:1.0" in self.phys_path or "usb1/1-1/1-1.4/1-1.4:1.0" in self.phys_path):
			match = None

		if match:
			# print("[Harddisk] DEBUG: Device is removable.  (device='%s', match='%s')" % (device, match))
			return (False, match.upper())
		else:
			# print("[Harddisk] DEBUG: Device is not removable.  (device='%s', No bus)" % (device))
			return (True, "ATA")


class Partition:
	# For backward compatibility, force_mounted actually means "hotplug".
	def __init__(self, mountpoint, device=None, description="", force_mounted=False):
		self.mountpoint = mountpoint
		self.device = device
		self.description = description
		self.force_mounted = mountpoint and force_mounted
		self.is_hotplug = force_mounted  # So far; this might change.

	def __str__(self):
		return "Partition(mountpoint = %s, description = %s, device = %s)" % (self.mountpoint, self.description, self.device)

	def stat(self):
		if self.mountpoint:
			return statvfs(self.mountpoint)
		else:
			raise OSError("Device '%s' is not mounted!" % self.device)

	def free(self):
		try:
			status = self.stat()
			return status.f_bavail * status.f_bsize
		except (IOError, OSError):
			return None

	def total(self):
		try:
			status = self.stat()
			return status.f_blocks * status.f_bsize
		except (IOError, OSError):
			return None

	def tabbedDescription(self):
		if self.mountpoint.startswith("/media/net") or self.mountpoint.startswith("/media/autofs"):
			return self.description  # Network devices have a user defined name.
		return "%s\t%s" % (self.description, self.mountpoint)

	def mounted(self, mounts=None):
		# THANK YOU PYTHON FOR STRIPPING AWAY f_fsid.
		# TODO: Can ospath.ismount be used?
		if self.force_mounted:
			return True
		if self.mountpoint:
			if mounts is None:
				mounts = getProcMounts()
			for parts in mounts:
				if self.mountpoint.startswith(parts[1]):  # Use startswith so a mount not ending with "/" is also detected.
					return True
		return False

	def filesystem(self, mounts=None):
		if self.mountpoint:
			if mounts is None:
				mounts = getProcMounts()
			for fields in mounts:
				if self.mountpoint.endswith(ossep) and not self.mountpoint == ossep:
					if "%s%s" % (fields[1], ossep) == self.mountpoint:
						return fields[2]
				else:
					if fields[1] == self.mountpoint:
						return fields[2]
		return ""


class HarddiskManager:
	def __init__(self):
		self.hdd = []
		self.partitions = []
		self.cd = ""
		self.on_partition_list_change = CList()
		self.enumerateBlockDevices()
		self.enumerateNetworkMounts()

	def enumerateBlockDevices(self):
		print("[Harddisk] Enumerating block devices...")
		self.partitions.append(Partition(mountpoint="/", description=("Internal flash")))  # Add the root device.
		# print("[Harddisk] DEBUG: Partition(mountpoint=%s, description=%s)" % ("/", _("Internal flash")))
		try:
			rootDev = stat("/").st_dev
			rootMajor = major(rootDev)
			# rootMinor = minor(rootDev)
		except (IOError, OSError):
			rootMajor = None
			# rootMinor = None
		# print("[Harddisk] DEBUG: rootMajor = '%s', rootMinor = '%s'" % (rootMajor, rootMinor))
		for device in sorted(listdir("/sys/block")):
			try:
				physicalDevice = ospath.realpath(ospath.join("/sys/block", device, "device"))
			except (IOError, OSError) as err:
				print("[Harddisk] Error: Couldn't determine physicalDevice for device '%s':" % device, err)
				continue
			devicePath = ospath.join("/sys/block/", device)
			data = readFile(ospath.join(devicePath, "dev"))  # This is the device's major and minor device numbers.
			if data is None:
				print("[Harddisk] Error: Device '%s' (%s) does not appear to have valid device numbers!" % (device, physicalDevice))
				continue
			devMajor = int(data.split(":")[0])
			if devMajor in blacklistedDisks:
				# print("[Harddisk] DEBUG: Major device number '%s' for device '%s' (%s) is blacklisted." % (devMajor, device, physicalDevice))
				continue
			if devMajor == 179 and not SystemInfo["HasSDnomount"]:		# Lets handle Zgemma SD card mounts - uses SystemInfo to determine SDcard status
				# print("[Harddisk] DEBUG: Major device number '%s' for device '%s' (%s) doesn't have 'HasSDnomount' set." % (devMajor, device, physicalDevice))
				continue
			if devMajor == 179 and devMajor == rootMajor and not SystemInfo["HasSDnomount"][0]:
				# print("[Harddisk] DEBUG: Major device number '%s' for device '%s' (%s) is the root disk." % (devMajor, device, physicalDevice))
				continue
			if SystemInfo["HasSDnomount"] and device.startswith("%s" % (SystemInfo["HasSDnomount"][1])) and SystemInfo["HasSDnomount"][0]:
				# print("[Harddisk] DEBUG: Major device number '%s' for device '%s' (%s) starts with 'mmcblk0' and has 'HasSDnomount' set." % (devMajor, device, physicalDevice))
				continue
			description = self.getUserfriendlyDeviceName(device, physicalDevice)
			isCdrom = devMajor in opticalDisks or device.startswith("sr")
			if isCdrom:
				self.cd = devicePath
				self.partitions.append(Partition(mountpoint=self.getMountpoint(device), description=description, force_mounted=True, device=device))
				# print("[Harddisk] DEBUG: Partition(mountpoint=%s, description=%s, force_mounted=True, device=%s)" % (self.getMountpoint(device), description, device))
				# print("[Harddisk] Found optical disk '%s' (%s)." % (device, physicalDevice))
			data = readFile(ospath.join(devicePath, "removable"))
			removable = False if data is None else bool(int(data))
			# if removable:
			# 	# print("[Harddisk] DEBUG: Device '%s' (%s) has removable media." % (device, physicalDevice))
			try:
				open(ospath.join("/dev", device), "r").close()
				mediumFound = True  # noqa: F841 Check for medium set for debug.
			except (IOError, OSError) as err:
				if err.errno in (123, 159):  # ENOMEDIUM - No medium found.  (123 = Common Linux, 159 = MIPS Linux)
					mediumFound = False  # noqa: F841 set for Debug
				else:
					print("[Harddisk] Error: Device '%s' (%s) media availability test failed:" % (device, physicalDevice), err)
					continue
			# if mediumFound:
			# 	print("[Harddisk] DEBUG: Device '%s' (%s) has media." % (device, physicalDevice))
			# print("[Harddisk] DEBUG: device = '%s', physicalDevice = '%s', devMajor = '%s', description = '%s'" % (device, physicalDevice, devMajor, description))
			if not isCdrom and ospath.exists(devicePath):
				partitions = [partition for partition in sorted(listdir(devicePath)) if partition.startswith(device)]  # Add HDD check for partitions.
				if len(partitions) == 0:  # Add HDD check for HDD with no partitions (unformatted).
					print("[Harddisk]1 Found storage device '%s' (Removable=%s) NoPartitions = %s." % (device, removable, len(partitions)))
					self.hdd.append(Harddisk(device, removable))
					SystemInfo["Harddisk"] = True
				else:
					if SystemInfo["HasHiSi"] and devMajor == 8 and len(partitions) >= 4:
						partitions = [] if len(partitions) > 6 else partitions[4:]
					print("[Harddisk] len partitions = %s, device = %s" % (len(partitions), device))
					if len(partitions) != 0:
						if removable:
							SystemInfo["HasUsbhdd"][device] = len(partitions)
						print("[Harddisk]2 Found storage device '%s' (Removable=%s) NoPartitions = %s." % (device, removable, len(partitions)))			# [Harddisk] Found storage device 'sdb' (Removable=True) NoPartitions = 1.
						print("[Harddisk]1 SystemInfo['HasUsbhdd']= %s" % SystemInfo["HasUsbhdd"])
						self.hdd.append(Harddisk(device, removable))
						SystemInfo["Harddisk"] = True
						# self.partitions.append(Partition(mountpoint = self.getMountpoint(device), description = description, force_mounted, device = device))
						# print("[Harddisk] DEBUG: Partition(mountpoint=%s, description=%s, force_mounted=True, device=%s)" % (self.getMountpoint(device), description, device))
						for partition in partitions:
							description = self.getUserfriendlyDeviceName(partition, physicalDevice)
							print("[Harddisk] Found partition '%s', description='%s', device='%s'." % (partition, description, physicalDevice))
							# part = Partition(mountpoint=self.getMountpoint(partition), description=description, force_mounted=True, device=partition)
							part = Partition(mountpoint=self.getMountpoint(partition, skiproot=True), description=description, force_mounted=True, device=partition)
							self.partitions.append(part)
							# print("[Harddisk] DEBUG: Partition(mountpoint = %s, description = %s, force_mounted = True, device = %s)" % (self.getMountpoint(partition), description, partition))
							self.on_partition_list_change("add", part)
							# print("[Harddisk] DEBUG: on_partition_list_change('add', Partition(mountpoint = %s, description = %s, force_mounted = True, device = %s))" % (self.getMountpoint(partition), description, partition))
		self.hdd.sort()
		print("[Harddisk] Enumerating block devices complete.")

	def enumerateNetworkMounts(self):
		print("[Harddisk] Enumerating network mounts...")
		for entry in sorted(listdir("/media")):
			mountEntry = ospath.join("/media", entry)
			if not ospath.isdir(mountEntry):
				continue
			try:  # protect against drive being removed unexpectedly
				mounts = listdir(mountEntry)
			except IOError as err:
				print("[Harddisk] drive not accessible", err)
				continue
			if len(mounts) > 0:
				for mount in mounts:
					mountDir = ospath.join(mountEntry, mount, "")
					# print("[Harddisk] enumerateNetworkMountsNew DEBUG: mountDir = '%s', isMount = '%s'" % (mountDir, ospath.ismount(mountDir)))
					if ospath.ismount(mountDir) and mountDir not in [partition.mountpoint for partition in self.partitions]:
						print("[Harddisk] Found network mount (%s) '%s' -> '%s'." % (entry, mount, mountDir))
						self.partitions.append(Partition(mountpoint=mountDir, description=mount))
						# print("[Harddisk] DEBUG: Partition(mountpoint = %s, description = %s)" % (mountDir, mount))
					elif "/media/net" in mountEntry and ospath.exists(mountDir) and mountDir not in [partition.mountpoint for partition in self.partitions]:
						print("[Harddisk] Found network mount (%s) '%s' -> '%s'." % (entry, mount, mountDir))
						self.partitions.append(Partition(mountpoint=mountDir, description=mount))
		if ospath.ismount("/media/hdd") and "/media/hdd/" not in [partition.mountpoint for partition in self.partitions]:
			print("[Harddisk] new Network Mount being used as HDD replacement -> /media/hdd/")
			self.partitions.append(Partition(mountpoint="/media/hdd/", description="/media/hdd"))
		print("[Harddisk] Enumerating network mounts complete.")

	def getUserfriendlyDeviceName(self, device, physicalDevice):
		dev, part = self.splitDeviceName(device)
		description = readFile(ospath.join(physicalDevice, "model"))
		if description is None:
			description = readFile(ospath.join(physicalDevice, "name"))
			if description is None:
				# print("[Harddisk] Error: Couldn't read harddisk model on '%s' ('%s')!" % (device, physicalDevice))
				description = _("Device %s") % dev
		if part:  # and part != 1:  # Not wholedisk and not partition 1.
			description = "%s %s" % (description, _("(Partition %d)") % part)
		return description

	def splitDeviceName(self, devName):
		devNameLen = len(devName)
		device = devName.rstrip("0123456789")
		deviceLen = len(device)
		if devName.startswith("mmcblk"):  # This works for devices in the form: mmcblk0pX
			if device.endswith("p") and deviceLen < devNameLen:
				device = devName[0:deviceLen - 1]
				partition = int(devName[deviceLen:])
			else:
				device = devName
				partition = 0
		else:  # This works for devices in the form: sdaX, hdaX, srX or any device that has a numeric suffix.
			partition = int(devName[deviceLen:]) if deviceLen < devNameLen else 0
		# print("[Harddisk] splitDeviceName DEBUG: devName = '%s', device = '%s', partition = '%d'" % (devName, device, partition))
		return device, partition

	def getAutofsMountpoint(self, device):
		mnt = self.getMountpoint(device)
		if mnt is None:
			return ospath.join("/media", device)
		return mnt

	def getMountpoint(self, device, skiproot=None):
		dev = ospath.join("/dev", device)
		for item in getProcMounts():
			if (item[0] == dev and skiproot is None) or (item[0] == dev and skiproot is True and item[1] != "/"):
				return ospath.join(item[1], "")
		return None

	# device - Hotplug passed partition name, without /dev e.g. mmcblk1p1.
	# physDevice - Hotplug passed incorrect device path e.g. /block/mmcblk1/device - Not much use!
	# physicalDevice is the physical device path e.g. sys/block/mmcblk1/device.
	# devicePath in def is e.g. /sys/block/mmcblk1.
	# hddDev is the hdd device name e.g. mmcblk1.
	#
	def addHotplugPartition(self, device, physDevice=None):
		print("[Harddisk] Evaluating hotplug connected device...")
		print("[Harddisk] DEBUG: device = '%s', physDevice = '%s'" % (device, physDevice))
		HDDin = error = removable = isCdrom = blacklisted = False
		mediumFound = True
		hddDev, part = self.splitDeviceName(device)
		devicePath = "/sys/block/%s" % hddDev
		try:
			physicalDevice = ospath.realpath(ospath.join("/sys/block", hddDev, "device"))
		except (IOError, OSError):
			print("[Harddisk] Error: Couldn't determine physical device for device '%s'!" % hddDev)
			physicalDevice = hddDev
		description = self.getUserfriendlyDeviceName(device, physicalDevice)
		# print("[Harddisk] DEBUG: Hotplug description = '%s', devicePath = '%s', hddDev = '%s'." % (description, devicePath, hddDev))
		data = readFile(ospath.join(devicePath, "dev"))  # This is the device's major and minor device numbers.
		if data is not None:
			devMajor = int(data.split(":")[0])
			isCdrom = devMajor in opticalDisks or device.startswith("sr")
			if isCdrom:
				print("[Harddisk] Found optical disk '%s' (%s)." % (device, physicalDevice))
				self.cd = devicePath
				self.partitions.append(Partition(mountpoint=self.getMountpoint(hddDev), description=description, force_mounted=True, device=hddDev))
			else:  # Lets get to work on real HDD.
				data = readFile(ospath.join(devicePath, "removable"))
				removable = False if data is None else bool(int(data))
				for hdd in self.hdd:  # Perhaps the disk has not been removed, so don't add it again.
					# print("[Harddisk] DEBUG hddDev in hddlist. (hdd = '%s', hdd.device = '%s', hddDev = '%s')" % (hdd, hdd.device, hddDev))
					if hdd.device == hddDev:
						HDDin = True
						break
				partitions = [partition for partition in sorted(listdir(devicePath)) if partition.startswith(hddDev)]
				if SystemInfo["HasHiSi"] and devMajor == 8 and len(partitions) >= 4:
					partitions = partitions[4:]
				if HDDin is False and len(partitions) != 0:
					SystemInfo["HasUsbhdd"][device] = len(partitions)
					print("[Harddisk]2 SystemInfo['HasUsbhdd']= %s" % SystemInfo["HasUsbhdd"])
					self.hdd.append(Harddisk(hddDev, removable))
					# print("[Harddisk] DEBUG: Add hotplug HDD device in hddlist. (device = '%s', hdd.device = '%s', hddDev = '%s')" % (device, hdd.device, hddDev))
					self.hdd.sort()
					SystemInfo["Harddisk"] = True
				# self.partitions.append(Partition(mountpoint = self.getMountpoint(hddDev), description = description, force_mounted = True, device = hddDev))
				# print("[Harddisk] DEBUG add hddDev: Partition(mountpoint=%s, description=%s, force_mounted=True, hddDev=%s)" % (self.getMountpoint(device), description, hddDev))
				for partition in partitions:
					description = self.getUserfriendlyDeviceName(partition, physicalDevice)
					print("[Harddisk] Found partition '%s', description = '%s', device = '%s'." % (partition, description, physicalDevice))
					part = Partition(mountpoint=self.getMountpoint(partition), description=description, force_mounted=True, device=partition)  # add in partition
					# print("[Harddisk] DEBUG add partition: Part(mountpoint = %s, description = %s, force_mounted =  True, device = %s)" % (self.getMountpoint(partition), description, partition))
					self.partitions.append(part)
					if part.mountpoint:  # Plugins won't expect unmounted devices.
						self.on_partition_list_change("add", part)
						# print("[Harddisk] DEBUG: on_partition_list_change('add', Partition(mountpoint = %s, description = %s, force_mounted = True, device = %s))" % (self.getMountpoint(partition), description, partition))
		# print("[Harddisk] Hotplug connection complete.")
		return error, blacklisted, removable, isCdrom, self.partitions, mediumFound  # Return for hotplug legacy code.

	def removeHotplugPartition(self, device):
		print("[Harddisk] Evaluating hotplug disconnected device...")
		hddDev, part = self.splitDeviceName(device)  # Separate the device from the partition.
		for partition in self.partitions:
			if partition.device is None:
				continue
			pDevice = partition.device
			# print("[Harddisk] DEBUG: Partition is in self.partitions.  (partition.device = '%s', device = '%s')" % (pDevice, device))
			if pDevice.startswith(hddDev):  # This is the disk's partition for which we are looking.
				print("[Harddisk] Unmounting partition '%s'." % device)
				self.partitions.remove(partition)  # Remove partition.
				if partition.mountpoint:  # Plugins won't expect unmounted devices.
					self.on_partition_list_change("remove", partition)
		for hdd in self.hdd:
			if hdd.device == hddDev:  # This is the storage device for which we are looking.
				print("[Harddisk] Removing storage device '%s'." % hddDev)
				# print("[Harddisk] DEBUG: Storage device is in self.hdd.  (hdd.device = '%s', device = '%s', hddDev = '%s')" % (hdd.device, device, hddDev))
				hdd.stop()  # Stop the disk.
				self.hdd.remove(hdd)  # Remove the disk.
				break
		SystemInfo["Harddisk"] = len(self.hdd) > 0
		print("[Harddisk] Hotplug disconnection complete.")

	def HDDCount(self):
		return len(self.hdd)

	def HDDList(self):
		list = []
		for hd in self.hdd:
			hdd = "%s - %s" % (hd.model(), hd.bus())
			cap = hd.capacity()
			if cap != "":
				hdd += " (%s)" % cap
			list.append((hdd, hd))
		# print("[Harddisk] HDDlist = %s." % list)
		return list

	def getCD(self):
		return self.cd

	def getMountedPartitions(self, onlyhotplug=False, mounts=None):
		if mounts is None:
			mounts = getProcMounts()
		parts = [partition for partition in self.partitions if (partition.is_hotplug or not onlyhotplug) and partition.mounted(mounts)]
		devs = set([partition.device for partition in parts])
		for devname in devs.copy():
			if not devname:
				continue
			dev, part = self.splitDeviceName(devname)
			if part and dev in devs:  # If this is a partition and we still have the wholedisk, remove wholedisk.
				devs.remove(dev)
		# Return all devices which are not removed due to being a wholedisk when a partition exists.
		return [partition for partition in parts if not partition.device or partition.device in devs]

	def addMountedPartition(self, device, desc):
		for partition in self.partitions:
			if partition.mountpoint == device:
				return  # Already_mounted.
		self.partitions.append(Partition(mountpoint=device, description=desc))

	def removeMountedPartition(self, mountpoint):
		for partition in self.partitions[:]:
			if partition.mountpoint == mountpoint:
				self.partitions.remove(partition)
				self.on_partition_list_change("remove", partition)

	def setDVDSpeed(self, device, speed=0):
		if not device.startswith(ossep):
			device = ospath.join("/dev", device)
		try:
			with open(device, "wb") as fd:
				ioctl(fd.fileno(), int(0x5322), speed)
		except (IOError, OSError) as err:
			print("[Harddisk] Error: Failed to set '%s' speed to '%s':" % (device, speed), err)


class UnmountTask(Components.Task.LoggingTask):
	def __init__(self, job, hdd):
		Components.Task.LoggingTask.__init__(self, job, _("Unmount."))
		print("[Harddisk] UnMountTask - init")
		self.hdd = hdd
		self.mountpoints = []

	def prepare(self):
		print("[Harddisk] UnMountTask - prepare")
		try:
			dev = self.hdd.disk_path.split(ossep)[-1]
			print("[Harddisk] [UnMountTask - prepare]", dev)
			open("/dev/nomount.%s" % dev, "wb").close()
		except (IOError, OSError) as err:
			print("[Harddisk] UnmountTask - Error: Failed to create /dev/nomount file:", err)
		self.setTool("umount")
		self.args.append("-f")
		for dev in self.hdd.enumMountDevices():
			self.args.append(dev)
			self.postconditions.append(Components.Task.ReturncodePostcondition())
			self.mountpoints.append(dev)
		if not self.mountpoints:
			print("[Harddisk] UnmountTask - No mountpoints found?")
			self.cmd = "true"
			self.args = [self.cmd]

	def afterRun(self):
		for path in self.mountpoints:
			try:
				rmdir(path)
			except (IOError, OSError) as err:
				print("[Harddisk] UnmountTask - Error: Failed to remove path '%s':" % path, err)


class MountTask(Components.Task.LoggingTask):
	def __init__(self, job, hdd):
		Components.Task.LoggingTask.__init__(self, job, _("Mount."))
		self.hdd = hdd

	def prepare(self):
		print("[Harddisk] MountTask - prepare")
		try:
			dev = self.hdd.disk_path.split(ossep)[-1]
			unlink("/dev/nomount.%s" % dev)
		except (IOError, OSError) as err:
			print("[Harddisk] MountTask - Error: Failed to remove '/dev/nomount' file:", err)
		if self.hdd.mount_device is None:
			dev = self.hdd.partitionPath("1")  # Try mounting through fstab first.
		else:
			dev = self.hdd.mount_device  # If previously mounted, use the same spot.
		try:
			with open("/etc/fstab", "r") as fd:
				for line in fd.readlines():
					parts = line.strip().split(" ")
					fspath = ospath.realpath(parts[0])
					if ospath.realpath(fspath) == dev:
						self.setCmdline("mount -t auto %s" % fspath)
						self.postconditions.append(Components.Task.ReturncodePostcondition())
						return
		except (IOError, OSError) as err:
			print("[Harddisk] MountTask - Error: Failed to read '/etc/fstab' file:", err)
		# Device is not in fstab.
		# We can let udev do the job, re-read the partition table.
		# Sorry for the sleep 2 hack...
		print("[Harddisk] MountTask - let udev complete the job")
		self.setCmdline("sleep 2; hdparm -z %s" % self.hdd.disk_path)
		self.postconditions.append(Components.Task.ReturncodePostcondition())


class MkfsTask(Components.Task.LoggingTask):
	def prepare(self):
		self.fsck_state = None

	def processOutput(self, data):
		data = data.decode()
		print("[Harddisk] MkfsTask - [Mkfs]", data)
		if "Writing inode tables:" in data:
			self.fsck_state = "inode"
		elif "Creating journal" in data:
			self.fsck_state = "journal"
			self.setProgress(80)
		elif "Writing superblocks " in data:
			self.setProgress(95)
		elif self.fsck_state == "inode":
			if "/" in data:
				try:
					d = data.strip(" \x08\r\n").split("/", 1)
					if "\x08" in d[1]:
						d[1] = d[1].split("\x08", 1)[0]
					self.setProgress(80 * int(d[0]) / int(d[1]))
				except Exception as err:
					print("[Harddisk] MkfsTask - [Mkfs] Error:", err)
				return  # Don't log the progess.
		self.log.append(data)


harddiskmanager = HarddiskManager()
