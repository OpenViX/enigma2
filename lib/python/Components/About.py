# -*- coding: utf-8 -*-
import struct
import socket
import fcntl
import re
import sys
import os
import time
from Tools.HardwareInfo import HardwareInfo

from boxbranding import getBoxType, getMachineBuild, getImageType, getImageVersion

def getVersionString():
	return getImageVersionString()

def getImageVersionString():
	try:
		if os.path.isfile('/var/lib/opkg/status'):
			st = os.stat('/var/lib/opkg/status')
		tm = time.localtime(st.st_mtime)
		if tm.tm_year >= 2011:
			return time.strftime("%Y-%m-%d %H:%M:%S", tm)
	except:
		pass
	return _("unavailable")

def getFlashDateString():
	try:
		# return time.strftime(_("%Y-%m-%d %H:%M:%S"), time.localtime(os.stat("/etc/version").st_ctime))
		return time.strftime(_("%Y-%m-%d %H:%M:%S"), time.localtime(os.path.getatime("/bin")))
	except:
		return _("unknown")

def getEnigmaVersionString():
	# import enigma
	# enigma_version = enigma.getEnigmaVersionString()
	# if len(enigma_version) > 11:
	# 	enigma_version = enigma_version[:10] + " " + enigma_version[11:]
	from boxbranding import getImageVersion
	enigma_version = getImageVersion()
	if '-(no branch)' in enigma_version:
		enigma_version = enigma_version[:-12]
	return enigma_version

def getGStreamerVersionString(cpu):
	try:
		from glob import glob
		gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer[0-9].[0-9].control")[0], "r") if x.startswith("Version:")][0]
		return "%s" % gst[1].split("+")[0].replace("\n","")
	except:
		return _("Not Required") if cpu.upper().startswith('HI') else _("Not Installed")

def getKernelVersionString():
	try:
		return open("/proc/version","r").read().split(' ', 4)[2].split('-',2)[0]
	except:
		return _("unknown")

def getChipSetString():
	if getMachineBuild() in ('gb73625', ):
		return "BCM73625"
	else:
		try:
			f = open('/proc/stb/info/chipset', 'r')
			chipset = f.read()
			f.close()
			return str(chipset.lower().replace('\n','').replace('bcm','BCM').replace('brcm','BRCM').replace('sti',''))
		except IOError:
			return "unavailable"

def getCPUString():
	if getMachineBuild() in ('xc7362', ):
		return "Broadcom"
	elif getMachineBuild() in ('gbmv200', ):
		return "Hisilicon"
	#elif getMachineBuild() in ('gb73625', ):
	#	return "BCM73625"
	else:
		try:
			system = "unknown"
			file = open('/proc/cpuinfo', 'r')
			lines = file.readlines()
			for x in lines:
				splitted = x.split(': ')
				if len(splitted) > 1:
					splitted[1] = splitted[1].replace('\n','')
					if splitted[0].startswith("system type"):
						system = splitted[1].split(' ')[0]
					elif splitted[0].startswith("Processor"):
						system = splitted[1].split(' ')[0]
			file.close()
			return system
		except IOError:
			return "unavailable"

def getCpuCoresString():
	try:
		file = open('/proc/cpuinfo', 'r')
		lines = file.readlines()
		for x in lines:
			splitted = x.split(': ')
			if len(splitted) > 1:
				splitted[1] = splitted[1].replace('\n','')
				if splitted[0].startswith("processor"):
					if int(splitted[1]) > 0:
						cores = 2
					else:
						cores = 1
		file.close()
		return cores
	except IOError:
		return "unavailable"

def getHardwareTypeString():
	return HardwareInfo().get_device_string()

def getImageTypeString():
	#try:
	#       image_type = open("/etc/issue").readlines()[-2].strip()[:-6]
	#       return image_type.capitalize()
	#except:
	#       return _("undefined")
	return "%s %s" % (getImageVersion(),getImageType())

def getCPUInfoString():
	if getMachineBuild() in ('gbmv200', ):
		return "Hisilicon 1,6 GHz 4 Cores"

	try:
		cpu_count = 0
		cpu_speed = 0
		temperature = None
		for line in open("/proc/cpuinfo").readlines():
			line = [x.strip() for x in line.strip().split(":")]
			if line[0] == "system type":
				processor = line[1].split()[0]
			elif line[0] == "model name":
				processor = line[1].split()[0]
			if line[0] == "cpu MHz":
				cpu_speed = "%1.0f" % float(line[1])
			if line[0] == "processor":
				cpu_count += 1

		if not cpu_speed:
			try:
				cpu_speed = int(open("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq").read()) / 1000
			except:
				try:
					import binascii
					cpu_speed = int(int(binascii.hexlify(open('/sys/firmware/devicetree/base/cpus/cpu@0/clock-frequency', 'rb').read()), 16) / 100000000) * 100
				except:
					cpu_speed = "-"
		if os.path.isfile('/proc/stb/fp/temp_sensor_avs'):
			temperature = open("/proc/stb/fp/temp_sensor_avs").readline().replace('\n','')
		if os.path.isfile("/sys/devices/virtual/thermal/thermal_zone0/temp"):
			try:
				temperature = int(open("/sys/devices/virtual/thermal/thermal_zone0/temp").read().strip()) / 1000
			except:
				pass
		elif os.path.isfile("/proc/hisi/msp/pm_cpu"):
			try:
				temperature = re.search('temperature = (\d+) degree', open("/proc/hisi/msp/pm_cpu").read()).group(1)
			except:
				pass
		if temperature:
			return "%s %s MHz (%s) %s\xb0C" % (processor, cpu_speed, ngettext("%d core", "%d cores", cpu_count) % cpu_count, temperature)
		return "%s %s MHz (%s)" % (processor, cpu_speed, ngettext("%d core", "%d cores", cpu_count) % cpu_count)
	except:
		return _("undefined")

def getCPUSpeedString():
	if getMachineBuild() in ('gbmv200', ):
		return "1,6 GHz"
	mhz = "unavailable"
	try:
		file = open('/proc/cpuinfo', 'r')
		lines = file.readlines()
		for x in lines:
			splitted = x.split(': ')
			if len(splitted) > 1:
				splitted[1] = splitted[1].replace('\n','')
				if splitted[0].startswith("cpu MHz"):
					mhz = float(splitted[1].split(' ')[0])
					if mhz and mhz >= 1000:
						mhz = "%s GHz" % str(round(mhz / 1000,1))
					else:
						mhz = "%s MHz" % str(round(mhz,1))
		file.close()
		return mhz
	except IOError:
		return "unavailable"

def _ifinfo(sock, addr, ifname):
	iface = struct.pack('256s', ifname[:15])
	info = fcntl.ioctl(sock.fileno(), addr, iface)
	if addr == 0x8927:
		return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1].upper()
	else:
		return socket.inet_ntoa(info[20:24])

def getIfConfig(ifname):
	ifreq = {'ifname': ifname}
	infos = {}
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	# offsets defined in /usr/include/linux/sockios.h on linux 2.6
	infos['addr'] = 0x8915 # SIOCGIFADDR
	infos['brdaddr'] = 0x8919 # SIOCGIFBRDADDR
	infos['hwaddr'] = 0x8927 # SIOCSIFHWADDR
	infos['netmask'] = 0x891b # SIOCGIFNETMASK
	try:
		for k,v in infos.items():
			print infos.items()
			ifreq[k] = _ifinfo(sock, v, ifname)
	except:
		pass
	sock.close()
	return ifreq

def getIfTransferredData(ifname):
	f = open('/proc/net/dev', 'r')
	for line in f:
		if ifname in line:
			data = line.split('%s:' % ifname)[1].split()
			rx_bytes, tx_bytes = (data[0], data[8])
			f.close()
			return rx_bytes, tx_bytes

def getDriverInstalledDate():
	try:
		from glob import glob
		try:
			driver = [x.split("-")[-2:-1][0][-8:] for x in open(glob("/var/lib/opkg/info/*-dvb-modules-*.control")[0], "r") if x.startswith("Version:")][0]
			return "%s-%s-%s" % (driver[:4], driver[4:6], driver[6:])
		except:
			driver = [x.split("Version:") for x in open(glob("/var/lib/opkg/info/*-dvb-proxy-*.control")[0], "r") if x.startswith("Version:")][0]
			return "%s" % driver[1].replace("\n","")
	except:
		return _("unknown")

def getPythonVersionString():
	try:
		import commands
		status, output = commands.getstatusoutput("python -V")
		return output.split(' ')[1]
	except:
		return _("unknown")

def GetIPsFromNetworkInterfaces():
	import socket
	import fcntl
	import struct
	import array
	import sys
	is_64bits = sys.maxsize > 2**32
	struct_size = 40 if is_64bits else 32
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	max_possible = 8 # initial value
	while True:
		_bytes = max_possible * struct_size
		names = array.array('B')
		for i in range(0, _bytes):
			names.append(0)
		outbytes = struct.unpack('iL', fcntl.ioctl(
			s.fileno(),
			0x8912,  # SIOCGIFCONF
			struct.pack('iL', _bytes, names.buffer_info()[0])
		))[0]
		if outbytes == _bytes:
			max_possible *= 2
		else:
			break
	namestr = names.tostring()
	ifaces = []
	for i in range(0, outbytes, struct_size):
		iface_name = bytes.decode(namestr[i:i + 16]).split('\0', 1)[0].encode('ascii')
		if iface_name != 'lo':
			iface_addr = socket.inet_ntoa(namestr[i + 20:i + 24])
			ifaces.append((iface_name, iface_addr))
	return ifaces

def getBoxUptime():
	try:
		time = ''
		f = open("/proc/uptime", "rb")
		secs = int(f.readline().split('.')[0])
		f.close()
		if secs > 86400:
			days = secs / 86400
			secs = secs % 86400
			time = ngettext("%d day","%d days", days) % days + " "
		h = secs / 3600
		m = (secs % 3600) / 60
		time += ngettext("%d hour", "%d hours", h) % h + " "
		time += ngettext("%d minute", "%d minutes", m) % m
		return "%s" % time
	except:
		return '-'

# For modules that do "from About import about"
about = sys.modules[__name__]
