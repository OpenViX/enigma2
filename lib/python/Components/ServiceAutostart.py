from os.path import exists
import glob

from Components.config import config, configfile, ConfigSubsection, ConfigSelection
from Components.Console import Console

# Autostart for the services in Network utilities is only the boot links in /etc/rc*.d.
# Those are not in a backup, and when a restore reinstalls a package its install script
# switches autostart back on. So the choice made in Network utilities is also kept in
# the settings file (which every backup includes) and put back at every enigma2 start.

# init script name: extra arguments for "update-rc.d <name> defaults"
SERVICES = {
	"atalk": "",
	"inadyn-mt": "",
	"minidlna": "",
	"nfsserver": "13",
	"openvpn": "",
	"samba": "",
	"telnetd.busybox": "",
	"ushare": "",
	"vsftpd": "",
}

config.networkservices = ConfigSubsection()
for name in SERVICES:
	# "unset" until a choice is known: applyServiceAutostart() records the current state
	# at the first start, and Network utilities updates it when autostart is switched
	setattr(config.networkservices, name.replace(".", "_").replace("-", "_"), ConfigSelection(default="unset", choices=["unset", "on", "off"]))

console = Console(binary=True)


def serviceIsEnabled(name):
	return len(glob.glob("/etc/rc2.d/S*" + name)) > 0


def autostartCommand(name, enable):
	if enable:
		return ("update-rc.d -f %s defaults %s" % (name, SERVICES.get(name, ""))).strip()
	return "update-rc.d -f %s remove" % name


def setServiceAutostart(name, enable):
	"""Remember the choice in the settings file and return the update-rc.d command for it."""
	setting = getattr(config.networkservices, name.replace(".", "_").replace("-", "_"))
	setting.value = "on" if enable else "off"
	setting.save()
	configfile.save()
	return autostartCommand(name, enable)


def applyServiceAutostart():
	"""Make each service's boot links match the choice saved in the settings file."""
	commands = []
	changed = False
	for name in SERVICES:
		setting = getattr(config.networkservices, name.replace(".", "_").replace("-", "_"))
		if not exists("/etc/init.d/" + name):
			continue
		enabled = serviceIsEnabled(name)
		wanted = setting.value
		if wanted == "unset":
			# no choice saved yet (e.g. first start after this update): record the current
			# state, so the next backup carries it
			setting.value = "on" if enabled else "off"
			setting.save()
			changed = True
		elif wanted == "off" and enabled:
			print("[ServiceAutostart] %s: autostart was switched back on, disabling it again" % name)
			commands.append(autostartCommand(name, False))
			commands.append("/etc/init.d/%s stop" % name)
		elif wanted == "on" and not enabled:
			print("[ServiceAutostart] %s: autostart was switched off, enabling it again" % name)
			commands.append(autostartCommand(name, True))
	if changed:
		configfile.save()
	if commands:
		console.eBatch(commands, lambda *args: None, debug=True)
