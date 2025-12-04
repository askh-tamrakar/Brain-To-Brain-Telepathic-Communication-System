import tkinter as tk
from tkinter import messagebox, font as tkfont
import serial
import serial.tools.list_ports
import json
import datetime
import threading
import time
import re 
import sys

# --- APPLICATION CONFIGURATION ---
BAUD_RATE = 9600
LOG_FILENAME = "eeg_data_log.json"

class SerialDataLoggerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Arduino Serial Data Logger (BCI Utility)")
        self.geometry("600x450")
        self.config(bg="#F8F9FA")
        
        self.serial_connection = None
        self.is_logging = False
        self.data_log = []
        self.log_thread = None
        
        self._initialize_ui()
        
    def _initialize_ui(self):
        # --- Styling ---
        self.title_font = tkfont.Font(family="Arial", size=16, weight="bold")
        self.label_font = tkfont.Font(family="Arial", size=10)
        
        # --- Main Frame ---
        main_frame = tk.Frame(self, bg="#FFFFFF", padx=20, pady=20)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        tk.Label(main_frame, text="BCI Serial Data Acquisition", font=self.title_font, bg="#FFFFFF", fg="#007BFF").pack(pady=(0, 20))
        
        # --- Port Selection Frame ---
        port_frame = tk.Frame(main_frame, bg="#F1F1F1", padx=10, pady=10, relief=tk.GROOVE, borderwidth=1)
        port_frame.pack(fill="x", pady=10)
        
        tk.Label(port_frame, text="COM Port:", font=self.label_font, bg="#F1F1F1").pack(side=tk.LEFT, padx=5)
        
        self.port_var = tk.StringVar(self)
        self.ports = self._get_available_ports()
        
        if self.ports:
            self.port_var.set(self.ports[0])
        else:
            self.ports = ["No Ports Found"]
            self.port_var.set(self.ports[0])
            
        self.port_menu = tk.OptionMenu(port_frame, self.port_var, *self.ports)
        self.port_menu.config(width=15, relief=tk.FLAT)
        self.port_menu.pack(side=tk.LEFT, padx=5)
        
        tk.Button(port_frame, text="Refresh Ports", command=self._refresh_ports, bg="#FFC107", fg="black", relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
        
        # --- Control Buttons ---
        control_frame = tk.Frame(main_frame, bg="#FFFFFF")
        control_frame.pack(fill="x", pady=20)
        
        self.start_button = tk.Button(control_frame, text="START LOGGING", command=self.start_logging, state=tk.NORMAL, bg="#28A745", fg="white", font=('Arial', 10, 'bold'), relief=tk.RAISED, padx=10, pady=5)
        self.start_button.pack(side=tk.LEFT, expand=True, padx=10)
        
        self.stop_button = tk.Button(control_frame, text="STOP & SAVE", command=self.stop_logging, state=tk.DISABLED, bg="#DC3545", fg="white", font=('Arial', 10, 'bold'), relief=tk.RAISED, padx=10, pady=5)
        self.stop_button.pack(side=tk.LEFT, expand=True, padx=10) 
        
        # --- Status and Log Display ---
        self.status_label = tk.Label(main_frame, text="Status: Disconnected", fg="#6C757D", bg="#FFFFFF", font=('Arial', 10))
        self.status_label.pack(pady=10)
        
        tk.Label(main_frame, text="Live Console Output:", fg="#343A40", bg="#FFFFFF", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        
        self.log_text = tk.Text(main_frame, height=8, width=70, state=tk.DISABLED, bg="#E9ECEF", fg="#000000", wrap=tk.WORD)
        self.log_text.pack(fill="x", expand=True)

    def _get_available_ports(self):
        """Fetches a list of available serial ports (COM ports)."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def _refresh_ports(self):
        """Updates the OptionMenu with current available ports."""
        new_ports = self._get_available_ports()
        
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        
        if not new_ports:
            new_ports = ["No Ports Found"]

        for port in new_ports:
            menu.add_command(label=port, command=tk._setit(self.port_var, port))
        
        self.ports = new_ports
        self.port_var.set(new_ports[0])

    def start_logging(self):
        """Initializes the serial connection and starts the logging thread."""
        selected_port = self.port_var.get()
        
        if selected_port == "No Ports Found" or selected_port not in self._get_available_ports():
            messagebox.showerror("Connection Error", "Please select a valid COM port.")
            return

        try:
            # 1. Establish Serial Connection
            self.serial_connection = serial.Serial(selected_port, BAUD_RATE, timeout=0.1)
            time.sleep(2) # Wait for Arduino reset/connection
            
            # 2. Reset logging state
            self.data_log = []
            self.is_logging = True
            
            # 3. Start Data Logging Thread
            self.log_thread = threading.Thread(target=self._log_data_stream, daemon=True)
            self.log_thread.start()
            
            # 4. Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self._update_status(f"LOGGING on {selected_port}...", "#28A745")
            self._update_log_text("--- Logging Started ---")
            
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Could not open port {selected_port}: {e}")
            self.serial_connection = None

    def _log_data_stream(self):
        """Reads data from the serial port in a separate thread."""
        while self.is_logging:
            try:
                if self.serial_connection and self.serial_connection.is_open and self.serial_connection.in_waiting > 0:
                    # Use errors='ignore' to skip non-UTF-8 characters safely
                    raw_line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    
                    if raw_line:
                        # Clean the line (remove control characters, ensure clean ASCII)
                        cleaned_line = re.sub(r'[^\x20-\x7E]', '', raw_line).strip()
                        
                        if cleaned_line:
                            log_entry = {
                                "timestamp": datetime.datetime.now().isoformat(),
                                "raw_data": cleaned_line
                            }
                            self.data_log.append(log_entry)
                            
                            # Update console output on the main thread
                            self.after(0, lambda: self._update_log_text(cleaned_line))
                
                time.sleep(0.005) 
                
            except Exception as e:
                # Log the thread error but gracefully stop the application components
                self.after(0, lambda: self._update_log_text(f"THREAD ERROR: {e}"))
                self.after(0, self.stop_logging)
                break

    def stop_logging(self):
        """Stops the logging thread, closes the serial port, and saves data to JSON."""
        if self.serial_connection:
            # 1. Stop logging flag and close connection
            self.is_logging = False
            
            # Wait briefly for thread to detect is_logging = False
            if self.log_thread and self.log_thread.is_alive():
                pass 
            
            try:
                self.serial_connection.close()
                self.serial_connection = None
            except Exception as e:
                self._update_status(f"Error closing port: {e}", "#DC3545")
            
            # 2. Save data to JSON file
            self._save_to_json()
            
            # 3. Update UI
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self._update_status("Disconnected & Saved", "#007BFF")
            self._update_log_text("--- Logging Stopped and Data Saved ---")

    def _save_to_json(self):
        """Writes the collected data log to a JSON file."""
        try:
            with open(LOG_FILENAME, 'w') as f:
                json.dump(self.data_log, f, indent=4)
            messagebox.showinfo("Success", f"Data successfully saved to {LOG_FILENAME}. Total records: {len(self.data_log)}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving data: {e}")

    def _update_log_text(self, message):
        """Appends a message to the Text widget (thread-safe)."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _update_status(self, text, color):
        """Updates the status label (thread-safe)."""
        self.status_label.config(text=f"Status: {text}", fg=color)

    def on_closing(self):
        """Handles application closing event."""
        if self.is_logging:
            self.stop_logging()
        self.destroy()

if __name__ == "__main__":
    try:
        # Check for module existence first
        import serial 
        
        app = SerialDataLoggerApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except ImportError:
        messagebox.showerror("Error", "The 'serial' library (pyserial) is missing. Please run: pip install pyserial")
        sys.exit(1)
    except Exception as e:
        messagebox.showerror("Fatal Error", f"An unexpected error occurred: {e}")