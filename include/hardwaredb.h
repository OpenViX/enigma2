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


Note: when creating a list of a receivers USB locations and phyical attachments,
typically a USB 2.0 device will use a different connection than a USB 3.0 device.
In most situations an ehci attachment is USB 2.0, xhci attachment is USB 3.0.
In most receivers there will be both ehci & xchi attachments for a USB port.

Front locations are from viewing the receiver from the front.
Rear locations are from viewing the receiver from the back.
*/

#ifndef __hardwaredb_h
#define __hardwaredb_h
#include <string>
#include <unordered_map>

static std::unordered_map<std::string, std::string> HardwareDB{

#ifdef HWDM900 // CHECKED
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
#elif HWDM920 // CHECKED
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
#elif HWDUAL // CHECKED
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1:1.0", "Rear USB 3.0"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Front USB"}
#elif HWET7X00 // CHECKED
	{"/devices/platform/ehci-brcm.0/usb1/1-1/1-1:1.0", "Rear USB"},
	{"/devices/platform/ehci-brcm.0/usb1/1-2/1-2:1.0", "Front panel USB"} 
#elif HWGBIP4K // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.3/1-1.3", "Rear MicroSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.2/1-1.2", "Rear Right USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/4-1/4-1", "Rear Left USB 3.0"}
#elif HWGBQUAD4K // CHECKED
	{"/devices/platform/rdb/f045a000.sata/", "SATA"},
	{"/devices/platform/rdb/f03e0000.sdhci/mmc_host/", "SD"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1:1.0", "Front USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.4/4-1.4:1.0", "Rear Left USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.3/4-1.3:1.0", "Rear Right USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.4/2-2.4:1.0", "Rear Left USB 3.0"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.3/2-2.3:1.0", "Rear Right USB 3.0"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.2/4-1.2:1.0", "Rear Lower USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.1/4-1.1:1.0", "Rear Upper USB"}
#elif HWGBQUAD4KPRO // CHECKED
	{"/devices/platform/rdb/f045a000.sata/", "SATA"},
	{"/devices/platform/rdb/f03e0000.sdhci/mmc_host/", "SD"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.1", "Front USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.1", "Front USB 3.0"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.4", "Rear Right USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.4", "Rear Right USB 3.0"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1", "Rear Left USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-1/2-1", "Rear Left USB 3.0"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1.3", "Rear USB-C"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2.3", "Rear USB-C 3.0"}
#elif HWGBTRIO4K // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.3/1-1.3:1.0", "Rear Right MicroSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.2/1-1.2:1.0", "Rear Right USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1:1.0", "Rear Left USB 3.0"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/4-1/4-1:1.0", "Rear Left USB 3.0"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2:1.0", "Front USB"}
#elif HWGBTRIO4KPRO // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2", "MicroSD"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/4-1/4-1", "Rear Left USB 3.0"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1", "Rear Left USB 3.0"},
	{"/devices/platform/soc/f9880000.ohci/usb2/2-1/2-1", "Rear Right USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1", "Rear Right USB"}
#elif HWGBUE4K // CHECKED
	{"/devices/platform/rdb/f045a000.sata/ata2/", "SATA"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1.1/3-1.1:", "Front USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1:1.0", "Rear Left USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2:1.0", "Rear Left USB 3.0"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1.2/3-1.2:", "Rear Upper USB"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1.3/3-1.3:", "Rear Lower USB"}
#elif HWH7
	{"/devices/platform/rdb/f045a000.sata/ata1/", "SATA"},
	{"/devices/platform/f0470500.ehci/usb2/", "Rear USB 3.0"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.2/", "Rear USB Lower"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.1/", "Rear USB Upper"}
#elif HWH9 // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc0/mmc0", "Rear microSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Rear USB"}
#elif HWH9COMBO // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1/mmc1", "Rear microSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Rear USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2.4/1-2.4:1.0", "Front panel USB"}
#elif HWH9COMBOSE // CHECKED
	{"/devices/platform/soc/f9900000.hiahci/ata1/host0/target0:0:0/0:0:0:0", "SATA"},
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1/mmc1", "Rear MicroSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Rear USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2.4/1-2.4:1.0", "Front USB"}
#elif HWH9SSE // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1/mmc1", "Rear MicroSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Rear USB"}
#elif HWH10 // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1", "Rear USB left"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2", "Rear USB right"},
	{"/devices/platform/soc/f9900000.hiahci/ata1/", "SATA"}
#elif HWH11 // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1/mmc1:1234", "Rear MicroSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Rear USB"}
#elif HWH17 // CHECKED
	{"/devices/platform/f0470300.ehci/usb1/", "Front USB"},
	{"/devices/platform/f0471000.xhci/usb6/", "Rear USB"},
	{"/devices/platform/f0471000.ohci/usb4/", "Rear USB"},
	{"/devices/platform/f0470500.ehci/usb2/", "Rear USB"}
#elif HWHD51 // CHECKED
	{"/devices/platform/rdb/f045a000.sata/ata1/", "SATA"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.2", "Front USB"},
	{"/devices/platform/f0470300.ehci/usb1/1-1/1-1.3", "Rear left USB"},
	{"/devices/platform/f0471000.xhci/usb6/6-2/6-2", "Rear right USB"},
	{"/devices/platform/f0470500.ehci/usb2/2-1/2-1", "Rear right USB"}
#elif HWHD61 // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1", "Front panel, microSD"}, 
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1", "Front panel USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1", "Rear USB"},
	{"/devices/platform/soc/f9900000.hiahci/ata1/", "SATA"}
#elif HWMULTIBOXPRO // CHECKED
	{"/devices/platform/soc/f98a0000.xhci/usb3", "Rear USB Left 3.0"},
	{"/devices/platform/soc/f9890000.ehci/usb1", "Rear USB Right"},
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1", "MicroSD"}
#elif HWOSMIO4KPLUS
	{"/devices/platform/rdb/f0b00300.ehci_v2/usb1/1-1/1-1:1.0", "Rear USB"},
	{"/devices/platform/rdb/f0b00500.ehci_v2/usb2/2-1/2-1:1.0", "Left USB"}
#elif HWPULSE4K
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1", "Front MicroSD"},
	{"/devices/platform/soc/f9900000.hiahci/ata1/host0/target0:0:0/0:0:0:0", "SATA"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/", "Front USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/", "Rear USB"}
#elif HWPULSE4KMINI // CHECKED
	{"/devices/platform/soc/f9820000.himciv200.SD/mmc_host/mmc1/", "MicroSD"},
	{"/devices/platform/soc/f9890000.ehci/usb1/", "Rear Upper USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/", "Rear Lower USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/", "Rear Lower USB"}
#elif HWSF8008M
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1:1.0", "Right USB 3.0"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Right USB 2.0"}
#elif HWSF8008
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.4", "Internal NVMe"},
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1:1.0", "Right USB 3.0"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/4-1/4-1", "Right USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/3-1/3-1", "Right USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.2", "Rear USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.3", "Rear MicroSD"}
#elif HWSFX6008 // CHECKED
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1", "Left USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1", "Rear USB"}
#elif HWSX88V2 // CHECKED
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1", "Right USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2", "Left USB"}
#elif HWSX988 // CHECKED
	{"/devices/platform/soc/f9890000.ehci/usb1/1-2/1-2:1.0", "Right Side Front USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1:1.0", "Right Side Rear USB"}
#elif HWUSTYM4KPRO
	{"/devices/platform/soc/f98a0000.xhci/usb3/3-1/3-1:1.0", "Right USB 3.0"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/4-1/4-1", "Right USB"},
	{"/devices/platform/soc/f98a0000.xhci/usb4/3-1/3-1", "Right USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.2", "Rear USB"},
	{"/devices/platform/soc/f9890000.ehci/usb1/1-1/1-1.3", "Rear MicroSD"}
#elif HWVUDUO2 // CHECKED
	{"/devices/platform/strict-ahci.0/ata1/", "eSATA"},
	{"/devices/platform/ehci-brcm.2/usb3/", "Front USB"},
	{"/devices/platform/ehci-brcm.0/usb1/", "Rear Lower USB"},
	{"/devices/platform/ehci-brcm.1/usb2/", "Rear Upper USB"}
#elif HWVUDUO4K // CHECKED
	{"/devices/platform/rdb/8b0a000.sata/", "SATA"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb1/1-2/1-2.1/1-2.1:1.0", "Front USB"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb2/2-2/2-2:1.0", "Rear Upper USB 3.0"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb2/2-1/2-1:1.0", "Rear Lower USB 3.0"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb1/1-1/1-1.2/1-1.2:1.0", "Rear Upper USB"},
	{"/devices/platform/rdb/8b39000.xhci_v2/usb1/1-1/1-1.1/1-1.1:1.0", "Rear Lower USB"}
#elif HWVUDUO4KSE // CHECKED
	{"/devices/platform/rdb/f045a000.sata/", "SATA"},
	{"/devices/platform/rdb/f0480500.ehci_v2/usb6/6-1/6-1:1.0", "Front USB"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1:1.0", "Rear Lower USB"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1:1.0", "Rear Upper USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2:1.0", "Rear Upper USB 3.0"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-1/2-1:1.0", "Rear Lower USB 3.0"}
#elif HWVUSOLO4K // CHECKED
	{"/devices/platform/strict-ahci.0/ata1", "SATA"},
	{"/devices/f0490500.ehci/usb6/6-1/6-1:1.0", "Front USB"},
	{"/devices/f0481000.xhci/usb2/2-1/2-1:1.0", "Rear Lower USB 3.0"},
	{"/devices/f0481000.xhci/usb2/2-2/2-2:1.0", "Rear Upper USB 3.0"},
	{"/devices/f0480500.ehci/usb4/4-1/4-1:1.0", "Upper USB"},
	{"/devices/f0480300.ehci/usb3/3-1/3-1:1.0", "Lower USB"}
#elif HWVUUNO4K // NOT CHECKED
	{"/devices/platform/rdb/f045a000.sata/ata1", "SATA"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1", "Rear Lower USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-1/2-1", "Rear Lower USB 3.0"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1", "Rear Upper USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2", "Rear Upper USB 3.0"}
#elif HWVUUNO4KSE // CHECKED
	{"/devices/platform/rdb/f045a000.sata/ata1", "SATA"},
	{"/devices/platform/rdb/f0470300.ehci_v2/usb3/3-1/3-1", "Rear Lower USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-1/2-1", "Rear Lower USB 3.0"},
	{"/devices/platform/rdb/f0470500.ehci_v2/usb4/4-1/4-1", "Rear Upper USB"},
	{"/devices/platform/rdb/f0471000.xhci_v2/usb2/2-2/2-2", "Rear Upper USB 3.0"}
#elif HWVUULTIMO4K // CHECKED
	{"/devices/platform/brcmstb-ahci.0/ata1", "SATA"},
	{"/devices/rdb.1/f0471000.xhci_v2/usb2/2-1/2-1:1.0", "Rear Lower USB 3.0"},
	{"/devices/rdb.1/f0471000.xhci_v2/usb2/2-2/2-2:1.0", "Rear Upper USB 3.0"},
	{"/devices/rdb.1/f0470500.ehci_v2/usb4/4-1/4-1:1.0", "Rear Upper USB"},
	{"/devices/rdb.1/f0470300.ehci_v2/usb3/3-1/3-1:1.0", "Rear Lower USB"},
	{"/devices/rdb.1/f0480500.ehci_v2/usb6/6-1/6-1:1.0", "Front USB"}
#elif HWVUZERO // NOT CHECKED
	{"/devices/platform/ehci-brcm.2/usb1", "USB"}
#elif HWVUZERO4K // CHECKED
	{"/devices/platform/rdb/f0b00300.ehci_v2/usb1/1-1/1-1:1.0", "Rear USB"}
#else

#endif

};

#endif
