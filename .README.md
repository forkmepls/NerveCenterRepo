# NNC (Nick's Nerve Center) - Hardware Monitor

![Status](https://img.shields.io/badge/Status-Active_Development-green) ![Platform](https://img.shields.io/badge/Platform-Windows_10%2F11-blue) ![License](https://img.shields.io/badge/License-Proprietary-orange)

## 📖 About the Project
**NNC** is a specialized hardware monitoring utility designed to provide accurate, real-time telemetry for modern high-performance PCs.

Unlike standard industry tools (such as HWMonitor) which often report "Target Frequency" (P-State requests), NNC calculates the **Effective Clock Speed**. This is particularly critical for **AMD Ryzen 9000 Series** processors, which utilize aggressive sleep states that legitimate monitoring tools often fail to capture.

### Key Features
* **True Effective Clock Monitoring:** Accurately reports idle downclocking (e.g., ~2000 MHz) instead of falsely reporting Max Boost (5000+ MHz) during idle.
* **Low Overhead:** Built with Python and optimized C# libraries for minimal CPU impact.
* **Portable Deployment:** Runs as a standalone executable with no installation required.

---

## ⚠️ Important: Antivirus & Driver Warning

This software utilizes the **WinRing0** low-level driver to access CPU registers. Because this driver allows direct communication with hardware (Ring 0 access), **Windows Defender and other Antivirus software will likely flag it as a "Vulnerable Driver" or generic Malware.**

**This is a known false positive.** The driver is standard in the hardware monitoring industry, but its power triggers heuristic security alerts.

### 🛡️ Verification (Check the Hash)
To ensure you are running the genuine, unmodified software, please verify the SHA-256 hash of the `.exe` against the value below:

| File Name | SHA-256 Hash | Direct link to results |
| :--- | :--- |
| `NNC_25.exe` | `19df8747e5a70843e5b34f12d2fa6836996756648ddb06eb44dfdc7ee6c6b8b9` | `https://www.virustotal.com/gui/file/19df8747e5a70843e5b34f12d2fa6836996756648ddb06eb44dfdc7ee6c6b8b9?nocache=1`

> *You can verify this hash by uploading the file to [VirusTotal.com](https://www.virustotal.com/)*

---

## ⚖️ Legal & Third-Party Credits

This software is a proprietary application that utilizes open-source components. In compliance with their respective licenses, the following attributions are provided:

### LibreHardwareMonitor
Hardware monitoring functionality is provided by the **LibreHardwareMonitor** library.
* **License:** Mozilla Public License 2.0 (MPL 2.0)
* **Source Code:** [https://github.com/LibreHardwareMonitor/LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)

### WinRing0 (OpenLibSys)
Low-level hardware access is provided by the **WinRing0** driver.
* **License:** BSD License
* **Copyright:** Copyright (c) 2007-2009 OpenLibSys.org. All rights reserved.
* *Full license text is included in the `LICENSE-3RD-PARTY.txt` file distributed with this release.*

---

## 🚀 Installation & Usage
1.  Download the latest release from the **Releases** tab.
2.  Extract the folder to a preferred location.
3.  Run `NNC.exe` as administrator, required to pull sensor data.
    * *Note: If prompted by Windows SmartScreen, click "More Info" -> "Run Anyway".*
    * *Note: If blocked by Antivirus, you may need to add an exclusion for the NNC folder due to the WinRing0 driver.*

---

**Developer Contact:**
*Maintained by venatic/forkmepls*
