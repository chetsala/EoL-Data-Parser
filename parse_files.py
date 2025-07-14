import os
import time
import json
import threading
import sqlite3
import csv
import tkinter as tk
from pystray import Icon, MenuItem as item, Menu
from PIL import Image, ImageDraw
from datetime import datetime
from collections import OrderedDict
import hashlib

# === SETUP: SQLite database for deduplication ===
# Stores a hash of each parsed record to prevent duplicates from being written to the CSV
conn = sqlite3.connect("local_cache.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT UNIQUE
)
""")
conn.commit()
conn.close()

# === CONFIGURATION ===
# Contains hardcoded paths and refresh settings
DEFAULT_SETTINGS = {
    "csv_dir": r"C:\CSVDashboard\EoL_test.csv",
    "refresh_interval": 30, # How often the parser runs (in seconds)
    "source_dir": r"C:\Users\chets\OneDrive - aquacal.com\Desktop\ChlorSync Powercenter Test Results"
} 

# === GLOBAL STATUS TRACKING ===
# Used for updating the status window
last_run_time = "Never"
last_parsed_count = 0
current_status = "Idle"

# === PARSES a single log file ===
# Extracts key-value pairs from each line formatted like: "Key: Value"
def parse_log_file(file_path):
    data = OrderedDict()
    current_scope = None # Will be 'Forward', 'Reverse', or None
    scoped_keys = {
        "Reported Voltage [Actual +/-10%]",
        "Actual Voltage",
        "Reported Current [Actual +/-20%]",
        "Actual Current"
    }
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            # Detect Forward/Reverse section headers
            if line.lower().startswith("forward:"):
                current_scope = "Forward"
                continue
            elif line.lower().startswith("reverse:"):
                current_scope = "Reverse"
                continue       
            
            # Parse key-value lines
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Only prefix key if it's in the scoped set
                if key in scoped_keys and current_scope:
                    data[f"{current_scope} {key}"] = value
                else:
                    data[key] = value
    return data

# === APPENDS new unique records to the CSV ===
# Uses retry loop to handle file lock if the CSV is open (e.g. in Excel)
def append_to_csv(new_data):
    if not new_data:
        return

    file_path = DEFAULT_SETTINGS["csv_dir"]

    # Collect all unique keys across new records for the CSV header
    all_keys = []
    seen = set()
    for record in new_data:
        for key in record:
            if key not in seen:
                seen.add(key)
                all_keys.append(key)

    # Keep trying to open the file until it becomes available
    while True:
        try:
            file_exists = os.path.isfile(file_path)

            with open(file_path, mode='a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_keys)
                if not file_exists:
                    writer.writeheader()
                for record in new_data:
                    writer.writerow(record)

            break  # Exit retry loop on success
        except PermissionError:
            print(f"[WARNING] {file_path} is locked. Waiting for it to close...")
            time.sleep(5)
        except Exception as e:
            print(f"[ERROR] Failed to write to CSV: {e}")
            time.sleep(5)
            
# === CORE FUNCTION: Parses all log files and appends new entries ===
# Prevents duplicates by hashing content and checking SQLite
def parse_and_process():
    global last_run_time, last_parsed_count, current_status

    current_status = "Syncing..."
    parsed_count = 0
    new_data = []

    conn = sqlite3.connect("local_cache.db")
    cursor = conn.cursor()

    # Walk through the log file directory recursively
    for root, dirs, files in os.walk(DEFAULT_SETTINGS["source_dir"]):
        for file in files:
            if file.endswith('.log'):
                file_path = os.path.join(root, file)
                parsed = parse_log_file(file_path)
                # Hash the content BEFORE adding timestamp to avoid unique hash each time
                record_hash = hashlib.md5(json.dumps(parsed, sort_keys=True).encode()).hexdigest() # hash before adding timestamp

                # Skip if we've already seen this record
                cursor.execute("SELECT 1 FROM logs WHERE data = ?", (record_hash,))
                if cursor.fetchone():
                    continue  # already processed
                
                # Store hash and queue record for CSV
                cursor.execute("INSERT INTO logs (data) VALUES (?)", (record_hash,))
                new_data.append(parsed)
                parsed_count += 1

    conn.commit()
    conn.close()

    new_data
    # Append to CSV if any new records were found
    if new_data:
        append_to_csv(new_data)

    # Update GUI state
    last_run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    last_parsed_count = parsed_count
    current_status = "Idle" if parsed_count else "Idle (No new files)"

# === GUI WINDOW: Shows status of parsing loop ===
def open_status_window():
    win = tk.Tk()
    win.title("Log Parser Status")
    win.geometry("350x150")
    win.resizable(False, False)

    # Periodically update the displayed info
    def refresh_status():
        lbl_last_run.config(text=f"Last Run: {last_run_time}")
        lbl_count.config(text=f"Records Parsed: {last_parsed_count}")
        lbl_status.config(text=f"Status: {current_status}")
        win.after(1000, refresh_status)

    # GUI Labels
    lbl_last_run = tk.Label(win, text=f"Last Run: {last_run_time}")
    lbl_last_run.pack(pady=5)

    lbl_count = tk.Label(win, text=f"Records Parsed: {last_parsed_count}")
    lbl_count.pack(pady=5)

    lbl_status = tk.Label(win, text=f"Status: {current_status}")
    lbl_status.pack(pady=5)

    refresh_status()
    win.mainloop()

# === BACKGROUND THREAD LOOP ===
# Runs parsing on a fixed interval (default 30 seconds)
def periodic_loop():
    while True:
        parse_and_process()
        time.sleep(DEFAULT_SETTINGS["refresh_interval"])

# === SYSTEM TRAY SETUP ===
# Shows tray icon with menu and starts background thread
def setup_tray_icon():
     # Build tray icon image
    img = Image.new('RGB', (64, 64), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 54, 54], fill="blue")
    d.text((15, 20), "LOG", fill="white")

    icon = Icon("LogParser", img)
    # Exit program cleanly
    def on_quit(icon, item):
        icon.stop()

# Build menu
    icon.menu = Menu(
        item('Open Status Window', lambda i: threading.Thread(target=open_status_window).start()),
        item('Quit', on_quit)
    )
 # Start parsing loop in background
    threading.Thread(target=periodic_loop, daemon=True).start()
# Run tray app
    icon.run()

# === START APP ===
setup_tray_icon()
