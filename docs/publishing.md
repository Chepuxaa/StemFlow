# Publishing an application release

The repository is [Chepuxaa/StemFlow](https://github.com/Chepuxaa/StemFlow).
Application builds use a single `StemFlow.exe`; model assets live in a separate
release and are downloaded by the app.

1. Run repository checks and unit tests as documented in the README.
2. Review the staged diff; exclude tracks, weights, local caches and credentials.
3. Commit and push the source to `main`.
4. Build and verify the EXE using [build.md](build.md).
5. Create a draft prerelease targeting the source commit.
6. Upload `StemFlow.exe` and `SHA256SUMS.txt`; verify asset size and checksum.
7. Publish the prerelease with setup instructions, changes and known limitations.

No split archive or `_internal` directory is required for the current build.
Dependency licenses are embedded. Do not include downloaded models, engine
caches or the acquired FFmpeg binary in the application release.
