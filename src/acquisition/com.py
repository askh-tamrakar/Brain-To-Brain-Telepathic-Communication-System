"""
NUCLEAR COM PORT UNLOCK SCRIPT
Forcefully releases COM7 from all locks and resets it

Run as Administrator: python unlock_com7.py
"""

import subprocess
import sys
import time
import os
import ctypes

def is_admin():
    """Check if running as administrator"""
    try:
        return ctypes.windll.shell.IsUserAnAdmin()
    except:
        return False

def run_command(cmd, description=""):
    """Execute a command and print result"""
    print(f"\n⚡ {description}")
    print(f"   Command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"   ✅ Success")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()[:100]}")
        else:
            if result.stderr.strip():
                print(f"   ⚠️  {result.stderr.strip()[:100]}")
    except subprocess.TimeoutExpired:
        print(f"   ⚠️  Command timed out")
    except Exception as e:
        print(f"   ❌ {e}")

def unlock_com_port():
    """Nuclear unlock procedure for COM7"""
    
    print("\n" + "="*70)
    print("🔓 NUCLEAR COM PORT UNLOCK FOR COM7")
    print("="*70)
    
    # Check admin
    if not is_admin():
        print("\n❌ ERROR: This script MUST run as Administrator!")
        print("\nHow to fix:")
        print("  1. Press Windows + X")
        print("  2. Select 'Windows PowerShell (Admin)' or 'Command Prompt (Admin)'")
        print("  3. Navigate to your project folder")
        print("  4. Run: python unlock_com7.py")
        print("\nOR right-click this script and select 'Run as Administrator'")
        sys.exit(1)
    
    print("✅ Running as Administrator")
    
    # ===== STEP 1: Kill all blocking processes =====
    print("\n" + "-"*70)
    print("STEP 1: Kill Blocking Processes")
    print("-"*70)
    
    processes = [
        ("python.exe", "Python processes"),
        ("arduino.exe", "Arduino IDE"),
        ("chordspy.exe", "Chords"),
        ("java.exe", "Java (Arduino)"),
        ("WerFault.exe", "Error reporting"),
    ]
    
    for proc, desc in processes:
        run_command(f"taskkill /IM {proc} /F", f"Killing {desc}")
        time.sleep(0.5)
    
    time.sleep(2)
    print("\n   ⏸️  Waiting 2 seconds for processes to fully close...")
    time.sleep(2)
    
    # ===== STEP 2: Disable COM7 device =====
    print("\n" + "-"*70)
    print("STEP 2: Disable/Enable COM7 Device")
    print("-"*70)
    
    # Get COM7 device info
    run_command(
        "powershell -Command \"Get-CimInstance Win32_SerialPort | Where-Object {$_.Name -like '*COM7*'}\"",
        "Querying COM7 device info"
    )
    
    # Disable USB Serial Device
    run_command(
        "powershell -Command \"Disable-PnpDevice -InstanceId (Get-PnpDevice -FriendlyName '*COM*' | Select -First 1).InstanceId -Confirm:$false\"",
        "Disabling COM7 device"
    )
    
    time.sleep(1)
    
    # Enable USB Serial Device
    run_command(
        "powershell -Command \"Enable-PnpDevice -InstanceId (Get-PnpDevice -FriendlyName '*COM*' | Select -First 1).InstanceId -Confirm:$false\"",
        "Re-enabling COM7 device"
    )
    
    time.sleep(2)
    
    # ===== STEP 3: Reset COM port settings =====
    print("\n" + "-"*70)
    print("STEP 3: Reset COM Port Settings")
    print("-"*70)
    
    run_command("mode COM7: /status", "Check COM7 status")
    run_command("mode COM7: baud=115200 parity=n data=8 stop=1", "Reset COM7 to 115200 baud")
    
    time.sleep(1)
    
    # ===== STEP 4: Clear registry locks (careful!) =====
    print("\n" + "-"*70)
    print("STEP 4: Clear Serial Port Registry Locks")
    print("-"*70)
    
    run_command(
        "reg delete HKCU\\Software\\Classes\\CLSID\\{00000000-0000-0000-0000-000000000000} /f",
        "Clearing registry locks (may fail safely)"
    )
    
    time.sleep(1)
    
    # ===== STEP 5: Unplug/replug instruction =====
    print("\n" + "-"*70)
    print("STEP 5: Physical Device Reset")
    print("-"*70)
    
    input("\n🔌 UNPLUG Arduino USB cable NOW, then press Enter when done...")
    print("   ⏸️  Waiting 5 seconds...")
    time.sleep(5)
    
    input("🔌 PLUG Arduino USB cable back in, then press Enter...")
    time.sleep(3)
    
    print("   ✅ Device reset complete")
    
    # ===== STEP 6: Verify COM7 is accessible =====
    print("\n" + "-"*70)
    print("STEP 6: Verify COM7 Access")
    print("-"*70)
    
    run_command("mode COM7: /status", "Final COM7 status check")
    
    # ===== STEP 7: Test with Python =====
    print("\n" + "-"*70)
    print("STEP 7: Test Python Access to COM7")
    print("-"*70)
    
    test_code = '''
import serial
try:
    ser = serial.Serial('COM7', 115200, timeout=1)
    print('✅ Python can access COM7!')
    ser.close()
except Exception as e:
    print(f'❌ Python error: {e}')
'''
    
    with open('test_com7_access.py', 'w') as f:
        f.write(test_code)
    
    run_command("python test_com7_access.py", "Test Python serial access")
    
    # ===== SUCCESS MESSAGE =====
    print("\n" + "="*70)
    print("✅ UNLOCK COMPLETE!")
    print("="*70)
    print("""
🎉 COM7 should now be accessible!

Next steps:

1. Verify Arduino is connected:
   python test_com7.py

2. Start EEG server:
   python eeg_serial_server.py --port COM7 --baud 115200

3. Check for data:
   You should see: 📡 raw=... filt=...

If still getting permission errors, try one more thing:
   
   taskkill /IM python.exe /F
   taskkill /IM chordspy* /F
   [Unplug Arduino for 10 seconds]
   [Plug back in]
   python eeg_serial_server.py --port COM7 --baud 115200
    """)

if __name__ == "__main__":
    try:
        unlock_com_port()
    except KeyboardInterrupt:
        print("\n\n⛔ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)