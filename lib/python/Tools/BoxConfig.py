#
#	derived from code by OpenVision now in OE-A replacing earlier BoxBranding extraction code  code by Huevos 
#	this version uses the base functionality without reinventing the wheel  
#
import errno


class BoxConfig:  # To maintain data integrity class variables should not be accessed from outside of this class!
	def __init__(self, root=""):
		self.procList = []
		self.boxInfo = {}
		path = "%s/usr/lib/enigma.info" % root
		# print("[BoxConfig] BoxConfig Info path = %s." % path)	
		lines = None		
		try:
			with open(path, "r") as fd:
				lines = fd.read().splitlines()
		except (IOError, OSError) as err:
			if err.errno != errno.ENOENT:  # ENOENT - No such file or directory.
				print("[BoxConfig] Error %d: Unable to read lines from file '%s'! (%s)" % (err.errno, path, err.strerror))
		if lines:
			for line in lines:
				if line.startswith("#") or line.strip() == "":
					continue
				if "=" in line:
					item, value = [x.strip() for x in line.split("=", 1)]
					if item:
						self.procList.append(item)
						self.boxInfo[item] = self.processValue(value)
			self.procList = sorted(self.procList)
			# print("[BoxConfig] Information file data loaded into BoxConfig.")
			# print("[BoxConfig] ProcList = %s." % self.procList)
			# print("[BoxConfig] BoxInfo = %s." % self.boxInfo)			
		else:
			print("[BoxConfig] ERROR: Information file is not available!  The system is unlikely to boot or operate correctly.")


	def processValue(self, value):
		if value is None:
			pass
		elif value.startswith("\"") or value.startswith("'") and value.endswith(value[0]):
			value = value[1:-1]
		elif value.startswith("(") and value.endswith(")"):
			data = []
			for item in [x.strip() for x in value[1:-1].split(",")]:
				data.append(self.processValue(item))
			value = tuple(data)
		elif value.startswith("[") and value.endswith("]"):
			data = []
			for item in [x.strip() for x in value[1:-1].split(",")]:
				data.append(self.processValue(item))
			value = list(data)
		elif value.upper() == "NONE":
			value = None
		elif value.upper() in ("FALSE", "NO", "OFF", "DISABLED"):
			value = False
		elif value.upper() in ("TRUE", "YES", "ON", "ENABLED"):
			value = True
		elif value.isdigit() or (value[0:1] == "-" and value[1:].isdigit()):
			value = int(value)
		elif value.startswith("0x") or value.startswith("0X"):
			value = int(value, 16)
		elif value.startswith("0o") or value.startswith("0O"):
			value = int(value, 8)
		elif value.startswith("0b") or value.startswith("0B"):
			value = int(value, 2)
		else:
			try:
				value = float(value)
			except ValueError:
				pass
		return value

	def getProcList(self):
		return self.procList

	def getItemsList(self):
		return sorted(list(self.boxInfo.keys()))

	def getItem(self, item, default=None):
		if item in self.boxInfo:
			value = self.boxInfo[item]
		else:
			value = default
		return value

	def setItem(self, item, value):
		self.boxInfo[item] = value
		return True

	def deleteItem(self, item):
		if item in self.procList:
			print("[BoxConfig] Error: Item '%s' is immutable and can not be deleted!" % item)
		elif item in self.boxInfo:
			del self.boxInfo[item]
			return True
		return False
