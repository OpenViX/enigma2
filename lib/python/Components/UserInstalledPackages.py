import subprocess


class UserInstalledPackages:
	# Fetch a list of user install packages, not including their depends.
	# Note: this list does not include packages installed on other mount
	# points, such as  picons on /media/usb. This is deliberate. Such
	# installs survive reflashes and are picked up on software updates.

	def __init__(self):
		self.embedded_packages_file = "/usr/lib/package.lst"

	def run(self, callback=None):
		dependencies = set()
		plugins_out = []
		embedded_packages = False
		status = False
		try:
			embedded_packages = set([x for line in open(self.embedded_packages_file).read().splitlines() if (x := line.split()[0].strip())])
		except Exception as e:
			print(f"[UserInstalledPackages] failed to read {self.embedded_packages_file}\n", e)
			embedded_packages = self.getEmbeddedPackagesOldMethod()  # retain this until the end of core 5.6, will only be used if /usr/lib/package.lst is missing
		try:
			status = subprocess.run(['opkg', 'status'], stdout=subprocess.PIPE, check=True).stdout.decode('utf-8')
		except Exception as e:
			print("[UserInstalledPackages] failed to read opkg status\n", e)
		if embedded_packages and status:
			packages, provides = self.parsestatus(status)
			for package in packages:
				for depends in packages[package]["depends"]:
					d_package = provides.get(depends)
					if d_package and d_package in packages:
						dependencies.add(d_package)
			plugins_out = [p for p in packages if p not in dependencies and p not in embedded_packages]
		callback(plugins_out)

	def parsestatus(self, status):
		packages = {}
		provides = {}
		for package in [x for x in status.split("\n\n")]:
			lines = package.splitlines()
			p_name = None
			p_depends = []
			p_provides = []
			for line in lines:
				if line.startswith("Package: "):
					p_name = line.replace("Package: ", "").strip()
				elif line.startswith("Provides: ") and (tmp_prov := line.replace("Provides: ", "").strip()):
					p_provides += [x.strip().split(" ", 1)[0] for x in tmp_prov.split(",")]
				elif line.startswith("Depends: ") and (tmp_dep := line.replace("Depends: ", "").strip()):
					p_depends += [x.strip().split(" ", 1)[0] for x in tmp_dep.split(",")]
				elif line.startswith("Recommends: ") and (tmp_dep := line.replace("Recommends: ", "").strip()):
					p_depends += [x.strip().split(" ", 1)[0] for x in tmp_dep.split(",")]
			if p_name:
				packages[p_name] = {"depends": p_depends}
				for x in p_provides:
					provides[x] = p_name
				provides[p_name] = p_name
		return packages, provides

	def getEmbeddedPackagesOldMethod(self):
		# retain this until the end of core 5.6, will only be used if /usr/lib/package.lst is missing
		embedded = []
		try:
			result = open("/var/lib/opkg/status").read()
		except Exception as e:
			print("[UserInstalledPackages] failed to read /var/lib/opkg/status\n", e)
			result = ""
		if result:
			min_installed_time = min([int(parts[1]) for line in result.split("\n") if line.startswith("Installed-Time") and len(parts := line.strip().split()) > 1 and parts[1].isnumeric()])
			embedded += [z for x in result.split("\n\n") if ("Installed-Time: " in x and "Installed-Time: " + str(min_installed_time) in x or "Auto-Installed: yes" in x) and (y := x.split("\n")[0]).startswith("Package: ") and (z := y.replace("Package: ", "").strip())]
		return embedded


if __name__ == "__main__":
	UserInstalledPackages().run(lambda x: print("\n".join(x)))
