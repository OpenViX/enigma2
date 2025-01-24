/*
Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License

Copyright (c) 2023-2025 OpenATV, jbleyel

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
1. Non-Commercial Use: You may not use the Software or any derivative works
   for commercial purposes without obtaining explicit permission from the
   copyright holder.
2. Share Alike: If you distribute or publicly perform the Software or any
   derivative works, you must do so under the same license terms, and you
   must make the source code of any derivative works available to the
   public.
3. Attribution: You must give appropriate credit to the original author(s)
   of the Software by including a prominent notice in your derivative works.
THE SOFTWARE IS PROVIDED "AS IS," WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE,
ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more details about the CC BY-NC-SA 4.0 License, please visit:
https://creativecommons.org/licenses/by-nc-sa/4.0/
*/

#ifndef __hardwaredb_h
#define __hardwaredb_h
#include <string>
#include <unordered_map>

static std::unordered_map<std::string, std::string> HardwareDB{

#ifdef HWDM900
	{"/devices/platform/brcmstb-ahci.0/ata1/", "SATA"},
	{"/devices/rdb.4/f03e0000.sdhci/mmc_host/mmc0/", "eMMC"},
	{"/devices/rdb.4/f03e0200.sdhci/mmc_host/mmc1/", "SD"},
	{"/devices/rdb.4/f0470600.ohci_v2/usb6/6-0:1.0", "Front panel USB"},
	{"/devices/rdb.4/f0470300.ehci_v2/usb3/3-0:1.0", "Front panel USB"},
	{"/devices/rdb.4/f0471000.xhci_v2/usb2/2-0:1.0", "Front panel USB"},
	{"/devices/rdb.4/f0470300.ehci_v2/usb3/3-1/3-1:1.0", "Front panel USB"},
	{"/devices/rdb.4/f0470400.ohci_v2/usb5/5-0:1.0", "Rear USB"},
	{"/devices/rdb.4/f0470500.ehci_v2/usb4/4-0:1.0", "Rear USB"},
	{"/devices/rdb.4/f0470500.ehci_v2/usb4/4-1/4-1:1.0", "Rear USB"},
	{"/devices/rdb.4/f0471000.xhci_v2/usb2/2-0:1.0", "Rear USB"}
#elif HWDM920
	{"/devices/platform/brcmstb-ahci.0/ata1/", "SATA"},
	{"/devices/rdb.4/f03e0000.sdhci/mmc_host/mmc0/", "eMMC"},
	{"/devices/rdb.4/f03e0200.sdhci/mmc_host/mmc1/", "SD"},
	{"/devices/rdb.4/f0470600.ohci_v2/usb6/6-0:1.0/port1/", "Front USB"},
	{"/devices/rdb.4/f0470300.ehci_v2/usb3/3-0:1.0/port1/", "Front USB"},
	{"/devices/rdb.4/f0471000.xhci_v2/usb2/2-0:1.0/port1/", "Front USB"},
	{"/devices/rdb.4/f0470300.ehci_v2/usb3/3-1/3-1:1.0", "Front panel USB"},	
	{"/devices/rdb.4/f0470400.ohci_v2/usb5/5-0:1.0/port1/", "Rear USB"},
	{"/devices/rdb.4/f0470500.ehci_v2/usb4/4-0:1.0/port1/", "Rear USB"},
	{"/devices/rdb.4/f0470500.ehci_v2/usb4/4-1/4-1:1.0", "Rear USB"},	
	{"/devices/rdb.4/f0471000.xhci_v2/usb2/2-0:1.0/port2/", "Rear USB"}
#elif HWVUSOLO4K
	{"/devices/platform/strict-ahci.0/ata1/", "SATA"},
	{"/devices/f0490600.ohci/usb10/", "Front USB"},
	{"/devices/f0480400.ohci/usb7/", "Rear USB 3.0 lower"},
	{"/devices/f0480600.ohci/usb8/", "Rear USB 3.0 upper"}
#elif HWUNO4KSE
	{"/devices/platform/rdb/f045a000.sata/ata1/", "SATA"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1", "Rear USB 3.0 lower"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-1/2-1", "Rear USB 3.0 lower"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1", "Rear USB 3.0 upper"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2", "Rear USB 3.0 upper"}
#elif HWDUO2 // CHECKED
	{"/devices/platform/strict-ahci.0/ata1/", "eSATA"},
	{"/devices/platform/ehci-brcm.2/usb3/", "Front USB"},
	{"/devices/platform/ehci-brcm.0/usb1/", "Rear USB lower"},
	{"/devices/platform/ehci-brcm.1/usb2/", "Rear USB upper"}
#elif HWDUO4K
	{"/devices/platform/rdb/8b0a000.sata/", "SATA"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb1/", "Front USB"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb2/2-2/", "Rear USB 3.0 upper"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb2/2-1/", "Rear USB 3.0 lower"}
#elif HWDUO4KSE
	{"/devices/platform/rdb/f045a000.sata/", "SATA"},
	{"/devices/platform/rdb/f0480500.ehci_v2/usb6/", "Front USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/", "Rear USB 3.0 upper"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-1/", "Rear USB 3.0 lower"}
#elif HWVUULTIMO4K
	{"/devices/platform/brcmstb-ahci.0/ata1", "SATA"},
	{"/devices/rdb.3/f0470300.ehci_v2/usb3/", "Rear USB 3.0 lower"},
	{"/devices/rdb.3/f0470500.ehci_v2/usb4/", "Rear USB 3.0 upper"},
	{"/devices/rdb.3/f0480600.ohci_v2/usb10/", "Front USB"}
#elif HWH7
	{"/devices/platform/rdb/f045a000.sata/ata1/", "SATA"},
	{"/devices/platform/f0470500.ehci/usb2/", "Rear USB 3.0"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.2/", "Rear USB lower"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.1/", "Rear USB upper"}
#elif HWH17 // CHECKED
	{"/devices/platform/f0470300.ehci/usb1/", "Front USB"},
	{"/devices/platform/f0471000.xhci/usb6/", "Rear USB"},
	{"/devices/platform/f0471000.ohci/usb4/", "Rear USB"},
	{"/devices/platform/f0470500.ehci/usb2/", "Rear USB"}
#elif HWPULSE4K
	{"/devices/platform/soc/f9900000.hiahci/ata1/host0/target0:0:0/0:0:0:0", "SATA"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/", "Front USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/", "Rear USB"}
#elif HWPULSE4KMINI // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1/", "microSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/", "Rear upper USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/", "Rear lower USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/", "Rear lower USB"}
#elif HWGBTRIO4K // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.3/1-1.3:1.0", "Rear right microSD"}, 
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.2/1-1.2:1.0", "Rear right USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1:1.0", "Rear left USB 3.0"},	
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2:1.0", "Front panel USB"}
#elif HWGBTRIO4KPRO // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2", "microSD"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/4-1/4-1", "Rear USB left"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1", "Rear USB left"},
	{"/devices/platform/soc/f9880000.ohci/usb2/2-1/2-1", "Rear USB right"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1", "Rear USB right"}
#elif HWGBUE4K
	{"/devices/platform/rdb/f045a000.sata/ata2/", "SATA"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1.1/3-1.1:", "Front panel USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/", "Rear USB 3.0"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1.2/3-1.2:", "Rear upper USB"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1.3/3-1.3:", "Rear lower USB"}
#elif HWGBQUAD4K
	{"/devices/platform/rdb/f045a000.sata/", "SATA"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.4/4-1.4:1.0", "Rear middle USB 3.0 left"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.3/2-2.3:1.0", "Rear middle USB 3.0 right"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.2/4-1.2:1.0", "Rear right lower USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.1/4-1.1:1.0", "Rear right upper USB"}, 
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1:1.0", "Front panel, USB"}
#elif HWGBQUAD4KPRO // CHECKED
	{"/devices/platform/rdb/f045a000.sata/", "SATA"},
	{"/devices/platform/rdb/f03e0000.sdhci/mmc_host/", "SD"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.1", "Front USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.1", "Front USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.4", "Rear USB right"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.4", "Rear USB right"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1", "Rear USB 3.0, left"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-1/2-1", "Rear USB 3.0, left"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.3", "Rear USB-C"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.3", "Rear USB-C"}
#elif HWHD51 // CHECKED
	{"/devices/platform/rdb/f045a000.sata/ata1/", "SATA"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.2", "Front USB"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.3", "Rear USB left"},
	{"/devices/platform/f0471000.xhci/usb6/6-2/6-2", "Rear USB right"},
	{"/devices/platform/f0470500.ehci/usb2/2-1/2-1", "Rear USB right"}
#elif HWHD61 // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1", "Front panel, microSD"}, 
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1", "Front panel USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1", "Rear USB"},
	{"/devices/platform/soc/f9900000.hiahci/ata1/", "SATA"}
#elif HWSFX6008 // CHECKED
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1", "Left USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1", "Rear USB"}
#elif HWOSNINO // CHECKED
	{"/devices/platform/ehci-brcm.0/usb1/1-2", "Front USB right"},
	{"/devices/platform/ehci-brcm.0/usb1/1-1", "Rear USB right"}
#elif HWMULTIBOXPRO // CHECKED
	{"/devices/platform/soc/f98a0000.xhci/usb3", "Rear USB left"},
	{"/devices/platform/soc/f9890000.ehci/usb1", "Rear USB right"},
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1", "microSD"}
#elif HWU5 // eg. Dinobot4k
	{"/devices/platform/soc/f98a0000.xhci/usb3/", "Rear USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2.3/", "Rear USB Left"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2.4/", "Front Left USB"}
#elif HWSF8008
	{"/devices/platform/soc/f98a0000.xhci/usb4/4-1/4-1", "Right USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/3-1/3-1", "Right USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.2", "Rear USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.3", "Rear microSD"}
#elif HWSF8008M
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1:1.0", "Right side - left USB 3.0"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Right side - right USB"}
#elif HWET7X00 // CHECKED
	{"/devices/platform/ehci-brcm.0/usb1/1-1/1-1:1.0", "Rear USB"},
	{"/devices/platform/ehci-brcm.0/usb1/1-2/1-2:1.0", "Front panel USB"}  
#elif HWH9COMBO // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1/mmc1:0007", "Rear microSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Rear USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2.4/1-2.4:1.0", "Front panel USB"}
#elif HWH9 // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc0/mmc0:0007", "Rear microSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Rear USB"}
#elif HWH10 // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1", "Rear USB left"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2", "Rear USB right"},
	{"/devices/platform/soc/f9900000.hiahci/ata1/", "SATA"}
#else

#endif

};

#endif
