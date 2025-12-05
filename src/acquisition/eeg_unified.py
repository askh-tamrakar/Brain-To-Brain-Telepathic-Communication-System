"""
EEG Signal Acquisition System - Unified v4.0
SSVEP Real-time visualization with JSON data logging
Features: Live plotting, FFT spectrum, statistics, graph export
Author: BCI Team
Date: 2024-12-05
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import json
import threading
import time
import numpy as np
from datetime import datetime
from pathlib import Path
from collections import deque
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import queue


class EEGAcquisitionApp:
    """EEG Acquisition System with unified status, FFT & export"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("EEG Signal Acquisition - SSVEP v4.0")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')
        
        # Configuration
        self.PACKET_LEN = 8
        self.SYNC_BYTE_1 = 0xC7
        self.SYNC_BYTE_2 = 0x7C
        self.END_BYTE = 0x01
        self.SAMPLING_RATE = 512.0
        self.BAUD_RATE = 230400
        self.NUM_CHANNELS = 2
        
        # State
        self.ser = None
        self.is_connected = False
        self.is_acquiring = False
        self.is_recording = False
        self.acquisition_thread = None
        
        # Data storage
        self.packet_count = 0
        self.sample_count = 0
        self.bytes_received = 0
        self.session_start_time = None
        self.session_data = []
        self.recorded_data = []
        
        # Buffers
        self.graph_buffer_ch0 = deque(maxlen=512)
        self.graph_buffer_ch1 = deque(maxlen=512)
        self.graph_time_buffer = deque(maxlen=512)
        self.graph_index = 0
        
        # Queue for thread safety
        self.data_queue = queue.Queue()
        
        # Default save path
        self.save_path = Path("data/raw/session/eeg")
        
        # Setup UI
        self.setup_ui()
        self.update_port_list()
        self.root.after(30, self.update_graph_display)
        self.root.after(10, self.process_queue)
    
    def setup_ui(self):
        """Create the user interface"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # LEFT COLUMN: Controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=False, padx=5, ipadx=10)
        
        # RIGHT COLUMN: Graph
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)
        
        # ===== CONNECTION SECTION =====
        connection_frame = ttk.LabelFrame(left_frame, text="🔌 Connection", padding="10")
        connection_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Label(connection_frame, text="COM Port:", font=("Arial", 9)).pack(anchor="w", padx=5, pady=2)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, width=25, state="readonly")
        self.port_combo.pack(fill="x", padx=5, pady=2)
        
        self.refresh_btn = ttk.Button(connection_frame, text="🔄 Refresh Ports", command=self.update_port_list)
        self.refresh_btn.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(connection_frame, text="Baud: 230400 (Fixed) | 512 Hz", font=("Arial", 8)).pack(anchor="w", padx=5)
        
        # ===== STATUS SECTION =====
        status_frame = ttk.LabelFrame(left_frame, text="📊 Status", padding="10")
        status_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Label(status_frame, text="Connection:").pack(anchor="w", padx=5, pady=1)
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red", font=("Arial", 10, "bold"))
        self.status_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Acquisition:").pack(anchor="w", padx=5, pady=1)
        self.acq_label = ttk.Label(status_frame, text="Idle", foreground="gray", font=("Arial", 10, "bold"))
        self.acq_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Packets:").pack(anchor="w", padx=5, pady=1)
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.packet_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Duration:").pack(anchor="w", padx=5, pady=1)
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial", 10, "bold"))
        self.duration_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Rate (Hz):").pack(anchor="w", padx=5, pady=1)
        self.rate_label = ttk.Label(status_frame, text="0 Hz", font=("Arial", 10, "bold"))
        self.rate_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Speed (KBps):").pack(anchor="w", padx=5, pady=1)
        self.speed_label = ttk.Label(status_frame, text="0 KBps", font=("Arial", 10, "bold"))
        self.speed_label.pack(anchor="w", padx=5, pady=1)
        
        # ===== CONTROL BUTTONS =====
        control_frame = ttk.LabelFrame(left_frame, text="⚙️ Control", padding="10")
        control_frame.pack(fill="x", padx=0, pady=5)
        
        self.connect_btn = ttk.Button(control_frame, text="🔌 Connect", command=self.connect_device)
        self.connect_btn.pack(fill="x", padx=2, pady=2)
        
        self.disconnect_btn = ttk.Button(control_frame, text="❌ Disconnect", command=self.disconnect_device, state="disabled")
        self.disconnect_btn.pack(fill="x", padx=2, pady=2)
        
        self.start_btn = ttk.Button(control_frame, text="▶️ Start", command=self.start_acquisition, state="disabled")
        self.start_btn.pack(fill="x", padx=2, pady=2)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop", command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(fill="x", padx=2, pady=2)
        
        # ===== RECORDING SECTION =====
        rec_frame = ttk.LabelFrame(left_frame, text="📝 Recording", padding="10")
        rec_frame.pack(fill="x", padx=0, pady=5)
        
        self.rec_btn = ttk.Button(rec_frame, text="⏺️ Start Record", command=self.start_recording, state="disabled")
        self.rec_btn.pack(fill="x", padx=2, pady=2)
        
        self.stop_rec_btn = ttk.Button(rec_frame, text="⏹️ Stop Record", command=self.stop_recording, state="disabled")
        self.stop_rec_btn.pack(fill="x", padx=2, pady=2)
        
        # ===== SAVE OPTIONS =====
        save_frame = ttk.LabelFrame(left_frame, text="💾 Save", padding="10")
        save_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Button(save_frame, text="📁 Choose Path", command=self.choose_save_path).pack(fill="x", padx=2, pady=2)
        
        self.path_label = ttk.Label(save_frame, text="data/raw/session/eeg", font=("Arial", 8), wraplength=200, justify="left")
        self.path_label.pack(fill="x", padx=2, pady=5)
        
        self.save_btn = ttk.Button(save_frame, text="💾 Save Data", command=self.save_session_data, state="disabled")
        self.save_btn.pack(fill="x", padx=2, pady=2)
        
        self.export_btn = ttk.Button(save_frame, text="📊 Export Graph", command=self.export_graph, state="disabled")
        self.export_btn.pack(fill="x", padx=2, pady=2)
        
        # ===== STATISTICS =====
        stats_frame = ttk.LabelFrame(left_frame, text="📈 Stats", padding="10")
        stats_frame.pack(fill="both", expand=True, padx=0, pady=5)
        
        ttk.Label(stats_frame, text="Channel 0 (O1):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2, pady=1)
        self.ch0_min_label = ttk.Label(stats_frame, text="Min: 0", font=("Arial", 8))
        self.ch0_min_label.pack(anchor="w", padx=5, pady=0)
        self.ch0_max_label = ttk.Label(stats_frame, text="Max: 0", font=("Arial", 8))
        self.ch0_max_label.pack(anchor="w", padx=5, pady=0)
        self.ch0_mean_label = ttk.Label(stats_frame, text="Mean: 0", font=("Arial", 8))
        self.ch0_mean_label.pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(stats_frame, text="Channel 1 (O2):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2, pady=1)
        self.ch1_min_label = ttk.Label(stats_frame, text="Min: 0", font=("Arial", 8))
        self.ch1_min_label.pack(anchor="w", padx=5, pady=0)
        self.ch1_max_label = ttk.Label(stats_frame, text="Max: 0", font=("Arial", 8))
        self.ch1_max_label.pack(anchor="w", padx=5, pady=0)
        self.ch1_mean_label = ttk.Label(stats_frame, text="Mean: 0", font=("Arial", 8))
        self.ch1_mean_label.pack(anchor="w", padx=5, pady=2)
        
        # ===== GRAPH PANEL =====
        graph_frame = ttk.LabelFrame(right_frame, text="📡 Real-Time EEG Signal (512 Hz)", padding="5")
        graph_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(10, 6), dpi=100, facecolor='white')
        self.fig.patch.set_facecolor('#f0f0f0')
        
        # Subplot for signal
        self.ax_signal = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_signal.plot([], [], color='#667eea', linewidth=1.5, label='CH0 (O1)')
        self.line_ch1, = self.ax_signal.plot([], [], color='#f56565', linewidth=1.5, label='CH1 (O2)')
        self.ax_signal.set_ylabel('Voltage (µV)', fontsize=10)
        self.ax_signal.set_ylim(-2000, 2000)
        self.ax_signal.grid(True, alpha=0.3, linestyle='--')
        self.ax_signal.legend(loc='upper right', fontsize=9)
        self.ax_signal.set_title('Real-Time EEG Signal', fontsize=10, fontweight='bold')
        
        # Subplot for FFT
        self.ax_fft = self.fig.add_subplot(212)
        self.line_fft, = self.ax_fft.plot([], [], color='#667eea', linewidth=1.5)
        self.ax_fft.set_xlabel('Frequency (Hz)', fontsize=10)
        self.ax_fft.set_ylabel('Magnitude (µV)', fontsize=10)
        self.ax_fft.grid(True, alpha=0.3, linestyle='--')
        self.ax_fft.set_title('Frequency Spectrum (FFT)', fontsize=10, fontweight='bold')
        
        self.fig.tight_layout()
        
        # Embed matplotlib in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def update_port_list(self):
        """Refresh available COM ports"""
        ports = []
        for port, desc, hwid in serial.tools.list_ports.comports():
            ports.append(f"{port} - {desc}")
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)
    
    def connect_device(self):
        """Connect to Arduino"""
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return
        
        port_name = self.port_var.get().split(" ")[0]
        try:
            self.ser = serial.Serial(port_name, self.BAUD_RATE, timeout=0.1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.is_connected = True
            self.status_label.config(text="✅ Connected", foreground="green")
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.start_btn.config(state="normal")
            messagebox.showinfo("Success", f"Connected to {port_name}")
            
            # Start read thread
            self.acquisition_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.acquisition_thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")
    
    def disconnect_device(self):
        """Disconnect from Arduino"""
        if self.is_acquiring:
            self.stop_acquisition()
        
        self.is_connected = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        
        self.status_label.config(text="❌ Disconnected", foreground="red")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
    
    def read_serial_data(self):
        """Read serial data in background thread"""
        buffer = bytearray()
        while self.is_connected and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    if chunk:
                        self.bytes_received += len(chunk)
                        buffer.extend(chunk)
                    
                    while len(buffer) >= self.PACKET_LEN:
                        if (buffer[0] == self.SYNC_BYTE_1 and 
                            buffer[1] == self.SYNC_BYTE_2):
                            if buffer[self.PACKET_LEN - 1] == self.END_BYTE:
                                self.data_queue.put(bytes(buffer[:self.PACKET_LEN]))
                                del buffer[:self.PACKET_LEN]
                            else:
                                del buffer[0]
                        else:
                            del buffer[0]
                else:
                    time.sleep(0.001)
            except Exception as e:
                print(f"Read error: {e}")
                break
    
    def process_queue(self):
        """Process packets from queue"""
        try:
            while True:
                packet = self.data_queue.get_nowait()
                self.process_packet(packet)
        except queue.Empty:
            pass
        
        if self.root.winfo_exists():
            self.root.after(10, self.process_queue)
    
    def process_packet(self, packet):
        """Process a single packet"""
        try:
            self.packet_count += 1
            counter = packet[2]
            ch0 = (packet[4] << 8) | packet[3]
            ch1 = (packet[6] << 8) | packet[5]
            
            # Convert to µV
            ch0_uv = ((ch0 / 16384) * 3300) - 1650
            ch1_uv = ((ch1 / 16384) * 3300) - 1650
            
            self.graph_buffer_ch0.append(ch0_uv)
            self.graph_buffer_ch1.append(ch1_uv)
            self.graph_time_buffer.append(self.graph_index)
            self.graph_index += 1
            self.sample_count += 2
            
            # Store data
            data_entry = {
                "timestamp": datetime.now().isoformat(),
                "counter": counter,
                "ch0_uv": ch0_uv,
                "ch1_uv": ch1_uv,
                "ch0_raw": ch0,
                "ch1_raw": ch1
            }
            
            self.session_data.append(data_entry)
            
            if self.is_recording:
                self.recorded_data.append(data_entry)
            
            if self.packet_count % 50 == 0:
                self.root.after(0, self.update_status_labels)
        except Exception as e:
            print(f"Process error: {e}")
    
    def update_status_labels(self):
        """Update status displays"""
        if self.is_acquiring and self.session_start_time:
            elapsed = (datetime.now() - self.session_start_time).total_seconds()
            hours, remainder = divmod(int(elapsed), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.duration_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
            if elapsed > 0:
                rate = self.packet_count / elapsed
                speed_kbps = (self.bytes_received / elapsed) / 1024
                self.rate_label.config(text=f"{rate:.1f} Hz")
                self.speed_label.config(text=f"{speed_kbps:.2f} KBps")
            
            self.packet_label.config(text=str(self.packet_count))
            
            if len(self.graph_buffer_ch0) > 0:
                ch0_data = list(self.graph_buffer_ch0)
                self.ch0_min_label.config(text=f"Min: {min(ch0_data):.0f}")
                self.ch0_max_label.config(text=f"Max: {max(ch0_data):.0f}")
                self.ch0_mean_label.config(text=f"Mean: {np.mean(ch0_data):.0f}")
            
            if len(self.graph_buffer_ch1) > 0:
                ch1_data = list(self.graph_buffer_ch1)
                self.ch1_min_label.config(text=f"Min: {min(ch1_data):.0f}")
                self.ch1_max_label.config(text=f"Max: {max(ch1_data):.0f}")
                self.ch1_mean_label.config(text=f"Mean: {np.mean(ch1_data):.0f}")
    
    def update_graph_display(self):
        """Update graph with FFT"""
        if len(self.graph_buffer_ch0) == 0:
            if self.root.winfo_exists():
                self.root.after(30, self.update_graph_display)
            return
        
        try:
            x_data = list(self.graph_time_buffer)
            ch0_data = list(self.graph_buffer_ch0)
            ch1_data = list(self.graph_buffer_ch1)
            
            if len(x_data) > 1:
                # Update signal plot
                self.line_ch0.set_data(x_data, ch0_data)
                self.line_ch1.set_data(x_data, ch1_data)
                self.ax_signal.set_xlim(max(0, self.graph_index - 512), max(512, self.graph_index))
                
                # Update FFT plot
                if len(ch0_data) >= 256:
                    signal = ch0_data[-256:]
                    fft_data = np.fft.fft(signal)
                    freq = np.fft.fftfreq(256, 1 / self.SAMPLING_RATE)
                    magnitude = np.abs(fft_data)[:128]
                    
                    self.line_fft.set_data(freq[:128], magnitude)
                    self.ax_fft.set_xlim(0, 100)
                    max_mag = np.max(magnitude) if np.max(magnitude) > 0 else 1
                    self.ax_fft.set_ylim(0, max_mag * 1.2)
                
                self.canvas.draw_idle()
        except Exception as e:
            print(f"Graph error: {e}")
        
        if self.root.winfo_exists():
            self.root.after(30, self.update_graph_display)
    
    def start_acquisition(self):
        """Start acquisition"""
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Not connected")
            return
        
        try:
            self.ser.write(b"START\n")
            self.is_acquiring = True
            self.session_start_time = datetime.now()
            self.packet_count = 0
            self.sample_count = 0
            self.bytes_received = 0
            self.session_data = []
            
            self.acq_label.config(text="Acquiring", foreground="orange")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.rec_btn.config(state="normal")
            self.save_btn.config(state="normal")
            self.export_btn.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error", f"Start failed: {e}")
    
    def stop_acquisition(self):
        """Stop acquisition"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"STOP\n")
            except:
                pass
        
        self.is_acquiring = False
        self.is_recording = False
        self.acq_label.config(text="Idle", foreground="gray")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.rec_btn.config(state="disabled")
        self.stop_rec_btn.config(state="disabled")
    
    def start_recording(self):
        """Start recording data"""
        self.recorded_data = []
        self.is_recording = True
        self.rec_btn.config(state="disabled")
        self.stop_rec_btn.config(state="normal")
    
    def stop_recording(self):
        """Stop recording data"""
        self.is_recording = False
        self.rec_btn.config(state="normal")
        self.stop_rec_btn.config(state="disabled")
    
    def choose_save_path(self):
        """Choose save directory"""
        path = filedialog.askdirectory(title="Select save directory", initialdir=str(self.save_path.parent))
        if path:
            self.save_path = Path(path)
            self.path_label.config(text=str(self.save_path))
    
    def save_session_data(self):
        """Save session to JSON"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            self.save_path.mkdir(parents=True, exist_ok=True)
            
            filename = f"EEG_session_{timestamp}.json"
            filepath = self.save_path / filename
            
            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds(),
                    "total_packets": self.packet_count,
                    "sampling_rate_hz": self.SAMPLING_RATE,
                    "channels": self.NUM_CHANNELS,
                    "device": "Arduino Uno R4",
                    "sensor_type": "EEG",
                    "channel_0": "O1",
                    "channel_1": "O2"
                },
                "data": self.session_data
            }
            
            with open(filepath, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            messagebox.showinfo("Success", f"Saved {len(self.session_data)} packets\nFile: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
    
    def export_graph(self):
        """Export graph to PNG"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to export")
            return
        
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            filename = f"EEG_graph_{timestamp}.png"
            filepath = filedialog.asksaveasfilename(defaultextension=".png", initialfile=filename)
            
            if filepath:
                self.fig.savefig(filepath, dpi=150, bbox_inches='tight')
                messagebox.showinfo("Success", f"Graph exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")


def main():
    root = tk.Tk()
    app = EEGAcquisitionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
