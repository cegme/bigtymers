# BigTymers

A minimal full screen clock and countdown timer for exams and presentations.
It runs in the browser and in the terminal.

Browser: https://ceg.me/bigtymers

Terminal, with nothing to download:

```
curl -fsSL https://ceg.me/bigtymers/bigtymers.py | python3 - 45m
```

The terminal version needs only Python 3.9 or newer and no packages.
Keys are read from the terminal device, so piping the script into Python works.

## Display

Both versions show an analog face, a digital face, or both.
The main screen shows only the time.
Everything else is in settings, which are hidden until needed.

The clock view shows the current time.
The timer view shows the time left.
Press `v` to switch between them.
The timer ring and digits turn amber and then red as time runs low.
When the timer reaches zero the screen flashes and the alarm sounds until someone dismisses it.

## Browser

The controls fade out when the mouse is idle.
Open settings with the gear or the `s` key.

| Key | Action |
| --- | --- |
| Space | Start or pause the timer, or dismiss the alarm |
| v | Switch between current time and time left |
| a | Cycle both, analog and digital |
| f | Full screen (double click also works) |
| s | Settings |
| + / - | Add or remove 1 minute |
| Up / Down | Add or remove 5 minutes |
| r | Reset the timer |
| h | 12 hour (AM/PM) or 24 hour clock |
| m | Mute the alarm |

Settings include face, 12 or 24 hour time, seconds, time zone, date line, analog numerals, theme, timer presets and the alarm.
The alarm has 6 tones (beep, chime, bell, siren, buzzer, digital watch), a volume slider, a repeat count, and an optional cue at 5 minutes and 1 minute left.
Settings are remembered in the browser.
The screen is kept awake while the page is open.

Link options start the page in a given state.

```
https://ceg.me/bigtymers/?t=45m&go&face=analog&tz=Europe/London&h12=1&seconds=0&details=1&tone=bell
```

| Option | Meaning |
| --- | --- |
| t | Timer length: 45, 45m, 90s, 1h30m, 1:30:00. A bare number is minutes. |
| go | Start the timer immediately (needs t) |
| view | clock or timer |
| face | both, analog or digital |
| tz | IANA time zone such as Asia/Tokyo |
| h12, seconds, details, numerals | 1 or 0 |
| tone | beep, chime, bell, siren, buzzer, digital |
| theme | dark or light |

Browsers only play sound after the page has been clicked or a key has been pressed once.
Press any key when the page opens to arm the alarm sound.

## Terminal

```
bigtymers.py [duration] [--view clock|timer] [--face both|analog|digital]
             [--tz ZONE[,ZONE...]] [--12] [--no-seconds] [--details]
             [--sound NAME_OR_FILE] [--no-bell] [--paused]
```

Examples:

```
curl -fsSL https://ceg.me/bigtymers/bigtymers.py | python3 - 90m --face analog
curl -fsSL https://ceg.me/bigtymers/bigtymers.py | python3 - --tz local,Asia/Tokyo --12
curl -fsSL https://ceg.me/bigtymers/bigtymers.py | python3 - 1h30m --sound Glass
```

Giving a duration starts the timer.
Without one, the clock is shown.
Make the terminal window full screen for the largest display.

| Key | Action |
| --- | --- |
| space | Start or pause, or dismiss the alarm |
| v | Switch between clock and timer |
| a | Cycle faces |
| + / - | Add or remove 1 minute |
| Up / Down | Add or remove 5 minutes |
| r | Reset |
| h | 12 or 24 hour clock |
| s | Show or hide seconds |
| z | Cycle through the zones given with `--tz` |
| d or ? | Show or hide the header and help line |
| m | Mute |
| q | Quit |

The alarm flashes the screen and rings the terminal bell.
`--sound` plays a file instead.
On macOS use a system sound name such as Glass, Submarine or Hero, or a path to an audio file.
Playback uses `afplay`, `paplay` or `aplay`, whichever is installed.

## Hosting

The site is served by GitHub Pages from the main branch.
The `ceg.me` domain is set on the `cegme.github.io` user site, so this repository is served at `ceg.me/bigtymers`.
