from os import listdir, path, readlink, symlink, unlink
from enigma import eConsoleAppContainer


class CamControl:
	'''CAM convention is that a softlink named /etc/init.c/softcam.* points
	to the start/stop script.'''

	def __init__(self, name):
		self.name = name
		print(f"[CamControl] self.name={self.name}")
		self.link = '/etc/init.d/' + name
		print(f"[CamControl] self.link={self.link}")
		if not path.exists(self.link):
			print(f"[CamControl] No softcam link {self.link}")

	def getList(self):
		result = []
		prefix = self.name + '.'
		for f in listdir("/etc/init.d"):
			if f.startswith(prefix):
				result.append(f[len(prefix):])
		print(f"[CamControl][getList] returnlist={result}")
		return result

	def getConfigs(self, prefix):
		configs = []
		if path.exists("/etc/tuxbox/config/%s" % prefix):
			configs = listdir(f"/etc/tuxbox/config/{prefix}")
		print(f"[CamControl][getList] configs={configs}")
		return configs

	def current(self):
		try:
			l = readlink(self.link)  # noqa: E741
			prefix = self.name + '.'
			return path.split(l)[1].split(prefix, 2)[1]
		except:
			pass
		return None

	def command(self, cmd):
		if path.exists(self.link):
			cmd = f"{self.link} {cmd}"
			print(f"[CamControl][command]Executing {cmd}")
			eConsoleAppContainer().execute(cmd)

	def select(self, cam):
		print(f"[CamControl]Selecting CAM:{cam}")
		if not cam:
			cam = "None"
		dst = f"{self.name}.{cam}"
		print(f"[CamControl][select] dst:{dst}")
		if not path.exists(f"/etc/init.d/{dst}"):
			print(f"[CamControl][select] init script does not exist:{dst}")
			return
		try:
			print(f"[CamControl][select][unlink] self.link={self.link} ")
			unlink(self.link)
		except:
			pass
		try:
			print(f"[CamControl][select][symlink] dst={dst} self.link={self.link}")
			symlink(dst, self.link)
		except:
			print(f"[CamControl][select] Failed to create symlink for softcam:{dst}")
			import sys
			print(f"[CamControl][select] sys info = {sys.exc_info()[:2]}")
