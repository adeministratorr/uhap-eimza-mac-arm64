#!/usr/bin/env python3
"""Jar-içi ve nested-jar-içi native imzalama helper'ı.

Kullanım: python3 scripts/inner-sign.py <APP> <IDENTITY>
- Contents/app altındaki her .jar'ın içini açar
- Mach-O magic'e sahip TÜM dosyaları (.dylib/.jnilib ve uzantısız da dahil) Developer ID ile
  hardened-runtime + secure timestamp imzalar
- jar içindeki .jar'lara DAHIL girer (jna/sqlite-jdbc gibi nested jar'lar)
- imza sonrası jar'ları orijinal konuma geri zip'ler
Hata olursa process exit 9 — make bunu yakalar.
"""
import os
import shutil
import subprocess
import sys
import tempfile

MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce",  # Mach-O 32 bit  BE
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit BE
    b"\xce\xfa\xed\xfe",  # Mach-O 32 bit LE
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit LE
    b"\xca\xfe\xba\xbe",  # Fat (universal) binary
}

app = os.path.abspath(sys.argv[1])
identity = sys.argv[2]

if not os.path.isdir(app):
    print(f">> inner-sign: .app yok: {app}", file=sys.stderr)
    sys.exit(1)

root = os.path.join(app, "Contents", "app")
if not os.path.isdir(root):
    print(f">> inner-sign: /Contents/app bulunamadı: {app}", file=sys.stderr)
    sys.exit(1)


def is_macho(path):
    # 0xCAFEBABE hem fat-binary hem Java class magic olduğundan byte-magic
    # kullanmak yerine `file` mime'ı ile ayrım yapılıyor.
    r = subprocess.run(
        ["file", "--brief", "--mime-type", path],
        capture_output=True, text=True,
    )
    mime = r.stdout.strip()
    return mime in ("application/x-mach-binary", "application/x-pie-executable")


def sign_macho(path):
    r = subprocess.run(
        [
            "codesign", "--force", "--options", "runtime",
            "--timestamp", "--sign", identity, path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    if r.returncode != 0:
        print(f">> inner-sign: codesign BAŞARISIZ: {path}", file=sys.stderr)
        sys.exit(9)


def process_jar(jar):
    jar = os.path.abspath(jar)
    tmp = tempfile.mkdtemp()
    try:
        r = subprocess.run(
            ["unzip", "-q", jar, "-d", tmp],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        if r.returncode != 0:
            print(f">> inner-sign: unzip BAŞARISIZ: {jar}", file=sys.stderr)
            sys.exit(12)
        for d, dirs, files in os.walk(tmp):
            for name in files:
                p = os.path.join(d, name)
                if name.endswith(".jar"):
                    with open(p, "rb") as fh:
                        head = fh.read(4)
                    if head == b"PK\x03\x04":
                        process_jar(p)  # nested jar — recursif işle
                        continue
                if is_macho(p):
                    sign_macho(p)
        r2 = subprocess.run(
            ["zip", "-qr", jar, "."], cwd=tmp,
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        if r2.returncode != 0:
            print(f">> inner-sign: zip BAŞARISIZ: {jar}", file=sys.stderr)
            sys.exit(11)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


top = []
for name in os.listdir(root):
    p = os.path.join(root, name)
    if name.endswith(".jar") and os.path.isfile(p):
        top.append(p)

if not top:
    print(">> inner-sign: /Contents/app altında .jar yok", file=sys.stderr)
    sys.exit(1)

for jar in top:
    process_jar(jar)
print(">> inner-sign tamam (nested jar'lar dahil)")
