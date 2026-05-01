from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.config import config


class RemainingToText(Poll, Converter):
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

	TYPES = {
		"Default": (DEFAULT, None),
		"WithSeconds": (WITH_SECONDS, 1000),
		"NoSeconds": (NO_SECONDS, 60 * 1000),
		"InSeconds": (IN_SECONDS, 1000),
		"Percentage": (PERCENTAGE, 60 * 1000),
		"VFD": (VFD, None),
		"VFDWithSeconds": (VFD_WITH_SECONDS, 1000),
		"VFDNoSeconds": (VFD_NO_SECONDS, 60 * 1000),
		"VFDInSeconds": (VFD_IN_SECONDS, 1000),
		"VFDPercentage": (VFD_PERCENTAGE, 60 * 1000),
	}

	def __init__(self, type):
		Poll.__init__(self)
		Converter.__init__(self, type)
		print(f"[RemainingToText] Converter argument: '{type}'")
		if type and type not in self.TYPES:
			print(f"[RemainingToText] Error: unknown converter argument '{type}'")
		self.type, poll_interval = self.TYPES.get(type, (self.DEFAULT, None))

		# override skin setting with user setting if swap_time_display is not ("0", _("Skin Setting"))
		swap_time_display = config.usage.swap_time_display_on_vfd.value if self.type >= self.VFD else config.usage.swap_time_display_on_osd.value  # if VFD use VFD config
		if swap_time_display in ("1", "3", "5"):
			poll_interval = 60 * 1000
		elif swap_time_display in ("2", "4"):
			poll_interval = 1000

		if poll_interval:
			self.poll_interval = poll_interval
			self.poll_enabled = True

	@cached
	def getText(self):
		time = self.source.time  # from EventTime.getTime()
		if time is None:
			return ""

		duration, remaining, elapsed = time  # "remaining" and "elapsed" will be None if this is not a current event

		if self.type >= self.VFD:  # if VFD use VFD config
			elapsed_time_positive = config.usage.elapsed_time_positive_vfd.value
			swap_time_display = config.usage.swap_time_display_on_vfd.value
			swap_time_remaining = config.usage.swap_time_remaining_on_vfd.value
			default = self.VFD
			with_seconds = self.VFD_WITH_SECONDS
			no_seconds = self.VFD_NO_SECONDS
			in_seconds = self.VFD_IN_SECONDS
			percentage = self.VFD_PERCENTAGE
		else:
			elapsed_time_positive = config.usage.elapsed_time_positive_osd.value
			swap_time_display = config.usage.swap_time_display_on_osd.value
			swap_time_remaining = config.usage.swap_time_remaining_on_osd.value
			default = self.DEFAULT
			with_seconds = self.WITH_SECONDS
			no_seconds = self.NO_SECONDS
			in_seconds = self.IN_SECONDS
			percentage = self.PERCENTAGE

		l = duration  # noqa: E741 Length
		p = elapsed  # Position
		r = remaining  # Remaining

		if elapsed_time_positive:
			sign_p = "+"
			sign_r = "-"
		else:
			sign_p = "-"
			sign_r = "+"
		if swap_time_display == "1":  # Mins
			if remaining is not None:
				if swap_time_remaining == "1":  # Elapsed
					return sign_p + ngettext("%d Min", "%d Mins", (p // 60)) % (p // 60)
				elif swap_time_remaining == "2":  # Elapsed & Remaining
					return sign_p + "%d  " % (p // 60) + sign_r + ngettext("%d Min", "%d Mins", (r // 60)) % (r // 60)
				elif swap_time_remaining == "3":  # Remaining & Elapsed
					return sign_r + "%d  " % (r // 60) + sign_p + ngettext("%d Min", "%d Mins", (p // 60)) % (p // 60)
				else:
					return sign_r + ngettext("%d Min", "%d Mins", (r // 60)) % (r // 60)
			else:
				return ngettext("%d Min", "%d Mins", (l // 60)) % (l // 60)

		elif swap_time_display == "2":  # Mins Secs
			if remaining is not None:
				if swap_time_remaining == "1":  # Elapsed
					return sign_p + "%d:%02d" % (p // 60, p % 60)
				elif swap_time_remaining == "2":  # Elapsed & Remaining
					return sign_p + "%d:%02d  " % (p // 60, p % 60) + sign_r + "%d:%02d" % (r // 60, r % 60)
				elif swap_time_remaining == "3":  # Remaining & Elapsed
					return sign_r + "%d:%02d  " % (r // 60, r % 60) + sign_p + "%d:%02d" % (p // 60, p % 60)
				else:
					return sign_r + "%d:%02d" % (r // 60, r % 60)
			else:
				return "%d:%02d" % (l // 60, l % 60)
		elif swap_time_display == "3":  # Hours Mins
			if remaining is not None:
				if swap_time_remaining == "1":  # Elapsed
					return sign_p + "%d:%02d" % (p // 3600, p % 3600 // 60)
				elif swap_time_remaining == "2":  # Elapsed & Remaining
					return sign_p + "%d:%02d  " % (p // 3600, p % 3600 // 60) + sign_r + "%d:%02d" % (r // 3600, r % 3600 // 60)
				elif swap_time_remaining == "3":  # Remaining & Elapsed
					return sign_r + "%d:%02d  " % (r // 3600, r % 3600 // 60) + sign_p + "%d:%02d" % (p // 3600, p % 3600 // 60)
				else:
					return sign_r + "%d:%02d" % (r // 3600, r % 3600 // 60)
			else:
				return "%d:%02d" % (l // 3600, l % 3600 // 60)
		elif swap_time_display == "4":  # Hours Mins Secs
			if remaining is not None:
				if swap_time_remaining == "1":  # Elapsed
					return sign_p + "%d:%02d:%02d" % (p // 3600, p % 3600 // 60, p % 60)
				elif swap_time_remaining == "2":  # Elapsed & Remaining
					return sign_p + "%d:%02d:%02d  " % (p // 3600, p % 3600 // 60, p % 60) + sign_r + "%d:%02d:%02d" % (r // 3600, r % 3600 // 60, r % 60)
				elif swap_time_remaining == "3":  # Remaining & Elapsed
					return sign_r + "%d:%02d:%02d  " % (r // 3600, r % 3600 // 60, r % 60) + sign_p + "%d:%02d:%02d" % (p // 3600, p % 3600 // 60, p % 60)
				else:
					return sign_r + "%d:%02d:%02d" % (r // 3600, r % 3600 // 60, r % 60)
			else:
				return "%d:%02d:%02d" % (l // 3600, l % 3600 // 60, l % 60)
		elif swap_time_display == "5":  # Percentage
			if remaining is not None:
				try:
					if swap_time_remaining == "1":  # Elapsed
						return sign_p + "%d%%" % int((float(p) / float(l)) * 100)
					elif swap_time_remaining == "2":  # Elapsed & Remaining
						return sign_p + "%d%%  " % int((float(p) / float(l)) * 100) + sign_r + "%d%%" % int((float(r) / float(l)) * 100 + 1)
					elif swap_time_remaining == "3":  # Remaining & Elapsed
						return sign_r + "%d%%  " % int((float(r) / float(l)) * 100 + 1) + sign_p + "%d%%" % int((float(p) / float(l + 0.0)) * 100)
					else:
						return sign_r + "%d%%" % int((float(p) / float(l)) * 100)
				except:
					return ""
			else:
				return "%d:%02d:%02d" % (l // 3600, l % 3600 // 60, l % 60)
		else:  # Skin Setting
			if self.type == default:
				if remaining is not None:
					if swap_time_remaining == "1":  # Elapsed
						return sign_p + ngettext("%d Min", "%d Mins", (p // 60)) % (p // 60)
					elif swap_time_remaining == "2":  # Elapsed & Remaining
						return sign_p + "%d  " % (p // 60) + sign_r + ngettext("%d Min", "%d Mins", (r // 60)) % (r // 60)
					elif swap_time_remaining == "3":  # Remaining & Elapsed
						return sign_r + "%d  " % (r // 60) + sign_p + ngettext("%d Min", "%d Mins", (p // 60)) % (p // 60)
					else:
						return sign_r + ngettext("%d Min", "%d Mins", (r // 60)) % (r // 60)
				else:
					return ngettext("%d Min", "%d Mins", (l // 60)) % (l // 60)
			elif self.type == with_seconds:
				if remaining is not None:
					if swap_time_remaining == "1":  # Elapsed
						return sign_p + "%d:%02d:%02d" % (p // 3600, p % 3600 // 60, p % 60)
					elif swap_time_remaining == "2":  # Elapsed & Remaining
						return sign_p + "%d:%02d:%02d  " % (p // 3600, p % 3600 // 60, p % 60) + sign_r + "%d:%02d:%02d" % (r // 3600, r % 3600 // 60, r % 60)
					elif swap_time_remaining == "3":  # Remaining & Elapsed
						return sign_r + "%d:%02d:%02d  " % (r // 3600, r % 3600 // 60, r % 60) + sign_p + "%d:%02d:%02d" % (p // 3600, p % 3600 // 60, p % 60)
					else:
						return sign_r + "%d:%02d:%02d" % (r // 3600, r % 3600 // 60, r % 60)
				else:
					return "%d:%02d:%02d" % (l // 3600, l % 3600 // 60, l % 60)
			elif self.type == no_seconds:
				if remaining is not None:
					if swap_time_remaining == "1":  # Elapsed
						return sign_p + "%d:%02d" % (p // 3600, p % 3600 // 60)
					elif swap_time_remaining == "2":  # Elapsed & Remaining
						return sign_p + "%d:%02d  " % (p // 3600, p % 3600 // 60) + sign_r + "%d:%02d" % (r // 3600, r % 3600 // 60)
					elif swap_time_remaining == "3":  # Remaining & Elapsed
						return sign_r + "%d:%02d  " % (r // 3600, r % 3600 // 60) + sign_p + "%d:%02d" % (p // 3600, p % 3600 // 60)
					else:
						return sign_r + "%d:%02d" % (r // 3600, r % 3600 // 60)
				else:
					return "%d:%02d" % (l // 3600, l % 3600 // 60)
			elif self.type == in_seconds:
				if remaining is not None:
					if swap_time_remaining == "1":  # Elapsed
						return sign_p + "%d " % p
					elif swap_time_remaining == "2":  # Elapsed & Remaining
						return sign_p + "%d  " % p + sign_r + "%d " % r
					elif swap_time_remaining == "3":  # Remaining & Elapsed
						return sign_r + "%d  " % r + sign_p + "%d " % p
					else:
						return sign_r + "%d " % r
				else:
					return "%d " % l + _("Mins")
			elif self.type == percentage:
				try:
					if swap_time_remaining == "1":  # Elapsed
						return sign_p + "%d%%" % ((float(p + 0.0) // float(l + 0.0)) * 100)
					elif swap_time_remaining == "2":  # Elapsed & Remaining
						return sign_p + "%d%%  " % ((float(p + 0.0) // float(l + 0.0)) * 100) + sign_r + "%d%%" % ((float(r + 0.0) // float(l + 0.0)) * 100 + 1)
					elif swap_time_remaining == "3":  # Remaining & Elapsed
						return sign_r + "%d%%  " % ((float(r + 0.0) // float(l + 0.0)) * 100 + 1) + sign_p + "%d%%" % ((float(p + 0.0) // float(l + 0.0)) * 100)
					else:
						return sign_r + "%d%%" % ((float(p + 0.0) // float(l + 0.0)) * 100)
				except:
					return ""
			else:
				return "%d" % l

	text = property(getText)
