class ListHeader(tuple):
	"""A header entry for any kind of listbox: a non selectable title that the listbox paints with the header style
	of the skin (headerFont, headerForegroundColor, headerBackgroundColor, headerHeight, ... attributes of the
	widget). Put it in the list like any other entry:

		self["list"].setList([ListHeader(_("Movies")), ("Alien", 1), ("Heat", 2), ListHeader(_("Series")), ("Lost", 3)])

	The cursor never stops on it, getCurrent() never returns it. It is a one element tuple so that engines without
	header support at least show the text as a greyed out entry.

	For config lists use the HEADER element instead: getConfigListEntry(_("Title"), HEADER)."""

	isListHeader = True

	def __new__(cls, text):
		return tuple.__new__(cls, (text,))
