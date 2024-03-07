from chardet import detect


class VariableText:
	"""VariableText can be used for components which have a variable text, based on any widget with setText call"""

	def __init__(self):
		object.__init__(self)
		self.message = ""
		self.instance = None
		self.onChanged = []

	def setText(self, text):
		self.message = text
		if text:
			atext = text.encode('UTF-8', 'surrogateescape')
			if text != atext.decode('UTF-8', 'ignore'):
				encoding = detect(atext)['encoding'] or 'ascii'
				self.message = atext.decode(encoding)
		if self.instance:
			self.instance.setText(self.message or "")
		for x in self.onChanged:
			x()

	def setMarkedPos(self, pos):
		if self.instance:
			self.instance.setMarkedPos(int(pos))

	def getText(self):
		return self.message

	text = property(getText, setText)

	def postWidgetCreate(self, instance):
		instance.setText(str(self.message) or "")
