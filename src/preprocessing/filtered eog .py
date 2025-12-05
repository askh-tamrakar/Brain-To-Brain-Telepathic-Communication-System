# import numpy as np
# from scipy.signal import butter, filtfilt, iirnotch
# import serial
# import pyautogui
# import time

# # -------------------------------------------------
# # FILTERS
# # -------------------------------------------------

# def bandpass_filter(data, low=0.1, high=10, fs=250, order=4):
#     nyq = fs * 0.5
#     b, a = butter(order, [low/nyq, high/nyq], btype='band')
#     return filtfilt(b, a, data)

# def notch_filter(data, freq=50, fs=250, q=30):
#     w0 = freq / (fs/2)
#     b, a = iirnotch(w0, q)
#     return filtfilt(b, a, data)

# # -------------------------------------------------
# # BLINK DETECTOR
# # -------------------------------------------------

# def detect_blink(value, threshold=0.8):
#     return value > threshold

# # -------------------------------------------------
# # MAIN DINO CONTROLLER
# # -------------------------------------------------

# def run_eog_dino(port="COM3", fs=250):
#     ser = serial.Serial(port, 115200)
#     buffer = []

#     print("\nEOG Dino Game Controller Running…")
#     print("Blink = JUMP\n")

#     while True:
#         try:
#             # -------- Read a single EOG sample --------
#             line = ser.readline().decode().strip()
#             if line == "":
#                 continue

#             sample = float(line)
#             buffer.append(sample)

#             # Need at least 1 second of data to filter
#             if len(buffer) >= fs:

#                 window = np.array(buffer[-fs:])   # last 1 second

#                 # -------- FILTERING --------
#                 filtered = bandpass_filter(window, fs=fs)
#                 filtered = notch_filter(filtered, fs=fs)

#                 latest = filtered[-1]  # last filtered sample

#                 # -------- BLINK EVENT --------
#                 if detect_blink(latest):
#                     print("Blink → Dino JUMP!")
#                     pyautogui.press("space")
#                     time.sleep(0.25)   # small debounce

#         except KeyboardInterrupt:
#             print("\nStopped.")
#             break

#         except:
#             continue


# # -------------------------------------------------
# # RUN
# # -------------------------------------------------

# if __name__ == "__main__":
#     run_eog_dino("COM3")  # Change COM port for your device


import json
import numpy as np
from scipy.signal import butter, filtfilt, iirnotch
import pyautogui
import time

# -------------------------------------------------
# FILTERS
# -------------------------------------------------

def bandpass_filter(data, low=0.1, high=10, fs=250, order=4):
    nyq = fs * 0.5
    b, a = butter(order, [low/nyq, high/nyq], btype='band')
    return filtfilt(b, a, data)

def notch_filter(data, freq=50, fs=250, q=30):
    w0 = freq / (fs/2)
    b, a = iirnotch(w0, q)
    return filtfilt(b, a, data)

def smooth_signal(data, window=5):
    return np.convolve(data, np.ones(window)/window, mode='same')

# -------------------------------------------------
# DETECT EVENTS
# -------------------------------------------------

def detect_blink(value, threshold=0.8):
    return value > threshold

def detect_left_right(left_val, right_val, threshold=0.25):
    diff = left_val - right_val
    if diff > threshold:
        return "LEFT"
    elif diff < -threshold:
        return "RIGHT"
    return None

# -------------------------------------------------
# MAIN JSON READER + CONTROLLER
# -------------------------------------------------

def run_eog_from_json(json_file, fs=250, thresh=0.8):
    # -------- LOAD JSON FILE --------
    with open(json_file, "r") as f:
        data = json.load(f)

    # Check for dual or single channel
    dual = "left" in data and "right" in data

    if dual:
        left = np.array(data["left"])
        right = np.array(data["right"])
        length = min(len(left), len(right))
        left, right = left[:length], right[:length]
    else:
        raw = np.array(data["eog"])

    print("\nEOG Dino Controller (JSON Mode)")
    print("Blink = Jump | Left Eye = ← | Right Eye = →\n")

    # -------- PROCESS SAMPLE BY SAMPLE --------
    for i in range(fs, len(left) if dual else len(raw)):

        # Extract 1-second window
        if dual:
            L = left[i-fs:i]
            R = right[i-fs:i]
        else:
            signal = raw[i-fs:i]

        # ---- FILTERING ----
        if dual:
            L_bp = bandpass_filter(L, fs=fs)
            R_bp = bandpass_filter(R, fs=fs)

            L_n = notch_filter(L_bp, fs=fs)
            R_n = notch_filter(R_bp, fs=fs)

            L_final = smooth_signal(L_n)
            R_final = smooth_signal(R_n)

            last_L = L_final[-1]
            last_R = R_final[-1]
        else:
            bp = bandpass_filter(signal, fs=fs)
            n = notch_filter(bp, fs=fs)
            smooth = smooth_signal(n)
            last_L = last_R = smooth[-1]

        # -------- EVENTS --------

        # Blink event
        avg = (last_L + last_R) / 2
        if detect_blink(avg, thresh):
            print("Blink → JUMP!")
            pyautogui.press("space")
            time.sleep(0.20)

        # Left / Right eye movement
        if dual:
            move = detect_left_right(last_L, last_R)
            if move == "LEFT":
                print("LEFT → ←")
                pyautogui.press("left")
                time.sleep(0.15)
            elif move == "RIGHT":
                print("RIGHT → →")
                pyautogui.press("right")
                time.sleep(0.15)

        time.sleep(1 / fs)

# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    run_eog_from_json("eog_data.json")   # change file name
