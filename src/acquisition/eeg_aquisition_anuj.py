import tkinter as tk
from tkinter import messagebox
import serial
import json
import threading
import time
from datetime import datetime
import os

# --- Configuration ---
DEFAULT_PORT = 'COM3'  # Change this to your common default port (e.g., '/dev/ttyACM0' on Linux)
BAUD_RATE = 9600
OUTPUT_FILENAME = 'arduino_log.json'

class SerialDataLoggerApp:
    def __init__(self, master):
        self.master = master
        master.title("Arduino Serial Data Logger")
        master.geometry("400x250")

        # --- State Variables ---
        self.is_running = False
        self.serial_connection = None
        self.data_log = []
        self.log_thread = None

        # --- GUI Elements ---
        
        # 1. Port Selection
        self.port_label = tk.Label(master, text="Serial Port:")
        self.port_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.port_entry = tk.Entry(master, width=20)
        self.port_entry.insert(0, DEFAULT_PORT)
        self.port_entry.grid(row=0, column=1, padx=10, pady=10)

        # 2. Status Label
        self.status_text = tk.StringVar()
        self.status_text.set("Status: Stopped")
        self.status_label = tk.Label(master, textvariable=self.status_text, fg="red")
        self.status_label.grid(row=1, column=0, columnspan=2, pady=10)

        # 3. Control Buttons
        self.start_button = tk.Button(master, text="Start Acquisition", command=self.start_acquisition, bg="green", fg="white")
        self.start_button.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        self.stop_button = tk.Button(master, text="Stop & Save", command=self.stop_acquisition, bg="red", fg="white", state=tk.DISABLED)
        self.stop_button.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        # 4. Save Path Info
        self.path_label = tk.Label(master, text=f"Saving to: {os.path.abspath(OUTPUT_FILENAME)}", font=('Arial', 8))
        self.path_label.grid(row=3, column=0, columnspan=2, pady=5)
        
        # Protocol for closing the window
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_status(self, text, color="black"):
        """Updates the status label text and color."""
        self.status_text.set(text)
        self.status_label.config(fg=color)

    def start_acquisition(self):
        """Initializes serial connection and starts the data logging thread."""
        if self.is_running:
            messagebox.showwarning("Warning", "Acquisition is already running.")
            return

        port = self.port_entry.get()
        if not port:
            messagebox.showerror("Error", "Please enter a valid serial port.")
            return

        try:
            # 1. Open Serial Port
            self.serial_connection = serial.Serial(port, BAUD_RATE, timeout=1)
            time.sleep(2) # Wait for Arduino to reset after connection

            # 2. Reset State
            self.data_log = []
            self.is_running = True
            
            # 3. Start Thread
            self.log_thread = threading.Thread(target=self.log_data_worker, daemon=True)
            self.log_thread.start()
            
            # 4. Update GUI
            self.update_status(f"Status: Running on {port}...", color="blue")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.port_entry.config(state=tk.DISABLED)

        except serial.SerialException as e:
            messagebox.showerror("Serial Error", f"Could not open serial port {port}. Error: {e}")
            self.is_running = False
            self.update_status("Status: Stopped (Error)", color="red")


    def log_data_worker(self):
        """Worker function that runs in a separate thread to acquire and process data."""
        while self.is_running:
            try:
                if self.serial_connection.in_waiting > 0:
                    # Read a line and decode it (strip whitespace/newlines)
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    
                    if line:
                        # Generate timestamp and create log entry
                        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        
                        # Assuming the Arduino sends a single numerical value
                        try:
                            # Attempt to convert the signal to a float
                            signal_value = float(line)
                        except ValueError:
                            # If conversion fails, keep it as a string or handle the error
                            signal_value = line 
                            
                        entry = {
                            "timestamp": timestamp_str,
                            "signal_value": signal_value
                        }
                        
                        self.data_log.append(entry)
                        # Optional: Print to console for real-time monitoring
                        print(f"Logged: {entry}")
                        
                time.sleep(0.01) # Small delay to be CPU friendly
            except Exception as e:
                print(f"Error in data logging thread: {e}")
                # Automatically stop on unexpected error
                self.master.after(0, lambda: self.stop_acquisition(error=True))
                break


    def save_data_to_json(self):
        """Saves the collected data_log to the configured JSON file."""
        if not self.data_log:
            messagebox.showinfo("Info", "No data was collected to save.")
            return
            
        try:
            with open(OUTPUT_FILENAME, 'w') as f:
                json.dump(self.data_log, f, indent=4)
            
            self.update_status(f"Status: Saved {len(self.data_log)} entries.", color="darkgreen")
            print(f"Data successfully saved to {os.path.abspath(OUTPUT_FILENAME)}")
            messagebox.showinfo("Success", f"Data saved successfully to {OUTPUT_FILENAME}\nEntries: {len(self.data_log)}")
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save data to JSON: {e}")
            self.update_status("Status: Save Error", color="red")


    def stop_acquisition(self, error=False):
        """Stops the data logging process and closes the serial connection."""
        if not self.is_running and not error:
            messagebox.showwarning("Warning", "Acquisition is already stopped.")
            return
            
        self.is_running = False
        
        # 1. Wait for thread to finish (if it was started)
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=1) # Give it 1 second to clean up

        # 2. Close Serial Port
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

        # 3. Update GUI
        self.update_status("Status: Stopped", color="red")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.NORMAL)
        
        # 4. Save Data (Only on normal stop)
        if not error:
            self.save_data_to_json()

    def on_closing(self):
        """Handles the window closing event."""
        if self.is_running:
            # Stop the thread and close the serial port before quitting
            self.stop_acquisition() 
        self.master.destroy()

if __name__ == "__main__":
    # Ensure pyserial is installed: pip install pyserial
    
    root = tk.Tk()
    app = SerialDataLoggerApp(root)
    root.mainloop()