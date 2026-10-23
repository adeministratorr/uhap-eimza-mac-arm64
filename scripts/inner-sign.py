#!/usr/bin/env python3
"""Jar-içi ve nested-jar-içi native imzalama helper'ı (bellek-içi zipfile).

Kullanım: python3 scripts/inner-sign.py <APP> <IDENTITY>
- Contents/app altındaki her .jar zipfile ile okunur (diskte AÇILMAZ)
- Mach-O magic'e sahip TÜM dosyaları (.dylib/.jnilib ve uzantısız da dahil) Developer ID ile
  hardened-runtime + secure timestamp imzalar
- jar içindeki .jar'lara DAHIL girer (jna/sqlite-jdbc gibi nested jar'lar)
- macOS harf-duyarsız FS'te obfuscate çakışmalarından kaçınmak için extract yok;
  yeni arşiv temp dosyaya yazılır ve os.replace ile orijinal yerine geçer
  (duplicate entry korunur — ilk-gelen kazanır)
Hata olursa process exit 9 — make bunu yakalar.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

MACHO_LE32 = b"\xce\xfa\xed\xfe"   # x86/i386/aarch64 LE
MACHO_LE64 = b"\xcf\xfa\xed\xfe"
MACHO_BE32 = b"\xfe\xed\xfa\xce"
MACHO_BE64 = b"\xfe\xed\xfa\xcf"
FAT_MAGIC = b"\xca\xfe\xba\xbe"

app = os.path.abspath(sys.argv[1])
identity = sys.argv[2]

if not os.path.isdir(app):
    print(f">> inner-sign: .app yok: {app}", file=sys.stderr)
    sys.exit(1)

root = os.path.join(app, "Contents", "app")
if not os.path.isdir(root):
    print(f">> inner-sign: /Contents/app bulunamadı: {app}", file=sys.stderr)
    sys.exit(1)

_signed = 0
_nested = 0


def is_macho_bytes(raw):
    """0xCAFEBABE hem Java class hem universal-binary magic'i. Fat header'dan
    hemen sonra 4 bayt = slice SAYISI (1..15); Java class'ta o alan
    minor/major version'dur (>=45). count>15 => java.class, imzalanmaz."""
    if len(raw) < 8:
        return False
    m = raw[:4]
    if m == FAT_MAGIC:
        count = int.from_bytes(raw[4:8], "big")
        return 1 <= count <= 15
    return m in (MACHO_LE32, MACHO_LE64, MACHO_BE32, MACHO_BE64)


def sign_macho_bytes(raw, tmpdir, label):
    """raw baytları geçici dosyaya yazıp codesign'dan geçirir, imzalı baytları döner."""
    fd, path = tempfile.mkstemp(dir=tmpdir)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        r = subprocess.run(
            ["codesign", "--force", "--options", "runtime",
             "--timestamp", "--sign", identity, path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        if r.returncode != 0:
            print(f">> inner-sign: codesign BAŞARISIZ: {label}", file=sys.stderr)
            sys.exit(9)
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def process_jar_bytes(raw, tmpdir, label, depth=0):
    """Bir jar'ın bayt dizisini imzalar → yeni bayt dizisi. Duplicate entry'ler
    (merged jar'da ilk-gelen-kazanır) sırasıyla korunur."""
    if depth >= 4:
        return raw
    global _signed, _nested
    with zipfile.ZipFile(io.BytesIO(raw)) as zin:
        infos = zin.infolist()
        datas = [zin.read(i) for i in infos]
    out = []
    for info, data in zip(infos, datas):
        name = info.filename
        if name.endswith(".jar") and data[:4] == b"PK\x03\x04":
            data = process_jar_bytes(data, tmpdir, f"{label}!{name}", depth + 1)
            _nested += 1
        elif not name.endswith("/") and is_macho_bytes(data):
            data = sign_macho_bytes(data, tmpdir, f"{label}!{name}")
            _signed += 1
        out.append((info, data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zout:
        for info, data in out:
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zout.writestr(zi, data)
    return buf.getvalue()


def process_jar(jar):
    jar = os.path.abspath(jar)
    tmpdir = tempfile.mkdtemp()
    try:
        try:
            with open(jar, "rb") as f:
                original = f.read()
        except OSError as e:
            print(f">> inner-sign: okunamadı {jar}: {e}", file=sys.stderr)
            sys.exit(12)
        try:
            new = process_jar_bytes(original, tmpdir, os.path.basename(jar))
        except zipfile.BadZipFile as e:
            print(f">> inner-sign: BADZIP {jar}: {e}", file=sys.stderr)
            sys.exit(12)
        fd, tmpzip = tempfile.mkstemp(dir=os.path.dirname(jar), suffix=".jar.new")
        with os.fdopen(fd, "wb") as f:
            f.write(new)
        os.replace(tmpzip, jar)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


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
print(f">> inner-sign tamam: {_signed} Mach-O imzalandı, {_nested} nested jar işlendi")
