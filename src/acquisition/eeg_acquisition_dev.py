import serial
import json
import time
from datetime import datetime
import threading
from tkinter import *
from tkinter import ttk, messagebox
import glob
import sys

# Matplotlib dependencies for live plotting
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import collections

# --- Configuration ---
# File jahan data save hoga
OUTPUT_FILENAME = "eeg_data_log.json"
# Baud rate jo Arduino ke code se match hona chahiye
BAUD_RATE = 115200 
# Aapke packets ka size
PACKET_SIZE = 8
# Sync bytes
SYNC1 = 0xC7
SYNC2 = 0x7C
# Data points ki sankhya jo plot mein dikhegi
PLOT_WINDOW_SIZE = 500 


class SerialDataLogger:
    """ Serial Port se data acquire karne aur use JSON mein save karne ke liye class. """
    def __init__(self, port, baudrate, plot_callback=None):
        self.ser = None
        self.is_running = False
        self.port = port
        self.baudrate = baudrate
        self.log_thread = None
        self.data_buffer = []
        self.plot_callback = plot_callback
        # Live plot ke liye data queues
        self.ch0_data = collections.deque([0.0] * PLOT_WINDOW_SIZE, maxlen=PLOT_WINDOW_SIZE)
        self.ch1_data = collections.deque([0.0] * PLOT_WINDOW_SIZE, maxlen=PLOT_WINDOW_SIZE)
        self.packet_count = 0 # Packet counter for tracking

    def start_acquisition(self):
        """ Data acquisition shuru karta hai. """
        if self.is_running:
            return "Acquisition is already running."

        try:
            # Serial connection establish karna
            # Timeout kam rakhte hain taaki non-blocking read ho
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.01) 
            time.sleep(2) 
            
            if self.ser.is_open:
                # Arduino ko 'start' command bhejna (agar zaroori ho)
                # self.ser.write(b'START\n') 
                
                self.is_running = True
                self.log_thread = threading.Thread(target=self._log_data)
                self.log_thread.daemon = True # Taaki main program band hone par thread bhi band ho jaaye
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
            self.log_thread.join(timeout=2) # 2 second ka timeout dete hain
        
        # Connection band karna
        if self.ser and self.ser.is_open:
            # self.ser.write(b'STOP\n') # Agar zaroori ho
            self.ser.close()

        # Buffer mein jama data ko JSON file mein save karna
        self._save_to_json()
        return f"Acquisition stopped. Data saved to {OUTPUT_FILENAME}. Total packets received: {self.packet_count}"

    def _parse_packet(self, packet_bytes):
        """ 8-byte binary packet ko parse karta hai. 
            Format: [SYNC1][SYNC2][CTR][Ch0_H][Ch0_L][Ch1_H][Ch1_L][END]
            Hum 'END' byte ko ignore kar rahe hain, aur sirf data nikaal rahe hain.
        """
        # Data bytes: [Ch0_H][Ch0_L] aur [Ch1_H][Ch1_L]
        # Ch0: packet_bytes[3:5], Ch1: packet_bytes[5:7]

        # 10-bit resolution ke liye (0-1023) assumed. High aur Low bytes ko jodna.
        
        # NOTE: Arduino se data kaise bhej rahe hain uspar depend karta hai.
        # Agar yeh 10-bit values hain:
        
        # Ch0_H = packet_bytes[3]
        # Ch0_L = packet_bytes[4]
        # Ch1_H = packet_bytes[5]
        # Ch1_L = packet_bytes[6]
        
        # 10-bit data ko 16-bit integer mein convert karna (Assuming standard format)
        # Data format: Ch0_H (high 8 bits) | Ch0_L (low 2 bits) + 6 zero bits
        # Ya phir, agar yeh simply High/Low bytes hain, toh 
        
        # Simplifying: 
        # Hum maan rahe hain ki Arduino ne 10-bit value ko 2-bytes mein split karke bheja hai.
        # Ch0 = (packet_bytes[3] << 8) | packet_bytes[4] 
        # Ch1 = (packet_bytes[5] << 8) | packet_bytes[6]

        # Based on your diagnostics: 'C7 7C 90 20 0E 0D 8F 01'
        # CTR=90. Ch0_H=20, Ch0_L=0E. Ch1_H=0D, Ch1_L=8F. END=01.
        
        # Value for Ch0: 0x200E = 8206
        ch0_raw = (packet_bytes[3] << 8) | packet_bytes[4]
        # Value for Ch1: 0x0D8F = 3471
        ch1_raw = (packet_bytes[5] << 8) | packet_bytes[6]

        # Raw values ko voltage ya meaningful units mein convert karna aapke Arduino code par depend karta hai.
        # Abhi ke liye hum raw values use kar rahe hain.
        
        return ch0_raw, ch1_raw


    def _log_data(self):
        """ Background mein data acquire karne ka kaam karta hai. """
        
        # Partial packet ko store karne ke liye buffer
        partial_packet = bytearray() 
        
        while self.is_running:
            try:
                # 1 byte read karna (non-blocking)
                byte = self.ser.read(1)
                
                if byte:
                    byte_int = byte[0]
                    
                    # Agar buffer mein kuch nahi hai aur pehla sync byte mil jaaye
                    if not partial_packet and byte_int == SYNC1:
                        partial_packet.append(byte_int)
                    # Agar pehla sync byte mil gaya hai aur doosra sync byte bhi mil jaaye
                    elif len(partial_packet) == 1 and partial_packet[0] == SYNC1 and byte_int == SYNC2:
                        partial_packet.append(byte_int)
                    # Agar packet shuru ho chuka hai
                    elif len(partial_packet) > 1:
                        partial_packet.append(byte_int)
                        
                        # Agar pura packet mil gaya hai
                        if len(partial_packet) == PACKET_SIZE:
                            
                            # Packet ko parse karna
                            ch0, ch1 = self._parse_packet(partial_packet)
                            
                            # Timestamp add karna
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                            
                            # Data entry banana
                            data_entry = {
                                "timestamp": timestamp, 
                                "ctr": partial_packet[2], 
                                "ch0": ch0, 
                                "ch1": ch1
                            }
                            
                            # Data ko buffer mein add karna
                            self.data_buffer.append(data_entry)
                            self.packet_count += 1
                            
                            # Plotting ke liye data update karna
                            self.ch0_data.append(ch0)
                            self.ch1_data.append(ch1)
                            
                            # GUI update ke liye callback function ko call karna
                            if self.plot_callback:
                                self.plot_callback()
                                
                            # Packet process ho gaya, buffer ko clear karna
                            partial_packet = bytearray()
                        
                    # Agar beech mein sync byte miss ho gaya aur phir se sync1 aa jaaye
                    elif len(partial_packet) > 0 and byte_int == SYNC1:
                        # Purana data reject karo aur naya packet shuru karo
                        partial_packet = bytearray([byte_int])
                    # Agar beech mein kuch aur random byte aa jaaye toh purana partial data reject karo
                    elif len(partial_packet) > 0:
                        partial_packet = bytearray()
                        
            except serial.SerialTimeoutException:
                # Timeout hone par kuch nahi karna
                pass  
            except Exception as e:
                if self.is_running:
                    print(f"Acquisition error: {e}")
                    self.is_running = False
                break

    def _save_to_json(self):
        """ Buffer mein jama data ko JSON file mein save karta hai. """
        if not self.data_buffer:
            return

        try:
            # File ko 'append' mode mein open karna
            with open(OUTPUT_FILENAME, 'a') as f:
                for entry in self.data_buffer:
                    f.write(json.dumps(entry) + '\n')
            
            self.data_buffer = []

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save data to JSON: {e}")


# --- GUI Application ---
class Application(Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ SSVEP Serial Logger & Dashboard")
        self.geometry("800x600") # Window size badhana
        
        self.logger = None
        self.style = ttk.Style(self)
        self.style.configure('TButton', font=('Arial', 10, 'bold'), padding=5)

        # Plotting setup
        self.fig, (self.ax0, self.ax1) = plt.subplots(2, 1, figsize=(7, 4), tight_layout=True)
        self.fig.patch.set_facecolor('#f0f0f0') # Background color
        self._setup_plots()

        self._create_widgets()

        # Animation setup for live plot
        self.plot_update_id = None


    def _setup_plots(self):
        """ Matplotlib plots ko configure karna. """
        
        # Channel 0 Plot
        self.line0, = self.ax0.plot([], [], 'r-')
        self.ax0.set_title('Channel 0 Signal (Raw)')
        self.ax0.set_ylabel('Raw Value')
        self.ax0.grid(True, linestyle='--', alpha=0.6)
        self.ax0.set_xlim(0, PLOT_WINDOW_SIZE)
        self.ax0.set_ylim(-100, 70000) # Initial y-limit, adjust according to max 16-bit value

        # Channel 1 Plot
        self.line1, = self.ax1.plot([], [], 'b-')
        self.ax1.set_title('Channel 1 Signal (Raw)')
        self.ax1.set_xlabel('Sample Number')
        self.ax1.set_ylabel('Raw Value')
        self.ax1.grid(True, linestyle='--', alpha=0.6)
        self.ax1.set_xlim(0, PLOT_WINDOW_SIZE)
        self.ax1.set_ylim(-100, 70000) # Initial y-limit

    def _create_widgets(self):
        # Main Frame for Controls
        control_frame = ttk.Frame(self, padding="10")
        control_frame.pack(side=TOP, fill='x')

        # Frame for Port Selection
        port_frame = ttk.Frame(control_frame)
        port_frame.pack(side='left', padx=10)

        ttk.Label(port_frame, text="Select Port:").pack(side='left', padx=5)
        self.port_var = StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=15)
        self.port_combo['values'] = self._get_available_ports()
        self.port_combo.pack(side='left', padx=5)
        ttk.Button(port_frame, text="🔄 Refresh Ports", command=self._refresh_ports).pack(side='left', padx=5)

        # Frame for Control Buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side='right', padx=10)

        self.start_button = ttk.Button(button_frame, text="▶️ START Acquisition", command=self._start_btn_action, style='TButton')
        self.start_button.pack(side='left', padx=10)

        self.stop_button = ttk.Button(button_frame, text="⏹️ STOP and Save", command=self._stop_btn_action, state=DISABLED, style='TButton')
        self.stop_button.pack(side='left', padx=10)

        # Status Label
        self.status_label = ttk.Label(self, text="Status: Ready", foreground="blue", font=('Arial', 10, 'bold'))
        self.status_label.pack(pady=5)

        # Matplotlib Plot Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(side=BOTTOM, fill=BOTH, expand=1)

        # Output File Info
        ttk.Label(self, text=f"Data will be appended to: {OUTPUT_FILENAME}", font=('Arial', 8)).pack(side=BOTTOM, pady=2)
    
    # Port functions (same as before)
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
            # Puraani value set karne ki koshish, warna pehli value
            current_port = self.port_var.get()
            if current_port in ports:
                self.port_var.set(current_port)
            else:
                self.port_var.set(ports[0])
        else:
            self.port_var.set("No Ports Found")

    # Live Plotting Logic
    def _update_plot(self):
        """ Logger se data lekar plot update karta hai. """
        if not self.logger or not self.logger.is_running:
            return

        # Data series update karna
        x_data = list(range(PLOT_WINDOW_SIZE))
        y0_data = list(self.logger.ch0_data)
        y1_data = list(self.logger.ch1_data)

        # Lines ko naye data ke saath update karna
        self.line0.set_data(x_data, y0_data)
        self.line1.set_data(x_data, y1_data)

        # Y-axis limits ko auto-scale karna
        max_val = max(max(y0_data), max(y1_data)) if (y0_data or y1_data) else 100
        min_val = min(min(y0_data), min(y1_data)) if (y0_data or y1_data) else 0

        # Thoda padding add karna
        padding = (max_val - min_val) * 0.1
        if padding == 0: padding = 100 # Default padding agar data flat ho
        
        # Agar limits mein zaroori change ho toh update karna
        current_y0_min, current_y0_max = self.ax0.get_ylim()
        current_y1_min, current_y1_max = self.ax1.get_ylim()

        new_min = min(min_val - padding, current_y0_min, current_y1_min)
        new_max = max(max_val + padding, current_y0_max, current_y1_max)
        
        # Only update if change is significant
        if new_max > current_y0_max or new_min < current_y0_min:
             self.ax0.set_ylim(new_min, new_max)
             self.ax1.set_ylim(new_min, new_max)
        
        # Canvas ko redraw karna
        self.canvas.draw_idle()
        
        # Next update scheduled karna (100 ms ke baad)
        self.plot_update_id = self.after(100, self._update_plot)
    
    # Button Actions
    def _start_btn_action(self):
        """ Start button click hone par action. """
        selected_port = self.port_var.get()
        if not selected_port or selected_port == "No Ports Found":
            messagebox.showwarning("Error", "Please select a valid Serial Port.")
            return

        # Logger object banana, plot update function pass karna
        self.logger = SerialDataLogger(selected_port, BAUD_RATE, plot_callback=lambda: self._trigger_plot_update())
        
        status_message = self.logger.start_acquisition()

        self.status_label.config(text=f"Status: {status_message}", foreground="green" if "started" in status_message else "red")
        
        if self.logger.is_running:
            self.start_button.config(state=DISABLED)
            self.stop_button.config(state=NORMAL)
            self.port_combo.config(state=DISABLED)
            
            # Plotting shuru karna
            self._update_plot()

    def _trigger_plot_update(self):
        """ This is called from the logger thread. We need to schedule the GUI update 
            in the main thread using self.after to avoid thread conflicts. 
        """
        # Hum sirf update schedule kar rahe hain, direct call nahi kar rahe
        # Python's deque handles thread-safety for append/pop
        pass 
        

    def _stop_btn_action(self):
        """ Stop button click hone par action. """
        if self.logger:
            status_message = self.logger.stop_acquisition()
            self.status_label.config(text=f"Status: {status_message}", foreground="blue")
            
            # Plotting band karna
            if self.plot_update_id:
                self.after_cancel(self.plot_update_id)
                self.plot_update_id = None
            
            # Buttons state update karna
            self.start_button.config(state=NORMAL)
            self.stop_button.config(state=DISABLED)
            self.port_combo.config(state=NORMAL)

# --- Main Execution ---
if __name__ == "__main__":
    # Check for Matplotlib
    try:
        pass # Already imported
    except ImportError:
        messagebox.showerror("Dependency Error", "Matplotlib library is not installed. Please install it using: pip install matplotlib")
        sys.exit(1)

    try:
        app = Application()
        # Jab user window band kare toh logger ko theek se stop karna
        app.protocol("WM_DELETE_WINDOW", lambda: [app._stop_btn_action(), app.destroy()])
        app.mainloop()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"The application failed to start: {e}")