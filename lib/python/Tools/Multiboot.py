from Components.SystemInfo import SystemInfo
from Components.Console import Console
from boxbranding import getMachineMtdRoot
import os, time
import shutil
import subprocess

#		#default layout for 				Mut@nt HD51						 Giga4K						SF8008
# boot								/dev/mmcblk0p1						/dev/mmcblk0p1				/dev/mmcblk0p3
# STARTUP_1 			Image 1: boot emmcflash0.kernel1 'root=/dev/mmcblk0p3 rw rootwait'	boot emmcflash0.kernel1: 'root=/dev/mmcblk0p5		boot emmcflash0.kernel 'root=/dev/mmcblk0p13 
# STARTUP_2 			Image 2: boot emmcflash0.kernel2 'root=/dev/mmcblk0p5 rw rootwait'      boot emmcflash0.kernel2: 'root=/dev/mmcblk0p7		boot usb0.sda1 'root=/dev/sda2
# STARTUP_3		        Image 3: boot emmcflash0.kernel3 'root=/dev/mmcblk0p7 rw rootwait'	boot emmcflash0.kernel3: 'root=/dev/mmcblk0p9		boot usb0.sda3 'root=/dev/sda4
# STARTUP_4		        Image 4: boot emmcflash0.kernel4 'root=/dev/mmcblk0p9 rw rootwait'	NOT IN USE due to Rescue mode in mmcblk0p3		NOT IN USE due to only 4 partitions on SDcard

def GetCurrentImage():
	f = open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read()
	if "%s" %(SystemInfo["canMultiBoot"][2]) in f:
		return SystemInfo["canMultiBoot"] and (int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read().replace('\0', '').split('%s' %(SystemInfo["canMultiBoot"][2]))[1].split(' ')[0])-SystemInfo["canMultiBoot"][0])/2
	else:
		return 0	# if multiboot media not in SystemInfo["canMultiBoot"], then assumes using SDcard and mmc is in 1st slot so tell caller with 0 return 

def GetCurrentImageMode():
	return SystemInfo["canMultiBoot"] and SystemInfo["canMode12"] and int(open('/sys/firmware/devicetree/base/chosen/bootargs', 'r').read().replace('\0', '').split('=')[-1])

class GetImagelist():
	MOUNT = 0
	UNMOUNT = 1
	NoRun = 0		# receivers only uses 1 media for multiboot
	FirstRun = 1		# receiver uses eMMC and SD card for multiboot - so handle SDcard slots 1st via SystemInfo(canMultiBoot)
	LastRun = 2		# receiver uses eMMC and SD card for multiboot - and then handle eMMC (currently one time)

	def __init__(self, callback):
		if SystemInfo["canMultiBoot"]:
			(self.firstslot, self.numberofslots, self.mtdboot) = SystemInfo["canMultiBoot"]
			self.callback = callback
			self.imagelist = {}
			if not os.path.isdir('/tmp/testmount'):
				os.mkdir('/tmp/testmount')
			self.container = Console()
			self.slot = 1
			self.slot2 = 1
			if SystemInfo["HasSDmmc"]:
				self.SDmmc = self.FirstRun	# process SDcard slots
			else:
				self.SDmmc = self.NoRun		# only mmc slots
			self.phase = self.MOUNT
			self.part = SystemInfo["canMultiBoot"][2]	# pick up slot type
			self.run()
		else:	
			callback({})
	
	def run(self):
		if self.SDmmc == self.LastRun:
			self.part2 = getMachineMtdRoot()	# process mmc slot
			self.slot2 = 1
		else:
			self.part2 = "%s" %(self.part + str(self.slot * 2 + self.firstslot))
			if self.SDmmc == self.FirstRun:
				self.slot2 += 1			# allow for mmc slot"
		if self.phase == self.MOUNT:
			self.imagelist[self.slot2] = { 'imagename': _("Empty slot"), 'part': '%s' %self.part2 }
		self.container.ePopen('mount /dev/%s /tmp/testmount' %self.part2 if self.phase == self.MOUNT else 'umount /tmp/testmount', self.appClosed)

	def appClosed(self, data, retval, extra_args):
		if retval == 0 and self.phase == self.MOUNT:
			BuildVersion = "  "	
			Build = " "	#ViX Build No.#
			Dev = " "	#ViX Dev No.#
			Creator = " " 	#Openpli Openvix Openatv etc #
			Date = " "	
			BuildType = " "	#release etc #
			if os.path.isfile("/tmp/testmount/usr/bin/enigma2"):
 				if  os.path.isfile('/tmp/testmount/etc/issue'):
					Creator = open("/tmp/testmount/etc/issue").readlines()[-2].capitalize().strip()[:-6].replace("-release", " rel")
					if Creator.startswith("Openpli"):
						build = [x.split("-")[-2:-1][0][-8:] for x in open("/tmp/testmount/var/lib/opkg/info/openpli-bootlogo.control").readlines() if x.startswith("Version:")]
						Date = "%s-%s-%s" % (build[0][6:], build[0][4:6], build[0][2:4])
						BuildVersion = "%s %s" % (Creator, Date)
					elif Creator.startswith("Openvix"):
						reader = boxbranding_reader()
						BuildType = reader.getImageType()
						Build = reader.getImageBuild()
						Dev = BuildType != "release" and " %s" % reader.getImageDevBuild() or ''
						BuildVersion = "%s %s %s %s" % (Creator, BuildType[0:3], Build, Dev)
					else:
						st = os.stat('/tmp/testmount/var/lib/opkg/status')
						tm = time.localtime(st.st_mtime)
						if tm.tm_year >= 2011:
							Date = time.strftime("%d-%m-%Y", tm).replace("-20", "-")
						BuildVersion = "%s rel %s" % (Creator, Date)
				self.imagelist[self.slot2] =  { 'imagename': '%s' %BuildVersion, 'part': '%s' %self.part2 }
			self.phase = self.UNMOUNT
			self.run()
		elif self.slot < self.numberofslots:
			self.slot += 1
			self.slot2 = self.slot
			self.phase = self.MOUNT
			self.run()
		elif self.SDmmc == self.FirstRun:
			self.phase = self.MOUNT
			self.SDmmc = self.LastRun	# process mmc slot
			self.run()
		else:
			self.container.killAll()
			if not os.path.ismount('/tmp/testmount'):
				os.rmdir('/tmp/testmount')
			self.callback(self.imagelist)


class boxbranding_reader:		# many thanks to Huevos for creating this reader - well beyond my skill levels! 
	def __init__(self):
		self.branding_path = "/tmp/testmount/usr/lib/enigma2/python/"
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

	def readBrandingFile(self): # reads boxbranding.so and updates self.output
		output = eval(subprocess.check_output(['python', self.tmp_path + self.helper_file]))
		if output:
			for att in self.output.keys():
				self.output[att] = output[att]

	def addBrandingMethods(self): # this creates reader.getBoxType(), reader.getImageDevBuild(), etc
		l =  {}                
		for att in self.output.keys():
			exec("def %s(self): return self.output['%s']" % (att, att), None, l)
		for name, value in l.items():
			setattr(boxbranding_reader, name, value)

	def createHelperFile(self):
		f = open(self.tmp_path + self.helper_file, "w+")
		f.write(self.helperFileContent())
		f.close()

	def copyBrandingFile(self):
		shutil.copy2(self.branding_path + self.branding_file, self.tmp_path + self.branding_file)

	def removeHelperFile(self):
		self.removeFile(self.tmp_path + self.helper_file)

	def removeBrandingFile(self):
		self.removeFile(self.tmp_path + self.branding_file)

	def removeFile(self, toRemove):
			if os.path.isfile(toRemove):
				os.remove(toRemove)

	def helperFileContent(self):
		eol = "\n"
		out = []
		out.append("try:%s" % eol)
		out.append("\timport boxbranding%s" % eol)
		out.append("\toutput = {%s" % eol)
		for att in self.output.keys():
			out.append('\t\t"%s": boxbranding.%s(),%s' % (att, att, eol))
		out.append("\t}%s" % eol)
		out.append("except:%s" % eol)
		out.append("\t\toutput = None%s" % eol)
		out.append("print output%s" % eol)
		return ''.join(out)


class EmptySlot():
	MOUNT = 0
	UNMOUNT = 1
	def __init__(self, Contents, callback):
		self.callback = callback
		self.container = Console()
		(self.firstslot, self.numberofslots, self.mtdboot) = SystemInfo["canMultiBoot"]
		self.slot = Contents
		if not os.path.isdir('/tmp/testmount'):
			os.mkdir('/tmp/testmount')
		if SystemInfo["HasSDmmc"]:			# allow for mmc & SDcard in passed slot number, so SDcard slot -1
			self.slot -= 1
		self.part = "%s%s" %(self.mtdboot, str(self.slot * 2 + self.firstslot))
		if SystemInfo["HasSDmmc"] and self.slot == 0:	# this is the mmc slot, so pick up from MtdRoot
			self.part = getMachineMtdRoot()
		self.phase = self.MOUNT
		self.run()

	def run(self):
		self.container.ePopen('mount /dev/%s /tmp/testmount' %self.part if self.phase == self.MOUNT else 'umount /tmp/testmount', self.appClosed)

	
	def appClosed(self, data, retval, extra_args):
		if retval == 0 and self.phase == self.MOUNT:
			if os.path.isfile("/tmp/testmount/usr/bin/enigma2"):
				os.rename('/tmp/testmount/usr/bin/enigma2', '/tmp/testmount/usr/bin/enigmax.bin')
			self.phase = self.UNMOUNT
			self.run()
		else:
			self.container.killAll()
			if not os.path.ismount('/tmp/testmount'):
				os.rmdir('/tmp/testmount')
			self.callback()
