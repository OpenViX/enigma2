installdir = $(pkglibdir)/python/Plugins/SystemPlugins

SUBDIRS = SoftwareManager PositionerSetup Satfinder \
	SatelliteEquipmentControl Videomode VideoTune Hotplug \
	DefaultServicesScanner DiseqcTester CommonInterfaceAssignment GBAspectRatioSwitch \
	CableScan FastScan OSDPositionSetup OSD3DSetup HdmiCEC VideoClippingSetup \
	VideoEnhancement WirelessLan NetworkWizard DeviceManager \
	SwapManager SoftcamStartup

if HAVE_OSDANIMATION
SUBDIRS += AnimationSetup
endif

install_PYTHON =	\
	__init__.py
