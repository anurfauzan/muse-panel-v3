#!/usr/bin/env python3
"""Muse Panel v3 - ringan, stdlib-only, tanpa systemd, tanpa sudo.

Perubahan dari v2:
- Stop membunuh PID yang tepat (SIGTERM lalu SIGKILL), bukan pkill -f
  yang polanya lebar dan bisa kena proses lain.
- Riwayat restart/mati disimpan ke events.json (tahan restart panel),
  dibatasi 20 kejadian per layanan.
- Status menambah uptime layanan, info sistem (disk, load, uptime host),
  dan uptime panel sendiri.
- Token placeholder ditolak mentah-mentah (tidak mau jalan).
- Path di config boleh pakai $HOME, jadi satu config bisa dipakai di
  VM Lynn maupun VM Puki selama layout workspace-nya sama.
- Log: jumlah baris bisa diatur (?lines=, dibatasi 10..200).
"""
import json, os, shutil, signal, subprocess, sys, threading, time, hmac
import urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

D = os.path.dirname(os.path.abspath(__file__))
STARTED = time.time()
EVENTS_FILE = os.path.join(D, "events.json")

def expand(v):
    return os.path.expandvars(os.path.expanduser(v)) if isinstance(v, str) else v

try:
    C = json.load(open(os.path.join(D, "config.json")))
except FileNotFoundError:
    print("config.json tidak ada. Jalankan run.sh dulu (dia yang membuatnya).", file=sys.stderr)
    sys.exit(2)
if not C.get("token") or C["token"] == "CHANGE_ME_TOKEN":
    print("Token masih placeholder. Isi token di config.json dulu, lalu jalankan lagi.", file=sys.stderr)
    sys.exit(2)

SV = {}
for s in C["services"]:
    s = dict(s)
    for k in ("cmd", "cwd", "log"):
        if s.get(k):
            s[k] = expand(s[k])
    SV[s["name"]] = s

HIST, STATE, QUIET = [], {}, {}

def load_events():
    try:
        d = json.load(open(EVENTS_FILE))
        return {k: v[-20:] for k, v in d.items() if isinstance(v, list)}
    except Exception:
        return {}

def save_events():
    try:
        tmp = EVENTS_FILE + ".tmp"
        json.dump({n: STATE[n]["ev"] for n in STATE}, open(tmp, "w"))
        os.replace(tmp, EVENTS_FILE)
    except Exception:
        pass

def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, timeout=15)

def pid_of(s):
    p = sh("pgrep", "-f", s["match"]).stdout.split()
    return int(p[0]) if p else None

def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def info(pid):
    r = sh("ps", "-o", "rss=,etimes=", "-p", str(pid)).stdout.split()
    return (round(int(r[0]) / 1024), int(r[1])) if len(r) == 2 else (None, None)

def start(s):
    if pid_of(s):
        return False, "sudah berjalan"
    try:
        subprocess.Popen(s["cmd"], shell=True, cwd=s.get("cwd"),
                         stdin=subprocess.DEVNULL,
                         stdout=open(s.get("log", "/dev/null"), "ab"),
                         stderr=subprocess.STDOUT, start_new_session=True)
        return True, ""
    except Exception as e:
        return False, str(e)

def stop(s):
    """Matikan layanan lewat PID-nya (plus process group-nya kalau ada).

    Layanan yang di-start panel jalan di session sendiri, jadi killpg
    juga mematikan anak prosesnya (mis. shell pembungkus + proses utama).
    Jauh lebih aman dari pkill -f yang bisa kena proses lain.
    """
    p = pid_of(s)
    if not p:
        return True, "sudah mati"
    def sig(sig):
        try:
            os.killpg(p, sig)
        except Exception:
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
    sig(signal.SIGTERM)
    for _ in range(5):
        time.sleep(1)
        if not pid_alive(p):
            return True, ""
    sig(signal.SIGKILL)
    time.sleep(1)
    return (not pid_alive(p)), ("" if not pid_alive(p) else "proses masih hidup")

def tg(msg):
    t, c = C.get("telegram_token"), C.get("telegram_chat_id")
    if not t or not c:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": c, "text": msg}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{t}/sendMessage", data, timeout=10)
    except Exception:
        pass

def cpu_times():
    v = list(map(int, open("/proc/stat").readline().split()[1:]))
    return sum(v), v[3] + v[4]

def sampler():
    t0, i0 = cpu_times()
    while True:
        time.sleep(10)
        t1, i1 = cpu_times()
        cpu = 100 * (1 - (i1 - i0) / max(t1 - t0, 1))
        t0, i0 = t1, i1
        m = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
        ram = 100 * (1 - m["MemAvailable"] / m["MemTotal"])
        HIST.append([int(time.time()), round(ram, 1), round(cpu, 1)])
        del HIST[:-360]

def record(n, kind, pid):
    STATE[n]["ev"] = (STATE[n]["ev"] + [{"t": int(time.time()), "type": kind, "pid": pid}])[-20:]
    save_events()

def monitor():
    ev = load_events()
    for n, s in SV.items():
        STATE[n] = {"pid": pid_of(s), "ev": ev.get(n, [])}
    while True:
        time.sleep(15)
        now = time.time()
        for n, s in SV.items():
            st, p = STATE[n], pid_of(s)
            if p != st["pid"] and now > QUIET.get(n, 0):
                if p is None:
                    record(n, "died", None)
                    tg(f"{n} mati (proses hilang)")
                elif st["pid"] is None:
                    record(n, "started", p)
                else:
                    record(n, "restart", p)
                    k = len([x for x in st["ev"] if x["type"] == "restart" and now - x["t"] < 3600])
                    tg(f"{n} restart terdeteksi ({k}x dalam 1 jam)" + (" - terlalu sering, cek penyebabnya" if k > 2 else ""))
            st["pid"] = p

def system_info():
    try:
        du = shutil.disk_usage("/")
        disk = round(100 * (1 - du.free / du.total), 1)
    except Exception:
        disk = None
    try:
        load = round(os.getloadavg()[0], 2)
    except Exception:
        load = None
    try:
        host_up = int(float(open("/proc/uptime").read().split()[0]))
    except Exception:
        host_up = None
    return {"disk_pct": disk, "load1": load, "host_uptime_s": host_up,
            "panel_uptime_s": int(time.time() - STARTED)}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def send(self, code, body, ct="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def ok(self):
        good = hmac.compare_digest(self.headers.get("X-Token", ""), C["token"])
        if not good:
            time.sleep(1)
        return good
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self.send(200, open(os.path.join(D, "index.html"), "rb").read(), "text/html; charset=utf-8")
        if not self.ok():
            return self.send(401, {"error": "token salah"})
        if u.path == "/api/status":
            out, now = [], time.time()
            for n, s in SV.items():
                p = pid_of(s)
                mem, up = info(p) if p else (None, None)
                out.append({"name": n, "state": "active" if p else "failed",
                            "sub": f"pid {p}" if p else "tidak ada proses",
                            "mem_mb": mem, "uptime_s": up, "note": s.get("note", ""),
                            "restarts": len([x for x in STATE.get(n, {}).get("ev", []) if x["type"] == "restart" and now - x["t"] < 3600]),
                            "events": STATE.get(n, {}).get("ev", [])[-5:]})
            return self.send(200, {"services": out, "hist": HIST, "system": system_info()})
        if u.path == "/api/logs":
            n = parse_qs(u.query).get("name", [""])[0]
            try:
                lines = max(10, min(200, int(parse_qs(u.query).get("lines", ["80"])[0])))
            except Exception:
                lines = 80
            if n not in SV or not SV[n].get("log"):
                return self.send(404, {"error": "log tidak tersedia"})
            if not os.path.exists(SV[n]["log"]):
                return self.send(404, {"error": "file log tidak ada: " + SV[n]["log"]})
            r = sh("tail", "-n", str(lines), SV[n]["log"])
            return self.send(200, {"log": r.stdout or r.stderr})
        self.send(404, {"error": "tidak ditemukan"})
    def do_POST(self):
        if not self.ok():
            return self.send(401, {"error": "token salah"})
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        except Exception:
            return self.send(400, {"error": "data rusak"})
        n, a = b.get("name"), b.get("action")
        if self.path != "/api/action" or n not in SV or a not in ("start", "stop", "restart"):
            return self.send(400, {"error": "permintaan tidak valid"})
        s = SV[n]
        QUIET[n] = time.time() + 40
        ok, msg = True, ""
        if a in ("stop", "restart"):
            ok, msg = stop(s)
        if ok and a in ("start", "restart"):
            ok, msg = start(s)
        self.send(200, {"ok": ok, "msg": msg})

if __name__ == "__main__":
    threading.Thread(target=sampler, daemon=True).start()
    threading.Thread(target=monitor, daemon=True).start()
    try:
        ThreadingHTTPServer((C.get("bind", "127.0.0.1"), C.get("port", 8080)), H).serve_forever()
    except OSError as e:
        print(f"Gagal bind {C.get('bind', '127.0.0.1')}:{C.get('port', 8080)}: {e}", file=sys.stderr)
        print("Kemungkinan port sudah dipakai panel lain. Cek dengan: ss -tln | grep 8080", file=sys.stderr)
        sys.exit(1)
