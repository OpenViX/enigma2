import os, re, unicodedata
from Renderer import Renderer
from enigma import ePixmap, ePicLoad
from Tools.Directories import pathExists, SCOPE_ACTIVE_SKIN, resolveFilename
from boxbranding import getDisplayType
from Components.config import config
from Picon import PiconLocator

def useLcdPicons():
	return getDisplayType() in ('bwlcd255', 'bwlcd140', 'bwlcd128') or config.lcd.picon_pack.value

lcdPiconLocator = None

def initPiconPaths(_ = None):
	global lcdPiconLocator
	lcdPiconLocator = PiconLocator(['lcd_picon', 'piconlcd']) if useLcdPicons() else PiconLocator()
config.lcd.picon_pack.addNotifier(initPiconPaths)

class LcdPicon(Renderer):
	def __init__(self):
		Renderer.__init__(self)
		self.PicLoad = ePicLoad()
		self.PicLoad.PictureData.get().append(self.updatePicon)
		self.piconsize = (0,0)
		config.lcd.picon_pack.addNotifier(self.configChanged)

	def configChanged(self, _):
		self.pngname = None
		serviceName = "lcd_picon_default" if useLcdPicons() else "picon_default"
		pngname = lcdPiconLocator.findPicon(serviceName)
		if not pngname:
			pngname = resolveFilename(SCOPE_ACTIVE_SKIN, serviceName + ".png")
		self.defaultpngname = pngname if os.path.getsize(pngname) else None
		self.changed((self.CHANGED_DEFAULT,))

	def destroy(self):
		# remove the notifier before properties get destroyed
		config.lcd.picon_pack.removeNotifier(self.configChanged)
		Renderer.destroy(self)

	def applySkin(self, desktop, parent):
		attribs = self.skinAttributes[:]
		for (attrib, value) in self.skinAttributes:
			if attrib == "path":
				lcdPiconLocator.addSearchPath(value)
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
			if what[0] in (self.CHANGED_DEFAULT, self.CHANGED_ALL, self.CHANGED_SPECIFIC):
				pngname = lcdPiconLocator.getPiconName(self.source.text)
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
