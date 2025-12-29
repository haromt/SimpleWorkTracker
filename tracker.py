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
user32 = ctypes.windll.user32

RED = "\033[91m"
YEL = "\033[93m"
GRN = "\033[92m"
BLU = "\033[34m"
RST = "\033[0m"
GRY = "\033[90m"

CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 1
CTRL_CLOSE_EVENT = 2
CTRL_LOGOFF_EVENT = 5
CTRL_SHUTDOWN_EVENT = 6


class SingleInstance:
    def __init__(self):
        self.mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not self.mutex:
            sys.exit(1)
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            sys.exit(0)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class IdleDetector:
    def __init__(self):
        self.info = LASTINPUTINFO()
        self.info.cbSize = ctypes.sizeof(LASTINPUTINFO)

    def get_idle_seconds(self):
        user32.GetLastInputInfo(ctypes.byref(self.info))
        tick = kernel32.GetTickCount()
        idle = tick - self.info.dwTime
        if idle < 0:
            idle += 2**32
        return idle / 1000.0


class AppConfig:
    def __init__(self, path="tracker_config.ini"):
        parser = configparser.ConfigParser()
        parser.read(path)
        self.data_file = parser["TRACKER"]["DATA_FILE"]
        self.idle_threshold_seconds = parser.getfloat("TRACKER", "IDLE_THRESHOLD_SECONDS")
        self.poll_interval_seconds = parser.getfloat("TRACKER", "POLL_INTERVAL_SECONDS")
        self.update_interval_seconds = parser.getfloat("TRACKER", "UPDATE_INTERVAL_SECONDS")
        self.save_interval_seconds = 300
        target_h = parser.getint("TRACKER", "ACTIVE_TIME_TARGET_HOURS")
        target_m = parser.getint("TRACKER", "ACTIVE_TIME_TARGET_MINUTES")
        self.active_time_target = target_h * 3600 + target_m * 60
        self.progress_bar_width = parser.getint("TRACKER", "PROGRESS_BAR_WIDTH")
        start_h = parser.getint("WORKTIME", "WORKDAY_START_HOUR")
        start_m = parser.getint("WORKTIME", "WORKDAY_START_MINUTE")
        end_h = parser.getint("WORKTIME", "WORKDAY_END_HOUR")
        end_m = parser.getint("WORKTIME", "WORKDAY_END_MINUTE")
        self.workday_start = dtime(start_h, start_m)
        self.workday_end = dtime(end_h, end_m)


class DataStore:
    def __init__(self, path):
        self.path = path

    def load_all(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def write_atomic(self, obj):
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def save_day(self, day_str, stats):
        data = self.load_all()
        data[day_str] = stats.to_dict()
        self.write_atomic(data)

    def load_day(self, day_str):
        data = self.load_all()
        entry = data.get(day_str)
        if not isinstance(entry, dict):
            return DailyStats()
        return DailyStats.from_dict(entry)

    def last_days(self, n):
        today = date.today()
        return [today - timedelta(days=i) for i in range(1, n + 1)]


class DailyStats:
    def __init__(
        self,
        active_seconds=0.0,
        max_idle_seconds=0.0,
        sum_idle_seconds=0.0,
        total_elapsed_seconds=0.0,
        first_active_time=None,
        last_active_time=None,
    ):
        self.active_seconds = float(active_seconds)
        self.max_idle_seconds = float(max_idle_seconds)
        self.sum_idle_seconds = float(sum_idle_seconds)
        self.total_elapsed_seconds = float(total_elapsed_seconds)
        self.first_active_time = first_active_time
        self.last_active_time = last_active_time
        self.idle_run_seconds = 0.0

    def update_on_active(self, delta, now):
        self.active_seconds += delta
        self.idle_run_seconds = 0.0
        if self.first_active_time is None:
            self.first_active_time = now
        self.last_active_time = now

    def update_on_idle(self, delta, in_worktime_flag):
        if in_worktime_flag:
            self.sum_idle_seconds += delta
            self.idle_run_seconds += delta
            if self.idle_run_seconds > self.max_idle_seconds:
                self.max_idle_seconds = self.idle_run_seconds
        else:
            self.idle_run_seconds = 0.0

    def sync_total_elapsed(self, session_start, now_m):
        self.total_elapsed_seconds = now_m - session_start

    def to_dict(self):
        entry = {
            "active_seconds": float(self.active_seconds),
            "max_idle_seconds": float(self.max_idle_seconds),
            "sum_idle_seconds": float(self.sum_idle_seconds),
            "total_elapsed_seconds": float(self.total_elapsed_seconds),
        }
        if self.first_active_time is not None:
            entry["first_active_time"] = self.first_active_time.isoformat()
        if self.last_active_time is not None:
            entry["last_active_time"] = self.last_active_time.isoformat()
        return entry

    @classmethod
    def from_dict(cls, d):
        active = float(d.get("active_seconds", 0.0) or 0.0)
        max_idle = float(d.get("max_idle_seconds", 0.0) or 0.0)
        sum_idle = float(d.get("sum_idle_seconds", 0.0) or 0.0)
        total = float(d.get("total_elapsed_seconds", 0.0) or 0.0)
        first_ts_str = d.get("first_active_time")
        last_ts_str = d.get("last_active_time")
        first_ts = datetime.fromisoformat(first_ts_str) if first_ts_str else None
        last_ts = datetime.fromisoformat(last_ts_str) if last_ts_str else None
        return cls(active, max_idle, sum_idle, total, first_ts, last_ts)


def fmt(seconds):
    s = int(seconds)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


def fmt_signed(seconds):
    s = int(seconds)
    sign = "+" if s >= 0 else "-"
    s = abs(s)
    return f"{sign}{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


def weekday_hu(d):
    names = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"]
    return names[d.weekday()]


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


def in_worktime(now, cfg):
    return cfg.workday_start <= now.time() <= cfg.workday_end


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


class ConsoleReport:
    def __init__(self, datastore):
        self.datastore = datastore

    def print_last_5_days(self):
        data = self.datastore.load_all()
        days = self.datastore.last_days(5)
        rows = []
        for d in days:
            ds = d.strftime("%Y-%m-%d")
            label = f"{ds} {weekday_hu(d)}"
            entry = data.get(ds)
            if isinstance(entry, dict):
                mi = float(entry.get("max_idle_seconds", 0.0) or 0.0)
                si = float(entry.get("sum_idle_seconds", 0.0) or 0.0)
                te = float(entry.get("total_elapsed_seconds", 0.0) or 0.0)
                first_ts_str = entry.get("first_active_time")
                last_ts_str = entry.get("last_active_time")
                activesecs = entry.get("active_seconds")
                work_span = "-"
                if first_ts_str and last_ts_str:
                    try:
                        first_ts = datetime.fromisoformat(first_ts_str)
                        last_ts = datetime.fromisoformat(last_ts_str)
                        if last_ts >= first_ts:
                            f_activesecs = fmt(activesecs)
                            work_span = f"{first_ts.strftime('%H:%M')}–{last_ts.strftime('%H:%M')} ({f_activesecs})"
                    except:
                        work_span = "-"
                rows.append((label, work_span, fmt(mi), fmt(si), fmt(te)))
            else:
                rows.append((label, "-", "-", "-", "-"))
        headers = ("last 5 days", "work span", "max idle", "Σ idle", "Σ ")
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
        for d, r in zip(days, rows):
            if d.weekday() >= 5:
                print(f"{GRY}{row(r)}{RST}")
            else:
                print(row(r))
        print(sep())
        print()


class TrackerApp:
    def __init__(self):
        self.single_instance = SingleInstance()
        self.config = AppConfig()
        self.datastore = DataStore(self.config.data_file)
        self.idle_detector = IdleDetector()
        self.stats = None
        self.current_day = date.today()
        self.day_str = self.current_day.strftime("%Y-%m-%d")
        self.stats = self.datastore.load_day(self.day_str)
        self.now_m0 = time.monotonic()
        self.session_start = self.now_m0 - self.stats.total_elapsed_seconds
        self.last_update = self.now_m0
        self.last_save = self.now_m0
        self.last_ui_update = self.now_m0
        self.day_closed = False
        self.show_active_minus_target = False
        self.setup_handlers()
        print_ascii_banner()
        ConsoleReport(self.datastore).print_last_5_days()
        self.print_start_info()

    def setup_handlers(self):
        atexit.register(self.save_and_exit)
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

        def console_handler(ctrl_type):
            if ctrl_type in (
                CTRL_C_EVENT,
                CTRL_BREAK_EVENT,
                CTRL_CLOSE_EVENT,
                CTRL_LOGOFF_EVENT,
                CTRL_SHUTDOWN_EVENT,
            ):
                self.save_and_exit()
                os._exit(0)
            return False

        self.console_handler = handler_type(console_handler)
        kernel32.SetConsoleCtrlHandler(self.console_handler, True)

    def print_start_info(self):
        print(f"🚀 Started at: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f"⏱️ Idle threshold: {int(self.config.idle_threshold_seconds)}s")
        print(f"🏢 Core time: {self.config.workday_start.strftime('%H:%M')} - {self.config.workday_end.strftime('%H:%M')}")
        print(f"🎯 Target: {fmt(self.config.active_time_target)}")
        print(f"💾 Autosave: {self.config.save_interval_seconds}s")
        print()

    def save_and_exit(self):
        try:
            now_m = time.monotonic()
            self.stats.sync_total_elapsed(self.session_start, now_m)
            self.datastore.save_day(self.day_str, self.stats)
        except:
            pass

    def restart_program(self):
        python = sys.executable
        os.execv(python, [python] + sys.argv)

    def handle_midnight_rollover(self, now, now_m):
        if now.date() != self.current_day and not self.day_closed:
            self.day_closed = True
            self.stats.sync_total_elapsed(self.session_start, now_m)
            self.datastore.save_day(self.day_str, self.stats)
            try:
                self.restart_program()
            except:
                self.current_day = now.date()
                self.day_str = self.current_day.strftime("%Y-%m-%d")
                self.stats = self.datastore.load_day(self.day_str)
                self.session_start = now_m - self.stats.total_elapsed_seconds
                self.last_update = now_m
                self.last_save = now_m
                self.last_ui_update = now_m
                self.stats.idle_run_seconds = 0.0
                self.day_closed = False

    def handle_keyboard(self):
        if msvcrt and msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch == b"\x04":
                self.show_active_minus_target = not self.show_active_minus_target

    def update_stats(self, delta, now):
        idle_sec = self.idle_detector.get_idle_seconds()
        is_active = idle_sec < self.config.idle_threshold_seconds
        if is_active:
            self.stats.update_on_active(delta, now)
        else:
            self.stats.update_on_idle(delta, in_worktime(now, self.config))
        return idle_sec

    def maybe_save(self, now_m):
        if now_m - self.last_save >= self.config.save_interval_seconds:
            self.stats.sync_total_elapsed(self.session_start, now_m)
            self.datastore.save_day(self.day_str, self.stats)
            self.last_save = now_m

    def maybe_update_ui(self, now_m, now, idle_sec):
        if now_m - self.last_ui_update >= self.config.update_interval_seconds:
            status = "🌞" if in_worktime(now, self.config) else "🌙"
            elapsed = fmt(now_m - self.session_start)
            active_display = fmt(self.stats.active_seconds)
            if self.show_active_minus_target:
                active_display = fmt_signed(self.stats.active_seconds - self.config.active_time_target)
            idle_str = f"{int(idle_sec):4d}s"
            max_idle_str = f"{fmt(self.stats.max_idle_seconds):>8}"
            sum_idle_str = f"{fmt(self.stats.sum_idle_seconds):>8}"
            bar = progress_bar(self.stats.active_seconds, self.config.active_time_target, self.config.progress_bar_width)
            smile = progress_smile(self.stats.active_seconds, self.config.active_time_target)
            line = (
                f"⏳ {elapsed} "
                f"{status} "
                f"💻 {active_display:>9}  "
                f"{bar} "
                f"{smile}  "
                f"🕒 idle: {idle_str}  "
                f"⬆ max idle: {max_idle_str}  "
                f"Σ idle: {sum_idle_str}"
            )
            print(line, end="\r", flush=True)
            self.last_ui_update = now_m

    def run(self):
        while True:
            now = datetime.now()
            now_m = time.monotonic()
            self.handle_keyboard()
            self.handle_midnight_rollover(now, now_m)
            delta = now_m - self.last_update
            self.last_update = now_m
            idle_sec = self.update_stats(delta, now)
            self.maybe_save(now_m)
            self.maybe_update_ui(now_m, now, idle_sec)
            time.sleep(self.config.poll_interval_seconds)


if __name__ == "__main__":
    app = TrackerApp()
    app.run()
