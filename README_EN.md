# 🖱️ DotConnector Auto Clicker

[简体中文](https://github.com/iop666/DotConnector/blob/main/README.md) · **English**

A lightweight, reliable Windows mouse auto-clicker. Implemented in **pure Python + tkinter**, simulating clicks directly via `ctypes` calling the Win32 `mouse_event` / `SetCursorPos` APIs — **zero third-party runtime dependencies**.

---

### 🖥️ Interface & Interaction

<img width="1032" height="1293" alt="image" src="https://github.com/user-attachments/assets/1b9660c8-821c-4420-8f32-dcfc35066c70" />

- **5 tabs**: Run Status / Click Mode / Script Mode / Hotkey Settings / More Settings
- **5 global hotkeys**, all customizable (conflict detection, Esc to cancel, bare F1–F24 supported)
- **Dual running records**: click count + script run count, each showing current-session / historical total
- **On-top windows**: real-time click counter + script playback progress; draggable, adjustable font/opacity, **smart avoidance**
- **Red icon status**: the tray & window icons turn red while clicking / recording / playing, and return to the default blue when stopped
- **Single-instance lock**: reopening switches to the existing instance instead of spawning a duplicate
- **Session log history**: an independent log file is generated on every launch; view / preview / delete / export
- UI scaling **100% / 150% / 200%**, high-DPI aware, settings auto-saved & restored

---

## ✨ Feature Overview

### 🖱️ Auto Clicking

<img width="1021" height="1295" alt="image" src="https://github.com/user-attachments/assets/0964136c-c3e9-4393-b224-1290e594508e" />

| Capability | Description |
|---|---|
| Mouse button | **Left / Middle / Right** |
| Click mode | **Fixed interval** / **Random interval** (set a min–max range) / **Hold mode** (hold + release durations) |
| Click speed | **Live conversion** of the ms interval to "≈ X clicks per second"; 5 presets: 1 / 10 / 20 / 50 / 100 per second |
| Click position | **Follow mouse** (default) or **Locked coordinates** (capture by hotkey / manual input, optional **±5px random offset**) |
| Stop condition | **Four mutually-exclusive radio options**: no auto-stop / click count / countdown (min+sec) / run until a specific time (hh:mm:ss) |
| Window detection | Match by **window title or process name**; **auto-pauses** when the target loses focus and **auto-resumes** when it regains focus; blocks startup if enabled but no window is bound |

### 🎬 Script Recording & Replay

<img width="1037" height="1311" alt="image" src="https://github.com/user-attachments/assets/b94a567e-e3ba-47e6-8fa5-b80dfbbdfe67" />

- **Record**: mouse movement, mouse buttons (left/middle/right press & release), **keyboard input** (letters / digits / function keys / symbol keys `-=[]\;',./`), and delays between actions
- **Playback**: run once (default) / loop count / **infinite loop** / loop gap / **speed multiplier** (faster/slower) / **relative movement** (don't jump to the recorded coordinates)
- **Two file formats**: structured XML (`.xml`, human-readable) + lightweight binary (`.dcs`, 10 bytes per action) — **auto-detected on playback**
- **Configurable max recording steps** (default 50000); movement trails auto-thinned (>5px or >50ms)
- Live playback progress: `index/total` + loop count + **next action** (clicks & keys only)

## 📦 Installation

### Option 1: Use the executable (recommended)

1. Download [DotConnector.exe] (single file, ~12 MB)
2. Double-click to run — no installation required

### Option 2: Run from source

Requires Python 3.9+ (with tkinter):

```bash
python DotConnector_basic.py
```

> **No third-party dependencies** (except for packaging) — pure Python standard library only.

---
## ⌨️ Global Hotkeys

They work even when the window is not focused. Customize them in the "Hotkey Settings" tab:

<img width="1050" height="775" alt="image" src="https://github.com/user-attachments/assets/d9a46bc9-99d2-4cf4-a795-bf31c4abd86a" />

| Default hotkey | Function |
|---|---|
| `Ctrl+F9` | Start / stop clicking |
| `Ctrl+Shift+F8` | Capture current mouse coordinates |
| `Ctrl+Shift+F11` | Start / stop script recording |
| `Ctrl+Shift+F12` | Start / stop script playback |
| `Ctrl+Alt+F10` | Force quit (emergency — ends the process immediately) |

> 💡 Click the "Set" button next to a hotkey in the "Hotkey Settings" tab, then press the new combination — it takes effect **immediately** and syncs across the whole UI.

---

## ⚙️ Feature Details

### Click Mode

| Item | Description |
|---|---|
| **Click mode** | Fixed interval (1–2000ms) / Random interval (min~max, auto-swapped if min > max) / Hold mode (hold + release durations) |
| **Mouse button** | Left / Middle / Right |
| **Click speed** | Live conversion to "clicks per second"; presets: 1/10/20/50/100 per second (auto-disabled in random/hold modes) |
| **Click position** | Follow mouse / locked coordinates (capture by hotkey or manual input, optional ±5px random offset) |
| **Stop condition** | No auto-stop / click count / countdown (min+sec) / run until a specific time (hh:mm:ss) — mutually-exclusive radio buttons |
| **Window detection** | Match a target window by title or process name; pause on focus loss, resume on focus return; blocks startup if enabled but no window is bound |

### Script Mode

**Recording:**
- Records mouse movement (thinned when >5px or >50ms apart), mouse buttons (left/middle/right press & release), keyboard input, and delays between actions
- **Keyboard recording is on by default**; **the max recording steps are configurable** (default 50000)
- Script format: **XML** (default, human-readable) or **binary .dcs** (lightweight, 10 bytes per action)

**Playback:**
- **Run once** (default; loop count/interval inputs auto-disabled) / loop count / infinite loop, with a configurable loop gap
- **Speed multiplier** (faster/slower) and **relative movement** (don't jump to the recorded coordinates)
- Script list sortable by **name / time**, ascending/descending, with one-click **refresh** and **open scripts folder**
- Shows script info on selection: **steps / total duration / whether keyboard input is recorded**
- Live display while playing: progress `index/total` + loop count + **next action**

### On-top Display (More Settings tab)

| On-top window | Content |
|---|---|
| **Click counter (on-top)** | Real-time click count for the current session; shows the click / emergency hotkeys |
| **Script progress (on-top)** | Playback progress + loop count + next action; shows the script / emergency hotkeys |

- Defaults to the screen **top-left**; the entire window is draggable and its position is remembered
- **Font size and opacity are adjustable** (default 16pt / 92%)
- **Smart avoidance**: automatically moves down / to the top-right when the script is about to click where the on-top window sits, then returns automatically
- A "Reset on-top position" button restores the defaults

---

## 🗂️ Locally Generated Files

The software creates the following files / folders in the **program directory** (project folder when running from source; exe folder when packaged):

### ① `config.ini` — Settings persistence

All settings are auto-saved on exit and restored on the next launch:

```ini
[general]   version, historical total clicks / script runs, UI scale
[click]     mouse button, click mode, speed parameters (interval / random range / hold / release)
[position]  position strategy, locked coordinates, random-offset switch
[stop]      stop condition (radio mode + count / countdown / until time)
[window]    window-detection switch, match method (title / process), target
[view]      on-top switches, font, opacity, on-top window positions, history-log switch, resize
[script]    script options (run-once / loop / rate / relative / format / max steps, etc.)
[hotkey]    5 global hotkeys (modifier + key code)
```

### ② `logs\` — Session history logs

A separate session log file is created on every launch:

```
logs/dotconnector_20260810_153045.log
```

- Records everything from the session: program start, click start/stop (with the full config), script record/play, window pause/resume, hotkey changes, coordinate captures, etc.
- "Run Status → History" lists the files, lets you preview them, opens the log folder, and deletes entries
- Can be disabled in "More Settings → Log Settings" (on by default)

### ③ `Scripts\` — Scripts folder

- Recorded scripts are saved here by default
- The "Script Mode → Playback" list reads from this folder — **importing/exporting is as simple as dropping files into or moving files out of it**

> **Tip**: On first run, only `config.ini` may exist; `logs\` and `Scripts\` are created automatically the first time a log is written / a script is saved. **Back up these three items before upgrading or migrating** (they live only in the program directory and are never written to the system).

---

## 🖥️ System Requirements

- Windows 10 / 11 (64-bit)
- High-DPI displays (e.g. 3200×2000@200%) supported

---

### Run from source

```bash
python DotConnector_basic.py                # Run the GUI
python DotConnector_basic.py --selftest     # Engine self-test (simulated clicks, no real mouse)
python tests/run_regression.py              # Regression test
python tests/single_instance_check.py       # Single-instance lock test
```

### Package into an executable

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name DotConnector \
    --icon icon.ico \
    --add-data "icon.ico;." --add-data "icon_run.ico;." \
    DotConnector_basic.py
```

### Architecture

```
ClickEngine (separate thread)
    ├─ fixed / random / hold modes
    ├─ ctypes → user32.mouse_event simulates clicks
    └─ coordinate stats (coord_counts / last_coord)

ScriptRecorder / ScriptPlayer (separate threads)
    ├─ Record: GetAsyncKeyState polls mouse/keyboard, trail thinning
    ├─ Play: streams XML / DCS, speed multiplier + loops
    └─ Progress: index / total / loop_now / next_desc

Tray (separate thread)
    ├─ RegisterHotKey global hotkeys (5)
    ├─ tray icon (blue/red status switch)
    └─ message loop forwarded to the main thread

Single-instance lock (startup)
    └─ CreateMutexW named mutex; reactivates the existing window on duplicate launch

Main thread (tkinter UI)
    ├─ 5 tabs + custom ModernRadio / ModernCheck
    ├─ config.ini persistence
    ├─ logs/ session logs
    └─ on-top windows (click counter / script progress)
```

---

## ❓ FAQ

**Q: Does antivirus software flag this program?**
Click-simulation tools may be flagged by some security software — this is normal. This tool only calls standard system APIs and contains no malicious behavior.

**Q: Hotkeys are not working?**
The software has a built-in single-instance lock, but a crashed process may still hold the global hotkeys — end all `DotConnector.exe` processes in Task Manager and restart.

**Q: Where are the config / scripts / logs stored?**
All in the **program directory**: `config.ini`, `logs\`, `Scripts\`. Copy the whole folder to take all data to another machine or after a reinstall.

**Q: The UI looks blurry on a high-DPI display?**
DPI awareness is enabled. In "More Settings", set the scale to 200% (the default on high-DPI systems).

**Q: I want to click without accidental triggers?**
Enable **window detection** and bind the target window to auto-pause on focus loss; or use locked coordinates with a ±5px random offset.

**Q: Can I share recorded scripts?**
Yes. The `.xml` format is human-readable text — just share the file; the other person drops it into their `Scripts\` folder and it works.

---

## 📄 License

Free to use, modify, and redistribute (MIT-style).

---

**Thanks for using!** If you have questions or feature suggestions, feel free to open an issue.
