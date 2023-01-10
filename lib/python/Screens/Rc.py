from keyids import KEYIDS
from Components.config import config, ConfigInteger
from Components.Pixmap import MovingPixmap, MultiPixmap
from Components.SystemInfo import SystemInfo
from Tools.Directories import resolveFilename, SCOPE_SKIN, fileReadXML
from Tools.KeyBindings import keyDescriptions

config.misc.rcused = ConfigInteger(default=1)


class Rc:
	def __init__(self):
		self["rc"] = MultiPixmap()

		nSelectPics = 16
		rcheights = (500,) * 2
		self.selectpics = []
		for i in range(nSelectPics):
			self.selectpics.append(
				self.KeyIndicator(
					self, rcheights,
					("indicatorL" + str(i), "indicatorU" + str(i))
				)
			)
		self.rcPositions = RcPositions()
		self.oldNSelectedKeys = self.nSelectedKeys = 0
		self.clearSelectedKeys()
		self.onLayoutFinish.append(self.initRc)

		# Test code to visit every button in turn
		# self.onExecBegin.append(self.test)

	class KeyIndicator:

		class KeyIndicatorPixmap(MovingPixmap):
			def __init__(self, activeYPos, pixmap):
				MovingPixmap.__init__(self)
				self.activeYPos = activeYPos
				self.pixmapName = pixmap

		def __init__(self, owner, activeYPos, pixmaps):
			self.pixmaps = []
			for actYpos, pixmap in zip(activeYPos, pixmaps):
				pm = self.KeyIndicatorPixmap(actYpos, pixmap)
#				print("[KeyIndicator]", actYpos, pixmap)
				owner[pixmap] = pm
				self.pixmaps.append(pm)
			self.pixmaps.sort(key=lambda x: x.activeYPos)

		def slideTime(self, frm, to, time=20):
			if not self.pixmaps:
				return time
			dist = ((to[0] - frm[0]) ** 2 + (to[1] - frm[1]) ** 2) ** 0.5
			slide = int(round(dist / self.pixmaps[-1].activeYPos * time))
			return slide if slide > 0 else 1

		def moveTo(self, pos, rcpos, moveFrom=None, time=20):
			foundActive = False
			for i in range(len(self.pixmaps)):
				pm = self.pixmaps[i]
				fromx, fromy = pm.getPosition()
				if moveFrom:
					fromPm = moveFrom.pixmaps[i]
					fromx, fromy = fromPm.getPosition()

				x = pos[0] + rcpos[0]
				y = pos[1] + rcpos[1]
				if pos[1] <= pm.activeYPos and not foundActive:
					st = self.slideTime((fromx, fromy), (x, y), time)
					pm.move(fromx, fromy)
					pm.moveTo(x, y, st)
					pm.show()
					pm.startMoving()
					foundActive = True
				else:
					pm.move(x, y)

		def hide(self):
			for pm in self.pixmaps:
				pm.hide()

	def initRc(self):
		if SystemInfo["rc_default"]:
			self["rc"].setPixmapNum(config.misc.rcused.value)
		else:
			self["rc"].setPixmapNum(0)
		rcHeight = self["rc"].getSize()[1]
		for kp in self.selectpics:
			nbreaks = len(kp.pixmaps)
			roundup = nbreaks - 1
			n = 1
			for pic in kp.pixmaps:
				pic.activeYPos = (rcHeight * n + roundup) / nbreaks
				n += 1

	def getRcPositions(self):
		return self.rcPositions

	def hideRc(self):
		self["rc"].hide()
		self.hideSelectPics()

	def showRc(self):
		self["rc"].show()

	def selectKey(self, key):
		pos = self.rcPositions.getRcKeyPos(key)

		if pos and self.nSelectedKeys < len(self.selectpics):
			rcpos = self["rc"].getPosition()
			selectPic = self.selectpics[self.nSelectedKeys]
			self.nSelectedKeys += 1
			if self.oldNSelectedKeys > 0 and self.nSelectedKeys > self.oldNSelectedKeys:
				selectPic.moveTo(pos, rcpos, moveFrom=self.selectpics[self.oldNSelectedKeys - 1], time=10)
			else:
				selectPic.moveTo(pos, rcpos, time=10)

	def clearSelectedKeys(self):
		self.showRc()
		self.oldNSelectedKeys = self.nSelectedKeys
		self.nSelectedKeys = 0
		self.hideSelectPics()

	def hideSelectPics(self):
		for selectPic in self.selectpics:
			selectPic.hide()

	# Visits all the buttons in turn, sliding between them.
	# Leaves the indicator at the incorrect position at the end of
	# the test run. Change to another entry in the help list to
	# get the indicator in the correct position
	# def test(self):
	# 	if not self.selectpics or not self.selectpics[0].pixmaps:
	# 		return
	# 	self.hideSelectPics()
	# 	pm = self.selectpics[0].pixmaps[0]
	# 	pm.show()
	# 	rcpos = self["rc"].getPosition()
	# 	for key in self.rcPositions.getRcKeyList():
	# 		pos = self.rcPositions.getRcKeyPos(key)
	# 		pm.addMovePoint(rcpos[0] + pos[0], rcpos[1] + pos[1], time=5)
	# 		pm.addMovePoint(rcpos[0] + pos[0], rcpos[1] + pos[1], time=10)
	# 	pm.startMoving()


class RcPositions:
	rc = None
	def __init__(self):
		if RcPositions.rc is not None:
			return
		descriptions = [{v[0]:k for k,v in x.items()} for x in keyDescriptions] # used by wizards and legacy xml format
		file = resolveFilename(SCOPE_SKIN, "rcpositions.xml") if SystemInfo["rc_default"] else SystemInfo["RCMapping"]
		rcs = fileReadXML(file, "<rcs />")
		remotes = {}
		machine_id = 2
		for rc in rcs.findall("rc"):
			rc_id = int(rc.attrib.get("id", machine_id))
			remotes[rc_id] = {}
			remotes[rc_id]["keyIds"] = []
			remotes[rc_id]["remaps"] = {}
			remotes[rc_id]["keyDescriptions"] = descriptions[rc_id]
			for key in rc.findall("button"):
				if  "id" in key.attrib:
					keyId = KEYIDS.get(key.attrib["id"])
				elif "name" in key.attrib: # legacy xml format
					keyId = descriptions[rc_id].get(key.attrib["name"])
				if keyId:
					remotes[rc_id]["keyIds"].append(keyId)
					remotes[rc_id][keyId] = {}
					remotes[rc_id][keyId]["label"] = key.attrib.get("name") or key.attrib.get("label", "UNKNOWN")
					remotes[rc_id][keyId]["pos"] = [int(x.strip()) for x in key.attrib.get("pos", "0,0").split(",")]
					remap = key.attrib.get("remap")
					if remap is not None and remap in KEYIDS:
						remapId = KEYIDS[remap]
						remotes[rc_id]["remaps"][keyId] = remapId
						remotes[rc_id][remapId] = remotes[rc_id][keyId] # so the button remaps in the help screen

		if SystemInfo["rc_default"]:
			RcPositions.rc = remotes[config.misc.rcused.value]
		else:
			try:
				RcPositions.rc = remotes[machine_id]
			except:
				# empty RC map just in case xml file failed to load
				RcPositions.rc = {"keyIds":[], "remaps":{}, "keyDescriptions":{}}
				print("[RcPositions] failed to load RC mapping file")

	def getRc(self):
		return self.rc

	def getRcKeyPos(self, keyId):
		if isinstance(keyId, str): # used by wizards and available to legacy code
			keyId = self.rc["keyDescriptions"].get(keyId, -1)
		if keyId in self.rc:
			return self.rc[keyId]["pos"]
		return None

	def getRcKeyLabel(self, keyId):
		if keyId in self.rc:
			return self.rc[keyId]["label"]
		return None

	def getRcKeyList(self):
		return self.rc["keyIds"]

	def getRcKeyRemaps(self):
		return self.rc["remaps"]
