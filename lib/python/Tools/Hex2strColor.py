# Converts hex colors to formatted strings,
# suitable for embedding in python code.

from skin import parameters


def Hex2strColor(rgb):
	return r"\c%08x" % rgb  # noqa: W605


class ColorizeText:
	# wraps text in colors imported from skin <parameters>, e.g.
	# <parameter name="AboutColors" value="#00ffc000"/>
	# "default" can be None, int or list of ints.

	def __init__(self, session, param_name, default=None):
		self.colors = parameters.get(param_name, default or [])
		if isinstance(self.colors, int):  # a single entry in skin parameters would not be comma separated and therefore an int, not a list
			self.colors = [self.colors]

	def addColor(self, text, i=0):
		if i < len(self.colors):
			text = Hex2strColor(self.colors[i]) + text + r"\C"
		return text
