from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Components.SystemInfo import SystemInfo
from Screens.Screen import Screen

from enigma import eTimer
from sys import modules
from datetime import datetime
from json import loads
# required methods: Request, urlopen, HTTPError, URLError
from urllib.request import urlopen, Request  # raises ImportError in Python 2
from urllib.error import HTTPError, URLError  # raises ImportError in Python 2

if SystemInfo["imagetype"] == 'release':
	ImageVer = "%03d" % int(SystemInfo["imagebuild"])
else:
	ImageVer = "%s.%s" % (SystemInfo["imagebuild"], SystemInfo["imagedevbuild"])
	ImageVer = float(ImageVer)

E2Branches = {
	'developer': 'Developer',
	'release': 'Release'
}

project = 0
projects = [
	("https://api.github.com/repos/oe-alliance/oe-alliance-core/commits?sha=5.3", "OE-A Core"),
	("https://api.github.com/repos/OpenViX/enigma2/commits?sha=%s" % getattr(E2Branches, SystemInfo["imagetype"], "Release"), "Enigma2"),
	("https://api.github.com/repos/OpenViX/skins/commits", "ViX Skins"),
	("https://api.github.com/repos/oe-alliance/oe-alliance-plugins/commits", "OE-A Plugins"),
	("https://api.github.com/repos/oe-alliance/AutoBouquetsMaker/commits", "AutoBouquetsMaker"),
	("https://api.github.com/repos/oe-alliance/branding-module/commits", "Branding Module"),
]
cachedProjects = {}


def readGithubCommitLogsSoftwareUpdate():
	global ImageVer
	gitstart = True
	url = projects[project][0]
	commitlog = ""
	try:
		try:
			from ssl import _create_unverified_context
			req = Request(url)
			log = loads(urlopen(req, timeout=5, context=_create_unverified_context()).read())
		except:
			log = loads(urlopen(req, timeout=5).read())
		for c in log:
			if c['commit']['message'].startswith('openbh:') or (gitstart and not c['commit']['message'].startswith('openvix:') and getScreenTitle() in ("OE-A Core", "Enigma2", "ViX Core", "ViX Skins")):
				continue
			if c['commit']['message'].startswith('openvix:'):
				gitstart = False
				if SystemInfo["imagetype"] == 'release' and c['commit']['message'].startswith('openvix: developer'):
					print('[GitCommitLog] Skipping developer line')
					continue
				elif SystemInfo["imagetype"] != 'release' and c['commit']['message'].startswith('openvix: release'):
					print('[GitCommitLog] Skipping release line')
					continue
				tmp = c['commit']['message'].split(' ')[2].split('.')
				if len(tmp) > 2:
					if SystemInfo["imagetype"] == 'release':
						releasever = tmp[2]
						releasever = "%03d" % int(releasever)
					else:
						releasever = '%s.%s' % (tmp[2], tmp[3])
						releasever = float(releasever)
				if ImageVer >= releasever:
					break

			creator = c['commit']['author']['name']
			title = c['commit']['message']
			date = datetime.strptime(c['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%x %X')
			commitlog += date + ' ' + creator + '\n' + title + 2 * '\n'
		cachedProjects[getScreenTitle()] = commitlog
	except HTTPError as err:
		if err.code == 403:
			print('[GitCommitLog] It seems you have hit your API limit - please try again later.', err)
			commitlog += _("It seems you have hit your API limit - please try again later.")
		else:
			print('[GitCommitLog] The commit log cannot be retrieved at the moment - please try again later.', err)
			commitlog += _("The commit log cannot be retrieved at the moment - please try again later.")
	except URLError as err:
		print('[GitCommitLog] The commit log cannot be retrieved at the moment - please try again later.', err)
		commitlog += _("The commit log cannot be retrieved at the moment - please try again later.\n")
	except Exception as err:
		print('[GitCommitLog] The commit log cannot be retrieved at the moment - please try again later.', err)
		commitlog += _("The commit log cannot be retrieved at the moment - please try again later.")
	return commitlog


def readGithubCommitLogs():
	global ImageVer
	global cachedProjects
	cachedProjects = {}
	blockstart = False
	gitstart = True
	url = projects[project][0]
	commitlog = ""
	try:
		try:
			from ssl import _create_unverified_context
			req = Request(url)
			log = loads(urlopen(req, timeout=5, context=_create_unverified_context()).read())
		except:
			log = loads(urlopen(req, timeout=5).read())
		for c in log:
			if c['commit']['message'].startswith('openbh:') or (gitstart and not c['commit']['message'].startswith('openvix:') and getScreenTitle() in ("OE-A Core", "Enigma2", "ViX Core", "ViX Skins")):
				continue
			if c['commit']['message'].startswith('openvix:'):
				blockstart = False
				gitstart = False
				if SystemInfo["imagetype"] == 'release' and c['commit']['message'].startswith('openvix: developer'):
					print('[GitCommitLog] Skipping developer line')
					continue
				elif SystemInfo["imagetype"] == 'developer' and c['commit']['message'].startswith('openvix: release'):
					print('[GitCommitLog] Skipping release line')
					continue
				tmp = c['commit']['message'].split(' ')[2].split('.')
				if len(tmp) > 2:
					if SystemInfo["imagetype"] == 'release':
						releasever = tmp[2]
						releasever = "%03d" % int(releasever)
					else:
						releasever = '%s.%s' % (tmp[2], tmp[3])
						releasever = float(releasever)
				if releasever > ImageVer:
					blockstart = True
					continue
			elif blockstart and getScreenTitle() in ("OE-A Core", "Enigma2", "ViX Core", "ViX Skins"):
				blockstart = True
				continue

			creator = c['commit']['author']['name']
			title = c['commit']['message']
			date = datetime.strptime(c['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%x %X')
			commitlog += date + ' ' + creator + '\n' + title + 2 * '\n'
		cachedProjects[getScreenTitle()] = commitlog
	except HTTPError as err:
		if err.code == 403:
			print('[GitCommitLog] It seems you have hit your API limit - please try again later.', err)
			commitlog += _("It seems you have hit your API limit - please try again later.")
		else:
			print('[GitCommitLog] The commit log cannot be retrieved at the moment - please try again later.', err)
			commitlog += _("The commit log cannot be retrieved at the moment - please try again later.")
	except URLError as err:
		print('[GitCommitLog] The commit log cannot be retrieved at the moment - please try again later.', err)
		commitlog += _("The commit log cannot be retrieved at the moment - please try again later.\n")
	except Exception as err:
		print('[GitCommitLog] The commit log cannot be retrieved at the moment - please try again later.', err)
		commitlog += _("The commit log cannot be retrieved at the moment - please try again later.")
	return commitlog


def getScreenTitle():
	return projects[project][1]


def left():
	global project
	project = project == 0 and len(projects) - 1 or project - 1


def right():
	global project
	project = project != len(projects) - 1 and project + 1 or 0


gitcommitinfo = modules[__name__]


class CommitInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = ["CommitInfo", "AboutOE"]
		self["AboutScrollLabel"] = ScrollLabel(_("Please wait"))
		self["HintText"] = Label(_("Press up/down to scroll through the selected log\n\nPress left/right to see different log types"))

		self["actions"] = ActionMap(["SetupActions", "DirectionActions"],
			{
				"cancel": self.close,
				"ok": self.close,
				"up": self["AboutScrollLabel"].pageUp,
				"down": self["AboutScrollLabel"].pageDown,
				"left": self.left,
				"right": self.right
			}  # noqa: E123
		)

		self["key_red"] = Button(_("Cancel"))

		self.Timer = eTimer()
		self.Timer.callback.append(self.readGithubCommitLogs)
		self.Timer.start(50, True)

	def readGithubCommitLogs(self):
		self.setTitle(gitcommitinfo.getScreenTitle())
		self["AboutScrollLabel"].setText(gitcommitinfo.readGithubCommitLogs())

	def updateCommitLogs(self):
		if gitcommitinfo.getScreenTitle() in gitcommitinfo.cachedProjects:
			self.setTitle(gitcommitinfo.getScreenTitle())
			self["AboutScrollLabel"].setText(gitcommitinfo.cachedProjects[gitcommitinfo.getScreenTitle()])
		else:
			self["AboutScrollLabel"].setText(_("Please wait"))
			self.Timer.start(50, True)

	def left(self):
		gitcommitinfo.left()
		self.updateCommitLogs()

	def right(self):
		gitcommitinfo.right()
		self.updateCommitLogs()

	def closeRecursive(self):
		self.close(("menu", "menu"))
