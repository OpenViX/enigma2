from os import listdir

from Components.config import config
from Components.Console import Console
from Tools.Directories import SCOPE_KEYMAPS, pathExists, resolveFilename


class Keyboard:
	def __init__(self):
		self.keyboardMaps = []
		self.readKeyboardMapFiles()

	def readKeyboardMapFiles(self):
		for keymapFile in listdir(resolveFilename(SCOPE_KEYMAPS)):
			if keymapFile.endswith(".info"):
				mapFile = None
				mapName = None
				try:
					with open(resolveFilename(SCOPE_KEYMAPS, keymapFile), "r") as fd:
						for line in fd.readlines():
							key, val = [x.strip() for x in line.split("=", 1)]
							if key == "kmap":
								mapFile = val
							if key == "name":
								mapName = val
				except (IOError, OSError) as err:
					print("[Keyboard] Error %d: Opening keymap file '%s'! (%s)" % (err.errno, keymapFile, err.strerror))
				if mapFile is not None and mapName is not None:
					print("[Keyboard] Adding keymap '%s' ('%s')." % (mapName, mapFile))
					self.keyboardMaps.append((mapFile, mapName))

	def activateKeyboardMap(self, index):
		try:
			keymap = self.keyboardMaps[index]
			print("[Keyboard] Activating keymap: '%s'." % keymap[1])
			keymapPath = resolveFilename(SCOPE_KEYMAPS, keymap[0])
			if pathExists(keymapPath):
				Console().ePopen("loadkmap < %s" % keymapPath)
		except IndexError:
			print("[Keyboard] Error: Selected keymap does not exist!")

	def getKeyboardMaplist(self):
		return self.keyboardMaps

	def getDefaultKeyboardMap(self):
		for map in self.keyboardMaps:
			if "eng.kmap" == map[0] and config.osd.language.value.startswith("en_"):
		 		return "eng.kmap"
			else:
				continue
		return "default.kmap"		# this is US for some strange reason


keyboard = Keyboard()
