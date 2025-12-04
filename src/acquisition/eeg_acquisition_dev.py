import serial
import json
import time
from datetime import datetime
import threading
from tkinter import *
from tkinter import ttk, messagebox
import glob

# --- Configuration ---
# File jahan data save hoga
OUTPUT_FILENAME = "eeg_data_log.json"
# Baud rate jo Arduino ke code se match hona chahiye
BAUD_RATE = 115200 


class SerialDataLogger:
    """ Serial Port se data acquire karne aur use JSON mein save karne ke liye class. """
    def __init__(self, port, baudrate):
        self.ser = None
        self.is_running = False
        self.port = port
        self.baudrate = baudrate
        self.log_thread = None
        self.data_buffer = []

    def start_acquisition(self):
        """ Data acquisition shuru karta hai. """
        if self.is_running:
            return "Acquisition is already running."

        try:
            # Serial connection establish karna
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            # Thoda wait karte hain taaki connection stable ho jaaye
            time.sleep(2) 
            
            if self.ser.is_open:
                self.is_running = True
                # Naya thread shuru karte hain taaki GUI freeze na ho
                self.log_thread = threading.Thread(target=self._log_data)
                self.log_thread.start()
                return f"Acquisition started on {self.port}."
            else:
                return f"Error: Could not open port {self.port}."

        except serial.SerialException as e:
            return f"Serial Error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def stop_acquisition(self):
        """ Data acquisition band karta hai aur buffer ko save karta hai. """
        if not self.is_running:
            return "Acquisition is already stopped."

        self.is_running = False
        
        # Thread ko complete hone ka wait karna
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join()
        
        # Connection band karna
        if self.ser and self.ser.is_open:
            self.ser.close()

        # Buffer mein jama data ko JSON file mein save karna
        self._save_to_json()
        return f"Acquisition stopped. Data saved to {OUTPUT_FILENAME}."

    def _log_data(self):
        """ Background mein data acquire karne ka kaam karta hai. """
        while self.is_running:
            try:
                # Serial se ek line read karna (Arduino data bhej raha hoga)
                line = self.ser.readline().decode('utf-8').strip()
                
                if line:
                    # Timestamp add karna
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    
                    # Data entry banana
                    # Assuming Arduino sends comma-separated data (e.g., '1023,512,200')
                    
                    # Agar aapka Arduino sirf ek raw value bhej raha hai:
                    # data_entry = {"timestamp": timestamp, "signal": float(line)}
                    
                    # Agar aapka Arduino multiple values bhej raha hai:
                    try:
                        signals = [float(s) for s in line.split(',')]
                        data_entry = {"timestamp": timestamp, "signals": signals}
                    except ValueError:
                        # Agar data number nahi hai toh skip karna
                        continue

                    # Data ko buffer mein add karna
                    self.data_buffer.append(data_entry)
                    
            except serial.SerialTimeoutException:
                pass  # Timeout hone par kuch nahi karna
            except Exception as e:
                # Agar koi aur error aaye toh acquisition band kar dena
                if self.is_running:
                    print(f"Acquisition error: {e}")
                    self.is_running = False
                break

    def _save_to_json(self):
        """ Buffer mein jama data ko JSON file mein save karta hai. """
        if not self.data_buffer:
            return

        # Agar file pehle se maujood hai toh append karna, warna naya file banana
        try:
            with open(OUTPUT_FILENAME, 'a') as f:
                # Har entry ko naye line mein JSON format mein likhna
                for entry in self.data_buffer:
                    f.write(json.dumps(entry) + '\n')
            
            # Data save hone ke baad buffer ko clear karna
            self.data_buffer = []

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save data to JSON: {e}")


# --- GUI Application ---
class Application(Tk):
    def __init__(self):
        super().__init__()
        self.title("SSVEP Serial Logger")
        self.geometry("400x250")
        
        # Data Logger ka object banana
        self.logger = None
        
        # Styles setup karna
        self.style = ttk.Style(self)
        self.style.configure('TButton', font=('Arial', 10), padding=5)

        self._create_widgets()

    def _create_widgets(self):
        # Frame for Port Selection
        port_frame = ttk.Frame(self, padding="10")
        port_frame.pack(fill='x')

        ttk.Label(port_frame, text="Select Port:").pack(side='left', padx=5)
        
        # Port mention box (Dropdown menu)
        self.port_var = StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=15)
        self.port_combo['values'] = self._get_available_ports()
        self.port_combo.pack(side='left', padx=5)
        
        # Refresh Button
        ttk.Button(port_frame, text="Refresh Ports", command=self._refresh_ports).pack(side='left', padx=5)

        # Frame for Control Buttons
        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(pady=10)

        # Start Button
        self.start_button = ttk.Button(button_frame, text="START Acquisition", command=self._start_btn_action, style='TButton')
        self.start_button.pack(side='left', padx=10)

        # Stop Button
        self.stop_button = ttk.Button(button_frame, text="STOP and Save", command=self._stop_btn_action, state=DISABLED, style='TButton')
        self.stop_button.pack(side='left', padx=10)

        # Status Label
        self.status_label = ttk.Label(self, text="Status: Ready", foreground="blue")
        self.status_label.pack(pady=10)

        # Output File Info
        ttk.Label(self, text=f"Data will be appended to: {OUTPUT_FILENAME}", font=('Arial', 8)).pack(pady=5)
    
    def _get_available_ports(self):
        """ System par available serial ports dhundhta hai. """
        if sys.platform.startswith('win'):
            ports = [f'COM{i + 1}' for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            return []

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result

    def _refresh_ports(self):
        """ Port list ko update karta hai. """
        ports = self._get_available_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_var.set(ports[0])
        else:
            self.port_var.set("No Ports Found")

    def _start_btn_action(self):
        """ Start button click hone par action. """
        selected_port = self.port_var.get()
        if not selected_port or selected_port == "No Ports Found":
            messagebox.showwarning("Error", "Please select a valid Serial Port.")
            return

        self.logger = SerialDataLogger(selected_port, BAUD_RATE)
        
        # Acquisition shuru karna
        status_message = self.logger.start_acquisition()

        # Status update karna
        self.status_label.config(text=f"Status: {status_message}", foreground="green" if "started" in status_message else "red")
        
        # Buttons state update karna
        if self.logger.is_running:
            self.start_button.config(state=DISABLED)
            self.stop_button.config(state=NORMAL)
            self.port_combo.config(state=DISABLED)

    def _stop_btn_action(self):
        """ Stop button click hone par action. """
        if self.logger:
            status_message = self.logger.stop_acquisition()
            self.status_label.config(text=f"Status: {status_message}", foreground="blue")
            
            # Buttons state update karna
            self.start_button.config(state=NORMAL)
            self.stop_button.config(state=DISABLED)
            self.port_combo.config(state=NORMAL)

# --- Main Execution ---
if __name__ == "__main__":
    import sys
    
    try:
        app = Application()
        # Jab user window band kare toh logger ko theek se stop karna
        app.protocol("WM_DELETE_WINDOW", lambda: [app._stop_btn_action(), app.destroy()])
        app.mainloop()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"The application failed to start: {e}")