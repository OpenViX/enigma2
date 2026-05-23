from os import listdir
from os.path import join, normpath, isdir
from re import compile

from enigma import ePixmap, eServiceCenter, eServiceReference, iServiceInformation, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER, BT_VALIGN_CENTER

from Components.config import config
from Components.Harddisk import harddiskmanager
from Components.Renderer.Renderer import Renderer
from Tools.Alternatives import GetWithAlternative
from Tools.Directories import pathExists, SCOPE_CURRENT_SKIN, resolveFilename, sanitizeFilename


class PiconLocator:
	EXT_PRIORITY = {
		"png_only": (".png",),
		"svg_only": (".svg",),
		"png_svg": (".png", ".svg"),
		"svg_png": (".svg", ".png")}

	CONTROL_CHARS = {  # DVB control characters for removal from the service name
		0x80: None,
		0x86: None,
		0x87: None}

	LEGACY_TRANSLATION = {
		ord("&"): "and",
		ord("+"): "plus",
		ord("*"): "star"}

	SUFFIX_RE = compile(r"(fhd|uhd|hd|sd|4k)$")   # for suffix removal
	LEGACY_RE = compile("[^a-z0-9]")  # legacy only allows lower case letters and numbers

	def __init__(self, piconDirectories=None):
		if piconDirectories is None:
			piconDirectories = ["picon"]
		harddiskmanager.on_partition_list_change.append(self.__onPartitionChange)
		self.piconDirectories = piconDirectories
		self.activePiconPath = None
		self.searchPaths = []
		for mp in ("/usr/share/enigma2", "/"):
			self.__onMountpointAdded(mp)
		for part in harddiskmanager.getMountedPartitions():
			self.__onMountpointAdded(part.mountpoint)

	def __onMountpointAdded(self, mountpoint):
		for piconDirectory in self.piconDirectories:
			try:
				path = join(normpath(mountpoint), piconDirectory)
				if isdir(path) and path not in self.searchPaths:
					for fn in listdir(path):
						if fn.endswith((".png", ".svg")):
							print("[PiconLocator] adding path:", path)
							self.searchPaths.append(path)
							break
			except Exception as err:
				print("[PiconLocator] Error adding mount point", err)

	def __onMountpointRemoved(self, mountpoint):
		for piconDirectory in self.piconDirectories:
			path = join(normpath(mountpoint), piconDirectory)
			if path in self.searchPaths:
				self.searchPaths.remove(path)
				print("[PiconLocator] removed path:", path)
				if path == self.activePiconPath:
					self.activePiconPath = None

	def __onPartitionChange(self, why, part):
		if why == "add":
			self.__onMountpointAdded(part.mountpoint)
		elif why == "remove":
			self.__onMountpointRemoved(part.mountpoint)

	def findPicon(self, service):
		exts = self.EXT_PRIORITY[config.usage.picon_lookup_priority.value]  # must go here because this function is used externally
		if self.activePiconPath:
			for ext in exts:
				pngname = join(self.activePiconPath, service + ext)
				if pathExists(pngname):
					return pngname
		else:
			for path in self.searchPaths:
				for ext in exts:
					pngname = join(path, service + ext)
					if pathExists(pngname):
						self.activePiconPath = path
						return pngname
		return ""

	def addSearchPath(self, value):
		value = normpath(value)
		if pathExists(value) and not value.startswith(("/media/net", "/media/autofs")) and value not in self.searchPaths:
			self.searchPaths.append(value)

	def __iterServiceRefPiconCandidates(self, serviceRef):
		# remove the path and name fields, and replace ":" with "_"
		fields = GetWithAlternative(serviceRef).split(":", 10)[:10]
		if len(fields) < 10:
			return

		yield "_".join(fields)        # exact service reference

		x = "_".join(fields[3:7])     # SID/TSID/ONID/namespace fields
		p = "1_0_1_%s_0_0_0"          # canonical service reference pattern

		yield p % x                   # canonical service reference (SID/TSID/ONID/namespace, normalized)
		yield p % (x[:-4] + "0000")   # canonical service reference with namespace-subnet wildcard

	def __iterServiceNamePiconCandidates(self, serviceRef):
		sname = eServiceReference(serviceRef).getServiceName().translate(self.CONTROL_CHARS)

		if not sname or "SID 0x" in sname:
			return

		utf8_name = sanitizeFilename(sname).lower()
		if utf8_name == "__":  # sname sanitized was zero length
			return
		yield utf8_name

		legacy_name = self.LEGACY_RE.sub("", utf8_name.translate(self.LEGACY_TRANSLATION))
		yield legacy_name

		yield self.SUFFIX_RE.sub("", utf8_name).strip()    # utf8_no_suffix
		yield self.SUFFIX_RE.sub("", legacy_name).strip()  # legacy_no_suffix

	def getPiconName(self, serviceRef):
		if not serviceRef:
			return ""

		service = eServiceReference(serviceRef)
		if service.getPath().startswith("/") and serviceRef.startswith("1:"):  # for when serviceRef is a recording path
			info = eServiceCenter.getInstance().info(service)
			refstr = info and info.getInfoString(service, iServiceInformation.sServiceref)
			serviceRef = refstr and eServiceReference(refstr).toCompareString()

		if not serviceRef:  # serviceRef could be None if something failed in the block above
			return ""

		dedupe = set()
		for generator in self.__iterServiceRefPiconCandidates(serviceRef), self.__iterServiceNamePiconCandidates(serviceRef):
			for candidate in generator:
				if not candidate or candidate in dedupe:
					continue
				dedupe.add(candidate)
				if pngname := self.findPicon(candidate):
					return pngname
		return ""


piconLocator = None


def initPiconPaths():
	global piconLocator
	piconLocator = PiconLocator()


initPiconPaths()


def getPiconName(serviceRef):
	return piconLocator.getPiconName(serviceRef)


class Picon(Renderer):
	def __init__(self):
		Renderer.__init__(self)
		self.pngname = None
		self.defaultpngname = resolveFilename(SCOPE_CURRENT_SKIN, "picon_default.png")
		if not pathExists(self.defaultpngname):
			self.defaultpngname = ""

	def applySkin(self, desktop, parent):
		new_attrs = []
		for attrib, value in self.skinAttributes:
			if attrib == "path":
				piconLocator.addSearchPath(value)
				continue
			new_attrs.append((attrib, value))
		self.skinAttributes = new_attrs
		rc = Renderer.applySkin(self, desktop, parent)
		self.changed((self.CHANGED_DEFAULT,))
		return rc

	GUI_WIDGET = ePixmap

	def changed(self, what):
		if self.instance:
			if what[0] in (self.CHANGED_DEFAULT, self.CHANGED_ALL, self.CHANGED_SPECIFIC):
				pngname = piconLocator.getPiconName(self.source.text) or self.defaultpngname
				if self.pngname != pngname:
					if pngname:
						self.instance.setPixmapScaleFlags(BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER)
						self.instance.setPixmapFromFile(pngname)
						self.instance.show()
					else:
						self.instance.hide()
					self.pngname = pngname
			elif what[0] == self.CHANGED_CLEAR:
				self.pngname = None
				self.instance.hide()
