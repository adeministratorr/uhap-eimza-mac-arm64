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
    # Hem mime hem magic kontrolü: eski universal (ppc/ppc64 + i386/x64) dosyaların
    # mime'ı bazı file sürümlerinde x-mach-binary dışına da düşüyor; Java .class dosyası
    # ile paylaşılan 0xCAFEBABE magic'i SADECE .class uzantısız dosyada Mach-O sayılıyor.
    r = subprocess.run(
        ["file", "--brief", "--mime-type", path],
        capture_output=True, text=True,
    )
    if r.stdout.strip() in ("application/x-mach-binary", "application/x-pie-executable"):
        return True
    try:
        with open(path, "rb") as f:
            head = f.read(4)
    except OSError:
        return False
    if head == b"\xca\xfe\xba\xbe" and path.endswith(".class"):
        return False          # Java class (fat-binary magic'ini paylaşır)
    return head in MACHO_MAGICS


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
        # zip mevcut arşive EKLEME yapar; imzalı yeni girdi aynı path için arşivde
        # ikinci defa görünür ve unzip/JVM tarayıcılar İLK (eski/imsız) girdiyi alır.
        # O yüzden önce eski jar silinir.
        if os.path.exists(jar):
            os.remove(jar)
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
