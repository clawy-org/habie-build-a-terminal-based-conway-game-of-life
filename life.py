#!/usr/bin/env python3
"""
life.py — Terminal Conway's Game of Life with curses UI.

Controls:
  Space       Pause/resume
  n           Step one generation (while paused)
  r           Random reset
  Up/Down     Speed up/slow down
  q           Quit
  Mouse       Toggle cell (while paused, if supported)

Patterns:
  python life.py --pattern glider|blinker|pulsar|gosper_gun|random

Save/Load:
  python life.py --save state.json
  python life.py --load state.json
"""

import argparse
import curses
import json
import os
import random
import sys
import time
from typing import Dict, FrozenSet, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Core game logic (pure functions, no curses dependency)
# ---------------------------------------------------------------------------

Cell = Tuple[int, int]
Grid = FrozenSet[Cell]


def neighbors(r: int, c: int, rows: int, cols: int) -> list:
    """Return the 8 neighbours of (r, c) with toroidal wrap-around."""
    return [
        ((r + dr) % rows, (c + dc) % cols)
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if not (dr == 0 and dc == 0)
    ]


def count_neighbors(grid: Grid, r: int, c: int, rows: int, cols: int) -> int:
    return sum(1 for cell in neighbors(r, c, rows, cols) if cell in grid)


def step(grid: Grid, rows: int, cols: int) -> Grid:
    """Apply one generation of Conway rules and return the new grid."""
    candidate_counts: Dict[Cell, int] = {}
    for (r, c) in grid:
        for nb in neighbors(r, c, rows, cols):
            candidate_counts[nb] = candidate_counts.get(nb, 0) + 1
        if (r, c) not in candidate_counts:
            candidate_counts[(r, c)] = 0

    new_grid: Set[Cell] = set()
    for cell, n in candidate_counts.items():
        alive = cell in grid
        if alive and n in (2, 3):
            new_grid.add(cell)
        elif not alive and n == 3:
            new_grid.add(cell)
    return frozenset(new_grid)


def random_grid(rows: int, cols: int, density: float = 0.3) -> Grid:
    return frozenset(
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if random.random() < density
    )


# ---------------------------------------------------------------------------
# Preset patterns
# ---------------------------------------------------------------------------

def _translate(cells: list, dr: int, dc: int) -> Grid:
    return frozenset((r + dr, c + dc) for r, c in cells)


def _center(cells: list, rows: int, cols: int) -> Grid:
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    max_r = max(r for r, _ in cells)
    max_c = max(c for _, c in cells)
    dr = (rows - (max_r - min_r + 1)) // 2 - min_r
    dc = (cols - (max_c - min_c + 1)) // 2 - min_c
    return _translate(cells, dr, dc)


GLIDER_CELLS = [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]

BLINKER_CELLS = [(1, 0), (1, 1), (1, 2)]

PULSAR_CELLS = [
    (0, 2), (0, 3), (0, 4), (0, 8), (0, 9), (0, 10),
    (2, 0), (2, 5), (2, 7), (2, 12),
    (3, 0), (3, 5), (3, 7), (3, 12),
    (4, 0), (4, 5), (4, 7), (4, 12),
    (5, 2), (5, 3), (5, 4), (5, 8), (5, 9), (5, 10),
    (7, 2), (7, 3), (7, 4), (7, 8), (7, 9), (7, 10),
    (8, 0), (8, 5), (8, 7), (8, 12),
    (9, 0), (9, 5), (9, 7), (9, 12),
    (10, 0), (10, 5), (10, 7), (10, 12),
    (12, 2), (12, 3), (12, 4), (12, 8), (12, 9), (12, 10),
]

GOSPER_GUN_CELLS = [
    (0, 24),
    (1, 22), (1, 24),
    (2, 12), (2, 13), (2, 20), (2, 21), (2, 34), (2, 35),
    (3, 11), (3, 15), (3, 20), (3, 21), (3, 34), (3, 35),
    (4, 0), (4, 1), (4, 10), (4, 16), (4, 20), (4, 21),
    (5, 0), (5, 1), (5, 10), (5, 14), (5, 16), (5, 17), (5, 22), (5, 24),
    (6, 10), (6, 16), (6, 24),
    (7, 11), (7, 15),
    (8, 12), (8, 13),
]


def load_pattern(name: str, rows: int, cols: int) -> Grid:
    if name == "glider":
        return _center(GLIDER_CELLS, rows, cols)
    elif name == "blinker":
        return _center(BLINKER_CELLS, rows, cols)
    elif name == "pulsar":
        return _center(PULSAR_CELLS, rows, cols)
    elif name == "gosper_gun":
        return _center(GOSPER_GUN_CELLS, rows, cols)
    elif name == "random":
        return random_grid(rows, cols)
    else:
        raise ValueError(f"Unknown pattern: {name}")


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def save_grid(grid: Grid, rows: int, cols: int, path: str, generation: int = 0) -> None:
    data = {
        "rows": rows,
        "cols": cols,
        "generation": generation,
        "cells": [[r, c] for r, c in sorted(grid)],
    }
    with open(path, "w") as f:
        json.dump(data, f)


def load_grid(path: str) -> Tuple[Grid, int, int, int]:
    """Returns (grid, rows, cols, generation)."""
    with open(path) as f:
        data = json.load(f)
    grid = frozenset((cell[0], cell[1]) for cell in data["cells"])
    return grid, data["rows"], data["cols"], data.get("generation", 0)


# ---------------------------------------------------------------------------
# Curses UI
# ---------------------------------------------------------------------------

# Color pair IDs
COLOR_ALIVE = 1      # green  — alive this gen
COLOR_BORN = 2       # cyan   — just born
COLOR_DYING = 3      # red    — just died
COLOR_STATUS = 4     # yellow — status bar
COLOR_HEAT1 = 5      # dim green — heatmap level 1
COLOR_HEAT2 = 6      # dim cyan  — heatmap level 2


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_ALIVE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_BORN, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_DYING, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_STATUS, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_HEAT1, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_HEAT2, curses.COLOR_CYAN, -1)


SPEEDS = [0.5, 0.25, 0.1, 0.05, 0.02, 0.01]
SPEED_LABELS = ["0.5s", "0.25s", "0.1s", "0.05s", "0.02s", "0.01s"]


def run(
    stdscr,
    pattern: str = "random",
    save_path: Optional[str] = None,
    load_path: Optional[str] = None,
) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(50)

    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        mouse_enabled = True
    except Exception:
        mouse_enabled = False

    init_colors()

    max_rows, max_cols = stdscr.getmaxyx()
    grid_rows = max_rows - 2       # reserve 2 rows for status bar
    grid_cols = max_cols // 2      # each cell is 2 chars wide

    generation = 0
    speed_idx = 2  # default 0.1s

    # Previous and heat grids for visual effects
    prev_grid: Grid = frozenset()
    heat: Dict[Cell, int] = {}   # cells that were recently alive

    # Load or initialise grid
    if load_path and os.path.exists(load_path):
        grid, loaded_rows, loaded_cols, generation = load_grid(load_path)
        grid_rows = min(grid_rows, loaded_rows)
        grid_cols = min(grid_cols, loaded_cols)
        grid = frozenset((r, c) for r, c in grid if r < grid_rows and c < grid_cols)
    else:
        grid = load_pattern(pattern, grid_rows, grid_cols)

    paused = False
    heatmap = False
    last_step = time.monotonic()

    while True:
        # --- Handle input ---
        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
        elif key == ord("n") and paused:
            prev_grid = grid
            grid = step(grid, grid_rows, grid_cols)
            generation += 1
            _update_heat(heat, prev_grid, grid)
        elif key == ord("r"):
            grid = random_grid(grid_rows, grid_cols)
            prev_grid = frozenset()
            heat.clear()
            generation = 0
        elif key == ord("h"):
            heatmap = not heatmap
        elif key == curses.KEY_UP and speed_idx < len(SPEEDS) - 1:
            speed_idx += 1
        elif key == curses.KEY_DOWN and speed_idx > 0:
            speed_idx -= 1
        elif key == ord("s") and save_path:
            save_grid(grid, grid_rows, grid_cols, save_path, generation)
        elif key == curses.KEY_MOUSE and mouse_enabled and paused:
            try:
                _, mx, my, _, _ = curses.getmouse()
                # mx is column (each cell = 2 chars), my is row
                c = mx // 2
                r = my
                if 0 <= r < grid_rows and 0 <= c < grid_cols:
                    cell = (r, c)
                    s = set(grid)
                    if cell in s:
                        s.discard(cell)
                    else:
                        s.add(cell)
                    grid = frozenset(s)
            except Exception:
                pass

        # --- Auto-step ---
        now = time.monotonic()
        if not paused and now - last_step >= SPEEDS[speed_idx]:
            prev_grid = grid
            grid = step(grid, grid_rows, grid_cols)
            generation += 1
            _update_heat(heat, prev_grid, grid)
            last_step = now

        # --- Draw ---
        stdscr.erase()
        _draw_grid(stdscr, grid, prev_grid, heat, grid_rows, grid_cols, heatmap)
        _draw_status(
            stdscr, generation, len(grid), paused, heatmap,
            SPEED_LABELS[speed_idx], max_rows, max_cols, save_path, mouse_enabled
        )
        stdscr.refresh()

    # Auto-save on quit if path given
    if save_path:
        save_grid(grid, grid_rows, grid_cols, save_path, generation)


def _update_heat(heat: Dict[Cell, int], prev: Grid, current: Grid) -> None:
    """Update heat map: recently alive cells glow for a few generations."""
    MAX_HEAT = 3
    # Decay existing heat
    to_delete = [k for k, v in heat.items() if v <= 1]
    for k in to_delete:
        del heat[k]
    for k in list(heat):
        heat[k] = heat[k] - 1
    # Cells that just died get heat
    just_died = prev - current
    for cell in just_died:
        heat[cell] = MAX_HEAT


def _draw_grid(
    stdscr,
    grid: Grid,
    prev: Grid,
    heat: Dict[Cell, int],
    rows: int,
    cols: int,
    heatmap: bool,
) -> None:
    born = grid - prev
    died = prev - grid

    for r in range(rows):
        for c in range(cols):
            cell = (r, c)
            x = c * 2
            if x + 1 >= curses.COLS:
                continue
            if r >= curses.LINES - 2:
                continue

            if cell in grid:
                if cell in born:
                    attr = curses.color_pair(COLOR_BORN) | curses.A_BOLD
                    ch = "██"
                else:
                    attr = curses.color_pair(COLOR_ALIVE) | curses.A_BOLD
                    ch = "██"
                try:
                    stdscr.addstr(r, x, ch, attr)
                except curses.error:
                    pass
            elif heatmap and cell in heat:
                h = heat[cell]
                pair = COLOR_HEAT1 if h <= 1 else COLOR_HEAT2
                try:
                    stdscr.addstr(r, x, "░░", curses.color_pair(pair))
                except curses.error:
                    pass


def _draw_status(
    stdscr,
    generation: int,
    population: int,
    paused: bool,
    heatmap: bool,
    speed: str,
    rows: int,
    cols: int,
    save_path: Optional[str],
    mouse: bool,
) -> None:
    state = "PAUSED" if paused else "RUNNING"
    heat_str = "[H]eat ON" if heatmap else "[H]eat off"
    save_str = f" [S]ave:{save_path}" if save_path else ""
    mouse_str = " [mouse]" if mouse else ""
    status = (
        f" Gen:{generation:6d}  Pop:{population:6d}  {state}"
        f"  Speed:{speed}  [↑↓][Space][N][R][Q]{save_str}  {heat_str}{mouse_str}"
    )
    try:
        stdscr.addstr(
            rows - 1, 0,
            status[:cols - 1].ljust(cols - 1),
            curses.color_pair(COLOR_STATUS) | curses.A_BOLD,
        )
    except curses.error:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conway's Game of Life — terminal edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pattern",
        choices=["glider", "blinker", "pulsar", "gosper_gun", "random"],
        default="random",
        help="Starting pattern (default: random)",
    )
    parser.add_argument("--save", metavar="FILE", help="Auto-save state to JSON on quit")
    parser.add_argument("--load", metavar="FILE", help="Load grid state from JSON file")
    args = parser.parse_args()

    curses.wrapper(run, pattern=args.pattern, save_path=args.save, load_path=args.load)


if __name__ == "__main__":
    main()
