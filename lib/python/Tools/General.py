def isIPTV(service):
	path = service and service.getPath()
	return path and service.type in [0x1, 0x1001, 0x138A, 0x1389]
