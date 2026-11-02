#!/bin/bash
# Muse Panel v3 - launcher ringan, tanpa sudo, tanpa systemd.
# Idempoten: aman dipasang di cron tiap 5 menit seperti watchdog lain.
#  - Cari python: $PY dulu, lalu python3.14 di PATH, lalu python3.14
#    bawaan VM Muse (~/.hermes/...), lalu python3 biasa (buat VM Puki).
#  - PATH ditambah ~/.local/bin (hermes) dan folder python yang ketemu,
#    supaya perintah di config.json (hermes, python3.14) ketemu juga
#    saat panel dijalankan dari cron yang PATH-nya minim.
#  - Token TIDAK pernah dicetak ke terminal/log. Lihat config.json.
cd "$(dirname "$0")"
if [ -n "$PY" ]; then :;
elif command -v python3.14 >/dev/null 2>&1; then PY=python3.14;
elif [ -x "$HOME/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3.14" ]; then PY="$HOME/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3.14";
elif command -v python3 >/dev/null 2>&1; then PY=python3;
else echo "Python tidak ketemu. Set PY=/path/ke/python3"; exit 1; fi
export PATH="$HOME/.local/bin:$(dirname "$PY"):$PATH"
if [ ! -f config.json ]; then
  sed "s/CHANGE_ME_TOKEN/$($PY -c 'import secrets;print(secrets.token_hex(16))')/" config.example.json > config.json
  chmod 600 config.json
  echo "config.json dibuat. Cek/edit path layanan di dalamnya, lalu jalankan lagi."
  echo "Token ada di config.json (bukan di sini, sengaja tidak dicetak)."
  exit 0
fi
if grep -q CHANGE_ME_TOKEN config.json 2>/dev/null; then
  echo "Token di config.json masih placeholder. Isi token dulu, lalu jalankan lagi."
  exit 1
fi
pgrep -f "$PWD/server.py" >/dev/null && exit 0
setsid nohup "$PY" "$PWD/server.py" >> panel.log 2>&1 &
echo "Panel dimulai (log: panel.log). Buka http://127.0.0.1:8080 dari mesin yang sama."
