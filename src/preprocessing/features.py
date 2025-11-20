# filters.py
import mne
import numpy as np
from scipy.signal import butter, sosfiltfilt

def bandpass(data, sf, low=1.0, high=50.0, order=4):
    sos = butter(order, [low, high], btype='band', fs=sf, output='sos')
    return sosfiltfilt(sos, data, axis=-1)

def notch(data, sf, freq=50.0, q=30.0):
    from scipy.signal import iirnotch, filtfilt
    b, a = iirnotch(freq, q, sf)
    return filtfilt(b, a, data, axis=-1)

