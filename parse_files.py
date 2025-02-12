import os
import openpyxl
import tkinter as tk
from tkinter import filedialog, messagebox

# Function to parse the log file and extract relevant data
def parse_log_file(file_path):
    data = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
    return data

# Function to parse logs and save to Excel
def parse_and_save_logs(main_directory, output_directory):
    # List to store parsed data from all log files
    all_data = []

    # Iterate over each subdirectory and file in the main directory
    for root, dirs, files in os.walk(main_directory):
        for file in files:
            if file.endswith('.log'):
                file_path = os.path.join(root, file)
                parsed_data = parse_log_file(file_path)
                all_data.append(parsed_data)

    # Create a new Excel workbook and select the active worksheet
    wb = openpyxl.Workbook()
    ws = wb.active

    # Write headers to the Excel sheet
    headers = set()
    for data in all_data:
        headers.update(data.keys())
    ws.append(list(headers))

    # Write data to the Excel sheet
    for data in all_data:
        row = [data.get(header, "") for header in headers]
        ws.append(row)

    # Save the Excel workbook to the specified directory
    output_file = os.path.join(output_directory, 'parsed_log_data.xlsx')
    wb.save(output_file)

    messagebox.showinfo("Success", f"Data from log files has been parsed and saved to {output_file}.")

# Function to select the main directory
def select_main_directory():
    main_directory = filedialog.askdirectory(title="Select Main Directory")
    main_dir_entry.delete(0, tk.END)
    main_dir_entry.insert(0, main_directory)

# Function to select the output directory
def select_output_directory():
    output_directory = filedialog.askdirectory(title="Select Output Directory")
    output_dir_entry.delete(0, tk.END)
    output_dir_entry.insert(0, output_directory)

# Function to start the parsing process
def start_parsing():
    main_directory = main_dir_entry.get()
    output_directory = output_dir_entry.get()

    if not main_directory or not output_directory:
        messagebox.showerror("Error", "Please select both directories.")
        return

    parse_and_save_logs(main_directory, output_directory)

# Create the main window
root = tk.Tk()
root.title("Log File Parser")

# Create and place widgets
tk.Label(root, text="Main Directory:").grid(row=0, column=0, padx=10, pady=10)
main_dir_entry = tk.Entry(root, width=50)
main_dir_entry.grid(row=0, column=1, padx=10, pady=10)
tk.Button(root, text="Browse", command=select_main_directory).grid(row=0, column=2, padx=10, pady=10)

tk.Label(root, text="Output Directory:").grid(row=1, column=0, padx=10, pady=10)
output_dir_entry = tk.Entry(root, width=50)
output_dir_entry.grid(row=1, column=1, padx=10, pady=10)
tk.Button(root, text="Browse", command=select_output_directory).grid(row=1, column=2, padx=10, pady=10)

tk.Button(root, text="Start Parsing", command=start_parsing).grid(row=2, columnspan=3, pady=20)

# Run the application
root.mainloop()
