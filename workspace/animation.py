#!/usr/bin/env python3
"""Terminal animations using only standard libraries.

Usage:
    python animation.py              # default wave animation
    python animation.py wave         # sine-wave color field
    python animation.py starfield    # 3D starfield fly-through
    python animation.py retro        # retro scrolling text effect
"""

import argparse
import math
import random
import shutil
import time

RESET = "\033[0m"

# ── Wave animation ──────────────────────────────────────────────────

WAVE_CHARS = " ░▒▓█▓▒░"
WAVE_PALETTE = [
    "\033[38;5;21m",   # deep blue
    "\033[38;5;27m",
    "\033[38;5;33m",
    "\033[38;5;39m",
    "\033[38;5;45m",
    "\033[38;5;51m",   # cyan
    "\033[38;5;50m",
    "\033[38;5;49m",
    "\033[38;5;48m",
    "\033[38;5;47m",
    "\033[38;5;46m",   # green
    "\033[38;5;82m",
    "\033[38;5;118m",
    "\033[38;5;154m",
    "\033[38;5;190m",
    "\033[38;5;226m",  # yellow
]


def render_wave(cols: int, rows: int, t: float) -> str:
    lines = []
    for y in range(rows):
        row = []
        for x in range(cols):
            wave1 = math.sin(x * 0.08 + t * 2.0)
            wave2 = math.sin(y * 0.12 - t * 1.5)
            wave3 = math.sin((x + y) * 0.06 + t * 1.2)
            val = (wave1 + wave2 + wave3) / 3.0

            ci = int((val + 1) / 2 * (len(WAVE_CHARS) - 1))
            pi = int((val + 1) / 2 * (len(WAVE_PALETTE) - 1))
            row.append(f"{WAVE_PALETTE[pi]}{WAVE_CHARS[ci]}")
        lines.append("".join(row))
    return "\n".join(lines) + RESET


def run_wave() -> None:
    t = 0.0
    while True:
        cols, rows = shutil.get_terminal_size()
        rows -= 1
        frame = render_wave(cols, rows, t)
        print(f"\033[H{frame}", end="", flush=True)
        t += 0.05
        time.sleep(0.03)


# ── Starfield animation ────────────────────────────────────────────

STAR_CHARS = ".·+*#@"
STAR_COLORS = [
    "\033[38;5;240m",  # dim
    "\033[38;5;245m",
    "\033[38;5;250m",
    "\033[38;5;255m",  # bright white
    "\033[38;5;229m",  # warm white
    "\033[38;5;159m",  # cool blue-white
]


def run_starfield() -> None:
    cols, rows = shutil.get_terminal_size()
    rows -= 1
    num_stars = int(cols * rows * 0.012)
    stars = []
    for _ in range(num_stars):
        stars.append([
            random.uniform(-1, 1),  # x in [-1, 1]
            random.uniform(-1, 1),  # y in [-1, 1]
            random.uniform(0.1, 1), # z (depth)
        ])

    while True:
        cols, rows = shutil.get_terminal_size()
        rows -= 1
        cx, cy = cols // 2, rows // 2
        buf = [[" "] * cols for _ in range(rows)]

        for star in stars:
            star[2] -= 0.015
            if star[2] <= 0.01:
                star[0] = random.uniform(-1, 1)
                star[1] = random.uniform(-1, 1)
                star[2] = 1.0

            sx = int(cx + star[0] / star[2] * cx)
            sy = int(cy + star[1] / star[2] * cy * 0.5)

            if 0 <= sx < cols and 0 <= sy < rows:
                brightness = 1.0 - star[2]
                ci = min(int(brightness * len(STAR_CHARS)), len(STAR_CHARS) - 1)
                ki = min(int(brightness * len(STAR_COLORS)), len(STAR_COLORS) - 1)
                buf[sy][sx] = f"{STAR_COLORS[ki]}{STAR_CHARS[ci]}{RESET}"

        frame = "\n".join("".join(row) for row in buf)
        print(f"\033[H{frame}", end="", flush=True)
        time.sleep(0.04)


# ── Retro text animation ───────────────────────────────────────────

RETRO_GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&!?<>{}[]"
RETRO_PALETTE = [
    "\033[38;5;46m",   # bright green
    "\033[38;5;34m",
    "\033[38;5;28m",
    "\033[38;5;22m",   # dark green
]


def run_retro() -> None:
    cols, rows = shutil.get_terminal_size()
    rows -= 1
    columns = []
    for x in range(cols):
        columns.append({
            "y": random.randint(-rows, 0),
            "speed": random.uniform(0.3, 1.0),
            "length": random.randint(4, rows // 2),
            "acc": 0.0,
        })

    grid = [[(" ", "")] * cols for _ in range(rows)]

    while True:
        cols_now, rows_now = shutil.get_terminal_size()
        rows_now -= 1
        if cols_now != cols or rows_now != rows:
            cols, rows = cols_now, rows_now
            columns = []
            for x in range(cols):
                columns.append({
                    "y": random.randint(-rows, 0),
                    "speed": random.uniform(0.3, 1.0),
                    "length": random.randint(4, rows // 2),
                    "acc": 0.0,
                })
            grid = [[(" ", "")] * cols for _ in range(rows)]

        for y in range(rows):
            for x in range(cols):
                grid[y][x] = (" ", "")

        for x, col in enumerate(columns):
            if x >= cols:
                continue
            col["acc"] += col["speed"]
            while col["acc"] >= 1.0:
                col["y"] += 1
                col["acc"] -= 1.0

            head = int(col["y"])
            for i in range(col["length"]):
                cy = head - i
                if 0 <= cy < rows:
                    ch = random.choice(RETRO_GLYPHS) if i < 2 else RETRO_GLYPHS[
                        (cy * 7 + x * 13) % len(RETRO_GLYPHS)
                    ]
                    if i == 0:
                        color = "\033[1;97m"  # bright white head
                    else:
                        pi = min(i * len(RETRO_PALETTE) // col["length"],
                                 len(RETRO_PALETTE) - 1)
                        color = RETRO_PALETTE[pi]
                    grid[cy][x] = (ch, color)

            if head - col["length"] > rows:
                col["y"] = random.randint(-rows // 2, -1)
                col["speed"] = random.uniform(0.3, 1.0)
                col["length"] = random.randint(4, rows // 2)

        lines = []
        for y in range(rows):
            row = []
            for x in range(cols):
                ch, color = grid[y][x]
                if color:
                    row.append(f"{color}{ch}{RESET}")
                else:
                    row.append(ch)
            lines.append("".join(row))

        print(f"\033[H" + "\n".join(lines), end="", flush=True)
        time.sleep(0.05)


# ── Entry point ─────────────────────────────────────────────────────

ANIMATIONS = {
    "wave": run_wave,
    "starfield": run_starfield,
    "retro": run_retro,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal animations")
    parser.add_argument(
        "animation",
        nargs="?",
        default="wave",
        choices=ANIMATIONS,
        help="animation type (default: wave)",
    )
    args = parser.parse_args()

    print("\033[?25l\033[2J", end="", flush=True)  # hide cursor, clear screen
    try:
        ANIMATIONS[args.animation]()
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\033[?25h{RESET}\033[2J\033[H", end="", flush=True)


if __name__ == "__main__":
    main()
