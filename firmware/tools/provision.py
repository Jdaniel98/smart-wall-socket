#!/usr/bin/env python3
"""Bench provisioning for Proto 0: a development CA, per-device certificates,
and the factory NVS image that carries them.

    # once: create a development CA (keep ca.key off any shared drive)
    python tools/provision.py ca --out certs/

    # per device: id comes from the console command `id`, e.g. sws-a1b2c3d4e5f6
    python tools/provision.py device --id sws-a1b2c3d4e5f6 \\
        --ca certs/ --uri mqtts://broker.example.com:8883 --out build/sws-a1b2c3d4e5f6/

    # flash the factory partition only (mains DISCONNECTED, isolated adapter)
    esptool.py --chip esp32 -p /dev/ttyUSB0 write_flash 0x3F0000 build/sws-.../fctry.bin

The device certificate's CN is the device id. With Mosquitto's
`use_identity_as_username true` and the ACL `pattern readwrite dev/%u/#`, a
device can only publish and subscribe on its own topics.

These are development credentials: the private key sits unencrypted in flash
(flash encryption stays off on bench units). Revoke and discard them when a
unit is retired. Production identities are created at the test jig.

Needs: openssl on PATH, and esp-idf-nvs-partition-gen (installed with
ESP-IDF, or `pip install esp-idf-nvs-partition-gen`).
"""
import argparse
import csv
import pathlib
import re
import subprocess
import sys

FCTRY_SIZE = 0x6000  # must match partitions.csv
ID_RE = re.compile(r"^sws-[0-9a-f]{12}$")


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def make_ca(out: pathlib.Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    key, crt = out / "ca.key", out / "ca.crt"
    if key.exists():
        sys.exit(f"{key} already exists; refusing to overwrite a CA")
    run("openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(key))
    run("openssl", "req", "-x509", "-new", "-key", str(key), "-sha256", "-days", "1825",
        "-subj", "/O=Aether Labs/CN=Smart Wall Socket Dev CA", "-out", str(crt))
    key.chmod(0o600)
    print(f"CA written to {crt} (key {key})")


def make_device(dev_id: str, ca_dir: pathlib.Path, uri: str, out: pathlib.Path,
                bench: bool) -> None:
    if not ID_RE.match(dev_id):
        sys.exit("device id must look like sws-a1b2c3d4e5f6 (from the console `id` command)")
    if not uri.startswith(("mqtts://", "mqtt://")):
        sys.exit("uri must start with mqtts:// (or mqtt:// for a local test broker)")
    out.mkdir(parents=True, exist_ok=True)
    key, csr, crt = out / "device.key", out / "device.csr", out / "device.crt"
    run("openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(key))
    key.chmod(0o600)
    run("openssl", "req", "-new", "-key", str(key), "-subj", f"/O=Aether Labs/CN={dev_id}",
        "-out", str(csr))
    run("openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca_dir / "ca.crt"),
        "-CAkey", str(ca_dir / "ca.key"), "-CAcreateserial", "-days", "825", "-sha256",
        "-out", str(crt))

    nvs_csv = out / "fctry.csv"
    rows = [
        ("key", "type", "encoding", "value"),
        ("sws", "namespace", "", ""),
        ("mqtt_uri", "data", "string", uri),
        ("ca_pem", "file", "string", str((ca_dir / "ca.crt").resolve())),
        ("cert_pem", "file", "string", str(crt.resolve())),
        ("key_pem", "file", "string", str(key.resolve())),
    ]
    if bench:
        rows.append(("bench", "data", "u32", "1"))
    with nvs_csv.open("w", newline="") as f:
        csv.writer(f).writerows(rows)

    image = out / "fctry.bin"
    run(sys.executable, "-m", "esp_idf_nvs_partition_gen", "generate", str(nvs_csv), str(image),
        hex(FCTRY_SIZE))
    print(f"factory image: {image}  (flash at 0x3F0000)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    ca = sub.add_parser("ca", help="create a development CA")
    ca.add_argument("--out", type=pathlib.Path, required=True)
    dev = sub.add_parser("device", help="create a device certificate and factory image")
    dev.add_argument("--id", required=True)
    dev.add_argument("--ca", type=pathlib.Path, required=True)
    dev.add_argument("--uri", required=True)
    dev.add_argument("--out", type=pathlib.Path, required=True)
    dev.add_argument("--bench", action="store_true",
                     help="allow calibration commands over MQTT (bench units only)")
    a = p.parse_args()
    if a.cmd == "ca":
        make_ca(a.out)
    else:
        make_device(a.id, a.ca, a.uri, a.out, a.bench)


if __name__ == "__main__":
    main()
