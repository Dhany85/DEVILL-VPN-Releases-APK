# Audit kesiapan rilis — DEVILL VPN 1.0.0

Build yang diaudit: `build/DEVILL-VPN-1.0.0.apk`
15.773.754 byte, SHA-256 `d33f1d83636da17b07d2200e491832b82a4597f8d5efb548a900d084b53afd59`
`com.devill.vpn`, versionCode 2001, minSdk 24, targetSdk 36, arm64-v8a.

**Kesimpulan: belum siap rilis publik / Play Store.**
Siap untuk dipakai pribadi dan dibagikan sebagai APK sideload.

---

## 1. Penghalang rilis (tidak bisa diselesaikan tanpa source)

| # | Temuan | Bukti | Dampak |
|---|---|---|---|
| B1 | Ini klien tidak resmi Mozilla VPN. Login otomatis ke `oauth.accounts.firefox.com` / `api.accounts.firefox.com`, ambil serverlist resmi dari `firefox.settings.services.mozilla.com/v1/buckets/main/collections/vpn-serverlist/records`, cek kuota "Guardian" | string di `libgojni.so` | Melanggar ToS Mozilla; akun pengguna bisa diblokir; server bisa berubah kapan saja |
| B2 | Ada solver proteksi bot: `fxa.solveFastlyChallenge`, `answerChallenge`, `solvePow`, `captchaSolver`, `installChallengeCookies`, "still HTTP 406 after %d solved challenges" | simbol Go `core/internal/fxa.*` | Sengaja menembus proteksi akses Mozilla (Fastly). Ini bukan fitur netral; risiko hukum dan alasan kuat penolakan store |
| B3 | Merek pihak ketiga masih ada di binary: "Firefox" 53×, "Mozilla" 144× (`libapp.so`); 38×/83× (`libgojni.so`); `https://vpn.mozilla.org`, "Firefox's built-in VPN", "Sign in with a Firefox Account" | scan string | "Firefox"/"Mozilla" merek terdaftar → komplain/takedown |
| B4 | Tanpa source code. Semua perubahan = patch byte di binary; repo `core` tidak tersedia (404) | — | Tidak bisa perbaiki bug, ubah UI, atau hapus B1–B3. "Update" hanya bisa mengganti APK, bukan mengembangkan app |
| B5 | Kunci tanda tangan self-signed hanya ada di perangkat ini (`build/devill.jks`) | — | Kunci hilang = tidak bisa update sama sekali; tidak ada Play App Signing |
| B6 | Kode Go `core` tanpa berkas lisensi; `NOTICES.Z` hanya memuat lisensi Flutter/pub | isi APK | Distribusi ulang tanpa lisensi = pelanggaran hak cipta pihak asli |

## 2. Risiko tinggi (bisa diperbaiki dengan patch)

| # | Temuan | Bukti | Saran |
|---|---|---|---|
| T1 | ~~`allowBackup=true`; token akun ikut cloud backup~~ **Sudah diperbaiki**: `allowBackup=false` dipaksa saat build | `aapt2 dump xmltree` → `allowBackup=false` | Selesai |
| T2 | `QUERY_ALL_PACKAGES` (untuk daftar app split-tunneling) | manifest | Play butuh deklarasi + justifikasi; sering ditolak. Untuk sideload tidak masalah |
| T3 | Field "Relay server" menerima Cloudflare Worker / `relay.php` milik pengguna. Login (email + password FxA) lewat relay itu kalau diisi | UI Settings + `relay.php` di libgojni | Nonaktifkan field, atau beri peringatan tegas di UI |
| T4 | Endpoint update sekarang `DhanyDevill/DEVILL-VPN-Releases` — repo belum ada (404) | `curl` → 404 | Buat repo + release `v1.0.1` (lihat bawah) |
| T5 | Hanya `arm64-v8a` | manifest/lib | Tidak bisa dipasang di perangkat 32-bit |
| T6 | Tidak ada privacy policy, tidak ada halaman store, tidak ada dokumentasi data yang dikirim (email, password, token, serverlist) | — | Wajib untuk Play; untuk sideload minimal taruh di repo |

## 3. Risiko menengah

- Ikon legacy 48–192 px masih gambar penuh (bingkai marble ikut) → di launcher lama terlihat kecil.
- Ikon notifikasi tetap silhouette perisai, bukan kepala iblis.
- Teks UI masih menyebut "Firefox Account" / "Mozilla" di banyak bahasa.
- Split tunneling, log `core/logs/`, dan routing TUN belum diuji runtime (butuh perangkat + akun Mozilla aktif).
- Belum ada uji DNS leak / kill switch / perilaku saat izin VPN ditolak.

## 4. Yang sudah benar

- Package unik `com.devill.vpn`, tidak menimpa `com.shivaay.firefoxvpn`.
- Tanda tangan v2 + v3 valid, `CN=DEVILL VPN`.
- ZIP + `resources.arsc` sehat (`unzip -t` bersih, `resources.arsc` STORED & aligned).
- Tidak ada sisa string "shivaay" di luar allowlist (nama class Java + JNI).
- Tidak ada SDK telemetri (Sentry/Firebase/Crashlytics: nihil).
- Token akun dienkripsi di disk (`accounts.encrypt` / `accounts.decrypt`).
- Tanpa `usesCleartextTraffic` dan tanpa network security config longgar → cleartext mati secara default (targetSdk 36).
- Permission minimal: INTERNET, ACCESS_NETWORK_STATE, FOREGROUND_SERVICE(_SPECIAL_USE), POST_NOTIFICATIONS, QUERY_ALL_PACKAGES.
- `CoreService` (VpnService) `exported=false` + `BIND_VPN_SERVICE`.

## 5. Jalur terdekat ke "layak dibagikan"

1. Buat repo `DhanyDevill/DEVILL-VPN-Releases` (nama harus persis, 19 karakter,
   sudah tertanam di binary) + release `v1.0.1` berisi APK → fitur cek update hidup.
2. ~~`allowBackup=false`~~ selesai (dipaksa oleh `rebuild_apk.py`).
3. Matikan field relay (patch di Dart AOT — perlu cari string UI-nya; belum tentu bisa).
4. Tulis privacy policy singkat di repo: data apa yang dikirim dan ke mana.
5. Umumkan sebagai klien tidak resmi, atau—lebih aman—jangan distribusikan publik.

Untuk Play Store: B1–B6 harus diselesaikan, dan itu berarti membangun ulang
aplikasi dari source sendiri (bukan klien Mozilla), bukan menambal APK ini.

---

Cara pakai cepat:

```
adb install -r DEVILL-VPN-1.0.0.apk     # atau tap APK di Download
```
