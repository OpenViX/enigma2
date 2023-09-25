from os import listdir, path, readlink, symlink, unlink
from enigma import eConsoleAppContainer

class CamControl:
	'''CAM convention is that a softlink named /etc/init.c/softcam.* points
	to the start/stop script.'''

	def __init__(self, name):
		self.name = name
		print("[CamControl] self.name=%s" % self.name)
		self.link = '/etc/init.d/' + name
		print("[CamControl] self.link=%s" % self.link)
		if not path.exists(self.link):
			print("[CamControl] No softcam link %s" % self.link)

	def getList(self):
		result = []
		prefix = self.name + '.'
		for f in listdir("/etc/init.d"):
			if f.startswith(prefix):
				result.append(f[len(prefix):])
		print("[CamControl][getList] returnlist=%s" % result)
		return result


	def getConfigs(self, prefix):
		configs = []
		if path.exists("/etc/tuxbox/config/%s" % prefix):
			configs = listdir("/etc/tuxbox/config/%s" % prefix)
		print("[CamControl][getList] configs=%s" % configs)
		return configs

	def current(self):
		try:
			l = readlink(self.link)
			prefix = self.name + '.'
			return path.split(l)[1].split(prefix, 2)[1]
		except:
			pass
		return None

	def command(self, cmd):
		if path.exists(self.link):
			cmd = "%s %s" % (self.link, cmd)
			print("[CamControl][command]Executing %s" % cmd)
			eConsoleAppContainer().execute(cmd)

	def select(self, cam):
		print("[CamControl]Selecting CAM:%s" % cam)
		if not cam:
			cam = "None"
		dst = "%s.%s" % (self.name, cam)
		print("[CamControl][select] dst:%s" % dst)
		if not path.exists("/etc/init.d/%s" % dst):
			print("[CamControl][select] init script does not exist:%s" % dst)
			return
		try:
			print("[CamControl][select][unlink] self.link=%s " % self.link)
			unlink(self.link)
		except:
			pass
		try:
			print("[CamControl][select][symlink] dst=%s self.link=%s" % (dst, self.link))
			symlink(dst, self.link)
		except:
			print("[CamControl][select] Failed to create symlink for softcam:%s" % dst)
			import sys
			print("[CamControl][select] sys info = %s" % sys.exc_info()[:2])
