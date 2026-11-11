# Bully MasterMod Easy Installer

An easy way to install the Bully MasterMod.

A Windows graphical utility that patches a **user-provided Bully PS2 ISO** with files from a separately downloaded MasterMod folder.

## Download for Windows

**[Download the latest Windows executable (GitHub Releases)](https://github.com/bedylsebub/Bully-Master-Mod-Installer/releases/latest)**

Once a release is published, open that page, expand **Assets**, and download **BullyModPatcher.exe**. No Python installation is needed.

**No release available yet?** Download the executable from the latest successful [GitHub Actions build](https://github.com/bedylsebub/Bully-Master-Mod-Installer/actions/workflows/build-windows.yml) under **Artifacts**, then extract the ZIP.

The executable is unsigned, so Windows SmartScreen may display a warning. Review the source code before running unfamiliar software.

## Use

1. Select your original legally obtained Bully PS2 ISO.
2. Select the extracted MasterMod folder containing `ACT`, `Scripts`, `DAT`, and `Config`.
3. Select a **new** output ISO path (do not use the original ISO filename).
4. Start the patch and wait for completion.
5. Load the resulting ISO in PCSX2 to check it.

The program refuses to overwrite your original ISO or an existing output file. Allow plenty of free space for temporary ISO copies.

## Run from source

Install Python 3 with Tkinter, then run:

```powershell
python BullyModPatcher.py
```

No third-party Python packages are required to run the source.

## Build yourself

On Windows with Python 3 installed, run `build_windows.bat`. This installs PyInstaller into a local virtual environment and produces `dist\BullyModPatcher.exe`.

## Publishing a release

Push a version tag such as `v1.0.0` to GitHub. The **Build Windows executable** workflow builds the portable executable and automatically attaches it to a GitHub Release. This requires repository Actions and workflow write permissions to be enabled. The executable is not published until a tagged workflow succeeds.

## Limitations and legal notice

This tool patches nine expected files in a standard ISO 9660 image. Other ISO layouts may not be supported. An executable build does not guarantee that a patched ISO boots correctly; test with PCSX2. No game ISO or mod assets are distributed. This unofficial utility is not affiliated with the game's publisher or the MasterMod authors.
