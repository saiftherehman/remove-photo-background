#!/usr/bin/env python3
"""Photo Background: replace the background of a photo with a plain colour.

Made for portraits (CV and profile photos), and it works on product photos too.

Run it with nothing after it and it asks for the photo and the colour:
    python3 photo_background.py

Or give everything at once:
    python3 photo_background.py "photo.jpg"
    python3 photo_background.py "photo.jpg" --color white
    python3 photo_background.py *.jpg --color lightblue

Two methods, picked automatically:
  plain  Plain one-colour backgrounds (studio blue, white wall) where the
         subject stands out clearly. Every pixel of the subject is kept as it
         is, so this gives the best quality.
  model  Everything else (walls, trees, rooms, a table, or a backdrop close in
         colour to the subject). Uses the two offline models in the
         "models" folder. No internet or account needed once they are there.
         Add --fast to use only one of them.

The first time it runs on a computer it installs numpy, Pillow and
onnxruntime into the "lib" folder next to this file, puts a
"Photo Background" button and a link to this folder on the Desktop, and
downloads the models when they are first needed. Nothing is installed
system-wide.
"""
import sys

if sys.version_info < (3, 9):
    sys.exit("Photo Background needs Python 3.9 or newer (3.10+ recommended). "
             f"This is Python {sys.version.split()[0]}.")

import argparse
import hashlib
import importlib
import importlib.metadata
import os
import platform
import re
import shlex
import subprocess
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
# One lib folder per OS, CPU and Python version, so the same folder keeps
# working when it is copied to (or shared between) different computers.
LIB = HERE / "lib" / (f"{sys.platform}-{platform.machine().lower()}"
                      f"-py{sys.version_info[0]}{sys.version_info[1]}")
MODELS_DIR = HERE / "models"

# The two models are good at different things. BiRefNet gives clean, firm
# edges and keeps thin threads and stems, so its mask is the base. IS-Net
# sometimes finds whole objects that BiRefNet misses (a large map, a towel),
# but also keeps pieces of tables and walls, so its extra areas are only
# added when their colours look like the subject (see combine_masks).
# name: input size, mean, std, output type, download size in MB, sha256
MODELS = {
    "isnet-general-use": (
        1024, (0.5, 0.5, 0.5), (1.0, 1.0, 1.0), "minmax", 179,
        "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"),
    "BiRefNet-general-bb_swin_v1_tiny-epoch_232": (
        1024, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225), "sigmoid", 224,
        "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333"),
}
ISNET = "isnet-general-use"
BIREFNET = "BiRefNet-general-bb_swin_v1_tiny-epoch_232"
FAST_MODEL = ISNET
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/{}.onnx"

COLORS = {
    "grey": (232, 234, 237),       # soft light grey, good for CVs
    "white": (255, 255, 255),
    "offwhite": (245, 245, 242),
    "lightblue": (214, 228, 240),
    "darkgrey": (60, 64, 70),
    "navy": (31, 45, 74),
}


# ---------------------------------------------------------------- setup ----

def pip_works():
    return subprocess.call([sys.executable, "-m", "pip", "--version"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def pip_missing_help():
    system = platform.system()
    if system == "Linux":
        return ("pip is not installed for this Python. Install it once, then start again:\n"
                "    Debian / Ubuntu / Mint:          sudo apt install python3-pip\n"
                "    Fedora / RHEL / CentOS / Rocky:  sudo dnf install python3-pip\n"
                "    Arch / Manjaro:                  sudo pacman -S python-pip\n"
                "    openSUSE:                        sudo zypper install python3-pip")
    if system == "Darwin":
        return "pip is missing. Run this once, then start again:\n    python3 -m ensurepip --upgrade"
    return ("pip is missing. Run this once, then start again:\n    py -m ensurepip --upgrade\n"
            "If that fails, reinstall Python from python.org with 'pip' ticked.")


# What the program needs: import name -> (pip package, oldest version that works).
# numpy and Pillow are required, onnxruntime is only needed for busy backgrounds.
LIBRARIES = {
    "numpy": ("numpy", "1.21"),
    "PIL": ("pillow", "9.0"),
    "onnxruntime": ("onnxruntime", "1.16"),
}


def version_tuple(text):
    parts = []
    for piece in re.split(r"[.+-]", text):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts)


def installed_version(package):
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def usable(module):
    """True if the module loads and is new enough. A copy that is already on the
    computer is used as it is; only missing, old or broken ones get installed."""
    package, minimum = LIBRARIES[module]
    try:
        importlib.import_module(module)
    except Exception:       # missing, or broken (e.g. built for another numpy)
        return False
    version = installed_version(package)
    return version is None or version_tuple(version) >= version_tuple(minimum)


def requirement_met(requirement):
    """Check one 'Requires-Dist' line of a package against what is installed."""
    if ";" in requirement:
        requirement, marker = requirement.split(";", 1)
        if "extra" in marker:       # optional extras are never needed here
            return True
    m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*(?:\[[^]]*\])?\s*(.*)", requirement)
    name, spec = m.group(1), m.group(2).strip(" ()")
    version = installed_version(name)
    if version is None:
        return False
    for clause in filter(None, (c.strip() for c in spec.split(","))):
        if clause.startswith(">=") and version_tuple(version) < version_tuple(clause[2:]):
            return False
    return True


def pip_install(packages):
    """Install packages into LIB, plus only those dependencies that are missing.

    pip's --target mode would otherwise reinstall every dependency, including
    ones the computer already has (a second numpy is 70 MB of wasted space).
    So each package is installed without dependencies, then its requirements
    are checked one by one against what is already there.
    """
    LIB.mkdir(parents=True, exist_ok=True)
    queue, done = list(packages), set()
    while queue:
        package = queue.pop(0)
        if package.lower() in done:
            continue
        done.add(package.lower())
        print(f"Installing {package} (needs internet)...", flush=True)
        cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
               "--no-deps", "--upgrade", "--target", str(LIB), package]
        if subprocess.call(cmd) != 0:
            return False
        importlib.invalidate_caches()
        name = re.match(r"[A-Za-z0-9_.\-]+", package).group(0)
        try:
            requires = importlib.metadata.requires(name) or []
        except importlib.metadata.PackageNotFoundError:
            requires = []
        for req in requires:
            if not requirement_met(req):
                dep = req.split(";")[0].replace(" ", "").replace("(", "").replace(")", "")
                queue.append(dep)
    return True


def ensure_libraries():
    """Make sure numpy, Pillow and onnxruntime can be used.

    Copies already on the computer are used if they work and are new enough.
    Anything missing, too old or broken is installed into LIB (this program's
    own folder, nothing system-wide). pip picks the right files for this OS
    and CPU. Returns True if onnxruntime works.
    """
    sys.path.insert(0, str(LIB))
    missing = [mod for mod in LIBRARIES if not usable(mod)]
    if not missing:
        return True
    if os.environ.get("PHOTO_BACKGROUND_RESTARTED"):
        # Already installed once in this run; whatever still fails can't be fixed here
        if "numpy" in missing or "PIL" in missing:
            sys.exit("The libraries were installed but can't be loaded. Delete the 'lib' "
                     "folder and start again.")
        print("Note: onnxruntime doesn't work on this computer, so only plain "
              "one-colour backgrounds can be replaced.")
        return False

    names = ", ".join(LIBRARIES[m][0] for m in missing)
    print(f"Setting up Photo Background on this computer: {names} needed.")
    print(f"They will be saved in: {LIB}", flush=True)
    if not pip_works():
        sys.exit(pip_missing_help())
    for mod in missing:
        package, minimum = LIBRARIES[mod]
        if not pip_install([f"{package}>={minimum}"]):
            if mod == "onnxruntime":
                print("onnxruntime has no version for this computer. Plain one-colour "
                      "backgrounds will still work.")
            else:
                sys.exit(f"Could not install {package}. Check the internet connection and "
                         "start again.")

    # Start again so the new libraries are loaded cleanly
    print("Setup finished.\n", flush=True)
    env = dict(os.environ, PHOTO_BACKGROUND_RESTARTED="1")
    sys.exit(subprocess.call([sys.executable, str(Path(__file__).resolve())] + sys.argv[1:],
                             env=env))


def show_status():
    """Print what is used and where. Used by --check."""
    print(f"Program folder: {HERE}")
    print(f"Python:         {sys.version.split()[0]} ({sys.executable})")
    print("Libraries:")
    lib = LIB.resolve()
    for mod, (package, _) in LIBRARIES.items():
        try:
            m = importlib.import_module(mod)
        except Exception:
            print(f"  {package:12} missing")
            continue
        where = Path(m.__file__).resolve()
        place = "program's lib folder" if lib in where.parents else f"already on this computer ({where.parent.parent})"
        print(f"  {package:12} {installed_version(package) or '?':10} {place}")
    print(f"Models in:      {MODELS_DIR}")
    for name, info in MODELS.items():
        f = MODELS_DIR / f"{name}.onnx"
        state = f"{f.stat().st_size / 1e6:.0f} MB" if f.is_file() else \
            f"not downloaded yet (about {info[4]} MB)"
        print(f"  {name}.onnx  {state}")
    marker = LIB / ".desktop_shortcut_done"
    print(f"Desktop button: {'made' if marker.exists() else 'not made yet'}")


def desktop_dir():
    system = platform.system()
    if system == "Windows":
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "[Environment]::GetFolderPath('Desktop')"],
                                 capture_output=True, text=True).stdout.strip()
            if out:
                return Path(out)
        except OSError:
            pass
    elif system == "Linux":
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                 capture_output=True, text=True).stdout.strip()
            if out:
                return Path(out)
        except OSError:
            pass
    return Path.home() / "Desktop"


def make_desktop_shortcut():
    """Once per computer: a "Photo Background" button and a folder link on the Desktop."""
    marker = LIB / ".desktop_shortcut_done"
    if marker.exists():
        return
    try:
        LIB.mkdir(parents=True, exist_ok=True)
        desk = desktop_dir()
        desk.mkdir(parents=True, exist_ok=True)
        system = platform.system()
        if system == "Linux":
            link = desk / "PhotoBackground"
            if not link.exists():
                link.symlink_to(HERE, target_is_directory=True)
            launcher = desk / "photo-background.desktop"
            launcher.write_text(
                "[Desktop Entry]\nType=Application\nName=Photo Background\n"
                "Comment=Replace the background of a photo\n"
                f'Exec="{HERE / "run_linux.sh"}"\nIcon=image-x-generic\nTerminal=true\n')
            launcher.chmod(0o755)
            (HERE / "run_linux.sh").chmod(0o755)
            try:    # GNOME won't run a desktop launcher until it is marked trusted
                subprocess.run(["gio", "set", str(launcher), "metadata::trusted", "true"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        elif system == "Windows":
            def q(s):
                return str(s).replace("'", "''")
            script = (
                "$w = New-Object -ComObject WScript.Shell; "
                f"$s = $w.CreateShortcut('{q(desk / 'Photo Background.lnk')}'); "
                f"$s.TargetPath = '{q(HERE / 'run_windows.bat')}'; "
                f"$s.WorkingDirectory = '{q(HERE)}'; "
                "$s.IconLocation = 'imageres.dll,67'; $s.Save(); "
                f"$f = $w.CreateShortcut('{q(desk / 'PhotoBackground folder.lnk')}'); "
                f"$f.TargetPath = '{q(HERE)}'; $f.Save()")
            subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True,
                           stdout=subprocess.DEVNULL)
        elif system == "Darwin":
            for name, target in (("Photo Background.command", HERE / "run_mac.command"),
                                 ("PhotoBackground", HERE)):
                link = desk / name
                if not link.exists():
                    link.symlink_to(target)
            (HERE / "run_mac.command").chmod(0o755)
        else:
            return
        marker.touch()
        print(f"Added a 'Photo Background' button and a folder link to {desk}")
    except (OSError, subprocess.SubprocessError) as e:
        print(f"Note: couldn't create the Desktop shortcut ({e}). "
              "You can still start the program from this folder.")


HAS_ORT = ensure_libraries()
make_desktop_shortcut()

import numpy as np                                      # noqa: E402
from PIL import Image, ImageFilter, ImageOps            # noqa: E402


# --------------------------------------------------------------- colours ---

def parse_rgb(text):
    """Accept a name (grey, white, ...), a hex code (#e8eaed) or R,G,B."""
    text = text.strip().lower()
    if text in COLORS:
        return COLORS[text]
    try:
        if text.startswith("#") and len(text) == 7:
            rgb = tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))
        else:
            rgb = tuple(int(v) for v in text.split(","))
    except ValueError:
        rgb = ()
    if len(rgb) != 3 or not all(0 <= v <= 255 for v in rgb):
        raise argparse.ArgumentTypeError(
            f"unknown colour '{text}'. Use a name ({', '.join(COLORS)}), #rrggbb or R,G,B")
    return rgb


# ----------------------------------------------------------- image tools ---

def border_pixels(im):
    return np.concatenate([im[:5].reshape(-1, 3), im[-5:].reshape(-1, 3),
                           im[:, :5].reshape(-1, 3), im[:, -5:].reshape(-1, 3)])


def border_is_plain(im):
    """True if the frame around the photo is one flat colour."""
    border = border_pixels(im)
    dist = np.linalg.norm(border - np.median(border, axis=0), axis=1)
    return np.mean(dist < 30) > 0.6


def plain_method_fits(im, lo=30, hi=90):
    """True if the plain method will give a clean result.

    The background must be one flat colour, and the subject must stand out
    from it. If a lot of pixels are close to the background colour without
    matching it (a wooden comb on a peach backdrop, soft shadows), the plain
    method would make them half see-through, so the models do better.
    On a portrait against a studio backdrop only the thin outline is unsure,
    about 1% of the pixels.
    """
    if not border_is_plain(im):
        return False
    bg = np.median(border_pixels(im), axis=0)
    a = np.clip((np.linalg.norm(im - bg, axis=2) - lo) / (hi - lo), 0, 1)
    return ((a > 0.05) & (a < 0.95)).mean() < 0.03


def gaussian_blur(x, sigma):
    """Separable Gaussian blur on a float array (keeps full precision)."""
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        xp = np.pad(x, pad, mode="edge")
        n = x.shape[axis]
        x = sum(w * np.take(xp, range(i, i + n), axis=axis) for i, w in enumerate(k))
    return x


def box_mean(x, r):
    """Mean over a (2r+1) x (2r+1) window. Near the edges the window is clipped."""
    for axis in (0, 1):
        n = x.shape[axis]
        pad = [(0, 0)] * x.ndim
        pad[axis] = (1, 0)
        c = np.cumsum(np.pad(x, pad), axis=axis)
        hi = np.minimum(np.arange(n) + r + 1, n)
        lo = np.maximum(np.arange(n) - r, 0)
        shape = [1] * x.ndim
        shape[axis] = n
        x = (np.take(c, hi, axis=axis) - np.take(c, lo, axis=axis)) / (hi - lo).reshape(shape)
    return x


def guided_filter(guide, p, r=6, eps=1e-3):
    """Colour guided filter (He, Sun and Tang, 2010).

    Moves the soft edges of the mask p onto the real colour edges of the
    photo, for example the gaps between the teeth of a comb.
    guide: HxWx3 in 0..1, p: HxW in 0..1.
    """
    mean_i = np.stack([box_mean(guide[..., c], r) for c in range(3)], -1)
    mean_p = box_mean(p, r)
    cov_ip = (np.stack([box_mean(guide[..., c] * p, r) for c in range(3)], -1)
              - mean_i * mean_p[..., None])
    var = np.empty(guide.shape[:2] + (3, 3))
    for i in range(3):
        for j in range(i, 3):
            v = box_mean(guide[..., i] * guide[..., j], r) - mean_i[..., i] * mean_i[..., j]
            var[..., i, j] = var[..., j, i] = v
    var += eps * np.eye(3)
    a = np.linalg.solve(var, cov_ip[..., None])[..., 0]
    b = mean_p - (a * mean_i).sum(-1)
    mean_a = np.stack([box_mean(a[..., c], r) for c in range(3)], -1)
    return np.clip((mean_a * guide).sum(-1) + box_mean(b, r), 0, 1)


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def to_arr(img):
    return np.asarray(img).astype(float) / 255


# ---------------------------------------------------------------- masks ----

def plain_mask(im, lo=30, hi=90):
    """Alpha from the colour distance to a flat background colour."""
    bg = np.median(border_pixels(im), axis=0)
    dist = np.linalg.norm(im - bg, axis=2)
    alpha = np.clip((dist - lo) / (hi - lo), 0, 1)
    # Clean specks, pull the edge in by 1 px, then soften it a little.
    return to_arr(to_img(alpha).filter(ImageFilter.MedianFilter(3))
                  .filter(ImageFilter.MinFilter(3))
                  .filter(ImageFilter.GaussianBlur(0.7)))


def wanted_models(fast=False):
    return [FAST_MODEL] if fast else list(MODELS)


def present_models(fast=False):
    return [n for n in wanted_models(fast) if (MODELS_DIR / f"{n}.onnx").is_file()]


def get_models(fast=False):
    """Download any missing model. Returns the models that are ready to use."""
    for name in wanted_models(fast):
        if not (MODELS_DIR / f"{name}.onnx").is_file():
            try:
                download_model(name)
            except OSError as e:
                print(f"Couldn't get the model {name}: {e}")
    return present_models(fast)


def download_model(name):
    MODELS_DIR.mkdir(exist_ok=True)
    dst = MODELS_DIR / f"{name}.onnx"
    tmp = dst.with_suffix(".part")
    print(f"Downloading the model {name} (about {MODELS[name][4]} MB, one time only)...")

    def progress(blocks, block_size, total):
        if total > 0:
            done = min(blocks * block_size, total)
            print(f"\r  {done / 1e6:4.0f} / {total / 1e6:.0f} MB", end="", flush=True)

    try:
        urllib.request.urlretrieve(MODEL_URL.format(name), tmp, progress)
    except urllib.error.URLError as e:
        if tmp.exists():
            tmp.unlink()
        if "CERTIFICATE_VERIFY_FAILED" in str(e) and platform.system() == "Darwin":
            v = f"{sys.version_info[0]}.{sys.version_info[1]}"
            raise OSError("macOS Python can't check website certificates yet. Run this once:\n"
                          f'    open "/Applications/Python {v}/Install Certificates.command"') from e
        raise OSError(f"download failed ({e.reason})") from e
    print()

    h = hashlib.sha256()
    with open(tmp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != MODELS[name][5]:
        tmp.unlink()
        raise OSError("the downloaded file is damaged (checksum mismatch). Try again.")
    tmp.replace(dst)
    print(f"Model saved to {dst}")


_sessions = {}


def run_model(name, img):
    """One model's guess of the subject, as an alpha mask at the photo's size."""
    import onnxruntime as ort
    size, mean, std, output = MODELS[name][:4]
    if name not in _sessions:
        _sessions[name] = ort.InferenceSession(str(MODELS_DIR / f"{name}.onnx"),
                                               providers=["CPUExecutionProvider"])
    session = _sessions[name]
    x = np.asarray(img.resize((size, size), Image.LANCZOS)).astype(np.float32)
    x = x / max(float(x.max()), 1e-6) if output == "minmax" else x / 255
    x = ((x - np.array(mean)) / np.array(std)).transpose(2, 0, 1)[None].astype(np.float32)
    y = session.run(None, {session.get_inputs()[0].name: x})[0][0, 0]
    if output == "sigmoid":
        y = 1 / (1 + np.exp(-y))
    else:
        y = (y - y.min()) / max(float(y.max() - y.min()), 1e-6)
    alpha = Image.fromarray((y * 255).astype(np.uint8)).resize(img.size, Image.BICUBIC)
    return to_arr(alpha.filter(ImageFilter.MedianFilter(3)))


def label_regions(mask):
    """Number the connected areas of a bool array (4 neighbours).
    Returns the labels (0 = not in mask) and how many areas there are."""
    h, w = mask.shape
    labels = np.zeros((h, w), int)
    n = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if labels[y0, x0]:
            continue
        n += 1
        labels[y0, x0] = n
        todo = deque([(y0, x0)])
        while todo:
            y, x = todo.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not labels[yy, xx]:
                    labels[yy, xx] = n
                    todo.append((yy, xx))
    return labels, n


def resized(a, size):
    return to_arr(to_img(a).resize(size, Image.BILINEAR))


def grown(mask, k):
    return to_arr(to_img(mask).filter(ImageFilter.MaxFilter(k))) > 0.5


def combine_masks(img, isnet, birefnet, s=256):
    """One mask from both models.

    BiRefNet is the base. Areas where only IS-Net is sure are added when
    their colours look like the subject rather than the background, or when
    BiRefNet found a piece of the same thing (same colours) inside them, so
    an object is kept whole or dropped whole. Pieces touching the edge of
    the photo that IS-Net calls background are dropped (a tray corner).
    Decisions are made on a small copy, which is plenty and much faster.
    """
    si, sb = resized(isnet, (s, s)), resized(birefnet, (s, s))
    q = np.asarray(img.resize((s, s), Image.BILINEAR)) // 16
    colour = (q[..., 0].astype(int) * 16 + q[..., 1]) * 16 + q[..., 2]

    def colours(m):
        """Share of each colour (16 steps per channel, slightly smoothed) in area m."""
        h = (np.bincount(colour[m], minlength=4096) / max(m.sum(), 1)).reshape(16, 16, 16)
        for axis in range(3):
            h = (np.roll(h, 1, axis) + 2 * h + np.roll(h, -1, axis)) / 4
        return h.ravel()

    subject_colours = colours(sb > 0.95)
    looks_subject = subject_colours / (subject_colours + colours((sb < 0.05) & (si < 0.5)) + 1e-9)

    pieces, _ = label_regions(sb > 0.5)
    extra, n = label_regions((si > 0.75) & (sb < 0.5))
    keep = np.zeros((s, s), bool)
    for k in range(1, n + 1):
        area = extra == k
        if area.mean() < 0.001:        # specks, such as one gap between comb teeth
            continue
        if looks_subject[colour[area]].mean() > 0.55:
            keep |= area
            continue
        # A hole that BiRefNet left inside the subject (gaps between comb
        # teeth) stays a hole
        near = grown(area, 5)
        if (sb[near & ~area] > 0.5).mean() > 0.8:
            continue
        # A whole object IS-Net is almost certain about (a wreath, a group of
        # pumpkins). Pieces of a table or wall get lower scores.
        if si[area].mean() > 0.975 and area.mean() > 0.005:
            keep |= area
            continue
        # A BiRefNet piece mostly surrounded by this area, with the same colours?
        area_colours = colours(area)
        for p in np.unique(pieces[near & (pieces > 0)]):
            piece = pieces == p
            if piece.sum() >= area.sum():
                continue
            rim = grown(piece, 3) & ~piece
            if (rim & area).sum() > 0.5 * rim.sum() and \
                    np.minimum(colours(piece), area_colours).sum() > 0.6:
                keep |= area
                break

    drop = np.zeros((s, s), bool)
    final, n = label_regions((sb > 0.5) | keep)
    edge = np.unique(np.concatenate([final[0], final[-1], final[:, 0], final[:, -1]]))
    for k in edge[edge > 0]:
        piece = final == k
        # IS-Net calls it background, or it is a small piece only IS-Net found
        if si[piece].mean() < 0.1 or (sb[piece].mean() < 0.1 and piece.mean() < 0.005):
            drop |= piece

    # Back to full size, a little wider so the soft edges of the areas come along
    keep = grown(resized(keep.astype(float), img.size), 9)
    drop = grown(resized(drop.astype(float), img.size), 9)
    # Inside a kept area IS-Net is fairly sure everywhere, so make it solid
    added = keep * np.clip((isnet - 0.25) / 0.5, 0, 1)
    return np.where(drop, 0, np.maximum(birefnet, added))


def drop_shadows(im, alpha, r=16, below=12):
    """Soft pixels just under the subject that are only a darker copy of the
    local background (same colour, less light) are a shadow, not the subject.

    Only done where the subject above has a clearly different colour from
    the background (a brown bowl on a cream blanket). For a grey thread or
    a black bat on a light table, a soft edge and a shadow look the same,
    so those are left alone.
    """
    def ratio(x, ref):
        """Brightness compared with ref, and how much the colour differs."""
        rt = x / np.maximum(ref, 1)
        m = rt.mean(-1)
        return m, rt.std(-1) / np.maximum(m, 1e-3)

    is_bg = (alpha < 0.05).astype(float)
    weight = box_mean(is_bg, r)
    bg = (np.stack([box_mean(im[..., c] * is_bg, r) for c in range(3)], -1)
          / np.maximum(weight, 1e-3)[..., None])
    light, tint = ratio(im, bg)
    shade = (np.clip((0.97 - light) / 0.1, 0, 1) * np.clip((0.12 - tint) / 0.06, 0, 1)
             * (weight > 0.05))

    # Average colour of the solid subject in the few pixels straight above
    solid = (alpha > 0.95).astype(float)
    total = np.zeros_like(im)
    count = np.zeros(alpha.shape)
    for k in range(1, below + 1):
        total[k:] += im[:-k] * solid[:-k, :, None]
        count[k:] += solid[:-k]
    _, subject_tint = ratio(total / np.maximum(count, 1)[..., None], bg)
    coloured = np.clip((subject_tint - 0.12) / 0.08, 0, 1) * (count > 0)
    return np.where(alpha < 0.9, alpha * (1 - shade * coloured), alpha)


def model_mask(img, models):
    """Alpha from the offline model(s), refined on the photo's own edges."""
    if len(models) > 1:
        print(f"Finding the subject of the photo ({len(models)} models, about 10 seconds)...")
    else:
        print("Finding the subject of the photo...")
    masks = {name: run_model(name, img) for name in models}
    if ISNET in masks and BIREFNET in masks:
        alpha = combine_masks(img, masks[ISNET], masks[BIREFNET])
    else:
        alpha = np.maximum.reduce(list(masks.values()))
    im = np.asarray(img).astype(float)
    alpha = guided_filter(im / 255, alpha)
    # Firm up the result, so a half-sure area (a ghost of the table) is
    # either kept or dropped instead of staying half see-through
    alpha = np.clip((alpha - 0.2) / 0.6, 0, 1)
    return drop_shadows(im, alpha)


# -------------------------------------------------------------- compose ----

def clean_edges_plain(im, alpha):
    """Edge colours for the plain method.

    Edge pixels still carry some of the flat background colour (a coloured
    halo), so their colour is taken from nearby solid pixels of the subject.
    The edge band is thin here, so this is safe.
    """
    core = to_arr(to_img(alpha > 0.99).filter(ImageFilter.MinFilter(5)))
    weight = gaussian_blur(core, 3)[..., None]
    nearby = np.stack([gaussian_blur(im[..., c] * core, 3) for c in range(3)], -1)
    nearby = np.where(weight > 1e-3, nearby / np.maximum(weight, 1e-3), im)
    return np.where((alpha < 0.99)[..., None], nearby, im)


def clean_edges_model(im, alpha, r=8):
    """Edge colours for the model method.

    Soft areas can be wide here (comb teeth, hair), so instead of repainting
    them, the old background colour is taken out: the local background is
    the average of nearby pixels that are clearly background, and each soft
    pixel is solved from  pixel = a * subject + (1 - a) * background.
    Texture inside the soft area is kept.
    """
    is_bg = (alpha < 0.05).astype(float)
    weight = box_mean(is_bg, r)
    bg = np.stack([box_mean(im[..., c] * is_bg, r) for c in range(3)], -1)
    bg = np.where(weight[..., None] > 1e-3, bg / np.maximum(weight, 1e-3)[..., None], im)
    a = alpha[..., None]
    fg = (im - (1 - a) * bg) / np.maximum(a, 0.15)
    soft = (a > 0.02) & (a < 0.98) & (weight[..., None] > 1e-3)
    return np.where(soft, np.clip(fg, 0, 255), im)


def composite(fg, alpha, new_bg):
    a = alpha[..., None]
    out = a * fg + (1 - a) * np.array(new_bg, float)
    return Image.fromarray(out.round().clip(0, 255).astype(np.uint8))


OUTPUT_DIR = "New Background"     # made next to the photo, holds the results


def process(src, color, dst=None, method="auto", lo=30, hi=90, fast=False):
    """Make the new photo. Returns its path, or None if src isn't a readable photo."""
    try:
        img = ImageOps.exif_transpose(Image.open(src))
        img.load()
    except (OSError, ValueError, Image.DecompressionBombError):
        print(f"Skipped: {src.name} is not a photo this program can open "
              "(it reads JPG, PNG, WebP, BMP and TIFF).")
        return None
    icc = img.info.get("icc_profile")
    rgb = img.convert("RGB")
    im = np.asarray(rgb).astype(float)

    if method == "auto":
        if plain_method_fits(im, lo, hi):
            method = "plain"
            print("Plain background found.")
        else:
            method = "model"
            print("Plain background, but the subject is close to it in colour."
                  if border_is_plain(im) else "Busy background found.")
    if method == "model":
        if not HAS_ORT:
            print("The model can't run on this computer (no onnxruntime), using the plain method.")
            method = "plain"
        else:
            models = get_models(fast)
            if not models:
                print("No model available, using the plain method instead.")
                method = "plain"

    if method == "model":
        alpha = model_mask(rgb, models)
        fg = clean_edges_model(im, alpha)
    else:
        alpha = plain_mask(im, lo, hi)
        fg = clean_edges_plain(im, alpha)
    result = composite(fg, alpha, color)
    if dst:
        dst = Path(dst)
    else:
        out_dir = src.parent / OUTPUT_DIR
        out_dir.mkdir(exist_ok=True)
        dst = out_dir / f"{src.stem}.jpg"
    result.save(dst, quality=97, subsampling=0, icc_profile=icc)
    print(f"Done: {dst}  ({result.width}x{result.height})")
    return dst


# ---------------------------------------------------------- interactive ----

def ask_photo():
    """Ask until an existing file is given. Accepts paths dragged into the window."""
    folders = [Path.cwd(), HERE] + [Path.home() / d for d in ("Desktop", "Pictures", "Downloads")]
    while True:
        raw = input("Photo name (or drag the photo here): ").strip()
        if raw.startswith("& "):        # PowerShell adds this when a file is dragged in
            raw = raw[2:].strip()
        if not raw:
            continue
        texts = [raw, raw.strip("'\"")]
        try:                            # dragged paths can come quoted or escaped
            parts = shlex.split(raw, posix=os.name != "nt")
            if len(parts) == 1:
                texts.append(parts[0].strip("'\""))
        except ValueError:
            pass
        for t in texts:
            for cand in [Path(t).expanduser()] + [f / t for f in folders]:
                if cand.is_file():
                    return cand
        print(f"  Can't find '{texts[-1]}'. Drag the photo into this window, or type its full path.")


def ask_color():
    names = list(COLORS)
    print("Background colour:")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}{'  (default)' if i == 1 else ''}")
    print(f"  {len(names) + 1}. other (type #rrggbb or R,G,B)")
    while True:
        choice = input(f"Choose 1-{len(names) + 1} [Enter = 1]: ").strip() or "1"
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return COLORS[names[int(choice) - 1]]
        if choice == str(len(names) + 1):
            try:
                return parse_rgb(input("  Colour: "))
            except argparse.ArgumentTypeError as e:
                print(f"  {e}")
                continue
        print("  Please type one of the numbers.")


def interactive():
    print("=== Photo Background ===")
    try:
        while True:
            src = ask_photo()
            color = ask_color()
            if process(src, color) is None:
                continue
            if input("\nAnother photo? (y = yes, Enter = close): ").strip().lower() != "y":
                break
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")


def main():
    if len(sys.argv) == 1:      # no arguments: ask step by step
        interactive()
        return

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="*", type=Path, help="photo(s) to process")
    p.add_argument("-o", "--output", type=Path,
                   help="output file (only with one photo). Default: a 'New Background' "
                        "folder next to the photo, same file name")
    p.add_argument("--color", type=parse_rgb, default="grey",
                   help="new background: a name (" + ", ".join(COLORS) + "), #rrggbb or R,G,B. "
                        "Default: grey")
    p.add_argument("--method", choices=("auto", "plain", "model"), default="auto",
                   help="auto (default) uses plain for one-colour backgrounds and model for the rest")
    p.add_argument("--fast", action="store_true",
                   help="busy backgrounds: use one model instead of two. About 5x faster, "
                        "but thin things like threads and stems may fade")
    p.add_argument("--check", action="store_true",
                   help="show which libraries and models are installed, and where")
    p.add_argument("--download-model", action="store_true",
                   help="download the models now, so busy backgrounds work later without internet")
    p.add_argument("--lo", type=float, default=30,
                   help="plain method: below this colour distance a pixel is background (default 30)")
    p.add_argument("--hi", type=float, default=90,
                   help="plain method: above this colour distance a pixel is the subject (default 90)")
    args = p.parse_args()

    if args.check:
        show_status()
        return
    if args.download_model:
        ready = get_models(args.fast)
        if len(ready) < len(wanted_models(args.fast)):
            sys.exit("Not all models could be downloaded. Check the internet connection and try again.")
        print(f"Models ready in {MODELS_DIR}")
    if not args.inputs:
        if not args.download_model:
            p.error("give at least one photo, or run it without arguments to be asked")
        return
    if args.output and len(args.inputs) > 1:
        p.error("--output can only be used with one photo")

    done = skipped = 0
    for src in args.inputs:
        if src.is_dir():        # e.g. the results folder, picked up by *
            continue
        if not src.is_file():
            print(f"Skipped: {src} not found")
            skipped += 1
            continue
        print(f"\n{src.name}")
        if process(src, args.color, args.output, args.method, args.lo, args.hi, args.fast):
            done += 1
        else:
            skipped += 1
    if len(args.inputs) > 1:
        print(f"\nFinished: {done} photo(s) done, {skipped} file(s) skipped.")


if __name__ == "__main__":
    main()
