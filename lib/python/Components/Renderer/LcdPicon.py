from Components.Renderer.Renderer import Renderer
from enigma import ePixmap, ePicLoad
from Tools.Directories import pathExists, SCOPE_CURRENT_SKIN, resolveFilename
from Components.config import config
from Components.SystemInfo import SystemInfo
from Components.Renderer.Picon import PiconLocator


def useLcdPicons():
	return SystemInfo["displaytype"] in ('bwlcd255', 'bwlcd140', 'bwlcd128') or config.lcd.picon_pack.value


lcdPiconLocator = None


def initPiconPaths(_=None):
	global lcdPiconLocator
	lcdPiconLocator = PiconLocator(['lcd_picon', 'piconlcd'] if useLcdPicons() else None)


config.lcd.picon_pack.addNotifier(initPiconPaths)


class LcdPicon(Renderer):
	def __init__(self):
		Renderer.__init__(self)
		self.pngname = None
		self.__initPicLoad()
		self.piconsize = (0, 0)
		config.lcd.picon_pack.addNotifier(self.configChanged)

	def configChanged(self, _):
		basename = "lcd_picon_default" if useLcdPicons() else "picon_default"
		pngname = lcdPiconLocator.findPicon(basename)
		if not pngname:
			pngname = resolveFilename(SCOPE_CURRENT_SKIN, basename + ".png")
		self.defaultpngname = pngname if pathExists(pngname) else None
		self.changed((self.CHANGED_DEFAULT,))

	def destroy(self):
		# remove the notifier before properties get destroyed
		config.lcd.picon_pack.removeNotifier(self.configChanged)
		Renderer.destroy(self)

	def applySkin(self, desktop, parent):
		attribs = []
		for attrib, value in self.skinAttributes:
			if attrib == "path":
				lcdPiconLocator.addSearchPath(value)
				continue
			elif attrib == "size":
				self.piconsize = value
			attribs.append((attrib, value))
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

	def __initPicLoad(self):
		self.PicLoad = ePicLoad()
		self.PicLoad.PictureData.get().append(self.updatePicon)

	def __decode(self, pngname, para=None):
		if para is None:
			para = (*self.piconsize, 1, 1, 1, 1, "#FF000000")
		self.PicLoad.setPara(para)
		return self.PicLoad.startDecode(pngname) == 0  # returns True on decode success

	def changed(self, what):
		if self.instance:
			if what[0] in (self.CHANGED_DEFAULT, self.CHANGED_ALL, self.CHANGED_SPECIFIC):
				pngname = lcdPiconLocator.getPiconName(self.source.text) or self.defaultpngname
				if self.pngname != pngname:
					if pngname:
						if not self.__decode(pngname):
							# If we are here decode failed, most likely because another decode is already
							# in progress. So, throw away the old picload and try again immediately.
							self.__initPicLoad()
							self.__decode(pngname)
					else:
						self.instance.hide()
					self.pngname = pngname  # irrespective of success, failure or default
			elif what[0] == self.CHANGED_CLEAR:
				self.pngname = None
				self.instance.hide()
