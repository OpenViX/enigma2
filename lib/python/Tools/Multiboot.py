from Components.SystemInfo import SystemInfo
from Components.Console import Console
import os, time
import shutil
import subprocess

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
				self.imagelist[self.slot] =  { 'imagename': '%s' %BuildVersion}
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
		(self.firstslot, self.numberofslots) = SystemInfo["canMultiBoot"]
		self.slot = Contents
		if not os.path.isdir('/tmp/testmount'):
			os.mkdir('/tmp/testmount')
		self.phase = self.MOUNT
		self.run()

	def run(self):
		self.container.ePopen('mount /dev/mmcblk0p%s /tmp/testmount' % str(self.slot * 2 + self.firstslot) if self.phase == self.MOUNT else 'umount /tmp/testmount', self.appClosed)

	
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
