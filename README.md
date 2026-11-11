# Bully MasterMod Easy Installer

An easy way to install the Bully MasterMod.

A Windows graphical utility that patches a **user provided Bully PS2 ISO** with files from a separately downloaded MasterMod folder.

## Get the Windows application

Open **Actions → Build Windows executable → latest successful run**, download the **Bully-MasterMod-Easy-Installer-Windows** artifact, extract it, and run `BullyModPatcher.exe`.

The executable is unsigned and Windows SmartScreen may show a warning.

## Use

1. Select your original legally obtained Bully PS2 ISO.
2. Select the extracted MasterMod folder containing `ACT`, `Scripts`, `DAT`, and `Config`.
3. Select a **new** output ISO path (do not use the original ISO filename).
4. Start the patch and wait until completion.
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

## Limitations and legal notice

This tool patches nine expected files in a standard ISO 9660 image. Other ISO layouts may not be supported. The source passes Python syntax checks, but the executable and resulting ISO still need real Windows and PCSX2 testing. No game ISO or mod assets are distributed. This unofficial utility is not affiliated with the game's publisher or the MasterMod authors.
