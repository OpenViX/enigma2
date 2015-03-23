import skin
from HTMLComponent import HTMLComponent
from GUIComponent import GUIComponent
from enigma import eLabel, eWidget, eSlider, fontRenderClass, ePoint, eSize

class ScrollLabel(HTMLComponent, GUIComponent):
	def __init__(self, text=""):
		GUIComponent.__init__(self)
		self.message = text
		self.instance = None
		self.long_text = None
		self.right_text = None
		self.scrollbar = None
		self.pages = None
		self.total = None
		self.split = False
		self.splitchar = "|"
		self.column = 0

	def applySkin(self, desktop, parent):
		ret = False
		if self.skinAttributes is not None:
			widget_attribs = [ ]
			scrollbar_attribs = [ ]
			for (attrib, value) in self.skinAttributes:
				if "borderColor" in attrib or "borderWidth" in attrib:
					scrollbar_attribs.append((attrib,value))
				if "transparent" in attrib or "backgroundColor" in attrib:
					widget_attribs.append((attrib,value))
				if "split" in attrib:
					self.split = int(value)
					if self.split:
						self.right_text = eLabel(self.instance)
				if "colposition" in attrib:
					self.column = int(value)
				if "dividechar" in attrib:
					self.splitchar = value
			if self.split:
				skin.applyAllAttributes(self.long_text, desktop, self.skinAttributes + [("halign", "left")], parent.scale)
				skin.applyAllAttributes(self.right_text, desktop, self.skinAttributes + [("transparent", "1"), ("halign", "left" and self.column or "right")], parent.scale)
			else:
				skin.applyAllAttributes(self.long_text, desktop, self.skinAttributes, parent.scale)
			skin.applyAllAttributes(self.instance, desktop, widget_attribs, parent.scale)
			skin.applyAllAttributes(self.scrollbar, desktop, scrollbar_attribs+widget_attribs, parent.scale)
			ret = True
		s = self.long_text.size()
		self.instance.move(self.long_text.position())
		lineheight=fontRenderClass.getInstance().getLineHeight( self.long_text.getFont() )
		if not lineheight:
			lineheight = 30 # assume a random lineheight if nothing is visible
		lines = int(s.height() / lineheight)
		self.pageHeight = int(lines * lineheight)
		self.instance.resize(eSize(s.width(), self.pageHeight+ int(lineheight/6)))
		self.scrollbar.move(ePoint(s.width()-10,0))
		self.scrollbar.resize(eSize(10,self.pageHeight+ int(lineheight/6)))
		self.scrollbar.setOrientation(eSlider.orVertical)
		self.scrollbar.setRange(0,100)
		self.scrollbar.setBorderWidth(1)
		self.long_text.move(ePoint(0,0))
		self.long_text.resize(eSize(s.width()-30, self.pageHeight*40))
		if self.split:
			self.right_text.move(ePoint(self.column,0))
			self.right_text.resize(eSize(s.width()-self.column-30, self.pageHeight*40))
		self.setText(self.message)
		return ret

	def setText(self, text):
		self.message = text
		if self.long_text is not None and self.pageHeight:
			self.long_text.move(ePoint(0,0))
			if self.split:
				left = []
				right = []
				for line in self.message.split("\n"):
					line = line.split(self.splitchar,1)
					if len(line) == 1:
						line.append("")
					left.append(line[0])
					right.append(line[1].lstrip(' '))
				self.long_text.setText("\n".join(left))
				self.right_text.setText("\n".join(right))
			else:
				self.long_text.setText(self.message)
			text_height=self.long_text.calculateSize().height()
			total=self.pageHeight
			pages=1
			while total < text_height:
				total += self.pageHeight
				pages += 1
			if pages > 1:
				self.scrollbar.show()
				self.total = total
				self.pages = pages
				self.updateScrollbar()
			else:
				self.scrollbar.hide()
				self.total = None
				self.pages = None

	def appendText(self, text):
		old_text = self.getText()
		if len(str(old_text)) >0:
			self.message += text
		else:
			self.message = text
		if self.long_text is not None:
			self.long_text.setText(self.message)
			text_height=self.long_text.calculateSize().height()
			total=self.pageHeight
			pages=1
			while total < text_height:
				total += self.pageHeight
				pages += 1
			if pages > 1:
				self.scrollbar.show()
				self.total = total
				self.pages = pages
				self.updateScrollbar()
			else:
				self.scrollbar.hide()
				self.total = None
				self.pages = None

	def updateScrollbar(self):
		start = -self.long_text.position().y() * 100 / self.total
		vis = self.pageHeight * 100 / self.total
		self.scrollbar.setStartEnd(start, start+vis)

	def getText(self):
		return self.message

	def GUIcreate(self, parent):
		self.instance = eWidget(parent)
		self.scrollbar = eSlider(self.instance)
		self.long_text = eLabel(self.instance)

	def GUIdelete(self):
		self.long_text = None
		self.scrollbar = None
		self.instance = None
		self.right_text = None

	def pageUp(self):
		if self.total is not None:
			curPos = self.long_text.position()
			if curPos.y() < 0:
				self.long_text.move( ePoint( curPos.x(), curPos.y() + self.pageHeight ) )
				self.split and self.right_text.move( ePoint( curPos.x(), curPos.y() + self.pageHeight ) )
				self.updateScrollbar()

	def pageDown(self):
		if self.total is not None:
			curPos = self.long_text.position()
			if self.total-self.pageHeight >= abs( curPos.y() - self.pageHeight ):
				self.long_text.move( ePoint( curPos.x(), curPos.y() - self.pageHeight ) )
				self.split and self.right_text.move( ePoint( curPos.x(), curPos.y() - self.pageHeight ) )
				self.updateScrollbar()

	def lastPage(self):
		if self.pages is not None:
			i = 1
			while i < self.pages:
				self.pageDown()
				i += 1

	def isAtLastPage(self):
		if self.total is not None:
			curPos = self.long_text.position()
			return self.total - self.pageHeight < abs( curPos.y() - self.pageHeight )
		else:
			return True

	def produceHTML(self):
		return self.getText()
