from Components.Renderer.Renderer import Renderer
from enigma import eLabel, gRGB
from skin import parseColor


class RatingIconLabel(Renderer):
	def __init__(self):
		Renderer.__init__(self)
		self.colors = {}
		self.extendDirection = "right"
		self.sidesMargin = 20

	GUI_WIDGET = eLabel

	def postWidgetCreate(self, instance):
		self.changed((self.CHANGED_DEFAULT,))

	def applySkin(self, desktop, parent):
		attribs = []
		for (attrib, value) in self.skinAttributes:
			if attrib == "colors":
				self.colors = {int(k): parseColor(v) for k, v in (item.split(":") for item in value.split(","))}
			elif attrib == "extendDirection":
				self.extendDirection = value
			elif attrib == "sidesMargin":
				self.sidesMargin = int(value)
			else:
				attribs.append((attrib, value))
		self.skinAttributes = attribs
		result = Renderer.applySkin(self, desktop, parent)
		self.changed((self.CHANGED_DEFAULT,))
		return result

	def hideLabel(self):
		if self.instance:
			self.instance.setText("")
			self.instance.hide()

	def changed(self, what):
		self.hideLabel()  # initially hide the label
		if self.source and hasattr(self.source, "text") and self.instance:
			if what[0] == self.CHANGED_CLEAR:
				self.hideLabel()
			else:
				if self.source.text:
					color = 0x00000000
					ageText = ""
					if ";" in self.source.text:
						split_text = self.source.text.split(";")
						if not split_text or len(split_text) == 1 or not split_text[0]:
							self.hideLabel()
							return
						ageText = split_text[0]
						color = int(split_text[1], 16)
					else:
						age = int(self.source.text.replace("+", ""))
						if age <= 15:
							age += 3
						ageText = str(age)
						color = self.colors.get(age, 0x10000000)

					size = self.instance.size()
					pos = self.instance.position()
					self.instance.setNoWrap(1)
					self.instance.setText(ageText)
					textSize = self.instance.calculateSize()
					self.instance.setNoWrap(0)
					newWidth = textSize.width() + self.sidesMargin
					if newWidth < size.width():
						newWidth = size.width()

					if self.extendDirection == "left":
						rightEdgePos = pos.x() + size.width()
						self.move(rightEdgePos - newWidth, pos.y())

					if self.extendDirection != "none":
						self.resize(newWidth, size.height())

					self.instance.setBackgroundColor(gRGB(color))
					self.instance.show()
				else:
					self.hideLabel()
