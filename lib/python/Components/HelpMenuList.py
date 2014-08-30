from GUIComponent import GUIComponent

from enigma import eListboxPythonMultiContent, eListbox, gFont
from Components.MultiContent import MultiContentEntryText
from Tools.KeyBindings import queryKeyBinding, getKeyDescription
import skin
from collections import defaultdict

# [ ( actionmap, context, [(action, help), (action, help), ...] ), (actionmap, ... ), ... ]

# The helplist is ordered by the order that the Helpable[Number]ActionMaps
# are initialised.

# The lookup of actions is by searching the HelpableActionMaps by priority,
# then my order of initialisation.

# The lookup of actions for a key press also stops at the first valid action
# encountered.

# The search for key press help is on a list sorted in priority order,
# and the search finishes when the first action/help matching matching
# the key is found.

# The code recognises that more than one button can map to an action and
# places a button name list instead of a single button in the help entry.

class HelpMenuList(GUIComponent):
	def __init__(self, helplist, callback):
		GUIComponent.__init__(self)
		self.onSelChanged = [ ]
		self.l = eListboxPythonMultiContent()
		self.callback = callback
		self.extendedHelp = False

		indent = False

		buttonsProcessed = set()
		sortedHelplist = sorted(helplist, key=lambda hle: hle[0].prio)
		actionMapHelp = defaultdict(list)

		for (actionmap, context, actions) in sortedHelplist:
			if not actionmap.enabled:
				continue

			if actionmap.description:
				if not indent:
					print "[HelpMenuList] indent found"
				indent = True

			for (action, help) in actions:
				if hasattr(help, '__call__'):
					help = help()

				if not help:
					continue

				buttons = queryKeyBinding(context, action)

				# do not display entries which are not accessible from keys
				if not buttons:
					continue

				name = None
				flags = 0

				buttonNames = [ ]

				for n in buttons:
					(name, flags) = (getKeyDescription(n[0]), n[1])
					if name is not None and (len(name) < 2 or name[1] not in("fp", "kbd")):
						if flags & 8: # for long keypresses, make the second tuple item "long".
							name = (name[0], "long")
						if n not in buttonsProcessed:
							buttonNames.append(name)
							buttonsProcessed.add(n[0])

				# only show entries with keys that are available on the used rc
				if not buttonNames:
					print '[HelpMenuList] no valid buttons 2'
					continue
				print '[HelpMenuList] valid buttons 2', buttonNames

				if isinstance(help, list):
					if not self.extendedHelp:
						print "[HelpMenuList] extendedHelpEntry found"
					self.extendedHelp = True

				entry = [ (actionmap, context, action, buttonNames ), help ]

				actionMapHelp[context].append(entry)

		x, y, w, h = self.extendedHelp and skin.parameters.get("HelpMenuListExtHlp0",(skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28))) or skin.parameters.get("HelpMenuListHlp",(skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28)))

		l = [ ]
		for (actionmap, context, actions) in helplist:
			if context in actionMapHelp and actionmap.description:
				self.addListBoxContext(actionMapHelp[context], indent)

				l.append([None, MultiContentEntryText(pos=(x, y), size=(w, h), text=actionmap.description)])
				l.extend(actionMapHelp[context])
				del actionMapHelp[context]

		if actionMapHelp:
			# Add a header if other actionmaps have descriptions
			if indent:
				l.append([None, MultiContentEntryText(pos=(x, y), size=(w, h), text=_("Other functions"))])

			for (actionmap, context, actions) in helplist:
				if context in actionMapHelp:
					self.addListBoxContext(actionMapHelp[context], indent)

					l.extend(actionMapHelp[context])
					del actionMapHelp[context]

		self.l.setList(l)
		if self.extendedHelp:
			font = skin.fonts.get("HelpMenuListExt0", ("Regular", skin.applySkinFactor(24), skin.applySkinFactor(56)))
			self.l.setFont(0, gFont(font[0], font[1]))
			self.l.setItemHeight(font[2])
			font = skin.fonts.get("HelpMenuListExt1", ("Regular", skin.applySkinFactor(18)))
			self.l.setFont(1, gFont(font[0], font[1]))
		else:
			font = skin.fonts.get("HelpMenuList", ("Regular", skin.applySkinFactor(24), skin.applySkinFactor(28)))
			self.l.setFont(0, gFont(font[0], font[1]))
			self.l.setItemHeight(font[2])

	def addListBoxContext(self, actionMapHelp, indent):
		for ent in actionMapHelp:
			help = ent[1]
			if isinstance(help, list):
				x, y, w, h = skin.parameters.get("HelpMenuListExtHlp0",(skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28)))
				x1, y1, w1, h1 = skin.parameters.get("HelpMenuListExtHlp1",(skin.applySkinFactor(5), skin.applySkinFactor(34), skin.applySkinFactor(595), skin.applySkinFactor(22)))
				i = skin.applySkinFactor(20)
				i1 = skin.applySkinFactor(20)
				if indent:
					x = min(x + i, x + w)
					w = max(w - i, 0)
					x1 = min(x1 + i1, x1 + w1)
					w1 = max(w1 - i1, 0)
				ent[1:] = [
					MultiContentEntryText(pos=(x, y), size=(w, h), font=0, text=help[0]),
					MultiContentEntryText(pos=(x1, y1), size=(w1, h1), font=1, text=help[1]),
				]
			else:
				x, y, w, h = skin.parameters.get("HelpMenuListHlp",(skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28)))
				i = skin.applySkinFactor(20)
				if indent:
					x = min(x + i, x + w)
					w = max(w - i, 0)
				ent[1] = MultiContentEntryText(pos=(x, y), size=(w, h), font=0, text=help)

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
