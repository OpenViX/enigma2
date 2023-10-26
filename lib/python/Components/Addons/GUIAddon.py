from Components.GUIComponent import GUIComponent


class GUIAddon(GUIComponent):
	def __init__(self):
		GUIComponent.__init__(self)
		self.sources = {}

	def connectRelatedElement(self, relatedElementName, container):
		relatedElementNames = relatedElementName.split(",")
		if len(relatedElementNames) == 1:
			self.source = container[relatedElementName]
		elif len(relatedElementNames) > 1:
			for x in relatedElementNames:
				x = x.strip()
				if x in container:
					self.sources[x] = container[x]
		container.onShow.append(self.onContainerShown)

	def onContainerShown(self):
		pass
