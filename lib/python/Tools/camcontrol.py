from __future__ import print_function
import os
import enigma


class CamControl:
	'''CAM convention is that a softlink named /etc/init.c/softcam.* points
	to the start/stop script.'''

	def __init__(self, name):
		self.name = name
		print("[CamControl] self.name=%s" % self.name)
		self.link = '/etc/init.d/' + name
		print("[CamControl] self.link=%s" % self.link)
		if not os.path.exists(self.link):
			print("[CamControl] No softcam link?", self.link)

	def getList(self):
		result = noresult = []
		prefix = self.name + '.'
		for f in os.listdir("/etc/init.d"):
			if f.startswith(prefix):
				print("[CamControl][getList] softcam=%s" % f)
				result.append(f[len(prefix):])
		print("[CamControl][getList] returnlist=%s" % result)	
		if len(result) > 1:
			return result
		else:
			return False	

	def current(self):
		try:
			l = os.readlink(self.link)
			prefix = self.name + '.'
			print("[CamControl][current] prefix=%s" % prefix)
			return os.path.split(l)[1].split(prefix, 2)[1]
		except:
			pass
		return None

	def command(self, cmd):
		if os.path.exists(self.link):
			print("[CamControl][command]Executing", self.link + ' ' + cmd)
			enigma.eConsoleAppContainer().execute(self.link + ' ' + cmd)

	def select(self, which):
		print("Selecting CAM:", which)
		if not which:
			which = "None"
		dst = self.name + '.' + which
		print("[CamControl][select] dst:%s" % dst)
		if not os.path.exists('/etc/init.d/' + dst):
			print("[CamControl][select] init script does not exist:%s" % dst)
			return
		try:
			print("[CamControl][select][unlink] self.link=%s " % self.link)
			os.unlink(self.link)
		except:
			pass
		try:
			print("[CamControl][select][symlink] dst=%s self.link=%s" % (dst, self.link))
			os.symlink(dst, self.link)
		except:
			print("[CamControl][select] Failed to create symlink for softcam:%s" % dst)
			import sys
			print("[CamControl][select] sys info = %s" % sys.exc_info()[:2])
