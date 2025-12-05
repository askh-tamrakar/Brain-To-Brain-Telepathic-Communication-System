import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import serial.tools.list_ports
import threading
import csv
from datetime import datetime
import numpy as np
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import queue
import time


class SSVEPEEGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SSVEP EEG Data Acquisition System")
        self.root.geometry("1400x800")
        self.root.configure(bg='#f0f0f0')
        
        # Configuration
        self.CONFIG = {
            'PACKET_SIZE': 8,
            'SYNC_BYTE_1': 0xC7,
            'SYNC_BYTE_2': 0x7C,
            'END_BYTE': 0x01,
            'SAMP_RATE': 512,
            'NUM_CHANNELS': 2,
            'CHART_POINTS': 512
        }
        
        # State
        self.is_connected = False
        self.is_acquiring = False
        self.is_recording = False
        self.serial_port = None
        self.packet_count = 0
        self.sample_count = 0
        
        self.samples = {'ch0': deque(maxlen=512), 'ch1': deque(maxlen=512)}
        self.recorded_data = []
        
        self.read_thread = None
        self.stop_reading = False
        
        # Queue for thread-safe communication
        self.data_queue = queue.Queue()
        
        # Setup UI
        self.setup_ui()
        self.populate_com_ports()
        self.process_queue()  # Start queue processor
        
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # LEFT PANEL - Controls
        control_frame = ttk.LabelFrame(main_frame, text="Control Panel", padding=15)
        control_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Connection Section
        ttk.Label(control_frame, text="CONNECTION", font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(10,5))
        
        ttk.Label(control_frame, text="COM Port:").grid(row=1, column=0, sticky='w')
        self.com_var = tk.StringVar()
        self.com_dropdown = ttk.Combobox(control_frame, textvariable=self.com_var, state='readonly', width=20)
        self.com_dropdown.grid(row=1, column=1, sticky='ew', pady=5)
        
        ttk.Label(control_frame, text="Baud Rate:").grid(row=2, column=0, sticky='w')
        ttk.Label(control_frame, text="230400", font=('Arial', 9)).grid(row=2, column=1, sticky='w', pady=5)
        
        ttk.Button(control_frame, text="Connect", command=self.connect_device, width=20).grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Button(control_frame, text="Disconnect", command=self.disconnect_device, width=20).grid(row=4, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Status Section
        ttk.Label(control_frame, text="STATUS", font=('Arial', 10, 'bold')).grid(row=5, column=0, columnspan=2, sticky='w', pady=(15,5))
        
        ttk.Label(control_frame, text="Connection:").grid(row=6, column=0, sticky='w')
        self.status_label = ttk.Label(control_frame, text="Disconnected", foreground='red', font=('Arial', 9, 'bold'))
        self.status_label.grid(row=6, column=1, sticky='w')
        
        ttk.Label(control_frame, text="Acquisition:").grid(row=7, column=0, sticky='w')
        self.acq_label = ttk.Label(control_frame, text="Idle", foreground='gray', font=('Arial', 9, 'bold'))
        self.acq_label.grid(row=7, column=1, sticky='w')
        
        ttk.Label(control_frame, text="Device Info:").grid(row=8, column=0, sticky='w')
        self.device_label = ttk.Label(control_frame, text="Not connected", font=('Arial', 8))
        self.device_label.grid(row=8, column=1, sticky='w')
        
        # Acquisition Section
        ttk.Label(control_frame, text="ACQUISITION", font=('Arial', 10, 'bold')).grid(row=9, column=0, columnspan=2, sticky='w', pady=(15,5))
        
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_acquisition, width=9)
        self.start_btn.grid(row=10, column=0, sticky='ew', padx=(0,5))
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_acquisition, width=9)
        self.stop_btn.grid(row=10, column=1, sticky='ew')
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='disabled')
        
        # Recording Section
        ttk.Label(control_frame, text="DATA LOGGING", font=('Arial', 10, 'bold')).grid(row=11, column=0, columnspan=2, sticky='w', pady=(15,5))
        
        ttk.Label(control_frame, text="Session Name:").grid(row=12, column=0, sticky='w')
        self.session_var = tk.StringVar(value="SSVEP_Session")
        ttk.Entry(control_frame, textvariable=self.session_var, width=22).grid(row=12, column=1, sticky='ew', pady=5)
        
        self.record_btn = ttk.Button(control_frame, text="Record", command=self.start_recording, width=9)
        self.record_btn.grid(row=13, column=0, sticky='ew', padx=(0,5))
        self.stop_rec_btn = ttk.Button(control_frame, text="Stop Rec", command=self.stop_recording, width=9)
        self.stop_rec_btn.grid(row=13, column=1, sticky='ew')
        self.record_btn.config(state='disabled')
        self.stop_rec_btn.config(state='disabled')
        
        ttk.Button(control_frame, text="Save Data", command=self.save_data, width=20).grid(row=14, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Statistics Section
        ttk.Label(control_frame, text="STATISTICS", font=('Arial', 10, 'bold')).grid(row=15, column=0, columnspan=2, sticky='w', pady=(15,5))
        
        ttk.Label(control_frame, text="Packets:").grid(row=16, column=0, sticky='w')
        self.packet_label = ttk.Label(control_frame, text="0", font=('Arial', 9, 'bold'))
        self.packet_label.grid(row=16, column=1, sticky='w')
        
        ttk.Label(control_frame, text="Samples:").grid(row=17, column=0, sticky='w')
        self.sample_label = ttk.Label(control_frame, text="0", font=('Arial', 9, 'bold'))
        self.sample_label.grid(row=17, column=1, sticky='w')
        
        ttk.Button(control_frame, text="Reset", command=self.reset_counters, width=20).grid(row=18, column=0, columnspan=2, sticky='ew', pady=5)
        
        control_frame.columnconfigure(1, weight=1)
        
        # RIGHT PANEL - Visualization
        viz_frame = ttk.LabelFrame(main_frame, text="Data Visualization", padding=15)
        viz_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Message area
        self.message_label = ttk.Label(viz_frame, text="Ready to connect", foreground='blue', font=('Arial', 9))
        self.message_label.pack(fill='x', pady=(0,10))
        
        # Charts
        self.fig = Figure(figsize=(8, 6), dpi=80)
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)
        
        self.ax1.set_title('Real-time EEG Signal')
        self.ax1.set_ylabel('Voltage (µV)')
        self.ax1.set_ylim(-2000, 2000)
        self.ax1.grid(True, alpha=0.3)
        self.line1_ch0, = self.ax1.plot([], [], label='CH0 (O1)', color='#667eea', linewidth=1.5)
        self.line1_ch1, = self.ax1.plot([], [], label='CH1 (O2)', color='#f56565', linewidth=1.5)
        self.ax1.legend(loc='upper right')
        
        self.ax2.set_title('Frequency Spectrum (FFT)')
        self.ax2.set_xlabel('Frequency (Hz)')
        self.ax2.set_ylabel('Magnitude (µV)')
        self.ax2.grid(True, alpha=0.3)
        self.line2, = self.ax2.plot([], [], color='#667eea', linewidth=1.5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Packet details
        ttk.Label(viz_frame, text="Latest Packet Details", font=('Arial', 9, 'bold')).pack(pady=(10,5))
        self.packet_tree = ttk.Treeview(viz_frame, columns=('Value', 'Description'), height=6)
        self.packet_tree.column('#0', width=120)
        self.packet_tree.column('Value', width=80)
        self.packet_tree.column('Description', width=150)
        self.packet_tree.heading('#0', text='Field')
        self.packet_tree.heading('Value', text='Value')
        self.packet_tree.heading('Description', text='Description')
        self.packet_tree.pack(fill='x')
        
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)
        
    def populate_com_ports(self):
        try:
            ports = serial.tools.list_ports.comports()
            port_list = [port.device for port in ports]
            self.com_dropdown['values'] = port_list if port_list else ['No ports available']
            if port_list:
                self.com_dropdown.current(0)
        except Exception as e:
            print(f"Error detecting ports: {e}")
    
    def connect_device(self):
        try:
            port = self.com_var.get()
            if not port or port == 'No ports available':
                messagebox.showerror("Error", "Please select a valid COM port")
                return
            
            self.serial_port = serial.Serial(port, 230400, timeout=0.1)
            time.sleep(2)  # Wait for Arduino to initialize
            
            self.is_connected = True
            self.update_status()
            self.show_message("✓ Connected successfully!", 'green')
            
            # Start reading thread
            self.stop_reading = False
            self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.read_thread.start()
            
            # Enable buttons
            self.start_btn.config(state='normal')
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
    
    def disconnect_device(self):
        try:
            if self.is_acquiring:
                self.stop_acquisition()
            
            self.stop_reading = True
            time.sleep(0.5)  # Give thread time to exit
            
            if self.serial_port:
                self.serial_port.close()
            
            self.is_connected = False
            self.update_status()
            self.show_message("Disconnected successfully", 'blue')
            
            # Disable buttons
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='disabled')
            self.record_btn.config(state='disabled')
            self.stop_rec_btn.config(state='disabled')
            
        except Exception as e:
            messagebox.showerror("Disconnection Error", f"Error: {str(e)}")
    
    def read_serial_data(self):
        """Read serial data in background thread"""
        buffer = bytearray()
        sync_found = False
        
        while not self.stop_reading and self.is_connected:
            try:
                if self.serial_port.in_waiting > 0:
                    # Read available data
                    chunk = self.serial_port.read(self.serial_port.in_waiting)
                    buffer.extend(chunk)
                    
                    # Try to find and parse packets
                    while len(buffer) >= self.CONFIG['PACKET_SIZE']:
                        # Look for sync bytes
                        if not sync_found:
                            if buffer[0] == self.CONFIG['SYNC_BYTE_1']:
                                if len(buffer) > 1 and buffer[1] == self.CONFIG['SYNC_BYTE_2']:
                                    sync_found = True
                                else:
                                    buffer.pop(0)
                            else:
                                buffer.pop(0)
                        
                        # If sync found, try to extract packet
                        if sync_found and len(buffer) >= self.CONFIG['PACKET_SIZE']:
                            packet = bytes(buffer[:self.CONFIG['PACKET_SIZE']])
                            
                            # Validate end byte
                            if packet[7] == self.CONFIG['END_BYTE']:
                                # Valid packet
                                self.data_queue.put(packet)
                                buffer = buffer[self.CONFIG['PACKET_SIZE']:]
                                sync_found = False
                            else:
                                # Invalid packet, skip first byte and search again
                                buffer.pop(0)
                                sync_found = False
                else:
                    time.sleep(0.001)  # Small delay to prevent busy waiting
                    
            except Exception as e:
                print(f"Read error: {e}")
                break
    
    def process_queue(self):
        """Process packets from queue in main thread"""
        try:
            while True:
                packet = self.data_queue.get_nowait()
                self.process_packet(packet)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(10, self.process_queue)
    
    def process_packet(self, packet):
        """Process a single packet"""
        try:
            self.packet_count += 1
            counter = packet[2]
            ch0 = (packet[3] << 8) | packet[4]
            ch1 = (packet[5] << 8) | packet[6]
            
            # Convert to µV (assuming 14-bit ADC, 3.3V reference)
            ch0_uv = ((ch0 / 16384) * 3300) - 1650
            ch1_uv = ((ch1 / 16384) * 3300) - 1650
            
            self.samples['ch0'].append(ch0_uv)
            self.samples['ch1'].append(ch1_uv)
            self.sample_count += 2
            
            # Update UI elements
            self.update_ui_elements(counter, ch0, ch1, ch0_uv, ch1_uv, packet)
            
            # Log if recording
            if self.is_recording:
                self.recorded_data.append({
                    'timestamp': datetime.now(),
                    'counter': counter,
                    'ch0_uv': ch0_uv,
                    'ch1_uv': ch1_uv,
                    'raw_ch0': ch0,
                    'raw_ch1': ch1
                })
        except Exception as e:
            print(f"Process packet error: {e}")
    
    def update_ui_elements(self, counter, ch0, ch1, ch0_uv, ch1_uv, packet):
        """Update UI elements with new data"""
        try:
            # Update labels
            self.packet_label.config(text=str(self.packet_count))
            self.sample_label.config(text=str(self.sample_count))
            
            # Update charts
            if len(self.samples['ch0']) > 0:
                x_data = list(range(len(self.samples['ch0'])))
                self.line1_ch0.set_data(x_data, list(self.samples['ch0']))
                self.line1_ch1.set_data(x_data, list(self.samples['ch1']))
                self.ax1.set_xlim(0, max(1, len(self.samples['ch0'])))
                
                # Simple FFT
                if len(self.samples['ch0']) >= 256:
                    signal = list(self.samples['ch0'])[-256:]
                    fft_data = np.fft.fft(signal)
                    freq = np.fft.fftfreq(256, 1/self.CONFIG['SAMP_RATE'])
                    magnitude = np.abs(fft_data)[:128]
                    self.line2.set_data(freq[:128], magnitude)
                    self.ax2.set_xlim(0, 100)
                    max_mag = np.max(magnitude)
                    self.ax2.set_ylim(0, max_mag * 1.2 if max_mag > 0 else 1)
                
                self.canvas.draw_idle()
            
            # Update packet details
            self.packet_tree.delete(*self.packet_tree.get_children())
            details = [
                ('Sync1', f'0x{packet[0]:02X}', 'Should be 0xC7'),
                ('Sync2', f'0x{packet[1]:02X}', 'Should be 0x7C'),
                ('Counter', str(counter), 'Packet sequence'),
                ('CH0 Raw', f'{ch0}', 'O1 ADC (0-16383)'),
                ('CH0 µV', f'{ch0_uv:.2f}', 'O1 Voltage'),
                ('CH1 Raw', f'{ch1}', 'O2 ADC (0-16383)'),
                ('CH1 µV', f'{ch1_uv:.2f}', 'O2 Voltage'),
                ('End', f'0x{packet[7]:02X}', 'Should be 0x01')
            ]
            
            for field, value, desc in details:
                self.packet_tree.insert('', 'end', text=field, values=(value, desc))
        except Exception as e:
            print(f"UI update error: {e}")
    
    def start_acquisition(self):
        try:
            self.serial_port.write(b'START\n')
            self.is_acquiring = True
            self.update_status()
            self.show_message("✓ Acquisition started", 'green')
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            self.record_btn.config(state='normal')
        except Exception as e:
            messagebox.showerror("Error", f"Start failed: {str(e)}")
    
    def stop_acquisition(self):
        try:
            self.serial_port.write(b'STOP\n')
            self.is_acquiring = False
            self.is_recording = False
            self.update_status()
            self.show_message("Acquisition stopped", 'blue')
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.record_btn.config(state='disabled')
            self.stop_rec_btn.config(state='disabled')
        except Exception as e:
            messagebox.showerror("Error", f"Stop failed: {str(e)}")
    
    def start_recording(self):
        self.recorded_data = []
        self.is_recording = True
        self.show_message("✓ Recording started", 'green')
        self.record_btn.config(state='disabled')
        self.stop_rec_btn.config(state='normal')
    
    def stop_recording(self):
        self.is_recording = False
        self.show_message(f"Recording stopped. {len(self.recorded_data)} samples captured.", 'blue')
        self.record_btn.config(state='normal')
        self.stop_rec_btn.config(state='disabled')
    
    def save_data(self):
        if not self.recorded_data:
            messagebox.showerror("Error", "No data to save")
            return
        
        session_name = self.session_var.get() or "SSVEP_Session"
        filename = f"{session_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", 
                                               initialfile=filename,
                                               filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        
        if filepath:
            try:
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Timestamp', 'Counter', 'CH0_µV', 'CH1_µV', 'Raw_CH0', 'Raw_CH1'])
                    for sample in self.recorded_data:
                        writer.writerow([
                            sample['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f'),
                            sample['counter'],
                            f"{sample['ch0_uv']:.2f}",
                            f"{sample['ch1_uv']:.2f}",
                            sample['raw_ch0'],
                            sample['raw_ch1']
                        ])
                messagebox.showinfo("Success", f"Data saved to {filepath}")
                self.show_message(f"✓ Data saved successfully ({len(self.recorded_data)} samples)", 'green')
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")
    
    def reset_counters(self):
        self.packet_count = 0
        self.sample_count = 0
        self.samples['ch0'].clear()
        self.samples['ch1'].clear()
        self.recorded_data = []
        self.packet_label.config(text='0')
        self.sample_label.config(text='0')
        self.show_message("Counters reset", 'blue')
    
    def update_status(self):
        if self.is_connected:
            self.status_label.config(text="Connected", foreground='green')
            self.device_label.config(text="UNO R4 @ 230400 baud")
        else:
            self.status_label.config(text="Disconnected", foreground='red')
            self.device_label.config(text="Not connected")
        
        if self.is_acquiring:
            self.acq_label.config(text="Acquiring", foreground='orange')
        else:
            self.acq_label.config(text="Idle", foreground='gray')
    
    def show_message(self, message, color='black'):
        self.message_label.config(text=message, foreground=color)


if __name__ == "__main__":
    root = tk.Tk()
    app = SSVEPEEGApp(root)
    root.mainloop()
