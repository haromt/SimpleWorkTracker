import ctypes, time
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

idle_threshold_seconds = 60
poll_interval_seconds = 0.5
update_interval_seconds = 1.0

active_seconds_today = 0.0
max_idle_seconds_today = 0.0
last_print = 0.0
start_monotonic = time.monotonic()
current_day = date.today()

def fmt(s):
    # Formázza a másodperceket ÓÓ:PP:MM formátumra
    s = int(s)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

print(f"Active time measurement has started... (idle threshold: {idle_threshold_seconds}s)")
print("Exit: Ctrl+C")

while True:
    now = datetime.now()
    if date.today() != current_day:
        current_day = date.today()
        active_seconds_today = 0.0
        max_idle_seconds_today = 0.0
        start_monotonic = time.monotonic()
        last_print = 0.0

    idle_sec = get_idle_ms() / 1000.0
    
    if idle_sec > max_idle_seconds_today:
        max_idle_seconds_today = idle_sec
        
    now_m = time.monotonic()
    delta = now_m - start_monotonic
    start_monotonic = now_m
    
    if idle_sec < idle_threshold_seconds:
        active_seconds_today += delta
    
    last_print += delta
    
    if last_print >= update_interval_seconds:
        last_print = 0.0
        
        max_idle_formatted = fmt(max_idle_seconds_today) 
        
        line = (
            f"[{now.strftime('%H:%M:%S')}] "
            f"Daily active time: {fmt(active_seconds_today)}  "
            f"(idle: {int(idle_sec):d}s, "
            f"max idle: {max_idle_formatted}) "
        )
        print(line, end="\r", flush=True)
    
    time.sleep(poll_interval_seconds)
