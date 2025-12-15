# 🚀 Time/Activity Tracker (Python)

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

Igen, a GITHUB_README_Tracker.md tartalmát lemásolhatod a virtuális fájlból, de sajnos közvetlen letöltést nem tudok indítani a platform korlátai miatt.

Ezt a szöveget másold át, majd mentsd el a számítógépeden README.md néven, és töltsd fel a Githubra.

📄 Tartalom: README.md (függőségmentes verzió)
Markdown

# 🚀 Time/Activity Tracker (Python)

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

🏃 Usage
Ensure you have set up the tracker_config.ini file with your preferred settings.

Run the application from your terminal:
