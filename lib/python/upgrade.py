from os import listdir, path as ospath, system

opkgDestinations = ['/']
opkgStatusPath = ''


def findMountPoint(path):
	"""Example: findMountPoint("/media/hdd/some/file") returns "/media/hdd\""""
	path = ospath.abspath(path)
	while not ospath.ismount(path):
		path = ospath.dirname(path)
	return path


def opkgExtraDestinations():
	global opkgDestinations
	return ''.join([" --add-dest %s:%s" % (i, i) for i in opkgDestinations])


def opkgAddDestination(mountpoint):
	global opkgDestinations
	if mountpoint not in opkgDestinations:
		opkgDestinations.append(mountpoint)
		print("[Ipkg] Added to OPKG destinations:", mountpoint)


mounts = listdir('/media')
for mount in mounts:
	mount = ospath.join('/media', mount)
	if mount and not mount.startswith('/media/net'):
		if opkgStatusPath == '':
			# recent opkg versions
			opkgStatusPath = 'var/lib/opkg/status'
			if not ospath.exists(ospath.join('/', opkgStatusPath)):
				# older opkg versions
				opkgStatusPath = 'usr/lib/opkg/status'
		if ospath.exists(ospath.join(mount, opkgStatusPath)):
			opkgAddDestination(mount)

system("(echo 'Updating Sysvinit' && opkg upgrade sysvinit && \
echo 'Updating Sysvinit-pidof' && opkg upgrade sysvinit-pidof && \
echo 'Updating Initscripts-functions' && opkg upgrade initscripts-functions && \
echo 'Updating Busybox' && opkg upgrade busybox && \
echo 'Updating Kmod' && opkg upgrade kmod && \
echo 'Updating Main system' && opkg " + opkgExtraDestinations() + " list-upgradable | cut -f 1 -d ' ' | xargs opkg " + opkgExtraDestinations() + " upgrade) 2>&1 | tee /home/root/ipkgupgrade.log && reboot")
