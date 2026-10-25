<img width="256" height="256" alt="image_122e4a3e" src="https://github.com/user-attachments/assets/926be8e5-30a7-49bc-bb4c-9c234cc48b34" />

# Ginseng

Local gematria calculator. Type a word or phrase and see its value in 27 ciphers across English/Latin, Hebrew and Greek. Ginseng also remembers your past phrases and shows which ones share the same numbers.

## Features

- **Word Search:** Enter a word or phrase to see its value in every cipher.
- **Number Search:** Enter a number to see every phrase in your history that has that value.
- **History:** Every phrase you look up is saved, and you can filter it, delete entries, import and export your history.
- **Ciphers:** Including Ordinal, Reverse Ordinal, Reduction, Latin, Reverse Sumerian, Reverse Satanic, Hebrew Standard and Gadol, and Greek.
- **Colours:** Customize the UI if you want to.

## Download

Go to the [Releases](../../releases) page and download `Ginseng.exe`. No installation is needed, just run it.

Windows may show a SmartScreen warning because the program isn't signed. Click **More info**, then **Run anyway**.

## Run from source

You need Python 3.9 or newer. Keep `gematria.py`, `history.py` and `logo_data.py` in the same folder, then run:

    python gematria.py

You can also use it from the command line:

    python gematria.py "hello world"

## Build the .exe yourself

    pip install pyinstaller
    python -m PyInstaller --onefile --windowed --icon gematria.ico --name Ginseng gematria.py

The program ends up in the `dist` folder.

## Where your data is stored

Your history and settings are saved in your user folder (`.gematria_calculator.json` and `.gematria_settings.json`).
