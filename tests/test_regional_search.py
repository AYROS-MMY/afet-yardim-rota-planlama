"""Büyük senaryonun topolojisi, arama izi ve çoklu ağ deneyleri."""

from dataclasses import replace
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ayros.model import Graph, NodeType, RoadStatus, ValidationError
from ayros.routing import CostModel, _time_heuristic, find_shortest_path
from ayros.scenario import load_scenario, scenario_from_dict
from ayros.search_visualize import write_search_svg
from scripts.generate_regional_scenario import build_scenario

ROOT = Path(__file__).resolve().parents[1]
REGIONAL = ROOT/'data/bolgesel_ag.json'


class RegionalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = load_scenario(REGIONAL)

    def test_generator_reproduces_fixture_and_valid_needs(self):
        generated = build_scenario()
        self.assertEqual(generated, json.loads(REGIONAL.read_text(encoding='utf-8')))
        graph = scenario_from_dict(generated).graph
        self.assertEqual(len(graph.nodes), 180)
        self.assertEqual(len(graph.roads), 348)
        self.assertEqual(sum(n.node_type == NodeType.AID_CENTER for n in graph.nodes.values()), 3)
        self.assertEqual(sum(n.node_type == NodeType.DISASTER_AREA for n in graph.nodes.values()), 12)
        self.assertEqual({n.urgency_level for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA}, {1,2,3,4,5})
        for road in graph.roads.values():
            a,b = graph.nodes[road.source],graph.nodes[road.target]
            self.assertGreaterEqual(road.distance_km+1e-9, math.hypot(a.x_km-b.x_km,a.y_km-b.y_km))

    def test_roads_do_not_cross_without_a_junction(self):
        graph = self.scenario.graph
        roads = list(graph.roads.values())
        def side(a,b,c):
            return (b.x_km-a.x_km)*(c.y_km-a.y_km)-(b.y_km-a.y_km)*(c.x_km-a.x_km)
        for i,r in enumerate(roads):
            a,b = graph.nodes[r.source],graph.nodes[r.target]
            for s in roads[i+1:]:
                if {r.source,r.target} & {s.source,s.target}:
                    continue
                c,d = graph.nodes[s.source],graph.nodes[s.target]
                self.assertFalse(side(a,b,c)*side(a,b,d)<0 and side(c,d,a)*side(c,d,b)<0, (r.id,s.id))
        for r in roads:
            cross_bank = (graph.nodes[r.source].x_km < 13) != (graph.nodes[r.target].x_km < 13)
            self.assertEqual(cross_bank, r.road_type == 'bridge')

    def test_reachability_and_three_bridge_closure(self):
        graph = self.scenario.graph
        for start in ('H0','H1','H2'):
            for n in graph.nodes:
                self.assertEqual(find_shortest_path(graph,start,n).found, n != 'A12')
        self.assertEqual(len(graph.neighbors('A12', traversable_only=False)), 2)
        bridges = [r.id for r in graph.roads.values() if r.road_type == 'bridge']
        self.assertEqual(len(bridges), 3)
        for blocked in ([b] for b in bridges):
            changed = Graph(list(graph.nodes.values()),[replace(r,status=RoadStatus.CLOSED) if r.id in blocked else r for r in graph.roads.values()])
            self.assertTrue(find_shortest_path(changed,'H0','A11').found)
        changed = Graph(list(graph.nodes.values()),[replace(r,status=RoadStatus.CLOSED) if r.id in bridges else r for r in graph.roads.values()])
        self.assertFalse(find_shortest_path(changed,'H0','A11').found)
        self.assertTrue(find_shortest_path(changed,'H0','A01').found)

    def test_72_queries_match_independent_bellman_ford_and_consistent_heuristic(self):
        graph = self.scenario.graph
        for factor in (1,2):
            for start in ('H0','H1','H2'):
                reference = dict.fromkeys(graph.nodes, math.inf)
                reference[start] = 0
                for _ in range(len(graph.nodes)-1):
                    changed = False
                    for r in graph.roads.values():
                        if r.status == RoadStatus.CLOSED:
                            continue
                        cost = r.travel_time_min * (factor if r.status == RoadStatus.DAMAGED else 1)
                        for a,b in ((r.source,r.target),(r.target,r.source)):
                            if reference[a]+cost < reference[b]:
                                reference[b] = reference[a]+cost
                                changed = True
                    if not changed:
                        break
                for target in (n.id for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA):
                    for algorithm in ('dijkstra','astar'):
                        result = find_shortest_path(graph,start,target,algorithm=algorithm,cost_model=CostModel(factor))
                        self.assertEqual(result.found, math.isfinite(reference[target]))
                        if result.found:
                            self.assertAlmostEqual(result.cost_min, reference[target])
                    costs = {r.id: CostModel(factor).cost_minutes(r) for r in graph.roads.values()}
                    h = _time_heuristic(graph,target,costs)
                    self.assertEqual(h[target], 0)
                    for r in graph.roads.values():
                        if costs[r.id] is not None:
                            self.assertLessEqual(abs(h[r.source]-h[r.target]),costs[r.id]+1e-9)

    def test_search_trace_is_optional_unique_and_does_not_change_route(self):
        graph = self.scenario.graph
        for target in ('A11','A12','H0'):
            for algorithm in ('dijkstra','astar'):
                normal = find_shortest_path(graph,'H0',target,algorithm=algorithm)
                traced = find_shortest_path(graph,'H0',target,algorithm=algorithm,record_search=True)
                self.assertEqual(normal.settled_order, ())
                self.assertEqual(len(traced.settled_order),traced.settled_nodes)
                self.assertEqual(len(set(traced.settled_order)),traced.settled_nodes)
                self.assertEqual(traced.settled_order[0],'H0')
                self.assertEqual((normal.path,normal.cost_min,normal.road_ids,normal.settled_nodes),
                                 (traced.path,traced.cost_min,traced.road_ids,traced.settled_nodes))
                if traced.found:
                    self.assertEqual(traced.settled_order[-1],target)

    def test_search_svg_matches_exact_traces_and_routes(self):
        for target in ('A11','A12'):
            scenario = replace(self.scenario,name='A & B <deney>')
            routes = {a:find_shortest_path(scenario.graph,'H0',target,algorithm=a,record_search=True) for a in ('dijkstra','astar')}
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'search.svg'
                write_search_svg(scenario,path,start='H0',target=target,**routes)
                xml = ET.parse(path).getroot()
                for panel in (e for e in xml.iter() if e.get('data-algorithm')):
                    result = routes[panel.get('data-algorithm')]
                    settled = {e.get('data-settled-node'):int(e.get('data-order')) for e in panel.iter() if e.get('data-settled-node')}
                    self.assertEqual(settled, {n:i+1 for i,n in enumerate(result.settled_order)})
                    self.assertEqual({e.get('data-route-road') for e in panel.iter() if e.get('data-route-road')},set(result.road_ids))
                self.assertIn('A & B <deney>', ''.join(xml.itertext()))
                with self.assertRaises(ValidationError):
                    write_search_svg(scenario,path,start='H0',target=target,dijkstra=replace(routes['dijkstra'],settled_order=()),astar=routes['astar'])

    def test_cli_search_svg_and_invalid_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'search.svg'
            for target,status in (('A11',0),('A12',3)):
                cmd = [sys.executable,'-m','ayros',str(REGIONAL),'--start','H0','--target',target,'--compare','--repeats','1','--search-svg',str(path)]
                result = subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=15)
                self.assertEqual(result.returncode,status,result.stderr)
                self.assertTrue(path.exists())
            for args in ([],['--start','H0','--target','A5'],['--start','H0','--all-targets','--compare']):
                result = subprocess.run([sys.executable,'-m','ayros',*args,'--search-svg',str(path)],cwd=ROOT,capture_output=True,timeout=15)
                self.assertEqual(result.returncode,2)

    def test_multi_scenario_benchmark_exports_96_identified_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'experiment.json'
            result = subprocess.run([sys.executable,'scripts/compare_algorithms.py','--scenario','data/hafta3_genis_ag.json',
                                     '--scenario',str(REGIONAL),'--repeats','2','--output',str(output)],cwd=ROOT,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            payload = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(len(payload['results']),96)
            self.assertEqual([s['nodes'] for s in payload['scenarios']],[40,180])
            self.assertEqual(payload['scenarios'][1]['sha256'],sha256(REGIONAL.read_bytes()).hexdigest())
            keys = {(r['scenario'],r['start'],r['target'],r['damage_factor']) for r in payload['results']}
            self.assertEqual(len(keys),96)
            for row in payload['results']:
                self.assertEqual(row['dijkstra']['route']['found'],row['astar']['route']['found'])
                for algorithm in ('dijkstra','astar'):
                    self.assertEqual(len(row[algorithm]['samples_ms']),2)
                    self.assertEqual(row[algorithm]['route']['settled_order'],[])


if __name__ == '__main__':
    unittest.main()
