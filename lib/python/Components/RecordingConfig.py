from Components.config import ConfigSelectionNumber, ConfigYesNo, ConfigSubsection, ConfigSelection, config


def InitRecordingConfig():
	config.recording = ConfigSubsection()
	# actually this is "recordings always have priority". "Yes" does mean: don't ask. The RecordTimer will ask when value is 0.
	config.recording.asktozap = ConfigYesNo(default=True)
	config.recording.setstreamto1 = ConfigSelection(default=(), choices=[
		((), _("don't convert")),
		(("4097",), _("4097 only")),
		(("4097", "5001"), _("4097 + 5001")),
		(("4097", "5001", "5002"), _("4097 + 5001 + 5002")),
		(("4097", "5002"), _("4097 + 5002")),
		(("5001",), _("5001 only")),
		(("5001", "5002"), _("5001 + 5002")),
		(("5002",), _("5002 only"))])
	config.recording.margin_before = ConfigSelectionNumber(min=0, max=120, stepwidth=1, default=3, wraparound=True)
	config.recording.margin_after = ConfigSelectionNumber(min=0, max=120, stepwidth=1, default=5, wraparound=True)
	config.recording.split_programme_minutes = ConfigSelectionNumber(min=0, max=30, stepwidth=1, default=15, wraparound=True)
	config.recording.ascii_filenames = ConfigYesNo(default=False)
	config.recording.keep_timers = ConfigSelectionNumber(min=1, max=120, stepwidth=1, default=7, wraparound=True)
	choicelist = [(0, _("Keep logs"))] + [(i, str(i)) for i in range(1, 14)]
	config.recording.keep_finished_timer_logs = ConfigSelection(default=0, choices=choicelist)
	config.recording.filename_composition = ConfigSelection(default="standard", choices=[
		("standard", _("Date first")),
		("event", _("Event name first")),
		("short", _("Short filenames")),
		("long", _("Long filenames"))])
	config.recording.offline_decode_delay = ConfigSelectionNumber(min=1, max=10000, stepwidth=10, default=1000, wraparound=True)
	config.recording.ecm_data = ConfigSelection(choices=[("normal", _("normal")), ("descrambled+ecm", _("descramble and record ecm")), ("scrambled+ecm", _("don't descramble, record ecm"))], default="normal")
	config.recording.record_icon_match = ConfigSelection(default="Sref + stream url", choices=[("Sref only", _("Sref only")), ("Sref + stream url", _("Sref + stream url"))])
