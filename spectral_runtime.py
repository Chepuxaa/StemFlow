"""MelBand STFT, mask averaging and inverse STFT using NumPy only."""
import numpy as np

RATE = 44100
FFT_SIZE = 4096
HOP = 882
WINDOW = np.hanning(FFT_SIZE + 1)[:-1].astype(np.float32)


def spectrum_of(audio):
    """Input batch/channel/sample; output batch/frequency-channel/time/complex."""
    padded = np.pad(audio, ((0, 0), (0, 0), (FFT_SIZE // 2, FFT_SIZE // 2)), mode='reflect')
    frames = np.lib.stride_tricks.sliding_window_view(padded, FFT_SIZE, axis=-1)[..., ::HOP, :]
    spectrum = np.fft.rfft(frames * WINDOW, axis=-1).transpose(0, 3, 1, 2)
    spectrum = spectrum.reshape(audio.shape[0], 4098, -1)
    return np.stack([spectrum.real, spectrum.imag], axis=-1).astype(np.float32)


def reconstruct(spectrum, masks, indices, length):
    source = spectrum[..., 0] + 1j * spectrum[..., 1]
    masks = masks[..., 0].astype(np.float32) + 1j * masks[..., 1].astype(np.float32)
    summed = np.zeros((source.shape[0], 4, 4098, source.shape[-1]), dtype=np.complex64)
    for batch in range(source.shape[0]):
        for stem in range(4):
            np.add.at(summed[batch, stem], indices, masks[batch, stem])
    denominator = np.bincount(indices, minlength=4098).astype(np.float32).clip(1e-8)[:, None]
    separated = source[:, None] * (summed / denominator)
    separated = separated.reshape(source.shape[0], 4, 2049, 2, -1).transpose(0, 1, 3, 4, 2)
    separated[..., 0] = 0  # SYH v2 zero_dc=True.
    frames = np.fft.irfft(separated, n=FFT_SIZE, axis=-1) * WINDOW
    total = FFT_SIZE + HOP * (frames.shape[-2] - 1)
    output = np.zeros((*frames.shape[:-2], total), dtype=np.float32)
    weights = np.zeros(total, dtype=np.float32)
    for frame in range(frames.shape[-2]):
        start = frame * HOP
        output[..., start:start + FFT_SIZE] += frames[..., frame, :]
        weights[start:start + FFT_SIZE] += WINDOW * WINDOW
    selection = slice(FFT_SIZE // 2, FFT_SIZE // 2 + length)
    return output[..., selection] / weights[selection].clip(1e-8)
