"""Geniş ağ, bağımsız maliyet doğrulaması ve toplu hedef sorguları."""

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ayros.model import NodeType, RoadStatus
from ayros.routing import CostModel, find_shortest_path
from ayros.scenario import load_scenario
from ayros.visualize import write_svg
from scripts.generate_week3_scenario import build_scenario


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "hafta3_genis_ag.json"


class LargeScenarioTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario(SAMPLE)

    def test_topology_and_measurements_are_reproducible(self):
        self.assertEqual(json.loads(SAMPLE.read_text(encoding="utf-8")), build_scenario())
        graph = self.scenario.graph
        self.assertEqual(len(graph.nodes), 30)
        self.assertEqual(len(graph.roads), 55)
        self.assertEqual([sum(n.node_type == kind for n in graph.nodes.values())
                          for kind in (NodeType.AID_CENTER, NodeType.DISASTER_AREA, NodeType.INTERSECTION)], [2, 6, 22])
        self.assertEqual([sum(r.status == status for r in graph.roads.values())
                          for status in (RoadStatus.OPEN, RoadStatus.DAMAGED, RoadStatus.CLOSED)], [39, 10, 6])
        for road in graph.roads.values():
            a, b = graph.nodes[road.source], graph.nodes[road.target]
            self.assertGreaterEqual(road.distance_km, math.hypot(a.x_km-b.x_km, a.y_km-b.y_km))

    def test_both_centers_and_damage_factors_match_independent_relaxation(self):
        # Referans Bellman-Ford: öncelik kuyruğu veya üretim CostModel'i kullanılmaz.
        graph = self.scenario.graph
        targets = [n.id for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA]
        for factor in (1, 2):
            for start in ("H0", "H1"):
                distances = {n: math.inf for n in graph.nodes}
                distances[start] = 0
                for _ in range(len(graph.nodes) - 1):
                    changed = False
                    for road in graph.roads.values():
                        if road.status == RoadStatus.CLOSED:
                            continue
                        weight = road.travel_time_min * (factor if road.status == RoadStatus.DAMAGED else 1)
                        for a, b in ((road.source, road.target), (road.target, road.source)):
                            candidate = distances[a] + weight
                            if candidate < distances[b]:
                                distances[b] = candidate
                                changed = True
                    if not changed:
                        break
                for target in targets:
                    route = find_shortest_path(graph, start, target, cost_model=CostModel(factor))
                    with self.subTest(factor=factor, start=start, target=target):
                        self.assertEqual(route.found, math.isfinite(distances[target]))
                        if route.found:
                            self.assertAlmostEqual(route.cost_min, distances[target])
                            self.assertFalse(any(graph.roads[r].status == RoadStatus.CLOSED for r in route.road_ids))
                        else:
                            self.assertIsNone(route.cost_min)

    def test_damage_changes_route_in_large_network(self):
        graph = self.scenario.graph
        normal = find_shortest_path(graph, "H0", "A3")
        no_penalty = find_shortest_path(graph, "H0", "A3", cost_model=CostModel(1))
        self.assertAlmostEqual(normal.cost_min, 38.14)
        self.assertAlmostEqual(no_penalty.cost_min, 31.24)
        self.assertNotEqual(normal.path, no_penalty.path)
        self.assertAlmostEqual(normal.base_time_min, 32.64)
        self.assertAlmostEqual(normal.distance_km, 15.4)

    def test_isolated_area_retains_closed_roads_but_is_unreachable(self):
        graph = self.scenario.graph
        self.assertEqual(len(graph.neighbors("A6", traversable_only=False)), 3)
        self.assertEqual(graph.neighbors("A6"), [])
        for center in ("H0", "H1"):
            route = find_shortest_path(graph, center, "A6")
            self.assertFalse(route.found)
            self.assertEqual(route.settled_nodes, 29)

    def test_large_svg_labels_match_selected_cost_model(self):
        graph = self.scenario.graph
        model = CostModel(1)
        route = find_shortest_path(graph, "H0", "A3", cost_model=model)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.svg"
            write_svg(self.scenario, path, route=route, cost_model=model)
            root = ET.parse(path).getroot()
            ns = {"s": "http://www.w3.org/2000/svg"}
            self.assertEqual(len(root.findall(".//s:circle", ns)), 30)
            self.assertEqual(len(root.findall(".//s:line", ns)), 55)
            self.assertEqual(root.attrib["width"], "1280")
            for road in graph.roads.values():
                group = next(e for e in root.iter() if e.get("data-road-id") == road.id)
                label = " ".join(e.text for e in group.findall("s:text", ns))
                expected = "kapalı" if road.status == RoadStatus.CLOSED else f"{model.cost_minutes(road):.2f} dk"
                self.assertIn(expected, label)
            highlighted = {e.get("data-route-road") for e in root.iter() if e.get("data-route-road")}
            self.assertEqual(highlighted, set(route.road_ids))

    def test_cli_all_targets_and_invalid_option_combinations(self):
        cases = [(["--start", "H0", "--all-targets"], 0, "Erişilebilir afet noktası: 5/6"),
                 (["--start", "H1", "--all-targets"], 0, "A6: Rota bulunamadı"),
                 (["--all-targets"], 2, "birlikte"),
                 (["--start", "H0", "--all-targets", "--target", "A1"], 2, "not allowed"),
                 (["--start", "H0", "--all-targets", "--svg", "unused.svg"], 2, "tek bir"),
                 (["--start", "unknown", "--all-targets"], 1, "bulunamadı"),
                 (["--start", "H0", "--target", "A6"], 3, "Rota bulunamadı")]
        for args, code, message in cases:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-m", "ayros", *args], cwd=ROOT,
                                        capture_output=True, text=True, encoding="utf-8", timeout=10,
                                        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(result.returncode, code)
                self.assertIn(message, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
