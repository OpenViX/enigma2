from sys import modules, version_info
import socket
import fcntl
import struct

from boxbranding import getImageVersion, getMachineBuild, getBoxType


def getVersionString():
	return getImageVersion()


def getFlashDateString():
	try:
		with open("/etc/install", "r") as f:
			flashdate = f.read()
			return flashdate
	except:
		return _("unknown")


def getEnigmaVersionString():
	return getImageVersion()


def getGStreamerVersionString():
	try:
		from glob import glob
		gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer[0-9].[0-9].control")[0], "r") if x.startswith("Version:")][0]
		return "%s" % gst[1].split("+")[0].replace("\n", "")
	except:
		return _("unknown")


def getKernelVersionString():
	try:
		with open("/proc/version", "r") as f:
			kernelversion = f.read().split(" ", 4)[2].split("-", 2)[0]
			return kernelversion
	except:
		return _("unknown")


def getIsBroadcom():
	try:
		with open("/proc/cpuinfo", "r") as file:
			lines = file.readlines()
			for x in lines:
				splitted = x.split(": ")
				if len(splitted) > 1:
					splitted[1] = splitted[1].replace("\n", "")
					if splitted[0].startswith("Hardware"):
						system = splitted[1].split(" ")[0]
					elif splitted[0].startswith("system type"):
						if splitted[1].split(" ")[0].startswith("BCM"):
							system = "Broadcom"
		if "Broadcom" in system:
			return True
		else:
			return False
	except:
		return False


def getChipSetString():
	try:
		with open("/proc/stb/info/chipset", "r") as f:
			return str(f.read().lower().replace("\n", "").replace("brcm", "").replace("bcm", ""))
	except IOError:
		return _("unavailable")


def getCPUSpeedMHzInt():
	cpu_speed = 0
	try:
		with open("/proc/cpuinfo", "r") as file:
			lines = file.readlines()
			for x in lines:
				splitted = x.split(": ")
				if len(splitted) > 1:
					splitted[1] = splitted[1].replace("\n", "")
					if splitted[0].startswith("cpu MHz"):
						cpu_speed = float(splitted[1].split(" ")[0])
						break
	except IOError:
		print("[About] getCPUSpeedMHzInt, /proc/cpuinfo not available")

	if cpu_speed == 0:
		if getMachineBuild() in ("h7", "hd51", "sf4008"):
			try:
				import binascii
				with open("/sys/firmware/devicetree/base/cpus/cpu@0/clock-frequency", "rb") as f:
					clockfrequency = f.read()
					cpu_speed = round(int(binascii.hexlify(clockfrequency), 16) // 1000000, 1)
			except IOError:
				cpu_speed = 1700
		else:
			try: # Solo4K sf8008
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
	return _("unavailable")


def getCPUArch():
	if getBoxType() in ("osmio4k", ):
		return "ARM V7"
	if "ARM" in getCPUString():
		return getCPUString()
	return _("Mipsel")


def getCPUString():
	system = _("unavailable")
	try:
		with open("/proc/cpuinfo", "r") as file:
			lines = file.readlines()
			for x in lines:
				splitted = x.split(": ")
				if len(splitted) > 1:
					splitted[1] = splitted[1].replace("\n", "")
					if splitted[0].startswith("system type"):
						system = splitted[1].split(" ")[0]
					elif splitted[0].startswith("model name"):
						system = splitted[1].split(" ")[0]
					elif splitted[0].startswith("Processor"):
						system = splitted[1].split(" ")[0]
			return system
	except IOError:
		return _("unavailable")


def getCpuCoresInt():
	cores = 0
	try:
		with open("/proc/cpuinfo", "r") as file:
			lines = file.readlines()
			for x in lines:
				splitted = x.split(": ")
				if len(splitted) > 1:
					splitted[1] = splitted[1].replace("\n", "")
					if splitted[0].startswith("processor"):
						cores = int(splitted[1]) + 1
	except IOError:
		pass
	return cores


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
	infos["addr"] = 0x8915 # SIOCGIFADDR
	infos["brdaddr"] = 0x8919 # SIOCGIFBRDADDR
	infos["hwaddr"] = 0x8927 # SIOCSIFHWADDR
	infos["netmask"] = 0x891b # SIOCGIFNETMASK
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


def getEnigmaUptime():
	from time import time
	import os
	location = "/etc/enigma2/profile"
	try:
		seconds = int(time() - os.path.getmtime(location))
		return formatUptime(seconds)
	except:
		return ''


def getBoxUptime():
	try:
		f = open("/proc/uptime", "rb")
		seconds = int(f.readline().split('.')[0])
		f.close()
		return formatUptime(seconds)
	except:
		return ''


def formatUptime(seconds):
	out = ''
	if seconds > 86400:
		days = int(seconds / 86400)
		out += ("1 day" if days == 1 else "%d days" % days) + ", "
	if seconds > 3600:
		hours = int((seconds % 86400) / 3600)
		out += ("1 hour" if hours == 1 else "%d hours" % hours) + ", "
	if seconds > 60:
		minutes = int((seconds % 3600) / 60)
		out += ("1 minute" if minutes == 1 else "%d minutes" % minutes) + " "
	else:
		out += ("1 second" if seconds == 1 else "%d seconds" % seconds) + " "
	return out


def getEnigmaUptime():
	from time import time
	import os
	location = "/etc/enigma2/profile"
	try:
		seconds = int(time() - os.path.getmtime(location))
		return formatUptime(seconds)
	except:
		return ''

def getBoxUptime():
	try:
		f = open("/proc/uptime", "rb")
		seconds = int(f.readline().split('.')[0])
		f.close()
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
