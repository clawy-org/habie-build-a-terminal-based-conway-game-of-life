# life.py — Terminal Conway's Game of Life

Interactive Game of Life in the terminal using `curses`. Zero external dependencies.

## Usage

```bash
python life.py                          # random start
python life.py --pattern glider         # start with a glider
python life.py --pattern pulsar         # start with a pulsar
python life.py --pattern gosper_gun     # start with Gosper Glider Gun
python life.py --pattern blinker        # start with a blinker
python life.py --save state.json        # auto-save on quit
python life.py --load state.json        # resume saved state
```

## Controls

| Key        | Action                          |
|------------|---------------------------------|
| `Space`    | Pause / Resume                  |
| `n`        | Step one generation (paused)    |
| `r`        | Random reset                    |
| `↑` / `↓`  | Speed up / slow down            |
| `h`        | Toggle heatmap (trail) mode     |
| `s`        | Save to file (if --save given)  |
| `q`        | Quit                            |
| Mouse click| Toggle cell (paused, if supported) |

## Visual Effects

- **Green** `██` — alive cell
- **Cyan** `██` — just born this generation
- **Red** — just died (heatmap mode: `h`)
- **░░** — heatmap trail: cells that were alive recently

## Features

- Classic Conway rules on a toroidal (wrap-around) grid
- Auto-detects terminal size
- 4 preset patterns: glider, blinker, pulsar, Gosper glider gun
- Adjustable speed (6 levels: 0.5s → 0.01s per generation)
- Pause, step, and random reset
- Save/load grid state as JSON
- Mouse cell toggle while paused (terminal permitting)
- Heatmap mode shows recent activity

## Tests

```bash
python -m unittest test_life -v
```

34 tests covering: Conway rules (birth/death/survival), neighbor counting with toroidal wrap, blinker period-2, glider period-4 translation, pulsar period-3, all preset patterns, persistence save/load, and edge/wrap-around behaviour.
