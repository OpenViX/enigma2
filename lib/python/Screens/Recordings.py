from os.path import isdir, realpath, join as pathJoin

from Components.config import config
from Components.UsageConfig import preferredPath
from Screens.LocationBox import MovieLocationBox
from Screens.Setup import Setup
from Tools.Directories import fileExists
import Components.Harddisk


class RecordingSettings(Setup):
	def __init__(self, session):
		self.styles = [("<default>", _("<Default movie location>")), ("<current>", _("<Current movielist location>")), ("<timer>", _("<Last timer location>"))]
		self.styleKeys = [x[0] for x in self.styles]
		self.buildChoices("DefaultPath", config.usage.default_path, None)
		self.buildChoices("TimerPath", config.usage.timer_path, None)
		self.buildChoices("InstantPath", config.usage.instantrec_path, None)
		self.errorItem = -1
		Setup.__init__(self, session=session, setup="recording")
		self.greenText = self["key_green"].text
		if self.getCurrentItem() in (config.usage.default_path, config.usage.timer_path, config.usage.instantrec_path):
			self.pathStatus(self.getCurrentValue())
		self.changedEntry()

	def buildChoices(self, item, configEntry, path):
		configList = config.movielist.videodirs.value[:]
		styleList = [] if item == "DefaultPath" else self.styleKeys
		if configEntry.saved_value and configEntry.saved_value not in styleList + configList:
			configList.append(configEntry.saved_value)
			configEntry.value = configEntry.saved_value
		if path is None:
			path = configEntry.value
		if path and path not in styleList + configList:
			configList.append(path)
		pathList = [(x, x) for x in configList] if item == "DefaultPath" else self.styles + [(x, x) for x in configList]
		configEntry.value = path
		configEntry.setChoices(pathList, default=configEntry.default)
		# print("[Recordings] DEBUG %s: Current='%s', Default='%s', Choices='%s'." % (item, configEntry.value, configEntry.default, styleList + configList))

	def pathSelect(self, path):
		if path is not None:
			path = pathJoin(path, "")
			item = self.getCurrentItem()
			if item is config.usage.default_path:
				self.buildChoices("DefaultPath", config.usage.default_path, path)
			else:
				self.buildChoices("DefaultPath", config.usage.default_path, None)
			if item is config.usage.timer_path:
				self.buildChoices("TimerPath", config.usage.timer_path, path)
			else:
				self.buildChoices("TimerPath", config.usage.timer_path, None)
			if item is config.usage.instantrec_path:
				self.buildChoices("InstantPath", config.usage.instantrec_path, path)
			else:
				self.buildChoices("InstantPath", config.usage.instantrec_path, None)
		self["config"].invalidateCurrent()
		self.changedEntry()

	def pathStatus(self, path):
		if path.startswith("<"):
			self.errorItem = -1
			self.footnote = ""
			green = self.greenText
		elif not isdir(path):
			self.errorItem = self["config"].getCurrentIndex()
			self.footnote = _("Directory '%s' does not exist.") % path
			green = ""
		elif not self.isValidPartition(path):
			self.errorItem = self["config"].getCurrentIndex()
			self.footnote = _("Directory '%s' not valid. Partition must be ext or nfs.") % path
			green = ""
		elif not fileExists(path, "w"):
			self.errorItem = self["config"].getCurrentIndex()
			self.footnote = _("Directory '%s' not writable.") % path
			green = ""
		else:
			self.errorItem = -1
			self.footnote = ""
			green = self.greenText
		self.setFootnote(self.footnote)
		self["key_green"].text = green

	def isValidPartition(self, path):
		if path is not None:
			supported_filesystems = ('ext4', 'ext3', 'ext2', 'nfs', 'cifs', 'ntfs')
			valid_partitions = []
			for partition in Components.Harddisk.harddiskmanager.getMountedPartitions():
				if partition.filesystem() in supported_filesystems:
					valid_partitions.append(partition.mountpoint)
			print("[" + self.__class__.__name__ + "] valid partitions", valid_partitions)
			if valid_partitions:
				return Components.Harddisk.findMountPoint(realpath(path)) + '/' in valid_partitions or Components.Harddisk.findMountPoint(realpath(path)) in valid_partitions
		return False

	def selectionChanged(self):
		if self.errorItem == -1:
			Setup.selectionChanged(self)
		else:
			self["config"].setCurrentIndex(self.errorItem)

	def changedEntry(self):
		if self.getCurrentItem() in (config.usage.default_path, config.usage.timer_path, config.usage.instantrec_path):
			self.pathStatus(self.getCurrentValue())
		Setup.changedEntry(self)

	def keySelect(self):
		item = self.getCurrentItem()
		if item in (config.usage.default_path, config.usage.timer_path, config.usage.instantrec_path):
			# print("[Recordings] DEBUG: '%s', '%s', '%s'." % (self.getCurrentEntry(), item.value, preferredPath(item.value)))
			self.session.openWithCallback(self.pathSelect, MovieLocationBox, self.getCurrentEntry(), preferredPath(item.value))
		else:
			Setup.keySelect(self)

	def keySave(self):
		if self.errorItem == -1:
			Setup.keySave(self)
