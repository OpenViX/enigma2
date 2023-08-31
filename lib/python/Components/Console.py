import enigma
from os import waitpid


class ConsoleItem:
	def __init__(self, containers, cmd, callback, extra_args, binary=False):
		self.extra_args = extra_args
		self.callback = callback
		self.container = enigma.eConsoleAppContainer()
		self.containers = containers
		self.binary = binary
		if isinstance(cmd, str):  # until .execute supports a better api
			cmd = [cmd]
		# Create a unique name
		name = cmd[0]
		if name in containers:
			name = str(cmd) + '@' + hex(id(self))
		self.name = name
		containers[name] = self
		# If the caller isn't interested in our results, we don't need
		# to store the output either.
		if callback is not None:
			self.appResults = []
			self.container.dataAvail.append(self.dataAvailCB)
		self.container.appClosed.append(self.finishedCB)
		retval = self.container.execute(*cmd)
		if retval:
			self.finishedCB(retval)
		if callback is None:
			pid = self.container.getPID()
			try:
				waitpid(pid, 0)
			except OSError:
				pass

	def dataAvailCB(self, data):
		self.appResults.append(data)

	def finishedCB(self, retval):
		print("[Console] finished:", self.name)
		del self.containers[self.name]
		del self.container.dataAvail[:]
		del self.container.appClosed[:]
		del self.container
		callback = self.callback
		if callback is not None:
			data = b''.join(self.appResults)
			data = data if self.binary else data.decode()
			callback(data, retval, self.extra_args)


class Console:
	"""
		Console by default will work with strings on callback.
		If binary data required class shoud be initialized with Console(binary=True)
	"""

	def __init__(self, binary=False):
		# Still called appContainers because Network.py accesses it to
		# know if there's still stuff running
		self.appContainers = {}
		self.binary = binary

	def ePopen(self, cmd, callback=None, extra_args=[]):
		print("[Console] command:", cmd)
		return ConsoleItem(self.appContainers, cmd, callback, extra_args, self.binary)

	def eBatch(self, cmds, callback, extra_args=None, debug=False):
		if not extra_args:
			extra_args = []
		self.debug = debug
		cmd = cmds.pop(0)
		self.ePopen(cmd, self.eBatchCB, [cmds, callback, extra_args])

	def eBatchCB(self, data, retval, _extra_args):
		(cmds, callback, extra_args) = _extra_args
		if self.debug:
			print('[Console][eBatch] retval=%s, cmds=%s cmds left=%d, data:\n%s' % (retval, cmds, len(cmds), data))
		if cmds:
			cmd = cmds.pop(0)
			self.ePopen(cmd, self.eBatchCB, [cmds, callback, extra_args])
		else:
			callback(extra_args)

	def kill(self, name):
		if name in self.appContainers:
			print("[Console] killing: ", name)
			self.appContainers[name].container.kill()

	def killAll(self):
		for name, item in self.appContainers.items():
			print("[Console] killing: ", name)
			item.container.kill()
