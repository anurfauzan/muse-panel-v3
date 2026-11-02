# Muse Panel v3

Panel monitoring ringan untuk Hermes, 9Router, dan ANVL Tracker.
Stdlib Python saja, tanpa dependensi, tanpa systemd, tanpa sudo.
Perkiraan RAM panel: ~15–25 MB. Dua thread saja (sampler + monitor),
polling UI 10 detik, grafik 1 jam terakhir.

## Yang diperbaiki dari v2

- **Stop aman:** membunuh PID yang tepat (SIGTERM, lalu SIGKILL kalau
  masih hidup), bukan `pkill -f` yang polanya lebar.
- **Riwayat tahan restart panel:** kejadian restart/mati/nyala disimpan
  ke `events.json` (maks 20 per layanan), jadi tidak hilang saat panel
  di-restart atau VM reboot.
- **Python ketemu sendiri:** `run.sh` mencari `python3.14` di PATH, lalu
  python3.14 bawaan VM Muse, lalu `python3` biasa. Di VM Muse, PATH
  juga ditambah `~/.local/bin` supaya perintah `hermes` ketemu dari cron.
- **Config portabel:** path di config boleh pakai `$HOME`, jadi satu
  config bisa dipakai di VM Lynn maupun VM Puki selama layout
  workspace-nya sama.
- **Token tidak dicetak:** token tidak pernah muncul di terminal/log.
  Lihat sendiri di `config.json` (mode 600).
- **Token placeholder ditolak:** server tidak mau jalan kalau token
  masih `CHANGE_ME_TOKEN`.
- **Status lebih lengkap:** uptime tiap layanan, 5 kejadian terakhir,
  disk, load, uptime host, dan uptime panel.
- **Log fleksibel:** `?lines=` 10–200 (default 80), file log yang tidak
  ada dilaporkan jelas, bukan kosong misterius.
- **Pola 9Router lebih sempit:** `custom-server.js`, bukan `next-server`
  yang bisa kena proses Next.js lain.
- **Port bentrok jelas:** kalau 8080 sudah dipakai, server berhenti
  dengan pesan yang bisa dimengerti, bukan traceback panjang.
- **Peringatan watchdog di UI:** tiap layanan menampilkan catatan bahwa
  watchdog cron tetap jalan.

## Install manual (tanpa sudo)

1. Salin folder `muse-panel` ke VM yang dituju, misalnya
   `~/muse-panel` atau `~/workspace/muse-panel`.
2. Masuk ke folder itu, jalankan sekali:
   ```
   bash run.sh
   ```
   Jalankan pertama ini hanya membuat `config.json` dari contoh
   (token acak, mode 600), lalu berhenti. Cek/edit path di
   `config.json` kalau layout di VM itu berbeda.
3. Jalankan lagi untuk start panel:
   ```
   bash run.sh
   ```
4. Supaya panel hidup terus, pasang di cron (tiap 5 menit, seperti
   watchdog lain). Ganti path-nya dengan path asli:
   ```
   */5 * * * * bash /home/hatch/muse-panel/run.sh
   ```
   `run.sh` idempoten: kalau panel sudah jalan, dia langsung keluar
   tanpa start duplikat.
5. Buka panel. Panel hanya bind `127.0.0.1:8080` di VM itu, jadi dari
   HP pakai SSH forward, misalnya dari Termux:
   ```
   ssh -L 8080:localhost:8080 -p 2222 fauzan@localhost
   ```
   lalu buka `http://localhost:8080` di browser HP. Token ada di
   `config.json` di VM; pertama kali dibuka, panel akan minta token
   dan menyimpannya di localStorage browser itu.
   Alternatif: tambahkan forward `127.0.0.1:8080:localhost:8080` ke
   reverse tunnel yang sudah ada, lalu buka dari sisi HP.

## Peringatan penting: rebutan dengan watchdog

Watchdog cron Hermes/9Router (10 menit) dan ANVL (5 menit) tetap jalan
dan tetap berhak me-restart layanan. Akibatnya:

- Tombol **Stop** di panel hanya sementara: watchdog akan menyalakan
  lagi layanan itu, dan panel akan mencatatnya sebagai restart.
- Alert Telegram panel (kalau diisi) bisa dobel dengan laporan
  watchdog. Biarkan `telegram_token` kosong kalau tidak mau dobel.
- Kalau memang mau menghentikan layanan lama, jeda dulu cron
  watchdog-nya, baru Stop dari panel.

## Uninstall

```
pkill -f "muse-panel/server.py"
# hapus baris cron panel, lalu hapus folder panel
```

## Keamanan singkat

- Bind localhost saja, auth token per request (dibandingkan dengan
  `hmac.compare_digest`, jeda 1 detik kalau salah).
- Tidak ada sudo, tidak ada user sistem baru, panel jalan sebagai user
  biasa yang sama dengan layanannya.
- Jangan forward port 8080 ke publik tanpa proteksi tambahan (tidak
  ada HTTPS di panel ini). Token yang bocor = siapa pun bisa
  start/stop layanan: rotate dengan edit token di `config.json` lalu
  restart panel.
