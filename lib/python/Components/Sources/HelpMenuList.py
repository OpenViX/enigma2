from Components.Sources.List import List
from Tools.KeyBindings import queryKeyBinding, getSkipKeys
from Components.config import config
from collections import defaultdict
from keyids import KEYIDS

# Helplist structure:
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

# In the template for HelpMenuList:

# In the template for HelpMenuList:

# Template "default" for simple string help items
# For headings use data[1:] = [heading, None, None]
# For the help entries:
# Use data[1:] = [None, helpText, None] for non-indented text
# and data[1:] = [None, None, helpText] for indented text (indent distance set in template)

# Template "extended" for list/tuple help items
# For headings use data[1:] = [heading, None, None, None, None]
# For the help entries:
# Use data[1] = None
# and data[2:] = [helpText, None, extText, None] for non-indented text
# and data[2:] = [None, helpText, None, extText] for indented text


class HelpMenuList(List):
	HEADINGS = 1
	EXTENDED = 2

	def __init__(self, helplist, callback, rcPos=None):
		List.__init__(self)
		self.callback = callback
		formatFlags = 0
		self.rcPos = rcPos
		self.rcKeyIndex = None
		self.buttonMap = {}
		self.longSeen = False
		self.skipKeys = getSkipKeys()

		def actMapId():
			return getattr(actionmap, "description", None) or id(actionmap)

		headings, sortKey = {
			"headings+alphabetic": (True, self._sortKeyAlpha),
			"flat+alphabetic": (False, self._sortKeyAlpha),
			"flat+remotepos": (False, self._sortPos),
			"flat+remotegroups": (False, self._sortInd)
		}.get(config.usage.help_sortorder.value, (False, None))

		if rcPos is None:
			if sortKey in (self._sortPos, self._sortInd):
				sortKey = None
		else:
			if sortKey == self._sortInd:
				self.rcKeyIndex = dict((x[1], x[0]) for x in enumerate(rcPos.getRcKeyList()))

		buttonsProcessed = set()
		helpSeen = defaultdict(list)
		sortedHelplist = sorted(helplist, key=lambda hle: hle[0].prio)
		actionMapHelp = defaultdict(list)

		for (actionmap, context, actions) in sortedHelplist:
			if not actionmap.enabled:
				continue

			if headings and actionmap.description and not (formatFlags & self.HEADINGS):
				print("[HelpMenuList] headings found")
				formatFlags |= self.HEADINGS

			for (action, help) in actions:
				helpTags = []
				if callable(help):
					help = help()
					helpTags.append(pgettext('Abbreviation of "Configurable"', 'C'))

				if not help:
					continue

				buttons = queryKeyBinding(context, action)

				# do not display entries which are not accessible from keys
				if not buttons:
					continue

				buttonLabels = []

				for keyId, flags in buttons:
					if not self.rcPos.getRcKeyPos(keyId):
						continue
					button = (keyId,)
					if keyId not in self.skipKeys:
						if flags & 8:  # for long keypresses, make the second tuple item "long".
							button = (keyId, "long")
						nlong = (keyId, flags & 8)
						if nlong not in buttonsProcessed:
							buttonLabels.append(button)
							buttonsProcessed.add(nlong)

				# only show entries with keys that are available on the used rc
				if not buttonLabels:
					continue

				isExtended = isinstance(help, (tuple, list))
				if isExtended and not (formatFlags & self.EXTENDED):
					print("[HelpMenuList] extendedHelp entry found")
					formatFlags |= self.EXTENDED

				if helpTags:
					helpStr = help[0] if isExtended else help
					tagsStr = pgettext("Text list separator", ', ').join(helpTags)
					helpStr = _("%s (%s)") % (helpStr, tagsStr)
					help = [helpStr, help[1]] if isExtended else helpStr

				entry = [(actionmap, context, action, buttonLabels), help]
				if self._filterHelpList(entry, helpSeen):
					actionMapHelp[actMapId()].append(entry)

		l = []
		extendedPadding = (None, ) if formatFlags & self.EXTENDED else ()

		for (actionmap, context, actions) in sorted(helplist, key=self._sortHeadingsAlpha):
			amId = actMapId()
			if headings and amId in actionMapHelp and getattr(actionmap, "description", None):
				if sortKey:
					actionMapHelp[amId].sort(key=sortKey)
				self.addListBoxContext(actionMapHelp[amId], formatFlags)

				l.append((None, actionmap.description, None) + extendedPadding)
				l.extend(actionMapHelp[amId])
				del actionMapHelp[amId]

		if actionMapHelp:
			# Add a header if other actionmaps have descriptions
			if formatFlags & self.HEADINGS:
				l.append((None, _("Other functions"), None) + extendedPadding)

			otherHelp = []
			for (actionmap, context, actions) in helplist:
				amId = actMapId()
				if amId in actionMapHelp:
					otherHelp.extend(actionMapHelp[amId])
					del actionMapHelp[amId]

			if sortKey:
				otherHelp.sort(key=sortKey)
			self.addListBoxContext(otherHelp, formatFlags)
			l.extend(otherHelp)

		for i, ent in enumerate(l):
			if ent[0] is not None:
				# Ignore "break" events from
				# OK and EXIT on return from
				# help popup
				for b in ent[0][3]:
					if b[0] not in (KEYIDS.get("KEY_OK"), KEYIDS.get("KEY_EXIT")):
						self.buttonMap[b] = i

		self.style = (
			"default",
			"default+headings",
			"extended",
			"extended+headings",
		)[formatFlags];

		self.list = l

	def _mergeButLists(self, bl1, bl2):
		bl1.extend([b for b in bl2 if b not in bl1])

	def _filterHelpList(self, ent, seen):
		hlp = tuple(ent[1]) if isinstance(ent[1], (tuple, list)) else (ent[1],)
		if hlp in seen:
			self._mergeButLists(seen[hlp], ent[0][3])
			return False
		else:
			seen[hlp] = ent[0][3]
			return True

	def addListBoxContext(self, actionMapHelp, formatFlags):
		extended = (formatFlags & self.EXTENDED) >> 1
		headings = formatFlags & self.HEADINGS
		for i, ent in enumerate(actionMapHelp):
			help = ent[1]
			ent[1:] = [None] * (1 + headings + extended)
			if isinstance(help, (tuple, list)):
				ent[1 + headings] = help[0]
				ent[2 + headings] = help[1]
			else:
				ent[1 + headings] = help
			actionMapHelp[i] = tuple(ent)

	def _getMinPos(self, a):
		# Reverse the coordinate tuple, too, to (y, x) to get
		# ordering by y then x.
		return min(map(lambda x: tuple(reversed(self.rcPos.getRcKeyPos(x[0]))), a))

	def _sortPos(self, a):
		return self._getMinPos(a[0][3])

	# Sort order "Flat by key group on remote" is really
	# "Sort in order of buttons in rcpositions.xml", and so
	# the buttons need to be grouped sensibly in that file for
	# this to work properly.

	def _getMinInd(self, a):
		return min(map(lambda x: self.rcKeyIndex[x[0]], a))

	def _sortInd(self, a):
		return self._getMinInd(a[0][3])

	def _sortKeyAlpha(self, hlp):
		# Convert normal help to extended help form for comparison
		# and ignore case
		return list(map(str.lower, hlp[1] if isinstance(hlp[1], (tuple, list)) else [hlp[1], '']))

	def _sortHeadingsAlpha(self, a):
		# ignore case
		return (getattr(a[0], "description", None) or "").lower()

	def ok(self):
		# a list entry has a "private" tuple as first entry...
		l = self.getCurrent()
		if l is None:
			return
		# ...containing (Actionmap, Context, Action, keydata).
		# we returns this tuple to the callback.
		self.callback(l[0], l[1], l[2])

	def handleButton(self, keyId, flag):
		if keyId not in self.skipKeys:
			button = (keyId, "long") if flag == 3 else (keyId,)
			if flag == 0:  # Reset the long press flag on Make.
				self.longSeen = False
			elif button in self.buttonMap and (flag == 3 or flag == 1 and not self.longSeen):  # Show help for pressed button for long press, or for Break if it's not a Long press.
					self.longSeen = flag == 3
					self.setIndex(self.buttonMap[button])
					return 1  # Report keyId handled.
		return 0  # Report keyId not handled.

	def getCurrent(self):
		sel = super(HelpMenuList, self).getCurrent()
		return sel and sel[0]
