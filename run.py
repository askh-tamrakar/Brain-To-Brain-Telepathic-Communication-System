"""
RUN_EMG.py - Main EMG Pipeline Orchestrator
Integrates acquisition, filtering, and WebSocket communication
Replaces the need to save JSON files; streams directly to filter and frontend
"""

import asyncio
import json
import time
import threading
import numpy as np
from datetime import datetime
from pathlib import Path
from collections import deque
import queue

from src.acquisition.emg_acquisition_modular import EMGAcquisitionModule
from src.preprocessing.emg2_filters import StatefulFilter, design_emg_sos, design_notch_sos

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("Warning: websockets not installed. Install with: pip install websockets")


class EMGPipeline:
    """
    Main orchestrator for EMG data pipeline:
    Acquisition → Filtering → WebSocket → Frontend
    
    No JSON files are saved to disk; data streams in real-time.
    """
    
    def __init__(
        self,
        sampling_rate: float = 512.0,
        num_channels: int = 2,
        ws_port: int = 8765,
        buffer_size: int = 1024,
        chunk_size: int = 64
    ):
        """
        Initialize EMG pipeline
        
        Args:
            sampling_rate: ADC sampling rate in Hz
            num_channels: Number of EMG channels
            ws_port: WebSocket server port
            buffer_size: Size of rolling buffer for each channel
            chunk_size: Samples to process before sending via WebSocket
        """
        self.sampling_rate = sampling_rate
        self.num_channels = num_channels
        self.ws_port = ws_port
        self.buffer_size = buffer_size
        self.chunk_size = chunk_size
        
        # === ACQUISITION ===
        self.acquisition = None  # Will be set if using Tkinter UI
        self.raw_data_queue = queue.Queue()  # Thread-safe queue from acquisition
        
        # === FILTERING ===
        self.emg_filter = StatefulFilter(
            sos=design_emg_sos(sampling_rate),
            notch_ba=design_notch_sos(50.0, sampling_rate)  # 50 Hz notch
        )
        self.filtered_data_queue = queue.Queue()
        
        # === DATA BUFFERS ===
        self.raw_buffers = [deque(maxlen=buffer_size) for _ in range(num_channels)]
        self.filtered_buffers = [deque(maxlen=buffer_size) for _ in range(num_channels)]
        self.time_buffer = deque(maxlen=buffer_size)
        
        # === RECORDING ===
        self.is_recording = False
        self.is_running = False
        self.recorded_data = []
        self.save_path = Path("data/raw/session/emg")
        
        # === WEBSOCKET ===
        self.websocket_server = None
        self.connected_clients = set()
        self.ws_enabled = HAS_WEBSOCKETS
        
        # === PROCESSING THREAD ===
        self.processing_thread = None
        
        # === STATISTICS ===
        self.sample_count = 0
        self.packets_processed = 0
        self.session_start_time = None
        
    def add_raw_data(self, channel_data: dict):
        """
        Add raw data from acquisition module
        
        Args:
            channel_data: Dict with keys like 'ch0_raw_adc', 'ch1_raw_adc', 'timestamp'
        """
        self.raw_data_queue.put(channel_data)
    
    def start(self, use_websocket: bool = True):
        """
        Start the complete pipeline
        
        Args:
            use_websocket: Enable WebSocket server for streaming to frontend
        """
        print("\n" + "="*70)
        print("Starting EMG Pipeline")
        print("="*70)
        
        self.is_running = True
        self.session_start_time = datetime.now()
        self.sample_count = 0
        
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        print(f"✓ Processing thread started - {self.num_channels} channels @ {self.sampling_rate}Hz")
        
        # Start WebSocket server (if enabled)
        if use_websocket and self.ws_enabled:
            self._start_websocket_server()
        
    def stop(self):
        """Stop the pipeline and clean shutdown"""
        print("\nStopping EMG Pipeline...")
        self.is_running = False
        
        if self.processing_thread:
            self.processing_thread.join(timeout=2)
        
        if self.websocket_server:
            asyncio.run_coroutine_threadsafe(
                self._shutdown_websocket(),
                self.websocket_server._loop
            )
        
        print("="*70)
        print(f"Total samples processed: {self.sample_count}")
        print(f"Total packets: {self.packets_processed}")
        print("="*70 + "\n")
    
    def _processing_loop(self):
        """
        Main processing loop running in background thread
        Acquires → Filters → Buffers → Broadcasts to WebSocket
        """
        chunk_buffer = [[] for _ in range(self.num_channels)]
        
        while self.is_running:
            try:
                # Get raw data from acquisition queue
                raw_data = self.raw_data_queue.get(timeout=0.1)
                
                # Extract channel values
                ch0_raw = raw_data.get('ch0_raw_adc', 0)
                ch1_raw = raw_data.get('ch1_raw_adc', 0) if self.num_channels > 1 else 0
                timestamp = raw_data.get('timestamp', datetime.now())
                
                # === FILTERING ===
                ch0_filtered = self.emg_filter.process_sample(ch0_raw)
                
                if self.num_channels > 1:
                    ch1_filtered = self.emg_filter.process_sample(ch1_raw)
                else:
                    ch1_filtered = 0
                
                # === BUFFER STORAGE ===
                self.raw_buffers[0].append(ch0_raw)
                self.filtered_buffers[0].append(ch0_filtered)
                
                if self.num_channels > 1:
                    self.raw_buffers[1].append(ch1_raw)
                    self.filtered_buffers[1].append(ch1_filtered)
                
                self.time_buffer.append(self.sample_count / self.sampling_rate)
                
                # === CHUNK ACCUMULATION ===
                chunk_buffer[0].append(ch0_filtered)
                if self.num_channels > 1:
                    chunk_buffer[1].append(ch1_filtered)
                
                # === RECORDING ===
                if self.is_recording:
                    self.recorded_data.append({
                        'timestamp': timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
                        'ch0_raw': ch0_raw,
                        'ch0_filtered': ch0_filtered,
                        'ch1_raw': ch1_raw if self.num_channels > 1 else None,
                        'ch1_filtered': ch1_filtered if self.num_channels > 1 else None,
                    })
                
                self.sample_count += 1
                
                # === WEBSOCKET BROADCAST (chunk-based) ===
                if len(chunk_buffer[0]) >= self.chunk_size:
                    self._broadcast_websocket(chunk_buffer)
                    chunk_buffer = [[] for _ in range(self.num_channels)]
                    self.packets_processed += 1
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Processing Error] {e}")
                continue
    
    def _broadcast_websocket(self, chunk_data: list):
        """
        Send filtered data to WebSocket clients
        
        Args:
            chunk_data: List of channel buffers containing filtered samples
        """
        if not self.connected_clients or not self.ws_enabled:
            return
        
        try:
            payload = {
                'source': 'EMG',
                'timestamp': time.time() * 1000,  # milliseconds
                'fs': self.sampling_rate,
                'window': chunk_data,  # List of channels
            }
            
            message = json.dumps(payload)
            
            # Broadcast to all connected clients
            for client in list(self.connected_clients):
                asyncio.run_coroutine_threadsafe(
                    client.send(message),
                    self.websocket_server._loop
                )
        except Exception as e:
            print(f"[WebSocket Broadcast Error] {e}")
    
    def _start_websocket_server(self):
        """Start WebSocket server in background thread"""
        if not HAS_WEBSOCKETS:
            print("⚠ WebSocket disabled (websockets module not installed)")
            return
        
        def run_ws_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def handler(websocket, path):
                """Handle WebSocket client connection"""
                self.connected_clients.add(websocket)
                print(f"[WebSocket] Client connected: {websocket.remote_address}")
                
                try:
                    async for message in websocket:
                        # Echo or command handling if needed
                        if message == "ping":
                            await websocket.send("pong")
                except websockets.exceptions.ConnectionClosed:
                    pass
                finally:
                    self.connected_clients.discard(websocket)
                    print(f"[WebSocket] Client disconnected: {websocket.remote_address}")
            
            async def start_server():
                async with websockets.serve(handler, "0.0.0.0", self.ws_port):
                    print(f"✓ WebSocket server listening on ws://0.0.0.0:{self.ws_port}")
                    self.websocket_server = websockets.serve(handler, "0.0.0.0", self.ws_port)
                    await asyncio.Future()  # Run forever
            
            loop.run_until_complete(start_server())
            loop.run_forever()
        
        ws_thread = threading.Thread(target=run_ws_server, daemon=True)
        ws_thread.start()
    
    async def _shutdown_websocket(self):
        """Shutdown WebSocket server"""
        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
    
    def get_current_data(self) -> dict:
        """
        Get current buffered data for analysis or export
        
        Returns:
            Dictionary with raw, filtered, and time data
        """
        return {
            'raw': [list(buf) for buf in self.raw_buffers],
            'filtered': [list(buf) for buf in self.filtered_buffers],
            'timestamps': list(self.time_buffer),
            'sample_count': self.sample_count,
            'packets_processed': self.packets_processed,
        }
    
    def start_recording(self):
        """Start recording data"""
        self.is_recording = True
        self.recorded_data = []
        print("✓ Recording started")
    
    def stop_recording(self) -> str:
        """
        Stop recording and save to file
        
        Returns:
            Path to saved file
        """
        self.is_recording = False
        
        if not self.recorded_data:
            print("⚠ No data to save")
            return None
        
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            folder = self.save_path
            folder.mkdir(parents=True, exist_ok=True)
            
            filename = f"EMG_recording_{timestamp}.json"
            filepath = folder / filename
            
            metadata = {
                "recording_info": {
                    "timestamp": self.session_start_time.isoformat() if self.session_start_time else datetime.now().isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0,
                    "total_samples": len(self.recorded_data),
                    "sampling_rate_hz": self.sampling_rate,
                    "channels": self.num_channels,
                    "device": "Arduino EMG",
                    "sensor_type": "EMG",
                },
                "data": self.recorded_data
            }
            
            with open(filepath, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"✓ Saved {len(self.recorded_data)} samples to {filepath}")
            return str(filepath)
        
        except Exception as e:
            print(f"✗ Save failed: {e}")
            return None
    
    def get_statistics(self) -> dict:
        """Get current pipeline statistics"""
        elapsed = (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0
        
        stats = {
            'sample_count': self.sample_count,
            'packets_processed': self.packets_processed,
            'elapsed_seconds': elapsed,
            'sample_rate': self.sample_count / elapsed if elapsed > 0 else 0,
            'websocket_clients': len(self.connected_clients) if self.ws_enabled else 0,
            'is_recording': self.is_recording,
        }
        
        # Per-channel statistics
        for ch in range(self.num_channels):
            if len(self.filtered_buffers[ch]) > 0:
                data = np.array(list(self.filtered_buffers[ch]))
                stats[f'ch{ch}_min'] = float(np.min(data))
                stats[f'ch{ch}_max'] = float(np.max(data))
                stats[f'ch{ch}_mean'] = float(np.mean(data))
        
        return stats


# ============================================================================
# INTEGRATION WITH TKINTER ACQUISITION UI
# ============================================================================

class EMGAcquisitionBridge:
    """
    Bridge between Tkinter EMG acquisition UI and EMG pipeline
    Extracts packets from acquisition and feeds into pipeline
    """
    
    def __init__(self, tkinter_app, pipeline: EMGPipeline):
        """
        Args:
            tkinter_app: EMGAcquisitionApp instance
            pipeline: EMGPipeline instance
        """
        self.app = tkinter_app
        self.pipeline = pipeline
        self.original_parse_method = tkinter_app.parse_and_store_packet
        
        # Override parse method
        tkinter_app.parse_and_store_packet = self.parse_and_forward
    
    def parse_and_forward(self, packet):
        """
        Intercept packet parsing and forward to pipeline
        """
        try:
            counter = packet[2]
            ch0_raw = (packet[4] << 8) | packet[3]
            ch1_raw = (packet[6] << 8) | packet[5]
            timestamp = datetime.now()
            
            # Feed into pipeline
            self.pipeline.add_raw_data({
                'ch0_raw_adc': ch0_raw,
                'ch1_raw_adc': ch1_raw,
                'timestamp': timestamp,
                'sequence_counter': int(counter),
            })
            
            # Still update Tkinter UI
            self.app.graph_buffer_ch0.append(ch0_raw)
            self.app.graph_buffer_ch1.append(ch1_raw)
            self.app.graph_time_buffer.append(self.app.graph_index)
            self.app.graph_index += 1
            
            self.app.packet_count += 1
            self.app.latest_packet = {
                'timestamp': timestamp.isoformat(),
                'ch0_raw_adc': ch0_raw,
                'ch1_raw_adc': ch1_raw,
                'sequence_counter': int(counter),
            }
            self.app.pending_updates += 1
        
        except Exception as e:
            print(f"Bridge parse error: {e}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point"""
    
    # Create pipeline
    pipeline = EMGPipeline(
        sampling_rate=512.0,
        num_channels=2,
        ws_port=8765,
        buffer_size=2048,
        chunk_size=64
    )
    
    # Start pipeline
    pipeline.start(use_websocket=True)
    
    # Create Tkinter acquisition UI
    import tkinter as tk
    from src.acquisition.emg_acquisition import EMGAcquisitionApp
    
    root = tk.Tk()
    app = EMGAcquisitionApp(root)
    
    # Bridge acquisition to pipeline
    bridge = EMGAcquisitionBridge(app, pipeline)
    
    # Override recording buttons to use pipeline
    original_start = app.start_acquisition
    original_stop = app.stop_acquisition
    
    def start_with_pipeline():
        original_start()
        pipeline.start_recording()
    
    def stop_with_pipeline():
        pipeline.stop_recording()
        original_stop()
    
    app.start_acquisition = start_with_pipeline
    app.stop_acquisition = stop_with_pipeline
    
    print(f"✓ Tkinter UI connected to pipeline")
    print(f"✓ WebSocket server on ws://localhost:8765")
    print(f"✓ Connect frontend to receive real-time data\n")
    
    try:
        root.mainloop()
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()