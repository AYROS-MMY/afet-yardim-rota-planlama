from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ayros.assignment import DispatchInput, Task, Vehicle, assign_vehicles, load_dispatch
from ayros.model import Graph, RoadStatus, ValidationError
from ayros.routing import CostModel
from ayros.scenario import load_scenario
from ayros.simulation import Simulation
from ayros.simulate import load_events

ROOT = Path(__file__).resolve().parents[1]


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.graph = load_scenario(ROOT / 'data/hafta7_mikro_ag.json').graph
        self.fleet = load_dispatch(ROOT / 'data/hafta7_mikro_arac.json', self.graph)
        self.sim = Simulation(self.graph, self.fleet)

    def finish(self, sim=None):
        sim = sim or self.sim
        for _ in range(1000):
            state = sim.snapshot()
            for task in state['tasks']:
                completed = task['delivered'] if task['service'] == 'logistics' else int(task['team_arrived'])
                self.assertEqual(completed + task['reserved'] + task['unassigned'], task['requested'])
                self.assertGreaterEqual(task['remaining'], 0)
            if not state['can_advance']:
                return state
            sim.step()
        self.fail('Simulation failed to terminate')

    def test_initial_plan_and_arrival_accounting(self):
        initial = self.sim.snapshot()
        self.assertEqual(initial['logistics'], dict(requested=100, delivered=0, reserved=100, unassigned=0, remaining=100))
        first = self.sim.step()
        self.assertEqual((first['time_min'], first['vehicles'][0]['node']), (2, 'K'))
        self.assertEqual(first['logistics']['delivered'], 0)
        final = self.finish()
        self.assertEqual((final['time_min'], final['vehicles'][0]['node']), (4, 'A'))
        self.assertEqual(final['logistics']['delivered'], 100)
        self.assertEqual(final['logistics']['remaining'], 0)

    def test_final_step_is_idempotent(self):
        final = self.finish()
        for _ in range(3):
            self.assertEqual(self.sim.step(), final)
        self.assertEqual(sum(e['kind'] == 'delivered' for e in final['events']), 1)

    def test_closure_replans_from_current_node_and_preserves_assignment(self):
        self.sim.step()
        state = self.sim.change_roads({'R2': 'closed'})
        vehicle = state['vehicles'][0]
        self.assertEqual(vehicle['node'], 'K')
        self.assertEqual(vehicle['remaining_path'], ['K', 'B', 'A'])
        self.assertEqual(vehicle['task_id'], 'A-L')
        final = self.finish()
        self.assertEqual(final['time_min'], 8)
        self.assertEqual(final['logistics']['delivered'], 100)
        self.assertEqual(final['vehicles'][0]['completed_distance_km'], 3.5)

    def test_isolation_holds_load_and_reopening_resumes(self):
        self.sim.step()
        blocked = self.sim.change_roads({'R2': 'closed', 'R3': 'closed'})
        self.assertEqual(blocked['vehicles'][0]['status'], 'blocked')
        self.assertEqual(blocked['logistics']['reserved'], 100)
        self.assertEqual(blocked['logistics']['delivered'], 0)
        self.assertEqual(self.sim.step(), blocked)
        self.sim.change_roads({'R3': 'open'})
        self.assertEqual(self.finish()['logistics']['delivered'], 100)

    def test_change_group_is_atomic_and_input_graph_is_unchanged(self):
        before = self.sim.snapshot()
        with self.assertRaises(ValidationError):
            self.sim.change_roads({'R2': 'closed', 'missing': 'closed'})
        self.assertEqual(self.sim.snapshot(), before)
        self.sim.change_roads({'R2': 'closed'})
        self.assertEqual(self.graph.roads['R2'].status, RoadStatus.OPEN)

    def test_same_road_event_is_idempotent(self):
        state = self.sim.change_roads({'R2': 'closed'})
        self.assertEqual(self.sim.change_roads({'R2': 'closed'}), state)

    def test_routing_failure_rolls_back_graph_tasks_and_event_log(self):
        self.sim.step()
        before = self.sim.snapshot()
        with patch('ayros.simulation.find_shortest_path', side_effect=ValidationError('cost overflow')):
            with self.assertRaises(ValidationError):
                self.sim.change_roads({'R2': 'closed'})
        self.assertEqual(self.sim.snapshot(), before)
        self.assertEqual(self.finish()['time_min'], 4)

    def test_input_order_does_not_change_simulation(self):
        graph = load_scenario(ROOT / 'data/bolgesel_ag.json').graph
        fleet = load_dispatch(ROOT / 'data/gorev_senaryosu_12_arac.json', graph)
        reversed_fleet = replace(fleet, vehicles=tuple(reversed(fleet.vehicles)), tasks=tuple(reversed(fleet.tasks)))
        self.assertEqual(self.finish(Simulation(graph, fleet)), self.finish(Simulation(graph, reversed_fleet)))

    def test_damage_changes_route_cost(self):
        self.sim.step()
        self.sim.change_roads({'R2': 'damaged'})
        self.assertEqual(self.finish()['time_min'], 6)

    def test_unaffected_vehicle_keeps_route(self):
        before = self.sim.snapshot()['vehicles']
        self.sim.change_roads({'R3': 'closed'})
        self.assertEqual(self.sim.snapshot()['vehicles'], before)

    def test_snapshot_and_graph_are_detached(self):
        state = self.sim.snapshot()
        state['tasks'][0]['delivered'] = 10000
        state['events'].clear()
        self.sim.graph.roads.clear()
        self.assertEqual(self.sim.snapshot()['logistics']['delivered'], 0)
        self.assertEqual(self.finish()['logistics']['delivered'], 100)

    def test_multiple_services_arrive_independently_and_deterministically(self):
        vehicles = tuple(Vehicle(s, 'H0', 1, service=s) for s in ('medical', 'rescue'))
        tasks = tuple(Task(s, 'A', s, 1, 5) for s in ('medical', 'rescue'))
        sim = Simulation(self.graph, DispatchInput(self.fleet.vehicles + vehicles, {}, self.fleet.tasks + tasks))
        final = self.finish(sim)
        self.assertEqual(final['logistics']['delivered'], 100)
        self.assertEqual([t['status'] for t in final['tasks']], ['delivered', 'team_arrived', 'team_arrived'])
        self.assertEqual(sum(t['team_arrived'] for t in final['tasks']), 2)

    def test_fractional_edge_time_and_occupied_change_rejection(self):
        roads = [replace(r, travel_time_min=0.3 if r.id == 'R1' else r.travel_time_min) for r in self.graph.roads.values()]
        sim = Simulation(Graph(list(self.graph.nodes.values()), roads), self.fleet)
        self.assertEqual(sim.step()['time_min'], 0.3)
        self.assertAlmostEqual(self.finish(sim)['time_min'], 2.3)
        # Two vehicles with different departure edges allow an occupied edge at a checkpoint.
        nodes = list(self.graph.nodes.values()) + [replace(self.graph.nodes['H0'], id='H1', x_km=-1)]
        roads = list(self.graph.roads.values()) + [replace(self.graph.roads['R1'], id='R5', source='H1', travel_time_min=5)]
        fleet = DispatchInput(self.fleet.vehicles + (Vehicle('S', 'H1', 1, service='medical'),), {},
                              self.fleet.tasks + (Task('A-S', 'A', 'medical', 1, 5),))
        sim = Simulation(Graph(nodes, roads), fleet)
        first = sim.step()
        self.assertEqual(first['vehicles'][0]['edge_id'], 'R5')
        with self.assertRaises(ValidationError):
            sim.change_roads({'R2': 'closed', 'R5': 'closed'})
        self.assertEqual(sim.snapshot(), first)
        sim.change_roads({'R2': 'closed'})
        self.assertTrue(sim.snapshot()['vehicles'][0]['reroute_pending'])
        self.assertEqual(sum(t['team_arrived'] for t in self.finish(sim)['tasks']), 1)

    def test_regional_arrivals_match_initial_route_costs(self):
        graph = load_scenario(ROOT / 'data/bolgesel_ag.json').graph
        fleet = load_dispatch(ROOT / 'data/gorev_senaryosu_12_arac.json', graph)
        entries = assign_vehicles(graph, fleet)
        final = self.finish(Simulation(graph, fleet))
        actual = {v['id']: v for v in final['vehicles']}
        for entry in entries:
            if entry.vehicle:
                self.assertAlmostEqual(actual[entry.vehicle.id]['arrival_at'], entry.route.cost_min)
        self.assertEqual(final['logistics']['delivered'], 455)
        self.assertEqual(final['logistics']['unassigned'], 475)
        self.assertEqual(sum(t['status'] == 'unassigned' for t in final['tasks']), 5)

    def run_regional_event(self, event_file):
        graph = load_scenario(ROOT / 'data/bolgesel_ag.json').graph
        fleet = load_dispatch(ROOT / 'data/gorev_senaryosu_12_arac.json', graph)
        events = load_events(ROOT / 'data' / event_file, graph)
        sim = Simulation(graph, fleet)
        while sim.snapshot()['step'] < 1:
            sim.step()
        sim.change_roads(events[1])
        final = self.finish(sim)
        return final, {v['id']: v for v in final['vehicles']}

    def test_regional_bridge_closure_reroutes_only_the_affected_vehicle(self):
        final, vehicles = self.run_regional_event('hafta7_bolgesel_kopru_kapanmasi.json')
        self.assertEqual([v for v in vehicles if vehicles[v]['reroutes']], ['S02'])
        self.assertAlmostEqual(vehicles['S02']['arrival_at'], 67.79)
        self.assertAlmostEqual(vehicles['V04']['arrival_at'], 52.835)
        change = next(e for e in final['events'] if e['kind'] == 'route_changed')
        self.assertNotEqual(change['old_path'], change['new_path'])
        self.assertIn('K003', change['new_path'])
        self.assertNotIn('K001', change['new_path'][1:])
        self.assertEqual(final['logistics']['delivered'], 455)

    def test_regional_damaged_bridges_keep_route_and_double_bridge_time(self):
        final, vehicles = self.run_regional_event('hafta7_bolgesel_kopruler_hasarli.json')
        # Köprü temel süresi 4,8 dk; hasar katsayısı 2 olduğundan gecikme 4,8 dk'dır.
        self.assertAlmostEqual(vehicles['S02']['arrival_at'], 53.575 + 4.8)
        self.assertAlmostEqual(vehicles['V04']['arrival_at'], 52.835 + 4.8)
        for event in final['events']:
            if event['kind'] == 'route_changed':
                self.assertEqual(event['old_path'], event['new_path'])

    def test_closing_all_bridges_holds_cross_river_vehicles(self):
        final, vehicles = self.run_regional_event('hafta7_bolgesel_tum_kopruler_kapali.json')
        self.assertEqual({v for v in vehicles if vehicles[v]['status'] == 'blocked'}, {'S02', 'V04'})
        self.assertIsNone(vehicles['S02']['arrival_at'])
        self.assertEqual(final['logistics']['delivered'], 405)
        self.assertEqual(final['logistics']['reserved'], 50)
        tasks = {t['id']: t for t in final['tasks']}
        self.assertFalse(tasks['A11-S']['team_arrived'])
        self.assertEqual(tasks['A04-L']['status'], 'blocked')

    def test_published_experiment_records_match_a_fresh_run(self):
        with tempfile.TemporaryDirectory() as directory:
            run = subprocess.run([sys.executable, 'scripts/run_simulation_examples.py', '--output', directory],
                                 cwd=ROOT, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            fresh = json.loads((Path(directory) / 'sonuclar.json').read_text(encoding='utf-8'))
            published = json.loads((ROOT / 'docs/deneyler/hafta7_sonuclar.json').read_text(encoding='utf-8'))
            self.assertEqual(fresh, published)
            for name in ('simulasyon.svg', 'bolgesel_kopru.svg'):
                self.assertEqual((Path(directory) / name).read_text(encoding='utf-8'),
                                 (ROOT / 'docs' / name).read_text(encoding='utf-8'))

    def test_legacy_fleet_and_algorithms(self):
        graph = load_scenario(ROOT / 'data/bolgesel_ag.json').graph
        fleet = load_dispatch(ROOT / 'data/arac_senaryosu.json', graph)
        a = self.finish(Simulation(graph, fleet, algorithm='astar'))
        b = self.finish(Simulation(graph, fleet, algorithm='dijkstra'))
        self.assertEqual(a, b)
        self.assertEqual(a['logistics']['delivered'], 340)

    def test_delivered_quantities_survive_later_road_events(self):
        final = self.finish()
        state = self.sim.change_roads({'R2': 'closed'})
        self.assertEqual(state['tasks'], final['tasks'])
        self.assertEqual(state['vehicles'], final['vehicles'])

    def test_no_vehicles_and_empty_tasks_terminate(self):
        sim = Simulation(self.graph, replace(self.fleet, vehicles=()))
        self.assertFalse(sim.step()['can_advance'])
        self.assertEqual(sim.snapshot()['logistics']['unassigned'], 100)
        sim = Simulation(self.graph, DispatchInput((), {}, ()))
        self.assertEqual(sim.step()['tasks'], [])

    def test_event_validation(self):
        for events in ([{'after_step': True, 'changes': {'R1': 'closed'}}],
                       [{'after_step': 1, 'changes': {'missing': 'closed'}}],
                       [{'after_step': 1, 'changes': {}}]):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'events.json'
                path.write_text(json.dumps(dict(schema_version=1, events=events)))
                with self.assertRaises(ValidationError):
                    load_events(path, self.graph)

    def test_cli_reproducibility_and_input_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            command = [sys.executable, '-m', 'ayros.simulate', '--scenario', 'data/hafta7_mikro_ag.json',
                       '--fleet', 'data/hafta7_mikro_arac.json', '--events', 'data/hafta7_yol_kapanmasi.json']
            run = subprocess.run(command + ['--json', str(output)], cwd=ROOT, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            first = output.read_bytes()
            run = subprocess.run(command + ['--json', str(output)], cwd=ROOT, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual(json.loads(first)['final']['time_min'], 8)
            run = subprocess.run(command + ['--json', 'data/hafta7_mikro_arac.json'], cwd=ROOT, capture_output=True)
            self.assertEqual(run.returncode, 2)

    def test_cli_runs_on_console_without_turkish_characters(self):
        # İngilizce Windows konsolu (cp1252) 'ı', 'ş', 'ğ' karakterlerini yazamaz; CLI çökmemelidir.
        env = dict(os.environ, PYTHONIOENCODING='cp1252')
        run = subprocess.run([sys.executable, '-m', 'ayros.simulate', '--scenario', 'data/hafta7_mikro_ag.json',
                              '--fleet', 'data/hafta7_mikro_arac.json'], cwd=ROOT, capture_output=True, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn(b'Teslim 100', run.stdout)

    def test_cli_rejects_unreachable_event_step_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / 'events.json'
            output = Path(directory) / 'result.json'
            events.write_text(json.dumps(dict(schema_version=1, events=[dict(after_step=999, changes={'R2': 'closed'})])))
            command = [sys.executable, '-m', 'ayros.simulate', '--scenario', 'data/hafta7_mikro_ag.json',
                       '--fleet', 'data/hafta7_mikro_arac.json', '--events', str(events), '--json', str(output)]
            run = subprocess.run(command, cwd=ROOT, capture_output=True)
            self.assertEqual(run.returncode, 1)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
