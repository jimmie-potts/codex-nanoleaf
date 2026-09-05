# Tray artwork

`tray-icon-source.png` is the approved wall-layout design, with a green status orb radiating into blue Lines. The artwork was developed with built-in imagegen and prepared with real alpha transparency. The icon is a fixed identity mark; its colors do not report live task status.

Run `python scripts/build-tray-icon.py` from the repository root to package the source into `bridge/tray-icon.ico`. This optional development command requires Pillow. The installed bridge does not require Pillow.

The ICO includes 16, 20, 24, 32, 48, and 256-pixel images. Packaging preserves the square close-up framing without extra padding. The enlarged green center and hexagon fill the tray slot; the four outer branches are cropped at the edges. The Windows tray and application shortcuts share this asset.
