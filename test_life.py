#!/usr/bin/env python3
"""Tests for Conway's Game of Life core logic."""

import json
import os
import tempfile
import unittest

from life import (
    Grid,
    count_neighbors,
    load_grid,
    load_pattern,
    neighbors,
    random_grid,
    save_grid,
    step,
    GLIDER_CELLS,
    BLINKER_CELLS,
    PULSAR_CELLS,
    GOSPER_GUN_CELLS,
    _center,
)


class TestNeighbors(unittest.TestCase):
    def test_center_cell(self):
        nb = neighbors(5, 5, 10, 10)
        self.assertEqual(len(nb), 8)
        self.assertNotIn((5, 5), nb)

    def test_wrap_top_left(self):
        nb = neighbors(0, 0, 10, 10)
        self.assertIn((9, 9), nb)  # wraps both row and col
        self.assertIn((0, 9), nb)
        self.assertIn((9, 0), nb)

    def test_wrap_bottom_right(self):
        nb = neighbors(9, 9, 10, 10)
        self.assertIn((0, 0), nb)
        self.assertIn((9, 0), nb)
        self.assertIn((0, 9), nb)

    def test_count_neighbors_empty(self):
        grid = frozenset()
        self.assertEqual(count_neighbors(grid, 5, 5, 10, 10), 0)

    def test_count_neighbors_surrounded(self):
        # Place all 8 neighbors
        nb = neighbors(5, 5, 10, 10)
        grid = frozenset(nb)
        self.assertEqual(count_neighbors(grid, 5, 5, 10, 10), 8)


class TestConwayRules(unittest.TestCase):
    """Test birth, survival, and death rules."""

    def test_underpopulation_1_neighbor(self):
        """Live cell with 1 neighbor dies."""
        grid = frozenset([(5, 5), (5, 6)])
        new = step(grid, 10, 10)
        self.assertNotIn((5, 5), new)

    def test_underpopulation_0_neighbors(self):
        """Live cell with 0 neighbors dies."""
        grid = frozenset([(5, 5)])
        new = step(grid, 10, 10)
        self.assertNotIn((5, 5), new)

    def test_survival_2_neighbors(self):
        """Live cell with 2 neighbors survives."""
        # Blinker: middle cell has 2 neighbours
        grid = frozenset([(5, 4), (5, 5), (5, 6)])
        new = step(grid, 10, 10)
        self.assertIn((5, 5), new)

    def test_survival_3_neighbors(self):
        """Live cell with 3 neighbors survives."""
        # Create a stable 2x2 block — each cell has 3 neighbors
        grid = frozenset([(5, 5), (5, 6), (6, 5), (6, 6)])
        new = step(grid, 10, 10)
        self.assertEqual(new, grid)

    def test_overpopulation_4_neighbors(self):
        """Live cell with 4+ neighbors dies."""
        # Centre of a plus shape has 4 neighbors
        grid = frozenset([(4, 5), (5, 4), (5, 5), (5, 6), (6, 5)])
        new = step(grid, 10, 10)
        self.assertNotIn((5, 5), new)

    def test_birth_3_neighbors(self):
        """Dead cell with exactly 3 live neighbors is born."""
        grid = frozenset([(5, 4), (5, 5), (5, 6)])
        new = step(grid, 10, 10)
        self.assertIn((4, 5), new)
        self.assertIn((6, 5), new)

    def test_no_birth_2_neighbors(self):
        """Dead cell with 2 neighbors stays dead."""
        grid = frozenset([(5, 4), (5, 5)])
        new = step(grid, 10, 10)
        # (5,3) has 1 neighbor, (4,4) has 2 neighbors — should NOT be born
        self.assertNotIn((5, 3), new)

    def test_2x2_block_stable(self):
        """2×2 block is a still life."""
        grid = frozenset([(0, 0), (0, 1), (1, 0), (1, 1)])
        self.assertEqual(step(grid, 10, 10), grid)

    def test_empty_grid(self):
        """Empty grid stays empty."""
        self.assertEqual(step(frozenset(), 10, 10), frozenset())


class TestBlinker(unittest.TestCase):
    """Blinker oscillates with period 2."""

    def setUp(self):
        self.rows, self.cols = 20, 20
        self.horizontal = frozenset([(10, 9), (10, 10), (10, 11)])
        self.vertical = frozenset([(9, 10), (10, 10), (11, 10)])

    def test_horizontal_to_vertical(self):
        new = step(self.horizontal, self.rows, self.cols)
        self.assertEqual(new, self.vertical)

    def test_vertical_to_horizontal(self):
        new = step(self.vertical, self.rows, self.cols)
        self.assertEqual(new, self.horizontal)

    def test_period_2(self):
        gen2 = step(step(self.horizontal, self.rows, self.cols), self.rows, self.cols)
        self.assertEqual(gen2, self.horizontal)


class TestGlider(unittest.TestCase):
    """Glider moves diagonally and repeats every 4 generations."""

    def setUp(self):
        self.rows, self.cols = 40, 40
        self.grid = frozenset([(1, 2), (2, 3), (3, 1), (3, 2), (3, 3)])

    def test_period_4_translation(self):
        """After 4 generations, glider moves 1 down and 1 right."""
        g = self.grid
        for _ in range(4):
            g = step(g, self.rows, self.cols)
        expected = frozenset((r + 1, c + 1) for r, c in self.grid)
        self.assertEqual(g, expected)


class TestRandomGrid(unittest.TestCase):
    def test_size(self):
        g = random_grid(10, 10, density=1.0)
        self.assertEqual(len(g), 100)

    def test_empty_density(self):
        g = random_grid(10, 10, density=0.0)
        self.assertEqual(len(g), 0)

    def test_bounds(self):
        rows, cols = 15, 20
        g = random_grid(rows, cols)
        for r, c in g:
            self.assertGreaterEqual(r, 0)
            self.assertLess(r, rows)
            self.assertGreaterEqual(c, 0)
            self.assertLess(c, cols)


class TestPatterns(unittest.TestCase):
    def test_glider_loads(self):
        g = load_pattern("glider", 20, 20)
        self.assertEqual(len(g), 5)

    def test_blinker_loads(self):
        g = load_pattern("blinker", 20, 20)
        self.assertEqual(len(g), 3)

    def test_pulsar_loads(self):
        g = load_pattern("pulsar", 30, 40)
        self.assertEqual(len(g), len(PULSAR_CELLS))

    def test_gosper_gun_loads(self):
        g = load_pattern("gosper_gun", 50, 50)
        self.assertEqual(len(g), len(GOSPER_GUN_CELLS))

    def test_random_loads(self):
        g = load_pattern("random", 20, 20)
        self.assertGreater(len(g), 0)

    def test_unknown_pattern_raises(self):
        with self.assertRaises(ValueError):
            load_pattern("invalid_pattern", 10, 10)

    def test_pattern_within_bounds(self):
        for name in ["glider", "blinker", "pulsar", "gosper_gun"]:
            rows, cols = 50, 50
            g = load_pattern(name, rows, cols)
            for r, c in g:
                self.assertGreaterEqual(r, 0, f"{name}: row {r} out of bounds")
                self.assertLess(r, rows, f"{name}: row {r} out of bounds")
                self.assertGreaterEqual(c, 0, f"{name}: col {c} out of bounds")
                self.assertLess(c, cols, f"{name}: col {c} out of bounds")

    def test_center(self):
        cells = [(0, 0), (1, 1)]
        g = _center(cells, 10, 10)
        rs = [r for r, _ in g]
        cs = [c for _, c in g]
        # Should be roughly centered
        self.assertGreater(min(rs), 0)
        self.assertLess(max(rs), 10)
        self.assertGreater(min(cs), 0)
        self.assertLess(max(cs), 10)


class TestPulsar(unittest.TestCase):
    """Pulsar oscillates with period 3."""

    def test_period_3(self):
        rows, cols = 40, 40
        g = load_pattern("pulsar", rows, cols)
        g3 = g
        for _ in range(3):
            g3 = step(g3, rows, cols)
        self.assertEqual(g3, g)


class TestPersistence(unittest.TestCase):
    def test_save_load_roundtrip(self):
        grid = frozenset([(1, 2), (3, 4), (5, 6)])
        rows, cols, generation = 20, 20, 42
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_grid(grid, rows, cols, path, generation)
            loaded, lrows, lcols, lgen = load_grid(path)
            self.assertEqual(loaded, grid)
            self.assertEqual(lrows, rows)
            self.assertEqual(lcols, cols)
            self.assertEqual(lgen, generation)
        finally:
            os.unlink(path)

    def test_save_json_structure(self):
        grid = frozenset([(0, 0), (1, 1)])
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_grid(grid, 10, 10, path, 5)
            with open(path) as f:
                data = json.load(f)
            self.assertIn("rows", data)
            self.assertIn("cols", data)
            self.assertIn("generation", data)
            self.assertIn("cells", data)
            self.assertEqual(data["generation"], 5)
            self.assertEqual(len(data["cells"]), 2)
        finally:
            os.unlink(path)

    def test_load_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_grid("/tmp/does_not_exist_clawy.json")


class TestWrapAround(unittest.TestCase):
    """Cells on edges should wrap around (toroidal grid)."""

    def test_glider_wraps_vertically(self):
        rows, cols = 5, 20
        # Place glider near bottom edge — it should wrap
        g = frozenset([(rows - 2, 5), (rows - 1, 6), (0, 4), (0, 5), (0, 6)])
        # Just ensure step doesn't crash and returns valid cells
        new = step(g, rows, cols)
        for r, c in new:
            self.assertGreaterEqual(r, 0)
            self.assertLess(r, rows)
            self.assertGreaterEqual(c, 0)
            self.assertLess(c, cols)


if __name__ == "__main__":
    unittest.main()
