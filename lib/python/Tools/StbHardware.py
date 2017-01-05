from fcntl import ioctl
from struct import pack, unpack
from boxbranding import getBrandOEM
from Components.config import config

def getFPVersion():
	ret = None
	try:
		ret = long(open("/proc/stb/fp/version", "r").read())
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ret = ioctl(fp.fileno(),0)
			fp.close()
		except IOError:
			print "getFPVersion failed!"
	return ret

def setFPWakeuptime(wutime):
	try:
		f = open("/proc/stb/fp/wakeup_time", "w")
		f.write(str(wutime))
		f.close()
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ioctl(fp.fileno(), 6, pack('L', wutime)) # set wake up
			fp.close()
		except IOError:
			print "setFPWakeupTime failed!"

def setRTCoffset():
	import time
	if time.localtime().tm_isdst == 0:
		forsleep = 7200+time.timezone
	else:
		forsleep = 3600-time.timezone

	t_local = time.localtime(int(time.time()))

	print "set RTC to %s (rtc_offset = %s sec.)" % (time.strftime(config.usage.date.daylong.value + "  " + config.usage.time.short.value, t_local), forsleep)

	# Set RTC OFFSET (diff. between UTC and Local Time)
	try:
		open("/proc/stb/fp/rtc_offset", "w").write(str(forsleep))
	except IOError:
		print "set RTC Offset failed!"

def setRTCtime(wutime):
	if getBrandOEM() == 'ini':
		setRTCoffset()
	try:
		f = open("/proc/stb/fp/rtc", "w")
		f.write(str(wutime))
		f.close()
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ioctl(fp.fileno(), 0x101, pack('L', wutime)) # set wake up
			fp.close()
		except IOError:
			print "setRTCtime failed!"

def getFPWakeuptime():
	ret = 0
	try:
		f = long(open("/proc/stb/fp/wakeup_time", "r"))
		ret = f.read()
		f.close()
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ret = unpack('L', ioctl(fp.fileno(), 5, '    '))[0] # get wakeuptime
			fp.close()
		except IOError:
			print "getFPWakeupTime failed!"
	return ret

wasTimerWakeup = None

def getFPWasTimerWakeup():
	global wasTimerWakeup
	if wasTimerWakeup is not None:
		return wasTimerWakeup
	wasTimerWakeup = False
	try:
		f = open("/proc/stb/fp/was_timer_wakeup", "r")
		file = f.read()
		f.close()
		wasTimerWakeup = int(file) and True or False
	except:
		try:
			fp = open("/dev/dbox/fp0")
			wasTimerWakeup = unpack('B', ioctl(fp.fileno(), 9, ' '))[0] and True or False
			fp.close()
		except IOError:
			print "wasTimerWakeup failed!"
	if wasTimerWakeup:
		# clear hardware status
		clearFPWasTimerWakeup()
	return wasTimerWakeup

def clearFPWasTimerWakeup():
	try:
		f = open("/proc/stb/fp/was_timer_wakeup", "w")
		f.write('0')
		f.close()
	except:
		try:
			fp = open("/dev/dbox/fp0")
			ioctl(fp.fileno(), 10)
			fp.close()
		except IOError:
			print "clearFPWasTimerWakeup failed!"
