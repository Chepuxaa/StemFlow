# Windows runtime size

The CUDA runtime is the largest part of StemFlow. Model weights are separate;
compressing the application archive does not reduce its installed dependencies.

## Validated PyTorch profile

The default Windows build excludes these optional DLLs from PyTorch
`2.14.1+cu126`. The development environment itself is left intact.

| DLL | MiB | Component omitted |
|---|---:|---|
| cudnn_adv64_9.dll | 269.4 | Legacy advanced cuDNN APIs such as RNN/MHA |
| cusolverMg64_11.dll | 80.7 | Multi-GPU solver |
| curand64_10.dll | 60.3 | Separate cuRAND host library |
| nvrtc64_120_0.alt.dll | 43.8 | Alternate NVRTC library |
| nvperf_host.dll | 14.7 | Host profiling support |
| cufftw64_11.dll | 0.2 | FFTW compatibility wrapper |

Total excluded: approximately **469.1 MiB**. cuDNN graph, engines, operations
and heuristics remain available for the model's fast attention path. cuBLAS,
cuFFT, the primary NVRTC, the CPU runtime and required solver dependencies stay.

Validation on RTX 3070 8 GB and Ryzen 7 5700X:

- Inspect normal and delayed PE imports before selecting exclusion candidates.
- Load the real MelBand four-stem SYH v2 checkpoint in an isolated Torch clone.
- Infer deterministic stereo signals at 44.1 kHz, with 6- and 11-second chunks.
- All four CUDA outputs matched the full runtime bit for bit.
- All four CPU outputs matched bit for bit, including a clone run with CUDA hidden.
- Inspect loaded modules after inference: excluded DLLs were not found in any
  other directory, so the test did not silently use system copies.
- A single warm 11-second CUDA chunk took 1.153 s with the full runtime and
  1.149 s with the slim clone. These are smoke-test measurements, not a statistically
  controlled performance benchmark or a claim of acceleration.

The packaged worker was also tested with CUDA export and Auto export while
CUDA was hidden. Both produced validated five-stream Stem files. The prepared
slim application folder measured **3,983,472,057 bytes**, compared with
4,475,342,315 bytes for the initial full-runtime release.

The newly generated GUI EXE was blocked on the development PC by Windows Code
Integrity (event 3077: the unsigned file did not meet signing requirements).
Therefore native GUI startup for this build remains unverified. The published
alpha release has not been replaced by this development build. Release signing
must be handled before relying on unsigned builds on machines enforcing such
policies; no system security policy was changed during testing.
[Microsoft signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).

This profile is specific to the current inference path. Revalidate it when
changing PyTorch, the architecture or using training/other workloads. A full
runtime build is available by setting `STEMFLOW_FULL_RUNTIME=1`; the default
slim profile rejects an unvalidated PyTorch version.

## Alternative inference engines

- **ONNX Runtime** supports CPU and CUDA execution providers. Its CUDA provider
  still needs compatible CUDA and cuDNN dependencies; changing the engine does
  not by itself make those dependencies disappear.
  [Install requirements](https://onnxruntime.ai/docs/install/).
- **NVIDIA TensorRT for RTX** is described by NVIDIA as an inference engine under
  200 MB. It targets RTX GPUs, including the RTX 3070's compute capability 8.6.
  That size excludes StemFlow's model weights and is not a measured size of a
  converted StemFlow application. It does not supply our CPU fallback.
  [Overview](https://docs.nvidia.com/deeplearning/tensorrt-rtx/latest/index.html),
  [support matrix](https://docs.nvidia.com/deeplearning/tensorrt-rtx/latest/getting-started/support-matrix.html).

The current checkpoint is a PyTorch state dictionary. TensorRT-RTX expects an
ONNX model, with supported operators and precisions. MelBand uses complex
STFT/ISTFT, indexing and mask aggregation in addition to its transformer core.
Conversion needs a separate proof of compatibility and numerical equivalence;
spectral preprocessing and reconstruction may need to run outside the exported
neural core. No alternate backend is enabled in StemFlow yet.
[ONNX conversion guide](https://docs.nvidia.com/deeplearning/tensorrt-rtx/latest/installing-tensorrt-rtx/onnx-conversion.html).
