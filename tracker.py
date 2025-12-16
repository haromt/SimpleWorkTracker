import ctypes, time
import json
from datetime import datetime, date, time as dtime
import configparser
import sys
import signal

def fmt(s):
    s = int(s)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

def save_on_exit(signum=None, frame=None):
    print("\n--- Program termination initiated. Saving data... ---")
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
    print("--- Data successfully saved. Exiting. ---")
    sys.exit(0)

signal.signal(signal.SIGINT, save_on_exit)

# ===================== CONFIGURATION LOADING =====================

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
    WORKDAY_END   = dtime(end_h, end_m)

except KeyError as e:
    print(f"ERROR: Missing key in config file: {e}. Check 'tracker_config.ini' file!")
    sys.exit(1)
except Exception as e:
    print(f"ERROR while reading config file: {e}")
    sys.exit(1)

# ===================== WINDOWS IDLE DETECTION =====================

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

# ===================== MOOD SCALE (10 STATES) =====================

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

# ===================== UTILS =====================

def progress_bar(current, total, width=PROGRESS_BAR_WIDTH):
    ratio = current / total
    filled = int(min(ratio, 1.0) * width)
    bar = "█" * filled + "░" * (width - filled)
    percent = int(ratio * 100)
    return f"[{bar}] {percent:3d}%"

def mood_smiley(current, target):
    ratio = current / target
    for level, emoji in MOOD_LEVELS:
        if ratio <= level:
            return emoji
    return "🔥"

def in_worktime(now: datetime):
    t = now.time()
    return WORKDAY_START <= t <= WORKDAY_END

# ===================== JSON HANDLING =====================

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
            print(f"\n  Data saved to '{DATA_FILE}'.")
    except Exception as e:
        print(f"\n  Error saving JSON file: {e}")

def load_initial_data(today_date):
    data = load_data()
    today_str = today_date.strftime('%Y-%m-%d')
    
    if today_str in data:
        today_data = data[today_str]
        
        loaded_active = today_data.get("active_seconds", 0.0)
        loaded_max_idle = today_data.get("max_idle_seconds", 0.0)
        loaded_sum_idle = today_data.get("sum_idle_seconds", 0.0)
        loaded_total_elapsed = today_data.get("total_elapsed_seconds", 0.0)
        
        print(f"Data loaded for {today_str}. Continuing...")
        print(f"  Active time: {fmt(loaded_active)}")
        
        return loaded_active, loaded_max_idle, loaded_sum_idle, loaded_total_elapsed
    
    return 0.0, 0.0, 0.0, 0.0

# ===================== STATE INITIALIZATION =====================

current_day = date.today()
(active_seconds_today, 
 max_idle_seconds_today, 
 sum_idle_seconds_today,
 total_elapsed_seconds_at_start) = load_initial_data(current_day)

active_today = active_seconds_today > 0.0

last_print = 0.0
session_start_monotonic = time.monotonic() 
last_save_time = time.monotonic() 

start_monotonic = time.monotonic()

# ===================== INITIAL PRINTS =====================

print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"working hours measurement has started... (idle threshold: {int(idle_threshold_seconds)}s)")
print(f"⏰ Workday Core Time: {WORKDAY_START.strftime('%H:%M')} - {WORKDAY_END.strftime('%H:%M')}")
print(f"📊 Progress Bar 100% Target: {fmt(ACTIVE_TIME_TARGET)}")
print(f"💾 Data will be saved every {SAVE_INTERVAL_SECONDS // 60} minutes.")
print("Exit: Ctrl+C")

# ===================== MAIN LOOP =====================

try:
    while True:
        now = datetime.now()
        now_m = time.monotonic()

        total_elapsed_seconds = total_elapsed_seconds_at_start + (now_m - session_start_monotonic)

        # --------- DAY CHANGE (SAVE & RESET) ---------
        if date.today() != current_day:
            yesterday_str = current_day.strftime('%Y-%m-%d')

            print("\n" + "="*60)
            print(f"[{yesterday_str}] Daily Summary:")
            print(f"  Total 💻 Time: {fmt(active_seconds_today)}")
            print(f"  Max Idle Time: {fmt(max_idle_seconds_today)}")
            print(f"  Sum Idle Time (worktime): {fmt(sum_idle_seconds_today)}")
            print("="*60 + "\n")

            save_daily_data(
                yesterday_str,
                active_seconds_today,
                max_idle_seconds_today,
                sum_idle_seconds_today,
                total_elapsed_seconds,
                silent=False 
            )

            current_day = date.today()
            active_seconds_today = 0.0
            max_idle_seconds_today = 0.0
            sum_idle_seconds_today = 0.0
            total_elapsed_seconds_at_start = 0.0
            active_today = False
            session_start_monotonic = now_m 
            start_monotonic = now_m
            last_print = 0.0
            last_save_time = now_m 

        # --------- IDLE CHECK & TIME CALCULATION ---------
        idle_sec = get_idle_ms() / 1000.0
        
        is_in_worktime = in_worktime(now) # Ellenőrizzük, hogy törzsidő van-e

        if active_today and is_in_worktime and idle_sec > max_idle_seconds_today:
            max_idle_seconds_today = idle_sec

        delta = now_m - start_monotonic
        start_monotonic = now_m

        if idle_sec < idle_threshold_seconds:
            active_seconds_today += delta
            if not active_today:
                active_today = True
                # A max idle időt CSAK akkor reseteljük, ha az aktivitás törzsidőben kezdődik/folytatódik
                if is_in_worktime:
                    max_idle_seconds_today = 0.0
        else:
            if is_in_worktime:
                sum_idle_seconds_today += delta

        last_print += delta

        # --------- INTERVAL SAVE ---------
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
            
            print(f"[{fmt(total_elapsed_seconds)}] Auto-Save OK.", end="\r", flush=True)


        # --------- PRINT (OVERWRITTEN LINE) ---------
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

            line = (
                f"[{elapsed_time_formatted}] "
                f"Daily 💻: {fmt(active_seconds_today)} "
                f"{active_progress} {mood}  "
                f"(idle: {int(idle_sec)}s, "
                f"max idle: {fmt(max_idle_seconds_today)}, "
                f"sum idle: {fmt(sum_idle_seconds_today)}) "
            )

            print(line, end="\r", flush=True)

        time.sleep(poll_interval_seconds)

except KeyboardInterrupt:
    save_on_exit()
