"""A* doğruluğu, sezgisel alt sınır ve tekrarlı karşılaştırma kontrolleri."""

import copy
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from ayros.benchmark import compare_algorithms
from ayros.model import Graph, Node, NodeType, Road, RoadStatus, ValidationError
from ayros.routing import CostModel, _time_heuristic, find_shortest_path
from ayros.scenario import load_scenario
from ayros.visualize import write_svg


ROOT = Path(__file__).resolve().parents[1]
LARGE = ROOT / "data/hafta3_genis_ag.json"
SMALL = ROOT / "data/hafta3_ornek.json"


def reference_costs(graph, start, factor=2):
    """Bağımsız Bellman-Ford; üretim maliyet fonksiyonu kullanılmaz."""
    distances = dict.fromkeys(graph.nodes, math.inf)
    distances[start] = 0
    for _ in range(len(graph.nodes) - 1):
        changed = False
        for road in graph.roads.values():
            if road.status == RoadStatus.CLOSED:
                continue
            cost = road.travel_time_min * (factor if road.status == RoadStatus.DAMAGED else 1)
            for a, b in ((road.source, road.target), (road.target, road.source)):
                candidate = distances[a] + cost
                if candidate < distances[b]:
                    distances[b] = candidate
                    changed = True
        if not changed:
            break
    return distances


class AStarTests(unittest.TestCase):
    def test_manual_example_damage_and_input_immutability(self):
        graph = load_scenario(SMALL).graph
        before = copy.deepcopy((graph.nodes, graph.roads))
        for factor, expected, cost in ((1, ("S", "B", "T"), 4), (2, ("S", "C", "T"), 5)):
            with self.subTest(factor=factor):
                result = find_shortest_path(graph, "S", "T", algorithm="astar", cost_model=CostModel(factor))
                self.assertEqual(result.algorithm, "astar")
                self.assertEqual(result.path, expected)
                self.assertEqual(result.cost_min, cost)
                self.assertNotIn("ST", result.road_ids)
        self.assertEqual(before, (graph.nodes, graph.roads))

    def test_seeded_arbitrary_geometry_matches_independent_reference(self):
        # Uzaklık/hız ilişkisi varsayılmaz: kısa sürede çok uzak bir kenar da olabilir.
        rng = random.Random(20261026)
        for case in range(12):
            nodes = [Node(str(i), str(i), NodeType.INTERSECTION, rng.uniform(-20, 20), rng.uniform(-20, 20))
                     for i in range(7)]
            roads = []
            for a in range(7):
                for b in range(a + 1, 7):
                    if rng.random() < 0.45:
                        roads.append(Road(f"{a}-{b}", str(a), str(b), 1,
                                          rng.choice((0.01, 1, 3, 7)), rng.choice(list(RoadStatus))))
            graph = Graph(nodes, roads)
            for factor in (1, 2):
                expected = reference_costs(graph, "0", factor)
                for target in map(str, range(1, 7)):
                    route = find_shortest_path(graph, "0", target, algorithm="astar", cost_model=CostModel(factor))
                    with self.subTest(case=case, factor=factor, target=target):
                        self.assertEqual(route.found, math.isfinite(expected[target]))
                        if route.found:
                            self.assertAlmostEqual(route.cost_min, expected[target])
                            self.assertEqual(route.path[0], "0")
                            self.assertEqual(route.path[-1], target)
                        else:
                            self.assertIsNone(route.cost_min)

    def test_heuristic_is_consistent_and_admissible_in_all_fixtures(self):
        for path in (SMALL, LARGE, ROOT / "data/hafta2_senaryo.json"):
            graph = load_scenario(path).graph
            for factor in (1, 2):
                costs = {r.id: CostModel(factor).cost_minutes(r) for r in graph.roads.values()}
                for target in graph.nodes:
                    h = _time_heuristic(graph, target, costs)
                    remaining = reference_costs(graph, target, factor)
                    with self.subTest(scenario=path.name, factor=factor, target=target):
                        self.assertEqual(h[target], 0)
                        for node, value in h.items():
                            self.assertGreaterEqual(value, 0)
                            self.assertLessEqual(value, remaining[node] + 1e-9)
                        for road in graph.roads.values():
                            if costs[road.id] is not None:
                                self.assertLessEqual(abs(h[road.source] - h[road.target]), costs[road.id] + 1e-9)

    def test_main_network_costs_match_reference_for_both_centers(self):
        graph = load_scenario(LARGE).graph
        for factor in (1, 2):
            for start in ("H0", "H1"):
                expected = reference_costs(graph, start, factor)
                for target in ("A1", "A2", "A3", "A4", "A5", "A6"):
                    route = find_shortest_path(graph, start, target, algorithm="astar", cost_model=CostModel(factor))
                    with self.subTest(factor=factor, start=start, target=target):
                        self.assertEqual(route.found, math.isfinite(expected[target]))
                        if route.found:
                            self.assertAlmostEqual(route.cost_min, expected[target])
                            self.assertFalse(any(graph.roads[r].status == RoadStatus.CLOSED for r in route.road_ids))

    def test_goal_direction_avoids_unnecessary_branch_expansion(self):
        positions = dict(S=(0, 0), A=(1, 0), T=(3, 0), B=(0, 1), C=(0, 2), D=(0, 3))
        nodes = [Node(n, n, NodeType.INTERSECTION, *xy) for n, xy in positions.items()]
        edges = [("S", "A", 1), ("A", "T", 2), ("S", "B", 1), ("B", "C", 1), ("C", "D", 1)]
        roads = [Road(str(i), a, b, 1, cost, RoadStatus.OPEN) for i, (a, b, cost) in enumerate(edges)]
        roads.append(Road("closed", "S", "D", 1, 0.001, RoadStatus.CLOSED))
        graph = Graph(nodes, roads)
        dijkstra = find_shortest_path(graph, "S", "T")
        astar = find_shortest_path(graph, "S", "T", algorithm="astar")
        self.assertEqual(astar.cost_min, dijkstra.cost_min)
        self.assertEqual(astar.cost_min, 3)
        self.assertLess(astar.settled_nodes, dijkstra.settled_nodes)

    def test_zero_or_extreme_geometry_falls_back_safely(self):
        for positions in (((0, 0), (0, 0)), ((-1e308, 0), (1e308, 0))):
            graph = Graph([Node(n, n, NodeType.INTERSECTION, *xy) for n, xy in zip(("S", "T"), positions)],
                          [Road("ST", "S", "T", 1, 2, RoadStatus.OPEN)])
            self.assertEqual(_time_heuristic(graph, "T", {"ST": 2}), {"S": 0, "T": 0})
            self.assertEqual(find_shortest_path(graph, "S", "T", algorithm="astar").cost_min, 2)

    def test_same_node_unreachable_and_invalid_inputs(self):
        graph = load_scenario(LARGE).graph
        same = find_shortest_path(graph, "H0", "H0", algorithm="astar")
        self.assertEqual((same.path, same.cost_min, same.settled_nodes), (("H0",), 0, 1))
        missing = find_shortest_path(graph, "H0", "A6", algorithm="astar")
        self.assertFalse(missing.found)
        self.assertIsNone(missing.cost_min)
        self.assertEqual(missing.settled_nodes, 39)
        for algorithm in ("A*", "unknown", None, []):
            with self.subTest(algorithm=algorithm), self.assertRaises(ValidationError):
                find_shortest_path(graph, "H0", "A5", algorithm=algorithm)
        with self.assertRaises(ValidationError):
            find_shortest_path(graph, "unknown", "A5", algorithm="astar")

    def test_svg_identifies_astar_and_highlights_its_route(self):
        scenario = load_scenario(LARGE)
        route = find_shortest_path(scenario.graph, "H0", "A5", algorithm="astar")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "astar.svg"
            write_svg(scenario, path, route=route, cost_model=CostModel())
            root = ET.parse(path).getroot()
            text = "".join(root.itertext())
            self.assertIn("A* rotası", text)
            self.assertNotIn("Dijkstra rotası", text)
            self.assertEqual({e.get("data-route-road") for e in root.iter() if e.get("data-route-road")}, set(route.road_ids))


class BenchmarkTests(unittest.TestCase):
    def test_warmups_are_excluded_and_order_alternates(self):
        graph = load_scenario(SMALL).graph
        template = find_shortest_path(graph, "S", "T")
        calls = []

        def measured(*args, algorithm, **kwargs):
            calls.append(algorithm)
            # İlk iki tur ölçüme girmemeli.
            elapsed = 99 if len(calls) <= 4 else (3 if algorithm == "dijkstra" else 5)
            return replace(template, algorithm=algorithm, elapsed_ms=elapsed)

        with patch("ayros.benchmark.find_shortest_path", side_effect=measured):
            result = compare_algorithms(graph, "S", "T", repeats=3, warmups=2)
        self.assertEqual(calls, ["dijkstra", "astar", "astar", "dijkstra", "dijkstra", "astar", "astar", "dijkstra", "dijkstra", "astar"])
        self.assertEqual(result.dijkstra.samples_ms, (3, 3, 3))
        self.assertEqual(result.astar.median_ms, 5)
        self.assertEqual((result.repeats, result.warmups), (3, 2))

    def test_invalid_measurement_counts_and_mismatching_costs_are_rejected(self):
        graph = load_scenario(SMALL).graph
        for repeats in (0, -1, 1001, True, 1.5):
            with self.subTest(repeats=repeats), self.assertRaises(ValidationError):
                compare_algorithms(graph, "S", "T", repeats=repeats)
        for warmups in (-1, 101, True):
            with self.subTest(warmups=warmups), self.assertRaises(ValidationError):
                compare_algorithms(graph, "S", "T", warmups=warmups)
        template = find_shortest_path(graph, "S", "T")
        with patch("ayros.benchmark.find_shortest_path", side_effect=[template, replace(template, cost_min=999)]):
            with self.assertRaisesRegex(ValidationError, "uyuşmuyor"):
                compare_algorithms(graph, "S", "T", repeats=1, warmups=0)

    def test_cli_algorithms_comparisons_and_invalid_combinations(self):
        cases = [(["--start", "H0", "--target", "A5", "--algorithm", "astar"], 0, "A* | H0 -> A5"),
                 (["--start", "H0", "--all-targets", "--algorithm", "astar"], 0, "5/6"),
                 (["--start", "H0", "--target", "A5", "--compare", "--repeats", "2"], 0, "Ortak en düşük maliyet: 38.08"),
                 (["--start", "H0", "--target", "A6", "--compare", "--repeats", "1"], 3, "Rota bulunamadı"),
                 (["--start", "H0", "--all-targets", "--compare", "--repeats", "1"], 0, "5/6"),
                 (["--compare"], 2, "başlangıç"),
                 (["--repeats", "2"], 2, "yalnızca"),
                 (["--start", "H0", "--target", "A5", "--compare", "--repeats", "0"], 2, "1-1000"),
                 (["--start", "H0", "--target", "A5", "--compare", "--svg", "unused.svg"], 2, "SVG"),
                 (["--compare", "--algorithm", "astar"], 2, "not allowed")]
        for args, status, expected in cases:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-m", "ayros", *args], cwd=ROOT,
                                        text=True, capture_output=True, encoding="utf-8", timeout=15,
                                        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertIn(expected, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_experiment_script_exports_all_queries_and_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results.json"
            result = subprocess.run([sys.executable, "scripts/compare_algorithms.py", "--repeats", "2", "--output", str(output)],
                                    cwd=ROOT, text=True, capture_output=True, encoding="utf-8", timeout=15,
                                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["results"]), 24)
            self.assertEqual(len({(r["start"], r["target"], r["damage_factor"]) for r in payload["results"]}), 24)
            for row in payload["results"]:
                self.assertEqual(row["dijkstra"]["route"]["found"], row["astar"]["route"]["found"])
                for algorithm in ("dijkstra", "astar"):
                    self.assertEqual(len(row[algorithm]["samples_ms"]), 2)
                    self.assertEqual(row[algorithm]["route"]["algorithm"], algorithm)
                    self.assertGreaterEqual(row[algorithm]["median_ms"], 0)


if __name__ == "__main__":
    unittest.main()
