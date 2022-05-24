# The following block uses code from https://github.com/scaperot/the-BPM-detector-python
# licensed under GNU General Public License version 3 as published by the Free Software Foundation
# which you can find here: https://www.gnu.org/licenses/gpl-3.0.en.html

import argparse
import array
import math
import wave

import matplotlib.pyplot as plt
import numpy
import pywt
from scipy import signal

def read_wav(filename):
    # open file, get metadata for audio
    try:
        wf = wave.open(filename, "rb")
    except IOError as e:
        print(e)
        return
    # typ = choose_type( wf.getsampwidth() ) # TODO: implement choose_type
    nsamps = wf.getnframes()
    assert nsamps > 0
    fs = wf.getframerate()
    assert fs > 0
    # Read entire file and make into an array
    samps = list(array.array("i", wf.readframes(nsamps)))
    try:
        assert nsamps == len(samps)
    except AssertionError:
        print(nsamps, "not equal to", len(samps))
    return samps, fs

# simple peak detection
def peak_detect(data):
    max_val = numpy.amax(abs(data))
    peak_ndx = numpy.where(data == max_val)
    if len(peak_ndx[0]) == 0:  # if nothing found then the max must be negative
        peak_ndx = numpy.where(data == -max_val)
    return peak_ndx

def bpm_detector(data, fs, debug=False):
    cA = []
    cD = []
    correl = []
    cD_sum = []
    levels = 4
    max_decimation = 2 ** (levels - 1)
    min_ndx = math.floor(60.0 / 220 * (fs / max_decimation))
    max_ndx = math.floor(60.0 / 40 * (fs / max_decimation))
    for loop in range(0, levels):
        cD = []
        # 1) DWT
        if loop == 0:
            [cA, cD] = pywt.dwt(data, "db4")
            cD_minlen = len(cD) / max_decimation + 1
            cD_sum = numpy.zeros(math.floor(cD_minlen))
        else:
            [cA, cD] = pywt.dwt(cA, "db4")
        # 2) Filter
        cD = signal.lfilter([0.01], [1 - 0.99], cD)
        # 4) Subtract out the mean.
        # 5) Decimate for reconstruction later.
        cD = abs(cD[:: (2 ** (levels - loop - 1))])
        cD = cD - numpy.mean(cD)
        # 6) Recombine the signal before ACF
        #    Essentially, each level the detail coefs (i.e. the HPF values) are concatenated to the beginning of the array
        cD_sum = cD[0 : math.floor(cD_minlen)] + cD_sum
    if [b for b in cA if b != 0.0] == []:
        return None
    # Adding in the approximate data as well...
    cA = signal.lfilter([0.01], [1 - 0.99], cA)
    cA = abs(cA)
    cA = cA - numpy.mean(cA)
    cD_sum = cA[0 : math.floor(cD_minlen)] + cD_sum
    # ACF
    correl = numpy.correlate(cD_sum, cD_sum, "full")
    midpoint = math.floor(len(correl) / 2)
    correl_midpoint_tmp = correl[midpoint:]
    peak_ndx = peak_detect(correl_midpoint_tmp[min_ndx:max_ndx])
    if len(peak_ndx) > 1:
        return None
    peak_ndx_adjusted = peak_ndx[0] + min_ndx
    bpm = 60.0 / peak_ndx_adjusted * (fs / max_decimation)
    if(debug):
        print(f"Current window's estimated BPM: {bpm}")
    return bpm, correl