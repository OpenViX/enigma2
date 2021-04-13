from enigma import eServiceCenter, eServiceReference


def getServiceRef(service):
	if isinstance(service, eServiceReference):
		return service.ref if hasattr(service, "ref") else service
	elif isinstance(service, str):
		return eServiceReference(service)
	else:
		return eServiceReference()


def getAlternativeChannels(service):
	alternativeServices = eServiceCenter.getInstance().list(getServiceRef(service))
	return alternativeServices and alternativeServices.getContent("S", True)

# Get alternatives in a form useful for equality comparison: in
# eServiceReference.toCompareString() form


def getAlternativeChannelsCompare(service):
	alternativeServices = eServiceCenter.getInstance().list(getServiceRef(service))
	return alternativeServices and alternativeServices.getContent("C", True)

# Get alternatives in a form useful for equality comparison:
# as eServiceReference instances


def getAlternativeChannelsSRef(service):
	alternativeServices = eServiceCenter.getInstance().list(getServiceRef(service))
	return alternativeServices and alternativeServices.getContent("R", True)

# Compare service using alternatices, ensuring the serviceref strings
# are compared in eServiceReference.toCompareString() form


def CompareWithAlternatives(serviceA, serviceB):
	serviceA = getServiceRef(serviceA)
	serviceB = getServiceRef(serviceB)
	return serviceA and serviceB and (
		serviceA == serviceB or
		serviceA.type == 0 and serviceA.flags == 134 and serviceB in getAlternativeChannelsSRef(serviceA) or
		serviceB.type == 0 and serviceB.flags == 134 and serviceB in getAlternativeChannelsSRef(serviceB)
	)

# Get a service's first alternative


def GetWithAlternative(service):
	service = getServiceRef(service)
	if service.type == 0 and service.flags == 134:
		channels = getAlternativeChannels(service)
		if channels:
			return channels[0]
	return service.toString()
