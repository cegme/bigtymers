#!/usr/bin/env python3
"""BigTymers: a full screen analog and digital clock and countdown timer for the terminal.

Run it without downloading anything:

    curl -fsSL https://ceg.me/bigtymers/bigtymers.py | python3 - 45m

Keys are read from /dev/tty, so piping the script into python3 works.
Only the Python standard library is used.
"""

import argparse
import math
import os
import re
import select
import shutil
import subprocess
import sys
import termios
import time
import tty
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

RESET = "\x1b[0m"
COLORS = {
    "dim": "\x1b[90m",
    "white": "\x1b[97m",
    "red": "\x1b[91m",
    "green": "\x1b[92m",
    "yellow": "\x1b[93m",
    "cyan": "\x1b[96m",
}
ENTER_SCREEN = "\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J"
LEAVE_SCREEN = "\x1b[?7h\x1b[?25h\x1b[?1049l"
FLASH_BG = "\x1b[41;97m"

FONT = {
    "0": ["###", "# #", "# #", "# #", "###"],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["###", "  #", "###", "#  ", "###"],
    "3": ["###", "  #", "###", "  #", "###"],
    "4": ["# #", "# #", "###", "  #", "  #"],
    "5": ["###", "#  ", "###", "  #", "###"],
    "6": ["###", "#  ", "###", "# #", "###"],
    "7": ["###", "  #", "  #", "  #", "  #"],
    "8": ["###", "# #", "###", "# #", "###"],
    "9": ["###", "# #", "###", "  #", "###"],
    ":": [" ", "#", " ", "#", " "],
    " ": ["   ", "   ", "   ", "   ", "   "],
    "A": [" # ", "# #", "###", "# #", "# #"],
    "P": ["###", "# #", "###", "#  ", "#  "],
    "M": ["# #", "###", "###", "# #", "# #"],
}
FACES = ["both", "analog", "digital"]
HELP = (
    " space start/pause  v clock/timer  a face  +/- minutes  up/down 5 min"
    "  r reset  h 12/24h  s seconds  z zone  d details  m mute  q quit"
)


def parse_duration(text):
    """Parses a duration string into seconds.

    Accepts 45 (minutes), 45m, 90s, 1h30m, 1h30 (30 minutes), mm:ss and hh:mm:ss.

    Args:
        text: The duration text.

    Returns:
        The duration in seconds.

    Raises:
        ValueError: If the text is not a valid positive duration.
    """
    s = text.strip().lower()
    if ":" in s:
        parts = [float(p) if p else 0.0 for p in s.split(":")]
        if len(parts) > 3:
            raise ValueError(f"bad duration: {text}")
        while len(parts) < 3:
            parts.insert(0, 0.0)
        total = parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif re.fullmatch(r"(\s*\d+(\.\d+)?\s*[hms]?)+", s):
        scale = {"h": 3600, "m": 60, "s": 1, "": 60}
        total = sum(
            float(n) * scale[u]
            for n, u in re.findall(r"(\d+(?:\.\d+)?)\s*([hms]?)", s)
        )
    else:
        raise ValueError(f"bad duration: {text}")
    if total <= 0:
        raise ValueError(f"duration must be positive: {text}")
    return total


def format_hms(seconds, with_hours):
    """Formats whole seconds as H:MM:SS or MM:SS.

    Args:
        seconds: Seconds to format.
        with_hours: Whether to include an hours field.

    Returns:
        The formatted string.
    """
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if with_hours:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{h * 60 + m:02d}:{s:02d}"


def level(remaining, duration):
    """Returns a color name for the time left.

    Args:
        remaining: Seconds left.
        duration: Total seconds.

    Returns:
        One of green, yellow or red.
    """
    if remaining <= min(300, duration * 0.1):
        return "red"
    if remaining <= min(900, duration * 0.25):
        return "yellow"
    return "green"


class State:
    """Timer and display state."""

    def __init__(self, duration, view, face, twelve, bell, zones=None, seconds=True, details=False, sound=None):
        """Creates the state.

        Args:
            duration: Timer length in seconds.
            view: Either clock or timer.
            face: One of both, analog or digital.
            twelve: Whether the clock uses 12 hour time.
            bell: Whether the alarm makes a sound.
            zones: Time zone names to cycle through, where None is local time.
            seconds: Whether the clock shows seconds.
            details: Whether the header and help lines are shown.
            sound: Path of an audio file to play for the alarm instead of the bell.
        """
        self.duration = float(duration)
        self.left = float(duration)
        self.end = 0.0
        self.running = False
        self.alarm = False
        self.view = view
        self.face = face
        self.twelve = twelve
        self.bell = bell
        self.zones = zones or [None]
        self.zone_i = 0
        self.seconds = seconds
        self.details = details
        self.sound = sound

    def remaining(self):
        """Returns the seconds left on the timer."""
        if self.running:
            return max(0.0, self.end - time.monotonic())
        return self.left

    def start(self):
        """Starts the timer, restarting from the full duration when it is at zero."""
        if self.left <= 0:
            self.left = self.duration
        self.end = time.monotonic() + self.left
        self.running = True
        self.alarm = False

    def pause(self):
        """Pauses the timer."""
        self.left = self.remaining()
        self.running = False

    def reset(self):
        """Resets the timer to its full duration."""
        self.left = self.duration
        self.running = False
        self.alarm = False

    def adjust(self, delta):
        """Adds or removes time from the timer and its duration.

        Args:
            delta: Seconds to add (negative to remove).
        """
        self.duration = max(1.0, self.duration + delta)
        if self.running:
            self.end += delta
        else:
            self.left = min(self.duration, max(0.0, self.left + delta))

    def tick(self):
        """Raises the alarm when a running timer reaches zero."""
        if self.running and self.remaining() <= 0:
            self.running = False
            self.left = 0.0
            self.alarm = True
            self.view = "timer"


class Grid:
    """A character grid with per-cell colors."""

    def __init__(self, w, h):
        """Creates an empty grid.

        Args:
            w: Width in columns.
            h: Height in rows.
        """
        self.w = w
        self.h = h
        self.cells = [[(" ", None)] * w for _ in range(h)]

    def put(self, x, y, ch, color=None):
        """Sets one cell if it is inside the grid."""
        if 0 <= x < self.w and 0 <= y < self.h:
            self.cells[y][x] = (ch, color)

    def text(self, x, y, s, color=None):
        """Writes a string starting at x, y."""
        for i, ch in enumerate(s):
            self.put(x + i, y, ch, color)

    def lines(self):
        """Returns the rows as strings, merging runs of one color."""
        out = []
        for row in self.cells:
            parts = []
            cur = object()
            for ch, color in row:
                if color != cur:
                    parts.append(RESET + COLORS[color] if color else RESET)
                    cur = color
                parts.append(ch)
            parts.append(RESET)
            out.append("".join(parts))
        return out


def text_units(text):
    """Returns the glyph width of text in font units including gaps."""
    return sum(len(FONT[c][0]) for c in text) + len(text) - 1


def big_text(text, w, h, color):
    """Draws text in large block digits.

    Args:
        text: Characters from 0-9, colon and space.
        w: Available width in columns.
        h: Available height in rows.
        color: A key of COLORS.

    Returns:
        A list of h strings, each w columns wide when printed.
    """
    units = text_units(text)
    blank = " " * w
    sy = min(h // 5, w // (2 * units))
    if sy >= 1:
        sx = 2 * sy
    elif w >= units and h >= 5:
        sx = sy = 1
    else:
        lines = [blank] * h
        if h:
            lines[h // 2] = text.center(w)[:w]
        return lines
    rows = []
    for r in range(5):
        parts = []
        for c in text:
            parts.append("".join(("█" if g == "#" else " ") * sx for g in FONT[c][r]))
        rows.extend([(" " * sx).join(parts)] * sy)
    width = units * sx
    left = (w - width) // 2
    lines = [
        " " * left + COLORS[color] + row + RESET + " " * (w - left - width)
        for row in rows
    ]
    top = (h - len(lines)) // 2
    return [blank] * top + lines + [blank] * (h - top - len(lines))


def analog(w, h, st, now, rem):
    """Draws an analog face.

    Args:
        w: Width in columns.
        h: Height in rows.
        st: The State.
        now: The current datetime.
        rem: Seconds left on the timer.

    Returns:
        A list of h strings.
    """
    g = Grid(w, h)
    ry = min((h - 1) // 2, (w - 1) // 4)
    if ry < 3:
        return g.lines()
    rx = 2 * ry
    cx, cy = w // 2, h // 2

    def pos(deg, f):
        a = math.radians(deg)
        return cx + round(math.sin(a) * rx * f), cy - round(math.cos(a) * ry * f)

    def hand(deg, f, ch, color):
        n = 2 * rx
        for s in range(n + 1):
            x, y = pos(deg, f * s / n)
            g.put(x, y, ch, color)

    if st.view == "clock":
        for i in range(60):
            major = i % 5 == 0
            if major:
                for f in (0.88, 0.95):
                    g.put(*pos(i * 6, f), "█", "white")
            else:
                g.put(*pos(i * 6, 0.97), "·", "dim")
        if ry >= 7:
            for n in range(1, 13):
                x, y = pos(n * 30, 0.74)
                label = str(n)
                g.text(x - len(label) // 2, y, label, "cyan")
        sec = now.second + now.microsecond / 1e6
        minute = now.minute + sec / 60
        hour = now.hour % 12 + minute / 60
        hand(hour * 30, 0.5, "█", "white")
        hand(minute * 6, 0.75, "█", "white")
        if st.seconds:
            hand(sec * 6, 0.88, "•", "red")
    else:
        p = rem / st.duration if st.duration else 0.0
        color = level(rem, st.duration)
        for i in range(720):
            ang = i / 2
            if p > 0 and ang <= 360 * p:
                for f in (1.0, 0.94):
                    g.put(*pos(ang, f), "█", color)
            else:
                g.put(*pos(ang, 1.0), "·", "dim")
        if ry >= 7:
            for n in range(1, 13):
                x, y = pos(n * 30, 0.74)
                label = str(n * 5 % 60)
                g.text(x - len(label) // 2, y, label, "cyan")
        if rem > 0:
            hand((rem / 60 % 60) * 6, 0.62, "█", "white")
            hand((rem % 60) * 6, 0.82, "•", "red")
    g.put(cx, cy, "█", "white")
    return g.lines()


def clip(s, w, color):
    """Pads or clips a plain string to w columns and colors it."""
    return COLORS[color] + s.ljust(w)[:w] + RESET


def render(st, w, h, flash):
    """Renders one full frame.

    Args:
        st: The State.
        w: Terminal width.
        h: Terminal height.
        flash: Whether the alarm flash is in its on phase.

    Returns:
        The frame as one string, ready to write after moving the cursor home.
    """
    zone = st.zones[st.zone_i]
    now = datetime.now(ZoneInfo(zone)) if zone else datetime.now()
    rem = st.remaining()
    if st.view == "clock":
        hour = f"{now.hour % 12 or 12:2d}" if st.twelve else f"{now.hour:02d}"
        text = f"{hour}:{now.minute:02d}"
        if st.seconds:
            text += f":{now.second:02d}"
        if st.twelve:
            text += " PM" if now.hour >= 12 else " AM"
        digit_color = "white"
        top = f" CLOCK   {zone or 'local'}   {now:%A %B %d %Y}"
    else:
        with_hours = st.duration >= 3600 or rem >= 3600
        text = format_hms(math.ceil(rem), with_hours)
        digit_color = level(rem, st.duration)
        if st.alarm:
            state = "TIME'S UP"
        elif st.running:
            state = "RUNNING"
        else:
            state = "READY" if rem >= st.duration else "PAUSED"
        top = f" TIMER {state}   now {now:%H:%M:%S}"
        if st.running:
            top += f"   ends {now + timedelta(seconds=rem):%H:%M:%S}"
    bars = st.details or st.alarm
    body_h = h - 2 if bars else h
    if body_h < 5:
        body = big_text(text, w, max(body_h, 0), digit_color)
    elif st.face == "digital":
        body = big_text(text, w, body_h, digit_color)
    elif st.face == "analog":
        body = analog(w, body_h, st, now, rem)
    else:
        units = text_units(text)
        sy_w = max(1, w // (2 * units))
        dig_h = max(5, min(5 * sy_w + 2, body_h * 2 // 5))
        stacked_scale = min(dig_h // 5, w // (2 * units))
        analog_w = min(2 * body_h + 1, w // 2)
        side_scale = min(body_h // 5, (w - analog_w) // (2 * units))
        if side_scale >= max(stacked_scale, 1):
            left = analog(analog_w, body_h, st, now, rem)
            right = big_text(text, w - analog_w, body_h, digit_color)
            body = [a + b for a, b in zip(left, right)]
        else:
            body = big_text(text, w, dig_h, digit_color) + analog(
                w, body_h - dig_h, st, now, rem
            )
    lines = body
    if bars:
        lines = [clip(top, w, "cyan")] + body + [clip(HELP, w, "dim")]
    if flash:
        lines = [
            FLASH_BG + ln.replace(RESET, RESET + FLASH_BG) + RESET for ln in lines
        ]
    return "\x1b[H" + "\r\n".join(lines)


def find_player():
    """Returns the first available command line audio player, or None."""
    for name in ("afplay", "paplay", "aplay"):
        path = shutil.which(name)
        if path:
            return path
    return None


def resolve_sound(spec):
    """Resolves a sound name or file path to an audio file.

    Args:
        spec: A file path, or the name of a macOS system sound such as Glass.

    Returns:
        The path of the audio file.

    Raises:
        ValueError: If no matching file exists.
    """
    candidates = [
        spec,
        f"/System/Library/Sounds/{spec}.aiff",
        f"/usr/share/sounds/freedesktop/stereo/{spec}.oga",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise ValueError(f"sound not found: {spec}")


def play_alarm(st):
    """Rings the alarm using the chosen sound file, or the terminal bell."""
    player = find_player() if st.sound else None
    if player:
        subprocess.Popen(
            [player, st.sound],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        sys.stdout.write("\a")


def handle_keys(data, st):
    """Applies keystrokes to the state.

    Args:
        data: Raw bytes read from the terminal.
        st: The State.

    Returns:
        False when the user asked to quit, otherwise True.
    """
    keys = []
    text = data.decode("utf-8", "ignore")
    i = 0
    while i < len(text):
        if text.startswith("\x1b[", i) and i + 2 < len(text):
            keys.append({"A": "up", "B": "down"}.get(text[i + 2], "esc"))
            i += 3
        else:
            keys.append(text[i])
            i += 1
    for key in keys:
        if key in ("q", "\x03"):
            return False
        if st.alarm:
            st.alarm = False
            continue
        if key == " ":
            st.pause() if st.running else st.start()
        elif key in ("v", "\t", "c", "t"):
            st.view = "clock" if st.view == "timer" else "timer"
        elif key == "a":
            st.face = FACES[(FACES.index(st.face) + 1) % len(FACES)]
        elif key == "r":
            st.reset()
        elif key in ("+", "="):
            st.adjust(60)
        elif key in ("-", "_"):
            st.adjust(-60)
        elif key == "up":
            st.adjust(300)
        elif key == "down":
            st.adjust(-300)
        elif key == "h":
            st.twelve = not st.twelve
        elif key == "m":
            st.bell = not st.bell
        elif key == "s":
            st.seconds = not st.seconds
        elif key in ("d", "?"):
            st.details = not st.details
        elif key == "z":
            st.zone_i = (st.zone_i + 1) % len(st.zones)
    return True


def run(st):
    """Runs the interactive full screen loop.

    Args:
        st: The State.
    """
    fd = os.open("/dev/tty", os.O_RDONLY)
    old = termios.tcgetattr(fd)
    out = sys.stdout
    flash = False
    try:
        tty.setcbreak(fd)
        out.write(ENTER_SCREEN)
        while True:
            st.tick()
            new_flash = st.alarm and int(time.monotonic() * 2) % 2 == 0
            if new_flash and not flash and st.bell:
                play_alarm(st)
            flash = new_flash
            w, h = shutil.get_terminal_size()
            out.write(render(st, w, h, flash))
            out.flush()
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready and not handle_keys(os.read(fd, 64), st):
                break
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write(LEAVE_SCREEN)
        out.flush()
        os.close(fd)


def main(argv=None):
    """Parses arguments and starts BigTymers.

    Args:
        argv: Optional argument list for testing.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(
        prog="btyme",
        description="Full screen analog and digital clock and timer.",
        epilog="Examples: btyme 45m | btyme 1h30m --face analog | btyme",
    )
    parser.add_argument(
        "duration",
        nargs="?",
        help="timer length: 45, 45m, 90s, 1h30m, mm:ss or hh:mm:ss (bare numbers are minutes)",
    )
    parser.add_argument("--view", choices=["clock", "timer"], help="initial view")
    parser.add_argument("--face", choices=FACES, default="both", help="initial face")
    parser.add_argument("--paused", action="store_true", help="do not start the timer")
    parser.add_argument("--12", dest="twelve", action="store_true", help="12 hour clock")
    parser.add_argument("--no-bell", action="store_true", help="silence the alarm")
    parser.add_argument(
        "--tz",
        default="",
        help="time zones for the clock, comma separated, local first if you list 'local' "
        "(example: America/New_York,Europe/London); press z to cycle",
    )
    parser.add_argument("--no-seconds", action="store_true", help="hide seconds on the clock")
    parser.add_argument("--details", action="store_true", help="show the header and help lines")
    parser.add_argument(
        "--sound",
        help="alarm sound: a macOS system sound name such as Glass or Submarine, or an audio file path",
    )
    parser.add_argument("--once", action="store_true", help="print one frame and exit")
    parser.add_argument("--size", default="", help="WxH for --once, for example 100x30")
    args = parser.parse_args(argv)

    try:
        duration = parse_duration(args.duration) if args.duration else 600.0
    except ValueError as err:
        parser.error(str(err))
    view = args.view or ("timer" if args.duration else "clock")
    zones = []
    for name in filter(None, (z.strip() for z in args.tz.split(","))):
        if name.lower() == "local":
            zones.append(None)
            continue
        try:
            ZoneInfo(name)
        except Exception:
            parser.error(f"unknown time zone: {name}")
        zones.append(name)
    sound = None
    if args.sound:
        try:
            sound = resolve_sound(args.sound)
        except ValueError as err:
            parser.error(str(err))
    st = State(
        duration,
        view,
        args.face,
        args.twelve,
        not args.no_bell,
        zones=zones or None,
        seconds=not args.no_seconds,
        details=args.details,
        sound=sound,
    )
    if args.duration and not args.paused:
        st.start()

    if args.once:
        w, h = (
            map(int, args.size.lower().split("x"))
            if args.size
            else shutil.get_terminal_size((100, 30))
        )
        sys.stdout.write(render(st, w, h, False) + RESET + "\n")
        return 0
    if not sys.stdout.isatty():
        parser.error("stdout must be a terminal (use --once to print a single frame)")
    run(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
