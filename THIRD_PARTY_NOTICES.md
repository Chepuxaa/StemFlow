# Third-party components

The MIT license at the repository root covers original StemFlow code. Third-party
code, assets, model weights and bundled runtime components retain their licenses.

| Component | License / attribution | Source |
|---|---|---|
| MSST Mel-Band architecture | MIT, Copyright 2024 Roman Solovyev (ZFTurbo); full license in `vendor/msst/LICENSE` | [MSST](https://github.com/ZFTurbo/Music-Source-Separation-Training), pinned in `vendor/msst/source.json` |
| MelBand 4-stem SYH v2 weights | Apache-2.0 as declared in the author's model card; distributed separately | [SYH99999 model card](https://huggingface.co/SYH99999/MelBandRoformer4StemFTLarge), pinned revision and hash in `config/model.json` |
| Roboto font | SIL Open Font License 1.1; full text in `ui/assets/fonts/OFL.txt` | [Google Fonts](https://github.com/google/fonts/tree/main/ofl/roboto) |
| StemFlow logo | User-supplied project artwork | `ui/assets/logo.svg` |

Python dependencies are installed separately and listed in `requirements/app.lock.txt`.
When distributing an EXE bundle, retain license notices for Python, PyTorch,
pywebview, pythonnet, NumPy, SciPy, librosa and the other bundled packages.
The bundled imageio-ffmpeg executable is FFmpeg 7.1 essentials from Gyan, built
with `--enable-gpl --enable-version3`, and declares GPL version 3 or later.
Its license text and build information are in `packaging/licenses`, copied to
`THIRD_PARTY_LICENSES/FFmpeg` in the Windows bundle. See
[FFmpeg licensing](https://ffmpeg.org/legal.html) and the
[Windows build provider](https://www.gyan.dev/ffmpeg/builds/).
Public binary distribution must also provide the corresponding FFmpeg source
under its license; a link to the provider alone does not fulfill that requirement.
Review the actual contents of the built distribution before a public binary release.

StemFlow is an independent project and is not affiliated with Native Instruments.
Traktor is used to describe the intended export compatibility.
