from enigma import eCanvas, eRect, gRGB

from Components.Renderer.Renderer import Renderer


class Canvas(Renderer):
	GUI_WIDGET = eCanvas

	def __init__(self):
		Renderer.__init__(self)
		self.sequence = None
		self.draw_count = 0

	def pull_updates(self):
		if self.instance is None:
			return

		# do an incremental update
		list = self.source.drawlist
		if list is None:
			return

		# if the lists sequence count changed, re-start from begin
		if list[0] != self.sequence:
			self.sequence = list[0]
			self.draw_count = 0

		self.draw(list[1][self.draw_count:])
		self.draw_count = len(list[1])

	def draw(self, list):
		for element in list:
			if element[0] == 1:
				self.instance.fillRect(eRect(element[1], element[2], element[3], element[4]), gRGB(element[5]))
			elif element[0] == 2:
				self.instance.writeText(eRect(element[1], element[2], element[3], element[4]), gRGB(element[5]), gRGB(element[6]), element[7], element[8], element[9])
			elif element[0] == 3:
				self.instance.drawLine(element[1], element[2], element[3], element[4], gRGB(element[5]))
			elif element[0] == 4:
				self.instance.drawRotatedLine(element[1], element[2], element[3], element[4], element[5], element[6], element[7], element[8], gRGB(element[9]))
			else:
				print("drawlist entry:", element)
				raise RuntimeError("invalid drawlist entry")

	def changed(self, what):
		self.pull_updates()

	def postWidgetCreate(self, instance):
		self.sequence = None

		from enigma import eSize

		def parseSize(str):
			x, y = str.split(',')
			return eSize(int(x), int(y))

		for (attrib, value) in self.skinAttributes:
			if attrib == "size":
				self.instance.setSize(parseSize(value))

		self.pull_updates()
