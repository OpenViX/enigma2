from enigma import eListboxPythonStringContent, eListbox
from Components.GUIComponent import GUIComponent


class MenuList(GUIComponent):
	def __init__(self, list, enableWrapAround=True, content=eListboxPythonStringContent):
		GUIComponent.__init__(self)
		self.l = content()
		self.list = list
		self.onSelectionChanged = []
		self.enableWrapAround = enableWrapAround

	def getCurrent(self):
		return self.l.getCurrentSelection()

	GUI_WIDGET = eListbox

	def postWidgetCreate(self, instance):
		instance.setContent(self.l)
		instance.selectionChanged.get().append(self.selectionChanged)
		if self.enableWrapAround:
			self.instance.setWrapAround(True)

	def preWidgetRemove(self, instance):
		instance.setContent(None)
		instance.selectionChanged.get().remove(self.selectionChanged)

	def selectionChanged(self):
		for f in self.onSelectionChanged:
			f()

	def getSelectionIndex(self):
		return self.l.getCurrentSelectionIndex()

	def getSelectedIndex(self):
		return self.l.getCurrentSelectionIndex()

	def setList(self, list):
		self.__list = list
		self.l.setList(self.__list)

	def getList(self):
		return self.__list

	list = property(getList, setList)

	def moveToIndex(self, idx):
		if self.instance != None:
			self.instance.moveSelectionTo(idx)

	def moveTop(self):
		if self.instance != None:
			self.instance.moveSelection(self.instance.moveTop)

	def moveBottom(self):
		if self.instance != None:
			self.instance.moveSelection(self.instance.moveEnd)

	def pageUp(self):
		print("menulist pageUp")
		if self.instance != None:
			self.instance.moveSelection(self.instance.pageUp)

	def pageDown(self):
		print("menulist pageDown")
		if self.instance != None:
			self.instance.moveSelection(self.instance.pageDown)

	# Add new moveUp method for symmetry with ConfigList
	def moveUp(self):
		if self.instance != None:
			self.instance.moveSelection(self.instance.moveUp)

	# Add new moveDown method for symmetry with ConfigList
	def moveDown(self):
		if self.instance != None:

			self.instance.moveSelection(self.instance.moveDown)

	# Maintain the old up method for legacy compatibility
	def up(self):
		self.moveUp()

	# Maintain the old down method for legacy compatibility
	def down(self):
		self.moveDown()

	def selectionEnabled(self, enabled):
		if self.instance != None:
			self.instance.setSelectionEnable(enabled)
