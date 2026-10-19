# UHAP İmzalama — macOS Apple Silicon (M1/M2/M3/M4) Kurulumu (arm64)

UHAP e-imza aracını **MacBook, MacBook Pro, MacBook Air, Mac mini ve iMac**'de native çalıştırın. Apple Silicon (M serisi, ARM tabanlı işlemci) için native `.app`; gömülü arm64 Java 11 — Rosetta gerekmez, ayrı Java kurulumu gerekmez.

**Kimler için:** uhap.com.tr ve cmk.uhap.com.tr üzerinden e-imza ile işlem yapan **avukatlar** (özellikle baro CMK görevlendirmeleri), icra ve hukuk süreçlerinde UHAP imzalama kullanan hukuk profesyonelleri.

## Kimler için?
- **Avukatlar:** uhap.com.tr üzerinden belge imzalayanlar.
- **CMK görevlendirmeleri yapan avukatlar:** cmk.uhap.com.tr akışı için `MODE=cmk` kurulumu (aşağıda).
- **Hukuk büroları:** MacBook (M1/M2/M3/M4) ve iMac ile e-imza kurulumu.
- **İcra ve dava süreçleri:** UHAP üzerinden e-imza gerektiren tüm hukuk işlemleri.

## "Mac'te e-imza çalışmıyor" arayanlar için kısa cevaplar
- **Neden Mac'te çalışmıyor?** Aracın Windows sürümü dağıtılıyor; Mac kurulumu yok. Bu port, aracı arm64 Mac'te native çalıştırır.
- **MacBook / MacBook Pro / MacBook Air / iMac / Mac mini'de çalışır mı?** Evet — Apple Silicon (M1/M2/M3/M4). Intel desteklenmez.
- **Rosetta veya Java kurmam gerekir mi?** Hayır; ARM native (arm64), Java gömülü.
- **İmza için ek olarak ne gerekir?** e-imza kartı + kart okuyucu + **arm64 AKİS sürücüsü** (aşağıda).

## Neden Mac'te çalışmıyordu? Nasıl çözdük?

- **Sorun:** UHAP e-imza aracının Mac sürümü yoktu; Windows kurulumu ise Mac'te çalışmıyordu.
- **Neden:** Java tabanlı uygulama Windows'a özgü yollarla çalışıyordu: config dosyası Windows düzenine göre okunuyor, log yolu yazılamıyor ve yerel imza sunucusu sabit port kullanıyordu.
- **Çözüm:** `jpackage` + gömülü **arm64 Java 11** ile native `.app`; config `-Duser.dir` ile paket içinden okundu, yazılabilir log yolu verildi, ASCII yürütücü adı + ad-hoc imza uygulandı. CMK (cmk.uhap.com.tr) için `MODE=cmk` ile ayrı ortam/port derlemesi eklendi.
- **Doğrulama:** Gerçek AKİS kartı ile RSA-2048 imza uçtan uca doğrulandı.

## Kurulum (3 yol)
1. **Tek satır (kaynaktan derler):** aşağıdaki "Kurulum (tek komut)" bölümü.
2. **Homebrew cask (hazır DMG, derleme beklemez):**

```bash
brew install --cask adeministratorr/tap/uhap-eimza
```

3. **Hazır DMG:** [Releases](../../releases) → `UhapEimza-arm64-*.dmg`

Diğer araçlar (aynı tap): [e-Devlet E-İmza](https://github.com/adeministratorr/edevlet-eimza-mac-arm64) · [PTT KEP Webmail](https://github.com/adeministratorr/pttkep-eimza-mac-arm64) · [PTT UETS / e-Tebligat](https://github.com/adeministratorr/uets-eimza-mac-arm64) · [TNB Teknoloji İmza](https://github.com/adeministratorr/tnb-eimza-mac-arm64) · [UDF QuickLook](https://github.com/adeministratorr/udf-quicklook-extension) · [UYAP Doküman Editörü](https://github.com/adeministratorr/ude-mac-arm64-1)

---

# UHAP İmzalama — macOS (Apple Silicon) Portu

UHAP e-imza aracının (ARDGRUP/ImzaTek tabanlı) Apple Silicon Mac'ler için
**resmi olmayan, topluluk** portu. Gömülü arm64 Java 11 runtime ile native bir
`.app` üretir; Rosetta veya ayrı Java kurulumu gerekmez.

## Kurulum (tek komut)

Terminale şunu yapıştırın:

```bash
curl -fsSL https://raw.githubusercontent.com/saidsurucu/uhap-eimza-mac-arm64/main/kur.sh | bash
```

Bu betik sırayla: Xcode Command Line Tools'u (gerekirse) kurar, depoyu
`~/uhap-eimza-mac-arm64` altına klonlar, arm64 Java 11 runtime'ını indirir,
`UHAPImza.app`'i derleyip imzalar ve `/Applications`'a kurar. İnternet gerekir.

Kurulumdan sonra **UHAP İmzalama**'yı Launchpad/Uygulamalar'dan açın.

## Zorunlu: AKİS arm64 sürücüsü

Uygulama akıllı kartı `libakisp11.dylib` üzerinden okur ve **arm64** kod olarak
çalışır; Intel sürücü arm64 sürece yüklenemez. TÜBİTAK BİLGEM'den
**"Mac OS Arm (Apple Silicon)"** etiketli AKİS paketini kurun:

- https://akiskart.bilgem.tubitak.gov.tr/tr/destek/

Doğrulama (arm64 içermeli):

```bash
lipo -archs /usr/local/lib/libakisp11.dylib
```

`kur.sh`, uygulamanın sürücüyü aradığı yere (`~/Library/Java/Extensions/`)
arm64 `libakisp11.dylib`'i otomatik yerleştirir; oradaki eski Intel sürücüyü
`.x86_64.bak` olarak yedekler. AKİS arm64 paketini kurduktan sonra `kur.sh`'i
(tekrar) çalıştırmanız yeterlidir. Intel-only sürücü kuruluysa kart okunamaz;
arm64 paketini kurun.

## Kullanım

1. **UHAP İmzalama**'yı açın (arka planda `localhost:8080`'de çalışır).
2. Tarayıcıda https://uhap.com.tr açıp imzalama akışını başlatın.
3. Kart PIN'inizi girin; belge imzalanır.

Loglar: `~/Library/Logs/UHAPImza/log.out`

## UHAP-CMK (cmk.uhap.com.tr) için kurulum

CMK imzalama ekranı, UHAP ana sitesinden **farklı** bir ortam ve **farklı bir
port** kullanır. Varsayılan kurulum (`uhap.com.tr`, port 8080) CMK'da çalışmaz;
imzala butonu "imzalama aracının açık olduğundan emin olunuz" hatası verir.
CMK için `MODE=cmk` ile derleyin:

```bash
MODE=cmk ./kur.sh        # ya da: make install MODE=cmk
```

| | `MODE=uhap` (varsayılan) | `MODE=cmk` |
|---|---|---|
| Site | uhap.com.tr | cmk.uhap.com.tr |
| Ortam (jar argümanı) | `uhap-prod` | `ocas-prod` |
| Yerel port | 8080 | 5085 (jar'daki sabit derleme sırasında yamalanır) |
| Görünür imza yaması | kapalı (`PATCH_VISIBLE_SIG=1` ile açılır) | açık |

İki mod aynı anda çalışmaz (aynı uygulama adı); birini kurunca diğerinin yerine geçer.

**Chrome "yerel ağ erişimi" izni:** Yeni Chrome sürümleri, HTTPS bir siteden
`localhost`'a isteği izin verilmedikçe engeller; bu durumda istek uygulamaya hiç
ulaşmaz (log'a düşmez). `chrome://settings/content/localNetworkAccess` sayfasında
`https://cmk.uhap.com.tr` (ve ana site için `https://uhap.com.tr`) adresini
**İzin verilen** listesine ekleyin.

## Teknik özet

- **jpackage + Zulu 11 arm64**: `.app` içine gömülü runtime (HiDPI/Retina).
- **SunPKCS11 yolu**: uygulama TÜBİTAK ESYA (ma3api) ile SunPKCS11 üzerinden
  imzalar; `jdk.crypto.cryptoki` modülü `--add-exports` ile açılır.
- **Config çözümü**: `-Duser.dir=$APPDIR` ile config bundle içinden okunur.
- **Yazılabilir log yolu** ve **ASCII executable adı** (`UHAPImza`) +
  ad-hoc `codesign`.

arm64 Zulu 11 + AKİS ile uçtan uca gerçek imza (RSA-2048) bu makinede
doğrulanmıştır — bkz. `docs/VERIFICATION.md`.

## Elle derleme

```bash
git clone https://github.com/saidsurucu/uhap-eimza-mac-arm64.git
cd uhap-eimza-mac-arm64
make app        # sadece .app'i derle (build/UHAPImza.app)
make dmg        # sürükle-bırak disk imajı
make run        # derleyip çalıştır
make install    # /Applications'a kur
```

## Sorun giderme

- **Gatekeeper "açılamıyor":** Uygulamaya sağ tık → **Aç** (ad-hoc imzalı).
- **8080 meşgul:** Portu kullanan başka uygulamayı kapatın (port sabittir).
- **"kütüphane yüklenemedi" / kart okunmuyor:** AKİS **arm64** sürücüsünü kurun.
- **Sertifika doğrulama hatası:** Uygulama `depo.kamusm.gov.tr`'ye erişir;
  internet gerekir.

## Bilinen sınırlar

- Yalnızca **arm64** (Apple Silicon); Intel desteklenmez.
- **Notarize edilmemiştir** (ad-hoc imza; ilk açılışta sağ tık → Aç).
- Görünür (visible) PDF imzası test edilmemiştir; kaynak uygulamada bu yol
  Windows'a özgü bir dosya yolu içerir (görünmez imza test edilen yoldur).
- Kart tipi: **AKİS**. Diğer token'lar test edilmemiştir.
- Yerel sunucu tüm arayüzlerde (`*:8080`) dinler; yerel ağdan erişilebilir.

## Sorumluluk reddi

Bu depo **resmi değildir**; UHAP, ARDGRUP veya TÜBİTAK tarafından geliştirilmemiş
ya da onaylanmamıştır. Yalnızca paketleme ve derleme betikleri sağlar. UHAP /
ARDGRUP / TÜBİTAK marka ve yazılım hakları sahiplerine aittir.
