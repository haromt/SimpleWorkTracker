import ctypes, time
import json
from datetime import datetime, date

print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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


DATA_FILE = "tracker_data.json"

def load_data():
    """Beolvassa a JSON fájl tartalmát, ha létezik, különben egy üres dict-et ad vissza."""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print(f"Figyelem: '{DATA_FILE}' tartalmát nem sikerült beolvasni. Üres adatokkal folytatjuk.")
        return {}

def save_daily_data(day_str, active_time, max_idle_time):
    """Elmenti a napi adatokat a JSON fájlba."""
    data = load_data()
    
    data[day_str] = {
        "active_seconds": active_time,
        "active_time_formatted": fmt(active_time),
        "max_idle_seconds": max_idle_time,
        "max_idle_time_formatted": fmt(max_idle_time),
    }
    
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"  Adatok mentve a '{DATA_FILE}' fájlba.")
    except Exception as e:
        print(f"Hiba a JSON fájl mentésekor: {e}")


idle_threshold_seconds = 60
poll_interval_seconds = 0.5
update_interval_seconds = 1.0

active_seconds_today = 0.0
max_idle_seconds_today = 0.0
last_print = 0.0
start_monotonic = time.monotonic()
current_day = date.today()
active_today = True

def fmt(s):
    s = int(s)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

print(f"💻 time measurement has started... (idle threshold: {idle_threshold_seconds}s)")
print("Exit: Ctrl+C")

while True:
    now = datetime.now()
    
    if date.today() != current_day:
        
        # DAILY SUMMARY OUTPUT és JSON MENTÉS
        
        yesterday_str = current_day.strftime('%Y-%m-%d')
        
        print("\n" + "="*50)
        print(f"[{yesterday_str} {current_day.strftime('%A')}] Daily Summary:")
        print(f"  Total 💻 Time: {fmt(active_seconds_today)}")
        print(f"  Max Idle Time: {fmt(max_idle_seconds_today)}")
        
        # JSON mentés a megelőző nap adataival
        save_daily_data(yesterday_str, active_seconds_today, max_idle_seconds_today)
        
        print("="*50 + "\n")
        
        current_day = date.today()
        active_seconds_today = 0.0
        max_idle_seconds_today = 0.0 # Fontos: resetelni a maximális tétlenségi időt is
        active_today = False
        start_monotonic = time.monotonic()
        last_print = 0.0

    idle_sec = get_idle_ms() / 1000.0
    
    # Csak akkor frissítjük a max idle-t, ha aktív nap van
    if active_today and idle_sec > max_idle_seconds_today:
        max_idle_seconds_today = idle_sec
        
    now_m = time.monotonic()
    delta = now_m - start_monotonic
    start_monotonic = now_m
    
    if idle_sec < idle_threshold_seconds:
        active_seconds_today += delta
        
        if not active_today:
            active_today = True
            max_idle_seconds_today = 0.0
    
    last_print += delta
    
    if last_print >= update_interval_seconds:
        last_print = 0.0
        
        max_idle_formatted = fmt(max_idle_seconds_today) 
        
        line = (
            f"[{now.strftime('%H:%M:%S')}] "
            f"Daily 💻 time: {fmt(active_seconds_today)}  "
            f"(idle: {int(idle_sec):d}s, "
            f"max idle: {max_idle_formatted}) "
        )
        print(line, end="\r", flush=True)
    
    time.sleep(poll_interval_seconds)
