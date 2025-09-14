from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Harddisk import harddiskmanager, StorageDevice
from Components.MenuList import MenuList
from Components.Label import Label
from Components.SystemInfo import SystemInfo
from Components.Task import job_manager
from Screens.MessageBox import MessageBox
import Screens.InfoBar


class HarddiskSetup(Screen):
	def __init__(self, session, hdd, action, text, question):
		Screen.__init__(self, session)
		self.setTitle(text)
		self.text = text
		self.action = action
		self.question = question
		self.curentservice = None
		self["model"] = Label(_("Model: ") + hdd.model())
		self["capacity"] = Label(_("Capacity: ") + hdd.capacity())
		self["bus"] = Label(_("Bus: ") + hdd.bus())
		self["key_red"] = Label(_("Cancel"))
		self["key_green"] = Label(text)  # text can be either "Initialize" or "Check"
		self["actions"] = ActionMap(["OkCancelActions"],
		{
			"ok": self.hddQuestion,
			"cancel": self.close
		})
		self["shortcuts"] = ActionMap(["ShortcutActions"],
		{
			"red": self.close,
			"green": self.hddQuestion
		})

	def hddQuestion(self, answer=False):
		if Screens.InfoBar.InfoBar.instance.timeshiftEnabled():
			message = self.question + "\n\n" + _("You seem to be in timeshft, the service will briefly stop as timeshift stops.")
			message += '\n' + _("Do you want to continue?")
			self.session.openWithCallback(self.stopTimeshift, MessageBox, message)
		else:
			message = self.question + "\n" + _("You can continue watching TV while this is running.")
			self.session.openWithCallback(self.hddConfirmed, MessageBox, message)

	def stopTimeshift(self, confirmed):
		if confirmed:
			self.currentservice = self.session.nav.getCurrentlyPlayingServiceReference()
			self.session.nav.stopService()
			Screens.InfoBar.InfoBar.instance.stopTimeshiftcheckTimeshiftRunningCallback(True)
			self.hddConfirmed(True)

	def hddConfirmed(self, confirmed):
		if not confirmed:
			return
		try:
			job_manager.AddJob(self.action())
			for job in job_manager.getPendingJobs():
				if job.name in (_("Initializing storage device as ext4..."), _("Checking filesystem...")):
					self.showJobView(job)
					break
		except Exception as ex:
			self.session.open(MessageBox, str(ex), type=MessageBox.TYPE_ERROR, timeout=10)

		if self.curentservice:
			self.session.nav.playService(self.curentservice)
		self.close()

	def showJobView(self, job):
		from Screens.TaskView import JobView
		job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job, cancelable=False, afterEventChangeable=False, afterEvent="close")

	def JobViewCB(self, in_background):
		job_manager.in_background = in_background


class HarddiskSelection(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Initialize Devices"))

		self.skinName = "HarddiskSelection"  # For derived classes
		bootDevice = None if not SystemInfo["BootDevice"] else SystemInfo["BootDevice"][0:3]
		if harddiskmanager.HDDCount() == 0:
			tlist = [(_("no storage devices found"), 0)]
			self["hddlist"] = MenuList(tlist)
		else:
			self["hddlist"] = MenuList(harddiskmanager.HDDList(device=bootDevice))

		self["actions"] = ActionMap(["OkCancelActions"],
		{
			"ok": self.okbuttonClick,
			"cancel": self.close
		})

	def doIt(self, selection):
		selection = self["hddlist"].getCurrent()[1]
		disk = selection.device
		storageDevice = {
			"devicePoint": f"/dev/{disk}",
			"disk": disk,
			"device": disk,
			"size": 0
		}
		self.storageDevice = StorageDevice(storageDevice)
		self.session.openWithCallback(self.close, HarddiskSetup, selection,
			action=self.storageDevice.createInitializeJob,
			text=_("Initialize"),
			question=_("Do you really want to initialize this device?\nAll the data on the device will be lost!"))

	def okbuttonClick(self):
		selection = self["hddlist"].getCurrent()
		if selection[1] != 0:
			self.doIt(selection[1])
			self.close(True)


class HarddiskFsckSelection(HarddiskSelection):
	def __init__(self, session):
		HarddiskSelection.__init__(self, session)
		self.setTitle(_("Filesystem Check"))
		self.skinName = "HarddiskSelection"

	def doIt(self, selection):
		options = {"partitionType": "gpt", "partitions": [{"fsType": "ext4"}], "mountDevice": True}
		selection = self["hddlist"].getCurrent()[1]
		disk = selection.device
		fsType = options.get("fsType")
		storageDevice = {
			"devicePoint": f"/dev/{disk}",
			"disk": disk,
			"device": disk,
			"fsType": fsType,
			"size": 0
		}
		self.storageDevice = StorageDevice(storageDevice)
		self.session.openWithCallback(self.close, HarddiskSetup, selection,
			action=selection.createCheckJob,
			text=_("Check"),
			question=_("Do you really want to check the filesystem?\nThis could take a long time!"))
