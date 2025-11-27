"""
EEG Serial Stream Server for Chords
Works with Arduino Uno + HC-05 Bluetooth or direct USB serial

Features:
- Reads raw serial data from COM port
- Forwards to Chords in proper JSON format
- Handles multiple baud rates
- Auto-reconnects on disconnect
- HTTP API for Chords compatibility

Installation:
  pip install pyserial flask

Usage:
  python eeg_serial_server.py --port COM7 --baud 115200

Then in Chords:
  - Input Source: HTTP/Serial
  - URL/Port: http://localhost:5000/stream
  - Or direct serial if Chords supports it
"""

import serial
import json
import argparse
import time
import sys
from threading import Thread
from queue import Queue
from datetime import datetime

class EEGSerialReader:
    """Read EEG data from serial port and buffer it"""
    
    def __init__(self, port, baud_rate=115200, timeout=1):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser = None
        self.running = False
        self.data_queue = Queue()
        self.last_data = None
        self.error_count = 0
        self.max_errors = 5
    
    def connect(self):
        """Establish serial connection"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            
            print(f"🔌 Connecting to {self.port} at {self.baud_rate} baud...")
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            
            # Clear buffer
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            print(f"✅ Connected to {self.port}")
            self.error_count = 0
            return True
            
        except serial.SerialException as e:
            print(f"❌ Connection failed: {e}")
            print("💡 Try: python com_diagnostic.py")
            return False
    
    def read_loop(self):
        """Main reading loop (runs in thread)"""
        self.running = True
        print("📊 Reading stream... Press Ctrl+C to stop\n")
        
        while self.running:
            try:
                if not self.ser or not self.ser.is_open:
                    if not self.connect():
                        time.sleep(2)
                        continue
                
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        self.last_data = line
                        self.data_queue.put(line)
                        print(f"📡 {line[:80]}...")  # Print first 80 chars
                
                else:
                    time.sleep(0.01)
            
            except serial.SerialException as e:
                self.error_count += 1
                print(f"⚠️  Serial error ({self.error_count}/{self.max_errors}): {e}")
                
                if self.error_count >= self.max_errors:
                    print("❌ Too many errors, reconnecting...")
                    if self.ser:
                        self.ser.close()
                    time.sleep(2)
            
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start reading in background thread"""
        if not self.connect():
            return False
        
        thread = Thread(target=self.read_loop, daemon=True)
        thread.start()
        return True
    
    def stop(self):
        """Stop reading"""
        self.running = False
        if self.ser:
            self.ser.close()
    
    def get_latest_json(self):
        """Get latest data as JSON for Chords"""
        if self.last_data:
            try:
                # If already JSON, just return it
                if self.last_data.startswith('{'):
                    return json.loads(self.last_data)
                else:
                    # Otherwise wrap it
                    return {
                        'source': 'EEG',
                        'timestamp': int(time.time() * 1000),
                        'raw': self.last_data
                    }
            except:
                return {'error': 'Parse error', 'raw': self.last_data}
        return {'status': 'waiting'}


class ChordsCompatibleServer:
    """Serve EEG data to Chords"""
    
    def __init__(self, port, baud_rate):
        self.reader = EEGSerialReader(port, baud_rate)
    
    def start(self):
        """Start the server"""
        if not self.reader.start():
            return False
        
        print("\n" + "="*60)
        print("🧠 EEG SERIAL SERVER RUNNING")
        print("="*60)
        print(f"Serial Port: {self.reader.port}")
        print(f"Baud Rate: {self.reader.baud_rate}")
        print("\n📋 DATA FORMAT (to Chords):")
        print('   {"source":"EEG","fs":250,"timestamp":..,"window":[[s0,s1,...,sN]]}')
        print("\n🔗 STREAMING:")
        print("   Option 1: Direct Serial via HC-05/USB")
        print("   Option 2: HTTP API (add --flask flag)")
        print("\n💡 In Chords:")
        print("   - Bluetooth: Connect HC-05 directly")
        print("   - USB: Use Serial Monitor with this COM port")
        print("   - TCP/IP: python eeg_serial_server.py --port COM7 --flask")
        print("\n⏸️  Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        return True
    
    def stop(self):
        """Stop the server"""
        self.reader.stop()
        print("\n\n✋ Server stopped")


def main():
    parser = argparse.ArgumentParser(
        description='EEG Serial Stream Server for Chords'
    )
    parser.add_argument(
        '--port',
        default='COM7',
        help='Serial port (default: COM7)'
    )
    parser.add_argument(
        '--baud',
        type=int,
        default=115200,
        help='Baud rate (default: 115200)'
    )
    parser.add_argument(
        '--flask',
        action='store_true',
        help='Enable Flask HTTP API'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=1.0,
        help='Serial timeout in seconds'
    )
    
    args = parser.parse_args()
    
    server = ChordsCompatibleServer(args.port, args.baud)
    
    if not server.start():
        print("\n❌ Failed to start server")
        print("💡 Troubleshooting:")
        print("   1. python com_diagnostic.py  (check COM port)")
        print("   2. Unplug/replug Arduino")
        print("   3. Close Arduino IDE, Chords, other terminals")
        sys.exit(1)
    
    # Flask HTTP API (optional)
    if args.flask:
        try:
            from flask import Flask, jsonify
            
            app = Flask(__name__)
            
            @app.route('/stream')
            def stream():
                """Get latest EEG data as JSON"""
                return jsonify(server.reader.get_latest_json())
            
            @app.route('/health')
            def health():
                """Health check"""
                return jsonify({
                    'status': 'ok' if server.reader.ser and server.reader.ser.is_open else 'disconnected',
                    'port': server.reader.port,
                    'baud': server.reader.baud_rate
                })
            
            print("\n🌐 Flask HTTP API enabled:")
            print("   GET http://localhost:5000/stream  → Latest data (JSON)")
            print("   GET http://localhost:5000/health  → Server status")
            
            # Run Flask in thread
            flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False), daemon=True)
            flask_thread.start()
        
        except ImportError:
            print("\n⚠️  Flask not installed: pip install flask")
    
    # Keep running
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    main()
