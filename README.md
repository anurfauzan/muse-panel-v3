# muse-panel-v3

Panel monitoring ringan untuk Hermes, 9Router, dan ANVL Tracker.
Stdlib Python saja, tanpa dependensi, tanpa systemd, tanpa sudo.
Perkiraan RAM panel: ~15–25 MB.

Kode panel ada di folder `muse-panel/`. Panduan lengkap (instalasi,
konfigurasi, keamanan) ada di `muse-panel/README.md`.

## Mulai cepat

```bash
cd muse-panel
bash run.sh        # pertama kali: membuat config.json lalu berhenti
# isi path layanan + ganti token di config.json, lalu:
bash run.sh        # menjalankan panel
```

Panel mengikat localhost port 8080 dan minta token di tiap request.

## Catatan keamanan

- Jangan pernah commit `config.json` — file itu berisi token panel dan
  (opsional) token Telegram. File tersebut sudah masuk `.gitignore`.
- Yang dicommit hanya `config.example.json` (token placeholder).
- Panel ini hanya untuk jaringan lokal/terowongan SSH pribadi, bukan
  untuk diekspos ke internet publik.
