class SessionObject:
	__session = None

	def setSession(self, Session):
		SessionObject.__session = Session

	def getSession(self):
		return self.__session

	session = property(getSession, setSession)
