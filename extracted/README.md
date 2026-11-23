# Ekstraksi APK — Shivaay VPN 1.0.0

APK berhasil dikeluarkan dari ZIP dan seluruh isinya sudah dibongkar.

## Struktur folder

```
DEVILL VPN/
├── Shivaay_VPN_P_com.shivaay.firefoxvpn_V_v1.0.0.zip   (file asli)
├── Shivaay_VPN_P_com.shivaay.firefoxvpn_V_v1.0.0.apk   (APK hasil ekstrak)
└── extracted/
    ├── apk/                        Isi APK mentah (36 MB)
    │   ├── AndroidManifest.xml     Manifest biner (asli)
    │   ├── classes.dex             Kode Java/Kotlin (wrapper Flutter)
    │   ├── resources.arsc          Tabel resource
    │   ├── res/                    Semua resource (ikon, layout, XML biner)
    │   ├── assets/flutter_assets/  Asset Flutter (logo.png, font, shader)
    │   ├── lib/arm64-v8a/          Library native:
    │   │   ├── libapp.so                    Kode Dart (AOT, bukan source)
    │   │   ├── libflutter.so                Flutter engine
    │   │   ├── libgojni.so                  Core Go / sing-box
    │   │   └── libhev-socks5-tunnel.so      TUN → SOCKS5
    │   └── META-INF/
    ├── AndroidManifest.xml         Manifest hasil decode (mudah dibaca)
    ├── resources.txt               Dump lengkap tabel resource
    ├── resources-strings.txt       Semua string + terjemahan
    ├── badging.txt                 Info package dari aapt2
    ├── xml/                        Semua XML res yang sudah di-decode
    ├── xmltree/                    Dump mentah aapt2 (cadangan)
    ├── signature/
    │   └── signing-cert.pem        Sertifikat penanda tangan APK
    └── tools/
        └── xmltree2xml.py          Script konversi xmltree → XML
```

## Informasi APK

| Item | Nilai |
|---|---|
| Nama | Shivaay VPN |
| Package | `com.shivaay.firefoxvpn` |
| Versi | 1.0.0 (versionCode 2001) |
| minSdk / targetSdk | 24 (Android 7.0) / 36 (Android 16) |
| ABI | arm64-v8a saja |
| Ukuran APK | 15,3 MB |
| Isi terpasang | ± 36 MB (library diekstrak saat install) |
| Teknologi | Flutter (release AOT) + Go core + hev-socks5-tunnel |
| Tanda tangan | v2, RSA-2048/SHA-256, self-signed |
| SHA-256 APK | `bbd328d772bee8ec0601b9ecb2696cacca4024633b48775d36e053ce1ea3bdea` |

## Yang bisa diubah dari hasil ekstrak ini

- **Nama aplikasi** → resource string `app_name` (sekarang "Shivaay VPN")
- **Ikon launcher, banner, ikon notifikasi, widget** → folder `res/`
- **Manifest**: permission, komponen, package name, allowBackup, dll.
- **Logo dalam aplikasi** → `apk/assets/flutter_assets/assets/logo.png` (256×256)
- **Teks notifikasi & nama channel** → string resource (sudah ada terjemahan 14 bahasa)
- **Package name** (mis. jadi `com.devill.vpn`) → perlu edit manifest + smali, lebih aman lewat apktool

## Yang TIDAK bisa dipulihkan dari APK

- **Kode Dart/Flutter** → `libapp.so` sudah dikompilasi AOT, tidak ada `kernel_blob.bin`, jadi source Dart tidak ada di dalam APK.
- **Kode Go** (core VPN/sing-box) → `libgojni.so` hanya binary.
- **Layout/UI Flutter** → bukan XML Android; digambar oleh Flutter.
- **Private key** penanda tangan → yang ada hanya sertifikat publik. APK tidak bisa di-update dengan signature yang sama tanpa key aslinya.

Artinya: untuk mengembangkan UI/logika, kamu butuh **source project Flutter + Go**, bukan hasil ekstrak APK. Ekstrak ini berguna sebagai referensi (manifest, izin, aset, teks, ikon) dan untuk modding ringan.

## Jalur pengembangan yang realistis

1. **Cari source aslinya.** Di dalam APK ada referensi
   `github.com/Shivaay20005/Shivaay-vpn-client`, tetapi saat dicek endpoint repo/rilis-nya
   mengembalikan **404** (privat/dihapus/berganti nama). Coba cari fork, arsip, atau hubungi developer.
2. **Modding APK (rebrand ringan).** Butuh `apktool` + Java:
   ```bash
   apktool d -f -o apktool_out Shivaay_VPN_P_com.shivaay.firefoxvpn_V_v1.0.0.apk
   # edit res/, AndroidManifest.xml, smali
   apktool b apktool_out -o unsigned.apk
   zipalign -f 4 unsigned.apk aligned.apk
   apksigner sign --ks devill.jks --out devill-vpn.apk aligned.apk
   ```
   Ini hanya mengubah resource/manifest/wrapper Java. Teks dan logika di dalam Flutter
   tetap tidak bisa diedit dengan cara ini.
3. **Bangun ulang dari nol.** Buat project Flutter baru + integrasi core VPN
   (sing-box `libgojni.so` atau hev-socks5-tunnel), lalu desain ulang UI "DEVILL VPN".
   Ini jalur yang paling fleksibel dan bersih secara legal.
4. **Rebrand total.** Ganti package name, nama, ikon, dan buat keystore sendiri.
   Karena signature berbeda, versi lama harus di-uninstall dulu sebelum install versi baru.

## Catatan penting

- Aplikasi ini **bukan aplikasi resmi Mozilla/Firefox**. Ia login ke **Firefox Account**
  (`accounts.firefox.com`) untuk mendapatkan akses proxy. Sebaiknya jangan memakai akun
  Firefox utama.
- Izin `QUERY_ALL_PACKAGES` (melihat semua aplikasi terpasang) dan `allowBackup=true`
  perlu ditinjau ulang kalau mau dipublikasikan.
- Nama package mengandung "firefox" dan UI memakai branding Firefox Account — berisiko
  dari sisi trademark/kebijakan Google Play jika dipublikasikan.
- Endpoint cek update di APK sudah mati (404), jadi fitur update otomatis tidak berfungsi.
- APK hanya untuk **arm64-v8a**; tidak bisa dipasang di perangkat 32-bit.

---

# Rebrand → DEVILL VPN

Build jadi: **`DEVILL-VPN-1.0.0.apk`** (di root project dan `build/`).

| Item | Nilai |
|---|---|
| Nama aplikasi | `DEVILL VPN` |
| Package (app id) | `com.devill.vpn` — **beda** dari Shivaay, jadi bisa terpasang berdampingan |
| Versi | 1.0.0 (versionCode 2001) |
| Ukuran | 15,8 MB |
| Tanda tangan | v2 + v3, sertifikat baru `CN=DEVILL VPN` |
| SHA-256 | `46a26bb1b59b11447291f1424b0243a88a278c1e715abe9ea497b4673bb2d495` |

## Yang diubah (penggantian byte sama panjang)

Semua penggantian **wajib sama panjang** karena string Flutter AOT dan Go
memakai prefix panjang. Script: `extracted/tools/rebuild_apk.py`.

| File | Perubahan | Jumlah |
|---|---|---|
| `resources.arsc` | `Shivaay VPN` → `DEVILL VPN ` | 1 |
| `libapp.so` | `Shivaay VPN` → `DEVILL VPN ` (ASCII) | 20 |
| `libapp.so` | `Shivaay VPN` → `DEVILL VPN ` (UTF-16LE) | 26 |
| `libgojni.so` | `Shivaay VPN` → `DEVILL VPN ` | 15 |
| `libapp.so` | `Shivaay20005/Shivaay-vpn-client` → `DhanyDevill/Dhany-Devill-Client` | 1 |
| `libgojni.so` | `Shivaay20005/Shivaay-vpn-client` → `DhanyDevill/Dhany-Devill-Client` | 1973 |
| `libapp.so` | `Shivaay-vpn-client` → `DhanyDevill-Client` | 2 |
| `libgojni.so` | `Shivaay-vpn-client` → `DhanyDevill-Client` | 4 |
| `libhev-socks5-tunnel.so` | `Shivaay-vpn-client` → `DhanyDevill-Client` | 32 |
| `libapp.so` | `Shivaay-VPN-` → `DEVILL-VPN--` | 3 |
| `libgojni.so` | `Shivaay-VPN-` → `DEVILL-VPN--` | 3 |
| `libapp.so` | `shivaay_vpn` → `devill_vpns` | 48 |
| `libapp.so` | `shivaay-vpn` → `devill-vpns` | 1 |
| `libgojni.so` | `shivaay-vpn` → `devill-vpns` | 8 |
| `libapp.so` | `SHIVAAY_VPN_UPDATE_SERVER` → `DEVILL_VPN_UPDATE_SERVERS` | 1 |
| `libapp.so` | `__shivaayReply` → `__devillReply_` | 2 |
| `libapp.so` | `__shivaayHooked` → `__devillHooked_` | 2 |
| `libapp.so` | `ShivaayFxa` → `DevillFxa_` | 2 |

Nama app jadi `DEVILL VPN` + satu spasi di akhir (tidak terlihat di launcher).

Nama developer: `Shivaay20005` (12 byte) → `Dhany Devill` (12 byte). Karena semua
kemunculannya berbentuk `owner/repo`, yang dipakai adalah `DhanyDevill` (tanpa
spasi, karena spasi tidak valid di path/URL). Aturan `Shivaay20005` → `Dhany Devill`
tetap ada di script untuk kemunculan tunggal di masa depan.

Script juga punya `verify_output()`: build **gagal** kalau masih ada string
"shivaay" di luar daftar putih (nama class/JNI).

## Endpoint update → GitHub sendiri

Semua URL proyek Shivaay di `libapp.so` diganti (panjang byte identik,
`REPO = 'Dhany85/DEVILL-VPN-Releases-APK'`, 31 karakter) supaya fitur
"Cek update" menunjuk ke repo sendiri:

- `https://api.github.com/repos/Dhany85/DEVILL-VPN-Releases-APK/releases/latest`
- `https://github.com/Dhany85/DEVILL-VPN-Releases-APK/releases` (+ `/releases`,
  `/releases/tag/…`, `/releases/download/…`)
- `https://raw.githubusercontent.com/Dhany85/DEVILL-VPN-Releases-APK/HEAD/.github/updates.json`
- `https://cdn.jsdelivr.net/gh/Dhany85/DEVILL-VPN-Releases-APK@main/.github/updates.json`
- slug lama → `Dhany85/DEVILL-VPN-Releases-APK`
- teks error "Could not reach GitHub…" (5 bahasa) → kata netral

Repo itu **belum ada** (404), jadi cek update masih error sampai dibuat.
Langkah sekali saja:

1. Buat repo publik `Dhany85/DEVILL-VPN-Releases-APK` (nama harus persis,
   19 karakter — sudah tertanam di binary, tidak bisa diubah tanpa rebuild).
2. Buat Release dengan tag `v1.0.1` dan lampirkan `DEVILL-VPN-1.0.1.apk`.
3. (Opsional) tambah file `.github/updates.json` di branch `main`.

Catatan: path modul Go di `libgojni.so` juga ikut jadi
`github.com/Dhany85/DEVILL-VPN-Releases-APK/core@...` — itu hanya nama simbol,
tidak dipakai untuk jaringan.

## Ikon & artwork

Ikon memakai artwork yang dikirim pengguna
(`extracted/artwork/icon-source.png`, 1024×1024 RGBA): kartu putih berbingkai
silver dengan kepala iblis bertanduk merah, mata menyala, perisai sirkuit
cyan, ring cyan, dan wordmark "DEVILL VPN", di atas latar marble.

Artwork dipakai **apa adanya** — tidak dipotong, tidak di-inpainting, wordmark
tidak dihapus. `extracted/tools/icons_from_art.py` hanya melakukan resampling
(resampler area-average dengan alpha premultiplied), murni Python, tanpa
Pillow/ImageMagick. Preview untuk diperiksa: `build/artwork/`.

Arsip artwork versi sebelumnya: `icon-source-dark.png` (versi pertama) dan
`icon-source-darkcard.png` (kartu hitam glossy).

| Resource | File | Ukuran | Fungsi |
|---|---|---|---|
| `mipmap/ic_launcher` | `res/9w,yn,FS,RJ,o-.png` | 48–192 px | ikon lama (API < 26), seluruh artwork termasuk bingkai marble |
| `mipmap/ic_launcher_background` | `res/3z,I2,6h,cV,Gx.png` | 108–432 px | plate kartu full-bleed + desain (tanpa bingkai), 58 dp |
| `mipmap/ic_launcher_foreground` | `res/QZ,zr,Em,Lf,as.png` | 108–432 px | **transparan** (layer tetap ada karena direferensikan XML) |
| `drawable/banner` | `res/OA.png` | 320×180 | banner Android TV: artwork utuh di tengah |
| `drawable/ic_stat_logo` | `res/oN.xml` | 24 dp | ikon notifikasi & Quick Settings (silhouette putih) |
| `assets/logo.png` | `assets/flutter_assets/…/logo.png` | 256 px | logo di dalam aplikasi / splash |

Catatan teknis:

- **Tidak ada nama resource/ID yang berubah**, jadi `resources.arsc` dan
  `AndroidManifest.xml` tidak disentuh. Cukup timpa file lalu rebuild.
- Adaptive icon: bingkai kartu **tidak** dipakai. Kartu persegi tidak mungkin
  sekaligus mengisi mask bulat/squircle dan mempertahankan sudutnya, jadi
  layer background = warna plate kartu full-bleed (`#E5E9EC`, sampling bagian
  dalam kartu) + desain (kepala, ring, wordmark) dari area dalam kartu
  (`CROP = (135,125,890,908)`, bevel dan marble tidak ikut). Desain dirender
  58 dp dan tepinya di-feather 14 px sumber, jadi tidak ada bingkai yang bisa
  terpotong. Kepala + ring + wordmark menempati radius ≤ 34 dp dari pusat,
  aman di dalam lingkaran 72 dp.
- Wordmark dibiarkan di tempatnya di semua ukuran; tidak ada teks yang
  digambar ulang, jadi tidak ada teks ganda atau teks yang hilang.
- `res/oN.xml` adalah **binary XML** yang ditulis dari nol oleh
  `extracted/tools/axml.py` (string pool UTF-8 + resource map + vector
  `pathData`). Diperiksa ulang dengan `aapt2 dump xmltree`.
- Ikon notifikasi harus berupa silhouette putih (alpha only); sistem yang
  mewarnainya. Path perisai tanpa lubang kunci, `fillType` non-zero.
- `logo.png` (dipakai UI Flutter) = artwork utuh 256 px, sama seperti ikon
  launcher.
- Yang **tidak** diganti: `assets/flutter_assets/assets/tray/*.png|ico`
  (ikon tray desktop/Windows; tidak dipakai di Android).

Cara membuat ulang semuanya:

```bash
python3 extracted/tools/icons_from_art.py extracted/apk build/artwork
# lalu rebuild + sign seperti di bagian "Build ulang"
```


## Package / app id

`AndroidManifest.xml` biner di-patch dengan `extracted/tools/patch_manifest.py`
(rebuild ResStringPool, jadi panjang string boleh berubah):

| String | Lama | Baru |
|---|---|---|
| `package` | `com.shivaay.firefoxvpn` | `com.devill.vpn` |
| permission | `com.shivaay.firefoxvpn.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` | `com.devill.vpn.…` |
| provider authority | `com.shivaay.firefoxvpn.androidx-startup` | `com.devill.vpn.androidx-startup` |

Hasilnya: Android menganggapnya **aplikasi lain** → tidak menimpa / tidak
meng-update Shivaay VPN, dan bisa dipasang berdampingan.

Yang tetap memakai nama class lama (wajib):

- `com.shivaay.firefoxvpn.MainActivity`, `CoreService`, `QuickTile`,
  `ConnectWidget`, `ConnectWidget$Toggle` — nama class di `classes.dex`.
- `com.shivaay.firefoxvpn.Tun2Socks` — dipanggil JNI oleh
  `libhev-socks5-tunnel.so` (`com/shivaay/firefoxvpn/Tun2Socks`).
- Intent action internal (`com.shivaay.firefoxvpn.RECONNECT/STOP/WIDGET_TOGGLE`)
  — dipakai eksplisit antar-komponen aplikasi sendiri.

## Sisa nama lama (wajib dipertahankan)

Setelah rebrand, **satu-satunya** sisa "shivaay" ada di identitas Java
(paket/class), dan itu tidak boleh diubah:

| File | Jumlah | Isi |
|---|---|---|
| `classes.dex` | 10 | `Lcom/shivaay/firefoxvpn/*` (MainActivity, CoreService, QuickTile, ConnectWidget, Tun2Socks, a) + intent `RECONNECT` / `STOP` / `WIDGET_TOGGLE` |
| `AndroidManifest.xml` | 5 | `android:name="com.shivaay.firefoxvpn.*"` (UTF-16) |
| `libhev-socks5-tunnel.so` | 1 | `com/shivaay/firefoxvpn/Tun2Socks` — dipanggil JNI |
| `resources.arsc` | 1 | nama paket tabel resource (`id 0x7f`), bukan teks yang tampil |

`libapp.so` dan `libgojni.so`: **0 kemunculan**.

Alasannya: nama class ada di `classes.dex` (string table yang harus tetap
konsisten dengan `class_defs`) dan `libhev-socks5-tunnel.so` memanggil
`com/shivaay/firefoxvpn/Tun2Socks` lewat JNI. Mengganti keduanya berisiko
mematikan VPN.

## Yang sengaja TIDAK diubah

- URL data routing pihak ketiga yang masih berfungsi:
  `github.com/Loyalsoldier/v2ray-rules-dat/...` dan
  `raw.githubusercontent.com/Chocolate4U/Iran-v2ray-rules/...` (dipakai untuk
  mengunduh `geoip.dat`/`geosite.dat`; kalau dihapus, update aturan routing rusak).
- `libflutter.so` (pesan framework Flutter, bukan branding aplikasi).
- `classes.dex`: hanya string di atas; checksum/signature DEX tidak disentuh.

## Keystore

```
build/devill.jks      alias: devill      pass: devillvpn
```

Simpan file ini. Tanpa keystore ini, update APK berikutnya tidak bisa
ditimpa di atas versi ini (harus uninstall dulu).

## Build ulang

```bash
# 1. patch app id di manifest biner
python3 extracted/tools/patch_manifest.py extracted/apk/AndroidManifest.xml \
    "com.shivaay.firefoxvpn=com.devill.vpn" \
    "com.shivaay.firefoxvpn.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION=com.devill.vpn.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION" \
    "com.shivaay.firefoxvpn.androidx-startup=com.devill.vpn.androidx-startup"

# 2. rebuild (string replacement + zip)
python3 extracted/tools/rebuild_apk.py \
    Shivaay_VPN_P_com.shivaay.firefoxvpn_V_v1.0.0.apk \
    extracted/apk build/DEVILL-VPN-unsigned.apk

# 3. sign
apksigner sign --ks build/devill.jks --ks-key-alias devill \
    --ks-pass pass:devillvpn --key-pass pass:devillvpn \
    --out build/DEVILL-VPN-1.0.0.apk build/DEVILL-VPN-unsigned.apk
```

## Catatan pemasangan

- App id `com.devill.vpn` **berbeda** dari Shivaay → bisa dipasang **berdampingan**,
  tidak menimpa/meng-update Shivaay VPN, dan **tidak perlu uninstall** apa pun.
- Data aplikasi terpisah (preferensi, cache, akun) karena app id baru.
- Hanya `arm64-v8a` (Android 64-bit).
- `minSdk 24`, `targetSdk 36`.

