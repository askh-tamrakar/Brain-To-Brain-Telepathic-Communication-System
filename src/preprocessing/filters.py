# features.py
import numpy as np
from scipy.signal import welch

def bandpower_channel(x, sf, band):
    f, Pxx = welch(x, sf, nperseg=min(len(x), sf*2))
    idx = (f >= band[0]) & (f <= band[1])
    if idx.sum() == 0:
        return 0.0
    return np.trapz(Pxx[idx], f[idx])

def extract_features(window, fs):
    # window: shape (channels, samples)
    bands = {"delta": (1,4),"theta":(4,8),"alpha":(8,12),"beta":(12,30),"gamma":(30,45)}
    feats = []
    for ch in range(window.shape[0]):
        chdata = window[ch, :]
        # simple time-domain
        feats.append(np.mean(chdata))
        feats.append(np.std(chdata))
        feats.append(np.sqrt(np.mean(chdata**2)))  # RMS
        # bandpowers
        for b in bands.values():
            feats.append(bandpower_channel(chdata, fs, b))
    return np.array(feats)
