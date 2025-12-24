import ctypes
import time
import json
from datetime import datetime, date, time as dtime, timedelta
import configparser
import sys
import os
import atexit
import signal

try:
    import msvcrt
except ImportError:
    msvcrt = None

os.system("cls" if os.name == "nt" else "clear")

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\tracker_py_single_instance"

kernel32 = ctypes.windll.kernel32
mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
if not mutex:
    sys.exit(1)
if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
    sys.exit(0)

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

def fmt(s):
    s = int(s)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

def fmt_signed(s):
    s = int(s)
    sign = "+" if s >= 0 else "-"
    s = abs(s)
    return f"{sign}{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


config = configparser.ConfigParser()
config.read("tracker_config.ini")

DATA_FILE = config["TRACKER"]["DATA_FILE"]
idle_threshold_seconds = config.getfloat("TRACKER", "IDLE_THRESHOLD_SECONDS")
poll_interval_seconds = config.getfloat("TRACKER", "POLL_INTERVAL_SECONDS")
update_interval_seconds = config.getfloat("TRACKER", "UPDATE_INTERVAL_SECONDS")

SAVE_INTERVAL_SECONDS = 300

target_h = config.getint("TRACKER", "ACTIVE_TIME_TARGET_HOURS")
target_m = config.getint("TRACKER", "ACTIVE_TIME_TARGET_MINUTES")
ACTIVE_TIME_TARGET = target_h * 3600 + target_m * 60

PROGRESS_BAR_WIDTH = config.getint("TRACKER", "PROGRESS_BAR_WIDTH")

start_h = config.getint("WORKTIME", "WORKDAY_START_HOUR")
start_m = config.getint("WORKTIME", "WORKDAY_START_MINUTE")
end_h = config.getint("WORKTIME", "WORKDAY_END_HOUR")
end_m = config.getint("WORKTIME", "WORKDAY_END_MINUTE")

WORKDAY_START = dtime(start_h, start_m)
WORKDAY_END = dtime(end_h, end_m)

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

user32 = ctypes.windll.user32

def get_idle_ms():
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(info))
    tick = kernel32.GetTickCount()
    idle = tick - info.dwTime
    if idle < 0:
        idle += 2**32
    return idle

RED = "\033[91m"
YEL = "\033[93m"
GRN = "\033[92m"
BLU = "\033[34m"
RST = "\033[0m"
GRY = "\033[90m"

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

def progress_smile(current, total):
    ratio = current / total if total else 0

    if ratio < 0.2:
        return "☹️"
    if ratio < 0.4:
        return "🙁"
    if ratio < 0.6:
        return "😐"
    if ratio < 0.8:
        return "🙂"
    if ratio < 1.0:
        return "😄"
    return "😁"

def in_worktime(now):
    return WORKDAY_START <= now.time() <= WORKDAY_END

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def write_json_atomic(path, obj):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def save_daily_data(day, active, max_idle, sum_idle, total):
    data = load_data()
    data[day] = {
        "active_seconds": float(active),
        "max_idle_seconds": float(max_idle),
        "sum_idle_seconds": float(sum_idle),
        "total_elapsed_seconds": float(total)
    }
    write_json_atomic(DATA_FILE, data)

def load_today_state(day_str):
    data = load_data()
    d = data.get(day_str)
    if not isinstance(d, dict):
        return 0.0, 0.0, 0.0, 0.0

    active = float(d.get("active_seconds", 0.0) or 0.0)
    max_idle = float(d.get("max_idle_seconds", 0.0) or 0.0)
    sum_idle = float(d.get("sum_idle_seconds", 0.0) or 0.0)
    total = float(d.get("total_elapsed_seconds", 0.0) or 0.0)
    return active, max_idle, sum_idle, total

def weekday_hu(d):
    names = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"]
    return names[d.weekday()]

def restart_program():
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def print_last_5_days_report():
    data = load_data()
    days = [date.today() - timedelta(days=i) for i in range(1, 6)]
    rows = []

    for d in (days):
        ds = d.strftime("%Y-%m-%d")
        label = f"{ds} {weekday_hu(d)}"
        entry = data.get(ds)

        if isinstance(entry, dict):
            a = float(entry.get("active_seconds", 0.0) or 0.0)
            mi = float(entry.get("max_idle_seconds", 0.0) or 0.0)
            si = float(entry.get("sum_idle_seconds", 0.0) or 0.0)
            te = float(entry.get("total_elapsed_seconds", 0.0) or 0.0)
            rows.append((label, fmt(a), fmt(mi), fmt(si), fmt(te)))
        else:
            rows.append((label, "-", "-", "-", "-"))

    headers = ("last 5 days", "work", "max idle", "Σ idle", "Σ ")
    widths = (
        max(len(headers[0]), max(len(r[0]) for r in rows)),
        max(len(headers[1]), max(len(r[1]) for r in rows)),
        max(len(headers[2]), max(len(r[2]) for r in rows)),
        max(len(headers[3]), max(len(r[3]) for r in rows)),
        max(len(headers[4]), max(len(r[4]) for r in rows)),
    )

    def sep():
        return "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def row(cells):
        return "| " + " | ".join(f"{c:<{w}}" for c, w in zip(cells, widths)) + " |"
    print("📊")
    print(sep())
    print(row(headers))
    print(sep())
    for (d, r) in zip(days, rows):
      if d.weekday() >= 5:
        print(f"{GRY}{row(r)}{RST}")
      else:
        print(row(r))
    print(sep())
    print()

print_last_5_days_report()

print(f"🚀 Started at: {datetime.now():%Y-%m-%d %H:%M:%S}")
print(f"⏱️ Idle threshold: {int(idle_threshold_seconds)}s")
print(f"🏢 Core time: {WORKDAY_START.strftime('%H:%M')} - {WORKDAY_END.strftime('%H:%M')}")
print(f"🎯 Target: {fmt(ACTIVE_TIME_TARGET)}")
print(f"💾 Autosave: {SAVE_INTERVAL_SECONDS}s")
print()

current_day = date.today()
day_str = current_day.strftime("%Y-%m-%d")

active_seconds, max_idle_seconds, sum_idle_seconds, total_elapsed_saved = load_today_state(day_str)

now_m0 = time.monotonic()
session_start = now_m0 - total_elapsed_saved
last_update = now_m0
last_save = now_m0
day_closed = False
idle_run_seconds = 0.0
show_active_minus_target = False

def save_and_exit():
    try:
        save_daily_data(
            day_str,
            active_seconds,
            max_idle_seconds,
            sum_idle_seconds,
            time.monotonic() - session_start
        )
    except:
        pass

atexit.register(save_and_exit)
signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 1
CTRL_CLOSE_EVENT = 2
CTRL_LOGOFF_EVENT = 5
CTRL_SHUTDOWN_EVENT = 6

def _console_handler(ctrl_type):
    if ctrl_type in (CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
        save_and_exit()
        os._exit(0)
    return False

handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
console_handler = handler_type(_console_handler)
kernel32.SetConsoleCtrlHandler(console_handler, True)

while True:
    now = datetime.now()
    now_m = time.monotonic()

    if msvcrt and msvcrt.kbhit():
        ch = msvcrt.getch()
        if ch == b"\x04":
            show_active_minus_target = not show_active_minus_target

    if now.date() != current_day and not day_closed:
        day_closed = True
        save_daily_data(
            day_str,
            active_seconds,
            max_idle_seconds,
            sum_idle_seconds,
            now_m - session_start
        )
        try:
            restart_program()
        except:
            current_day = now.date()
            day_str = current_day.strftime("%Y-%m-%d")
            active_seconds, max_idle_seconds, sum_idle_seconds, total_elapsed_saved = load_today_state(day_str)
            session_start = now_m - total_elapsed_saved
            last_update = now_m
            last_save = now_m
            idle_run_seconds = 0.0
            day_closed = False

    delta = now_m - last_update
    last_update = now_m

    idle_sec = get_idle_ms() / 1000.0

    if in_worktime(now):
        if idle_sec < idle_threshold_seconds:
            active_seconds += delta
            idle_run_seconds = 0.0
        else:
            sum_idle_seconds += delta
            idle_run_seconds += delta
            if idle_run_seconds > max_idle_seconds:
                max_idle_seconds = idle_run_seconds
    else:
        idle_run_seconds = 0.0

    if now_m - last_save >= SAVE_INTERVAL_SECONDS:
        save_daily_data(
            day_str,
            active_seconds,
            max_idle_seconds,
            sum_idle_seconds,
            now_m - session_start
        )
        last_save = now_m

    if now_m - session_start >= update_interval_seconds:
        elapsed = fmt(now_m - session_start)
        active_display = fmt(active_seconds)
        if show_active_minus_target:
            active_display = fmt_signed(active_seconds - ACTIVE_TIME_TARGET)
        idle_str = f"{int(idle_sec):4d}s"
        max_idle_str = f"{fmt(max_idle_seconds):>8}"
        sum_idle_str = f"{fmt(sum_idle_seconds):>8}"

        line = (
            f"⏳ {elapsed}  "
            f"💻 {active_display:>9}  "
            f"{progress_bar(active_seconds, ACTIVE_TIME_TARGET, PROGRESS_BAR_WIDTH)} "
            f"{progress_smile(active_seconds, ACTIVE_TIME_TARGET)}  "
            f"🕒 idle: {idle_str}  "
            f"⬆ max idle: {max_idle_str}  "
            f"Σ idle: {sum_idle_str}"
        )

        print(line, end="\r", flush=True)

    time.sleep(poll_interval_seconds)
