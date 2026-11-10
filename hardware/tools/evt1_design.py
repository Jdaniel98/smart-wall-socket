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
    "TR5": "Fuse:Fuse_Littelfuse_395Series",
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
S_DZ = two_pin("D_Zener", "DZ", "D", desc="Zener diode, pin 1 = K, pin 2 = A")
S_TVS = two_pin("D_TVS_Uni", "TVS", "D", desc="Unidirectional TVS, pin 1 = K, pin 2 = A")
S_F = two_pin("Fuse", "F", "F", desc="Fuse")
S_RV = two_pin("Varistor", "RV", "RV", desc="Metal-oxide varistor")
S_NTC = two_pin("Thermistor_NTC", "NTC", "TH", desc="NTC thermistor")
S_TCO = two_pin("Thermal_Cutoff", "TCO", "TF", desc="Non-resettable thermal cut-off")
S_SH = two_pin("R_Shunt", "SH", "RS", desc="Current shunt; Kelvin taps are drawn in layout")
S_ANT = two_pin("NFC_Antenna", "L", "ANT", desc="PCB loop antenna")
S_E = one_pin("TouchPad", "E", desc="Capacitive touch electrode")
S_TP = one_pin("TestPad", "TP", desc="Test pad")

S_BL0939 = box("BL0939", [
    ("3", "IP1", "input"), ("4", "IN1", "input"), ("5", "IP2", "input"), ("6", "IN2", "input"),
    ("7", "VP", "input"), ("2", "VT", "input"),
    ("9", "A1", "input"), ("10", "A2", "input"), ("11", "A3", "input"), ("12", "A4", "input"),
], [
    ("1", "VDD", "power_in"), ("8", "GND", "power_in"), ("16", "SEL", "input"),
    ("18", "RX/SDI", "input"), ("19", "TX/SDO", "output"), ("13", "ZX", "output"),
    ("15", "CF", "output"), ("14", "I_LEAK", "output"), ("17", "SCLK", "input"), ("20", "VPP", "passive"),
], desc="Belling BL0939, 2-channel metering, SSOP-20")

S_KP3310 = box("KP3310SGA", [
    ("5,6,7,8", "DRAIN", "passive"), ("4", "VDD", "passive"), ("1", "SEL", "input"),
], [
    ("3", "VOUT", "power_out"), ("2", "GND", "power_in"),
], desc="Kiwi KP3310, non-isolated HV linear regulator, SOP-8")

S_LMV393 = box("LMV393", [
    ("3", "+INA", "input"), ("2", "-INA", "input"), ("5", "+INB", "input"), ("6", "-INB", "input"),
], [
    ("8", "V+", "power_in"), ("4", "GND", "power_in"), ("1", "OUTA", "open_collector"), ("7", "OUTB", "open_collector"),
], desc="Dual comparator, open-drain, SOIC-8")

S_OR = box("74LVC1G32", [("1", "A", "input"), ("2", "B", "input")],
           [("5", "VCC", "power_in"), ("3", "GND", "power_in"), ("4", "Y", "output")],
           desc="Single 2-input OR, SOT-23-5")

S_ISO = box("ISO7761DW", [
    ("1", "VCC1", "power_in"), ("8", "GND1", "power_in"), ("2", "INA", "input"), ("3", "INB", "input"),
    ("4", "INC", "input"), ("5", "IND", "input"), ("6", "INE", "input"), ("7", "OUTF", "output"),
], [
    ("16", "VCC2", "power_in"), ("9", "GND2", "power_in"), ("15", "OUTA", "output"), ("14", "OUTB", "output"),
    ("13", "OUTC", "output"), ("12", "OUTD", "output"), ("11", "OUTE", "output"), ("10", "INF", "input"),
], desc="TI ISO7761 6-ch reinforced digital isolator, 5 fwd / 1 rev, SOIC-16 wide. Side 1 = hot.")

S_LD03 = box("LD03-23B05R2", [("2", "AC(L)", "passive"), ("1", "AC(N)", "passive")],
             [("5", "+Vo", "power_out"), ("4", "-Vo", "power_out")],
             desc="Mornsun 3 W AC-DC module, 5 V / 600 mA, 4 kVAC reinforced")

S_RELAY = box("Relay_SPST_NO", [("1", "A1", "passive"), ("2", "A2", "passive")],
              [("3", "COM", "passive"), ("4", "NO", "passive")], ref="K",
              desc="16 A SPST-NO power relay. Pin numbers are placeholders until the footprint is drawn.")

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
    ("3", "3V3", "power_in"), (GND_PINS, "GND", "power_in"), ("8", "EN", "input"),
    ("12", "IO0", "bidirectional"), ("13", "IO1", "bidirectional"), ("5", "IO2", "bidirectional"),
    ("6", "IO3", "bidirectional"), ("9", "IO4", "bidirectional"), ("10", "IO5", "bidirectional"),
    ("15", "IO6", "bidirectional"), ("16", "IO7", "bidirectional"), ("22", "IO8", "bidirectional"),
], [
    ("23", "IO9", "bidirectional"), ("17", "IO12/USB_D-", "bidirectional"), ("18", "IO13/USB_D+", "bidirectional"),
    ("19", "IO14", "bidirectional"), ("20", "IO15", "bidirectional"), ("24", "IO18", "bidirectional"),
    ("25", "IO19", "bidirectional"), ("26", "IO20", "bidirectional"), ("27", "IO21", "bidirectional"),
    ("28", "IO22", "bidirectional"), ("29", "IO23", "bidirectional"), ("30", "RXD0", "bidirectional"),
    ("31", "TXD0", "bidirectional"), (NC_PINS, "NC", "no_connect"),
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
    "Shunt common end = L_BUS = hot-side ground. Route IP/IN as Kelvin taps from the shunt pads.\n"
    "Thermal cut-offs: non-resettable, clamped to the outlet feed near the contacts; Tf chosen after the EVT thermal test.",
    [
        U("J1", S_TERM, "Mains terminal L/N/E", {"1": "L_BUS", "2": "N_IN", "3": "E_IN"}, "TERM",
          note="Screw terminals for 3 x 2.5 mm2 ring conductors; part chosen with the mechanism"),
        Part("RS1", S_SH, "1m 2512 >=2W manganin", {"1": "L_BUS", "2": "H_I1"}, FP["R2512"], "", "", "",
             "Outlet 1 shunt; 0.256 W at 16 A"),
        Part("RS2", S_SH, "1m 2512 >=2W manganin", {"1": "L_BUS", "2": "H_I2"}, FP["R2512"], "", "", "",
             "Outlet 2 shunt"),
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
    "Open item: the MOV clamp (~925 V at 25 A for 561K) exceeds the KP3310 drain rating (650 V). See review notes R1.",
    [
        Part("F1", S_F, "1A 300V T, TR5", {"1": "N_IN", "2": "N_F"}, FP["TR5"], "", "", "",
             "Slow-blow, 300 V AC rated; Littelfuse 392/395 series or equivalent"),
        Part("RV1", S_RV, "MOV 561K 10mm, thermally protected", {"1": "L_BUS", "2": "N_F"}, FP["MOV10"], "", "",
             "", "e.g. Littelfuse TMOV/ Bourns TMOV-type; 350 VAC"),
        R("R1", "12R 3W wirewound", "N_F", "N_R", fp="R0617", note="Inrush limit for LD03; fusible type"),
    ])

hotsup = Block(
    "3. Hot-side 3.3 V supply (KP3310SGA)",
    "Half-wave from N_F; KP3310 charges VDD (7.8 V) while the line is low, then an LDO makes 3.3 V. SEL open = 3.3 V.\n"
    "Hold-up: 15 mA (worst case) x 20 ms / 220 uF = 1.4 V droop on VDD (7.8 V to 6.4 V), so VOUT stays in regulation.",
    [
        R("R2", "100R 1W flameproof", "N_F", "H_KP_A", fp="R0207", note="Surge/fault limiter for the KP3310 feed"),
        D(S_D, "D1", "M7 1000V 1A", "H_KP_D", "H_KP_A", "SMA", lcsc="C95872", mpn="M7"),
        U("U1", S_KP3310, "KP3310SGA", {"5": "H_KP_D", "4": "H_KP_VDD", "1": "NC", "3": "+3V3_HOT", "2": "L_BUS"},
          "SOIC8", lcsc="C310447", mfr="Kiwi Instruments", ver="plan", note="SEL floating selects 3.3 V"),
        CP("C1", "220u 16V 105C", "H_KP_VDD", "L_BUS", note="VDD energy store (VDD abs max 9 V)"),
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
        R("R3", "1k", "H_I1", "H_IP1", **R1K), R("R4", "1k", "L_BUS", "H_IN1", **R1K),
        C("C6", "33n C0G/X7R", "H_IP1", "L_BUS"), C("C7", "33n C0G/X7R", "H_IN1", "L_BUS"),
        R("R5", "1k", "H_I2", "H_IP2", **R1K), R("R6", "1k", "L_BUS", "H_IN2", **R1K),
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
    "5. Polarity and earth check",
    "Arm A: E -> 2 x 2M (HV) -> sense 20k -> L_BUS.  Arm B: E -> 2 x 2M (HV) + 20k -> N_F, so a missing earth floats to mid-supply.\n"
    "Peak detector BAT54WS + 1u // 1M (tau 1 s); thresholds 1.02 V (bit A) and 0.31 V (bit B) from a 220k/68k/30k ladder.\n"
    "Correct: A=1 B=1.  Swapped L/N: A=0 B=0.  No earth: A=0 B=1.  Each arm must withstand a 6 kV impulse: VR37-class HV resistors.",
    [
        R("R15", "2M VR37 3.5kV", "E_IN", "H_PA1", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R16", "2M VR37 3.5kV", "H_PA1", "H_POL_S", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R17", "20k 1%", "H_POL_S", "L_BUS", **R20K),
        R("R18", "2M VR37 3.5kV", "E_IN", "H_PB1", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R19", "2M VR37 3.5kV", "H_PB1", "H_PB2", fp="R0411", mpn="VR37000002004FA100", mfr="Vishay"),
        R("R20", "20k 1%", "H_PB2", "N_F", **R20K),
        D(S_DZ, "D2", "BZT52C5V1", "H_POL_S", "L_BUS", "SOD123", note="Clamps the sense node in a surge"),
        D(S_DS, "D3", "BAT54WS", "H_POL_PK", "H_POL_S", "SOD323", lcsc="C5251553", mfr="MDD", ver="yes"),
        C("C12", "1u", "H_POL_PK", "L_BUS", **C1U),
        R("R21", "1M", "H_POL_PK", "L_BUS", **R1M),
        R("R22", "220k 1%", "+3V3_HOT", "H_TH_A"),
        R("R23", "68k 1%", "H_TH_A", "H_TH_B"),
        R("R24", "30k 1%", "H_TH_B", "L_BUS"),
        R("R31", "10k", "H_POL_PK", "H_POL_IN", note="Limits comparator input current when D2 clamps at 5.1 V", **R10K),
        U("U4", S_LMV393, "LMV393IDR", {"3": "H_POL_IN", "2": "H_TH_A", "5": "H_POL_IN", "6": "H_TH_B",
                                        "8": "+3V3_HOT", "4": "L_BUS", "1": "H_POL_A", "7": "H_POL_B"},
          "SOIC8", lcsc="C7984", mfr="TI", ver="yes"),
        C("C13", "100n", "+3V3_HOT", "L_BUS", **C100N),
        R("R25", "10k", "H_POL_A", "+3V3_HOT", **R10K),
        R("R26", "10k", "H_POL_B", "+3V3_HOT", **R10K),
    ])

iso = Block(
    "6. Digital isolator (ISO7761DWR), straddles the 8 mm barrier",
    "Side 1 (hot): BL0939 TX, zero-cross, polarity A/B, alarm in; BL0939 RX out. Side 2 (safe): firmware nets.\n"
    "Routed slot under the package. Outputs default high if the other side is unpowered: firmware reads POL_x only while the meter is alive.",
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
        U("K1", S_RELAY, "G5RL-1A-E DC5", {"1": "+5V", "2": "RLY1_COIL", "3": "H_K1", "4": "L_OUT1"}, "RELAY",
          lcsc="C397237", mfr="Omron", ver="plan", note="Second source Hongfa HF115F/005-1HS3AF (C882368), pin map to confirm"),
        U("K2", S_RELAY, "G5RL-1A-E DC5", {"1": "+5V", "2": "RLY2_COIL", "3": "H_K2", "4": "L_OUT2"}, "RELAY",
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
        Sheet("Hot side", "hot_side.kicad_sch", "Rear board: hot side (mains referenced)",
              [mains, feed, hotsup, meter, polarity], flags=["L_BUS"]),
        Sheet("Barrier crossing", "crossing.kicad_sch", "Rear board: parts that bridge the reinforced barrier",
              [iso, ld03, relays]),
        Sheet("Safe zone", "safe_zone.kicad_sch", "Rear board: safe zone (SELV)", [drivers, safe_misc]),
    ],
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
    "SYNC/MODE strapped low by a 0R (fit the other 0R to strap high if the datasheet mode table calls for it).",
    [
        U("U103", S_QT, "AT42QT1011-TSHR", {"4": "TS1_S", "3": "TS1_K", "5": "+3V3", "2": "GND", "1": "TOUCH1", "6": "TS1_MODE"},
          "SOT23-6", lcsc="C112956", mfr="Microchip", ver="yes"),
        C("C111", "10n C0G", "TS1_K", "TS1_S", note="Cs, tune at EVT"),
        R("R108", "4.7k", "TS1_K", "TS1_E", **R4K7),
        Part("E101", S_E, "Touch key 1", {"1": "TS1_E"}, FP["TOUCH"]),
        R("R109", "0R", "TS1_MODE", "GND", **R0),
        R("R110", "0R", "TS1_MODE", "+3V3", dnp=True, **R0),
        C("C112", "100n", "+3V3", "GND", **C100N),
        U("U104", S_QT, "AT42QT1011-TSHR", {"4": "TS2_S", "3": "TS2_K", "5": "+3V3", "2": "GND", "1": "TOUCH2", "6": "TS2_MODE"},
          "SOT23-6", lcsc="C112956", mfr="Microchip", ver="yes"),
        C("C113", "10n C0G", "TS2_K", "TS2_S", note="Cs, tune at EVT"),
        R("R111", "4.7k", "TS2_K", "TS2_E", **R4K7),
        Part("E102", S_E, "Touch key 2", {"1": "TS2_E"}, FP["TOUCH"]),
        R("R112", "0R", "TS2_MODE", "GND", **R0),
        R("R113", "0R", "TS2_MODE", "+3V3", dnp=True, **R0),
        C("C114", "100n", "+3V3", "GND", **C100N),
    ])

nfc = Block(
    "5. NFC tag (NT3H2111)",
    "Field-powered: a phone can read the setup record with the socket unpowered. Antenna tuned to 13.56 MHz with C115 at EVT.",
    [
        U("U105", S_NFC, "NT3H2111W0FTTJ", {"1": "NFC_LA", "8": "NFC_LB", "6": "+3V3", "2": "GND", "3": "NFC_SCL",
                                            "5": "NFC_SDA", "4": "NFC_FD", "7": "NC"},
          "TSSOP8", lcsc="C2654884", mfr="NXP", ver="yes", note="Pinout from LCSC/Flux listing; check against NXP datasheet"),
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
        Sheet("MCU and power", "mcu_power.kicad_sch", "Front board: 3.3 V, ESP32-C6, test pads",
              [front_pwr, front_mcu, front_tp], flags=["+5V", "GND", "+3V3"]),
        Sheet("Touch, NFC, light", "hmi.kicad_sch", "Front board: touch keys, NFC tag, light lines",
              [touch, nfc, leds], flags=["LED_5V"]),
    ],
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
