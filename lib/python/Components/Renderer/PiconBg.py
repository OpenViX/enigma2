from Components.Renderer.Renderer import Renderer
from enigma import ePixmap, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER, BT_VALIGN_CENTER
from Components.config import config
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename


class PiconBg(Renderer):
	def __init__(self):
		Renderer.__init__(self)
		self.pngname = ""

	GUI_WIDGET = ePixmap

	def postWidgetCreate(self, instance):
		self.changed((self.CHANGED_DEFAULT,))

	def changed(self, what):
		if self.instance:
			pngname = ""
			if what[0] in (self.CHANGED_ALL, self.CHANGED_SPECIFIC):
				pngname = resolveFilename(SCOPE_CURRENT_SKIN, "piconbg/" + config.usage.show_picon_bkgrn.value + ".png")
				if self.pngname != pngname:
					if pngname:
						self.instance.setPixmapScaleFlags(BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER)
						self.instance.setPixmapFromFile(pngname)
						self.instance.show()
					else:
						self.instance.hide()
					self.pngname = pngname
