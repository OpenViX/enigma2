from GUIComponent import GUIComponent

from enigma import eListboxPythonMultiContent, eListbox, gFont
from Components.MultiContent import MultiContentEntryText
from Tools.KeyBindings import queryKeyBinding, getKeyDescription
import skin
from Components.config import config
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
	def __init__(self, helplist, callback, rcPos=None):
		GUIComponent.__init__(self)
		self.onSelChanged = [ ]
		self.l = eListboxPythonMultiContent()
		self.callback = callback
		self.extendedHelp = False
		self.rcPos = rcPos
		self.rcKeyIndex = None
		self.buttonMap = {}
		self.longSeen = False

		headings, sortCmp, sortKey = {
				"headings+alphabetic":	(True, None, self._sortKeyAlpha),
				"flat+alphabetic":	(False, None, self._sortKeyAlpha),
				"flat+remotepos":	(False, self._sortCmpPos, None),
				"flat+remotegroups":	(False, self._sortCmpInd, None)
			}.get(config.usage.help_sortorder.value, (False, None, None))

		if rcPos == None:
			if sortCmp in (self._sortCmpPos, self._sortCmpInd):
				sortCmp = None
		else:
			if sortCmp == self._sortCmpInd:
				self.rcKeyIndex = dict((x[1], x[0]) for x in enumerate(rcPos.getRcKeyList()))

		indent = False

		buttonsProcessed = set()
		helpSeen = defaultdict(list)
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
						nlong = (n[0], flags & 8)
						if nlong not in buttonsProcessed:
							buttonNames.append(name)
							buttonsProcessed.add(nlong)

				# only show entries with keys that are available on the used rc
				if not buttonNames:
					continue

				if isinstance(help, list):
					if not self.extendedHelp:
						print "[HelpMenuList] extendedHelpEntry found"
					self.extendedHelp = True

				entry = [ (actionmap, context, action, buttonNames ), help ]

				if self._filterHelpList(entry, helpSeen):
					actionMapHelp[id(actionmap)].append(entry)

		x, y, w, h = self.extendedHelp and skin.parameters.get("HelpMenuListExtHlp0",(skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28))) or skin.parameters.get("HelpMenuListHlp",(skin.applySkinFactor(5), 0, skin.applySkinFactor(595), skin.applySkinFactor(28)))

		l = [ ]
		for (actionmap, context, actions) in helplist:
			amId = id(actionmap)
			if headings and amId in actionMapHelp and getattr(actionmap, "description", None):
				if sortCmp or sortKey:
					actionMapHelp[amId].sort(cmp=sortCmp, key=sortKey)
				self.addListBoxContext(actionMapHelp[amId], indent)

				l.append([None, MultiContentEntryText(pos=(x, y), size=(w, h), text=actionmap.description)])
				l.extend(actionMapHelp[amId])
				del actionMapHelp[amId]

		if actionMapHelp:
			# Add a header if other actionmaps have descriptions
			if indent:
				l.append([None, MultiContentEntryText(pos=(x, y), size=(w, h), text=_("Other functions"))])

			otherHelp = []
			for (actionmap, context, actions) in helplist:
				amId = id(actionmap)
				if amId in actionMapHelp:
					otherHelp.extend(actionMapHelp[amId])
					del actionMapHelp[amId]

			if sortCmp or sortKey:
				otherHelp.sort(cmp=sortCmp, key=sortKey)
			self.addListBoxContext(otherHelp, indent)
			l.extend(otherHelp)

		for i, ent in enumerate(l):
			if ent[0] is not None:
				for b in ent[0][3]:
					self.buttonMap[b] = i

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

	def _mergeButLists(self, bl1, bl2):
		for b in bl2:
			if b not in bl1:
				bl1.append(b)

	def _filterHelpList(self, ent, seen):
		hlp = tuple(ent[1] if isinstance(ent[1], list) else [ent[1], ''])
		if hlp in seen:
			self._mergeButLists(seen[hlp], ent[0][3])
			return False
		else:
			seen[hlp] = ent[0][3]
			return True

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

	def _getMinPos(self, a):
		# Reverse the coordinate tuple, too, to (y, x) to get
		# ordering by y then x.
		return min(map(lambda x: tuple(reversed(self.rcPos.getRcKeyPos(x[0]))), a))

	def _sortCmpPos(self, a, b):
		return cmp(self._getMinPos(a[0][3]), self._getMinPos(b[0][3]))

	# Sort order "Flat by key group on remote" is really
	# "Sort in order of buttons in rcpositions.xml", and so
	# the buttons need to be grouped sensibly in that file for
	# this to work properly.

	def _getMinInd(self, a):
		return min(map(lambda x: self.rcKeyIndex[x[0]], a))

	def _sortCmpInd(self, a, b):
		return cmp(self._getMinInd(a[0][3]), self._getMinInd(b[0][3]))

	def _sortKeyAlpha(self, hlp):
		# Convert normal help to extended help form for comparison
		# and ignore case
		return map(str.lower, hlp[1] if isinstance(hlp[1], list) else [hlp[1], ''])

	def ok(self):
		# a list entry has a "private" tuple as first entry...
		l = self.getCurrent()
		if l is None:
			return
		# ...containing (Actionmap, Context, Action, keydata).
		# we returns this tuple to the callback.
		self.callback(l[0], l[1], l[2])

	def handleButton(self, key, flag):
		name = getKeyDescription(key)
		if name is not None and (len(name) < 2 or name[1] not in("fp", "kbd")) and flag not in (2, 4):
			if flag == 0:
				# Reset the long press flag on make
				self.longSeen = False
			elif flag == 3:  # for long keypresses, make the second tuple item "long".
				name = (name[0], "long")

			if name in self.buttonMap:
				# Show help for pressed button for
				# long press, or for break if it's not a
				# long press
				if flag == 3 or flag == 1 and not self.longSeen:
					self.longSeen = flag == 3
					self.setIndex(self.buttonMap[name])
					# Report key handled
					return 1
		# Report key not handled
		return 0

	def getCurrent(self):
		sel = self.l.getCurrentSelection()
		return sel and sel[0]

	def setIndex(self, index):
		if self.instance is not None:
			self.instance.moveSelectionTo(index)

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
