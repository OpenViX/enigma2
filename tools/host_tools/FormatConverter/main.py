#!/usr/bin/python
from os import system as ossystem

from . import datasource
from . import satxml
from . import lamedb
from . import input

maindata = datasource.genericdatasource()

sources = [satxml, lamedb]

datasources = [maindata]

for source in sources:
	datasources.append(source())

for source in datasources:
	source.setDatasources(datasources)

while True:
	ossystem("/usr/bin/clear")
	list = []
	for index in list(range(len(datasources))):
		list.append(datasources[index].getName() + (" (%d sats)" % len(datasources[index].transponderlist.keys())))
	index = input.inputChoices(list, "q", "quit")
	if index is None:
		break

	while True:
		print(datasources[index].getStatus())
		list = []
		for action in datasources[index].getCapabilities():
			list.append(action[0])
		action = input.inputChoices(list)
		if action is None:
			break

		datasources[index].getCapabilities()[action][1]()
