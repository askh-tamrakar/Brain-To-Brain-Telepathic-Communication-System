"""
emg_acquisition_modular.py - EMG Acquisition Module (Refactored)
This module is designed to work as a modular component with RUN_EMG.py

Key changes from original:
- Removed dependency on RUN_EMG.py
- Added data callback mechanism for pipeline integration
- Maintains Tkinter UI but feeds data to external handlers
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


class EMGAcquisitionModule:
    """
    Modular EMG acquisition without embedded Tkinter dependency
    Can be instantiated separately or with Tkinter UI
    """
    
    def __init__(self, sampling_rate: float = 512.0, num_channels: int = 2):
        """
        Initialize acquisition module
        
        Args:
            sampling_rate: ADC sampling rate in Hz
            num_channels: Number of EMG channels
        """
        # Device config
        self.PACKET_LEN = 8
        self.SYNC_BYTE_1 = 0xC7
        self.SYNC_BYTE_2 = 0x7C
        self.END_BYTE = 0x01
        self.SAMPLING_RATE = sampling_rate
        self.BAUD_RATE = 230400
        self.NUM_CHANNELS = num_channels
        
        # Connection state
        self.ser = None
        self.acquisition_active = False
        
        # Data queues
        self.data_queue = queue.Queue()  # For thread-safe packet passing
        self.read_thread = None
        
        # Statistics
        self.packet_count = 0
        self.bytes_received = 0
        self.session_start_time = None
        
        # Callbacks for external handlers
        self.on_packet_received = None  # Callback function
        self.on_acquisition_state_changed = None
    
    def connect(self, port_name: str) -> bool:
        """
        Connect to serial port
        
        Args:
            port_name: COM port name (e.g., "COM3")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.ser = serial.Serial(port_name, self.BAUD_RATE, timeout=1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            
            if self.on_acquisition_state_changed:
                self.on_acquisition_state_changed('connected', port_name)
            
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            if self.on_acquisition_state_changed:
                self.on_acquisition_state_changed('failed', str(e))
            return False
    
    def disconnect(self):
        """Disconnect from serial port"""
        if self.acquisition_active:
            self.stop_acquisition()
        
        if self.ser and self.ser.is_open:
            self.ser.close()
        
        if self.on_acquisition_state_changed:
            self.on_acquisition_state_changed('disconnected', None)
    
    def start_acquisition(self):
        """Start acquiring data"""
        if not self.ser or not self.ser.is_open:
            print("Not connected")
            return False
        
        try:
            self.ser.write(b"START\\n")
        except:
            pass
        
        self.acquisition_active = True
        self.packet_count = 0
        self.bytes_received = 0
        self.session_start_time = datetime.now()
        
        if self.on_acquisition_state_changed:
            self.on_acquisition_state_changed('started', None)
        
        return True
    
    def stop_acquisition(self):
        """Stop acquiring data"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"STOP\\n")
            except:
                pass
        
        self.acquisition_active = False
        
        if self.on_acquisition_state_changed:
            self.on_acquisition_state_changed('stopped', None)
    
    def _read_loop(self):
        """Background thread: read serial data and parse packets"""
        buffer = bytearray()
        
        while self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    if chunk:
                        self.bytes_received += len(chunk)
                        buffer.extend(chunk)
                        
                        # Parse packets from buffer
                        while len(buffer) >= self.PACKET_LEN:
                            if buffer[0] == self.SYNC_BYTE_1 and buffer[1] == self.SYNC_BYTE_2:
                                if buffer[self.PACKET_LEN - 1] == self.END_BYTE:
                                    packet = bytes(buffer[:self.PACKET_LEN])
                                    self.data_queue.put(packet)
                                    del buffer[:self.PACKET_LEN]
                                else:
                                    del buffer[0]
                            else:
                                del buffer[0]
                else:
                    time.sleep(0.001)
            except Exception as e:
                print(f"Read error: {e}")
                time.sleep(0.1)
    
    def get_next_packet(self) -> dict:
        """
        Get next parsed packet
        
        Returns:
            Dict with parsed data or None if queue empty
        """
        try:
            packet = self.data_queue.get_nowait()
            
            # Parse packet
            counter = packet[2]
            ch0_raw = (packet[4] << 8) | packet[3]
            ch1_raw = (packet[6] << 8) | packet[5]
            
            parsed = {
                'timestamp': datetime.now(),
                'sequence_counter': int(counter),
                'ch0_raw_adc': int(ch0_raw),
                'ch1_raw_adc': int(ch1_raw),
                'packet_number': int(self.packet_count),
            }
            
            self.packet_count += 1
            
            # Call callback if registered
            if self.on_packet_received:
                self.on_packet_received(parsed)
            
            return parsed
        except queue.Empty:
            return None
    
    def get_statistics(self) -> dict:
        """Get current acquisition statistics"""
        elapsed = (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0
        
        return {
            'packet_count': self.packet_count,
            'bytes_received': self.bytes_received,
            'elapsed_seconds': elapsed,
            'packet_rate': self.packet_count / elapsed if elapsed > 0 else 0,
            'byte_rate_kbps': (self.bytes_received / elapsed / 1024) if elapsed > 0 else 0,
        }


class EMGAcquisitionApp:
    """
    Tkinter UI for EMG acquisition (original UI maintained)
    Now uses EMGAcquisitionModule internally
    """
    
    def __init__(self, root, pipeline_callback=None):
        """
        Args:
            root: Tkinter root window
            pipeline_callback: Optional callback function for each packet
        """
        self.root = root
        self.root.title("EMG Signal Acquisition - Pipeline Ready v6.0")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')
        
        # Use modular acquisition
        self.acq = EMGAcquisitionModule(sampling_rate=512.0, num_channels=2)
        self.acq.on_acquisition_state_changed = self._on_state_changed
        self.acq.on_packet_received = pipeline_callback or self._default_packet_handler
        
        # UI State
        self.is_recording = False
        self.recorded_data = []
        self.save_path = Path("data/raw/session/emg")
        
        # Buffers for UI
        self.graph_buffer_ch0 = deque(maxlen=1024)
        self.graph_buffer_ch1 = deque(maxlen=1024)
        self.graph_time_buffer = deque(maxlen=1024)
        self.graph_index = 0
        self.latest_packet = {}
        
        # Stats
        self.pending_updates = 0
        self.last_update_time = time.time()
        self.update_interval = 0.1
        
        self.setup_ui()
        self.update_port_list()
        
        # Single update loop
        self.root.after(30, self.main_update_loop)
    
    def _default_packet_handler(self, packet):
        """Default handler if no external callback"""
        self.graph_buffer_ch0.append(packet['ch0_raw_adc'])
        self.graph_buffer_ch1.append(packet['ch1_raw_adc'])
        self.graph_time_buffer.append(self.graph_index)
        self.graph_index += 1
        self.latest_packet = packet
        self.pending_updates += 1
        
        if self.is_recording:
            self.recorded_data.append(packet)
    
    def _on_state_changed(self, state, info):
        """Handle acquisition state changes"""
        if state == 'connected':
            self.status_label.config(text="✅ Connected", foreground="green")
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.start_btn.config(state="normal")
        elif state == 'disconnected':
            self.status_label.config(text="❌ Disconnected", foreground="red")
            self.connect_btn.config(state="normal")
            self.disconnect_btn.config(state="disabled")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
        elif state == 'started':
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.pause_rec_btn.config(state="normal")
            self.save_btn.config(state="normal")
        elif state == 'stopped':
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.pause_rec_btn.config(state="disabled")
    
    def make_scrollable_left_panel(self, parent):
        """Create scrollable left panel"""
        container = ttk.Frame(parent)
        container.pack(side="left", fill="y", expand=False, padx=5, pady=5)
        
        canvas = tk.Canvas(container, width=320, highlightthickness=0, bg='white')
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _on_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)
        
        canvas.pack(side="left", fill="y", expand=False)
        scrollbar.pack(side="right", fill="y")
        
        return scrollable_frame
    
    def setup_ui(self):
        """Setup Tkinter UI"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        left_container = ttk.Frame(main_frame)
        left_container.pack(side="left", fill="y", expand=False)
        
        left_frame = self.make_scrollable_left_panel(left_container)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)
        
        # === CONNECTION FRAME ===
        connection_frame = ttk.LabelFrame(left_frame, text="🔌 Connection", padding=10)
        connection_frame.pack(fill="x", pady=5, padx=5)
        
        ttk.Label(connection_frame, text="COM Port:").pack(anchor="w", padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, width=30, state="readonly")
        self.port_combo.pack(fill="x", padx=5, pady=2)
        
        ttk.Button(connection_frame, text="🔄 Refresh Ports", command=self.update_port_list).pack(fill="x", padx=5, pady=2)
        ttk.Label(connection_frame, text=f"Baud: 230400 | 512 Hz").pack(anchor="w", padx=5)
        
        # === STATUS FRAME ===
        status_frame = ttk.LabelFrame(left_frame, text="📊 Status", padding=10)
        status_frame.pack(fill="x", pady=5, padx=5)
        
        ttk.Label(status_frame, text="Connection:").pack(anchor="w", padx=5)
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red", font=("Arial",10,"bold"))
        self.status_label.pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(status_frame, text="Packets:").pack(anchor="w", padx=5)
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.packet_label.pack(anchor="w", padx=5)
        
        ttk.Label(status_frame, text="Duration:").pack(anchor="w", padx=5)
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial", 10, "bold"))
        self.duration_label.pack(anchor="w", padx=5)
        
        # === CONTROL FRAME ===
        control_frame = ttk.LabelFrame(left_frame, text="⚙️ Control", padding=10)
        control_frame.pack(fill="x", pady=5, padx=5)
        
        self.connect_btn = ttk.Button(control_frame, text="🔌 Connect", command=self.connect_arduino)
        self.connect_btn.pack(fill="x", padx=2, pady=2)
        
        self.disconnect_btn = ttk.Button(control_frame, text="❌ Disconnect", command=self.disconnect_arduino, state="disabled")
        self.disconnect_btn.pack(fill="x", padx=2, pady=2)
        
        self.start_btn = ttk.Button(control_frame, text="▶️ Start Acquisition", command=self.start_acq, state="disabled")
        self.start_btn.pack(fill="x", padx=2, pady=2)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop Acquisition", command=self.stop_acq, state="disabled")
        self.stop_btn.pack(fill="x", padx=2, pady=2)
        
        # === RECORDING FRAME ===
        rec_frame = ttk.LabelFrame(left_frame, text="📝 Recording", padding=10)
        rec_frame.pack(fill="x", pady=5, padx=5)
        
        self.pause_rec_btn = ttk.Button(rec_frame, text="⏸️ Pause Recording", command=self.toggle_recording, state="disabled")
        self.pause_rec_btn.pack(fill="x", padx=2, pady=2)
        
        # === SAVE FRAME ===
        save_frame = ttk.LabelFrame(left_frame, text="💾 Save / Export", padding=10)
        save_frame.pack(fill="x", pady=5, padx=5)
        
        self.save_btn = ttk.Button(save_frame, text="💾 Save Session", command=self.save_session, state="disabled")
        self.save_btn.pack(fill="x", padx=2, pady=2)
        
        # === GRAPH FRAME ===
        graph_frame = ttk.LabelFrame(right_frame, text="📡 Real-Time EMG Signal (512 Hz)", padding=5)
        graph_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.fig = Figure(figsize=(10,6), dpi=100, facecolor='white')
        self.fig.patch.set_facecolor('#f0f0f0')
        
        self.ax_ch0 = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_ch0.plot([], [], linewidth=1.2, label='Ch0 (Flexor)', color='#0066cc')
        self.ax_ch0.set_ylabel('ADC Value')
        self.ax_ch0.set_ylim(0, 16384)
        self.ax_ch0.grid(True, alpha=0.3)
        self.ax_ch0.legend(loc='upper left', fontsize=9)
        
        self.ax_ch1 = self.fig.add_subplot(212)
        self.line_ch1, = self.ax_ch1.plot([], [], linewidth=1.2, label='Ch1 (Extensor)', color='#ff6600')
        self.ax_ch1.set_ylabel('ADC Value')
        self.ax_ch1.set_xlabel('Samples')
        self.ax_ch1.set_ylim(0, 16384)
        self.ax_ch1.grid(True, alpha=0.3)
        self.ax_ch1.legend(loc='upper left', fontsize=9)
        
        self.fig.tight_layout()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def update_port_list(self):
        """Update available COM ports"""
        ports = [f"{port} - {desc}" for port, desc, hwid in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)
    
    def connect_arduino(self):
        """Connect to Arduino"""
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return
        
        port_name = self.port_var.get().split(" ")[0]
        
        if self.acq.connect(port_name):
            messagebox.showinfo("Success", f"Connected to {port_name}")
        else:
            messagebox.showerror("Error", "Connection failed")
    
    def disconnect_arduino(self):
        """Disconnect from Arduino"""
        self.acq.disconnect()
    
    def start_acq(self):
        """Start acquisition"""
        self.acq.start_acquisition()
        self.is_recording = True
        self.recorded_data = []
    
    def stop_acq(self):
        """Stop acquisition"""
        self.acq.stop_acquisition()
        self.is_recording = False
    
    def toggle_recording(self):
        """Toggle recording"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.pause_rec_btn.config(text="⏸️ Pause Recording")
            self.recorded_data = []
        else:
            self.pause_rec_btn.config(text="▶️ Resume Recording")
    
    def save_session(self):
        """Save recorded session"""
        if not self.recorded_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        folder = self.save_path
        folder.mkdir(parents=True, exist_ok=True)
        
        filename = f"EMG_session_{timestamp}.json"
        filepath = folder / filename
        
        metadata = {
            "session_info": {
                "timestamp": datetime.now().isoformat(),
                "total_packets": len(self.recorded_data),
                "sampling_rate_hz": 512.0,
                "channels": 2,
            },
            "data": self.recorded_data
        }
        
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        messagebox.showinfo("Saved", f"Saved {len(self.recorded_data)} packets\\nFile: {filepath}")
    
    def main_update_loop(self):
        """Main UI update loop"""
        try:
            # Process any queued packets
            while True:
                packet = self.acq.get_next_packet()
                if packet is None:
                    break
            
            current_time = time.time()
            if current_time - self.last_update_time >= self.update_interval or self.pending_updates > 100:
                self.update_status_labels()
                self.update_graph_display()
                self.last_update_time = current_time
                self.pending_updates = 0
        
        except Exception as e:
            print(f"Update loop error: {e}")
        
        if self.root.winfo_exists():
            self.root.after(30, self.main_update_loop)
    
    def update_status_labels(self):
        """Update status labels"""
        stats = self.acq.get_statistics()
        self.packet_label.config(text=str(stats['packet_count']))
        
        if stats['elapsed_seconds'] > 0:
            hours = int(stats['elapsed_seconds']) // 3600
            minutes = (int(stats['elapsed_seconds']) % 3600) // 60
            seconds = int(stats['elapsed_seconds']) % 60
            self.duration_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def update_graph_display(self):
        """Update graph display"""
        if self.graph_index == 0:
            return
        
        try:
            x = list(self.graph_time_buffer)
            ch0 = list(self.graph_buffer_ch0)
            ch1 = list(self.graph_buffer_ch1)
            
            if len(x) > 1:
                self.line_ch0.set_data(x, ch0)
                self.ax_ch0.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                
                self.line_ch1.set_data(x, ch1)
                self.ax_ch1.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                
                self.canvas.draw_idle()
        except Exception as e:
            print(f"Graph error: {e}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = EMGAcquisitionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
