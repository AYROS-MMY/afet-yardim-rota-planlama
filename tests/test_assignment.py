"""Kapasite, erişim, tek görev kuralı ve CLI çıktı sözleşmeleri."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ayros.assignment import DispatchInput, Vehicle, assign_vehicles, load_dispatch
from ayros.assignment_output import assignment_svg
from ayros.assignment_viewer import write_assignment_html
from ayros.model import Graph, Node, NodeType, Road, RoadStatus, ValidationError
from ayros.priority import rank_needs
from ayros.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.graph = load_scenario(ROOT/'data/bolgesel_ag.json').graph
        self.fleet = load_dispatch(ROOT/'data/arac_senaryosu.json', self.graph)

    def test_known_example(self):
        result = assign_vehicles(self.graph, self.fleet)
        self.assertEqual((result[0].need.node.id, result[0].vehicle.id), ('A08', 'V03'))
        self.assertAlmostEqual(result[0].route.cost_min, 30.585)
        self.assertEqual(sum(e.demand for e in result if e.vehicle), 340)
        self.assertEqual(sum(e.vehicle is not None for e in result), 5)

    def test_no_duplicate_assignments_or_capacity_overflow(self):
        result = assign_vehicles(self.graph, self.fleet)
        assigned = [e for e in result if e.vehicle]
        self.assertEqual(len(assigned), len({e.vehicle.id for e in assigned}))
        for e in assigned:
            self.assertLessEqual(e.demand, e.vehicle.capacity)
            self.assertTrue(e.vehicle.available)
            self.assertEqual((e.route.path[0], e.route.path[-1]), (e.vehicle.center, e.need.node.id))

    def test_priority_order_preserved(self):
        result = assign_vehicles(self.graph, self.fleet)
        self.assertEqual([e.need for e in result], list(rank_needs(self.graph)))

    def test_unavailable_vehicle_cannot_satisfy_large_demand(self):
        result = assign_vehicles(self.graph, self.fleet)
        self.assertEqual(result[2].status, 'insufficient_capacity')
        fleet = replace(self.fleet, vehicles=(Vehicle('V05', 'H2', 200, False),),
                        demands={**self.fleet.demands, 'A08': 200})
        self.assertEqual(assign_vehicles(self.graph, fleet)[0].status, 'no_available_vehicle')
        enabled = replace(fleet, vehicles=(Vehicle('V05', 'H2', 200, True),))
        self.assertEqual(assign_vehicles(self.graph, enabled)[0].vehicle.id, 'V05')

    def test_unreachable_target_retains_rank_and_demand(self):
        e = assign_vehicles(self.graph, self.fleet)[7]
        self.assertEqual((e.need.node.id, e.status, e.demand), ('A12', 'unreachable', 30))
        self.assertIsNone(e.route)

    def test_empty_fleet_has_explicit_reasons(self):
        result = assign_vehicles(self.graph, replace(self.fleet, vehicles=()))
        self.assertEqual(result[0].status, 'no_available_vehicle')
        self.assertEqual(result[7].status, 'unreachable')

    def test_exact_capacity_is_eligible(self):
        fleet = replace(self.fleet, vehicles=(Vehicle('V', 'H1', 120),))
        self.assertEqual(assign_vehicles(self.graph, fleet)[0].vehicle.id, 'V')

    def test_equal_travel_time_uses_vehicle_id(self):
        fleet = replace(self.fleet, vehicles=(Vehicle('Z', 'H1', 200), Vehicle('A', 'H1', 200)))
        self.assertEqual(assign_vehicles(self.graph, fleet)[0].vehicle.id, 'A')

    def test_input_order_does_not_change_assignments(self):
        a = assign_vehicles(self.graph, self.fleet)
        b = assign_vehicles(self.graph, replace(self.fleet, vehicles=tuple(reversed(self.fleet.vehicles))))
        self.assertEqual([(e.status, e.vehicle) for e in a], [(e.status, e.vehicle) for e in b])

    def test_dijkstra_and_astar_agree(self):
        a = assign_vehicles(self.graph, self.fleet, algorithm='astar')
        b = assign_vehicles(self.graph, self.fleet, algorithm='dijkstra')
        for x, y in zip(a, b):
            self.assertEqual((x.status, x.vehicle), (y.status, y.vehicle))
            if x.route:
                self.assertAlmostEqual(x.route.cost_min, y.route.cost_min)

    def test_repeated_calls_do_not_consume_input_fleet(self):
        a = assign_vehicles(self.graph, self.fleet)
        b = assign_vehicles(self.graph, self.fleet)
        self.assertEqual([e.vehicle for e in a], [e.vehicle for e in b])

    def test_invalid_vehicle_fields(self):
        for capacity in (0, -1, 1.5, True, '20'):
            with self.subTest(capacity=capacity), self.assertRaises(ValidationError):
                Vehicle('V', 'H0', capacity)
        with self.assertRaises(ValidationError):
            Vehicle('V', 'H0', 10, 'true')

    def test_invalid_center_duplicates_and_demand(self):
        bad = [replace(self.fleet, vehicles=(Vehicle('V','A01',50),)),
               replace(self.fleet, vehicles=(Vehicle('V','H0',50),Vehicle('V','H1',50))),
               replace(self.fleet, demands={}),
               replace(self.fleet, demands={**self.fleet.demands,'A01':True})]
        for fleet in bad:
            with self.subTest(fleet=fleet), self.assertRaises(ValidationError):
                assign_vehicles(self.graph, fleet)

    def test_invalid_algorithm_even_without_vehicles(self):
        with self.assertRaises(ValidationError):
            assign_vehicles(self.graph, replace(self.fleet,vehicles=()), algorithm='invalid')

    def test_reachable_target_but_vehicle_in_disconnected_center(self):
        graph = Graph([Node('H0','Merkez',NodeType.AID_CENTER,0,0),
                       Node('H1','Diğer',NodeType.AID_CENTER,2,0),
                       Node('A','Hedef',NodeType.DISASTER_AREA,1,0,10,0,5)],
                      [Road('R','H0','A',1,1,RoadStatus.OPEN)])
        result = assign_vehicles(graph,DispatchInput((Vehicle('V','H1',10),),{'A':10}))
        self.assertEqual(result[0].status,'no_reachable_vehicle')

    def test_greedy_limitation_is_explicit(self):
        graph = Graph([Node('H0','Yakın',NodeType.AID_CENTER,0,0),
                       Node('H1','Uzak',NodeType.AID_CENTER,2,0),
                       Node('A','Öncelikli',NodeType.DISASTER_AREA,1,0,10,0,5),
                       Node('B','Büyük talep',NodeType.DISASTER_AREA,0,1,10,0,4)],
                      [Road('R1','H0','A',1,1,RoadStatus.OPEN),
                       Road('R2','H1','A',1,2,RoadStatus.OPEN),
                       Road('R3','H0','B',1,1,RoadStatus.OPEN)])
        fleet=DispatchInput((Vehicle('BIG','H0',100),Vehicle('SMALL','H1',10)),{'A':10,'B':100})
        result=assign_vehicles(graph,fleet)
        self.assertEqual(result[0].vehicle.id,'BIG')
        self.assertEqual(result[1].status,'insufficient_capacity')
        # SMALL->A and BIG->B could serve both: this policy is not global optimization.

    def test_assigned_route_cost_matches_road_sum_and_avoids_closed_roads(self):
        for entry in assign_vehicles(self.graph,self.fleet):
            if not entry.route:
                continue
            roads=[self.graph.roads[rid] for rid in entry.route.road_ids]
            self.assertTrue(all(r.status != RoadStatus.CLOSED for r in roads))
            self.assertAlmostEqual(entry.route.cost_min,sum(r.travel_time_min*(2 if r.status == RoadStatus.DAMAGED else 1) for r in roads))

    def test_cli_json_svg_match_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result.json'
            svg = Path(temp)/'result.svg'
            run = subprocess.run([sys.executable,'-m','ayros.dispatch','--json',str(output),'--svg',str(svg)],cwd=ROOT,capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr)
            data = json.loads(output.read_text(encoding='utf-8'))
            elements = ET.parse(svg).getroot().iter()
            actual = {(el.get('data-vehicle'),el.get('data-road')) for el in elements if el.get('data-vehicle')}
            expected = {(e['vehicle']['id'],rid) for e in data['entries'] if e['vehicle'] for rid in e['route']['road_ids']}
            self.assertEqual(actual,expected)
            self.assertEqual(len(data['scenario_sha256']),64)

    def test_cli_rejects_input_overwrite(self):
        run = subprocess.run([sys.executable,'-m','ayros.dispatch','--fleet','data/arac_senaryosu.json','--json','data/arac_senaryosu.json'],cwd=ROOT,capture_output=True)
        self.assertEqual(run.returncode,2)

    def test_map_shows_all_fleet_members_including_unavailable(self):
        scenario = load_scenario(ROOT/'data/bolgesel_ag.json')
        result = assign_vehicles(self.graph,self.fleet)
        root = ET.fromstring(assignment_svg(scenario,result,fleet=self.fleet))
        centers = {e.get('data-center'): ''.join(e.itertext()) for e in root.iter() if e.get('data-center')}
        for vehicle in self.fleet.vehicles:
            self.assertIn(vehicle.id,centers[vehicle.center])
        self.assertIn('V05 müsait değil',centers['H2'])

    def test_svg_route_geometry_follows_travel_direction(self):
        scenario=load_scenario(ROOT/'data/bolgesel_ag.json')
        entries=assign_vehicles(self.graph,self.fleet)
        root=ET.fromstring(assignment_svg(scenario,entries,fleet=self.fleet))
        for e in entries:
            if not e.vehicle:
                continue
            lines=[el for el in root.iter() if el.get('data-vehicle')==e.vehicle.id]
            self.assertEqual([line.get('data-road') for line in lines],list(e.route.road_ids))
            # Consecutive directed segments must join, including reversed stored roads.
            for first,second in zip(lines,lines[1:]):
                self.assertEqual(first.get('points').split()[-1],second.get('points').split()[0])
            self.assertIsNotNone(lines[-1].get('marker-end'))

    def test_html_escapes_vehicle_identifiers(self):
        scenario=load_scenario(ROOT/'data/bolgesel_ag.json')
        unsafe='V<script>alert(1)</script>"'
        fleet=replace(self.fleet,vehicles=(Vehicle(unsafe,'H1',150),))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'view.html'
            write_assignment_html(scenario,assign_vehicles(self.graph,fleet),fleet,path)
            content=path.read_text(encoding='utf-8')
            self.assertNotIn('<script>alert(1)</script>',content)
            self.assertIn('&lt;script&gt;',content)
            self.assertEqual(content.count('<script>'),1)

    def test_html_output_cannot_overwrite_fleet_or_other_outputs(self):
        for args in (['--fleet','data/arac_senaryosu.json','--html','data/arac_senaryosu.json'],['--html','same.svg','--svg','same.svg']):
            run=subprocess.run([sys.executable,'-m','ayros.dispatch',*args],cwd=ROOT,capture_output=True)
            self.assertEqual(run.returncode,2)

    def test_loader_rejects_unknown_fields_and_wrong_units(self):
        original = json.loads((ROOT/'data/arac_senaryosu.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'bad.json'
            for data in ({**original,'extra':1},{**original,'unit':'person'},{**original,'schema_version':True}):
                path.write_text(json.dumps(data),encoding='utf-8')
                with self.assertRaises(ValidationError):
                    load_dispatch(path,self.graph)

    def test_loader_rejects_duplicate_target_in_json(self):
        original=json.loads((ROOT/'data/arac_senaryosu.json').read_text(encoding='utf-8-sig'))
        ambiguous=json.dumps(original).replace('"A01": 45','"A01": 45, "A01": 100')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'duplicate.json'
            path.write_text(ambiguous,encoding='utf-8')
            with self.assertRaisesRegex(ValidationError,'yinelenen JSON alanı: A01'):
                load_dispatch(path,self.graph)


if __name__ == '__main__':
    unittest.main()
