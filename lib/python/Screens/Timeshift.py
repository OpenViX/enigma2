from os import link, remove, stat
from os.path import isdir, join as pathJoin, splitext
from tempfile import NamedTemporaryFile

from Components.config import config
from Screens.LocationBox import defaultInhibitDirs, TimeshiftLocationBox
from Screens.MessageBox import MessageBox
from Screens.Setup import Setup
from Tools.Directories import fileExists


class TimeshiftSettings(Setup):
	def __init__(self, session):
		self.inhibitDevs = []
		for dir in defaultInhibitDirs + ["/", "/media"]:
			if isdir(dir):
				device = stat(dir).st_dev
				if device not in self.inhibitDevs:
					self.inhibitDevs.append(device)
		self.buildChoices("TimeshiftPath", config.usage.timeshift_path, None)
		Setup.__init__(self, session=session, setup="timeshift")
		self.greenText = self["key_green"].text
		self.errorItem = -1
		if self.getCurrentItem() is config.usage.timeshift_path:
			self.pathStatus(self.getCurrentValue())

	def buildChoices(self, item, configEntry, path):
		configList = config.usage.allowed_timeshift_paths.value[:]
		if configEntry.saved_value and configEntry.saved_value not in configList:
			configList.append(configEntry.saved_value)
			configEntry.value = configEntry.saved_value
		if path is None:
			path = configEntry.value
		if path and path not in configList:
			configList.append(path)
		pathList = [(x, x) for x in configList]
		configEntry.value = path
		configEntry.setChoices(pathList, default=configEntry.default)
		print("[Timeshift] %s: Current='%s', Default='%s', Choices='%s'" % (item, configEntry.value, configEntry.default, configList))

	def pathSelect(self, path):
		if path is not None:
			path = pathJoin(path, "")
			self.buildChoices("TimeshiftPath", config.usage.timeshift_path, path)
		self["config"].invalidateCurrent()
		self.changedEntry()

	def pathStatus(self, path):
		if not isdir(path):
			self.errorItem = self["config"].getCurrentIndex()
			footnote = _("Directory '%s' does not exist!") % path
			green = ""
		elif stat(path).st_dev in self.inhibitDevs:
			self.errorItem = self["config"].getCurrentIndex()
			footnote = _("Flash directory '%s' not allowed!") % path
			green = ""
		elif not fileExists(path, "w"):
			self.errorItem = self["config"].getCurrentIndex()
			footnote = _("Directory '%s' not writeable!") % path
			green = ""
		elif not self.hasHardLinks(path):
			self.errorItem = self["config"].getCurrentIndex()
			footnote = _("Directory '%s' can't be linked to recordings!") % path
			green = ""
		else:
			self.errorItem = -1
			footnote = ""
			green = self.greenText
		self.setFootnote(footnote)
		self["key_green"].text = green

	def hasHardLinks(self, path):
		try:
			tmpfile = NamedTemporaryFile(suffix='.file', prefix='tmp', dir=path, delete=False)
		except (IOError, OSError) as err:
			print("[Timeshift] DEBUG: Create temp file - I/O Error %d: %s!" % (err.errno, err.strerror))
			return False
		srcname = tmpfile.name
		tmpfile.close()
		dstname = "%s.link" % splitext(srcname)[0]
		try:
			link(srcname, dstname)
			result = True
		except (IOError, OSError) as err:
			print("[Timeshift] DEBUG: Create link - I/O Error %d: %s!" % (err.errno, err.strerror))
			result = False
		try:
			remove(srcname)
		except (IOError, OSError) as err:
			print("[Timeshift] DEBUG: Remove source - I/O Error %d: %s!" % (err.errno, err.strerror))
			pass
		try:
			remove(dstname)
		except (IOError, OSError) as err:
			print("[Timeshift] DEBUG: Remove target - I/O Error %d: %s!" % (err.errno, err.strerror))
			pass
		return result

	def selectionChanged(self):
		if self.errorItem == -1:
			Setup.selectionChanged(self)
		else:
			self["config"].setCurrentIndex(self.errorItem)

	def changedEntry(self):
		if self.getCurrentItem() is config.usage.timeshift_path:
			self.pathStatus(self.getCurrentValue())
		Setup.changedEntry(self)

	def keySelect(self):
		if self.getCurrentItem() is config.usage.timeshift_path:
			self.session.openWithCallback(self.pathSelect, TimeshiftLocationBox)
		else:
			Setup.keySelect(self)

	def keySave(self):
		if self.errorItem == -1:
			Setup.keySave(self)
		else:
			self.session.open(MessageBox, "%s\n\n%s" % (self.getFootnote() % _("Please select an acceptable directory.")), type=MessageBox.TYPE_ERROR)
