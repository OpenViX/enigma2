from os import path

from Components.Harddisk import harddiskmanager


def getMountChoices():
	choices = []
	for p in harddiskmanager.getMountedPartitions():
		if p.mountpoint != "/" and path.exists(p.mountpoint):
			d = path.normpath(p.mountpoint)
			entry = (f"{d}/", d)  # example: entry = ("/media/hdd/", "/media/hdd")
			if entry not in choices:
				choices.append(entry)
	choices.sort(key=lambda x: (not x[0].startswith("/media/hdd"), x[0]))  # /media/hdd at index(0) if present
	return choices


def getMountDefault(choices):
	choices = {x[1]: x[0] for x in choices}
	default = choices.get("/media/hdd") or choices.get("/media/usb")
	return default
