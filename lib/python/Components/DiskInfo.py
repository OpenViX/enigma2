from __future__ import absolute_import
from __future__ import division

from os import statvfs

from enigma import eLabel
from Components.GUIComponent import GUIComponent
from Components.VariableText import VariableText


# TODO: Harddisk.py has similiar functions, but only similiar.
# fix this to use same code
class DiskInfo(VariableText, GUIComponent):
	FREE = 0
	USED = 1
	SIZE = 2

	def __init__(self, path, type, update=True):
		GUIComponent.__init__(self)
		VariableText.__init__(self)
		self.type = type
		self.path = path
		if update:
			self.update()

	def update(self):
		try:
			stat = statvfs(self.path)
		except OSError:
			return -1

		if self.type == self.FREE:
			try:
				percent = '(' + str((100 * stat.f_bavail) // stat.f_blocks) + '%)'
				free = stat.f_bfree * stat.f_bsize
				if free < 10000000:
					free = _("%d kB") % (free >> 10)
				elif free < 10000000000:
					free = _("%d MB") % (free >> 20)
				else:
					free = _("%d GB") % (free >> 30)
				self.setText(" ".join((free, percent, _("free diskspace"))))
			except:
				# occurs when f_blocks is 0 or a similar error
				self.setText("-?-")

	GUI_WIDGET = eLabel
