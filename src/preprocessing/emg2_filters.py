"""
filters.py

Stateful filters for biosignals (EMG, EEG, EOG).
Provides:
 - design_emg_sos, design_eeg_sos, design_eog_sos
 - design_notch_sos
 - StatefulFilter class (real-time sample/block processing)
 - apply_offline_filter helper (zero-phase for post-processing)

Typical usage (real-time):
  f = StatefulFilter(sos_emg, notch_sos)   # or pass None for second arg
  y = f.process_sample(x)

Typical usage (offline):
  y = apply_offline_filter(sos_emg, notch_sos, x_array, fs)
"""
from typing import Optional, Tuple, List
import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, sosfiltfilt

# ----------------------
# Design helpers
# ----------------------
def design_bandpass_sos(lowcut: float, highcut: float, fs: float, order: int = 4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if low <= 0:
        raise ValueError("lowcut must be > 0")
    if high >= 1:
        raise ValueError("highcut must be < Nyquist")
    sos = butter(order, [low, high], btype='band', output='sos')
    return sos

def design_lowpass_sos(cutoff: float, fs: float, order: int = 4):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    sos = butter(order, normal_cutoff, btype='low', output='sos')
    return sos

def design_highpass_sos(cutoff: float, fs: float, order: int = 4):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    sos = butter(order, normal_cutoff, btype='high', output='sos')
    return sos

def design_notch_sos(freq: float, fs: float, q: float = 30.0):
    """
    Design an IIR notch (bandstop) as second-order section via iirnotch + converting to SOS.
    We return as 2nd-order IIR numerator/denom in SOS-like structure (scipy's iirnotch returns b,a).
    For simplicity we will convert b,a to sos using butter if needed; here we return (b,a) as tuple and
    StatefulFilter will wrap using sosfilt with appropriate state.
    """
    b, a = iirnotch(freq / (0.5 * fs), Q=q)
    # convert to sos by forming single SOS. SciPy doesn't provide direct b,a->sos function here in imports,
    # but sosfilt accepts 'b,a' form via lfilter; to keep consistent we'll use the b,a pair directly in filter chain.
    return b, a

# ----------------------
# Presets for sensors
# ----------------------
def design_emg_sos(fs, lowcut=20.0, highcut=450.0, order=4):
    nyq = fs / 2.0
    # clamp highcut if needed
    if highcut >= nyq:
        highcut = 0.9 * nyq  # or nyq - 1

    return design_bandpass_sos(lowcut, highcut, fs, order=order)

def design_eeg_sos(fs: float, lowcut: float = 0.5, highcut: float = 40.0, order: int = 4) -> np.ndarray:
    """
    Typical EEG: 0.5-40 Hz bandpass (delta to low gamma / general purpose).
    """
    return design_bandpass_sos(lowcut, highcut, fs, order=order)

def design_eog_sos(fs: float, lowcut: float = 0.05, highcut: float = 10.0, order: int = 3) -> np.ndarray:
    """
    Typical EOG is very low-frequency (< 10 Hz). Use bandpass 0.05-10 Hz or lowpass ~5-10 Hz.
    """
    return design_bandpass_sos(lowcut, highcut, fs, order=order)

# ----------------------
# StatefulFilter class
# ----------------------
class StatefulFilter:
    """
    Stateful filter that can chain a SOS filter and optionally a notch (b,a).
    Use process_sample() for one sample at a time, or process_block() for a list/array.

    Internals:
      - uses sosfilt with internal zi for streaming
      - if notch (b,a) is provided, applied after SOS using lfilter-style (we implement streaming with direct form)
    """
    def __init__(self, sos: Optional[np.ndarray] = None, notch_ba: Optional[Tuple[np.ndarray, np.ndarray]] = None):
        self.sos = sos
        self.notch_ba = notch_ba
        self._init_state()

    def _init_state(self):
        # SOS state
        if self.sos is not None:
            # sosfilt_zi gives zi shape (n_sections, 2)
            try:
                self.zi = sosfilt_zi(self.sos)
                # scale by 0 initially (no prior input)
                self.zi = np.zeros_like(self.zi)
            except Exception:
                # fallback: create zeros sized to sos
                self.zi = np.zeros((self.sos.shape[0], 2))
        else:
            self.zi = None

        # notch state (b,a) -> we'll maintain last len(a)-1 inputs & outputs
        if self.notch_ba is not None:
            b, a = self.notch_ba
            self._b = np.array(b, dtype=float)
            self._a = np.array(a, dtype=float)
            self._x_hist = np.zeros(max(len(self._b), len(self._a)))
            self._y_hist = np.zeros(max(len(self._b), len(self._a)))
        else:
            self._b = None
            self._a = None

    def reset(self):
        self._init_state()

    def process_block(self, x: np.ndarray) -> np.ndarray:
        """
        Process a block (numpy array) of samples. Returns filtered array.
        Uses streaming sosfilt with stored zi to maintain continuity.
        """
        y = x.astype(float)
        if self.sos is not None:
            y, self.zi = sosfilt(self.sos, y, zi=self.zi)
        if self.notch_ba is not None:
            # Apply IIR (b,a) in streaming sample-wise fashion for stability of state
            y_out = np.zeros_like(y)
            for i, xi in enumerate(y):
                y_out[i] = self._process_notch_sample(xi)
            return y_out
        return y

    def process_sample(self, x: float) -> float:
        """
        Process single sample and return filtered value.
        For SOS stage we call sosfilt with single-sample array and update zi.
        """
        v = np.asarray([float(x)])
        if self.sos is not None:
            v, self.zi = sosfilt(self.sos, v, zi=self.zi)
            v = v[0]
        if self.notch_ba is not None:
            v = self._process_notch_sample(v)
        return float(v)

    def _process_notch_sample(self, x: float) -> float:
        """
        Direct form IIR single-sample processing for notch (b,a).
        Maintains small history buffers.
        """
        # shift history
        self._x_hist = np.roll(self._x_hist, 1)
        self._x_hist[0] = x
        # compute numerator
        y = 0.0
        for i in range(len(self._b)):
            y += self._b[i] * (self._x_hist[i] if i < len(self._x_hist) else 0.0)
        # subtract feedback (skip a[0] assumed 1)
        for i in range(1, len(self._a)):
            y -= self._a[i] * (self._y_hist[i-1] if i-1 < len(self._y_hist) else 0.0)
        # update output history
        self._y_hist = np.roll(self._y_hist, 1)
        self._y_hist[0] = y
        return float(y)

# ----------------------
# Offline (zero-phase) helper
# ----------------------
def apply_offline_filter(sos: Optional[np.ndarray], notch_ba: Optional[Tuple[np.ndarray, np.ndarray]], x: np.ndarray):
    """
    Apply zero-phase filtering for offline analysis:
     - First apply SOS with filtfilt (sosfiltfilt)
     - Then apply notch with filtfilt using b,a
    Note: filtfilt (sosfiltfilt) is zero-phase and removes phase distortion (good for post-processing).
    """
    y = x.astype(float)
    if sos is not None:
        # zero-phase using sosfiltfilt
        y = sosfiltfilt(sos, y)
    if notch_ba is not None:
        b, a = notch_ba
        # use filtfilt via sosfiltfilt if we had sos; for b,a we can use direct filtfilt from scipy.signal
        from scipy.signal import filtfilt
        y = filtfilt(b, a, y)
    return y

# ----------------------
# Example preset builder (convenience)
# ----------------------
def build_filter_for(sensor_type: str, fs: float, notch_freq: Optional[float] = None):
    """
    sensor_type: 'emg', 'eeg', or 'eog'
    notch_freq: 50 or 60 or None
    returns: (StatefulFilter instance, description string)
    """
    sensor = sensor_type.lower()
    if sensor == 'emg':
        sos = design_emg_sos(fs)
    elif sensor == 'eeg':
        sos = design_eeg_sos(fs)
    elif sensor == 'eog':
        sos = design_eog_sos(fs)
    else:
        raise ValueError("sensor_type must be 'emg','eeg' or 'eog'")
    notch = None
    if notch_freq is not None:
        b,a = design_notch_sos(notch_freq, fs)
        notch = (b,a)
    filt = StatefulFilter(sos=sos, notch_ba=notch)
    return filt, f"{sensor.upper()} filter: sos={'present' if sos is not None else 'none'}, notch={'yes' if notch else 'no'}"

# ----------------------
# Quick test (run as script)
# ----------------------
if __name__ == "__main__":
    # small sanity test
    fs = 512.0
    import matplotlib.pyplot as plt

    t = np.linspace(0, 1, int(fs), endpoint=False)
    # synthetic EMG-like: 100 Hz sine + 10 Hz noise + 50 Hz mains
    sig = 0.8*np.sin(2*np.pi*100*t) + 0.2*np.sin(2*np.pi*10*t) + 0.2*np.sin(2*np.pi*50*t)
    emg_sos = design_emg_sos(fs)
    notch_ba = design_notch_sos(50.0, fs, q=30.0)
    y_off = apply_offline_filter(emg_sos, notch_ba, sig)

    plt.figure()
    plt.plot(t, sig, label='raw')
    plt.plot(t, y_off, label='filtered (offline)')
    plt.legend()
    plt.title("Sanity test")
    plt.show()
