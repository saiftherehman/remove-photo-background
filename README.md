# Photo Background

A small offline tool that swaps the background of a photo for a plain colour.
I made it for CV and LinkedIn photos, where a soft grey or white background looks
cleaner than the bright blue you often get from a photo studio. It also works on
product photos, for example to put items on a clean white background for a shop.

You run it, drag your photo into the window, pick a colour number, and you get a new
photo saved in a **New Background** folder next to the old one. Your original file
is never touched.

It runs on Linux, macOS and Windows, and it doesn't need an account, a website or an
internet connection once it has been set up.

## Contents

- [How it works](#how-it-works)
- [What you need](#what-you-need)
- [Step 1: Install Python](#step-1-install-python)
- [Step 2: Download Photo Background](#step-2-download-photo-background)
- [Step 3: First run](#step-3-first-run)
- [What the program installs (reference)](#what-the-program-installs-reference)
- [Using it](#using-it)
- [Command line options](#command-line-options)
- [Using it without internet](#using-it-without-internet)
- [Moving it to another computer](#moving-it-to-another-computer)
- [Troubleshooting](#troubleshooting)
- [Folder layout](#folder-layout)
- [Credits](#credits)

## How it works

The tool looks at the edges of the photo first and picks one of two methods.

**Plain background** (a studio backdrop, a white wall), as long as the subject stands
out from it clearly. It measures how close each
pixel is to the background colour and replaces only those pixels. Every pixel of the
subject stays exactly as it was, so there is no loss in quality. This method needs
nothing except two small libraries. Afterwards it repaints the thin line along the
edge, which otherwise keeps a bit of the old colour (the blue halo you see around
hair and ears in most quick edits).

**Busy background** (a room, trees, a table, a street), or a plain backdrop that is
close in colour to the subject, like a wooden comb on a beige card. Here a simple
colour rule isn't enough, so it uses segmentation models, the same kind of model that
background remover websites use. The difference is that they run on your own computer.

It uses two models. BiRefNet does most of the work: it gives clean outlines and keeps
thin details, such as a strand of yarn, a plant stem or loose hair. IS-Net sometimes
finds a whole object that BiRefNet misses, such as a large folded map or a towel, but
it also likes to keep pieces of the table or wall. So an area only IS-Net found is
added only when its colours look like the rest of the subject and not like the
background. A piece at the edge of the photo that IS-Net calls background (the
corner of a tray, say) is dropped. The two files (about 400 MB together) are
downloaded once and then work offline. On a normal laptop a photo takes about 10
seconds. If you want speed over quality, add `--fast` to use IS-Net alone, which
takes one to two seconds but more often keeps bits of the background.

A few more steps follow. A guided filter moves the outline onto the real edges in the
photo, which matters for things like hair or the gaps between the teeth of a comb.
Areas the models are only half sure about are then either kept or dropped, so you
don't get a half see-through ghost of the table. Soft shadows just under an object
are removed. Then the old background colour is taken out of the soft edge pixels, so
you don't get a coloured fringe.

## What you need

The only thing you install yourself is **Python**. The program sets up everything
else on its first run: the Python libraries and the two models. It first checks
which libraries your computer already has, and uses those if they work and are new
enough. Only what is missing gets downloaded, into the program's own folder, so
nothing is installed twice and nothing is installed into your system. You don't need
to run `pip install` yourself.

| | Minimum |
|---|---|
| Python | 3.9 or newer (3.10 or newer is better) |
| pip | Comes with Python on Windows and macOS. A separate package on most Linux systems, see step 1 |
| Disk space | About 400 MB for the two models, plus up to 170 MB for libraries your computer doesn't have yet |
| Internet | Only for the first run, to download the libraries and the models |
| Admin rights | Not needed, except to install Python and pip on Linux |

Supported systems:

- **Linux**: Debian, Ubuntu, Mint, Pop!_OS, Fedora, RHEL, CentOS Stream, Rocky,
  AlmaLinux, Arch, Manjaro, openSUSE and others, on x86_64 and ARM64
- **macOS**: recent versions (12 Monterey or newer), Intel and Apple Silicon
- **Windows**: 10 and 11, 64-bit

## Step 1: Install Python

Check first, you may already have it. Open a terminal (on Windows: Command Prompt) and type:

```
python3 --version
```

On Windows type `py --version` instead. If it prints `Python 3.9` or higher, skip to
step 2.

### Debian, Ubuntu, Linux Mint, Pop!_OS

```
sudo apt update
sudo apt install python3 python3-pip
```

### Fedora

```
sudo dnf install python3 python3-pip
```

### RHEL, CentOS Stream, Rocky Linux, AlmaLinux (8 and newer)

The default `python3` on version 8 is 3.6, which is too old. Install a newer one next
to it. It doesn't replace the system Python, so nothing else breaks.

```
sudo dnf install python3.11 python3.11-pip
```

The Linux start script finds `python3.11` by itself. CentOS 7 is too old for this tool.

### Arch Linux, Manjaro, EndeavourOS

```
sudo pacman -S python python-pip
```

### openSUSE

```
sudo zypper install python3 python3-pip
```

### macOS

1. Download the installer from [python.org/downloads/macos](https://www.python.org/downloads/macos/)
   and run it.
2. When it finishes, a Finder window opens. Double-click **Install Certificates.command**
   in it. Without this step Python can't download the models.

If you use Homebrew, `brew install python` works too, and the certificate step isn't needed.

### Windows

1. Download the installer from [python.org/downloads/windows](https://www.python.org/downloads/windows/).
2. On the first screen of the installer, tick **Add python.exe to PATH**, then click
   **Install Now**.

## Step 2: Download Photo Background

**Option A, no Git needed.** On this GitHub page click the green **Code** button,
then **Download ZIP**. Unzip it wherever you want to keep the program, for example
your home folder.

**Option B, with Git.**

```
git clone https://github.com/saiftherehman/remove-photo-background.git
```

Keep the folder somewhere permanent. The Desktop button made in the next step points
to this folder, so if you move the folder later, see
[Moving it to another computer](#moving-it-to-another-computer).

## Step 3: First run

Open the folder and start the program:

| System | What to do |
|---|---|
| Linux | Double-click `run_linux.sh` and choose **Run in Terminal**, or open a terminal in the folder and type `./run_linux.sh` |
| macOS | Right-click `run_mac.command` and choose **Open**, then **Open** again (only the first time, see below) |
| Windows | Double-click `run_windows.bat` |

On the first run the program sets itself up. You don't have to do anything, just
leave the window open:

1. It checks for `numpy`, `Pillow` and `onnxruntime`. Any that are missing, too old
   or broken are downloaded and installed into its own `lib` folder. This takes a
   minute or two and you'll see pip's output scroll past. If your computer already
   has all three, this step is skipped.
2. It puts a **Photo Background** button and a **PhotoBackground** folder link on
   your Desktop.
3. It asks for your photo.
4. The first time you give it a photo with a busy background, it downloads the two
   models (about 400 MB) into its `models` folder. Every download is checked against
   a checksum, so a broken file is never used.

From then on, just use the button on the Desktop. Each time it starts, the program
checks the libraries and the `models` folder. If something is missing, for example
because the folder was copied to another computer, it downloads that part by itself.

To see what is installed and where, run:

```
python3 photo_background.py --check
```

```
Program folder: /home/alex/PhotoBackground
Python:         3.12.3 (/usr/bin/python3)
Libraries:
  numpy        2.3.5      already on this computer (/usr/lib/python3/dist-packages)
  pillow       12.1.1     already on this computer (/usr/lib/python3/dist-packages)
  onnxruntime  1.31.0     program's lib folder
Models in:      /home/alex/PhotoBackground/models
  isnet-general-use.onnx  179 MB
  BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx  224 MB
Desktop button: made
```

**Why right-click on macOS?** Files downloaded from the internet are blocked by
Gatekeeper the first time you double-click them. Right-click and **Open** tells macOS
you trust this one. You only do this once.

## What the program installs (reference)

You don't need to install any of this by hand. This list is here so you know what
the program uses and where it ends up.

**Python libraries:**

| Library | What it is for | Oldest version it accepts | Size if it has to be installed |
|---|---|---|---|
| [numpy](https://numpy.org) | All the pixel calculations | 1.21 | about 70 MB |
| [Pillow](https://python-pillow.org) | Opening and saving photos | 9.0 | about 25 MB |
| [onnxruntime](https://onnxruntime.ai) | Running the models, only needed for busy backgrounds | 1.16 | about 70 MB |

How the program decides what to install:

- A library that is already on your computer, loads without errors and is at least
  the version above is used as it is.
- A library that is missing, older than that, or broken (it fails to load) is
  installed into the program's `lib/<system>/` folder, for example
  `lib/linux-x86_64-py312` or `lib/win32-amd64-py313`.
- onnxruntime needs a few small helper packages (`protobuf`, `flatbuffers`,
  `packaging`, under 10 MB together). Again, only the ones your computer doesn't
  already have are added.
- pip picks the right files for your system by itself, so the same steps work on
  Linux, macOS and Windows.

If your computer has no Python libraries at all, the `lib` folder ends up at about
170 MB. If it already has numpy and Pillow, only onnxruntime is added, about 75 MB.

**Models**, saved in `models/`:

| File | What it is good at | Size |
|---|---|---|
| `isnet-general-use.onnx` | Finds whole objects the other one misses, and is fast | 179 MB |
| `BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx` | Clean outlines, thin details like hair, threads and stems | 224 MB |

**Desktop shortcut**, made once per computer:

| System | What is made |
|---|---|
| Linux | `photo-background.desktop` and a `PhotoBackground` folder link |
| macOS | `Photo Background.command` and a `PhotoBackground` folder link |
| Windows | `Photo Background.lnk` and `PhotoBackground folder.lnk` |

To remove everything, delete the program folder and the Desktop shortcuts. Nothing
else was changed on your computer.

## Using it

Start it from the Desktop button. You'll see this:

```
=== Photo Background ===
Photo name (or drag the photo here): my photo.jpg
Background colour:
  1. grey  (default)
  2. white
  3. offwhite
  4. lightblue
  5. darkgrey
  6. navy
  7. other (type #rrggbb or R,G,B)
Choose 1-7 [Enter = 1]: 2
Plain background found.
Done: /home/alex/Pictures/New Background/my photo.jpg  (450x570)

Another photo? (y = yes, Enter = close):
```

**Giving it the photo.** The easiest way is to drag the photo from your file manager
into the window and press Enter. You can also type just the file name if the photo is
on your Desktop, or in Pictures, Downloads or the program folder. If it can't find
the file it says so and asks again.

**Picking the colour.** Type the number and press Enter. Pressing Enter on its own
picks grey. Choose 7 to type any colour, either as a hex code like `#d6e4f0` or as
`214,228,240`.

**The result** is saved in a folder called **New Background**, which the program
makes next to your photo. It has the same name as the original and is a high quality
JPEG at the same size. If you run the same photo again, the result is replaced.

Which colour to use:

| Colour | Good for |
|---|---|
| grey | CVs and job applications. Soft and neutral, works with any shirt |
| white | Official forms and ID-style photos |
| offwhite | Like white, but less harsh on screen |
| lightblue | LinkedIn and company profiles |
| darkgrey, navy | Dark website themes and speaker profiles |

## Command line options

If you prefer the terminal, you can skip the questions:

```
python3 photo_background.py "photo.jpg"
python3 photo_background.py "photo.jpg" --color white
python3 photo_background.py "photo.jpg" --color "#d6e4f0" -o "cv photo.jpg"
python3 photo_background.py *.jpg --color lightblue
```

On Windows write `py` instead of `python3`.

| Option | What it does |
|---|---|
| `--color` | `grey`, `white`, `offwhite`, `lightblue`, `darkgrey`, `navy`, a hex code like `#e8eaed`, or `R,G,B`. Default is grey |
| `-o`, `--output` | Name of the new file. Only works with one photo |
| `--method` | `auto` (default), `plain` or `model`. Use it to force one method |
| `--fast` | Busy backgrounds: one model instead of two. About five times faster, but thin details may fade |
| `--download-model` | Downloads the models now, so busy backgrounds work later without internet |
| `--check` | Shows which libraries and models are installed, and where |
| `--lo`, `--hi` | Fine tuning for the plain method, see [Troubleshooting](#troubleshooting) |
| `-h`, `--help` | Shows all of this in the terminal |

## Using it without internet

The libraries are installed on the first run, but the models are only downloaded the
first time you give it a photo with a busy background. If you'll be offline later,
download them now:

```
python3 photo_background.py --download-model
```

After that the tool never needs the internet on this computer.

## Moving it to another computer

Copy the whole folder, including `lib` and `models`, to the other computer and start
it once with the start script for that system. You can even keep it on a USB stick.

The `lib` folder has one subfolder per type of computer, for example
`linux-x86_64-py312` or `win32-amd64-py313`. When the program starts on a computer it
hasn't seen before, it installs the right libraries for that computer next to the
others and makes a new Desktop button there. The models work everywhere, so they are
never downloaded twice.

If you moved the folder on the same computer, the old Desktop button will point to
the old place. Delete the button, delete the file `.desktop_shortcut_done` inside
`lib/<your system>/`, and start the program once from the folder.

## Troubleshooting

**"pip is not installed"** (Linux). Install pip with your package manager, see
[Step 1](#step-1-install-python). For example on Ubuntu: `sudo apt install python3-pip`.

**"Python 3.9 or newer is not installed"** (Linux). Your system Python is too old.
On RHEL, CentOS or Rocky: `sudo dnf install python3.11 python3.11-pip`.

**`CERTIFICATE_VERIFY_FAILED` or "can't check website certificates"** (macOS). Python
from python.org needs its certificates installed once. Run this, changing `3.13` to
your version:

```
open "/Applications/Python 3.13/Install Certificates.command"
```

**"Permission denied" when starting `run_linux.sh` or `run_mac.command`.** The file
lost its run permission while it was being unzipped. Fix it once:

```
chmod +x run_linux.sh run_mac.command
```

**The Desktop button does nothing** (Linux). On GNOME, right-click it and choose
**Allow Launching**. On other desktops, check that it is marked as executable in its
properties.

**`python` opens the Microsoft Store** (Windows). That is a Windows shortcut, not the
real Python. Install Python from python.org as described in step 1 and tick
**Add python.exe to PATH**.

**"onnxruntime isn't available for this computer"**. Some systems have no ready-made
onnxruntime package, for example Alpine Linux, 32-bit systems and very new Python
versions in their first weeks. Plain backgrounds still work. For busy backgrounds,
use a Python version that onnxruntime supports, usually the one before the newest.

**Some of the old background is left behind** (plain method). Raise `--lo`:

```
python3 photo_background.py "photo.jpg" --lo 45
```

**Clothes in a colour close to the background turn see-through** (plain method).
For example a blue shirt on a blue backdrop. Lower `--hi`, or use the models instead:

```
python3 photo_background.py "photo.jpg" --hi 70
python3 photo_background.py "photo.jpg" --method model
```

**Thin parts fade or go missing** (busy backgrounds). Check that you didn't use
`--fast`, and that both models are in the `models` folder (the program says
"2 models" while it works). Even then, something very thin and low in contrast, like
a pale thread on a pale blanket, can come out faint.

**A bit of the table or tray stays in the picture, or a part of the subject goes
missing** (busy backgrounds). When an object sits in a tray or on a cloth, or a
background object has the same colours as the subject, the models can get it wrong
in either direction. A side object both models are unsure about, like a cutting
board leaning in the corner, is usually left out. Crop the photo closer to the
subject and run it again.

**Gaps inside the subject keep the old background** (busy backgrounds). Small holes,
like the space between comb teeth or inside a cup handle, sometimes keep a little of
the background. The bigger the gap, the better it gets removed.

**It doesn't do videos.** Only photos (JPG, PNG, WebP, BMP, TIFF). Other files, such
as videos, are skipped with a message, and the rest of the photos are still done.

**Doing a whole folder at once.** Open a terminal in the folder and run
`python3 /path/to/photo_background.py * --color white`. Every photo gets done, the
results go into **New Background**, and anything that isn't a photo is skipped.

**Libraries seem broken after a Python or system update.** Delete the `lib` folder
and start the program again. It checks again what your computer has and installs
only what is missing.

**Not sure what is installed?** Run `python3 photo_background.py --check`
(`py photo_background.py --check` on Windows). It lists every library and model and
the folder it is in.

## Folder layout

```
photo-background/
├── photo_background.py    the program
├── run_linux.sh           start script for Linux
├── run_mac.command        start script for macOS
├── run_windows.bat        start script for Windows
├── README.md              this manual
├── models/                the program downloads the two models here
│   └── README.md          what the models folder is for
└── lib/                   libraries your computer was missing (one subfolder per system)
```

`lib/` and the model files are not on GitHub. The program creates them.

## Credits

- **IS-Net** (`isnet-general-use`) from the [DIS project](https://github.com/xuebinqin/DIS)
  by Xuebin Qin and others.
- **BiRefNet** (general, lite version) from [BiRefNet](https://github.com/ZhengPeng7/BiRefNet)
  by Peng Zheng and others.
- Both ONNX files are downloaded from the release page of
  [rembg](https://github.com/danielgatis/rembg). Please see those projects for their
  license terms.
- The edge refinement uses the guided filter by Kaiming He, Jian Sun and Xiaoou Tang.
- Built with [NumPy](https://numpy.org), [Pillow](https://python-pillow.org) and
  [ONNX Runtime](https://onnxruntime.ai).
