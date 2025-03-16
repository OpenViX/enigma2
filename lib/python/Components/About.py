from fcntl import ioctl
from socket import AF_INET, SOCK_DGRAM, inet_ntoa, socket
from struct import pack

from os import path as ospath
from sys import modules
from time import time


def getKernelVersionString():  # output from this function may not match kernel version from enigma.info (BoxInfo). This version is more accurate.
	try:
		return open("/proc/version").read().split(" ", 3)[2].split("-", 1)[0]
	except:
		return _("unknown")


def getCPUArch(MODEL):
	if MODEL.startswith("osmio4k"):
		CPUArch = "ARM V7"
	elif "ARM" in getCPUString():
		CPUArch = getCPUString()
	else:
		CPUArch = _("Mipsel")
	return [CPUArch, getCPUSpeedString(MODEL), getCpuCoresString()]


def getChipSetString(MODEL):
	try:
		return str(open("/proc/stb/info/chipset").read().lower().replace("\n", "").replace("brcm", "").replace("bcm", ""))
	except:
		if MODEL in ("dm900", "dm920"):
			return "7252s"
		else:
			return "unknown"


def getCPUSpeedMHzInt(MODEL):
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
		if MODEL in ("h7", "hd51", "sf4008", "osmio4k", "osmio4kplus", "osmini4k"):
			try:
				import binascii
				with open("/sys/firmware/devicetree/base/cpus/cpu@0/clock-frequency", "rb") as f:
					clockfrequency = f.read()
					cpu_speed = round(int(binascii.hexlify(clockfrequency), 16) // 1000000, 1)
			except IOError:
				cpu_speed = 1700
		elif MODEL in ('hzero', 'h8', 'sfx6008', 'sfx6018'):
			cpu_speed = 1200
		else:
			try:  # Solo4K sf8008
				with open("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "r") as file:
					cpu_speed = float(file.read()) // 1000
			except IOError:
				print("[About] getCPUSpeedMHzInt, /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq not available")
	return int(cpu_speed)


def getCPUSpeedString(MODEL):
	cpu_speed = float(getCPUSpeedMHzInt(MODEL))
	if cpu_speed > 0:
		if cpu_speed >= 1000:
			cpu_speed = f"{str(round(cpu_speed / 1000, 1))} GHz"
		else:
			cpu_speed = f"{str(int(cpu_speed))} MHz"
		return cpu_speed
	return "unknown"


def getCPUString():
	try:
		return [x.split(": ")[1].split(" ")[0] for x in open("/proc/cpuinfo").readlines() if x.startswith(("system type", "model name", "Processor")) and len(x.split(": ")) > 1][0]
	except:
		return _("unavailable")


def getKernelVersionString():  # required by OpenWebif
	try:
		return open("/proc/version").read().split(" ", 3)[2].split("-", 1)[0]
	except:
		return _("unknown")


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
	iface = pack('256s', bytes(ifname[:15], 'utf-8'))
	info = ioctl(sock.fileno(), addr, iface)
	if addr == 0x8927:
		return ''.join(['%02x:' % ord(chr(char)) for char in info[18:24]])[:-1].upper()
	else:
		return inet_ntoa(info[20:24])


def getIfConfig(ifname):
	ifreq = {"ifname": ifname}
	infos = {}
	sock = socket(AF_INET, SOCK_DGRAM)
	# Offsets defined in /usr/include/linux/sockios.h on linux 2.6.
	infos["addr"] = 0x8915  # SIOCGIFADDR
	infos["brdaddr"] = 0x8919  # SIOCGIFBRDADDR
	infos["hwaddr"] = 0x8927  # SIOCSIFHWADDR
	infos["netmask"] = 0x891b  # SIOCGIFNETMASK
	try:
		for k, v in infos.items():
			ifreq[k] = _ifinfo(sock, v, ifname)
	except Exception as ex:
		print(f"[About] getIfConfig Ex: {str(ex)}")
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
