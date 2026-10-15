#!/usr/bin/env python3
"""
OmniVoice 0.6B  -  ONNX int4  -  CPU voice cloning (one script)

Put this file INSIDE the OmniVoice ONNX model folder (next to llm_decoder.onnx).

Install:   pip install numpy soundfile librosa tokenizers
Upgrade:   pip install -U onnxruntime

Run:       python omnivoice_cpu.py              (menu: language -> reference path -> text)
           python omnivoice_cpu.py --check      (quick check: size of every file vs the real size on HF)
           python omnivoice_cpu.py --verify     (deep check: sha256 of every file)
           python omnivoice_cpu.py --fix        (quick check + resume/repair downloads, then stop)
           python omnivoice_cpu.py --probe      (writes outputs/omnivoice_io_report.txt)

Downloads: big files are fetched with an HTTP Range resume, so a disconnection is safe -
           run the script again and it continues from the last byte instead of starting over.
           A file is only called complete when its byte size (and sha256) matches the repo.

Result:    <model folder>/outputs/omnivoice_<time>.wav
"""
import os, sys, re, time, json, argparse, gc, threading, math
from pathlib import Path

# make Unicode art / Hindi safe on Windows consoles
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
try:
    os.system("")          # enables ANSI colours in Windows 10+ terminals
except Exception:
    pass

C1, C2, C3, DIM, BOLD, OFF = "\033[38;5;45m", "\033[38;5;213m", "\033[38;5;220m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    C1 = C2 = C3 = DIM = BOLD = OFF = ""

# ---------------------------------------------------------------- terminal art
# 74-column identity block.  The animated version reveals it line by line, types the
# subtitle, sweeps an equalizer, then settles.  Non-TTY (logs, pipes) gets the plain
# static block, so output stays readable in a file.
_W = 74
_LOGO = [
    "  ██████╗ ███╗   ███╗███╗   ██╗██╗██╗   ██╗ ██████╗ ██╗ ██████╗███████╗",
    " ██╔═══██╗████╗ ████║████╗  ██║██║██║   ██║██╔═══██╗██║██╔════╝██╔════╝",
    " ██║   ██║██╔████╔██║██╔██╗ ██║██║██║   ██║██║   ██║██║██║     █████╗  ",
    " ██║   ██║██║╚██╔╝██║██║╚██╗██║██║╚██╗ ██╔╝██║   ██║██║██║     ██╔══╝  ",
    " ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║ ╚████╔╝ ╚██████╔╝██║╚██████╗███████╗",
    "  ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝   ╚═════╝ ╚═╝ ╚═════╝╚══════╝",
]
_SUB1 = "◢◤  O M N I L I N G U A L   V O I C E   C L O N I N G  ◥◣"
_SUB2 = "0.6B · ONNX int4 · CPU · English / हिन्दी · HIGGS V2"
_SPEC = "25 fps · 8 codebooks · 1024 tokens · 32-step unmasking"
_EQ = "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁"

_T = "   ╔" + "═" * (_W + 2) + "╗"
_B = "   ╚" + "═" * (_W + 2) + "╝"

def _mid(txt="", col=""):
    body = txt[:_W].ljust(_W)
    return f"   ║ {col}{body}{OFF if col else ''} ║"

def _eq_row(frame, width=_W, col=None):
    s = _EQ * 6
    off = frame % len(_EQ)
    body = (s[off:] + s[:off])[:_W].ljust(_W)
    return f"   ║ {col or DIM}{body}{OFF} ║"

ART = "\n".join([_T] + [_mid(l, "") for l in _LOGO] + [_mid(""),
                 _mid("        " + _SUB1, ""), _mid("          " + _SUB2, ""),
                 _mid("      " + _SPEC, ""), _mid(""), _eq_row(0), _B]) + "\n"

# animation master switch: --no-anim or NO_ANIM=1 turns it off, non-TTY falls back
ANIM = True

def _anim_on():
    return ANIM and sys.stdout.isatty() and os.environ.get("NO_ANIM", "") in ("", "0", "false", "False")

# ---------------------------------------------------------------- live HUD
class _Hud:
    """One live line at the bottom of the terminal: spinner + status + progress.

    Log lines printed through say()/log() are always placed ABOVE it, so scrollback
    stays clean, and the status line is redrawn in place on a background thread.
    """

    _SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self):
        self.lock = threading.RLock()
        self.status = ""
        self._lines = 0
        self._frame = 0
        self._thread = None
        self._stop = False
        self._last_len = 0

    # ---- plumbing
    def _erase(self):
        if self._lines:
            sys.stdout.write("\033[{}A\033[J".format(self._lines))
            sys.stdout.flush()
            self._lines = 0

    def _paint(self):
        if not self.status:
            return
        spin = self._SPIN[self._frame % len(self._SPIN)]
        text = f"   {C1}{spin}{OFF} {self.status}"
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
        self._lines = 1

    def _loop(self):
        while not self._stop:
            time.sleep(0.10)
            if not _anim_on():           # logs / pipes: never paint a live line
                continue
            with self.lock:
                self._frame += 1
                if self.status and self._running:
                    self._erase()
                    self._paint()

    @property
    def _running(self):
        return self._thread is not None and not self._stop

    def start(self):
        if _anim_on() and self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop = True
        if self._thread is not None:
            self._thread.join(timeout=0.4)
        with self.lock:
            self._erase()

    # ---- api
    def set(self, text):
        with self.lock:
            self.status = text
            if _anim_on():
                self._erase()
                self._paint()

    def clear(self):
        with self.lock:
            self.status = ""
            self._erase()

    def log(self, msg=""):
        with self.lock:
            self._erase()
            print(msg, flush=True)
            self._paint()


HUD = _Hud()

def anim_banner():
    """The intro: reveal the logo, type the subtitle, sweep the equalizer."""
    if not _anim_on():
        print(ART)
        return
    out = sys.stdout
    out.write(_T + "\n")
    for i, line in enumerate(_LOGO):
        flash = C1 if i % 2 == 0 else C1
        out.write(_mid(line, flash) + "\n")
        out.flush()
        time.sleep(0.055)
    out.write(_mid("") + "\n")
    # typed subtitle
    for k in range(0, len(_SUB1) + 1, 2):
        out.write("\r" + _mid("        " + _SUB1[:k], C2) + "\x1b[K")
        out.flush()
        time.sleep(0.011)
    out.write("\r" + _mid("        " + _SUB1, C2) + "\x1b[K\n")
    out.write(_mid("          " + _SUB2, C3) + "\n")
    out.write(_mid("      " + _SPEC, "") + "\n")
    out.write(_mid("") + "\n")
    for f in range(17):                      # equalizer sweep, fast then easing out
        out.write("\r" + _eq_row(f * (2 if f < 10 else 1), col=C2) + "\x1b[K")
        out.flush()
        time.sleep(0.035 if f < 12 else 0.07)
    out.write("\r" + _eq_row(0, col="") + "\x1b[K\n")
    out.write(_B + "\n")
    out.flush()


def bar(frac, width=26, full="█", edge="▒", empty="░"):
    frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
    n = int(round(frac * width))
    left = width - n
    return full * n + (edge if left else "") + empty * max(0, left - 1 if left else 0)

# ----------------------------------------------------------------- libraries
# Only the modes that actually run the models need onnxruntime / librosa.
# --analyze works with numpy + soundfile alone, so a diagnostics run never fails
# just because a library is missing.
_missing = []

import numpy as np

try:
    import onnxruntime as ort
except Exception:
    ort = None
    _missing.append("onnxruntime")

try:
    import soundfile as sf
except Exception:
    sf = None
    _missing.append("soundfile")

try:
    import librosa
except Exception:
    librosa = None
    _missing.append("librosa")


def require_libs(which=None):
    """Stop with the pip line if a library this mode needs is missing."""
    need = list(which if which is not None else _missing)
    need = [n for n in need if n in _missing]
    if need:
        print(ART)
        print("Missing libraries. Run:\n  pip install " + " ".join(sorted(set(need))))
        sys.exit(1)


# ----------------------------------------------------------------- settings
NUM_STEPS = 32               # unmasking steps (official OmniVoice uses 32; 16 = faster/rougher)
MAX_CHARS_PER_PART = 200     # long text is split into parts of about this size
PAUSE_SEC = 0.20             # silence between parts
UNLOAD_AFTER_GENERATE = True # free models from RAM after every generation
SEED = 1234                  # kept for reproducibility of any sampling / Gumbel tie-breaks
MAX_REF_SECONDS = 12         # the reference clip is trimmed to this length
# How the output length is estimated: OmniVoice generates a fixed number of frames, it never
# decides the duration itself.  "rate" = same speaking rate as the reference clip (default),
# "chars" = 25 frames per ~13 characters, "fixed" = LENGTH_FRAMES below.
LENGTH_MODE = "rate"
LENGTH_FRAMES = 256          # used when LENGTH_MODE == "fixed"  (~10 s)
PROMPT_STYLE = "template"    # "template" = <|lang_start|>..<|text_start|>.. (OmniVoice style)
                             # "plain"    = raw text tokens (the ONNX repo's inference.py style)
DIAG = True                  # print per-run decoding diagnostics
SR = 24000
FRAME_RATE = 25              # codec frames per second (24000 / 960)
NUM_CODEBOOKS = 8
MASK_ID = 1024
THREADS = max(1, os.cpu_count() or 4)

LANGUAGES = {"1": ("English", "en"), "2": ("Hindi", "hi")}

HERE = Path(__file__).resolve().parent
MODEL = HERE
OUT = HERE / "outputs"

# every file that is needed for voice cloning  (name, needed-for)
REQUIRED = [
    ("llm_decoder.onnx", "backbone"),
    ("llm_decoder.onnx.data", "backbone weights"),
    ("audio_embeddings_encoder.onnx", "text + audio embeddings"),
    ("audio_embeddings_encoder.onnx.data", "embedding weights"),
    ("audio_heads_decoder.onnx", "codebook heads"),
    ("higgs_decoder.onnx", "codes -> waveform"),
    ("acoustic_encoder.onnx", "reference voice (acoustic)"),
    ("semantic_encoder.onnx", "reference voice (semantic)"),
    ("quantizer_encoder.onnx", "reference voice -> codes"),
    ("tokenizer.json", "text tokenizer"),
    ("config.json", "model settings"),
]


# ----------------------------------------------------------------- file check + resumable download
# Sizes and sha256 of every file on the Hugging Face repo (onnx-community/OmniVoice-Onnx),
# snapshotted 2026-10-15.  A local file smaller than its expected size is a PARTIAL download,
# not a complete one - that is the "it shows complete but it is half" case.
HF_ROOT = "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/"
HF_BASE = HF_ROOT + "audio_tokenizer/"
EXPECTED = {
    "llm_decoder.onnx": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/llm_decoder.onnx", "size": 298798, "sha256": "dba2abc6753795f47e9c2f79e274ba1149de8a056f4cda35c7fb30fa0e50fedc"},
    "llm_decoder.onnx.data": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/llm_decoder.onnx.data", "size": 296484864, "sha256": "59aa22f43d7b501d9ce64183106e60b65f97fb67e92f5d9e088d07504cf63383"},
    "audio_embeddings_encoder.onnx": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_embeddings_encoder.onnx", "size": 2172, "sha256": "5b216f18a58e33e52e7d2a85ea843b996b1b7da6ecfbc5d70fb82f5e15136ab6"},
    "audio_embeddings_encoder.onnx.data": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_embeddings_encoder.onnx.data", "size": 327426048, "sha256": "e2c605b03749beefd0b9d1c037b1ebd2d0c9c5c29928d7e382a1d4e5d3316660"},
    "audio_heads_decoder.onnx": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_heads_decoder.onnx", "size": 16795584, "sha256": "38e69afe9c9aa531fa59f23337d7fecbe84b7b04dc9c3ce0b871249a1c659ad4"},
    "higgs_decoder.onnx": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_tokenizer/higgs_decoder.onnx", "size": 86500102, "sha256": "b28b3317a6cbf0d0f4a71b476ecb5c767612a31702da6561154783c94b6fa806"},
    "acoustic_encoder.onnx": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_tokenizer/acoustic_encoder.onnx", "size": 205546480, "sha256": "431a5e58528f33c1f001baa64f979572667ff69f26bc727701e3529932065401"},
    "semantic_encoder.onnx": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_tokenizer/semantic_encoder.onnx", "size": 436736856, "sha256": "db5751893fb44487658e8de1a88096b5421c590ac203c8d124b6972a990c79d3"},
    # alt = the fp16 export, same file name, smaller graph
    "quantizer_encoder.onnx": {"alt": [6091791], "url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_tokenizer/quantizer_encoder.onnx", "size": 12131293, "sha256": "e4f0b707b06c24f7343d0d2d9bd977c1a4560d64b84bd19f30cdde54da1731a9"},
    "tokenizer.json": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/tokenizer.json", "size": 11423986, "sha256": "408f669b7e2b045fdf54201d815bd364e6667dbd845115da81239c40bc6dcfd1"},
    "config.json": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/config.json", "size": 1416, "sha256": ""},
    "acoustic_encoder.onnx.data": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_tokenizer/fp16/acoustic_encoder.onnx.data", "size": 102615040, "sha256": "eab4ff631dbd1346c23656c5b0b1dcc40f4608edd7f7f508e0a044950e233116"},
    "higgs_decoder.onnx.data": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_tokenizer/fp16/higgs_decoder.onnx.data", "size": 43100160, "sha256": "5be7ff51d117dd1cd001b87ec6e6e93f61cbe923355c50841a15fcaf19f64a19"},
    "semantic_encoder.onnx.data": {"url": "https://huggingface.co/onnx-community/OmniVoice-Onnx/resolve/main/audio_tokenizer/fp16/semantic_encoder.onnx.data", "size": 218235904, "sha256": "60c714753677a409e4226bc1e840f6e400bbbe0ab26f10618926a06cdf0e46ba"},
}
# models that exist in two shapes: one big .onnx, or a small graph + a big .data next to it
SPLIT_CAPABLE = ("semantic_encoder", "acoustic_encoder", "higgs_decoder", "quantizer_encoder")
PART_SUFFIX = ".part"
NET_TIMEOUT = 25


def human(n):
    if n >= 1e9:  return f"{n / 1e9:.2f} GB"
    if n >= 1e6:  return f"{n / 1e6:.1f} MB"
    return f"{n / 1e3:.0f} KB"


def say(msg="", **kw):
    """Print a normal line.  The live HUD is moved out of the way and restored."""
    if msg == "" and not kw:
        HUD.log()
    else:
        HUD.log(msg)


def local_path(name):
    """Where a manifest name lives locally (the *_fp16.onnx aliases have separate files)."""
    if name.endswith("_fp16.onnx"):
        return MODEL / (name[:-len("_fp16.onnx")] + "_fp16.onnx")
    return MODEL / name


GRAPH_MAX_BYTES = 5_000_000      # an ONNX "graph" with external weights is a few hundred KB;
                                 # anything bigger than this is the single-file export


def is_split_export(name):
    """True when this model is stored as a small graph + a .data weight file."""
    if not name.endswith(".onnx"):
        return False
    base = name[:-5]
    if base not in SPLIT_CAPABLE:
        return False
    g, d = MODEL / name, MODEL / f"{base}.onnx.data"
    return g.exists() and d.exists() and g.stat().st_size < GRAPH_MAX_BYTES


def sha256_file(path, chunk=1 << 22):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def head_remote(url, timeout=NET_TIMEOUT):
    """HEAD follow-redirects -> {"size", "etag", "ranges"}.  None if offline."""
    import urllib.request, urllib.error
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "omnivoice-cpu/1.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            h = r.headers
            size = int(h.get("Content-Length") or 0)
            return {"size": size, "etag": (h.get("ETag") or "").strip('"').lower(),
                    "ranges": (h.get("Accept-Ranges", "").lower() == "bytes" or size > 0)}
    except Exception:
        return None


def _looks_like_html_or_error(p, n=2048):
    try:
        with open(p, "rb") as f:
            head = f.read(n).lstrip().lower()
        return head.startswith(b"<") or head.startswith(b"<!doctype") or b"<html" in head
    except Exception:
        return False


def file_problem(name):
    """Quick check of one file: returns (status, detail) where status is
    OK / PARTIAL / MISSING / WRONG / EXTRA.  No hashing here - it is instant."""
    p = local_path(name)
    part = p.with_name(p.name + PART_SUFFIX)
    spec = EXPECTED.get(name)
    if spec is None:
        return ("MISSING", "not in manifest")
    want = spec["size"]
    have = p.stat().st_size if p.exists() else 0
    phave = part.stat().st_size if part.exists() else 0
    alts = spec.get("alt") or []
    if have == want or (have and have in alts):
        return ("OK", f"{human(have)}")            # exact size -> done, this is the real check
    if is_split_export(name):                      # tiny graph + external .data weights
        return ("SPLIT", f"graph {human(have)} + .data export")
    if have and have < GRAPH_MAX_BYTES and name.endswith(".onnx") \
            and (MODEL / (name[:-5] + ".onnx.data")).exists():
        return ("SPLIT", f"graph {human(have)} + .data export")
    if have > want:
        return ("EXTRA", f"{human(have)} > {human(want)}")
    if have > 100:
        return ("PARTIAL", f"{human(have)} of {human(want)}  ({100.0 * have / want:.1f}%, "
                           f"{human(want - have)} missing)")
    if phave > 0:
        return ("PARTIAL", f"{human(phave)} of {human(want)} in {part.name}")
    return ("MISSING", f"expected {human(want)}")


def check_files(verbose=True, live=False, fix_partial_aliases=True):
    """Quick integrity check of every needed file.  Returns the list of file names that
    are not exactly right (missing / partial / wrong size)."""
    if verbose:
        say(f"\n{BOLD}[1] Checking model files{OFF}   {DIM}{MODEL}{OFF}")
    problems, alias = [], []
    for name, purpose in REQUIRED:
        status, detail = file_problem(name)
        # if a split (.onnx + .onnx.data) export is present, do not demand the single big file
        if name.endswith(".onnx") and status in ("PARTIAL", "MISSING"):
            if is_split_export(name):
                alias.append(name)
                status, detail = "SPLIT", "graph + .data export"
        colour = {"OK": C1, "SPLIT": C1}.get(status, C2 if status == "MISSING" else C3)
        if verbose:
            say(f"    {colour}{status:<8}{OFF}  {name:<38} {detail:>34}   {DIM}{purpose}{OFF}")
        if status not in ("OK", "SPLIT"):
            problems.append(name)
    if verbose:
        extra = [n for n in EXPECTED if n.endswith(".data") and local_path(n).exists()
                 and n[:-5] in SPLIT_CAPABLE and is_split_export(n[:-5] + ".onnx")]
        for n in extra:
            p = local_path(n)
            st = "OK" if p.stat().st_size == EXPECTED[n]["size"] else "PARTIAL"
            if st != "OK":
                if verbose:
                    say(f"    {C3}{st:<8}{OFF}  {n:<38} {human(p.stat().st_size):>34}   {DIM}weights (extra){OFF}")
                if n not in problems:
                    problems.append(n)
        if alias:
            say(f"    {DIM}({', '.join(a[:-4] for a in alias)} found as graph + .data - that is fine){OFF}")
        if live:
            say(f"    {DIM}checking sizes against huggingface.co ...{OFF}")
            for name in list(problems):
                spec = EXPECTED.get(name)
                if not spec:
                    continue
                info = head_remote(spec["url"])
                if info and info["size"] and info["size"] != spec["size"]:
                    say(f"    {C3}NOTE{OFF}  {name}: remote size changed "
                        f"({human(info['size'])}, manifest says {human(spec['size'])})")
    return problems


def verify_files(deep=True, verbose=True):
    """Deep verification: sha256 (and it is the only way to catch a full-size but corrupt
    file).  Returns the list of file names that fail."""
    if verbose:
        say(f"\n{BOLD}[1b] Verifying contents (sha256){OFF}")
    bad = []
    names = [n for n, _ in REQUIRED if local_path(n).exists()]
    for name in names:
        p = local_path(name)
        spec = EXPECTED.get(name)
        if spec is None:
            continue
        if p.stat().st_size != spec["size"]:
            bad.append(name)
            if verbose:
                say(f"    {C2}BAD SIZE {OFF}  {name:<38} {human(p.stat().st_size)} != {human(spec['size'])}")
            continue
        if deep and spec.get("sha256"):
            t = time.time()
            got = sha256_file(p)
            good = got.startswith(spec["sha256"][:16]) or got == spec["sha256"]
            if verbose:
                say(f"    {C1 if good else C2}{'OK      ' if good else 'HASH BAD'}{OFF}  {name:<38} "
                    f"{DIM}{human(p.stat().st_size)}  {time.time() - t:.1f}s{OFF}")
            if not good:
                bad.append(name)
    if verbose and not names:
        say(f"    {C2}no files to verify{OFF}")
    return bad


# ---- resumable download ------------------------------------------------------
def _open_range(url, start, timeout=NET_TIMEOUT):
    """Open the url from byte `start`.  Returns (response, resumed_from)."""
    import urllib.request
    hdr = {"User-Agent": "omnivoice-cpu/1.1"}
    if start > 0:
        hdr["Range"] = f"bytes={start}-"
    req = urllib.request.Request(url, headers=hdr)
    r = urllib.request.urlopen(req, timeout=timeout)
    if start > 0 and getattr(r, "status", 200) != 206:      # server ignored the range
        try:
            r.close()
        except Exception:
            pass
        return None, 0
    return r, (start if getattr(r, "status", 200) == 206 else 0)


def acquire_lock(path, timeout=900):
    """One downloader per file.  Two processes writing the same .part would corrupt it,
    so the second one waits (and then finds the file already complete)."""
    lock = Path(str(path) + ".lock")
    t0 = time.time()
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return lock
        except FileExistsError:
            try:                                     # steal a lock left behind by a crash
                if time.time() - lock.stat().st_mtime > 6 * 3600:
                    lock.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.time() - t0 > timeout:
                return None
            time.sleep(2)
        except Exception:
            return None


def release_lock(lock):
    if lock:
        try:
            Path(lock).unlink()
        except Exception:
            pass


def download(url, dst, size=None, sha256=None, tries=10, label=None, quiet=False):
    """Download with resume.  Keeps everything already fetched, retries forever-ish,
    only renames to the final name once the size (and hash, if known) is right.

    Safe to run again after a disconnection: it continues from the byte it stopped at.
    """
    dst = Path(dst)
    part = dst.with_name(dst.name + PART_SUFFIX)
    label = label or dst.name
    _lock = acquire_lock(dst)
    if _lock is None:
        say(f"    {C2}{label}: another download of this file is running - try again in a moment{OFF}")
        return False
    try:
        return _download_locked(url, dst, part, size, sha256, tries, label, quiet)
    finally:
        release_lock(_lock)


def _download_locked(url, dst, part, size, sha256, tries, label, quiet):
    if size is None:
        spec = EXPECTED.get(dst.name)
        size = spec["size"] if spec else None
        sha256 = sha256 or (spec.get("sha256") if spec else None)

    # an existing file that is not complete becomes the partial we resume from
    if dst.exists() and not part.exists():
        have = dst.stat().st_size
        if size and have == size:
            if _verify_ok(dst, sha256):
                if not quiet:
                    say(f"    {C1}OK{OFF}      {label:<30} {human(have)}   {DIM}complete, hash verified{OFF}")
                return True
            say(f"    {C2}{label}: size is right but the hash is wrong - re-downloading from scratch{OFF}")
            dst.unlink()
        elif _looks_like_html_or_error(dst):
            say(f"    {C2}{label}: existing file is an error page, starting over{OFF}")
            dst.unlink()
        else:
            dst.rename(part)

    got = part.stat().st_size if part.exists() else 0
    if size and got > size:                 # too long -> cut back to the expected length
        with open(part, "r+b") as f:
            f.truncate(size)
        got = size
    if size and got == size:
        part.rename(dst)
        if not quiet:
            say(f"    {C1}OK{OFF}      {label:<30} {human(size)}   {DIM}complete, hash verified{OFF}")
        return True

    if got and not _looks_like_html_or_error(part):
        say(f"    {C3}{label}: resuming from {human(got)}{OFF}" + (f" of {human(size)}" if size else ""))
    elif got:
        say(f"    {C2}{label}: partial file looks corrupt, restarting{OFF}")
        part.unlink()
        got = 0

    t0, base = time.time(), got
    attempt = 0
    while attempt < tries:
        attempt += 1
        try:
            resp, start = _open_range(url, got)
            if resp is None:                                 # range refused -> clean restart
                if got:
                    say(f"    {C2}{label}: server refused resume, restarting{OFF}")
                    part.unlink()
                    got = 0
                    continue
            if size is None:
                total = int(resp.headers.get("Content-Length") or 0)
                size = total + start if total else None
            mode = "ab" if start > 0 else "wb"
            with open(part, mode) as f:
                last = time.time()
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    now = time.time()
                    if now - last > 0.25:
                        last = now
                        pct = f"{100.0 * got / size:5.1f}%" if size else "  ?  "
                        rate = (got - base) / max(1e-6, now - t0)
                        eta = (size - got) / rate if (size and rate > 1) else 0
                        print(f"\r      {label:<30} {pct}  {human(got):>10}"
                              + (f" / {human(size):>10}" if size else "")
                              + f"  {human(rate)}/s" + (f"  ETA {eta:4.0f}s" if eta else "      "),
                              end="", flush=True)
            try:
                resp.close()
            except Exception:
                pass
            print(f"\r      {label:<30} {'100.0%' if size and got >= size else '     '}  "
                  f"{human(got):>10}" + (f" / {human(size):>10}" if size else "") + " " * 18)
            if size and got < size:
                raise IOError(f"connection closed early at {human(got)} of {human(size)}")
            if size and got > size:
                with open(part, "r+b") as f:
                    f.truncate(size)
            if sha256:
                have = sha256_file(part)
                if not (have.startswith(sha256[:16]) or have == sha256):
                    say(f"    {C2}{label}: hash mismatch after download - re-downloading{OFF}")
                    part.unlink()
                    got, base, t0 = 0, 0, time.time()
                    continue
            part.rename(dst)
            say(f"    {C1}OK{OFF}      {label:<30} {human(size if size else got)}   "
                f"{DIM}{time.time() - t0:4.0f}s{OFF}")
            return True
        except Exception as e:
            say(f"    {C3}{label}: {type(e).__name__}: {e}{OFF}")
            got = part.stat().st_size if part.exists() else 0
            if attempt < tries:
                wait = min(30, 2 ** min(attempt, 5))
                say(f"    {DIM}retry {attempt}/{tries} in {wait}s  "
                    f"(kept {human(got)} - resuming from there){OFF}")
                time.sleep(wait)
            else:
                say(f"    {C2}{label}: giving up after {tries} tries, {human(got)} kept for next run{OFF}")
                return False
    return False


def _verify_ok(path, sha256, quiet=True):
    """True if the file at `path` matches its known sha256."""
    if not sha256:
        return True
    have = sha256_file(path)
    return have.startswith(sha256[:16]) or have == sha256


def fix_missing(missing_files, tries=10):
    """Resume / repair every file that is missing or incomplete.

    Nothing is ever deleted: a half file continues from its last byte, and a file is only
    accepted once its size (and sha256) matches the Hugging Face repo."""
    fixable = [m for m in missing_files if m in EXPECTED]
    if not fixable:
        return missing_files
    say(f"\n{BOLD}[1c] Repairing {len(fixable)} file(s){OFF}   {DIM}"
        f"{human(sum(EXPECTED[m]['size'] for m in fixable))} to fetch, partials are resumed{OFF}")
    if "semantic_encoder.onnx" in fixable:
        say(f"  {C2}semantic_encoder.onnx is the reference-voice encoder{OFF} - a half file here "
            f"means cloning silently cannot start.")
    for name in fixable:
        spec = EXPECTED[name]
        if not download(spec["url"], local_path(name), spec["size"], spec.get("sha256"), tries=tries):
            say(f"  {C2}could not finish {name} - run the script again, it resumes{OFF}")
            break
    return check_files(verbose=False)


# ----------------------------------------------------------------- sessions
_sessions = {}
DT = {"tensor(float)": np.float32, "tensor(float16)": np.float16, "tensor(int64)": np.int64,
      "tensor(int32)": np.int32, "tensor(bool)": np.bool_, "tensor(double)": np.float64}


def S(name):
    if name in _sessions:
        return _sessions[name]
    path = MODEL / f"{name}.onnx"
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    so.intra_op_num_threads = THREADS
    so.inter_op_num_threads = 1
    so.enable_cpu_mem_arena = False
    t = time.time()
    HUD.set(f"loading {name}.onnx  ({human(_file_size(path))})")
    s = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    HUD.clear()
    say(f"    {C1}▸{OFF} {name:<30} {DIM}{human(_file_size(path)):>10}   "
        f"{time.time() - t:5.1f}s{OFF}")
    _sessions[name] = s
    return s


def _file_size(p):
    try:
        return Path(p).stat().st_size
    except Exception:
        return 0


def unload(*names):
    for n in (names or list(_sessions)):
        _sessions.pop(n, None)
    gc.collect()


def cast(info, arr):
    return np.ascontiguousarray(np.asarray(arr).astype(DT.get(info.type, np.asarray(arr).dtype)))


MODEL_NAMES = ["audio_embeddings_encoder", "llm_decoder", "audio_heads_decoder", "acoustic_encoder",
               "semantic_encoder", "quantizer_encoder", "higgs_decoder"]


def io_report():
    lines = []
    for n in MODEL_NAMES:
        if not (MODEL / f"{n}.onnx").exists():
            lines.append(f"== {n}: MISSING")
            continue
        s = S(n)
        lines.append(f"== {n}")
        ins = s.get_inputs()
        for i in ins[:6] + ([] if len(ins) <= 6 else [None]):
            lines.append("   ... (%d inputs in total)" % len(ins) if i is None else
                         f"   in  {i.name:<40} {i.type:<16} {i.shape}")
        for o in s.get_outputs()[:6]:
            lines.append(f"   out {o.name:<40} {o.type:<16} {o.shape}")
    txt = "\n".join(lines)
    OUT.mkdir(exist_ok=True)
    (OUT / "omnivoice_io_report.txt").write_text(txt, encoding="utf-8")
    return txt


# ----------------------------------------------------------------- config / tokenizer
def read_json(name):
    f = MODEL / name
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_config():
    global NUM_CODEBOOKS, MASK_ID
    found = {}

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    found.setdefault(k, v)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    for fn in ("config.json", "model_config.json", "omnivoice_manifest.json"):
        walk(read_json(fn))
    NUM_CODEBOOKS = int(found.get("num_audio_codebook", found.get("num_codebooks", NUM_CODEBOOKS)))
    MASK_ID = int(found.get("audio_mask_id", MASK_ID))


def load_tokenizer():
    from tokenizers import Tokenizer
    tk = Tokenizer.from_file(str(MODEL / "tokenizer.json"))
    for t in ("<|lang_start|>", "<|instruct_start|>", "<|text_start|>", "<|text_end|>"):
        if tk.token_to_id(t) is None:
            say(f"    {C2}note:{OFF} special token {t} not found in tokenizer.json (model may use another format)")
    return tk


# ----------------------------------------------------------------- reference voice -> codes
def load_ref_audio(path):
    w, _ = librosa.load(str(path), sr=SR, mono=True)
    w = w[: SR * MAX_REF_SECONDS]
    w = librosa.effects.trim(w, top_db=40)[0]
    if len(w) < SR:
        raise RuntimeError("Reference audio is shorter than 1 second after trimming silence.")
    pk = float(np.abs(w).max())
    if pk > 0:
        w = w / pk * 0.9
    hop = 960
    n = (len(w) // hop) * hop            # whole number of codec frames
    return w[:n].astype(np.float32)


def encode_reference(wav24):
    """Higgs: acoustic encoder (24 kHz) + semantic encoder (16 kHz) -> quantizer -> codes [8, T]."""
    HUD.set("encoding reference voice (acoustic + semantic + quantizer)")
    wav16 = librosa.resample(wav24, orig_sr=SR, target_sr=16000).astype(np.float32)
    ac, se, qu = S("acoustic_encoder"), S("semantic_encoder"), S("quantizer_encoder")
    ai = ac.get_inputs()[0]
    shape = (1, 1, -1) if len(ai.shape) == 3 else (1, -1)
    acoustic = ac.run(None, {ai.name: cast(ai, wav24.reshape(shape))})[0]
    si = se.get_inputs()[0]
    shape = (1, 1, -1) if len(si.shape) == 3 else (1, -1)
    semantic = se.run(None, {si.name: cast(si, wav16.reshape(shape))})[0]
    feeds = {}
    for i in qu.get_inputs():
        ch = i.shape[1] if len(i.shape) > 1 else None
        src = semantic if ch == 768 else acoustic
        if ch not in (768, 256):                     # unknown layout: first input = acoustic, second = semantic
            src = acoustic if i is qu.get_inputs()[0] else semantic
        feeds[i.name] = cast(i, src)
    T = min(acoustic.shape[-1], semantic.shape[-1])
    for i in qu.get_inputs():                        # make both features the same length
        feeds[i.name] = cast(i, feeds[i.name][..., :T])
    codes = qu.run(None, feeds)[0]
    codes = np.asarray(codes).astype(np.int64).reshape(NUM_CODEBOOKS, -1)
    if UNLOAD_AFTER_GENERATE:
        unload("acoustic_encoder", "semantic_encoder", "quantizer_encoder")
    HUD.clear()
    say(f"    {C1}▸{OFF} reference encoded  {DIM}{codes.shape[1]} frames = "
        f"{codes.shape[1] / FRAME_RATE:.1f}s{OFF}")
    return codes


# ----------------------------------------------------------------- backbone
def backbone(ids, amask):
    """One full backbone forward pass.

    ids    [1, 8, S] int64   text tokens | reference codes | masked generation tokens
    amask  [1, S] bool       True ONLY at the positions being generated (official behaviour)

    Returns logits [8, S, 1025].
    """
    emb = S("audio_embeddings_encoder")
    feeds = {}
    for i in emb.get_inputs():
        # the graph declares input_ids (B,8,S) and audio_mask (B,S)
        feeds[i.name] = cast(i, ids if len(i.shape) == 3 else amask)
    embeds = emb.run(None, feeds)[0].astype(np.float32)                      # [1,S,1024]

    llm = S("llm_decoder")
    L = embeds.shape[1]
    feeds = {}
    for i in llm.get_inputs():
        n = i.name.lower()
        if "embed" in n:
            feeds[i.name] = cast(i, embeds)
        elif "mask" in n:
            feeds[i.name] = cast(i, np.ones((1, L), dtype=np.int64))
        elif "position" in n:
            feeds[i.name] = cast(i, np.arange(L, dtype=np.int64)[None, :])
        elif "past" in n or "key" in n or "value" in n:
            shp = [1 if k == 0 else (d if isinstance(d, int) else 0) for k, d in enumerate(i.shape)]
            shp[2] = 0
            feeds[i.name] = np.zeros(shp, dtype=DT.get(i.type, np.float32))
        else:
            raise RuntimeError(f"unknown llm_decoder input '{i.name}' - run --probe and send "
                               f"outputs/omnivoice_io_report.txt")
    outs = llm.run(None, feeds)
    names = [o.name for o in llm.get_outputs()]
    k = next((j for j, n in enumerate(names) if "present" not in n.lower()), 0)
    hidden = outs[k].astype(np.float32)                                      # [1,S,1024]

    hd = S("audio_heads_decoder")
    hi = hd.get_inputs()[0]
    logits = hd.run(None, {hi.name: cast(hi, hidden)})[0].astype(np.float32)  # [1,8,S,1025]
    return logits[0]


def _softmax(x):
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=-1, keepdims=True)


# Official OmniVoice codebook unmasking weights (coarse codebooks matter most).
CB_WEIGHTS = np.array([8, 8, 6, 6, 4, 4, 2, 2], dtype=np.float32)
CB_WEIGHTS = CB_WEIGHTS / CB_WEIGHTS.sum()


def generate_codes(text_ids, ref_codes, target_len, rng=None, verbose=True):
    """OmniVoice iterative unmasking - faithful port of the official inference.py.

    * one backbone pass per step (no classifier-free guidance)
    * confidence = weighted mean over codebooks of the softmax probability of the best
      REAL token (MASK id 1024 excluded), deterministic
    * every step fills ceil(remaining / remaining_steps) whole frames - all 8 codebooks of
      a frame are written together, so the RVQ hierarchy is always consistent
    """
    C, T = NUM_CODEBOOKS, int(target_len)
    T_text = len(text_ids)
    if ref_codes is not None:
        ref_codes = np.asarray(ref_codes, dtype=np.int64)
        if ref_codes.ndim == 3:                 # (8,1,T) -> (8,T)
            ref_codes = ref_codes[:, 0, :]
        if ref_codes.shape[0] != C:             # (T,8) -> (8,T)
            ref_codes = ref_codes.T
    T_ref = ref_codes.shape[1] if ref_codes is not None else 0
    S_len = T_text + T_ref + T
    gen = T_text + T_ref

    ids = np.zeros((1, C, S_len), dtype=np.int64)
    ids[0, :, :T_text] = np.asarray(text_ids, dtype=np.int64)[None, :]
    if T_ref:
        ids[0, :, T_text:gen] = np.asarray(ref_codes[:, :T_ref], dtype=np.int64)
    ids[0, :, gen:] = MASK_ID
    # OFFICIAL: audio_mask is True only where we are generating
    amask = np.zeros((1, S_len), dtype=bool)
    amask[0, gen:] = True

    num_masked = T
    stats = dict(steps=0, passes=0, unsure=0)
    t0 = time.time()
    last = None
    for step in range(NUM_STEPS):
        if num_masked == 0:
            break
        logits = backbone(ids, amask)[:, gen:, :]              # [8, T, 1025]
        stats["passes"] += 1
        last = logits
        real = logits[:, :, :1024]
        prob = _softmax(real)
        max_prob = prob.max(axis=-1)                           # [8, T]
        confidence = (max_prob * CB_WEIGHTS[:, None]).sum(axis=0)   # [T]

        masked = np.where(ids[0, 0, gen:] == MASK_ID)[0]
        if masked.size == 0:
            break
        remaining_steps = max(1, NUM_STEPS - step)
        n_this = max(1, int(np.ceil(masked.size / remaining_steps)))
        order = masked[np.argsort(-confidence[masked])][:n_this]
        for pos in order:                                      # whole frame, all codebooks
            ids[0, :, gen + pos] = real[:, pos, :].argmax(axis=-1)
        num_masked -= order.size
        stats["steps"] = step + 1
        if verbose:
            frac = 1.0 - (num_masked / max(1, T))
            el = time.time() - t0
            eta = (el / frac - el) if frac > 0.02 else 0.0
            HUD.set(f"unmasking  [{bar(frac)}] {frac * 100:5.1f}%  "
                    f"step {step + 1:2d}/{NUM_STEPS}  {num_masked:4d} frames left  "
                    f"{el:4.0f}s" + (f"  eta {eta:4.0f}s" if eta else ""))

    # safety net: nothing may stay masked, the codec would receive id 1024 and blow up
    left = np.where(ids[0, 0, gen:] == MASK_ID)[0]
    if left.size:
        if last is None:
            last = backbone(ids, amask)[:, gen:, :]
        for pos in left:
            ids[0, :, gen + pos] = last[:, pos, :1024].argmax(axis=-1)
        stats["unsure"] = int(left.size)
    if verbose:
        HUD.clear()
    stats["leftover_masks"] = int((ids[0, :, gen:] == MASK_ID).sum())
    return ids[0, :, gen:], stats


def decode_codes(tokens):
    HUD.set(f"decoding waveform  {tokens.shape[1]} frames "
            f"({tokens.shape[1] / FRAME_RATE:.1f}s of audio)")
    dec = S("higgs_decoder")
    i = dec.get_inputs()[0]
    codes = tokens[:, None, :] if (len(i.shape) == 3 and i.shape[0] == NUM_CODEBOOKS) else tokens[None]
    wav = dec.run(None, {i.name: cast(i, codes)})[0].astype(np.float32).reshape(-1)
    HUD.clear()
    return wav


# ----------------------------------------------------------------- text / audio helpers
def split_text(text):
    pieces = [p.strip() for p in re.split(r"(?<=[.!?;:।])\s+|\n+", text.strip()) if p.strip()]
    segs, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 1 + len(p) > MAX_CHARS_PER_PART:
            segs.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        segs.append(cur)
    if len(segs) > 1 and len(segs[-1]) < 25:
        segs[-2] += " " + segs.pop()
    return segs


def active_rms(w):
    env = np.abs(w)
    m = env > env.max() * 0.1 if env.size else env
    return float(np.sqrt((w[m] ** 2).mean())) if env.size and m.any() else 1e-6


def stitch(wavs, target_rms):
    out, fade = [], int(0.015 * SR)
    for w in wavs:
        w = librosa.effects.trim(w, top_db=35)[0]
        w = w * min(3.0, max(0.3, target_rms / active_rms(w)))
        if len(w) > 2 * fade:
            w[:fade] *= np.linspace(0, 1, fade)
            w[-fade:] *= np.linspace(1, 0, fade)
        out += [w.astype(np.float32), np.zeros(int(PAUSE_SEC * SR), dtype=np.float32)]
    wav = np.concatenate(out[:-1])
    return wav * min(1.0, 0.95 / max(1e-6, float(np.abs(wav).max())))


def build_text_ids(tok, lang_name, ref_text, text):
    """Prompt tokens.

    template : <|lang_start|>English<|lang_end|><|instruct_start|>None<|instruct_end|>
               <|text_start|>{reference transcript}{text}<|text_end|>
               (the reference transcript is what makes the model align the reference codes
                with their words - this is the voice-cloning prompt format)
    plain    : the raw text, like the reference inference.py of the ONNX repo
    """
    ref_text = (ref_text or "").strip()
    if PROMPT_STYLE == "plain":
        full = (ref_text + " " + text.strip()).strip() if ref_text else text.strip()
        ids = tok.encode(full, add_special_tokens=True).ids
        if isinstance(ids, list) and ids and isinstance(ids[0], list):
            ids = ids[0]
        return ids
    style = f"<|lang_start|>{lang_name}<|lang_end|><|instruct_start|>None<|instruct_end|>"
    full = (ref_text + " " + text.strip()).strip() if ref_text else text.strip()
    return tok.encode(f"{style}<|text_start|>{full}<|text_end|>", add_special_tokens=False).ids


def estimate_frames(part, ref_codes, ref_text):
    """How many 25 fps frames to generate for this part."""
    if LENGTH_MODE == "fixed":
        return int(LENGTH_FRAMES)
    rate = None
    if LENGTH_MODE == "rate" and ref_codes is not None and ref_text:
        ref = np.asarray(ref_codes)
        ref_frames = int(ref.shape[0] if ref.ndim == 2 and ref.shape[0] != NUM_CODEBOOKS
                         else ref.shape[-1] if ref.ndim >= 2 else 0)
        ref_chars = max(1, len(ref_text.strip()))
        rate = int(round(ref_frames * (len(part) / ref_chars))) if ref_frames else None
    chars = int(round(FRAME_RATE * len(part) / 13.0))          # ~13 chars per second fallback
    # a hard floor: speech cannot be faster than ~22 characters per second.  Without this a
    # wrong reference transcript (or a too-short reference) makes the model cram the whole
    # sentence into a couple of seconds, which comes out as warbling/pitched-up garbage.
    floor = int(math.ceil(len(part) / 22.0 * FRAME_RATE))
    if rate is None:
        T = chars
    elif not (0.5 <= rate / max(1, chars) <= 2.0):
        say(f"    {C2}note:{OFF} the reference rate suggests {rate / FRAME_RATE:.1f}s but the text "
            f"length suggests {chars / FRAME_RATE:.1f}s - using the text length "
            f"(check that the reference transcript really matches the audio)")
        T = chars
    else:
        T = rate
    if T < floor:
        say(f"    {C2}note:{OFF} {T / FRAME_RATE:.1f}s is too short for {len(part)} characters "
            f"(>22 chars/s = rushed) - raised to {floor / FRAME_RATE:.1f}s")
        T = floor
    return int(np.clip(T, 20, FRAME_RATE * 30))


def synthesize(text, lang_name, ref_wav, ref_text):
    tok = load_tokenizer()
    say(f"\n{BOLD}[4] Cloning{OFF}")
    ref_codes = encode_reference(ref_wav)
    if ref_codes.ndim == 3:
        ref_codes = ref_codes[:, 0, :]
    target_rms = min(0.15, max(0.03, active_rms(ref_wav)))
    parts = split_text(text)
    wavs, stats_all = [], []
    for n, part in enumerate(parts, 1):
        say(f"  part {n}/{len(parts)}: {part[:70]}{'...' if len(part) > 70 else ''}")
        T = estimate_frames(part, ref_codes, ref_text)
        say(f"    target length {T} frames = {T / FRAME_RATE:.1f}s")
        ids = build_text_ids(tok, lang_name, ref_text, part)
        say(f"    prompt tokens: {len(ids)}")
        tokens, stats = generate_codes(ids, ref_codes, T)
        wav = decode_codes(tokens)
        if DIAG:
            u, c = np.unique(tokens, return_counts=True)
            top = np.argsort(-c)[:5]
            say(f"    codes: {tokens.shape}  range [{tokens.min()}, {tokens.max()}]  "
                f"top ids {[(int(u[i]), int(c[i])) for i in top]}")
            say(f"    decoding: {stats['steps']} steps, {stats['passes']} backbone passes, "
                f"{stats['leftover_masks']} leftover masks")
        if tokens.max() >= MASK_ID:
            say(f"    {C2}[!] MASK token still present - the codec will be fed id 1024{OFF}")
        wavs.append(wav)
        stats_all.append(stats)
    if UNLOAD_AFTER_GENERATE:
        unload()
    return stitch(wavs, target_rms)


# ----------------------------------------------------------------- menu helpers
def clean_path(p):
    return p.strip().strip('"').strip("'").strip()


def choose_language():
    say(f"\n{BOLD}[2] Language{OFF}")
    for k, (name, _) in LANGUAGES.items():
        say(f"    {C3}{k}{OFF}  {name}")
    while True:
        try:
            v = input("  Select language (1 or 2): ").strip()
        except EOFError:
            sys.exit(0)
        if v in LANGUAGES:
            return LANGUAGES[v][0]
        say("    please type 1 or 2")


def ask_reference():
    say(f"\n{BOLD}[3] Reference voice{OFF}")
    say(f"    {DIM}3 to 12 seconds of clean speech, wav / mp3 / flac / m4a. You can drag the file into this window.{OFF}")
    while True:
        try:
            p = clean_path(input("  Path to reference sample: "))
        except EOFError:
            sys.exit(0)
        if p and Path(p).is_file():
            break
        say("    file not found, try again")
    say(f"    {DIM}Type exactly what is said in the sample (same language, Hindi in देवनागरी).{OFF}")
    while True:
        try:
            t = input("  Transcript of the reference: ").strip()
        except EOFError:
            sys.exit(0)
        if t:
            return Path(p), t
        say("    the transcript is needed for cloning")


def roundtrip(path, out=None):
    """Encode + decode the reference audio through Higgs only.

    This isolates the tokenizer from the LLM: if the round-trip sounds clean, the four
    Higgs files and their wiring are fine and any noise is coming from the unmasking loop;
    if the round-trip is noisy/buzzy, the tokenizer itself is the problem.
    """
    require_libs(["onnxruntime", "soundfile", "librosa"])
    wav = load_ref_audio(path)
    codes = encode_reference(wav)
    if codes.ndim == 3:
        codes = codes[:, 0, :]
    wav2 = decode_codes(codes)
    o = Path(out) if out else (OUT / f"roundtrip_{Path(path).stem}.wav")
    OUT.mkdir(exist_ok=True)
    n = min(wav.size, wav2.size)
    a, b = wav[:n], wav2[:n]
    err = float(np.abs(a - b).mean())
    corr = float(np.corrcoef(a, b)[0, 1]) if n > 100 else float("nan")
    say(f"\n  reference   : {wav.size / SR:.2f}s   peak {20 * np.log10(max(float(np.abs(wav).max()), 1e-9)):+.1f} dBFS")
    say(f"  round-trip  : {wav2.size / SR:.2f}s   peak {20 * np.log10(max(float(np.abs(wav2).max()), 1e-9)):+.1f} dBFS")
    say(f"  correlation {corr:.3f}   mean |error| {err:.4f}")
    sf.write(str(o), wav2, SR)
    say(f"  saved {o}")
    say(f"  {C1}listened verdict{OFF}: a good zero-shot tokenizer gives corr > 0.9 and clean speech.")
    return corr


def analyze_wav(path):
    """Objective quality report of a generated wav (noise, level, pitch stability)."""
    require_libs(["soundfile"])
    w, sr = sf.read(str(path))
    if w.ndim > 1:
        w = w.mean(axis=1)
    w = w.astype(np.float32)
    say(f"\n  {Path(path).name}: {w.size / sr:.2f}s  {sr} Hz")
    say(f"    peak {20 * np.log10(max(float(np.abs(w).max()), 1e-9)):+.1f} dBFS   "
        f"rms {20 * np.log10(max(float(np.sqrt((w ** 2).mean())), 1e-9)):+.1f} dBFS")
    # high-frequency energy = hiss / codec garbage
    S = np.abs(np.fft.rfft(w * np.hanning(w.size)))
    fr = np.fft.rfftfreq(w.size, 1 / sr)
    tot = float((S ** 2).sum()) + 1e-12
    hiss = float((S[(fr >= 6000) & (fr < 11000)] ** 2).sum()) / tot
    say(f"    high-band energy 6-11 kHz: {100 * hiss:.1f}%   "
        f"{C1}(good: < 1%){OFF}" if hiss < 0.01 else
        f"    high-band energy 6-11 kHz: {100 * hiss:.1f}%   {C2}(too much: {100 * hiss:.1f}%){OFF}")
    # pitch stability
    f0 = []
    hop, win = int(0.010 * sr), int(0.040 * sr)
    for i in range(0, max(0, w.size - win), hop):
        seg = w[i:i + win].astype(np.float64)
        seg -= seg.mean()
        if np.sqrt((seg ** 2).mean()) < 1e-3:
            continue
        ac = np.correlate(seg, seg, "full")[win - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        seg_ac = ac[lo:hi]
        if seg_ac.size == 0:
            continue
        lag = lo + int(np.argmax(seg_ac))
        if ac[lag] > 0.35 * ac[0]:
            f0.append(sr / lag)
    if len(f0) > 20:
        f0 = np.array(f0)
        say(f"    pitch: median {np.median(f0):.0f} Hz  spread {np.percentile(f0, 90) - np.percentile(f0, 10):.0f} Hz  "
            f"frame jitter {np.median(np.abs(np.diff(f0))):.1f} Hz/10ms")
    say(f"    {DIM}healthy speech: high band < 1%   ·   frame jitter < 3 Hz/10 ms"
        f"   ·   pitch spread < 60 Hz{OFF}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roundtrip", default=None, metavar="WAV",
                    help="encode+decode a reference wav through Higgs only (tokenizer sanity check)")
    ap.add_argument("--analyze", default=None, metavar="WAV", help="quality report of a wav")
    ap.add_argument("--no-anim", action="store_true",
                    help="disable the animated banner/HUD (also: set NO_ANIM=1)")
    ap.add_argument("--check", action="store_true", help="quick integrity check of the model files")
    ap.add_argument("--verify", action="store_true", help="deep check: sha256 of every model file")
    ap.add_argument("--fix", action="store_true", help="check + resume/repair downloads, then stop")
    ap.add_argument("--no-fix", action="store_true", help="never download anything automatically")
    ap.add_argument("--offline", action="store_true", help="skip the remote size check")
    ap.add_argument("--probe", action="store_true", help="write the model input/output report")
    ap.add_argument("--text", default=None)
    a = ap.parse_args()

    global ANIM
    if a.no_anim:
        ANIM = False
    HUD.start()
    anim_banner()
    say(f"{DIM}onnxruntime {ort.__version__ if ort else 'not installed'} · threads {THREADS} "
        f"· folder {MODEL}{OFF}")
    OUT.mkdir(exist_ok=True)
    load_config()

    if a.analyze:
        analyze_wav(a.analyze)
        return

    if a.roundtrip:
        roundtrip(a.roundtrip)
        return

    if a.verify:
        bad = [m for m in check_files(verbose=False)] or []
        bad += [m for m in verify_files(deep=True) if m not in bad]
        say(f"\n  {C1}✓ every file verified (size + sha256){OFF}" if not bad else
            f"\n  {C2}[!] {len(bad)} file(s) failed verification: {', '.join(bad)}{OFF}\n"
            f"    run again with --fix to re-fetch them.")
        return

    miss = check_files(live=not a.offline)
    if a.check:
        if miss:
            say(f"\n  {C3}[!] {len(miss)} file(s) missing or incomplete: {', '.join(miss)}{OFF}")
            for m in miss:
                st, detail = file_problem(m)
                say(f"      {m}: {st}  {detail}")
            say(f"    run  python {Path(sys.argv[0]).name} --fix   to resume/repair them")
        else:
            say(f"\n  {C1}✓ all files needed for voice cloning are present and complete{OFF}")
        return
    if miss and not a.no_fix:
        miss = fix_missing(miss)
    if miss:
        say(f"\n{C2}[!] Still missing or incomplete: {', '.join(miss)}{OFF}")
        say("    Partial files are resumed from where they stopped - just run again\n"
            "    (network dropouts are safe now; nothing already downloaded is thrown away).")
        sys.exit(1)
    say(f"\n  {C1}✓ all files needed for voice cloning are present and complete{OFF}")
    if a.fix:
        return
    if a.probe:
        say(io_report())
        say(f"\n  saved {OUT / 'omnivoice_io_report.txt'}")
        return

    lang = choose_language()
    ref_path, ref_text = ask_reference()
    ref_wav = load_ref_audio(ref_path)
    say(f"    reference loaded: {len(ref_wav) / SR:.1f}s")

    texts = [a.text] if a.text else None
    while True:
        if texts is not None:
            if not texts:
                break
            text = texts.pop(0)
        else:
            try:
                text = input(f"\n{BOLD}Type the {lang} text to speak{OFF} (empty = quit):\n> ").strip()
            except EOFError:
                break
            if not text:
                break
        t0 = time.time()
        try:
            wav = synthesize(text, lang, ref_wav, ref_text)
        except Exception as e:
            say(f"\n{C2}[!] Generation failed: {e!r}{OFF}")
            try:
                unload()
                io_report()
            except Exception:
                pass
            say("    Send me outputs/omnivoice_io_report.txt, omnivoice_manifest.json and higgs_inference.py.")
            sys.exit(2)
        out = OUT / f"omnivoice_{time.strftime('%Y%m%d_%H%M%S')}.wav"
        sf.write(str(out), wav, SR)
        HUD.stop()
        say(f"\n  {C1}✓{OFF} saved {out}   {DIM}({len(wav) / SR:.1f}s audio, "
            f"{time.time() - t0:.0f}s to generate){OFF}")


if __name__ == "__main__":
    main()
