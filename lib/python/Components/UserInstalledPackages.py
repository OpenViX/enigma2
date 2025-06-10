from Components.Console import Console


class UserInstalledPackages:
	# fetch a list of user install packages, not including their depends

	def __init__(self):
		self.callback = None
		self.Console = Console()

	def run(self, callback=None):
		self.callback = callback
		self.Console.ePopen("opkg status", self.readOPKG)

	def readOPKG(self, result, retval, extra_args):
		plugins_out = []
		dependencies = []
		if result:
			packages, provides = self.parseResult(result)
			for package in packages:
				for depends in packages[package]["depends"]:
					d_package = provides.get(depends)
					if d_package and d_package in packages and abs(packages[package]["installed"] - packages[d_package]["installed"]) < 300:  # less than 5 minutes between installing the package and a dependency (accounting for really slow connections)
						dependencies.append(d_package)
			plugins_out = [p for p in packages if p not in dependencies]
		if callable(self.callback):
			self.callback(plugins_out)

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
			if p_name:
				packages[p_name] = {"depends": p_depends, "installed": p_installed}
				for x in p_provides:
					provides[x] = p_name
				provides[p_name] = p_name
		return packages, provides
