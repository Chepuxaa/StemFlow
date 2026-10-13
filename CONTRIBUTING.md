# Contributing

Use the source setup in [README.md](README.md). Keep dependencies in `.venv`
and run `python scripts/check_repository.py` before opening a pull request.

Please include the trigger, expected behavior, actual behavior, device and
relevant validation. For audio issues, describe the model, chunk size and device;
share only audio you can redistribute. Avoid committing tracks, weights, cache,
personal paths, logs containing private filenames, or build output.

Keep the GUI lightweight. Inference and CUDA initialization belong in the worker.
Changes to model inference must preserve source order and be checked on real audio.
Replacement-mode changes must preserve originals if export or validation fails.
