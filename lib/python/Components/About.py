from sys import modules, version_info
from os import path as ospath
from time import time
from Tools.Directories import fileExists, resolveFilename, SCOPE_LIBDIR
from os.path import join as pathjoin
import socket
import fcntl
import struct

from enigma import getEnigmaVersionString


def getVersionString():
	from Components.SystemInfo import SystemInfo
	return SystemInfo["imageversion"]


def getFlashDateString():
	if ospath.isfile('/etc/install'):
		with open("/etc/install", "r") as f:
			return _formatDate(f.read())
	else:
		return _("unknown")


def driversDate():
	from Components.SystemInfo import SystemInfo
	return _formatDate(SystemInfo["driversdate"])


def getLastUpdate():
	return _formatDate(getEnigmaVersionString().replace("-", ""))


def _formatDate(Date):
	# expected input = "YYYYMMDD"
	if len(Date) != 8 or not Date.isnumeric():
		return _("unknown")
	from Components.config import config
	return config.usage.date.dateFormatAbout.value % {"year": Date[0:4], "month": Date[4:6], "day": Date[6:8]}


def getGStreamerVersionString():
	try:
		from glob import glob
		gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer[0-9].[0-9].control")[0], "r") if x.startswith("Version:")][0]
		return "%s" % gst[1].split("+")[0].split("-")[0].replace("\n", "")
	except:
		return _("unknown")


def getKernelVersionString():
	try:
		return open("/proc/version").read().split(" ", 3)[2].split("-", 1)[0]
	except:
		return _("unknown")


def getIsBroadcom():
	try:
		for x in open("/proc/cpuinfo").readlines():
			x = x.split(": ")
			if len(x) > 1 and (x[0].startswith("Hardware") and x[1].split(" ")[0] == "Broadcom" or x[0].startswith("system type") and x[1].startswith("BCM")):
				return True
	except:
		pass
	return False


def getModel():  # Because we can't call SystemInfo here
	if fileExists(f := pathjoin(resolveFilename(SCOPE_LIBDIR), "enigma.info")):
		return (m := [x.split("=")[1].strip() for x in open(f).readlines() if x.startswith("machinebuild=")]) and m[0] or None


def getChipSetString():
	try:
		return str(open("/proc/stb/info/chipset").read().lower().replace("\n", "").replace("brcm", "").replace("bcm", ""))
	except:
		if getModel() in ("'dm900'", "'dm920'"):
			return "7252s"
		return "unknown"


def getCPUSpeedMHzInt():
	cpu_speed = 0
	try:
		for x in open("/proc/cpuinfo").readlines():
			x = x.split(": ")
			if len(x) > 1 and x[0].startswith("cpu MHz"):
				cpu_speed = float(x[1].split(" ")[0].strip())
				break
	except IOError:
		print("[About] getCPUSpeedMHzInt, /proc/cpuinfo not available")

	if cpu_speed == 0:
		from Components.SystemInfo import MODEL
		if MODEL in ("h7", "hd51", "sf4008", "osmio4k", "osmio4kplus", "osmini4k"):
			try:
				import binascii
				with open("/sys/firmware/devicetree/base/cpus/cpu@0/clock-frequency", "rb") as f:
					clockfrequency = f.read()
					cpu_speed = round(int(binascii.hexlify(clockfrequency), 16) // 1000000, 1)
			except IOError:
				cpu_speed = 1700
		else:
			try:  # Solo4K sf8008
				with open("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "r") as file:
					cpu_speed = float(file.read()) // 1000
			except IOError:
				print("[About] getCPUSpeedMHzInt, /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq not available")
	return int(cpu_speed)


def getCPUSpeedString():
	cpu_speed = float(getCPUSpeedMHzInt())
	if cpu_speed > 0:
		if cpu_speed >= 1000:
			cpu_speed = "%s GHz" % str(round(cpu_speed / 1000, 1))
		else:
			cpu_speed = "%s MHz" % str(int(cpu_speed))
		return cpu_speed
	return "unknown"


def getCPUArch():
	from Components.SystemInfo import MODEL
	if MODEL.startswith("osmio4k"):
		return "ARM V7"
	if "ARM" in getCPUString():
		return getCPUString()
	return _("Mipsel")


def getCPUString():
	try:
		return [x.split(": ")[1].split(" ")[0] for x in open("/proc/cpuinfo").readlines() if x.startswith(("system type", "model name", "Processor")) and len(x.split(": ")) > 1][0]
	except:
		return _("unavailable")


def getCpuCoresInt():
	try:
		return int(open("/sys/devices/system/cpu/present").read().split("-")[1]) + 1
	except:
		return 0


def getCpuCoresString():
	cores = getCpuCoresInt()
	return {
		0: _("unavailable"),
		1: _("Single core"),
		2: _("Dual core"),
		4: _("Quad core"),
		8: _("Octo core")
	}.get(cores, _("%d cores") % cores)


def _ifinfo(sock, addr, ifname):
	iface = struct.pack('256s', bytes(ifname[:15], 'utf-8'))
	info = fcntl.ioctl(sock.fileno(), addr, iface)
	if addr == 0x8927:
		return ''.join(['%02x:' % ord(chr(char)) for char in info[18:24]])[:-1].upper()
	else:
		return socket.inet_ntoa(info[20:24])


def getIfConfig(ifname):
	ifreq = {"ifname": ifname}
	infos = {}
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	# offsets defined in /usr/include/linux/sockios.h on linux 2.6
	infos["addr"] = 0x8915  # SIOCGIFADDR
	infos["brdaddr"] = 0x8919  # SIOCGIFBRDADDR
	infos["hwaddr"] = 0x8927  # SIOCSIFHWADDR
	infos["netmask"] = 0x891b  # SIOCGIFNETMASK
	try:
		for k, v in infos.items():
			ifreq[k] = _ifinfo(sock, v, ifname)
	except:
		pass
	sock.close()
	print("[About] ifreq: ", ifreq)
	return ifreq


def getIfTransferredData(ifname):
	with open("/proc/net/dev", "r") as f:
		for line in f:
			if ifname in line:
				data = line.split("%s:" % ifname)[1].split()
				rx_bytes, tx_bytes = (data[0], data[8])
				return rx_bytes, tx_bytes


def getPythonVersionString():
	return "%s.%s.%s" % (version_info.major, version_info.minor, version_info.micro)


def getBoxUptime():
	try:
		with open("/proc/uptime", "rb") as f:
			seconds = int(f.readline().split('.')[0])
		return formatUptime(seconds)
	except:
		return ''


def getEnigmaUptime():
	try:
		seconds = int(time() - ospath.getmtime("/etc/enigma2/profile"))
		return formatUptime(seconds)
	except:
		return ''


def formatUptime(seconds):
	out = ''
	if seconds > 86400:
		days = int(seconds / 86400)
		out += (_("1 day") if days == 1 else _("%d days") % days) + ", "
	if seconds > 3600:
		hours = int((seconds % 86400) / 3600)
		out += (_("1 hour") if hours == 1 else _("%d hours") % hours) + ", "
	if seconds > 60:
		minutes = int((seconds % 3600) / 60)
		out += (_("1 minute") if minutes == 1 else _("%d minutes") % minutes) + " "
	else:
		out += (_("1 second") if seconds == 1 else _("%d seconds") % seconds) + " "
	return out


# For modules that do "from About import about"
about = modules[__name__]
