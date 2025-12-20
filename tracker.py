import ctypes, time
import json
from datetime import datetime, date, time as dtime, timedelta
import configparser
import sys
import signal
import msvcrt
import os

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
    sign = "+" if s >= 0 else "-"
    s = abs(int(s))
    return f"{sign}{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

def restart_program():
    print("\n🔁 Restarting program...")
    time.sleep(1)
    os.system('cls' if os.name == 'nt' else 'clear')
    python = sys.executable
    os.execl(python, python, *sys.argv)


def save_on_exit(signum=None, frame=None):
    print("\n⚠️ Program termination initiated. Saving data...")
    global active_seconds_today, max_idle_seconds_today, sum_idle_seconds_today, current_day, total_elapsed_seconds_at_start, session_start_monotonic
    now_m = time.monotonic()
    total_elapsed_seconds = total_elapsed_seconds_at_start + (now_m - session_start_monotonic)
    day_str = current_day.strftime('%Y-%m-%d')
    save_daily_data(
        day_str,
        active_seconds_today,
        max_idle_seconds_today,
        sum_idle_seconds_today,
        total_elapsed_seconds,
        silent=True
    )
    print("✅ Data successfully saved. Exiting.")
    sys.exit(0)

signal.signal(signal.SIGINT, save_on_exit)

config = configparser.ConfigParser()
config.read('tracker_config.ini')
try:
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
    WORKDAY_END = dtime(end_h, end_m)
except KeyError as e:
    print(f"ERROR: Missing key in config file: {e}. Check 'tracker_config.ini' file!")
    sys.exit(1)
except Exception as e:
    print(f"ERROR while reading config file: {e}")
    sys.exit(1)

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

MOOD_LEVELS = [
    (0.10, "😢"),
    (0.20, "😞"),
    (0.30, "🙁"),
    (0.40, "😐"),
    (0.50, "🙂"),
    (0.60, "😊"),
    (0.70, "😄"),
    (0.85, "😁"),
    (1.00, "🤩"),
]

RED_COLOR   = "\033[91m"
YELLOW_COLOR= "\033[93m"
GREEN_COLOR = "\033[92m"
BLUE_COLOR  = "\033[34m"
RESET_COLOR = "\033[0m"

def progress_bar(current, total, width=PROGRESS_BAR_WIDTH):
    ratio = current / total if total else 0
    percent = int(ratio * 100)
    if ratio < 0.5:
        color = RED_COLOR
    elif ratio < 0.8:
        color = YELLOW_COLOR
    elif ratio < 1.0:
        color = GREEN_COLOR
    else:
        color = BLUE_COLOR
    filled = int(min(ratio, 1.0) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{color}[{bar}] {percent:3d}%{RESET_COLOR}"

def mood_smiley(current, target):
    ratio = current / target if target else 0
    for level, emoji in MOOD_LEVELS:
        if ratio <= level:
            return emoji
    return "🔥"

def in_worktime(now: datetime):
    t = now.time()
    return WORKDAY_START <= t <= WORKDAY_END

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_daily_data(day_str, active_time, max_idle_time, sum_idle_time, total_elapsed_time, silent=False):
    data = load_data()
    data[day_str] = {
        "active_seconds": active_time,
        "active_time_formatted": fmt(active_time),
        "max_idle_seconds": max_idle_time,
        "max_idle_time_formatted": fmt(max_idle_time),
        "sum_idle_seconds": sum_idle_time,
        "sum_idle_time_formatted": fmt(sum_idle_time),
        "total_elapsed_seconds": total_elapsed_time,
        "total_elapsed_time_formatted": fmt(total_elapsed_time),
    }
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        if not silent:
            print(f"\n💾 Data saved to '{DATA_FILE}'.")
    except Exception as e:
        print(f"\n Error saving JSON file: {e}")

def load_initial_data(today_date):
    data = load_data()
    today_str = today_date.strftime('%Y-%m-%d')
    if today_str in data:
        today_data = data[today_str]
        loaded_active = today_data.get("active_seconds", 0.0)
        loaded_max_idle = today_data.get("max_idle_seconds", 0.0)
        loaded_sum_idle = today_data.get("sum_idle_seconds", 0.0)
        loaded_total_elapsed = today_data.get("total_elapsed_seconds", 0.0)
        print(f"📂 Data loaded for {today_str}. Continuing...")
        return loaded_active, loaded_max_idle, loaded_sum_idle, loaded_total_elapsed
    return 0.0, 0.0, 0.0, 0.0

print(f"🚀 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"⏱️ Monitoring activity... Idle threshold: {int(idle_threshold_seconds)}s")
print(f"\033[43m\033[30m🏢 Core Time: {WORKDAY_START.strftime('%H:%M')} - {WORKDAY_END.strftime('%H:%M')} \033[0m")
print(f"📊 100% target: {fmt(ACTIVE_TIME_TARGET)}")

def print_last_5_days():
    data = load_data()
    if not data:
        print("\n📅 Last 5 days: no data.\n")
        return

    today_str = date.today().strftime('%Y-%m-%d')
    days = sorted(data.keys(), reverse=True)
    last_days = [d for d in days if d != today_str][:5]

    if not last_days:
        print("\n📅 Last 5 days: no previous days to show.\n")
        return

    rows = []
    for d in last_days:
        day = data[d]
        active = day.get("active_time_formatted", fmt(day.get("active_seconds", 0)))
        total = day.get("total_elapsed_time_formatted", fmt(day.get("total_elapsed_seconds", 0)))
        sum_idle = day.get("sum_idle_time_formatted", fmt(day.get("sum_idle_seconds", 0)))
        max_idle = day.get("max_idle_time_formatted", fmt(day.get("max_idle_seconds", 0)))
        rows.append({
            "Date": d,
            "Active": active,
            "Max idle": max_idle,
            "Sum idle": sum_idle,
            "Total": total
        })

    headers = ["Date", "Active", "Max idle", "Sum idle", "Total"]
    widths = []
    for h in headers:
        max_len = len(h)
        for r in rows:
            if len(str(r[h])) > max_len:
                max_len = len(str(r[h]))
        widths.append(max_len)

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header_line = "|" + "|".join(" " + headers[i].ljust(widths[i]) + " " for i in range(len(headers))) + "|"

    print("\n📅 Last 5 days:\n")
    print(sep)
    print(header_line)
    print(sep)
    for r in rows:
        line = "|" + "|".join(" " + str(r[headers[i]]).ljust(widths[i]) + " " for i in range(len(headers))) + "|"
        print(line)
    print(sep)
    print()

current_day = date.today()
(active_seconds_today,
 max_idle_seconds_today,
 sum_idle_seconds_today,
 total_elapsed_seconds_at_start) = load_initial_data(current_day)

print_last_5_days()

active_today = active_seconds_today > 0.0
last_print = 0.0
session_start_monotonic = time.monotonic()
last_save_time = time.monotonic()
start_monotonic = time.monotonic()
was_in_core_time = in_worktime(datetime.now())

TOGGLE_KEY = b'\x04'
show_delta = False

try:
    while True:
        now = datetime.now()
        now_m = time.monotonic()
        total_elapsed_seconds = total_elapsed_seconds_at_start + (now_m - session_start_monotonic)

        if date.today() != current_day:
            day_str = current_day.strftime('%Y-%m-%d')
            print("\n" + "="*60)
            save_daily_data(
                day_str,
                active_seconds_today,
                max_idle_seconds_today,
                sum_idle_seconds_today,
                total_elapsed_seconds,
                silent=False
            )
            print("\n📅 New day detected. 🔁 Restarting...")
            restart_program()

        delta = now_m - start_monotonic
        start_monotonic = now_m

        idle_sec = get_idle_ms() / 1000.0
        is_in_worktime = in_worktime(now)

        if was_in_core_time and not is_in_worktime and now.time() >= WORKDAY_END:
            day_str = current_day.strftime('%Y-%m-%d')
            print("\n🏁 Core time finished. 🔁 Restarting...")
            save_daily_data(
                day_str,
                active_seconds_today,
                max_idle_seconds_today,
                sum_idle_seconds_today,
                total_elapsed_seconds,
                silent=False
            )
            restart_program()

        if active_today and is_in_worktime and idle_sec > max_idle_seconds_today and idle_sec > idle_threshold_seconds:
            max_idle_seconds_today += idle_sec

        if active_today and is_in_worktime and idle_sec > idle_threshold_seconds:
            sum_idle_seconds_today += delta

        if idle_sec < idle_threshold_seconds:
            active_seconds_today += delta
            if not active_today:
                active_today = True

        last_print += delta

        if now_m - last_save_time >= SAVE_INTERVAL_SECONDS:
            save_daily_data(
                current_day.strftime('%Y-%m-%d'),
                active_seconds_today,
                max_idle_seconds_today,
                sum_idle_seconds_today,
                total_elapsed_seconds,
                silent=True
            )
            last_save_time = now_m
            print(f"💾 {fmt(total_elapsed_seconds)} autosaved.", end="\r", flush=True)

        if last_print >= update_interval_seconds:
            last_print = 0.0

            active_progress = progress_bar(
                active_seconds_today,
                ACTIVE_TIME_TARGET
            )
            mood = mood_smiley(
                active_seconds_today,
                ACTIVE_TIME_TARGET
            )
            elapsed_time_formatted = fmt(total_elapsed_seconds)

            try:
                while msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch.lower() == TOGGLE_KEY:
                        show_delta = not show_delta
            except Exception:
                pass

            if show_delta:
                delta_sec = int(active_seconds_today - ACTIVE_TIME_TARGET)
                daily_str = fmt_signed(delta_sec)
            else:
                daily_str = fmt(int(active_seconds_today))

            line = (
                f"⏳ {elapsed_time_formatted}  "
                f"💻 {daily_str}  "
                f"{active_progress} {mood}  "
                f"🕒 idle: {int(idle_sec)}s  "
                f"⬆ max idle: {fmt(max_idle_seconds_today)}  "
                f"Σ idle: {fmt(sum_idle_seconds_today)}"
            )
            print(line, end="\r", flush=True)

        was_in_core_time = is_in_worktime

        time.sleep(poll_interval_seconds)

except KeyboardInterrupt:
    save_on_exit()
