#!/usr/bin/python
from __future__ import print_function
from . import datasource
from . import satxml
from . import lamedb

import sys

if len(sys.argv) != 3:
	print("usage: %s <lamedb> <satellites.xml>" % sys.argv[0])
	sys.exit()

gen = datasource.genericdatasource()
db = lamedb(sys.argv[1])
xml = satxml(sys.argv[2])

db.read()
gen.source = db
gen.destination = xml
gen.docopymerge(action="copy")
xml.write()
