from Components.Element import Element


class Source(Element):
	def execBegin(self):
		pass

	def execEnd(self):
		pass

	def onShow(self):
		pass

	def onHide(self):
		pass

	def destroy(self):
		# by setting all attributes to None, we release any references promptly
		# without completely removing attributes that are expected to exist 
		# dict's clear() can cause crashes due to expected attributes
		for name in self.__dict__:
			setattr(self, name, None)


class ObsoleteSource(Source):
	def __init__(self, newSource, description=None, removalDate="AS SOON AS POSSIBLE"):
		self.newSource = newSource
		self.description = description
		self.removalDate = removalDate
