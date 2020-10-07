class UserDefinedButtons:
	def __init__(self, config, *args):
		self.__config = config
		# roll the args into a single dictionary of actions
		# each value is a list where the first item is the button text and the optional second item is the help text
		self.__actions = {}
		for actions in args:
			for action in actions:
				self.__actions[action[0]] = list(action[1:])

	def setActionButtonText(self, actionName, buttonText):
		self.__actions[actionName][0] = buttonText
		self._updateButtonText(actionName)

	def __getActionName(self, keyName):
		buttonConfig = self.__config.dict().get("btn_" + keyName, None)
		return buttonConfig.value if buttonConfig is not None else None

	# build a key action suitable for an ActionMap
	def keyAction(self, keyName):
		def keypressHandler():
			actionName = self.__getActionName(keyName)
			# if do nothing is defined then...do nothing
			if actionName is None or len(actionName) == 0:
				return
			actions = actionName.split("/")
			if len(actions) == 1:
				action = getattr(self, actions[0], None)
				if action:
					action()
				else:
					print "[UserDefinedButtons] Missing action method", actionName
			elif len(actions) > 1 and actions[0] == "close":
				self.close(*(actions[1:]))
		return keypressHandler

	# build a tuple suitable for using in a helpable action
	def helpKeyAction(self, keyName):
		actionName = self.__getActionName(keyName)
		action = self.__actions.get(actionName, None)
		return (self.keyAction(keyName), _("Do nothing") if action is None else action[-1])

	def _updateButtonText(self, updateActionName=None):
		for keyName in ("red", "green", "yellow", "blue"):
			widgetName = "key_" + keyName
			if widgetName in self:
				actionName = self.__getActionName(keyName)
				if updateActionName is None or actionName == updateActionName:
					action = self.__actions.get(actionName, None)
					if action is None or actionName == "":
						self[widgetName].hide()
					else:
						self[widgetName].setText(action[0])
						self[widgetName].show()
