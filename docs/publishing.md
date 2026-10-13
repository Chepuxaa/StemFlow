# Publishing the source repository

Install [Git for Windows](https://git-scm.com/install/windows) and create a GitHub
account. Create an empty GitHub repository named `StemFlow` without adding an
initial README, license or gitignore; those files already exist locally.

Run from the project directory:

```powershell
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "Initial StemFlow source"
git remote add origin https://github.com/YOUR_ACCOUNT/StemFlow.git
git push -u origin main
```

Replace `YOUR_ACCOUNT` with your GitHub username. Before committing, verify that
the staged files contain no `.venv`, `.cache`, weights, tracks or generated output.
Git may ask you to configure your name and email for commits.

If you prefer uploading files through GitHub's web interface, a source-only ZIP
can be created without Git:

```powershell
.\.venv\Scripts\python.exe scripts/package_source.py
```

It is saved to `%LOCALAPPDATA%\StemFlow\StemFlow-source.zip`.
Extract it and upload the source files; uploading the ZIP itself does not create
a browsable source repository. Do not upload model weights into Git.

EXE builds belong in GitHub Releases after the validation described in
[build.md](build.md). No repository is created or published automatically.
