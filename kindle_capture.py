#!/usr/bin/env python3
"""
kindle_capture.py — Kindle automatic page capture with OCR and PDF generation.

Usage:
    python3 kindle_capture.py                    — Capture pages from Kindle
    python3 kindle_capture.py --pages 50         — Capture up to 50 pages
    python3 kindle_capture.py --ocr-only <dir>   — OCR existing screenshots
    python3 kindle_capture.py --pdf-only <dir>   — Generate PDF from screenshots
"""

import argparse
import atexit
import hashlib
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
OCR_HELPER = SCRIPT_DIR / "ocr_helper"
PID_LOCK = Path(tempfile.gettempdir()) / "kindle_capture.pid"

KINDLE_BUNDLE_ID = "com.amazon.Kindle"
KINDLE_PROCESS_NAME = "Kindle"

# Screenshot settings
CAPTURE_DELAY = 0.8          # seconds between screenshot and OCR
PAGE_TURN_DELAY = 1.0        # seconds after sending arrow key
FOCUS_REACTIVATE_INTERVAL = 50  # re-activate Kindle every N pages

# End detection
MAX_SAME_PAGE_COUNT = 3       # stop after N consecutive identical screenshots
END_MARKERS = [
    "amazonでこの本をレビュー",
    "amazon でこの本をレビュー",
    "review this book on amazon",
]

# Window bounds minimum (exclude dialogs)
MIN_WINDOW_WIDTH = 400
MIN_WINDOW_HEIGHT = 300

# PDF chunk size
PDF_CHUNK_SIZE = 25


# ---------------------------------------------------------------------------
# PID Lock (atomic creation, stale recovery)
# ---------------------------------------------------------------------------

def acquire_pid_lock():
    """Acquire PID lock file. Removes stale locks automatically."""
    pid = os.getpid()

    if PID_LOCK.exists():
        try:
            old_pid = int(PID_LOCK.read_text().strip())
            # Check if process is still alive
            try:
                os.kill(old_pid, 0)
                print(f"Error: Another instance is running (PID {old_pid}).")
                print(f"If this is stale, remove: {PID_LOCK}")
                sys.exit(1)
            except OSError:
                # Process is dead — stale lock
                print(f"Removing stale PID lock (was PID {old_pid}).")
                PID_LOCK.unlink(missing_ok=True)
        except (ValueError, IOError):
            PID_LOCK.unlink(missing_ok=True)

    # Atomic create using O_EXCL
    try:
        fd = os.open(str(PID_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, str(pid).encode())
        os.close(fd)
    except FileExistsError:
        print("Error: Could not acquire PID lock (race condition).")
        sys.exit(1)


def release_pid_lock():
    """Remove PID lock file."""
    try:
        if PID_LOCK.exists():
            stored_pid = int(PID_LOCK.read_text().strip())
            if stored_pid == os.getpid():
                PID_LOCK.unlink(missing_ok=True)
    except (ValueError, IOError):
        PID_LOCK.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AppleScript helpers
# ---------------------------------------------------------------------------

def run_applescript(script: str) -> str:
    """Run AppleScript and return stdout. Raises on failure."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript failed: {result.stderr.strip()}")
    return result.stdout.strip()


def is_kindle_running() -> bool:
    """Check if Kindle process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", KINDLE_PROCESS_NAME],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def is_kindle_frontmost() -> bool:
    """Check if Kindle is the frontmost application."""
    try:
        script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
            end tell
            return frontApp
        '''
        front = run_applescript(script)
        return front == KINDLE_PROCESS_NAME
    except (RuntimeError, subprocess.TimeoutExpired):
        return False


def activate_kindle() -> bool:
    """Bring Kindle to front. Returns True if successful."""
    try:
        script = f'''
            tell application "{KINDLE_PROCESS_NAME}"
                activate
            end tell
            delay 0.5
        '''
        run_applescript(script)
        time.sleep(0.5)
        return is_kindle_frontmost()
    except (RuntimeError, subprocess.TimeoutExpired):
        return False


def maximize_kindle_window():
    """Maximize Kindle window using set size (fullscreen not used because
    window 1 reference disappears in fullscreen mode)."""
    try:
        script = f'''
            tell application "System Events"
                tell process "{KINDLE_PROCESS_NAME}"
                    if exists window 1 then
                        set position of window 1 to {{0, 0}}
                        set size of window 1 to {{9999, 9999}}
                    end if
                end tell
            end tell
        '''
        run_applescript(script)
        time.sleep(0.3)
    except (RuntimeError, subprocess.TimeoutExpired):
        print("Warning: Could not maximize Kindle window.")


def get_kindle_window_bounds() -> tuple[int, int, int, int] | None:
    """Get Kindle window bounds as (x, y, width, height).
    Returns None if window not found or too small (dialog)."""
    try:
        script = f'''
            tell application "System Events"
                tell process "{KINDLE_PROCESS_NAME}"
                    if exists window 1 then
                        set {{x, y}} to position of window 1
                        set {{w, h}} to size of window 1
                        return (x as text) & "," & (y as text) & "," & (w as text) & "," & (h as text)
                    end if
                end tell
            end tell
            return ""
        '''
        result = run_applescript(script)
        if not result:
            return None
        parts = [int(p) for p in result.split(",")]
        x, y, w, h = parts[0], parts[1], parts[2], parts[3]
        if w < MIN_WINDOW_WIDTH or h < MIN_WINDOW_HEIGHT:
            return None  # Probably a dialog
        return (x, y, w, h)
    except (RuntimeError, subprocess.TimeoutExpired, ValueError):
        return None


def send_right_arrow():
    """Send right arrow key to advance page."""
    script = '''
        tell application "System Events"
            key code 124
        end tell
    '''
    run_applescript(script)


def ensure_kindle_focus() -> bool:
    """Ensure Kindle is frontmost. Try activate if not. Returns False if failed."""
    if is_kindle_frontmost():
        return True
    print("  Kindle lost focus, re-activating...")
    if activate_kindle():
        return True
    print("  ERROR: Cannot bring Kindle to front.")
    return False


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

def take_screenshot(output_path: str, bounds: tuple[int, int, int, int]) -> bool:
    """Take a screenshot of the specified region. Uses screencapture -x -o -R
    which does not steal focus."""
    x, y, w, h = bounds
    region = f"{x},{y},{w},{h}"
    try:
        result = subprocess.run(
            ["screencapture", "-x", "-o", "-R", region, output_path],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0 and os.path.exists(output_path)
    except subprocess.TimeoutExpired:
        return False


def image_hash(path: str) -> str:
    """Compute SHA-256 hash of an image file for duplicate detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def run_ocr(image_path: str) -> str:
    """Run OCR on an image using ocr_helper binary. Returns extracted text."""
    if not OCR_HELPER.exists():
        print(f"Error: OCR helper not found at {OCR_HELPER}")
        print("Run setup.sh first to compile it.")
        sys.exit(1)

    try:
        result = subprocess.run(
            [str(OCR_HELPER), image_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                print(f"  OCR warning: {stderr}")
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("  OCR timeout.")
        return ""


def check_end_marker(ocr_text: str) -> bool:
    """Check if OCR text contains an end-of-book marker."""
    lower = ocr_text.lower()
    return any(marker in lower for marker in END_MARKERS)


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_pdf(output_path: str, image_paths: list[str]) -> bool:
    """Generate PDF from images using ocr_helper --pdf."""
    if not OCR_HELPER.exists():
        print(f"Error: OCR helper not found at {OCR_HELPER}")
        return False

    if not image_paths:
        print("No images to create PDF from.")
        return False

    try:
        cmd = [str(OCR_HELPER), "--pdf", output_path] + image_paths
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"PDF generation failed: {result.stderr.strip()}")
            return False
        print(result.stdout.strip())
        return True
    except subprocess.TimeoutExpired:
        print("PDF generation timed out.")
        return False


# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

def create_output_dir() -> Path:
    """Create timestamped output directory."""
    base = Path.home() / "Documents" / "kindle_capture" / "captures"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# ---------------------------------------------------------------------------
# OCR-only mode
# ---------------------------------------------------------------------------

def ocr_only_mode(folder: str):
    """Run OCR on all images in a folder. Writes result atomically."""
    folder_path = Path(folder)
    if not folder_path.is_dir():
        print(f"Error: Not a directory: {folder}")
        sys.exit(1)

    images = sorted(
        p for p in folder_path.iterdir()
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".tiff", ".bmp")
    )
    if not images:
        print(f"No images found in {folder}")
        sys.exit(1)

    print(f"OCR processing {len(images)} images from {folder}")
    output_file = folder_path / "ocr_text.txt"

    # Write to temp file, then atomic replace
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(folder_path), prefix=".ocr_tmp_", suffix=".txt"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for i, img in enumerate(images, 1):
                print(f"  [{i}/{len(images)}] {img.name}")
                text = run_ocr(str(img))
                f.write(f"--- {img.name} ---\n")
                f.write(text + "\n\n")

        os.replace(tmp_path, str(output_file))
        print(f"OCR output: {output_file}")
    except Exception:
        os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# PDF-only mode
# ---------------------------------------------------------------------------

def pdf_only_mode(folder: str):
    """Generate PDF from screenshots in a folder."""
    folder_path = Path(folder)
    if not folder_path.is_dir():
        print(f"Error: Not a directory: {folder}")
        sys.exit(1)

    images = sorted(
        str(p) for p in folder_path.iterdir()
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".tiff", ".bmp")
    )
    if not images:
        print(f"No images found in {folder}")
        sys.exit(1)

    output_pdf = folder_path / "book.pdf"
    print(f"Generating PDF from {len(images)} images...")
    generate_pdf(str(output_pdf), images)


# ---------------------------------------------------------------------------
# Main capture loop
# ---------------------------------------------------------------------------

def capture_loop(max_pages: int | None = None):
    """Main capture loop: screenshot → duplicate check → OCR → page turn."""

    # Pre-flight checks
    if not is_kindle_running():
        print("Error: Kindle is not running. Please open Kindle first.")
        sys.exit(1)

    # Acquire lock
    acquire_pid_lock()
    atexit.register(release_pid_lock)

    # Activate and maximize
    print("Activating Kindle...")
    if not activate_kindle():
        print("Error: Cannot activate Kindle.")
        sys.exit(1)

    maximize_kindle_window()

    bounds = get_kindle_window_bounds()
    if bounds is None:
        print("Error: Cannot determine Kindle window bounds.")
        sys.exit(1)

    print(f"Window bounds: x={bounds[0]}, y={bounds[1]}, "
          f"w={bounds[2]}, h={bounds[3]}")

    # Create output directory
    output_dir = create_output_dir()
    ocr_file = output_dir / "ocr_text.txt"
    print(f"Output: {output_dir}")

    page_count = 0
    same_page_streak = 0
    prev_hash = None
    stopped = False

    def signal_handler(sig, frame):
        nonlocal stopped
        print("\n\nCtrl+C detected. Stopping after current page...")
        stopped = True

    signal.signal(signal.SIGINT, signal_handler)

    print(f"Starting capture (max pages: {max_pages or 'unlimited'})...")
    print("Press Ctrl+C to stop.\n")

    while not stopped:
        if max_pages is not None and page_count >= max_pages:
            print(f"\nReached page limit ({max_pages}).")
            break

        page_num = page_count + 1

        # Periodic focus re-activation
        if page_count > 0 and page_count % FOCUS_REACTIVATE_INTERVAL == 0:
            if not ensure_kindle_focus():
                print("Stopping: Cannot maintain Kindle focus.")
                break

        # Verify Kindle is still focused before page turn
        if page_count > 0:
            if not ensure_kindle_focus():
                print("Stopping: Kindle lost focus.")
                break

        # Take screenshot
        screenshot_path = str(output_dir / f"page_{page_num:04d}.png")
        if not take_screenshot(screenshot_path, bounds):
            print(f"  Warning: Screenshot failed for page {page_num}, retrying...")
            time.sleep(0.5)
            if not take_screenshot(screenshot_path, bounds):
                print(f"  Error: Screenshot failed twice for page {page_num}.")
                break

        time.sleep(CAPTURE_DELAY)

        # Duplicate detection
        current_hash = image_hash(screenshot_path)
        if current_hash == prev_hash:
            same_page_streak += 1
            print(f"  Page {page_num}: same as previous "
                  f"({same_page_streak}/{MAX_SAME_PAGE_COUNT})")
            # Remove duplicate screenshot
            os.unlink(screenshot_path)
            if same_page_streak >= MAX_SAME_PAGE_COUNT:
                print(f"\n{MAX_SAME_PAGE_COUNT} consecutive identical pages. "
                      f"End of book detected.")
                break
            # Try turning page anyway
            send_right_arrow()
            time.sleep(PAGE_TURN_DELAY)
            continue
        else:
            same_page_streak = 0
            prev_hash = current_hash

        # OCR
        ocr_text = run_ocr(screenshot_path)
        print(f"  Page {page_num}: captured "
              f"({len(ocr_text)} chars OCR)")

        # Append OCR text to file
        with open(ocr_file, "a", encoding="utf-8") as f:
            f.write(f"--- page_{page_num:04d}.png ---\n")
            f.write(ocr_text + "\n\n")

        # End-of-book detection
        if check_end_marker(ocr_text):
            print(f"\nEnd-of-book marker detected on page {page_num}.")
            page_count += 1
            break

        page_count += 1

        # Turn page
        send_right_arrow()
        time.sleep(PAGE_TURN_DELAY)

    # Summary
    print(f"\n{'='*50}")
    print(f"Capture complete: {page_count} pages")
    print(f"Screenshots: {output_dir}")
    print(f"OCR text:    {ocr_file}")

    # Generate PDF
    images = sorted(
        str(p) for p in output_dir.iterdir()
        if p.suffix == ".png"
    )
    if images:
        pdf_path = str(output_dir / "book.pdf")
        print(f"\nGenerating PDF...")
        generate_pdf(pdf_path, images)

    return page_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Kindle automatic page capture with OCR and PDF generation."
    )
    parser.add_argument(
        "--pages", type=int, default=None,
        help="Maximum number of pages to capture.",
    )
    parser.add_argument(
        "--ocr-only", metavar="FOLDER", default=None,
        help="Run OCR on existing screenshots in FOLDER.",
    )
    parser.add_argument(
        "--pdf-only", metavar="FOLDER", default=None,
        help="Generate PDF from screenshots in FOLDER.",
    )

    args = parser.parse_args()

    if args.ocr_only:
        ocr_only_mode(args.ocr_only)
    elif args.pdf_only:
        pdf_only_mode(args.pdf_only)
    else:
        capture_loop(max_pages=args.pages)


if __name__ == "__main__":
    main()
