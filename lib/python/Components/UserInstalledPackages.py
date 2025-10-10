class UserInstalledPackages:
	def __init__(self):
		self.opkg_package_list = "/var/lib/opkg/status"
		self.autopackages = ("opkg", "openvix-base", "run-postinsts")  # Auto installed packages not marked "Auto-Installed: yes" in "/var/lib/opkg/status"

	def run(self, callback):
		packages_out = []
		for package in [x for x in open(self.opkg_package_list).read().split("\n\n") if not "Auto-Installed: yes" in x]:
			lines = package.splitlines()
			p_name = None
			for line in lines:
				if line.startswith("Package: "):
					p_name = line.replace("Package: ", "").strip()
					break
			if p_name and p_name not in self.autopackages:
				packages_out.append(p_name)
		callback(packages_out)
