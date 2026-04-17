class classproperty:
	def __init__(self, func):
		self.func = func

	def __get__(self, instance, owner):
		return self.func(owner)
