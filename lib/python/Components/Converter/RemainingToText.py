from Components.Converter.Converter import Converter
from Poll import Poll
from Components.Element import cached
from Components.config import config

class RemainingToText(Poll, Converter, object):
	DEFAULT = 0
	WITH_SECONDS = 1
	NO_SECONDS = 2
	IN_SECONDS = 3
	PERCENTAGE = 4
	VFD = 5
	VFD_WITH_SECONDS = 6
	VFD_NO_SECONDS = 7
	VFD_IN_SECONDS = 8
	VFD_PERCENTAGE = 9

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		if type == "WithSeconds":
			self.type = self.WITH_SECONDS
			self.poll_interval = 1000
			self.poll_enabled = True
		elif type == "NoSeconds":
			self.type = self.NO_SECONDS
			self.poll_interval = 60*1000
			self.poll_enabled = True
		elif type == "InSeconds":
			self.type = self.IN_SECONDS
			self.poll_interval = 1000
			self.poll_enabled = True
		elif type == "Percentage":
			self.type = self.PERCENTAGE
			self.poll_interval = 60*1000
			self.poll_enabled = True
		elif type == "VFD":
			self.type = self.VFD
		elif type == "VFDWithSeconds":
			self.type = self.VFD_WITH_SECONDS
			self.poll_interval = 1000
			self.poll_enabled = True
		elif type == "VFDNoSeconds":
			self.type = self.VFD_NO_SECONDS
			self.poll_interval = 60*1000
			self.poll_enabled = True
		elif type == "VFDInSeconds":
			self.type = self.VFD_IN_SECONDS
			self.poll_interval = 1000
			self.poll_enabled = True
		elif type == "VFDPercentage":
			self.type = self.VFD_PERCENTAGE
			self.poll_interval = 60*1000
			self.poll_enabled = True
		else:
			self.type = self.DEFAULT

		if config.usage.swap_time_display_on_osd.value == "1" or config.usage.swap_time_display_on_osd.value == "3" or config.usage.swap_time_display_on_osd.value == "5" or config.usage.swap_time_display_on_vfd.value == "1" or config.usage.swap_time_display_on_vfd.value == "3" or config.usage.swap_time_display_on_vfd.value == "5":
			self.poll_interval = 60*1000
			self.poll_enabled = True
		if config.usage.swap_time_display_on_osd.value == "2" or config.usage.swap_time_display_on_osd.value == "4" or config.usage.swap_time_display_on_vfd.value == "2" or config.usage.swap_time_display_on_vfd.value == "4":
			self.poll_interval = 1000
			self.poll_enabled = True

	@cached
	def getText(self):
		time = self.source.time
		if time is None:
			return ""

		duration = 0
		elapsed = 0
		remaining = 0

		if str(time[1]) != 'None':
			if self.type < 5:
				if config.usage.swap_time_remaining_on_osd.value == "0":
					(duration, remaining) = self.source.time
				elif config.usage.swap_time_remaining_on_osd.value == "1":
					(duration, elapsed) = self.source.time
				elif config.usage.swap_time_remaining_on_osd.value == "2":
					(duration, elapsed, remaining) = self.source.time
				elif config.usage.swap_time_remaining_on_osd.value == "3":
					(duration, remaining, elapsed) = self.source.time
			else:
				if config.usage.swap_time_remaining_on_vfd.value == "0":
					(duration, remaining) = self.source.time
				elif config.usage.swap_time_remaining_on_vfd.value == "1":
					(duration, elapsed) = self.source.time
				elif config.usage.swap_time_remaining_on_vfd.value == "2":
					(duration, elapsed, remaining) = self.source.time
				elif config.usage.swap_time_remaining_on_vfd.value == "3":
					(duration, remaining, elapsed) = self.source.time
		else:
			(duration, remaining) = self.source.time

		l = duration # Length
		p = elapsed # Position
		r = remaining  # Remaining

		sign_l = ""

		if self.type < 5:
			if config.usage.elapsed_time_positive_osd.value:
				sign_p = "+"
				sign_r = "-"
			else:
				sign_p = "-"
				sign_r = "+"
			if config.usage.swap_time_display_on_osd.value == "1":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_osd.value == "1": # Elapsed
						return sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
					elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
						return sign_p + "%d  " % (p/60) + sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
					elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
						return sign_r + "%d  " % (r/60) + sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
					else:
						return sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
				else:
					return ngettext("%d Min", "%d Mins", (l/60)) % (l/60)

			elif config.usage.swap_time_display_on_osd.value == "2":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
						return sign_p + "%d:%02d" % (p/60, p%60)
					elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
						return sign_p + "%d:%02d  " % (p/60, p%60) + sign_r + "%d:%02d" % (r/60, r%60)
					elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
						return sign_r + "%d:%02d  " % (r/60, r%60) + sign_p + "%d:%02d" % (p/60, p%60)
					else:
						return sign_r + "%d:%02d" % (r/60, r%60)
				else:
					return "%d:%02d" % (l/60, l%60)
			elif config.usage.swap_time_display_on_osd.value == "3":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
						return sign_p + "%d:%02d" % (p/3600, p%3600/60)
					elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
						return sign_p + "%d:%02d  " % (p/3600, p%3600/60) + sign_r + "%d:%02d" % (r/3600, r%3600/60)
					elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
						return sign_r + "%d:%02d  " % (r/3600, r%3600/60) + sign_p + "%d:%02d" % (p/3600, p%3600/60)
					else:
						return sign_r + "%d:%02d" % (r/3600, r%3600/60)
				else:
					return sign_l + "%d:%02d" % (l/3600, l%3600/60)
			elif config.usage.swap_time_display_on_osd.value == "4":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
						return sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
					elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
						return sign_p + "%d:%02d:%02d  " % (p/3600, p%3600/60, p%60) + sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
					elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
						return sign_r + "%d:%02d:%02d  " % (r/3600, r%3600/60, r%60) + sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
					else:
						return sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
				else:
					return sign_l + "%d:%02d:%02d" % (l/3600, l%3600/60, l%60)
			elif config.usage.swap_time_display_on_osd.value == "5":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
						try:
							return sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
						try:
							return sign_p + "%d%%  " % ((float(p + 0.0) / float(l + 0.0)) * 100) + sign_r + "%d%%" % ((float(r + 0.0) / float(l + 0.0)) * 100 + 1)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
						try:
							return sign_r + "%d%%  " % ((float(r + 0.0) / float(l + 0.0)) * 100 +1 ) + sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					else:
						try:
							return sign_r + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
				else:
					return sign_l + "%d:%02d:%02d" % (l/3600, l%3600/60, l%60)
			else:
				if self.type == self.DEFAULT:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_osd.value == "1": # Elapsed
							return sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
						elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
							return sign_p + "%d  " % (p/60) + sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
						elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
							return sign_r + "%d  " % (r/60) + sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
						else:
							return sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
					else:
						return ngettext("%d Min", "%d Mins", (l/60)) % (l/60)
				elif self.type == self.WITH_SECONDS:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
							return sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
						elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
							return sign_p + "%d:%02d:%02d  " % (p/3600, p%3600/60, p%60) + sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
						elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
							return sign_r + "%d:%02d:%02d  " % (r/3600, r%3600/60, r%60) + sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
						else:
							return sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
					else:
						return sign_l + "%d:%02d:%02d" % (l/3600, l%3600/60, l%60)
				elif self.type == self.NO_SECONDS:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
							return sign_p + "%d:%02d" % (p/3600, p%3600/60)
						elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
							return sign_p + "%d:%02d  " % (p/3600, p%3600/60) + sign_r + "%d:%02d" % (r/3600, r%3600/60)
						elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
							return sign_r + "%d:%02d  " % (r/3600, r%3600/60) + sign_p + "%d:%02d" % (p/3600, p%3600/60)
						else:
							return sign_r + "%d:%02d" % (r/3600, r%3600/60)
					else:
						return sign_l + "%d:%02d" % (l/3600, l%3600/60)
				elif self.type == self.IN_SECONDS:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_osd.value == "1": # Elapsed
							return sign_p + "%d " % p
						elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
							return sign_p + "%d  " % p + sign_r + "%d " % r
						elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
							return sign_r + "%d  " % r + sign_p + "%d " % p
						else:
							return sign_r + "%d " % r
					else:
						return "%d " % l + _("Mins")
				elif self.type == self.PERCENTAGE:
					if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
						try:
							return sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
						try:
							return sign_p + "%d%%  " % ((float(p + 0.0) / float(l + 0.0)) * 100) + sign_r + "%d%%" % ((float(r + 0.0) / float(l + 0.0)) * 100 + 1)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
						try:
							return sign_r + "%d%%  " % ((float(r + 0.0) / float(l + 0.0)) * 100 +1 ) + sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					else:
						try:
							return sign_r + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
				else:
					return sign_l + "%d" % l

		else:
			if config.usage.elapsed_time_positive_vfd.value:
				sign_p = "+"
				sign_r = "-"
			else:
				sign_p = "-"
				sign_r = "+"
			if config.usage.swap_time_display_on_vfd.value == "1":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_vfd.value == "1": # Elapsed
						return sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
					elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
						return sign_p + "%d  " % (p/60) + sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
					elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
						return sign_r + "%d  " % (r/60) + sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
					else:
						return sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
				else:
					return ngettext("%d Min", "%d Mins", (l/60)) % (l/60)

			elif config.usage.swap_time_display_on_vfd.value == "2":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_vfd.value == "1":  # Elapsed
						return sign_p + "%d:%02d" % (p/60, p%60)
					elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
						return sign_p + "%d:%02d  " % (p/60, p%60) + sign_r + "%d:%02d" % (r/60, r%60)
					elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
						return sign_r + "%d:%02d  " % (r/60, r%60) + sign_p + "%d:%02d" % (p/60, p%60)
					else:
						return sign_r + "%d:%02d" % (r/60, r%60)
				else:
					return "%d:%02d" % (l/60, l%60)
			elif config.usage.swap_time_display_on_vfd.value == "3":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_vfd.value == "1":  # Elapsed
						return sign_p + "%d:%02d" % (p/3600, p%3600/60)
					elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
						return sign_p + "%d:%02d  " % (p/3600, p%3600/60) + sign_r + "%d:%02d" % (r/3600, r%3600/60)
					elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
						return sign_r + "%d:%02d  " % (r/3600, r%3600/60) + sign_p + "%d:%02d" % (p/3600, p%3600/60)
					else:
						return sign_r + "%d:%02d" % (r/3600, r%3600/60)
				else:
					return sign_l + "%d:%02d" % (l/3600, l%3600/60)
			elif config.usage.swap_time_display_on_vfd.value == "4":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_vfd.value == "1":  # Elapsed
						return sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
					elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
						return sign_p + "%d:%02d:%02d  " % (p/3600, p%3600/60, p%60) + sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
					elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
						return sign_r + "%d:%02d:%02d  " % (r/3600, r%3600/60, r%60) + sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
					else:
						return sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
				else:
					return sign_l + "%d:%02d:%02d" % (l/3600, l%3600/60, l%60)
			elif config.usage.swap_time_display_on_vfd.value == "5":
				if remaining is not None:
					if config.usage.swap_time_remaining_on_vfd.value == "1":  # Elapsed
						try:
							return sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
						try:
							return sign_p + "%d%%  " % ((float(p + 0.0) / float(l + 0.0)) * 100) + sign_r + "%d%%" % ((float(r + 0.0) / float(l + 0.0)) * 100 + 1)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
						try:
							return sign_r + "%d%%  " % ((float(r + 0.0) / float(l + 0.0)) * 100 +1 ) + sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					else:
						try:
							return sign_r + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
				else:
					return sign_l + "%d:%02d:%02d" % (l/3600, l%3600/60, l%60)
			else:
				if self.type == self.VFD:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_vfd.value == "1": # Elapsed
							return sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
						elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
							return sign_p + "%d  " % (p/60) + sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
						elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
							return sign_r + "%d  " % (r/60) + sign_p + ngettext("%d Min", "%d Mins", (p/60)) % (p/60)
						else:
							return sign_r + ngettext("%d Min", "%d Mins", (r/60)) % (r/60)
					else:
						return ngettext("%d Min", "%d Mins", (l/60)) % (l/60)
				elif self.type == self.VFD_WITH_SECONDS:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_osd.value == "1":  # Elapsed
							return sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
						elif config.usage.swap_time_remaining_on_osd.value == "2": # Elapsed & Remaining
							return sign_p + "%d:%02d:%02d  " % (p/3600, p%3600/60, p%60) + sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
						elif config.usage.swap_time_remaining_on_osd.value == "3": # Remaining & Elapsed
							return sign_r + "%d:%02d:%02d  " % (r/3600, r%3600/60, r%60) + sign_p + "%d:%02d:%02d" % (p/3600, p%3600/60, p%60)
						else:
							return sign_r + "%d:%02d:%02d" % (r/3600, r%3600/60, r%60)
					else:
						return sign_l + "%d:%02d:%02d" % (l/3600, l%3600/60, l%60)
				elif self.type == self.VFD_NO_SECONDS:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_vfd.value == "1":  # Elapsed
							return sign_p + "%d:%02d" % (p/3600, p%3600/60)
						elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
							return sign_p + "%d:%02d  " % (p/3600, p%3600/60) + sign_r + "%d:%02d" % (r/3600, r%3600/60)
						elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
							return sign_r + "%d:%02d  " % (r/3600, r%3600/60) + sign_p + "%d:%02d" % (p/3600, p%3600/60)
						else:
							return sign_r + "%d:%02d" % (r/3600, r%3600/60)
					else:
						return sign_l + "%d:%02d" % (l/3600, l%3600/60)
				elif self.type == self.VFD_IN_SECONDS:
					if remaining is not None:
						if config.usage.swap_time_remaining_on_vfd.value == "1": # Elapsed
							return sign_p + "%d " % p
						elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
							return sign_p + "%d  " % p + sign_r + "%d " % r
						elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
							return sign_r + "%d  " % r + sign_p + "%d " % p
						else:
							return sign_r + "%d " % r
					else:
						return "%d " % l + _("Mins")
				elif self.type == self.VFD_PERCENTAGE:
					if config.usage.swap_time_remaining_on_vfd.value == "1":  # Elapsed
						try:
							return sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_vfd.value == "2": # Elapsed & Remaining
						try:
							return sign_p + "%d%%  " % ((float(p + 0.0) / float(l + 0.0)) * 100) + sign_r + "%d%%" % ((float(r + 0.0) / float(l + 0.0)) * 100 + 1)
						except:
							return ""
					elif config.usage.swap_time_remaining_on_vfd.value == "3": # Remaining & Elapsed
						try:
							return sign_r + "%d%%  " % ((float(r + 0.0) / float(l + 0.0)) * 100 +1 ) + sign_p + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
					else:
						try:
							return sign_r + "%d%%" % ((float(p + 0.0) / float(l + 0.0)) * 100)
						except:
							return ""
				else:
					return sign_l + "%d" % l


	text = property(getText)
