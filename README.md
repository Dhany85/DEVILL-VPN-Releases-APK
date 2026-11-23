# DEVILL VPN

Rebrand + rebuild pipeline untuk APK `com.devill.vpn` (nama, ikon, teks, endpoint update),
dibuat dengan menambal byte APK Flutter/Go tanpa mengubah panjang string.

- Package: `com.devill.vpn` (terpisah dari `com.shivaay.firefoxvpn`)
- Versi: 1.0.0 (versionCode 2001), minSdk 24, targetSdk 36, arm64-v8a
- Tanda tangan: v2 + v3, sertifikat `CN=DEVILL VPN` (keystore **tidak** di repo)

## Status rilis

Belum siap untuk Play Store. Lihat [RELEASE-AUDIT.md](RELEASE-AUDIT.md) —
aplikasi ini klien tidak resmi layanan Mozilla, dan itu penghalang utama.

## Isi repo

| Path | Keterangan |
|---|---|
| `extracted/tools/rebuild_apk.py` | Penulis ulang APK: semua penggantian byte sama panjang, penulisan ZIP + `resources.arsc` aligned, gate verifikasi |
| `extracted/tools/icons_from_art.py` | Generator ikon, adaptive icon, banner TV, ikon notifikasi dari artwork 1024×1024 |
| `extracted/tools/axml.py` | Penulis/penyunting binary AXML (dipakai untuk ikon notifikasi) |
| `extracted/tools/patch_manifest.py` | Patch manifest (package, label, versi) |
| `extracted/tools/xmltree2xml.py`, `make_icons.py` | Utilitas bantu |
| `extracted/artwork/icon-source.png` | Artwork sumber ikon (1024×1024) |
| `extracted/README.md` | Dokumentasi teknis lengkap hasil rebrand |
| `extracted/xml/`, `extracted/xmltree/` | Manifest & resource hasil decode untuk referensi |
| `build/artwork/` | Preview ikon/banner hasil generator |

## Build

Butuh: Python 3, `apksigner`, `aapt2`, `unzip`. Tanpa Pillow/ImageMagick (resampler murni Python).

```sh
# 1. ikon (butuh extracted/apk/ hasil decode — tidak di repo)
python3 extracted/tools/icons_from_art.py extracted/apk build/artwork

# 2. tulis ulang APK dari base APK asli
python3 extracted/tools/rebuild_apk.py <base.apk> extracted/apk build/DEVILL-VPN-unsigned.apk

# 3. tanda tangan
apksigner sign --ks build/devill.jks --ks-key-alias devill \
  --ks-pass pass:*** --key-pass pass:*** \
  --out build/DEVILL-VPN-1.0.0.apk build/DEVILL-VPN-unsigned.apk

# 4. verifikasi
apksigner verify --print-certs build/DEVILL-VPN-1.0.0.apk
unzip -t build/DEVILL-VPN-1.0.0.apk
```

`rebuild_apk.py` menolak build kalau masih ada string `shivaay` di luar
daftar putih (nama class Java `com.shivaay.firefoxvpn.*` + JNI `Tun2Socks`,
yang tidak bisa diubah tanpa source).

## Update otomatis

Fitur "Cek update" di binary menunjuk ke repo ini:

```
https://api.github.com/repos/Dhany85/DEVILL-VPN-Releases-APK/releases/latest
https://github.com/Dhany85/DEVILL-VPN-Releases-APK/releases
https://raw.githubusercontent.com/Dhany85/DEVILL-VPN-Releases-APK/HEAD/.github/updates.json
```

Nama owner/repo sudah tertanam di `libapp.so` dan panjangnya harus tetap
31 karakter. Mengganti nama repo = rebuild APK, bukan sekadar rename di GitHub.

Rilis baru: buat Release dengan tag `v1.0.1` dan lampirkan file
`DEVILL-VPN-1.0.1.apk`. Jangan commit APK ke repo (ada di `.gitignore`).

## Lisensi & disclaimer

Repo ini hanya berisi skrip patching dan artwork. Kode aplikasi asli dan
APK dasarnya tidak disertakan. Aplikasi hasil build adalah klien pihak ketiga
yang tidak berafiliasi dengan Mozilla; "Firefox" dan "Mozilla" adalah merek
terdaftar pemiliknya. Pakai untuk diri sendiri, bukan untuk distribusi publik.
