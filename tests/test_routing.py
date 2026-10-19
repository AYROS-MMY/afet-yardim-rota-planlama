"""Dijkstra doğruluğu, sınır durumları ve kullanıcıya sunulan rota çıktısı."""

import copy
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ayros.model import Graph, Node, NodeType, Road, RoadStatus, ValidationError
from ayros.routing import CostModel, find_shortest_path
from ayros.scenario import load_scenario, scenario_from_dict
from ayros.visualize import write_svg


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "hafta3_ornek.json"


def small_graph(edges, node_ids="SABT"):
    nodes = [Node(n, n, NodeType.INTERSECTION, i, 0) for i, n in enumerate(node_ids)]
    roads = [Road(f"R{i}", a, b, 1, cost, RoadStatus.OPEN)
             for i, (a, b, cost) in enumerate(edges)]
    return Graph(nodes, roads)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario(SAMPLE)

    def test_manual_example_selects_lowest_time_not_shortest_distance(self):
        route = find_shortest_path(self.scenario.graph, "S", "T")
        self.assertTrue(route.found)
        self.assertEqual(route.path, ("S", "C", "T"))
        self.assertEqual(route.road_ids, ("SC", "CT"))
        self.assertEqual(route.cost_min, 5)
        self.assertEqual(route.base_time_min, 5)
        self.assertAlmostEqual(route.distance_km, 3.2)
        self.assertEqual(route.settled_nodes, 4)
        self.assertGreaterEqual(route.elapsed_ms, 0)

    def test_damage_factor_changes_route_and_keeps_base_time_separate(self):
        graph = self.scenario.graph
        route = find_shortest_path(graph, "S", "T", cost_model=CostModel(1.25))
        self.assertEqual(route.path, ("S", "B", "T"))
        self.assertEqual(route.cost_min, 4.5)
        self.assertEqual(route.base_time_min, 4)
        self.assertEqual(route.distance_km, 3)
        self.assertEqual(find_shortest_path(graph, "S", "T", cost_model=CostModel(1)).cost_min, 4)

    def test_closed_shortcut_is_excluded(self):
        graph = self.scenario.graph
        self.assertIsNone(CostModel().cost_minutes(graph.roads["ST"]))
        self.assertNotIn("ST", find_shortest_path(graph, "S", "T").road_ids)

    def test_search_does_not_stop_at_first_discovery_of_target(self):
        graph = small_graph([("S", "T", 10), ("S", "A", 1), ("A", "T", 1)])
        route = find_shortest_path(graph, "S", "T")
        self.assertEqual(route.path, ("S", "A", "T"))
        self.assertEqual(route.cost_min, 2)

    def test_old_queue_entries_are_not_counted_twice(self):
        graph = small_graph([("S", "A", 8), ("S", "B", 1), ("B", "A", 1), ("A", "T", 20)])
        route = find_shortest_path(graph, "S", "T")
        self.assertEqual(route.path, ("S", "B", "A", "T"))
        self.assertEqual(route.cost_min, 22)
        self.assertEqual(route.settled_nodes, 4)

    def test_unreachable_target_has_no_fictitious_zero_cost(self):
        route = find_shortest_path(small_graph([("S", "A", 1)]), "S", "T")
        self.assertFalse(route.found)
        self.assertEqual(route.path, ())
        self.assertEqual(route.road_ids, ())
        self.assertIsNone(route.cost_min)
        self.assertIsNone(route.distance_km)
        self.assertIsNone(route.base_time_min)
        self.assertEqual(route.settled_nodes, 2)

    def test_same_start_and_target_is_valid_zero_length_route(self):
        route = find_shortest_path(self.scenario.graph, "S", "S")
        self.assertTrue(route.found)
        self.assertEqual(route.path, ("S",))
        self.assertEqual(route.road_ids, ())
        self.assertEqual((route.cost_min, route.distance_km, route.base_time_min), (0, 0, 0))
        self.assertEqual(route.settled_nodes, 1)

    def test_unknown_or_invalid_endpoints_are_rejected(self):
        for start, target in (("missing", "T"), ("S", "missing"), ("", "T"), ("S", None)):
            with self.subTest(start=start, target=target), self.assertRaises(ValidationError):
                find_shortest_path(self.scenario.graph, start, target)

    def test_invalid_damage_factors_are_rejected(self):
        for value in (-1, 0, 0.9, True, "2", float("inf"), float("nan"), 10**400):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                CostModel(value)

    def test_numeric_overflow_is_reported_as_validation_error(self):
        road = Road("R", "S", "T", 1, 1e308, RoadStatus.DAMAGED)
        with self.assertRaises(ValidationError):
            CostModel(2).cost_minutes(road)
        graph = small_graph([("S", "A", 1e308), ("A", "T", 1e308)])
        with self.assertRaises(ValidationError):
            find_shortest_path(graph, "S", "T")

    def test_equal_cost_routes_return_a_valid_optimum(self):
        graph = small_graph([("S", "A", 1), ("A", "T", 1), ("S", "B", 1), ("B", "T", 1)])
        route = find_shortest_path(graph, "S", "T")
        self.assertEqual(route.cost_min, 2)
        self.assertIn(route.path, (("S", "A", "T"), ("S", "B", "T")))

    def test_search_does_not_modify_scenario(self):
        graph = self.scenario.graph
        before = copy.deepcopy((graph.nodes, graph.roads, [graph.neighbors(n, traversable_only=False) for n in graph.nodes]))
        find_shortest_path(graph, "S", "T")
        find_shortest_path(graph, "S", "T", cost_model=CostModel(3))
        after = (graph.nodes, graph.roads, [graph.neighbors(n, traversable_only=False) for n in graph.nodes])
        self.assertEqual(before, after)

    def test_reverse_direction_has_same_cost(self):
        route = find_shortest_path(self.scenario.graph, "T", "S")
        self.assertEqual(route.path, ("T", "C", "S"))
        self.assertEqual(route.cost_min, 5)

    def test_previous_week_scenario_can_be_routed(self):
        graph = load_scenario(ROOT / "data" / "hafta2_senaryo.json").graph
        route = find_shortest_path(graph, "H0", "A1")
        self.assertEqual(route.path, ("H0", "K1", "K3", "K5", "A2", "A1"))
        self.assertAlmostEqual(route.cost_min, 27.44)
        self.assertAlmostEqual(route.base_time_min, 23.04)
        self.assertAlmostEqual(route.distance_km, 11.52)

    def test_seeded_small_graphs_match_exhaustive_path_enumeration(self):
        # Bağımsız kontrol: Küçük ağlarda bütün tekrarsız yolları sırala.
        # Bu kontrol öncelik kuyruğu veya Dijkstra güncellemesi kullanmaz.
        rng = random.Random(2026)
        for case in range(12):
            nodes = [Node(str(i), str(i), NodeType.INTERSECTION, i, 0) for i in range(5)]
            roads = []
            adjacency = {node.id: [] for node in nodes}
            for a in range(5):
                for b in range(a + 1, 5):
                    if rng.random() < 0.6:
                        status = rng.choice(list(RoadStatus))
                        duration = rng.randint(1, 9)
                        roads.append(Road(f"{a}-{b}", str(a), str(b), 1, duration, status))
                        if status != RoadStatus.CLOSED:
                            weight = duration * (2 if status == RoadStatus.DAMAGED else 1)
                            adjacency[str(a)].append((str(b), weight))
                            adjacency[str(b)].append((str(a), weight))
            graph = Graph(nodes, roads)
            for target in ("1", "2", "3", "4"):
                totals = []

                def enumerate_paths(current, seen, total):
                    if current == target:
                        totals.append(total)
                        return
                    for neighbor, cost in adjacency[current]:
                        if neighbor not in seen:
                            enumerate_paths(neighbor, seen | {neighbor}, total + cost)

                enumerate_paths("0", {"0"}, 0)
                route = find_shortest_path(graph, "0", target)
                with self.subTest(case=case, target=target):
                    self.assertEqual(route.found, bool(totals))
                    self.assertEqual(route.cost_min, min(totals) if totals else None)

    def test_svg_highlights_exactly_the_selected_roads(self):
        route = find_shortest_path(self.scenario.graph, "S", "T")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "route.svg"
            write_svg(self.scenario, path, route=route)
            root = ET.parse(path).getroot()
            highlighted = [e.attrib["data-route-road"] for e in root.iter() if "data-route-road" in e.attrib]
            self.assertEqual(set(highlighted), {"SC", "CT"})
            self.assertIn("5.00 dk", "".join(root.itertext()))

    def test_unreachable_route_svg_has_message_without_highlight(self):
        data = json.loads(SAMPLE.read_text(encoding="utf-8"))
        data["roads"] = []
        scenario = scenario_from_dict(data)
        route = find_shortest_path(scenario.graph, "S", "T")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unreachable.svg"
            write_svg(scenario, path, route=route)
            root = ET.parse(path).getroot()
            self.assertFalse(any("data-route-road" in e.attrib for e in root.iter()))
            self.assertIn("Rota bulunamadı", "".join(root.itertext()))

    def test_cli_route_output_and_error_codes(self):
        cases = [(["--start", "S", "--target", "T"], 0, "Rota: S -> C -> T"),
                 (["--start", "S", "--target", "T", "--damage-factor", "1"], 0, "4.00 dk"),
                 (["--start", "S"], 2, "birlikte"),
                 (["--start", "S", "--target", "unknown"], 1, "bulunamadı"),
                 (["--damage-factor", "nan"], 1, "Hasar katsayısı")]
        for args, code, message in cases:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-m", "ayros", str(SAMPLE), *args],
                                        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                                        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=10)
                self.assertEqual(result.returncode, code)
                self.assertIn(message, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_cli_unreachable_target_returns_three_and_writes_svg(self):
        data = json.loads(SAMPLE.read_text(encoding="utf-8"))
        data["roads"] = []
        with tempfile.TemporaryDirectory() as directory:
            path, svg = Path(directory) / "empty.json", Path(directory) / "empty.svg"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "ayros", str(path), "--start", "S", "--target", "T", "--svg", str(svg)],
                                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                                    env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=10)
            self.assertEqual(result.returncode, 3)
            self.assertIn("Rota bulunamadı", result.stdout)
            self.assertNotIn("Traceback", result.stderr)
            self.assertTrue(svg.is_file())


if __name__ == "__main__":
    unittest.main()
