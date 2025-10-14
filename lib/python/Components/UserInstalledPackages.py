class UserInstalledPackages:
	# fetch a list of user install packages, not including their depends

	def __init__(self):
		self.opkg_package_list = "/var/lib/opkg/status"
		self.autopackages = ("opkg", "openvix-base", "run-postinsts")  # Auto installed packages not marked "Auto-Installed: yes" in "/var/lib/opkg/status"

	def run(self, callback=None):
		dependencies = []
		if result := open(self.opkg_package_list).read():
			packages, provides = self.parseResult(result)
			for package in packages:
				for depends in packages[package]["depends"]:
					d_package = provides.get(depends)
					if d_package and d_package in packages and abs(packages[package]["installed"] - packages[d_package]["installed"]) < 300:  # less than 5 minutes between installing the package and a dependency (accounting for really slow connections)
						dependencies.append(d_package)
			plugins_out = [p for p in packages if p not in self.autopackages and p not in dependencies and not packages[p]["auto-installed"]]
		callback(plugins_out)

	def parseResult(self, result):
		packages = {}
		provides = {}
		min_installed_time = min([int(parts[1]) for line in result.split("\n") if line.startswith("Installed-Time") and len(parts := line.strip().split()) > 1 and parts[1].isnumeric()])
		for package in [x for x in result.split("\n\n") if "Installed-Time: " in x and "Installed-Time: " + str(min_installed_time) not in x]:  # only packages that don't have the "base" date
			lines = package.splitlines()
			p_name = None
			p_depends = []
			p_provides = []
			p_installed = 0
			p_auto_installed = False
			for line in lines:
				if line.startswith("Package: "):
					p_name = line.replace("Package: ", "").strip()
				elif line.startswith("Provides: ") and (tmp_prov := line.replace("Provides: ", "").strip()):
					p_provides += [x.strip().split(" ", 1)[0] for x in tmp_prov.split(",")]
				elif line.startswith("Depends: ") and (tmp_dep := line.replace("Depends: ", "").strip()):
					p_depends += [x.strip().split(" ", 1)[0] for x in tmp_dep.split(",")]
				elif line.startswith("Recommends: ") and (tmp_dep := line.replace("Recommends: ", "").strip()):
					p_depends += [x.strip().split(" ", 1)[0] for x in tmp_dep.split(",")]
				elif line.startswith("Installed-Time: ") and (tmp_it := line.replace("Installed-Time: ", "").strip()).isnumeric():
					p_installed = int(tmp_it)
				elif "Auto-Installed: yes" in line.strip():
					p_auto_installed = True
			if p_name:
				packages[p_name] = {"depends": p_depends, "installed": p_installed, "auto-installed": p_auto_installed}
				for x in p_provides:
					provides[x] = p_name
				provides[p_name] = p_name
		return packages, provides


if __name__ == "__main__":
	UserInstalledPackages().run(lambda x: print("\n".join(x)))
