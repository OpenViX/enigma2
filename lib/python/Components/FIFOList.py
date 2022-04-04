from Components.MenuList import MenuList


class FIFOList(MenuList):
	def __init__(self, list=[], len=10):
		self.len = len
		self.fifoList = list
		MenuList.__init__(self, self.fifoList)

	def addItem(self, item):
		self.fifoList.append(item)
		self.setList(self.fifoList[-self.len:])

	def clear(self):
		del self.fifoList[:]
		self.setList(self.fifoList)

	def getCurrentSelection(self):
		return self.fifoList and self.getCurrent() or None

	def listAll(self):
		self.setList(self.fifoList)
		self.selectionEnabled(True)
