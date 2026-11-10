"""
Smart Wall Socket EVT1 schematic, as data.

Two KiCad projects:
  rear  - hot side (mains, metering, hot-side supply, polarity check),
          the barrier crossing (isolator, LD03, relays) and the safe zone
          (relay drivers, isolator 3.3 V, NTCs, board-to-board header)
  front - SELV only (buck, ESP32-C6, touch, NFC, light lines, test pads)

Net naming:
  L_BUS, N_IN, E_IN, N_F, N_R, L_OUT1/2 and every H_* net are mains-referenced.
  The hot side's ground IS the live busbar (L_BUS): never probe it with an
  earthed instrument.
  Safe-side nets carry the names used by the firmware's board layer.

Rear references start at 1, front references at 101.
"""
from kicad_gen import Block, Part, Project, Sheet, box, one_pin, two_pin

# --------------------------------------------------------------------------
# Footprints
# --------------------------------------------------------------------------
FP = {
    "R0603": "Resistor_SMD:R_0603_1608Metric",
    "R1206": "Resistor_SMD:R_1206_3216Metric",
    "R2512": "Resistor_SMD:R_2512_6332Metric",
    "R0411": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal",
    "R0207": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
    "R0617": "Resistor_THT:R_Axial_DIN0617_L17.0mm_D6.0mm_P20.32mm_Horizontal",
    "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric",
    "CP6.3": "Capacitor_SMD:CP_Elec_6.3x7.7",
    "CP6358": "Capacitor_SMD:CP_Elec_6.3x5.8",
    "SOT23": "Package_TO_SOT_SMD:SOT-23",
    "SOT23-5": "Package_TO_SOT_SMD:SOT-23-5",
    "SOT23-6": "Package_TO_SOT_SMD:SOT-23-6",
    "SOD123": "Diode_SMD:D_SOD-123",
    "SOD323": "Diode_SMD:D_SOD-323",
    "SMA": "Diode_SMD:D_SMA",
    "SMB": "Diode_SMD:D_SMB",
    "SOIC8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "SOIC16W": "Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm",
    "SSOP20": "Package_SO:SSOP-20_3.9x8.7mm_P0.635mm",
    "TSSOP8": "Package_SO:TSSOP-8_3x3mm_P0.65mm",
    "MOV10": "Varistor:RV_Disc_D12mm_W4.2mm_P7.5mm",
    "UMTH": "sws:Fuse_Schurter_UMT-H",
    "SMC": "Diode_SMD:D_SMC",
    "NETTIE": "NetTie:NetTie-2_SMD_Pad0.5mm",
    "CP_D8": "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
    "L_RAD": "Inductor_THT:L_Radial_D8.7mm_P5.00mm_Fastron_07HCP",
    "LNKSO8C": "Package_SO:PowerIntegrations_SO-8C",
    "L4018": "Inductor_SMD:L_Bourns-SRN4018",
    "HDR2x7": "Connector_PinHeader_1.27mm:PinHeader_2x07_P1.27mm_Vertical_SMD",
    "SKT2x7": "Connector_PinSocket_1.27mm:PinSocket_2x07_P1.27mm_Vertical_SMD",
    "TP": "TestPoint:TestPoint_Pad_D1.5mm",
    # Placeholders, drawn at layout once the part is confirmed (see review notes)
    "TERM": "sws:Mains_Terminal_3x2.5mm2",
    "OUTLET": "sws:BS1363_Outlet_Contacts",
    "TCO": "sws:TCO_Axial_15A",
    "RELAY": "sws:Relay_Omron_G5RL-1A-E",
    "LD03": "sws:Mornsun_LD03-23B",
    "ESP": "sws:ESP32-C6-MINI-1",
    "SK6812E": "sws:LED_SK6812MINI-E_Reverse",
    "TOUCH": "sws:TouchPad_12mm",
    "NFCANT": "sws:NFC_Antenna_PCB_25x15",
}

# --------------------------------------------------------------------------
# Symbols
# --------------------------------------------------------------------------
S_R = two_pin("R", "R", "R", desc="Resistor")
S_C = two_pin("C", "C", "C", desc="Capacitor")
S_CP = two_pin("C_Polarized", "CP", "C", desc="Polarised capacitor, pin 1 = +")
S_L = two_pin("L", "L", "L", desc="Inductor")
S_D = two_pin("D", "D", "D", desc="Diode, pin 1 = K, pin 2 = A")
S_DS = two_pin("D_Schottky", "DS", "D", desc="Schottky diode, pin 1 = K, pin 2 = A")
S_D_SOT23 = two_pin("D_SOT23", "D", "D", n1="3", n2="1", desc="Diode in SOT-23: pin 3 = K, pin 1 = A, pin 2 not connected")
S_DZ = two_pin("D_Zener", "DZ", "D", desc="Zener diode, pin 1 = K, pin 2 = A")
S_TVS = two_pin("D_TVS_Uni", "TVS", "D", desc="Unidirectional TVS, pin 1 = K, pin 2 = A")
S_F = two_pin("Fuse", "F", "F", desc="Fuse")
S_RV = two_pin("Varistor", "RV", "RV", desc="Metal-oxide varistor")
S_NTC = two_pin("Thermistor_NTC", "NTC", "TH", desc="NTC thermistor")
S_TCO = two_pin("Thermal_Cutoff", "TCO", "TF", desc="Non-resettable thermal cut-off")
S_SH = two_pin("R_Shunt", "SH", "RS", desc="Current shunt")
S_NT = two_pin("NetTie", "NT", "NT", desc="Net tie: forces a Kelvin tap at the shunt pad in layout")
S_ANT = two_pin("NFC_Antenna", "L", "ANT", desc="PCB loop antenna")
S_E = one_pin("TouchPad", "E", desc="Capacitive touch electrode")
S_TP = one_pin("TestPad", "TP", desc="Test pad")

S_BL0939 = box("BL0939", [
    ("3", "IP1", "input"), ("4", "IN1", "input"), ("5", "IP2", "input"), ("6", "IN2", "input"), None,
    ("7", "VP", "input"), ("2", "VT", "input"), None,
    ("9", "A1", "input"), ("10", "A2", "input"), ("11", "A3", "input"), ("12", "A4", "input"),
], [
    ("1", "VDD", "power_in"), ("8", "GND", "power_in"), ("16", "SEL", "input"), None,
    ("18", "RX/SDI", "input"), ("19", "TX/SDO", "output"), None, ("13", "ZX", "output"),
    ("15", "CF", "output"), ("14", "I_LEAK", "output"), None, ("17", "SCLK", "input"), ("20", "VPP", "passive"),
], desc="Belling BL0939, 2-channel metering, SSOP-20")

S_KP3310 = box("KP3310SGA", [
    ("5,6,7,8", "DRAIN", "passive"), ("4", "VDD", "passive"), ("1", "SEL", "input"),
], [
    ("3", "VOUT", "power_out"), ("2", "GND", "power_in"),
], desc="Kiwi KP3310, non-isolated HV linear regulator, SOP-8")

S_LNK = box("LNK3204D", [("4", "D", "passive"), ("1", "BP/M", "passive"), ("2", "FB", "input")],
            [("5,6,7,8", "S", "passive")], desc="Power Integrations LinkSwitch-TN2, 725 V, SO-8C: 1 BP/M, 2 FB, 4 D, 5-8 S, pin 3 absent (checked)")

S_LMV393 = box("LMV393", [
    ("3", "+INA", "input"), ("2", "-INA", "input"), ("5", "+INB", "input"), ("6", "-INB", "input"),
], [
    ("8", "V+", "power_in"), ("4", "GND", "power_in"), ("1", "OUTA", "open_collector"), ("7", "OUTB", "open_collector"),
], desc="Dual comparator, open-drain, SOIC-8")

S_OR = box("74LVC1G32", [("1", "A", "input"), ("2", "B", "input")],
           [("5", "VCC", "power_in"), ("3", "GND", "power_in"), ("4", "Y", "output")],
           desc="Single 2-input OR, SOT-23-5")

S_ISO = box("ISO7761DW", [
    ("1", "VCC1", "power_in"), ("8", "GND1", "power_in"), None, ("2", "INA", "input"), ("3", "INB", "input"),
    ("4", "INC", "input"), ("5", "IND", "input"), ("6", "INE", "input"), ("7", "OUTF", "output"),
], [
    ("16", "VCC2", "power_in"), ("9", "GND2", "power_in"), None, ("15", "OUTA", "output"), ("14", "OUTB", "output"),
    ("13", "OUTC", "output"), ("12", "OUTD", "output"), ("11", "OUTE", "output"), ("10", "INF", "input"),
], desc="TI ISO7761 6-ch reinforced digital isolator, 5 fwd / 1 rev, SOIC-16 wide. Side 1 = hot.")

S_LD03 = box("LD03-23B05R2", [("2", "AC(L)", "passive"), ("1", "AC(N)", "passive")],
             [("5", "+Vo", "power_out"), ("4", "-Vo", "power_out")],
             desc="Mornsun 3 W AC-DC module, 5 V / 600 mA, 4 kVAC reinforced")

S_RELAY = box("Relay_SPST_NO", [("1", "A1", "passive"), ("8", "A2", "passive")],
              [("3,6", "COM", "passive"), ("4,5", "NO", "passive")], ref="K",
              desc="16 A SPST-NO power relay, Omron G5RL-1A-E pinning: coil 1/8, COM 3+6, NO 4+5 (doubled for 16 A)")

S_TERM = box("Mains_Terminal", [], [("1", "L", "passive"), ("2", "N", "passive"), ("3", "E", "passive")], ref="J",
             desc="Mains screw terminals, 3 x 2.5 mm2")
S_OUTLET = box("Outlet_Contacts", [("1", "L", "passive"), ("2", "N", "passive"), ("3", "E", "passive")], [], ref="J",
               desc="BS 1363 socket-outlet contact set")

S_XC6206 = box("XC6206P332MR", [("3", "VI", "power_in")], [("2", "VO", "power_out"), ("1", "GND", "power_in")],
               desc="3.3 V LDO, SOT-23")
S_NFET = box("NMOS_GSD", [("1", "G", "input")], [("3", "D", "passive"), ("2", "S", "passive")], ref="Q",
             desc="N-channel MOSFET, SOT-23 (1 G, 2 S, 3 D)")
S_PFET = box("PMOS_GSD", [("1", "G", "input")], [("2", "S", "passive"), ("3", "D", "passive")], ref="Q",
             desc="P-channel MOSFET, SOT-23 (1 G, 2 S, 3 D)")

HDR_PINS = [
    ("1", "+5V"), ("2", "+5V"), ("3", "GND"), ("4", "GND"), ("5", "MTR_TX"), ("6", "MTR_RX"),
    ("7", "ZX"), ("8", "POL_A"), ("9", "POL_B"), ("10", "ALARM"), ("11", "RELAY1"), ("12", "RELAY2"),
    ("13", "NTC1"), ("14", "NTC2"),
]
S_HDR = box("Conn_B2B_2x07", [(n, f, "passive") for n, f in HDR_PINS if int(n) % 2],
            [(n, f, "passive") for n, f in HDR_PINS if not int(n) % 2], ref="J",
            desc="Board-to-board, 2 x 7, 1.27 mm. Same pin map on both boards.")
HDR_CONN = {n: f for n, f in HDR_PINS}

S_TLV = box("TLV62569DBV", [("4", "VIN", "power_in"), ("1", "EN", "input")],
            [("3", "SW", "power_out"), ("5", "FB", "input"), ("2", "GND", "power_in")],
            desc="2 A synchronous buck, SOT-23-5")

GND_PINS = ",".join(["1", "2", "11", "14"] + [str(i) for i in range(36, 54)])
NC_PINS = "4,7,21,32,33,34,35"
S_ESP = box("ESP32-C6-MINI-1", [
    ("3", "3V3", "power_in"), (GND_PINS, "GND", "power_in"), ("8", "EN", "input"), None,
    ("12", "IO0", "bidirectional"), ("13", "IO1", "bidirectional"), ("5", "IO2", "bidirectional"),
    ("6", "IO3", "bidirectional"), None, ("9", "IO4", "bidirectional"), ("10", "IO5", "bidirectional"), None,
    ("15", "IO6", "bidirectional"), ("16", "IO7", "bidirectional"), ("22", "IO8", "bidirectional"),
], [
    ("23", "IO9", "bidirectional"), None, ("17", "IO12/USB_D-", "bidirectional"), ("18", "IO13/USB_D+", "bidirectional"),
    None, ("19", "IO14", "bidirectional"), ("20", "IO15", "bidirectional"), None, ("24", "IO18", "bidirectional"),
    ("25", "IO19", "bidirectional"), ("26", "IO20", "bidirectional"), ("27", "IO21", "bidirectional"),
    ("28", "IO22", "bidirectional"), ("29", "IO23", "bidirectional"), None, ("30", "RXD0", "bidirectional"),
    ("31", "TXD0", "bidirectional"), None, (NC_PINS, "NC", "no_connect"),
], desc="Espressif ESP32-C6-MINI-1(-H4), 53 pads. GND and NC pads are stacked.")

S_QT = box("AT42QT1011", [("4", "SNS", "passive"), ("3", "SNSK", "passive")],
           [("5", "VDD", "power_in"), ("2", "VSS", "power_in"), ("1", "OUT", "output"), ("6", "SYNC/MODE", "input")],
           desc="Microchip 1-key QTouch sensor, SOT-23-6")
S_NFC = box("NT3H2111W0FTT", [("1", "LA", "passive"), ("8", "LB", "passive")],
            [("6", "VCC", "power_in"), ("2", "VSS", "power_in"), ("3", "SCL", "input"), ("5", "SDA", "bidirectional"),
             ("4", "FD", "open_collector"), ("7", "VOUT", "power_out")],
            desc="NXP NTAG I2C plus, 1 kB, TSSOP-8")
S_BUF = box("74AHCT1G125", [("2", "A", "input"), ("1", "~OE", "input")],
            [("5", "VCC", "power_in"), ("3", "GND", "power_in"), ("4", "Y", "tri_state")],
            desc="Single buffer, 3-state, TTL inputs (3.3 V to 5 V level shift), SOT-23-5")
S_SK = box("SK6812MINI-E", [("4", "DIN", "input")],
           [("1", "VDD", "power_in"), ("3", "GND", "power_in"), ("2", "DOUT", "output")], ref="D",
           desc="Addressable RGB LED, reverse mount")


# --------------------------------------------------------------------------
# Part helpers
# --------------------------------------------------------------------------
def R(ref, val, a, b, fp="R0603", lcsc="", note="", dnp=False, mpn="", mfr="", ver=""):
    return Part(ref, S_R, val, {"1": a, "2": b}, FP[fp], lcsc, mpn, mfr, note, dnp, ver)


def C(ref, val, a, b, fp="C0603", lcsc="", note="", dnp=False, mpn="", mfr="", ver=""):
    return Part(ref, S_C, val, {"1": a, "2": b}, FP[fp], lcsc, mpn, mfr, note, dnp, ver)


def CP(ref, val, pos, neg, fp="CP6.3", lcsc="", note="", mpn="", mfr="", ver=""):
    return Part(ref, S_CP, val, {"1": pos, "2": neg}, FP[fp], lcsc, mpn, mfr, note, False, ver)


def D(sym, ref, val, k, a, fp, lcsc="", note="", mpn="", mfr="", ver=""):
    return Part(ref, sym, val, {"1": k, "2": a}, FP[fp], lcsc, mpn or val, mfr, note, False, ver)


def U(ref, sym, val, conn, fp, lcsc="", note="", mpn="", mfr="", ver="", dnp=False):
    return Part(ref, sym, val, conn, FP[fp] if fp in FP else fp, lcsc, mpn or val, mfr, note, dnp, ver)


# Common values (JLC basic parts unless noted). "ver": yes = checked on LCSC on 10 Nov 2026.
R10K = dict(lcsc="C25804")
R100K = dict(lcsc="C25803")
R1K = dict(lcsc="C21190")
R4K7 = dict(lcsc="C23162")
R100 = dict(lcsc="C22775")
R0 = dict(lcsc="C21189")
R1M = dict(lcsc="C22935")
R20K = dict(lcsc="C4184")
C100N = dict(lcsc="C14663")
C1U = dict(lcsc="C15849")
C10N = dict(lcsc="C57112")
C10U_0805 = dict(fp="C0805", lcsc="C15850")
C22U_0805 = dict(fp="C0805", lcsc="C45783")

# ==========================================================================
# REAR BOARD
# ==========================================================================
mains = Block(
    "1. Mains entry and outlet feeds",
    "Ring L/N/E land on the busbar; only outlet current passes the shunts and relays.\n"
    "Shunt common end = L_BUS = hot-side ground. Net ties NT1-NT4 force the IP/IN taps to start at the shunt pads (Kelvin).\n"
    "Thermal cut-offs: non-resettable, clamped to the outlet feed near the contacts; Tf chosen after the EVT thermal test.",
    [
        U("J1", S_TERM, "Mains terminal L/N/E", {"1": "L_BUS", "2": "N_IN", "3": "E_IN"}, "TERM",
          note="Screw terminals for 3 x 2.5 mm2 ring conductors; part chosen with the mechanism"),
        Part("RS1", S_SH, "1m 2512 >=2W manganin", {"1": "L_BUS", "2": "H_I1"}, FP["R2512"], "", "", "",
             "Outlet 1 shunt; 0.256 W at 16 A"),
        Part("RS2", S_SH, "1m 2512 >=2W manganin", {"1": "L_BUS", "2": "H_I2"}, FP["R2512"], "", "", "",
             "Outlet 2 shunt"),
        Part("NT1", S_NT, "Kelvin -", {"1": "L_BUS", "2": "H_S1N"}, FP["NETTIE"], note="At RS1 pad 1", virtual=True),
        Part("NT2", S_NT, "Kelvin +", {"1": "H_I1", "2": "H_S1P"}, FP["NETTIE"], note="At RS1 pad 2", virtual=True),
        Part("NT3", S_NT, "Kelvin -", {"1": "L_BUS", "2": "H_S2N"}, FP["NETTIE"], note="At RS2 pad 1", virtual=True),
        Part("NT4", S_NT, "Kelvin +", {"1": "H_I2", "2": "H_S2P"}, FP["NETTIE"], note="At RS2 pad 2", virtual=True),
        Part("TF1", S_TCO, "TCO 15A 250V", {"1": "H_I1", "2": "H_K1"}, FP["TCO"], "", "", "",
             "Outlet 1 thermal cut-off; Tf TBD (EVT thermal test)"),
        Part("TF2", S_TCO, "TCO 15A 250V", {"1": "H_I2", "2": "H_K2"}, FP["TCO"], "", "", "",
             "Outlet 2 thermal cut-off"),
        U("J2", S_OUTLET, "Outlet 1 contacts", {"1": "L_OUT1", "2": "N_IN", "3": "E_IN"}, "OUTLET"),
        U("J3", S_OUTLET, "Outlet 2 contacts", {"1": "L_OUT2", "2": "N_IN", "3": "E_IN"}, "OUTLET"),
    ])

feed = Block(
    "2. Electronics feed and surge protection",
    "Fuse and series resistor per Mornsun's LD03 application circuit. MOV after the fuse, thermally protected type.\n"
    "F1 is a 1500 A breaking-capacity fuse: if RV1 fails short, F1 must interrupt the circuit's prospective fault current.",
    [
        Part("F1", S_F, "1A T 277VAC 1500A HBC", {"1": "N_IN", "2": "N_F"}, FP["UMTH"], "", "3403.0274.23", "Schurter",
             "UMT-H, breaking capacity 1500 A. Must clear a shorted MOV at household fault current; a 1 A TE5 breaks only 25 A"),
        Part("RV1", S_RV, "MOV 561K 10mm, thermally protected", {"1": "L_BUS", "2": "N_F"}, FP["MOV10"], "", "",
             "", "e.g. Littelfuse TMOV/ Bourns TMOV-type; 350 VAC"),
        R("R1", "12R 3W wirewound", "N_F", "N_R", fp="R0617", note="Inrush limit for LD03; fusible type"),
    ])

hotsup = Block(
    "3. Hot-side supply (LNK3204 half-wave buck, 5 V, then 3.3 V)",
    "Replaces the KP3310 (R1 study, hardware/sim/R1-study.md): half-wave charging through a surge resistor could not supply the 8-15 mA load.\n"
    "High-side buck referenced to L_BUS. RF 47R + 2 x M7 + pi filter (2 x 4.7 uF 450 V, 1 mH): simulated bulk/drain peak 465 V at a 4 kV surge (switch rated 725 V).\n"
    "Feedback: C25 samples Vout during freewheel; 2.00 V x (1 + 3.09k/2.49k) = 4.48 V + about 0.5 V diode offset = 5.0 V (trim R35 at bring-up).\n"
    "BP/M = 1 uF selects the reduced current limit (enough for 20 mA, allows a small choke). D9 must be <= 35 ns trr (enclosure above 70 C).",
    [
        R("R2", "47R 2W fusible wirewound", "N_F", "H_RF", fp="R0617",
          note="Surge limiter and fuse for the LNK input; 270-390 mJ per 2-4 kV surge, choose a surge-rated type"),
        D(S_D, "D1", "M7 1000V 1A", "H_DA", "H_RF", "SMA", lcsc="C95872", mpn="M7"),
        D(S_D, "D8", "M7 1000V 1A", "H_BULK1", "H_DA", "SMA", lcsc="C95872", mpn="M7",
          note="Two in series: a negative surge puts up to 1.7 kV across the string"),
        CP("C1", "4.7u 450V 105C", "H_BULK1", "L_BUS", fp="CP_D8"),
        Part("L1", S_L, "1mH 0.1A", {"1": "H_BULK1", "2": "H_BULK2"}, FP["L_RAD"], "", "", "", "Pi-filter choke"),
        CP("C23", "4.7u 450V 105C", "H_BULK2", "L_BUS", fp="CP_D8"),
        U("U1", S_LNK, "LNK3204D", {"4": "H_BULK2", "1": "H_BP", "2": "H_FB", "5": "H_SW"},
          "LNKSO8C", mfr="Power Integrations", note="Pinout from the KiCad library symbol: BP/M 1, FB 2, D 4, S 5-8, no pin 3"),
        C("C24", "1u 16V", "H_BP", "H_SW", note="BP/M: 1 uF = reduced current limit", **C1U),
        Part("L2", S_L, "1mH 0.2A", {"1": "H_SW", "2": "+5V_HOT"}, FP["L_RAD"], "", "", "", "Buck choke"),
        D(S_D, "D9", "ES1J 600V 35ns", "H_SW", "L_BUS", "SMA", mpn="ES1J", note="Freewheel, trr <= 35 ns"),
        D(S_D, "D10", "M7 1000V 1A", "H_FBC", "+5V_HOT", "SMA", lcsc="C95872", mpn="M7",
          note="Feedback sample diode, glass passivated"),
        C("C25", "10u 25V", "H_FBC", "H_SW", **C10U_0805),
        R("R35", "3.09k 1%", "H_FBC", "H_FB"),
        R("R36", "2.49k 1%", "H_FB", "H_SW"),
        CP("C26", "100u 16V 105C", "+5V_HOT", "L_BUS"),
        R("R37", "2.4k", "+5V_HOT", "L_BUS", dnp=True, note="Preload, fit only if no-load regulation needs it"),
        U("U7", S_XC6206, "XC6206P332MR", {"3": "+5V_HOT", "2": "+3V3_HOT", "1": "L_BUS"}, "SOT23", lcsc="C5446", mfr="Torex"),
        C("C27", "1u", "+5V_HOT", "L_BUS", **C1U),
        C("C2", "10u 25V", "+3V3_HOT", "L_BUS", **C10U_0805),
        C("C3", "100n", "+3V3_HOT", "L_BUS", **C100N),
    ])

meter = Block(
    "4. Metering (BL0939)",
    "UART address 5 (A1, A3 high; A2, A4 low): the firmware sends 0x55/0xA5, which encode address 5.\n"
    "Divider 5 x 390k + 470R: 230 V gives 55 mV rms, 290 V gives 70 mV rms (pin limit 70 mV rms). Firmware board file: div_r_bottom = 0.47 k.\n"
    "Alarms: CF (channel A, MODE[12]) OR I_LEAK (channel B) -> isolator channel E. Both active high.",
    [
        U("U2", S_BL0939, "BL0939", {
            "1": "+3V3_HOT", "8": "L_BUS", "3": "H_IP1", "4": "H_IN1", "5": "H_IP2", "6": "H_IN2", "7": "H_VP",
            "2": "NC", "9": "+3V3_HOT", "10": "L_BUS", "11": "+3V3_HOT", "12": "L_BUS",
            "16": "L_BUS", "18": "H_BL_RX", "19": "H_BL_TX", "13": "H_ZX", "15": "H_ALM_A", "14": "H_ALM_B",
            "17": "NC", "20": "NC"}, "SSOP20", lcsc="C2841044", mfr="Belling", ver="plan"),
        C("C4", "100n", "+3V3_HOT", "L_BUS", **C100N),
        C("C5", "10u 25V", "+3V3_HOT", "L_BUS", **C10U_0805),
        R("R3", "1k", "H_S1P", "H_IP1", **R1K), R("R4", "1k", "H_S1N", "H_IN1", **R1K),
        C("C6", "33n C0G/X7R", "H_IP1", "L_BUS"), C("C7", "33n C0G/X7R", "H_IN1", "L_BUS"),
        R("R5", "1k", "H_S2P", "H_IP2", **R1K), R("R6", "1k", "H_S2N", "H_IN2", **R1K),
        C("C8", "33n C0G/X7R", "H_IP2", "L_BUS"), C("C9", "33n C0G/X7R", "H_IN2", "L_BUS"),
        R("R7", "390k 1% 1206", "N_F", "H_VD1", fp="R1206"),
        R("R8", "390k 1% 1206", "H_VD1", "H_VD2", fp="R1206"),
        R("R9", "390k 1% 1206", "H_VD2", "H_VD3", fp="R1206"),
        R("R10", "390k 1% 1206", "H_VD3", "H_VD4", fp="R1206"),
        R("R11", "390k 1% 1206", "H_VD4", "H_VDIV", fp="R1206"),
        R("R12", "470R 0.5%", "H_VDIV", "L_BUS"),
        R("R13", "1k", "H_VDIV", "H_VP", **R1K),
        C("C10", "33n C0G/X7R", "H_VP", "L_BUS"),
        R("R14", "10k", "H_BL_TX", "+3V3_HOT", note="TX/SDO needs an external pull-up", **R10K),
        U("U3", S_OR, "SN74LVC1G32DBVR", {"1": "H_ALM_A", "2": "H_ALM_B", "5": "+3V3_HOT", "3": "L_BUS", "4": "H_ALARM"},
          "SOT23-5", lcsc="C10096", mfr="TI", ver="yes"),
        C("C11", "100n", "+3V3_HOT", "L_BUS", **C100N),
    ])

polarity = Block(
    "5. Polarity and earth check (pulse-width ratio, S2 scheme F)",
    "Arm A: E -> 2 x 2M (HV) -> sense 47k -> L_BUS.  Arm B: E -> 2 x 2M (HV) + 47k -> N_F, so a missing earth floats to mid-supply.\n"
    "D3 (low leakage) passes the positive half-wave to R21; U4 compares it with 1.490 V (A) and 0.496 V (B). POL_A/POL_B are 50 Hz pulses.\n"
    "Firmware: duty d -> amplitude (TH/g + Vf)/cos(pi d), divided by the BL0939 mains peak, ratio to the unit's end-of-line k0:\n"
    "> 0.68 earthed and correct, 0.33-0.68 no earth (advisory, outlets empty only), < 0.33 swapped (outlets stay off). Run with relays open.\n"
    "Each arm must withstand a 6 kV impulse: VR37-class HV resistors.",
    [
        R("R15", "2M VR37 3.5kV", "E_IN", "H_PA1", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R16", "2M VR37 3.5kV", "H_PA1", "H_POL_S", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R17", "47k 1%", "H_POL_S", "L_BUS"),
        R("R18", "2M VR37 3.5kV", "E_IN", "H_PB1", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R19", "2M VR37 3.5kV", "H_PB1", "H_PB2", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R20", "47k 1%", "H_PB2", "N_F", note="Equal to R17 so a floating earth sits at mid-supply"),
        D(S_DZ, "D2", "BZT52C5V1", "H_POL_S", "L_BUS", "SOD123", note="Clamps the sense node in a surge"),
        Part("D3", S_D_SOT23, "BAS116", {"3": "H_POL_X", "1": "H_POL_S"}, FP["SOT23"], "C48502", "BAS116,215",
             "Nexperia", "Low leakage (5 nA max): keeps the negative half-wave off the comparator inputs", False, "yes"),
        R("R21", "470k", "H_POL_X", "L_BUS"),
        R("R22", "182k 1%", "+3V3_HOT", "H_TH_A"),
        R("R23", "100k 1%", "H_TH_A", "H_TH_B"),
        R("R24", "49.9k 1%", "H_TH_B", "L_BUS"),
        R("R31", "10k", "H_POL_X", "H_POL_INA", note="Input current limit", **R10K),
        R("R32", "10k", "H_POL_X", "H_POL_INB", note="Input current limit", **R10K),
        U("U4", S_LMV393, "LMV393IDR", {"3": "H_POL_INA", "2": "H_TH_A", "5": "H_POL_INB", "6": "H_TH_B",
                                        "8": "+3V3_HOT", "4": "L_BUS", "1": "H_POL_A", "7": "H_POL_B"},
          "SOIC8", lcsc="C7984", mfr="TI", ver="yes"),
        C("C13", "100n", "+3V3_HOT", "L_BUS", **C100N),
        R("R25", "10k", "H_POL_A", "+3V3_HOT", **R10K),
        R("R26", "10k", "H_POL_B", "+3V3_HOT", **R10K),
    ])

iso = Block(
    "6. Digital isolator (ISO7761DWR), straddles the 8 mm barrier",
    "Side 1 (hot): BL0939 TX, zero-cross, polarity A/B, alarm in; BL0939 RX out. Side 2 (safe): firmware nets.\n"
    "Routed slot under the package. Outputs default high if the other side is unpowered: a POL duty of 100 % means the hot side is down.",
    [
        U("U5", S_ISO, "ISO7761DWR", {
            "1": "+3V3_HOT", "8": "L_BUS", "2": "H_BL_TX", "3": "H_ZX", "4": "H_POL_A", "5": "H_POL_B",
            "6": "H_ALARM", "7": "H_BL_RX", "16": "+3V3_ISO", "9": "GND", "15": "MTR_RX", "14": "ZX",
            "13": "POL_A", "12": "POL_B", "11": "ALARM", "10": "MTR_TX"}, "SOIC16W", lcsc="C2871529", mfr="TI", ver="plan"),
        C("C14", "100n", "+3V3_HOT", "L_BUS", **C100N),
        C("C15", "1u", "+3V3_HOT", "L_BUS", **C1U),
        C("C16", "100n", "+3V3_ISO", "GND", **C100N),
        C("C17", "1u", "+3V3_ISO", "GND", **C1U),
    ])

ld03 = Block(
    "7. Safe-side 5 V supply (Mornsun LD03-23B05R2), straddles the barrier",
    "Genuine Mornsun only. 600 mA, derated to 480 mA at 85 C. Output TVS protects the safe side if the module fails.",
    [
        U("PS1", S_LD03, "LD03-23B05R2", {"2": "L_BUS", "1": "N_R", "5": "+5V", "4": "GND"}, "LD03",
          mfr="Mornsun", note="Buy from Mornsun distributors or DigiKey 2725-LD03-23B05R2-ND; not LCSC third-party"),
        C("C18", "1u 25V", "+5V", "GND", fp="C0805"),
        CP("C19", "150u 10V 105C", "+5V", "GND"),
        D(S_TVS, "D4", "SMBJ7.0A", "+5V", "GND", "SMB", lcsc="C669050", mpn="SMBJ7.0A-TP", mfr="MCC", ver="yes"),
    ])

relays = Block(
    "8. Outlet relays, coil on the safe side, contacts on the hot side",
    "Live-only switching (ADR-0002). 8 mm between coil and contact pins with a routed slot. Coil 5 V, 80 mA pull-in.",
    [
        U("K1", S_RELAY, "G5RL-1A-E DC5", {"1": "+5V", "8": "RLY1_COIL", "3": "H_K1", "4": "L_OUT1"}, "RELAY",
          lcsc="C397237", mfr="Omron", ver="plan", note="Second source Hongfa HF115F/005-1HS3AF (C882368); footprint holes widened for its 2.52 mm grid"),
        U("K2", S_RELAY, "G5RL-1A-E DC5", {"1": "+5V", "8": "RLY2_COIL", "3": "H_K2", "4": "L_OUT2"}, "RELAY",
          lcsc="C397237", mfr="Omron", ver="plan"),
    ])

drivers = Block(
    "9. Relay drivers",
    "LEDC PWM at 20 kHz: 100% for 50 ms, then the holding duty. 100k keeps the coil off while the ESP32 boots.",
    [
        U("Q1", S_NFET, "AO3400A", {"1": "RLY1_G", "3": "RLY1_COIL", "2": "GND"}, "SOT23", lcsc="C20917", mfr="AOS"),
        R("R27", "100R", "RELAY1", "RLY1_G", **R100),
        R("R28", "100k", "RLY1_G", "GND", **R100K),
        D(S_DS, "D5", "SS14", "+5V", "RLY1_COIL", "SMA", lcsc="C2480", note="Freewheel; carries coil current during PWM"),
        U("Q2", S_NFET, "AO3400A", {"1": "RLY2_G", "3": "RLY2_COIL", "2": "GND"}, "SOT23", lcsc="C20917", mfr="AOS"),
        R("R29", "100R", "RELAY2", "RLY2_G", **R100),
        R("R30", "100k", "RLY2_G", "GND", **R100K),
        D(S_DS, "D6", "SS14", "+5V", "RLY2_COIL", "SMA", lcsc="C2480"),
    ])

safe_misc = Block(
    "10. Isolator 3.3 V, relay NTCs, board-to-board header",
    "XC6206 feeds only the isolator's safe side (keeps 3.3 V logic levels to the ESP32). NTCs are pressed against each relay body;\n"
    "their 10k pull-ups sit on the front board next to the ADC.",
    [
        U("U6", S_XC6206, "XC6206P332MR", {"3": "+5V", "2": "+3V3_ISO", "1": "GND"}, "SOT23", lcsc="C5446", mfr="Torex"),
        C("C20", "1u", "+5V", "GND", **C1U),
        C("C21", "1u", "+3V3_ISO", "GND", **C1U),
        Part("TH1", S_NTC, "10k B3950 1%", {"1": "NTC1", "2": "GND"}, FP["R0603"], "", "", "", "Against relay K1"),
        Part("TH2", S_NTC, "10k B3950 1%", {"1": "NTC2", "2": "GND"}, FP["R0603"], "", "", "", "Against relay K2"),
        U("J4", S_HDR, "B2B header 2x7 1.27mm", dict(HDR_CONN), "HDR2x7"),
        C("C22", "10u 25V", "+5V", "GND", **C10U_0805),
    ])

REAR = Project(
    name="sws-rear", title="Smart Wall Socket EVT1, rear board",
    warning="Hot side is referenced to LIVE (L_BUS). Treat every hot-side net as mains.",
    sheets=[
        Sheet("Hot side", "", "Mains referenced. Hot-side ground = L_BUS = LIVE.",
              [mains, feed, hotsup], flags=["L_BUS", "+5V_HOT"], tint=True),
        Sheet("Hot side, sensing", "", "Metering and wiring checks, all mains referenced.", [meter, polarity], tint=True),
        Sheet("Barrier crossing", "", "The only parts that bridge the barrier.", [iso, ld03, relays]),
        Sheet("Safe zone", "", "SELV.", [drivers, safe_misc]),
    ],
    rails={"L_BUS": "hot", "GND": "gnd", "+3V3_HOT": "rail", "+5V_HOT": "rail", "+3V3_ISO": "rail", "+5V": "rail"},
    barrier_after=1,
    root_notes=(
        "REAR BOARD, EVT1 DRAFT FOR REVIEW\n"
        "2 layers, 2 oz. One reinforced barrier: 8.0 mm creepage and clearance, crossed only by U5, PS1, K1, K2.\n"
        "Net classes: MAINS = L_BUS, N_IN, E_IN, N_F, N_R, L_OUT1/2 and every H_* net.  SAFE = everything else.\n"
        "MAINS to SAFE >= 8.0 mm; MAINS to E_IN >= 3.0 mm; L to N >= 3.0 mm with slots where traces converge.\n"
        "Outlet paths sized for 20 A combined (IPC-2152). No connector on the hot side.\n"
        "Bench rule: never power this board from the mains without an isolation transformer and an RCD."),
)

# ==========================================================================
# FRONT BOARD
# ==========================================================================
front_pwr = Block(
    "1. Board-to-board socket and 3.3 V buck",
    "TLV62569: Vout = 0.6 V x (1 + 453k/100k) = 3.32 V. PFM at light load keeps standby low.",
    [
        U("J101", S_HDR, "B2B socket 2x7 1.27mm", dict(HDR_CONN), "SKT2x7"),
        C("C101", "22u 10V", "+5V", "GND", **C22U_0805),
        U("U101", S_TLV, "TLV62569DBVR", {"4": "+5V", "1": "+5V", "3": "BUCK_SW", "5": "BUCK_FB", "2": "GND"},
          "SOT23-5", lcsc="C141836", mfr="TI", ver="yes"),
        C("C102", "10u 10V", "+5V", "GND", **C10U_0805),
        Part("L101", S_L, "2.2uH 2A shielded", {"1": "BUCK_SW", "2": "+3V3"}, FP["L4018"], "", "", "",
             "Isat >= 2.5 A, DCR <= 60 mOhm"),
        R("R101", "453k 1%", "+3V3", "BUCK_FB"),
        R("R102", "100k 1%", "BUCK_FB", "GND", **R100K),
        C("C103", "22p", "+3V3", "BUCK_FB", lcsc="C1653", dnp=True, note="Feed-forward, fit only if needed"),
        C("C104", "22u 10V", "+3V3", "GND", **C22U_0805),
        C("C105", "22u 10V", "+3V3", "GND", **C22U_0805),
    ])

front_mcu = Block(
    "2. ESP32-C6-MINI-1-H4",
    "Antenna at the faceplate rim, outside the steel box; keep-out per Espressif. Strapping: IO9 pulled up (SPI boot), IO8 pulled up.\n"
    "ADC1: IO0 = NTC1, IO1 = NTC2. UART1: IO20 RX / IO21 TX to the BL0939. LEDC: IO18/IO19 relays. RMT: IO8 light lines.",
    [
        U("U102", S_ESP, "ESP32-C6-MINI-1-H4", {
            "3": "+3V3", "1": "GND", "8": "EN", "12": "NTC1", "13": "NTC2", "5": "ALARM", "6": "ZX",
            "9": "NFC_SDA", "10": "NFC_SCL", "15": "TOUCH1", "16": "TOUCH2", "22": "LED_DIN",
            "23": "BOOT", "17": "USB_DN", "18": "USB_DP", "19": "NFC_FD", "20": "LED_PWR_EN",
            "24": "RELAY1", "25": "RELAY2", "26": "MTR_RX", "27": "MTR_TX", "28": "POL_A", "29": "POL_B",
            "30": "U0RXD", "31": "U0TXD"}, "ESP", lcsc="C6553337", mfr="Espressif", ver="plan"),
        C("C106", "10u 10V", "+3V3", "GND", **C10U_0805),
        C("C107", "100n", "+3V3", "GND", **C100N),
        R("R103", "10k", "+3V3", "EN", **R10K),
        C("C108", "1u", "EN", "GND", note="EN RC per Espressif (10k, 1uF)", **C1U),
        R("R104", "10k", "+3V3", "BOOT", **R10K),
        R("R105", "10k", "+3V3", "LED_DIN", note="IO8 strap high", **R10K),
        R("R106", "10k 0.1%", "+3V3", "NTC1"),
        R("R107", "10k 0.1%", "+3V3", "NTC2"),
        C("C109", "100n", "NTC1", "GND", **C100N),
        C("C110", "100n", "NTC2", "GND", **C100N),
    ])

front_tp = Block(
    "3. Programming and test pads",
    "USB-Serial-JTAG on IO12/IO13 for flashing and logs; UART0 as fallback. Hold BOOT low at reset for download mode.",
    [
        Part("TP101", S_TP, "+5V", {"1": "+5V"}, FP["TP"]),
        Part("TP102", S_TP, "+3V3", {"1": "+3V3"}, FP["TP"]),
        Part("TP103", S_TP, "GND", {"1": "GND"}, FP["TP"]),
        Part("TP104", S_TP, "EN", {"1": "EN"}, FP["TP"]),
        Part("TP105", S_TP, "BOOT", {"1": "BOOT"}, FP["TP"]),
        Part("TP106", S_TP, "U0TXD", {"1": "U0TXD"}, FP["TP"]),
        Part("TP107", S_TP, "U0RXD", {"1": "U0RXD"}, FP["TP"]),
        Part("TP108", S_TP, "USB_D+", {"1": "USB_DP"}, FP["TP"]),
        Part("TP109", S_TP, "USB_D-", {"1": "USB_DN"}, FP["TP"]),
    ])

touch = Block(
    "4. Touch keys (AT42QT1011), one per outlet",
    "Cs 10 nF and Rs 4.7k are starting values; tune on the EVT faceplate. OUT is active high: board_evt_c6 sets touch polarity.\n"
    "SYNC/MODE strapped high by a 0R: Fast mode (~1 ms between bursts). Low-power mode (strap low) sleeps ~80 ms per burst and feels slow.",
    [
        U("U103", S_QT, "AT42QT1011-TSHR", {"4": "TS1_S", "3": "TS1_K", "5": "+3V3", "2": "GND", "1": "TOUCH1", "6": "TS1_MODE"},
          "SOT23-6", lcsc="C112956", mfr="Microchip", ver="yes"),
        C("C111", "10n C0G", "TS1_K", "TS1_S", note="Cs, tune at EVT"),
        R("R108", "4.7k", "TS1_K", "TS1_E", **R4K7),
        Part("E101", S_E, "Touch key 1", {"1": "TS1_E"}, FP["TOUCH"]),
        R("R109", "0R", "TS1_MODE", "GND", dnp=True, **R0),
        R("R110", "0R", "TS1_MODE", "+3V3", **R0),
        C("C112", "100n", "+3V3", "GND", **C100N),
        U("U104", S_QT, "AT42QT1011-TSHR", {"4": "TS2_S", "3": "TS2_K", "5": "+3V3", "2": "GND", "1": "TOUCH2", "6": "TS2_MODE"},
          "SOT23-6", lcsc="C112956", mfr="Microchip", ver="yes"),
        C("C113", "10n C0G", "TS2_K", "TS2_S", note="Cs, tune at EVT"),
        R("R111", "4.7k", "TS2_K", "TS2_E", **R4K7),
        Part("E102", S_E, "Touch key 2", {"1": "TS2_E"}, FP["TOUCH"]),
        R("R112", "0R", "TS2_MODE", "GND", dnp=True, **R0),
        R("R113", "0R", "TS2_MODE", "+3V3", **R0),
        C("C114", "100n", "+3V3", "GND", **C100N),
    ])

nfc = Block(
    "5. NFC tag (NT3H2111)",
    "Field-powered: a phone can read the setup record with the socket unpowered. Antenna tuned to 13.56 MHz with C115 at EVT.",
    [
        U("U105", S_NFC, "NT3H2111W0FTTJ", {"1": "NFC_LA", "8": "NFC_LB", "6": "+3V3", "2": "GND", "3": "NFC_SCL",
                                            "5": "NFC_SDA", "4": "NFC_FD", "7": "NC"},
          "TSSOP8", lcsc="C2654884", mfr="NXP", ver="yes", note="Pinout checked against NXP NT3H2111_2211 datasheet (TSSOP8)"),
        Part("ANT101", S_ANT, "PCB loop antenna", {"1": "NFC_LA", "2": "NFC_LB"}, FP["NFCANT"]),
        C("C115", "TBD C0G", "NFC_LA", "NFC_LB", dnp=True, note="Tuning, value from antenna measurement"),
        R("R114", "4.7k", "+3V3", "NFC_SDA", **R4K7),
        R("R115", "4.7k", "+3V3", "NFC_SCL", **R4K7),
        R("R116", "10k", "+3V3", "NFC_FD", **R10K),
        C("C116", "100n", "+3V3", "GND", **C100N),
    ])

leds = Block(
    "6. Light lines (4 x SK6812MINI-E, two per outlet)",
    "LED power is switched off in standby (Q101); the buffer runs from the switched rail so nothing back-feeds the LEDs.\n"
    "74AHCT inputs tolerate 3.3 V with VCC off. Data: IO8 -> buffer -> 33R -> D101 -> D102 -> D103 -> D104.",
    [
        U("U106", S_BUF, "SN74AHCT1G125DBVR", {"2": "LED_DIN", "1": "GND", "5": "LED_5V", "3": "GND", "4": "LED_DBUF"},
          "SOT23-5", lcsc="C7484", mfr="TI", ver="yes"),
        C("C117", "100n", "LED_5V", "GND", **C100N),
        R("R117", "33R", "LED_DBUF", "LED_D0"),
        U("Q101", S_PFET, "AO3401A", {"1": "LED_PG", "2": "+5V", "3": "LED_5V"}, "SOT23", lcsc="C15127", mfr="AOS"),
        R("R118", "100k", "+5V", "LED_PG", **R100K),
        U("Q102", S_NFET, "2N7002", {"1": "LED_PWR_EN", "3": "LED_PG", "2": "GND"}, "SOT23", lcsc="C8545"),
        R("R119", "100k", "LED_PWR_EN", "GND", **R100K),
        C("C118", "10u 10V", "LED_5V", "GND", **C10U_0805),
        U("D101", S_SK, "SK6812MINI-E", {"4": "LED_D0", "1": "LED_5V", "3": "GND", "2": "LED_D1"}, "SK6812E",
          lcsc="C5149201", mfr="OPSCO", ver="yes", note="Outlet 1 line"),
        U("D102", S_SK, "SK6812MINI-E", {"4": "LED_D1", "1": "LED_5V", "3": "GND", "2": "LED_D2"}, "SK6812E",
          lcsc="C5149201", mfr="OPSCO", ver="yes", note="Outlet 1 line"),
        U("D103", S_SK, "SK6812MINI-E", {"4": "LED_D2", "1": "LED_5V", "3": "GND", "2": "LED_D3"}, "SK6812E",
          lcsc="C5149201", mfr="OPSCO", ver="yes", note="Outlet 2 line"),
        U("D104", S_SK, "SK6812MINI-E", {"4": "LED_D3", "1": "LED_5V", "3": "GND", "2": "NC"}, "SK6812E",
          lcsc="C5149201", mfr="OPSCO", ver="yes", note="Outlet 2 line"),
        C("C119", "100n", "LED_5V", "GND", **C100N),
        C("C120", "100n", "LED_5V", "GND", **C100N),
        C("C121", "100n", "LED_5V", "GND", **C100N),
        C("C122", "100n", "LED_5V", "GND", **C100N),
    ])

FRONT = Project(
    name="sws-front", title="Smart Wall Socket EVT1, front board",
    warning="SELV only. Connects to the rear board's safe zone through J101.",
    sheets=[
        Sheet("Power and processor", "", "3.3 V buck, ESP32-C6, programming pads.",
              [front_pwr, front_mcu, front_tp], flags=["+5V", "GND", "+3V3"]),
        Sheet("User interface", "", "Touch keys, NFC tag, light lines.", [touch, nfc, leds], flags=["LED_5V"]),
    ],
    rails={"GND": "gnd", "+5V": "rail", "+3V3": "rail", "LED_5V": "rail"},
    root_notes=(
        "FRONT BOARD, EVT1 DRAFT FOR REVIEW\n"
        "Entirely SELV. 4 layers for the ESP32's RF ground; antenna keep-out at the board edge under the faceplate rim.\n"
        "Connects to the rear board's safe zone only, through J101 (2 x 7, 1.27 mm)."),
)

PROJECTS = [REAR, FRONT]

# GPIO map for the firmware's board_evt_c6.c (checked against the netlist by verify.py)
GPIO_MAP = {
    "NTC1": 0, "NTC2": 1, "ALARM": 2, "ZX": 3, "NFC_SDA": 4, "NFC_SCL": 5, "TOUCH1": 6, "TOUCH2": 7,
    "LED_DIN": 8, "BOOT": 9, "USB_DN": 12, "USB_DP": 13, "NFC_FD": 14, "LED_PWR_EN": 15,
    "RELAY1": 18, "RELAY2": 19, "MTR_RX": 20, "MTR_TX": 21, "POL_A": 22, "POL_B": 23,
}
ESP_PAD_TO_GPIO = {"12": 0, "13": 1, "5": 2, "6": 3, "9": 4, "10": 5, "15": 6, "16": 7, "22": 8, "23": 9,
                   "17": 12, "18": 13, "19": 14, "20": 15, "24": 18, "25": 19, "26": 20, "27": 21,
                   "28": 22, "29": 23}


# --------------------------------------------------------------------------
# Part numbers assigned 10 Nov 2026 (R7). Each LCSC/JLC page was checked that day.
# ref: (lcsc, mpn, mfr, new value or None, new footprint key or None, ver)
# ver "yes" = LCSC page checked; "src:..." = sourced elsewhere or not a bought part.
# --------------------------------------------------------------------------
ASSIGN = {
    # rear, hot side
    "RS1": ("C4175647", "CSS2H-2512R-1L00F", "Bourns", "1m 1% 5W metal element", None, "yes"),
    "RS2": ("C4175647", "CSS2H-2512R-1L00F", "Bourns", "1m 1% 5W metal element", None, "yes"),
    "RV1": ("C3263770", "MOV-10D561K", "Bourns", "MOV 561K 10mm", None,
            "src:EVT uses plain MOV; thermally protected 10 mm type (Littelfuse TMOV / SETsafe SFV) to source for DVT"),
    "R1":  ("", "KNP3W-12R-5%", "CCO", None, None, "src:LCSC number to pick at order (KNP3W 12R)"),
    "R2":  ("", "FW20A47R0JA", "Bourns", "47R 2W fusible wirewound", None, "src:DigiKey/Mouser; certified fusible, no LCSC equivalent"),
    "C1":  ("C22391567", "LKGD1402W4R7MF", "Ymin", "4.7u 450V 105C 12000h", None, "yes"),
    "C23": ("C22391567", "LKGD1402W4R7MF", "Ymin", "4.7u 450V 105C 12000h", None, "yes"),
    "L1":  ("C72626", "VLU0810-102K", "FH", "1mH 0.36A", None, "yes"),
    "L2":  ("C72626", "VLU0810-102K", "FH", "1mH 0.36A", None, "yes"),
    "U1":  ("", "LNK3204D-TL", "Power Integrations", None, None, "src:DigiKey 596-LNK3204D-TLCT-ND (not on LCSC)"),
    "D9":  ("C412438", "ES1J", "MDD", None, None, "yes"),
    "R35": ("C843947", "CRCW06033K09FKEA", "Vishay", None, None, "yes"),
    "R36": ("C407609", "0603WAD2491T5E", "UNI-ROYAL", "2.49k 0.5%", None, "yes"),
    "C26": ("C128532", "EEE-FK1C101P", "Panasonic", "100u 16V 105C", "CP6358", "yes"),
    "R37": ("", "", "", None, None, "src:DNP"),
    "C6":  ("C21117", "CL10B333KB8NNNC", "Samsung", "33n X7R", None, "yes"),
    "C7":  ("C21117", "CL10B333KB8NNNC", "Samsung", "33n X7R", None, "yes"),
    "C8":  ("C21117", "CL10B333KB8NNNC", "Samsung", "33n X7R", None, "yes"),
    "C9":  ("C21117", "CL10B333KB8NNNC", "Samsung", "33n X7R", None, "yes"),
    "C10": ("C21117", "CL10B333KB8NNNC", "Samsung", "33n X7R", None, "yes"),
    "R7":  ("C307946", "KTR18EZPF3903", "ROHM", "390k 1% 1206 500V", None, "yes"),
    "R8":  ("C307946", "KTR18EZPF3903", "ROHM", "390k 1% 1206 500V", None, "yes"),
    "R9":  ("C307946", "KTR18EZPF3903", "ROHM", "390k 1% 1206 500V", None, "yes"),
    "R10": ("C307946", "KTR18EZPF3903", "ROHM", "390k 1% 1206 500V", None, "yes"),
    "R11": ("C307946", "KTR18EZPF3903", "ROHM", "390k 1% 1206 500V", None, "yes"),
    "R12": ("C23179", "0603WAF4700T5E", "UNI-ROYAL", "470R 1%", None, "yes"),
    "R15": ("", "VR37000002004FA100", "Vishay", None, None, "src:DigiKey/Mouser (VR37 not on LCSC)"),
    "R16": ("", "VR37000002004FA100", "Vishay", None, None, "src:DigiKey/Mouser (VR37 not on LCSC)"),
    "R18": ("", "VR37000002004FA100", "Vishay", None, None, "src:DigiKey/Mouser (VR37 not on LCSC)"),
    "R19": ("", "VR37000002004FA100", "Vishay", None, None, "src:DigiKey/Mouser (VR37 not on LCSC)"),
    "R17": ("C25819", "0603WAF4702T5E", "UNI-ROYAL", None, None, "yes"),
    "R20": ("C25819", "0603WAF4702T5E", "UNI-ROYAL", None, None, "yes"),
    "D2":  ("C2117", "BZT52C5V1", "CJ", None, None, "yes"),
    "R21": ("C23178", "0603WAF4703T5E", "UNI-ROYAL", "470k 1%", None, "yes"),
    "R22": ("C22894", "0603WAF1823T5E", "UNI-ROYAL", None, None, "yes"),
    "R23": ("C25803", "0603WAF1003T5E", "UNI-ROYAL", None, None, ""),
    "R24": ("C23184", "0603WAF4992T5E", "UNI-ROYAL", None, None, "yes"),
    "PS1": ("", "LD03-23B05R2", "Mornsun", None, None, "src:Mornsun distributor or DigiKey 2725-LD03-23B05R2-ND (D4)"),
    "F1":  ("", "3403.0274.23", "Schurter", None, None, "src:Schurter distributor"),
    "C18": ("C116352", "CL21B105KAFNNNE", "Samsung", None, None, "yes"),
    "C19": ("C264054", "EEE-FK1A151P", "Panasonic", "150u 10V 105C low ESR", "CP6358", "yes"),
    "TH1": ("C47118797", "CMFA103F3950HANT", "FH", None, None, "yes"),
    "TH2": ("C47118797", "CMFA103F3950HANT", "FH", None, None, "yes"),
    "J4":  ("C3975190", "PZ127-2-07-S", "HCTL", None, None, "yes"),
    "J1":  ("", "", "", None, None, "src:mechanical, chosen with the enclosure"),
    "J2":  ("", "", "", None, None, "src:mechanical, chosen with the enclosure"),
    "J3":  ("", "", "", None, None, "src:mechanical, chosen with the enclosure"),
    "TF1": ("", "", "", None, None, "src:mechanical, chosen with the enclosure"),
    "TF2": ("", "", "", None, None, "src:mechanical, chosen with the enclosure"),
    # front
    "J101": ("C3975133", "PM127-2-07-S-4.3", "HCTL", None, None, "yes"),
    "L101": ("C340367", "YNR4018-2R2M", "YJYCOIN", "2.2uH 1.65A 45mR shielded", None, "yes"),
    "R101": ("C667826", "TD03G4533FT", "FH", None, None, "yes"),
    "R106": ("C328421", "PTFR0603B10K0P9", "RESI", None, None, "yes"),
    "R107": ("C328421", "PTFR0603B10K0P9", "RESI", None, None, "yes"),
    "C111": ("C76599", "C1608C0G1H103JT000N", "TDK", None, None, "yes"),
    "C113": ("C76599", "C1608C0G1H103JT000N", "TDK", None, None, "yes"),
    "R117": ("C23140", "0603WAF330JT5E", "UNI-ROYAL", None, None, "yes"),
    "C115": ("", "", "", None, None, "src:DNP, value from antenna tuning"),
}
for _ref in [f"TP10{i}" for i in range(1, 10)] + ["E101", "E102", "ANT101"]:
    ASSIGN[_ref] = ("", "", "", None, None, "src:PCB feature, not a bought part")


def _apply_assignments():
    seen = set()
    for proj in (REAR, FRONT):
        for sh in proj.sheets:
            for b in sh.blocks:
                for p in b.parts:
                    a = ASSIGN.get(p.ref)
                    if not a:
                        continue
                    lcsc, mpn, mfr, val, fp, ver = a
                    p.lcsc = lcsc or p.lcsc
                    p.mpn, p.mfr = mpn or p.mpn, mfr or p.mfr
                    if val:
                        p.value = val
                    if fp:
                        p.footprint = FP[fp]
                    p.verified = ver
                    seen.add(p.ref)
    missing = set(ASSIGN) - seen
    assert not missing, f"ASSIGN refs not in design: {sorted(missing)}"


_apply_assignments()
