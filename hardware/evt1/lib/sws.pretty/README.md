# sws.pretty

Project footprints for the EVT1 boards. Drafts for engineering review, not released.

| Footprint | Source | Status |
|---|---|---|
| Relay_Omron_G5RL-1A-E | `hardware/tools/footprints.py`, from Omron G5RL dimensions | Drawn; confirm against Omron and Hongfa drawings |
| ESP32-C6-MINI-1 | Espressif, [espressif/kicad-libraries](https://github.com/espressif/kicad-libraries), CC-BY-SA 4.0 with the KiCad design exception | Imported unchanged |
| Fuse_Schurter_UMT-H | `footprints.py`, Schurter UMT-H datasheet land (pads 3.75 x 5.6, 10.0 inner gap); matches two independent KiCad footprints | Drawn |
| Mornsun_LD03-23B | `footprints.py`; Mornsun gives the layout only as a graphic, so pin positions come from two built designs (OpenEnergyMonitor emonVs, TasmotaFresh) that agree | Drawn; caliper-check the first module, plan for 17.6 mm height |
| LED_SK6812MINI-E_Reverse | `footprints.py`, OPSCO SK6812MINI-E (C5149201): 1 VDD, 2 DOUT, 3 GND, 4 DIN, pitch 1.5; 3.6 x 3.2 mm cutout with R0.5 corners | Drawn; pin pattern matches the LCSC land and three production keyboard footprints |
| Mains_Terminal_3x2.5mm2, BS1363_Outlet_Contacts, TCO_Axial_15A, TouchPad_12mm, NFC_Antenna_PCB_25x15 | set by the enclosure and faceplate | Placeholder, drawn at layout |
