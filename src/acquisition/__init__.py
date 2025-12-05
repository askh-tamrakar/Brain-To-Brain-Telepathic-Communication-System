"""
Acquisition subpackage.

Contains modules for hardware data acquisition (EMG/EEG/EOG/etc.).
"""

from . import emg_acquisition_modular
from . import emg_acquisition
# If emg_acquisition_modular defines a main class, re-export it here:
try:
    from .emg_acquisition_modular import EMGAcquisitionModule  # adjust name if different
    from .emg_acquisition import EMGAcquisitionApp
    __all__ = ["emg_acquisition_modular", "EMGAcquisitionModule", "emg_acquisition ", "EMGAcquisitionApp"]
except ImportError:
    __all__ = ["emg_acquisition_modular", "emg_acquisition"]
