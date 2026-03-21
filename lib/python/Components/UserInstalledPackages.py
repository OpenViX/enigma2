import subprocess


class UserInstalledPackages:
	# Fetch a list of user install packages, not including their depends.
	# Note: this list does not include packages installed on other mount
	# points, such as  picons on /media/usb. This is deliberate. Such
	# installs survive reflashes and are picked up on software updates.

	def __init__(self):
		self.embedded_packages_file = "/usr/lib/package.lst"

	def run(self, callback=None):
		dependencies = []
		plugins_out = []
		embedded_packages = False
		status = False
		try:
			embedded_packages = set([x for line in open(self.embedded_packages_file).read().splitlines() if (x := line.split()[0].strip())])
		except Exception as e:
			print(f"[UserInstalledPackages] failed to read {self.embedded_packages_file}\n", e)
		try:
			status = subprocess.run(['opkg', 'status'], stdout=subprocess.PIPE, check=True).stdout.decode('utf-8')
		except Exception as e:
			print(f"[UserInstalledPackages] failed to read opkg status\n", e)
		if embedded_packages and status:
			packages, provides = self.parsestatus(status, embedded_packages)
			for package in packages:
				for depends in packages[package]["depends"]:
					d_package = provides.get(depends)
					if d_package and d_package in packages:
						dependencies.append(d_package)
			plugins_out = [p for p in packages if p not in dependencies]
		callback(plugins_out)

	def parsestatus(self, status, embedded_packages):
		packages = {}
		provides = {}
		for package in [x for x in status.split("\n\n") if x.split("\n")[0].replace("Package: ", "").strip() not in embedded_packages]:
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


if __name__ == "__main__":
	UserInstalledPackages().run(lambda x: print("\n".join(x)))
