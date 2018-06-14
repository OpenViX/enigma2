from Components.SystemInfo import SystemInfo
from Components.Console import Console
import os
#		#default layout for 				Mut@nt HD51						& Giga4K
# boot								/dev/mmcblk0p1						/dev/mmcblk0p1
# STARTUP_1 			Image 1: boot emmcflash0.kernel1 'root=/dev/mmcblk0p3 rw rootwait'	boot emmcflash0.kernel1: 'root=/dev/mmcblk0p5 
# STARTUP_2 			Image 2: boot emmcflash0.kernel2 'root=/dev/mmcblk0p5 rw rootwait'      boot emmcflash0.kernel2: 'root=/dev/mmcblk0p7
# STARTUP_3		        Image 3: boot emmcflash0.kernel3 'root=/dev/mmcblk0p7 rw rootwait'	boot emmcflash0.kernel3: 'root=/dev/mmcblk0p9
# STARTUP_4		        Image 4: boot emmcflash0.kernel4 'root=/dev/mmcblk0p9 rw rootwait'	NOT IN USE due to Rescue mode in mmcblk0p3

def GetCurrentImage():
	return SystemInfo["canMultiBoot"] and (int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read().replace('\0', '').split('mmcblk0p')[1].split(' ')[0])-SystemInfo["canMultiBoot"][0])/2

def GetCurrentImageMode():
	return SystemInfo["canMultiBoot"] and SystemInfo["canMode12"] and int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read().replace('\0', '').split('=')[-1])

class GetImagelist():
	MOUNT = 0
	UNMOUNT = 1

	def __init__(self, callback):
		if SystemInfo["canMultiBoot"]:
			(self.firstslot, self.numberofslots) = SystemInfo["canMultiBoot"]
			self.callback = callback
			self.imagelist = {}
			if not os.path.isdir('/tmp/testmount'):
				os.mkdir('/tmp/testmount')
			self.container = Console()
			self.slot = 1
			self.phase = self.MOUNT
			self.run()
		else:	
			callback({})
	
	def run(self):
		self.container.ePopen('mount /dev/mmcblk0p%s /tmp/testmount' % str(self.slot * 2 + self.firstslot) if self.phase == self.MOUNT else 'umount /tmp/testmount', self.appClosed)
			
	def appClosed(self, data, retval, extra_args):
		if retval == 0 and self.phase == self.MOUNT:
			BuildVersion = "  "
			Build = " "
			Date = " "
			if os.path.isfile("/tmp/testmount/usr/bin/enigma2") and os.path.isfile('/tmp/testmount/etc/image-version'):
				file = open('/tmp/testmount/etc/image-version', 'r')
				lines = file.read().splitlines()
				for x in lines:
					splitted = x.split('= ')
					if len(splitted) > 1:
						if splitted[0].startswith("Build"):
							Build = splitted[1].split(' ')[0]
				file.close()
			if os.path.isfile('/tmp/testmount/etc/version') and Build == " ":
				version = open("/tmp/testmount/etc/version","r").read()
				Date = "%s-%s-%s" % (version[6:8], version[4:6], version[2:4])
			BuildVersion = " " + Build + " " + Date
			if os.path.isfile("/tmp/testmount/usr/bin/enigma2"):
				self.imagelist[self.slot] =  { 'imagename': open("/tmp/testmount/etc/issue").readlines()[-2].capitalize().strip()[:-6] + BuildVersion}
			else:
				self.imagelist[self.slot] = { 'imagename': _("Empty slot")}
			self.phase = self.UNMOUNT
			self.run()
		elif self.slot < self.numberofslots:
			self.slot += 1
			self.imagelist[self.slot] = { 'imagename': _("Empty slot")}
			self.phase = self.MOUNT
			self.run()
		else:
			self.container.killAll()
			if not os.path.ismount('/tmp/testmount'):
				os.rmdir('/tmp/testmount')
			self.callback(self.imagelist)


class WriteStartup():

	def __init__(self, Contents, callback):
		self.callback = callback
		self.container = Console()
		self.slotContents = Contents
		if os.path.isdir('/tmp/startupmount'):
			self.ContainerFallback()
		else:
			os.mkdir('/tmp/startupmount')
			self.container.ePopen('mount /dev/mmcblk0p1 /tmp/startupmount', self.ContainerFallback)

	
	def ContainerFallback(self, data=None, retval=None, extra_args=None):
		self.container.killAll()
#	If GigaBlue then slotContents = slot, use slot to read STARTUP_slot
#	If multimode and bootmode 1 or 12, then slotContents is STARTUP, so just write it to boot STARTUP.			
		if 'coherent_poll=2M' in open("/proc/cmdline", "r").read():
			import shutil
			shutil.copyfile("/tmp/startupmount/STARTUP_%s" % self.slotContents, "/tmp/startupmount/STARTUP")
		else:
			open('/tmp/startupmount/STARTUP', 'w').write(self.slotContents)
		self.callback()
