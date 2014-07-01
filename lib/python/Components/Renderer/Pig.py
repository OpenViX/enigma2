##
## P(icture)i(n)g(raphics) renderer
##
from Renderer import Renderer
from enigma import eVideoWidget, getDesktop
from Screens.PictureInPicture import PipPigMode

class Pig(Renderer):
	def __init__(self):
		Renderer.__init__(self)
		self.Position = self.Size = None

	GUI_WIDGET = eVideoWidget

	def postWidgetCreate(self, instance):
		desk = getDesktop(0)
		instance.setDecoder(0)
		instance.setFBSize(desk.size())

	def applySkin(self, desktop, parent):
		ret = Renderer.applySkin(self, desktop, parent)
		if ret:
			self.Position = self.instance.position()
			self.Size = self.instance.size()
		return ret

	def onShow(self):
		if self.instance:
			if self.Size:
				self.instance.resize(self.Size)
			if self.Position:
				self.instance.move(self.Position)
			PipPigMode(True)

	def onHide(self):
		if self.instance:
			self.preWidgetRemove(self.instance)
			PipPigMode(False)
