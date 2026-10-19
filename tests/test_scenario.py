"""Veri sözleşmesini ve kapalı yol davranışını doğrulayan ikinci hafta testleri."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ayros.model import NodeType, RoadStatus, ValidationError
from ayros.scenario import load_scenario, scenario_from_dict
from ayros.visualize import write_svg


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "hafta2_senaryo.json"


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(SAMPLE.read_text(encoding="utf-8"))

    def test_sample_counts_and_types(self):
        graph = load_scenario(SAMPLE).graph
        self.assertEqual(len(graph.nodes), 10)
        self.assertEqual(len(graph.roads), 14)
        self.assertEqual(sum(n.node_type == NodeType.DISASTER_AREA for n in graph.nodes.values()), 3)
        self.assertEqual(sum(n.node_type == NodeType.AID_CENTER for n in graph.nodes.values()), 1)
        self.assertEqual([sum(r.status == status for r in graph.roads.values())
                          for status in RoadStatus], [9, 3, 2])

    def test_roads_are_bidirectional(self):
        graph = load_scenario(SAMPLE).graph
        self.assertIn(("K1", graph.roads["R01"]), graph.neighbors("H0"))
        self.assertIn(("H0", graph.roads["R01"]), graph.neighbors("K1"))

    def test_closed_road_is_retained_but_not_traversable(self):
        graph = load_scenario(SAMPLE).graph
        self.assertIn(("K2", graph.roads["R03"]), graph.neighbors("K1", traversable_only=False))
        self.assertNotIn(("K2", graph.roads["R03"]), graph.neighbors("K1"))

    def test_damaged_road_is_traversable_without_changing_input_time(self):
        graph = load_scenario(SAMPLE).graph
        self.assertIn(("K5", graph.roads["R07"]), graph.neighbors("K3"))
        self.assertEqual(graph.roads["R07"].travel_time_min, self.data["roads"][6]["travel_time_min"])

    def test_duplicate_node_is_rejected(self):
        self.data["nodes"].append(copy.deepcopy(self.data["nodes"][0]))
        with self.assertRaisesRegex(ValidationError, "Tekrarlanan düğüm"):
            scenario_from_dict(self.data)

    def test_duplicate_road_id_is_rejected(self):
        self.data["roads"][1]["id"] = "R01"
        with self.assertRaisesRegex(ValidationError, "Tekrarlanan yol"):
            scenario_from_dict(self.data)

    def test_duplicate_reverse_road_is_rejected(self):
        road = dict(self.data["roads"][0], id="R99", source="K1", target="H0")
        self.data["roads"].append(road)
        with self.assertRaisesRegex(ValidationError, "ikinci yol"):
            scenario_from_dict(self.data)

    def test_missing_endpoint_is_rejected(self):
        self.data["roads"][0]["target"] = "missing"
        with self.assertRaisesRegex(ValidationError, "düğüm bulunamadı"):
            scenario_from_dict(self.data)

    def test_invalid_measurements_are_rejected(self):
        for field in ("distance_km", "travel_time_min"):
            for value in (-1, 0, True, "3", float("inf"), float("nan")):
                with self.subTest(field=field, value=value):
                    data = copy.deepcopy(self.data)
                    data["roads"][0][field] = value
                    with self.assertRaises(ValidationError):
                        scenario_from_dict(data)

    def test_invalid_status_is_rejected(self):
        self.data["roads"][0]["status"] = "unknown"
        with self.assertRaisesRegex(ValidationError, "Yol kaydı 1"):
            scenario_from_dict(self.data)

    def test_missing_and_invalid_coordinates_are_rejected(self):
        for value in (None, True, float("nan")):
            with self.subTest(value=value):
                self.data["nodes"][0]["x_km"] = value
                with self.assertRaises(ValidationError):
                    scenario_from_dict(self.data)
        del self.data["nodes"][0]["x_km"]
        with self.assertRaises(ValidationError):
            scenario_from_dict(self.data)

    def test_empty_graph_is_rejected(self):
        self.data["nodes"] = []
        with self.assertRaisesRegex(ValidationError, "en az bir düğüm"):
            scenario_from_dict(self.data)

    def test_disconnected_nodes_are_valid(self):
        self.data["roads"] = []
        graph = scenario_from_dict(self.data).graph
        self.assertEqual(graph.neighbors("H0"), [])

    def test_unknown_node_query_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "Düğüm bulunamadı"):
            load_scenario(SAMPLE).graph.neighbors("missing")

    def test_disaster_data_is_validated(self):
        for field, value in (("injured_count", 999), ("affected_count", -1),
                             ("urgency_level", 6), ("urgency_level", 0)):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data["nodes"][-1][field] = value
                with self.assertRaises(ValidationError):
                    scenario_from_dict(data)

    def test_bad_schema_is_rejected(self):
        for field, value in (("directed", True), ("coordinate_system", "lat_lon"),
                             ("schema_version", 2), ("nodes", {}), ("roads", None)):
            with self.subTest(field=field):
                data = dict(self.data, **{field: value})
                with self.assertRaises(ValidationError):
                    scenario_from_dict(data)

    def test_malformed_json_and_missing_file_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for contents in (None, "{invalid", "[]"):
                if contents is not None:
                    path.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValidationError):
                    load_scenario(path)

    def test_svg_contains_every_node_and_road_and_escapes_title(self):
        self.data["name"] = "Test <senaryo> & ağ"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.svg"
            write_svg(scenario_from_dict(self.data), path)
            root = ET.parse(path).getroot()
            ns = {"s": "http://www.w3.org/2000/svg"}
            self.assertEqual(len(root.findall(".//s:circle", ns)), 10)
            self.assertEqual(len(root.findall(".//s:line", ns)), 14)
            self.assertEqual(root.find("s:title", ns).text, self.data["name"])

    def test_cli_success_and_invalid_file_exit_codes(self):
        for args, expected in (([], 0), (["does-not-exist.json"], 1)):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-m", "ayros", *args],
                                        cwd=ROOT, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, expected)
                self.assertNotIn(b"Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
