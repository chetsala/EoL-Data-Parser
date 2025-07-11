import os
import time
import json
import threading
import sqlite3
import requests
import csv
import tkinter as tk
from tkinter import filedialog, messagebox
from pystray import Icon, MenuItem as item, Menu
from PIL import Image, ImageDraw
from datetime import datetime
import hashlib

# === HARD-CODED CONFIGURATION ===
SOURCE_DIRECTORY = r"C:\Users\chets\OneDrive - aquacal.com\Desktop\ChlorSync Powercenter Test Results"
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "csv_path": r"O:\Files\AutoPilot\Power Center EoL Database\parsed_log_data.csv",
    "refresh_interval": 30
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(DEFAULT_SETTINGS, f)
        return DEFAULT_SETTINGS.copy()
    with open(SETTINGS_FILE, 'r') as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

settings = load_settings()

# === GLOBAL STATUS TRACKING ===
last_run_time = "Never"
last_parsed_count = 0
current_status = "Idle"

# === SQLITE SETUP ===
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

# === UTILITIES ===

def is_connected():
    try:
        requests.get('https://www.google.com', timeout=3)
        return True
    except:
        return False

def parse_log_file(file_path):
    data = {}
    with open(file_path, 'r') as file:
        for line in file:
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
    return data

def hash_record(record):
    """Create a hash from parsed data (excluding timestamp)."""
    return hashlib.md5(json.dumps(record, sort_keys=True).encode()).hexdigest()

def append_to_csv(new_data):
    if not new_data:
        return

    file_path = settings["csv_path"]
    headers = set()
    for record in new_data:
        headers.update(record.keys())
    headers = list(headers)

    while True:
        try:
            file_exists = os.path.isfile(file_path)

            with open(file_path, mode='a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                if not file_exists:
                    writer.writeheader()
                for record in new_data:
                    writer.writerow(record)

            break  # success!
        except PermissionError:
            print(f"[WARNING] {file_path} is locked. Waiting for it to close...")
            time.sleep(5)
        except Exception as e:
            print(f"[ERROR] Failed to write to CSV: {e}")
            time.sleep(5)

def parse_and_process():
    global last_run_time, last_parsed_count, current_status

    current_status = "Syncing..."
    parsed_count = 0
    new_data = []

    conn = sqlite3.connect("local_cache.db")
    cursor = conn.cursor()

    for root, dirs, files in os.walk(SOURCE_DIRECTORY):
        for file in files:
            if file.endswith('.log'):
                file_path = os.path.join(root, file)
                parsed = parse_log_file(file_path)
                record_hash = hash_record(parsed)  # hash before adding timestamp

                cursor.execute("SELECT 1 FROM logs WHERE data = ?", (record_hash,))
                if cursor.fetchone():
                    continue  # already processed

                # only after hashing do we add timestamp
                parsed["Parsed Timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT INTO logs (data) VALUES (?)", (record_hash,))
                new_data.append(parsed)
                parsed_count += 1

    conn.commit()
    conn.close()

    if new_data:
        append_to_csv(new_data)

    last_run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    last_parsed_count = parsed_count
    current_status = "Idle" if parsed_count else "Idle (No new files)"

# === GUI ===

def open_status_window():
    win = tk.Tk()
    win.title("Log Parser Status")
    win.geometry("350x150")
    win.resizable(False, False)

    def refresh_status():
        lbl_last_run.config(text=f"Last Run: {last_run_time}")
        lbl_count.config(text=f"Records Parsed: {last_parsed_count}")
        lbl_status.config(text=f"Status: {current_status}")
        win.after(1000, refresh_status)

    lbl_last_run = tk.Label(win, text=f"Last Run: {last_run_time}")
    lbl_last_run.pack(pady=5)

    lbl_count = tk.Label(win, text=f"Records Parsed: {last_parsed_count}")
    lbl_count.pack(pady=5)

    lbl_status = tk.Label(win, text=f"Status: {current_status}")
    lbl_status.pack(pady=5)

    refresh_status()
    win.mainloop()

def open_settings_window():
    win = tk.Tk()
    win.title("Settings")
    win.geometry("500x200")

    def browse_output():
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if path:
            entry_output.delete(0, tk.END)
            entry_output.insert(0, path)

    def save_and_close():
        settings["csv_path"] = entry_output.get()
        try:
            settings["refresh_interval"] = int(entry_interval.get())
        except:
            messagebox.showerror("Error", "Refresh interval must be an integer.")
            return
        save_settings(settings)
        win.destroy()

    tk.Label(win, text="CSV Output File:").grid(row=0, column=0, padx=10, pady=10, sticky='e')
    entry_output = tk.Entry(win, width=50)
    entry_output.insert(0, settings["csv_path"])
    entry_output.grid(row=0, column=1)
    tk.Button(win, text="Browse", command=browse_output).grid(row=0, column=2)

    tk.Label(win, text="Refresh Interval (sec):").grid(row=1, column=0, padx=10, pady=10, sticky='e')
    entry_interval = tk.Entry(win, width=10)
    entry_interval.insert(0, str(settings["refresh_interval"]))
    entry_interval.grid(row=1, column=1, sticky='w')

    tk.Button(win, text="Save", command=save_and_close).grid(row=2, columnspan=3, pady=20)

    win.mainloop()

# === BACKGROUND THREAD ===

def periodic_loop():
    while True:
        parse_and_process()
        time.sleep(settings["refresh_interval"])

# === TRAY ICON ===

def setup_tray_icon():
    img = Image.new('RGB', (64, 64), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 54, 54], fill="blue")
    d.text((15, 20), "LOG", fill="white")

    icon = Icon("LogParser", img)

    def on_quit(icon, item):
        icon.stop()

    icon.menu = Menu(
        item('Open Status Window', lambda i: threading.Thread(target=open_status_window).start()),
        item('Settings', lambda i: threading.Thread(target=open_settings_window).start()),
        item('Quit', on_quit)
    )

    threading.Thread(target=periodic_loop, daemon=True).start()
    icon.run()

# === START APP ===
setup_tray_icon()
