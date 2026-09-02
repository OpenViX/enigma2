from enigma import eListbox
from Components.Converter.TemplatedMultiContent import TemplatedMultiContent
from Components.Converter.StringList import StringList


class TemplatedMultiContentEx(TemplatedMultiContent):
	"""TemplatedMultiContent with e (item width) and c (item horizontal center) available in the template."""

	def __init__(self, args):
		self._raw_args = args
		self._size_resolved = False
		StringList.__init__(self, args)
		from enigma import (  # noqa F401
			BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_ALPHATEST, BT_ALPHABLEND,
			BT_FIXRATIO, BT_HALIGN_LEFT, BT_HALIGN_CENTER, BT_HALIGN_RIGHT,
			BT_VALIGN_TOP, BT_VALIGN_CENTER, BT_VALIGN_BOTTOM, BT_ALIGN_CENTER,
			RT_HALIGN_CENTER, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_BOTTOM,
			RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP, RT_BLEND,
			eListboxPythonMultiContent, gFont)

		from Components.MultiContent import (  # noqa F401
			MultiContentEntryLinearGradient, MultiContentEntryLinearGradientAlphaBlend,
			MultiContentEntryPixmap, MultiContentEntryPixmapAlphaBlend,
			MultiContentEntryPixmapAlphaTest, MultiContentEntryProgress,
			MultiContentEntryProgressPixmap, MultiContentEntryText,
			MultiContentTemplateColor)

		from skin import parseFont, getSkinFactor  # noqa F401

		f = getSkinFactor()
		e = 0
		c = 0
		i = int
		loc = locals()
		del loc["self"]
		del loc["args"]
		self._eval_locals = loc
		self.active_style = None
		self.template = eval(args, {}, loc)
		self.scale = None
		self.orientations = {
			"orHorizontal": eListbox.orHorizontal,
			"orVertical": eListbox.orVertical,
			"orGrid": eListbox.orGrid,
		}
		assert "fonts" in self.template
		assert "itemHeight" in self.template
		assert "template" in self.template or "templates" in self.template
		assert "template" in self.template or "default" in self.template["templates"]
		if "template" not in self.template:
			templateDefault = self.template["templates"]["default"]
			self.template["template"] = templateDefault[1]
			self.template["itemHeight"] = templateDefault[0]
			if len(templateDefault) > 2:
				self.template["selectionEnabled"] = templateDefault[2]
			if len(templateDefault) > 3:
				self.template["scrollbarMode"] = templateDefault[3]
			if len(templateDefault) > 5:
				self.template["itemWidth"] = templateDefault[4]
				self.template["orientation"] = templateDefault[5]

	def setTemplate(self):
		if not self._size_resolved and self.master and self.master.instance:
			width = self.master.instance.size().width()
			if width > 0:
				self._eval_locals["e"] = width
				self._eval_locals["c"] = width // 2
				self.template = eval(self._raw_args, {}, self._eval_locals)
				self._size_resolved = True
				self.active_style = None  # force parent to re-apply the updated template
		TemplatedMultiContent.setTemplate(self)
