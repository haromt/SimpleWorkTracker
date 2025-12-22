import ctypes, time
import json
from datetime import datetime, date, time as dtime
import configparser
import sys
import signal
import msvcrt
import os

# =========================
# ASCII BANNER
# =========================
os.system("cls" if os.name == "nt" else "clear")
def print_ascii_banner():
    banner = r"""
 _____ _                 _        _    _            _  _____              _             
/  ___(_)               | |      | |  | |          | ||_   _|            | |            
\ `--. _ _ __ ___  _ __ | | ___  | |  | | ___  _ __| | _| |_ __ __ _  ___| | _____ _ __ 
 `--. \ | '_ ` _ \| '_ \| |/ _ \ | |/\| |/ _ \| '__| |/ / | '__/ _` |/ __| |/ / _ \ '__|
/\__/ / | | | | | | |_) | |  __/ \  /\  / (_) | |  |   <| | | | (_| | (__|   <  __/ |   
\____/|_|_| |_| |_| .__/|_|\___|  \/  \/ \___/|_|  |_|\_\_/_|  \__,_|\___|_|\_\___|_|   
                  | |                                                                   
                  |_|                                                                   
"""
    print(banner)

print_ascii_banner()

# =========================
# FORMAT HELPERS
# =========================
def fmt(s):
    s = int(s)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

def fmt_signed(s):
    sign = "+" if s >= 0 else "-"
    s = abs(int(s))
    return f"{sign}{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

# =========================
# CONFIG
# =========================
config = configparser.ConfigParser()
config.read('tracker_config.ini')

DATA_FILE = config['TRACKER']['DATA_FILE']
idle_threshold_seconds = config.getfloat('TRACKER', 'IDLE_THRESHOLD_SECONDS')
poll_interval_seconds = config.getfloat('TRACKER', 'POLL_INTERVAL_SECONDS')
update_interval_seconds = config.getfloat('TRACKER', 'UPDATE_INTERVAL_SECONDS')
SAVE_INTERVAL_SECONDS = config.getint('TRACKER', 'SAVE_INTERVAL_SECONDS')

target_h = config.getint('TRACKER', 'ACTIVE_TIME_TARGET_HOURS')
target_m = config.getint('TRACKER', 'ACTIVE_TIME_TARGET_MINUTES')
ACTIVE_TIME_TARGET = target_h * 3600 + target_m * 60

PROGRESS_BAR_WIDTH = config.getint('TRACKER', 'PROGRESS_BAR_WIDTH')

start_h = config.getint('WORKTIME', 'WORKDAY_START_HOUR')
start_m = config.getint('WORKTIME', 'WORKDAY_START_MINUTE')
end_h = config.getint('WORKTIME', 'WORKDAY_END_HOUR')
end_m = config.getint('WORKTIME', 'WORKDAY_END_MINUTE')

WORKDAY_START = dtime(start_h, start_m)
WORKDAY_END   = dtime(end_h, end_m)

# =========================
# WINDOWS IDLE API
# =========================
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_idle_ms():
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(info))
    tick = kernel32.GetTickCount()
    idle = tick - info.dwTime
    if idle < 0:
        idle += 2**32
    return idle

# =========================
# UI HELPERS
# =========================
RED   = "\033[91m"
YEL   = "\033[93m"
GRN   = "\033[92m"
BLU   = "\033[34m"
RST   = "\033[0m"

def progress_bar(current, total, width):
    ratio = current / total if total else 0
    percent = int(ratio * 100)

    if ratio < 0.5:
        color = RED
    elif ratio < 0.8:
        color = YEL
    elif ratio < 1.0:
        color = GRN
    else:
        color = BLU

    filled = int(min(ratio, 1.0) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{color}[{bar}] {percent:3d}%{RST}"

def in_worktime(now):
    return WORKDAY_START <= now.time() <= WORKDAY_END

# =========================
# DATA STORAGE
# =========================
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_daily_data(day, active, max_idle, sum_idle, total):
    data = load_data()
    data[day] = {
        "active_seconds": active,
        "max_idle_seconds": max_idle,
        "sum_idle_seconds": sum_idle,
        "total_elapsed_seconds": total
    }
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# =========================
# START
# =========================

print(f"🚀 Started at: {datetime.now():%Y-%m-%d %H:%M:%S}")
print(f"⏱️ Idle threshold: {int(idle_threshold_seconds)}s")
print(f"🏢 Core time: {WORKDAY_START.strftime('%H:%M')} - {WORKDAY_END.strftime('%H:%M')}")
print(f"🎯 Target: {fmt(ACTIVE_TIME_TARGET)}")

current_day = date.today()

active_seconds = 0.0
max_idle_seconds = 0.0
sum_idle_seconds = 0.0

session_start = time.monotonic()
last_update = time.monotonic()
last_save = time.monotonic()

# =========================
# MAIN LOOP
# =========================
while True:
    now = datetime.now()
    now_m = time.monotonic()
    delta = now_m - last_update
    last_update = now_m

    idle_sec = get_idle_ms() / 1000.0

    if in_worktime(now):
        if idle_sec < idle_threshold_seconds:
            active_seconds += delta
        else:
            sum_idle_seconds += delta
            max_idle_seconds = max(max_idle_seconds, idle_sec) - idle_threshold_seconds

    if now_m - last_save >= SAVE_INTERVAL_SECONDS:
        total_elapsed = now_m - session_start
        save_daily_data(
            current_day.strftime('%Y-%m-%d'),
            active_seconds,
            max_idle_seconds,
            sum_idle_seconds,
            total_elapsed
        )
        last_save = now_m

    if now_m - session_start >= update_interval_seconds:
        elapsed = fmt(now_m - session_start)
        idle_str     = f"{int(idle_sec):4d}s"
        max_idle_str = f"{fmt(max_idle_seconds):>8}"
        sum_idle_str = f"{fmt(sum_idle_seconds):>8}"

        line = (
            f"⏳ {elapsed}  "
            f"💻 {fmt(active_seconds):>8}  "
            f"{progress_bar(active_seconds, ACTIVE_TIME_TARGET, PROGRESS_BAR_WIDTH)}  "
            f"🕒 idle: {idle_str}  "
            f"⬆ max idle: {max_idle_str}  "
            f"Σ idle: {sum_idle_str}"
        )

        print(line, end="\r", flush=True)

    time.sleep(poll_interval_seconds)
