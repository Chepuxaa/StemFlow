"""CUDA/CPU runtime for Mel-Band four-stem SYH v2."""

import importlib
from contextlib import nullcontext
import math
from pathlib import Path
import sys
import types

import numpy as np
import torch
import yaml
from app_paths import RESOURCE_DIR, MODEL_DIR

ROOT = RESOURCE_DIR


class ModelCache:
    """One model for a queue; released when its worker exits."""
    def __init__(self):
        self.model = None
        self.config = None
        self.device = None
        self.force_cpu = False

    def get(self, device):
        reused = self.model is not None and self.device == device
        if not reused:
            self.clear()
            self.model, self.config = load_model(device)
            self.device = device
        return self.model, self.config, reused

    def clear(self):
        self.model = self.config = self.device = None


class ConfigLoader(yaml.SafeLoader):
    pass


ConfigLoader.add_constructor("tag:yaml.org,2002:python/tuple",
                             lambda loader, node: tuple(loader.construct_sequence(node)))


def resolve_device(requested):
    if requested not in ('auto', 'cuda', 'cpu'):
        raise ValueError(f'Unknown device: {requested}')
    if requested == 'cpu':
        return 'cpu'
    if torch.cuda.is_available():
        return 'cuda:0'
    if requested == 'cuda':
        raise RuntimeError('CUDA unavailable. Select Auto or CPU in Settings.')
    return 'cpu'


def load_model(device='cuda:0'):
    source = ROOT / "vendor/msst/models"
    for name, path in (("models", source), ("models.bs_roformer", source / "bs_roformer")):
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    cls = importlib.import_module("models.bs_roformer.mel_band_roformer").MelBandRoformer
    config = yaml.load((ROOT / 'config/melband4.yaml').read_text(), Loader=ConfigLoader)
    assert config["audio"]["sample_rate"] == 44100
    assert config["training"]["instruments"] == ["drums", "bass", "other", "vocals"]
    assert config["model"]["num_stems"] == 4
    config["model"]["match_input_audio_length"] = True
    # Construct parameter shapes without allocating a second 3.76 GB of weights.
    with torch.device('meta'):
        model = cls(**config["model"])
    state = torch.load(MODEL_DIR / "ver2.ckpt", map_location="cpu", weights_only=True, mmap=True)
    model.load_state_dict(state, strict=True, assign=True)
    for module in model.modules():
        for name, buffer in list(module._buffers.items()):
            if buffer is None or not buffer.is_meta:
                continue
            if name not in module._non_persistent_buffers_set:
                raise ValueError(f'Checkpoint did not initialize buffer: {name}')
            if module is model and name == 'freq_indices':
                bands = model.freqs_per_band
                indices = torch.arange(bands.shape[1]).expand(bands.shape[0], -1)[bands]
                if config['model']['stereo']:
                    indices = (indices[:, None] * 2 + torch.arange(2)).reshape(-1)
                module._buffers[name] = indices
            elif name in ('cached_freqs', 'dummy'):
                module._buffers[name] = torch.zeros(buffer.shape, dtype=buffer.dtype, device='cpu')
            else:
                raise ValueError(f'Unknown uninitialized runtime buffer: {name}')
    if str(device).startswith('cuda'):
        model = model.eval().to(device)
    else:
        torch.set_num_threads(min(8, torch.get_num_threads()))
        model = model.eval().to(device=device, dtype=torch.float32)
    return model, config


def infer(model, config, audio, chunk_seconds=11, progress=None):
    """Use the four-source checkpoint's 75% overlap with normalized overlap-add."""
    size = int(chunk_seconds * config["audio"]["sample_rate"])
    step = size // config["inference"]["num_overlap"]
    length = len(audio)
    count = math.ceil(max(length - size, 0) / step) + 1
    output = np.zeros((4, 2, length), dtype=np.float32)
    weights = np.zeros(length, dtype=np.float32)
    taper = np.bartlett(size).astype(np.float32)
    device = next(model.parameters()).device
    for index in range(count):
        start = index * step
        stop = min(start + size, length)
        batch = torch.zeros((1, 2, size), device=device)
        batch[0, :, :stop - start] = torch.from_numpy(audio[start:stop].T.copy()).to(device)
        precision = torch.autocast('cuda', dtype=torch.float16) if device.type == 'cuda' else nullcontext()
        with torch.inference_mode(), precision:
            prediction = model(batch)[0].float().cpu().numpy()
        assert prediction.shape == (4, 2, size) and np.isfinite(prediction).all()
        window = taper.copy()
        if index == 0:
            window[:size // 2] = 1
        if index == count - 1:
            window[size // 2:] = 1
        valid = stop - start
        output[:, :, start:stop] += prediction[:, :, :valid] * window[None, None, :valid]
        weights[start:stop] += window[:valid]
        if progress is not None:
            progress(index + 1, count)
    assert np.all(weights > 0)
    output /= weights[None, None, :]
    return dict(zip(config["training"]["instruments"], output))
