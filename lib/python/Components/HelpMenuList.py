from __future__ import print_function
from __future__ import absolute_import

from enigma import eListboxPythonMultiContent, eListbox, gFont

from Components.GUIComponent import GUIComponent
from Tools.KeyBindings import queryKeyBinding, getKeyDescription
import skin
#getKeyPositions

# [ ( actionmap, context, [(action, help), (action, help), ...] ), (actionmap, ... ), ... ]


class HelpMenuList(GUIComponent):
	def __init__(self, helplist, callback):
		GUIComponent.__init__(self)
		self.onSelChanged = []
		self.l = eListboxPythonMultiContent()
		self.callback = callback
		self.extendedHelp = False

		l = []

		sortlist = []
		for (actionmap, context, actions) in helplist:
			for (action, help) in actions:
				if hasattr(help, '__call__'):
					help = help()
				if not help:
					continue
				sortlist.append((actionmap, context, action, help))
		# Sort by description text (main and extended), then by action (this puts numeric actions in ascending order).
#		sortlist.sort(key=lambda helpItem: (list(map(str.lower, helpItem[3] if isinstance(helpItem[3], (tuple, list)) else [helpItem[3]])), helpItem[2]))
		sortlist.sort(key=lambda helpItem: ([s.lower() for s in (helpItem[3] if isinstance(helpItem[3], (tuple, list)) else [helpItem[3]])], helpItem[2]))

		for (actionmap, context, action, help) in sortlist:
				buttons = queryKeyBinding(context, action)

				# do not display entries which are not accessible from keys
				if not len(buttons):
					continue

				name = None
				flags = 0

				for n in buttons:
					(name, flags) = (getKeyDescription(n[0]), n[1])
					if name is not None:
						break

				# only show entries with keys that are available on the used rc
				if name is None:
					continue

				if flags & 8: # for long keypresses, prepend l_ into the key name.
					name = (name[0], "long")

				entry = [(actionmap, context, action, name)]

				if isinstance(help, list):
					self.extendedHelp = True
					print("extendedHelpEntry found")
					x, y, w, h = skin.parameters.get("HelpMenuListExtHlp0", (skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28)))
					x1, y1, w1, h1 = skin.parameters.get("HelpMenuListExtHlp1", (skin.applySkinFactor(5), skin.applySkinFactor(34), skin.applySkinFactor(595), skin.applySkinFactor(22)))
					entry.extend((
						(eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, 0, help[0]),
						(eListboxPythonMultiContent.TYPE_TEXT, x1, y1, w1, h1, 1, 0, help[1])
					))
				else:
					x, y, w, h = skin.parameters.get("HelpMenuListHlp", (skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28)))
					entry.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, 0, help))

				l.append(entry)

		self.l.setList(l)
		if self.extendedHelp is True:
			font = skin.fonts.get("HelpMenuListExt0", ("Regular", skin.applySkinFactor(24), skin.applySkinFactor(56)))
			self.l.setFont(0, gFont(font[0], font[1]))
			self.l.setItemHeight(font[2])
			font = skin.fonts.get("HelpMenuListExt1", ("Regular", skin.applySkinFactor(18)))
			self.l.setFont(1, gFont(font[0], font[1]))
		else:
			font = skin.fonts.get("HelpMenuList", ("Regular", skin.applySkinFactor(24), skin.applySkinFactor(28)))
			self.l.setFont(0, gFont(font[0], font[1]))
			self.l.setItemHeight(font[2])

	def ok(self):
		# a list entry has a "private" tuple as first entry...
		l = self.getCurrent()
		if l is None:
			return
		# ...containing (Actionmap, Context, Action, keydata).
		# we returns this tuple to the callback.
		self.callback(l[0], l[1], l[2])

	def getCurrent(self):
		sel = self.l.getCurrentSelection()
		return sel and sel[0]

	GUI_WIDGET = eListbox

	def postWidgetCreate(self, instance):
		instance.setContent(self.l)
		instance.selectionChanged.get().append(self.selectionChanged)
		self.instance.setWrapAround(True)

	def preWidgetRemove(self, instance):
		instance.setContent(None)
		instance.selectionChanged.get().remove(self.selectionChanged)

	def selectionChanged(self):
		for x in self.onSelChanged:
			x()
