import time
from Tools.Directories import resolveFilename, SCOPE_CONFIG  # , fileExists, SCOPE_LIBDIR

PERCENTAGE_START = 0
PERCENTAGE_END = 100

profile_start = time.time()

profile_data = {}
total_time = 1
profile_file = None


# def getModel():  # Here because we can't call SystemInfo this early in the boot process
# 	if fileExists(f := pathjoin(resolveFilename(SCOPE_LIBDIR), "enigma.info")):
# 		return (m := [x.split("=")[1].strip() for x in open(f).readlines() if x.startswith("machinebuild=")]) and m[0] or None


# MODEL = getModel()


try:
	f = open(resolveFilename(SCOPE_CONFIG, "profile"), "r")
	profile_old = f.readlines()
	f.close()

	t = None
	for line in profile_old:
		(t, id) = line[:-1].split('\t')
		t = float(t)
		total_time = t
		profile_data[id] = t
except:
	print("[Profile] no profile data available")

try:
	profile_file = open(resolveFilename(SCOPE_CONFIG, "profile"), "w")
except IOError:
	print("[Profile] WARNING: couldn't open profile file!")


def profile(id):
	now = time.time() - profile_start

	# GML: Set the device and format here...probably more could be added?
	#
	# if MODEL in ("odinm7", "odinm6", "xp1000s"):
	# 	dev_fmt = ("/dev/dbox/oled0", "%d")
	# elif MODEL in ("gb800se", "gb800solo"):
	# 	dev_fmt = ("/dev/dbox/oled0", "%d  \n")
	# elif MODEL == "mbtwin":
	# 	dev_fmt = ("/dev/dbox/oled0", "%d%%")
	# elif MODEL == "gb800seplus":
	# 	dev_fmt = ("/dev/mcu", "%d  \n")
	# elif MODEL == "ebox5000":
	# 	dev_fmt = ("/proc/progress", "%d"),
	# else:
	# 	dev_fmt = ("/proc/progress", "%d \n")

	dev_fmt = ("/proc/progress", "%d \n")
	(dev, fmt) = dev_fmt

	if profile_file:
		profile_file.write("%7.3f\t%s\n" % (now, id))

		if id in profile_data:
			t = profile_data[id]
			if total_time:
				perc = t * (PERCENTAGE_END - PERCENTAGE_START) // total_time + PERCENTAGE_START
			else:
				perc = PERCENTAGE_START
			try:
				f = open(dev, "w")
				f.write(fmt % perc)
				f.close()
			except IOError:
				pass


def profile_final():
	global profile_file
	if profile_file is not None:
		profile_file.close()
		profile_file = None
