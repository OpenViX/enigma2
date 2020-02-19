import os, re, unicodedata
from Renderer import Renderer
from enigma import ePixmap, ePicLoad
from Tools.Alternatives import GetWithAlternative
from Tools.Directories import pathExists, SCOPE_ACTIVE_SKIN, resolveFilename
from Components.Harddisk import harddiskmanager
from boxbranding import getBoxType
from ServiceReference import ServiceReference
from Components.config import config

searchPaths = []
lastLcdPiconPath = None

bw_lcd = ('xpeedlx3','vuultimo')

def initLcdPiconPaths():
	global searchPaths
	searchPaths = []
	for mp in ('/usr/share/enigma2/', '/'):
		onMountpointAdded(mp)
	for part in harddiskmanager.getMountedPartitions():
		onMountpointAdded(part.mountpoint)

def onMountpointAdded(mountpoint):
	global searchPaths
	try:
		if getBoxType() in bw_lcd or config.lcd.picon_pack.value:
			path = os.path.join(mountpoint, 'lcd_picon') + '/'
		else:
			path = os.path.join(mountpoint, 'picon') + '/'
		if os.path.isdir(path) and path not in searchPaths:
			for fn in os.listdir(path):
				if fn.endswith('.png'):
					print "[LcdPicon] adding path:", path
					searchPaths.append(path)
					break
	except Exception, ex:
		print "[LcdPicon] Failed to investigate %s:" % mountpoint, ex

def onMountpointRemoved(mountpoint):
	global searchPaths
	if getBoxType() in bw_lcd or config.lcd.picon_pack.value:
		path = os.path.join(mountpoint, 'lcd_picon') + '/'
	else:
		path = os.path.join(mountpoint, 'picon') + '/'
	try:
		searchPaths.remove(path)
		print "[LcdPicon] removed path:", path
	except:
		pass

def onPartitionChange(why, part):
	if why == 'add':
		onMountpointAdded(part.mountpoint)
	elif why == 'remove':
		onMountpointRemoved(part.mountpoint)

def findLcdPicon(serviceName):
	global lastLcdPiconPath
	if lastLcdPiconPath is not None:
		pngname = lastLcdPiconPath + serviceName + ".png"
		if pathExists(pngname):
			return pngname
		else:
			return ""
	else:
		global searchPaths
		pngname = ""
		for path in searchPaths:
			if pathExists(path) and not path.startswith('/media/net') and not path.startswith('/media/autofs'):
				pngname = path + serviceName + ".png"
				if pathExists(pngname):
					lastLcdPiconPath = path
					break
			elif pathExists(path):
				pngname = path + serviceName + ".png"
				if pathExists(pngname):
					lastLcdPiconPath = path
					break
		if pathExists(pngname):
			return pngname
		else:
			return ""

def getLcdPiconName(serviceName):
	#remove the path and name fields, and replace ':' by '_'
	fields = GetWithAlternative(serviceName).split(':', 10)[:10]
	if not fields or len(fields) < 10:
		return ""
	pngname = findLcdPicon('_'.join(fields))
	if not pngname and not fields[6].endswith("0000"):
		#remove "sub-network" from namespace
		fields[6] = fields[6][:-4] + "0000"
		pngname = findLcdPicon('_'.join(fields))
	if not pngname and fields[0] != '1':
		#fallback to 1 for IPTV streams
		fields[0] = '1'
		pngname = findLcdPicon('_'.join(fields))
	if not pngname and fields[2] != '2':
		#fallback to 1 for TV services with non-standard service types
		fields[2] = '1'
		pngname = findLcdPicon('_'.join(fields))
	if not pngname: # picon by channel name
		name = ServiceReference(serviceName).getServiceName()
		name = unicodedata.normalize('NFKD', unicode(name, 'utf_8', errors='ignore')).encode('ASCII', 'ignore')
		name = re.sub('[^a-z0-9]', '', name.replace('&', 'and').replace('+', 'plus').replace('*', 'star').lower())
		if len(name) > 0:
			pngname = findLcdPicon(name)
			if not pngname and len(name) > 2 and name.endswith('hd'):
				pngname = findLcdPicon(name[:-2])
	return pngname

class LcdPicon(Renderer):
	def __init__(self):
		Renderer.__init__(self)
		self.PicLoad = ePicLoad()
		self.PicLoad.PictureData.get().append(self.updatePicon)
		self.piconsize = (0,0)
		self.pngname = ""
		self.lastPath = None
		if getBoxType() in bw_lcd or config.lcd.picon_pack.value:
			pngname = findLcdPicon("lcd_picon_default")
		else:
			pngname = findLcdPicon("picon_default")
		self.defaultpngname = None
		if not pngname:
			if getBoxType() in bw_lcd or config.lcd.picon_pack.value:
				tmp = resolveFilename(SCOPE_ACTIVE_SKIN, "lcd_picon_default.png")
			else:
				tmp = resolveFilename(SCOPE_ACTIVE_SKIN, "picon_default.png")
			if pathExists(tmp):
				pngname = tmp
			else:
				if getBoxType() in bw_lcd or config.lcd.picon_pack.value:
					pngname = resolveFilename(SCOPE_ACTIVE_SKIN, "lcd_picon_default.png")
				else:
					pngname = resolveFilename(SCOPE_ACTIVE_SKIN, "picon_default.png")
		if os.path.getsize(pngname):
			self.defaultpngname = pngname

	def addPath(self, value):
		if pathExists(value):
			global searchPaths
			if not value.endswith('/'):
				value += '/'
			if value not in searchPaths:
				searchPaths.append(value)

	def applySkin(self, desktop, parent):
		attribs = self.skinAttributes[:]
		for (attrib, value) in self.skinAttributes:
			if attrib == "path":
				self.addPath(value)
				attribs.remove((attrib,value))
			elif attrib == "size":
				self.piconsize = value
		self.skinAttributes = attribs
		rc = Renderer.applySkin(self, desktop, parent)
		self.changed((self.CHANGED_DEFAULT,))
		return rc

	GUI_WIDGET = ePixmap

	def updatePicon(self, picInfo=None):
		ptr = self.PicLoad.getData()
		if ptr is not None:
			self.instance.setPixmap(ptr.__deref__())
			self.instance.show()

	def changed(self, what):
		if self.instance:
			pngname = ""
			if what[0] in (self.CHANGED_DEFAULT, self.CHANGED_ALL, self.CHANGED_SPECIFIC):
				pngname = getLcdPiconName(self.source.text)
				if not pathExists(pngname): # no picon for service found
					pngname = self.defaultpngname
				if self.pngname != pngname:
					if pngname:
						self.PicLoad.setPara((self.piconsize[0], self.piconsize[1], 0, 0, 1, 1, "#FF000000"))
						if self.PicLoad.startDecode(pngname):
							# if this has failed, then another decode is probably already in progress
							# throw away the old picload and try again immediately
							self.PicLoad = ePicLoad()
							self.PicLoad.PictureData.get().append(self.updatePicon)
							self.PicLoad.setPara((self.piconsize[0], self.piconsize[1], 0, 0, 1, 1, "#FF000000"))
							self.PicLoad.startDecode(pngname)
					else:
						self.instance.hide()
					self.pngname = pngname
			elif what[0] == self.CHANGED_CLEAR:
				self.pngname = None
				self.instance.hide()

harddiskmanager.on_partition_list_change.append(onPartitionChange)
initLcdPiconPaths()
