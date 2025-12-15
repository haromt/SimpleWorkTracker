🚀 Time/Activity Tracker (Python)

A simple, robust, and single-instance time and activity tracker written in Python, designed to measure active desk time and idle periods based on user input (keyboard and mouse). It tracks progress towards a configurable daily goal and persists data seamlessly.

## ✨ Features

* **Activity Tracking:** Measures active time based on keyboard and mouse input (using the Windows API).
* **Idle Metrics:** Tracks the current idle time, the maximum single idle period (`max_idle_seconds`), and the total accumulated idle time (`sum_idle_seconds`) during defined work hours.
* **Cumulative Time:** Records the total elapsed time since the start of the day's first monitoring session (`total_elapsed_seconds`).
* **Workday Constraints:** Idle time is only counted for the `sum_idle_seconds` metric during predefined workday hours.
* **Goal Visualization:**
    * **Progress Bar:** Visually tracks the daily active time progress towards a configurable target.
    * **Mood Smiley:** Provides quick visual feedback (emoji) on the progress completion percentage.
* **Persistent Data:** Saves progress automatically at set intervals and upon graceful application exit (`Ctrl+C`).
* **State Loading:** Loads today's progress upon startup for seamless continuation of tracking.

## ⚙️ Configuration (`tracker_config.ini`)

All adjustable parameters are stored in the `tracker_config.ini` file, which must be located in the same directory as `tracker.py`.

```ini
[TRACKER]
DATA_FILE = tracker_data.json       ; File where daily metrics are stored
IDLE_THRESHOLD_SECONDS = 60         ; Time (seconds) without input to count as idle
POLL_INTERVAL_SECONDS = 0.5         ; How often the system checks for input
UPDATE_INTERVAL_SECONDS = 1.0       ; How often the console output refreshes
SAVE_INTERVAL_SECONDS = 300         ; Auto-save interval (e.g., 5 minutes)
ACTIVE_TIME_TARGET_HOURS = 6        ; Daily active time target (Hours)
ACTIVE_TIME_TARGET_MINUTES = 45     ; Daily active time target (Minutes)
PROGRESS_BAR_WIDTH = 20             ; Console progress bar width

[WORKTIME]
WORKDAY_START_HOUR = 9
WORKDAY_START_MINUTE = 0            ; Start of the workday
WORKDAY_END_HOUR = 16
WORKDAY_END_MINUTE = 45             ; End of the workday
```
##🏃 Usage
Ensure you have set up the tracker_config.ini file with your preferred settings.Run the application from your
terminal:Bashpython tracker.py

The program will start logging your activity and display real-time progress.

##Console Output
The console output provides continuous, real-time feedback:[HH:MM:SS] Daily 💻: HH:MM:SS [██████████░░░░░░░░░░] 50% 🙂  (idle: 1s, max idle: 00:15:00, sum idle: 00:30:00) 
FieldDescription[HH:MM:SS]Total Elapsed Time since the first monitoring start today (cumulative across sessions).Daily 💻: HH:MM:SSTotal Active Time accumulated today.[Progress Bar]Visual progress towards the ACTIVE_TIME_TARGET.Mood EmojiQuick visual feedback based on the progress ratio.idle:Current time since the last mouse/keyboard input.max idle:Maximum single idle period detected today.sum idle:Total accumulated idle time during workday hours.🛑 Stopping the TrackerPress Ctrl+C (Keyboard Interrupt) to stop the tracker gracefully. The program executes a final save of the current day's progress before exiting.
