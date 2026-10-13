# Third-party components

The MIT license at the repository root covers original StemFlow code. Third-party
code, assets, model weights and bundled runtime components retain their licenses.

| Component | License / attribution | Source |
|---|---|---|
| MSST Mel-Band architecture | MIT, Copyright 2024 Roman Solovyev (ZFTurbo); full license in `packaging/licenses/MSST/LICENSE` | [MSST](https://github.com/ZFTurbo/Music-Source-Separation-Training), architecture revision in `config/model.json` |
| MelBand 4-stem SYH v2 weights | Apache-2.0 as declared in the author's model card; distributed separately | [SYH99999 model card](https://huggingface.co/SYH99999/MelBandRoformer4StemFTLarge), pinned revision and hash in `config/model.json` |
| Roboto font | SIL Open Font License 1.1; full text in `ui/assets/fonts/OFL.txt` | [Google Fonts](https://github.com/google/fonts/tree/main/ofl/roboto) |
| StemFlow logo | User-supplied project artwork | `ui/assets/logo.svg` |
| truststore | MIT; native system certificate verification | [truststore](https://github.com/sethmlarson/truststore) |
| certifi | MPL-2.0; bundled public CA certificates | [certifi](https://github.com/certifi/python-certifi) |
| ONNX | Apache-2.0; used for local fast CPU conversion | [ONNX](https://github.com/onnx/onnx) |

Python dependencies are installed separately and listed in `requirements/app.lock.txt`.
When distributing an EXE bundle, retain license notices for Python, ONNX Runtime,
TensorRT for RTX, pywebview, pythonnet, NumPy and the other bundled packages.
TensorRT for RTX is proprietary NVIDIA software, distributed as an incorporated
runtime component under its own terms; StemFlow's MIT license does not apply to it.
See the [NVIDIA TensorRT RTX agreement](https://docs.nvidia.com/deeplearning/tensorrt-rtx/latest/reference/sla.html).
The model was originally converted using PyTorch and the MSST architecture.
Those tools are no longer part of this repository or the application runtime.
Converted model files retain Apache-2.0.
FFmpeg is acquired directly from the upstream imageio-ffmpeg wheel during setup;
its executable is excluded from StemFlow's release archives. The upstream tool
is FFmpeg 7.1 essentials from Gyan, built
with `--enable-gpl --enable-version3`, and declares GPL version 3 or later.
Its license text and build information are in `packaging/licenses`, copied to
`THIRD_PARTY_LICENSES/FFmpeg` in the Windows bundle. See
[FFmpeg licensing](https://ffmpeg.org/legal.html) and the
[Windows build provider](https://www.gyan.dev/ffmpeg/builds/).
Anyone repackaging the acquired FFmpeg binary must also provide its corresponding
source under its license; a link to the provider alone does not fulfill that requirement.
Review the actual contents of the built distribution before a public binary release.

StemFlow is an independent project and is not affiliated with Native Instruments.
Traktor is used to describe the intended export compatibility.
