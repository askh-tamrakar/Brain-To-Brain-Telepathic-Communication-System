"""
EEG Acquisition App
Merged/extended from user's eeg_unified.py + common UI upgrades
Features:
 - Scrollable left control panel (mouse wheel + scrollbar)
 - Connection / Acquisition / Recording controls
 - Auto-start recording when acquisition starts
 - Pause / Resume recording button
 - Latest packet detail panel
 - FFT / real-time plotting
 - Save path format: data/raw/session/eeg/EEG_session_dd-mm-YYYY_HH-MM-SS.json
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
    def __init__(self, root):
        self.root = root
        self.root.title("EEG Signal Acquisition - SSVEP v5.0")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')

        # Packet / device config
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

        # Data
        self.packet_count = 0
        self.bytes_received = 0
        self.session_start_time = None
        self.session_data = []
        self.recorded_data = []

        # Buffers
        self.graph_buffer_ch0 = deque(maxlen=512)
        self.graph_buffer_ch1 = deque(maxlen=512)
        self.graph_time_buffer = deque(maxlen=512)
        self.graph_index = 0

        # Queue for thread-safe packet processing
        self.data_queue = queue.Queue()

        # Default save path (folder per sensor)
        self.save_path = Path("data/raw/session/eeg")

        # Last packet detail
        self.latest_packet = {}

        # Build UI
        self.setup_ui()
        self.update_port_list()
        self.root.after(30, self.update_graph_display)
        self.root.after(10, self.process_queue)

    # ---------- UI helpers ----------
    def make_scrollable_left_panel(self, parent):
        """Return a frame placed in parent that is scrollable vertically with mouse and scrollbar."""
        container = ttk.Frame(parent)
        container.pack(side="left", fill="y", expand=False, padx=5, pady=5)

        canvas = tk.Canvas(container, width=320, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse-wheel binding (Windows / Mac / Linux)
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
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # LEFT: scrollable (uses EEG layout style - roomy)
        left_frame_container = ttk.Frame(main_frame)
        left_frame_container.pack(side="left", fill="y", expand=False)
        left_frame = self.make_scrollable_left_panel(left_frame_container)

        # RIGHT: graph area
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)

        # -- Connection --
        connection_frame = ttk.LabelFrame(left_frame, text="🔌 Connection", padding=10)
        connection_frame.pack(fill="x", pady=5, padx=5)
        ttk.Label(connection_frame, text="COM Port:").pack(anchor="w", padx=5, pady=2)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, width=30, state="readonly")
        self.port_combo.pack(fill="x", padx=5, pady=2)
        ttk.Button(connection_frame, text="🔄 Refresh Ports", command=self.update_port_list).pack(fill="x", padx=5, pady=2)
        ttk.Label(connection_frame, text=f"Baud: {self.BAUD_RATE} | {int(self.SAMPLING_RATE)} Hz").pack(anchor="w", padx=5)

        # -- Status --
        status_frame = ttk.LabelFrame(left_frame, text="📊 Status", padding=10)
        status_frame.pack(fill="x", pady=5, padx=5)
        ttk.Label(status_frame, text="Connection:").pack(anchor="w", padx=5)
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red", font=("Arial", 10, "bold"))
        self.status_label.pack(anchor="w", padx=5, pady=2)

        ttk.Label(status_frame, text="Acquisition:").pack(anchor="w", padx=5)
        self.acq_label = ttk.Label(status_frame, text="Idle", foreground="gray", font=("Arial", 10, "bold"))
        self.acq_label.pack(anchor="w", padx=5, pady=2)

        ttk.Label(status_frame, text="Packets:").pack(anchor="w", padx=5)
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.packet_label.pack(anchor="w", padx=5, pady=2)

        ttk.Label(status_frame, text="Duration:").pack(anchor="w", padx=5)
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial", 10, "bold"))
        self.duration_label.pack(anchor="w", padx=5, pady=2)

        ttk.Label(status_frame, text="Rate (Hz):").pack(anchor="w", padx=5)
        self.rate_label = ttk.Label(status_frame, text="0 Hz", font=("Arial", 10, "bold"))
        self.rate_label.pack(anchor="w", padx=5, pady=2)

        ttk.Label(status_frame, text="Speed (KBps):").pack(anchor="w", padx=5)
        self.speed_label = ttk.Label(status_frame, text="0 KBps", font=("Arial", 10, "bold"))
        self.speed_label.pack(anchor="w", padx=5, pady=2)

        # -- Controls --
        control_frame = ttk.LabelFrame(left_frame, text="⚙️ Control", padding=10)
        control_frame.pack(fill="x", pady=5, padx=5)
        self.connect_btn = ttk.Button(control_frame, text="🔌 Connect", command=self.connect_device)
        self.connect_btn.pack(fill="x", padx=2, pady=2)
        self.disconnect_btn = ttk.Button(control_frame, text="❌ Disconnect", command=self.disconnect_device, state="disabled")
        self.disconnect_btn.pack(fill="x", padx=2, pady=2)
        self.start_btn = ttk.Button(control_frame, text="▶️ Start Acquisition", command=self.start_acquisition, state="disabled")
        self.start_btn.pack(fill="x", padx=2, pady=2)
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop Acquisition", command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(fill="x", padx=2, pady=2)

        # -- Recording (auto-start when acquisition starts) --
        rec_frame = ttk.LabelFrame(left_frame, text="📝 Recording", padding=10)
        rec_frame.pack(fill="x", pady=5, padx=5)
        self.pause_rec_btn = ttk.Button(rec_frame, text="⏸️ Pause Recording", command=self.toggle_recording, state="disabled")
        self.pause_rec_btn.pack(fill="x", padx=2, pady=2)
        ttk.Label(rec_frame, text="Recording will start automatically when acquisition starts.").pack(anchor="w", padx=5, pady=4)

        # -- Save / Export --
        save_frame = ttk.LabelFrame(left_frame, text="💾 Save / Export", padding=10)
        save_frame.pack(fill="x", pady=5, padx=5)
        ttk.Button(save_frame, text="📁 Choose Path", command=self.choose_save_path).pack(fill="x", padx=2, pady=2)
        self.path_label = ttk.Label(save_frame, text=str(self.save_path), wraplength=280, justify="left")
        self.path_label.pack(fill="x", padx=2, pady=4)
        self.save_btn = ttk.Button(save_frame, text="💾 Save Session JSON", command=self.save_session_data, state="disabled")
        self.save_btn.pack(fill="x", padx=2, pady=2)
        self.export_btn = ttk.Button(save_frame, text="📊 Export Graph PNG", command=self.export_graph, state="disabled")
        self.export_btn.pack(fill="x", padx=2, pady=2)

        # -- Stats --
        stats_frame = ttk.LabelFrame(left_frame, text="📈 Stats", padding=10)
        stats_frame.pack(fill="both", expand=True, pady=5, padx=5)
        ttk.Label(stats_frame, text="Channel 0 (O1):").pack(anchor="w", padx=5)
        self.ch0_min_label = ttk.Label(stats_frame, text="Min: 0")
        self.ch0_min_label.pack(anchor="w", padx=10)
        self.ch0_max_label = ttk.Label(stats_frame, text="Max: 0")
        self.ch0_max_label.pack(anchor="w", padx=10)
        self.ch0_mean_label = ttk.Label(stats_frame, text="Mean: 0")
        self.ch0_mean_label.pack(anchor="w", padx=10, pady=4)

        ttk.Label(stats_frame, text="Channel 1 (O2):").pack(anchor="w", padx=5)
        self.ch1_min_label = ttk.Label(stats_frame, text="Min: 0")
        self.ch1_min_label.pack(anchor="w", padx=10)
        self.ch1_max_label = ttk.Label(stats_frame, text="Max: 0")
        self.ch1_max_label.pack(anchor="w", padx=10)
        self.ch1_mean_label = ttk.Label(stats_frame, text="Mean: 0")
        self.ch1_mean_label.pack(anchor="w", padx=10, pady=4)

        # -- Latest packet detail --
        latest_frame = ttk.LabelFrame(left_frame, text="🧾 Latest packet detail", padding=8)
        latest_frame.pack(fill="x", pady=5, padx=5)
        self.latest_text = tk.Text(latest_frame, height=6, width=40, wrap="word")
        self.latest_text.insert("1.0", "No packet yet.")
        self.latest_text.configure(state="disabled")
        self.latest_text.pack(fill="both", expand=True)

        # -- Graph panel (right) --
        graph_frame = ttk.LabelFrame(right_frame, text="📡 Real-Time EEG Signal (512 Hz)", padding=5)
        graph_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.fig = Figure(figsize=(10, 6), dpi=100, facecolor='white')
        self.fig.patch.set_facecolor('#f0f0f0')

        self.ax_signal = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_signal.plot([], [], linewidth=1.2, label='CH0 (O1)')
        self.line_ch1, = self.ax_signal.plot([], [], linewidth=1.2, label='CH1 (O2)')
        self.ax_signal.set_ylabel('Voltage (µV)')
        self.ax_signal.set_ylim(-2000, 2000)
        self.ax_signal.grid(True, alpha=0.3)
        self.ax_signal.legend(loc='upper right', fontsize=9)
        self.ax_signal.set_title('Real-Time EEG Signal')

        self.ax_fft = self.fig.add_subplot(212)
        self.line_fft, = self.ax_fft.plot([], [], linewidth=1.2)
        self.ax_fft.set_xlabel('Frequency (Hz)')
        self.ax_fft.set_ylabel('Magnitude')
        self.ax_fft.grid(True, alpha=0.3)
        self.ax_fft.set_title('Frequency Spectrum (FFT)')

        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------- Serial / data ----------
    def update_port_list(self):
        ports = []
        for port, desc, hwid in serial.tools.list_ports.comports():
            ports.append(f"{port} - {desc}")
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)

    def connect_device(self):
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
            # start read thread (keeps reading even if not acquiring; queued)
            self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.read_thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")

    def disconnect_device(self):
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
        self.save_btn.config(state="disabled")
        self.export_btn.config(state="disabled")
        self.pause_rec_btn.config(state="disabled")

    def read_serial_data(self):
        buffer = bytearray()
        while True:
            if not self.is_connected:
                time.sleep(0.1)
                continue
            try:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    if chunk:
                        self.bytes_received += len(chunk)
                        buffer.extend(chunk)
                    while len(buffer) >= self.PACKET_LEN:
                        if buffer[0] == self.SYNC_BYTE_1 and buffer[1] == self.SYNC_BYTE_2:
                            if buffer[self.PACKET_LEN - 1] == self.END_BYTE:
                                pkt = bytes(buffer[:self.PACKET_LEN])
                                self.data_queue.put(pkt)
                                del buffer[:self.PACKET_LEN]
                            else:
                                del buffer[0]
                        else:
                            del buffer[0]
                else:
                    time.sleep(0.001)
            except Exception as e:
                print("Read error:", e)
                time.sleep(0.1)

    def process_queue(self):
        try:
            while True:
                pkt = self.data_queue.get_nowait()
                self.process_packet(pkt)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(10, self.process_queue)

    def process_packet(self, packet):
        try:
            self.packet_count += 1
            counter = packet[2]
            ch0 = (packet[4] << 8) | packet[3]
            ch1 = (packet[6] << 8) | packet[5]
            # Convert to µV (same as your original conversion)
            ch0_uv = ((ch0 / 16384) * 3300) - 1650
            ch1_uv = ((ch1 / 16384) * 3300) - 1650

            self.graph_buffer_ch0.append(ch0_uv)
            self.graph_buffer_ch1.append(ch1_uv)
            self.graph_time_buffer.append(self.graph_index)
            self.graph_index += 1

            data_entry = {
                "timestamp": datetime.now().isoformat(),
                "counter": int(counter),
                "ch0_uv": float(ch0_uv),
                "ch1_uv": float(ch1_uv),
                "ch0_raw": int(ch0),
                "ch1_raw": int(ch1)
            }
            self.session_data.append(data_entry)
            if self.is_recording:
                self.recorded_data.append(data_entry)

            # update latest packet detail view
            self.latest_packet = data_entry
            self.root.after(0, self.update_latest_packet_display)

            if self.packet_count % 50 == 0:
                self.root.after(0, self.update_status_labels)
        except Exception as e:
            print("Process error:", e)

    # ---------- UI / control actions ----------
    def update_latest_packet_display(self):
        self.latest_text.configure(state="normal")
        self.latest_text.delete("1.0", "end")
        pretty = json.dumps(self.latest_packet, indent=2)
        self.latest_text.insert("1.0", pretty)
        self.latest_text.configure(state="disabled")

    def update_status_labels(self):
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

            if len(self.graph_buffer_ch0):
                ch0 = list(self.graph_buffer_ch0)
                self.ch0_min_label.config(text=f"Min: {min(ch0):.0f}")
                self.ch0_max_label.config(text=f"Max: {max(ch0):.0f}")
                self.ch0_mean_label.config(text=f"Mean: {np.mean(ch0):.0f}")
            if len(self.graph_buffer_ch1):
                ch1 = list(self.graph_buffer_ch1)
                self.ch1_min_label.config(text=f"Min: {min(ch1):.0f}")
                self.ch1_max_label.config(text=f"Max: {max(ch1):.0f}")
                self.ch1_mean_label.config(text=f"Mean: {np.mean(ch1):.0f}")

    def start_acquisition(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Not connected")
            return
        try:
            # send start command to device (if it supports)
            try:
                self.ser.write(b"START\n")
            except:
                pass

            self.is_acquiring = True
            self.is_recording = True   # start recording automatically
            self.recorded_data = []
            self.session_start_time = datetime.now()
            self.packet_count = 0
            self.bytes_received = 0
            self.session_data = []
            self.acq_label.config(text="Acquiring", foreground="orange")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.pause_rec_btn.config(state="normal", text="⏸️ Pause Recording")
            self.save_btn.config(state="normal")
            self.export_btn.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error", f"Start failed: {e}")

    def stop_acquisition(self):
        try:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(b"STOP\n")
                except:
                    pass
        except:
            pass
        self.is_acquiring = False
        self.is_recording = False
        self.acq_label.config(text="Idle", foreground="gray")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.pause_rec_btn.config(state="disabled")
        self.pause_rec_btn.config(text="⏸️ Pause Recording")
        self.save_btn.config(state="normal")
        self.export_btn.config(state="normal")

    def toggle_recording(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.pause_rec_btn.config(text="⏸️ Pause Recording")
        else:
            self.pause_rec_btn.config(text="▶️ Resume Recording")

    # ---------- Graph / plotting ----------
    def update_graph_display(self):
        if len(self.graph_time_buffer) == 0:
            if self.root.winfo_exists():
                self.root.after(30, self.update_graph_display)
            return
        try:
            x = list(self.graph_time_buffer)
            ch0 = list(self.graph_buffer_ch0)
            ch1 = list(self.graph_buffer_ch1)
            if len(x) > 1:
                self.line_ch0.set_data(x, ch0)
                self.line_ch1.set_data(x, ch1)
                self.ax_signal.set_xlim(max(0, self.graph_index - 512), max(512, self.graph_index))
                # FFT on ch0
                if len(ch0) >= 256:
                    sig = ch0[-256:]
                    fft = np.fft.fft(sig)
                    freq = np.fft.fftfreq(256, 1/self.SAMPLING_RATE)
                    mag = np.abs(fft)[:128]
                    self.line_fft.set_data(freq[:128], mag)
                    self.ax_fft.set_xlim(0, 100)
                    maxmag = np.max(mag) if np.max(mag) > 0 else 1
                    self.ax_fft.set_ylim(0, maxmag * 1.2)
                self.canvas.draw_idle()
        except Exception as e:
            print("Graph error:", e)
        if self.root.winfo_exists():
            self.root.after(30, self.update_graph_display)

    # ---------- Save / export ----------
    def choose_save_path(self):
        path = filedialog.askdirectory(title="Select save directory", initialdir=str(self.save_path.parent))
        if path:
            self.save_path = Path(path)
            self.path_label.config(text=str(self.save_path))

    def save_session_data(self):
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            folder = Path(self.save_path)
            folder.mkdir(parents=True, exist_ok=True)
            filename = f"EEG_session_{timestamp}.json"
            filepath = folder / filename
            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat() if self.session_start_time else datetime.now().isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0,
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
            messagebox.showinfo("Saved", f"Saved {len(self.session_data)} packets\nFile: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")

    def export_graph(self):
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
