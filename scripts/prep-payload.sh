#!/usr/bin/env bash
# app/ (pristine) → build/app/ (patched). Tracked dosyalara dokunmaz.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/app"
DST="$ROOT/build/app"
LOGPATH='${user.home}/Library/Logs/UHAPImza/log.out'

rm -rf "$DST"
mkdir -p "$DST"
cp -R "$SRC"/. "$DST"/

# 1) log4j.properties'i yazılabilir yola çevir (jar içinde)
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
( cd "$TMP" && unzip -oq "$DST/Ard.ESignature.jar" log4j.properties )
# File= satırını değiştir (sed macOS: -i '')
sed -i '' "s#^log4j.appender.fileLogger.File=.*#log4j.appender.fileLogger.File=${LOGPATH}#" "$TMP/log4j.properties"
grep -q '^log4j.appender.fileLogger.File=${user.home}/Library/Logs/UHAPImza/log.out' "$TMP/log4j.properties" || { echo "HATA: log4j.properties yamasi eslesmedi" >&2; exit 1; }
( cd "$TMP" && zip -q "$DST/Ard.ESignature.jar" log4j.properties )

# 2) sunpkcs11.jar'ı payload'dan çıkar (split-package belirsizliğini önle)
rm -f "$DST/sunpkcs11.jar"

# 2b) config XML'lerini $APPDIR köküne de kopyala.
# ESYA, esya-signature-config.xml'i config/'ten mutlak yolla okur AMA içindeki
# <certificate-validation-policy-file>certval-policy.xml</...> göreli referansını
# bağlam kök URI'sine (user.dir = $APPDIR = Contents/app) göre çözer. Bu yüzden
# policy XML'leri Contents/app kökünde de bulunmalı (aksi halde
# FileNotFoundException: .../Contents/app/certval-policy.xml).
cp "$DST"/config/*.xml "$DST"/

# 2c) MODE=cmk: HTTP_SERVER_PORT 8080 -> 5085. UHAP-CMK sayfası imzalama aracını
# http://localhost:5085/imza adresinden çağırır; jar ise 8080'e sabitlenmiştir.
# contacts/constants.<clinit>: sipush 8080 (11 1F 90) + putstatic (B3 00 BB)
# -> sipush 5085 (11 13 DD)
MODE="${MODE:-uhap}"
if [ "$MODE" = "cmk" ]; then
  python3 -I - "$TMP" "$DST/Ard.ESignature.jar" <<'PYEOF'
import sys, zipfile, os, subprocess
tmp, jar = sys.argv[1], sys.argv[2]
name = "contacts/constants.class"
with zipfile.ZipFile(jar) as z:
    data = z.read(name)
old = bytes([0x11, 0x1F, 0x90, 0xB3, 0x00, 0xBB])
new = bytes([0x11, 0x13, 0xDD, 0xB3, 0x00, 0xBB])
if data.count(old) != 1:
    sys.exit("HATA: port yamasi eslesmedi (count=%d)" % data.count(old))
path = os.path.join(tmp, name)
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "wb").write(data.replace(old, new))
subprocess.check_call(["zip", "-q", jar, name], cwd=tmp)
print("port yamasi OK: 8080 -> 5085")
PYEOF
  # CMK görünür imza ister; yama varsayılan açık
  : "${PATCH_VISIBLE_SIG:=1}"
fi

# 2d) Yerel imza servisi yalnızca 127.0.0.1'e bağlansın (yerel ağa açılmasın).
# ArdHttpServer kurucusunda new InetSocketAddress(PORT) çağrısını
# InetAddress.getLoopbackAddress() alan varyanta çevirir (her iki MODE için).
python3 -I "$ROOT/scripts/patch-loopback-bind.py" "$DST/Ard.ESignature.jar"

# 3) (opsiyonel) görünür imza yolundaki ölü Windows yazımını kaldır
if [ "${PATCH_VISIBLE_SIG:-0}" = "1" ]; then
  "$ROOT/scripts/patch-visible-signature.sh"
fi

echo "prep OK → $DST"
