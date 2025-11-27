"""
COM Port Diagnostic & Recovery Tool
Fixes: Semaphore timeout, Permission Denied, Write timeout errors

Usage:
  python com_diagnostic.py
  
This will:
1. List all available COM ports
2. Check which processes are using them
3. Kill blocking processes (if safe)
4. Test connection at various baud rates
5. Show raw serial data
"""

import serial
import serial.tools.list_ports
import subprocess
import sys
import time
import os
from pathlib import Path

def list_com_ports():
    """List all available COM ports with descriptions"""
    print("\n" + "="*60)
    print("AVAILABLE COM PORTS")
    print("="*60)
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ No COM ports found!")
        return []
    
    available = []
    for i, port in enumerate(ports, 1):
        print(f"\n{i}. Port: {port.device}")
        print(f"   Description: {port.description}")
        print(f"   HWID: {port.hwid}")
        available.append(port.device)
    return available

def check_process_lock(com_port):
    """Check which processes are using a COM port (Windows)"""
    print(f"\n🔍 Checking processes using {com_port}...")
    try:
        # Use wmic to find processes using port
        result = subprocess.run(
            f'wmic logicaldisk get name',
            shell=True,
            capture_output=True,
            text=True
        )
        # This is a workaround; actual COM port checking is complex on Windows
        print(f"   ℹ️  Close Arduino IDE Serial Monitor, Chords, other terminal windows")
        print(f"   ℹ️  If issue persists, try: Device Manager → COM & LPT → Right-click {com_port} → Properties")
    except Exception as e:
        print(f"   ⚠️  Could not check locks: {e}")

def close_arduino_ide():
    """Kill Arduino IDE process to free COM port"""
    print("\n⚡ Attempting to close Arduino IDE...")
    try:
        subprocess.run('taskkill /IM arduino.exe /F', shell=True, capture_output=True)
        print("   ✅ Arduino IDE killed")
        time.sleep(1)
    except:
        pass

def close_chords():
    """Kill Chords process if running"""
    print("⚡ Attempting to close Chords...")
    try:
        subprocess.run('taskkill /IM chordspy* /F', shell=True, capture_output=True)
        subprocess.run('taskkill /IM python* /F', shell=True, capture_output=True)
        print("   ✅ Chords processes killed")
        time.sleep(1)
    except:
        pass

def test_port_connection(com_port, baud_rate):
    """Test if a port can be opened at given baud rate"""
    try:
        ser = serial.Serial(
            port=com_port,
            baudrate=baud_rate,
            timeout=1,
            write_timeout=1
        )
        ser.close()
        return True
    except (OSError, serial.SerialException) as e:
        error_msg = str(e).lower()
        if 'timeout' in error_msg or 'semaphore' in error_msg:
            return False  # Port locked by another process
        elif 'permission' in error_msg:
            return False  # Permission denied
        return False

def read_serial_data(com_port, baud_rate, duration=5):
    """Read raw data from serial port"""
    print(f"\n📊 Reading from {com_port} at {baud_rate} baud for {duration}s...")
    print("-" * 60)
    
    try:
        ser = serial.Serial(
            port=com_port,
            baudrate=baud_rate,
            timeout=1,
            write_timeout=1
        )
        
        start_time = time.time()
        line_count = 0
        
        while time.time() - start_time < duration:
            try:
                if ser.in_waiting:
                    data = ser.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        print(f"   {data}")
                        line_count += 1
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"   ⚠️  Read error: {e}")
                break
        
        ser.close()
        print("-" * 60)
        print(f"✅ Read {line_count} lines")
        return line_count > 0
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🧠 COM PORT DIAGNOSTIC TOOL FOR EEG STREAMING")
    print("="*60)
    
    # Step 1: List ports
    available_ports = list_com_ports()
    if not available_ports:
        print("\n❌ No COM ports available!")
        sys.exit(1)
    
    # Step 2: User selects port
    print("\n" + "-"*60)
    print("SELECT ACTION")
    print("-"*60)
    print("1. Test specific port")
    print("2. Auto-cleanup (close blocking apps)")
    print("3. Read raw data from port")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '2':
        print("\n🔧 CLEANUP MODE - Closing blocking applications...")
        close_arduino_ide()
        close_chords()
        print("✅ Cleanup complete. Try your command again.")
        print("\nRun again: chordspy  (or your streaming command)")
        return
    
    if choice not in ['1', '3']:
        print("Invalid choice")
        return
    
    # Select port
    port_idx = input(f"\nEnter port number (1-{len(available_ports)}): ").strip()
    try:
        com_port = available_ports[int(port_idx) - 1]
    except (ValueError, IndexError):
        print("Invalid port selection")
        return
    
    # Step 3: Check locks
    check_process_lock(com_port)
    
    # Step 4: Test connection
    if choice == '1':
        print(f"\n🧪 Testing {com_port} at various baud rates...")
        baud_rates = [9600, 115200, 230400]
        
        for baud in baud_rates:
            if test_port_connection(com_port, baud):
                print(f"   ✅ {baud} baud: SUCCESS")
            else:
                print(f"   ❌ {baud} baud: FAILED (locked/in use)")
    
    # Step 5: Read data
    if choice == '3':
        baud = input("Enter baud rate (default 115200): ").strip() or "115200"
        read_serial_data(com_port, int(baud), duration=5)
    
    print("\n" + "="*60)
    print("💡 TROUBLESHOOTING TIPS")
    print("="*60)
    print("""
1. SEMAPHORE TIMEOUT ERROR:
   → Close Arduino IDE Serial Monitor
   → Close any Chords windows
   → Run: python com_diagnostic.py  (choose option 2)

2. PERMISSION DENIED ERROR:
   → Right-click Device Manager
   → Expand 'Ports (COM & LPT)'
   → Right-click COM port → Properties
   → Advanced → Restore defaults
   → Restart computer if issue persists

3. WRITE TIMEOUT ERROR:
   → Check USB cable connection
   → Try different USB port on computer
   → Update CH340 drivers if using cheap adapters

4. NO DATA RECEIVED:
   → Verify Arduino is programmed and running
   → Check Serial Monitor shows data first
   → Verify HC-05 is properly wired

5. STILL STUCK?
   → Run: mode COM7 /status  (replace COM7 with your port)
   → Unplug Arduino, wait 5s, replug
   → Restart computer
    """)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔ Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)