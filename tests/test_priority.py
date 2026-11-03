"""İhtiyaç puanının bağımsızlığı, sınırları, erişim ve çıktı sözleşmeleri."""

from dataclasses import asdict, replace
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ayros.model import Graph, Node, NodeType, RoadStatus, ValidationError
from ayros.priority import PriorityPolicy, assess_priorities, load_priority_policy, rank_needs, score_need
from ayros.priority_output import assessment_dict, write_priority_json, write_priority_svg
from ayros.routing import CostModel
from ayros.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]


def area(id='A', *, urgency=3, injured=20, affected=100):
    return Node(id, 'Afet ' + id, NodeType.DISASTER_AREA, 0, 0, affected, injured, urgency)


class PriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = load_scenario(ROOT / 'data/bolgesel_ag.json')

    def test_known_hand_calculation_and_breakdown(self):
        score = score_need(self.scenario.graph.nodes['A08'])
        self.assertAlmostEqual(score.urgency_points, 50)
        self.assertAlmostEqual(score.injured_points, 6)
        self.assertAlmostEqual(score.affected_points, 7.24)
        self.assertAlmostEqual(score.score, 63.24)

    def test_fraction_oracle_for_random_valid_inputs_and_policies(self):
        rng = random.Random(20261031)
        for weights in ((.5,.3,.2),(.7,.2,.1),(.3,.2,.5)):
            policy = PriorityPolicy(*weights)
            for _ in range(100):
                affected = rng.randrange(0,2001)
                node = area(urgency=rng.randrange(1,6), injured=rng.randrange(affected+1), affected=affected)
                u,i,a = (Fraction(str(w)) for w in weights)
                expected = 100*(u*Fraction(node.urgency_level,5) + i*Fraction(min(node.injured_count,100),100)
                                + a*Fraction(min(node.affected_count,500),500))
                self.assertAlmostEqual(score_need(node,policy).score, float(expected), places=10)

    def test_score_is_bounded_and_monotone_for_each_input(self):
        for field, values in (('urgency_level',range(1,6)),('injured_count',range(0,201)),
                              ('affected_count',range(200,701))):
            scores = [score_need(replace(area(injured=0,affected=200), **{field:v})).score for v in values]
            self.assertTrue(all(0 <= v <= 100 for v in scores))
            self.assertEqual(scores,sorted(scores))

    def test_saturation_keeps_raw_counts_and_handles_large_integers(self):
        result = score_need(area(urgency=5, injured=10**400, affected=10**401))
        self.assertEqual(result.score,100)
        self.assertEqual(result.node.injured_count,10**400)
        self.assertTrue(result.injured_capped and result.affected_capped)
        at_reference = score_need(area(urgency=5,injured=100,affected=500))
        self.assertFalse(at_reference.injured_capped or at_reference.affected_capped)
        self.assertEqual(at_reference.score,result.score)

    def test_zero_counts_preserve_reported_urgency_contribution(self):
        result = score_need(area(urgency=1,injured=0,affected=0))
        self.assertEqual(result.score,10)
        self.assertEqual((result.injured_points,result.affected_points),(0,0))

    def test_invalid_weights_are_rejected(self):
        for bad in (-.1,1.1,float('nan'),float('inf'),True,'0.5',10**400):
            with self.subTest(bad=str(bad)[:30]), self.assertRaises(ValidationError):
                PriorityPolicy(urgency_weight=bad)
        for weights in ((0,0,0),(.5,.5,.5),(.5,.3,.19)):
            with self.assertRaises(ValidationError):
                PriorityPolicy(*weights)

    def test_invalid_references_and_single_component_policy(self):
        for key in ('injured_reference','affected_reference'):
            for value in (0,-1,True,1.5,'100'):
                with self.assertRaises(ValidationError):
                    PriorityPolicy(**{key:value})
        self.assertEqual(score_need(area(urgency=5),PriorityPolicy(1,0,0)).score,100)

    def test_non_disaster_node_cannot_be_scored(self):
        with self.assertRaises(ValidationError):
            score_need(self.scenario.graph.nodes['H0'])

    def test_policy_file_matches_defaults_and_rejects_bad_schema(self):
        self.assertEqual(load_priority_policy(ROOT/'data/oncelik_politikasi.json'),PriorityPolicy())
        base = {'schema_version':1, **asdict(PriorityPolicy())}
        invalid = [[], {}, {**base,'typo':1}, {**base,'schema_version':True},
                   {**base,'schema_version':2}, {**base,'urgency_weight':.8}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'policy.json'
            for data in invalid:
                path.write_text(json.dumps(data),encoding='utf-8')
                with self.assertRaises(ValidationError):
                    load_priority_policy(path)
            path.write_text('{',encoding='utf-8')
            with self.assertRaises(ValidationError):
                load_priority_policy(path)
            with self.assertRaises(ValidationError):
                load_priority_policy(Path(folder)/'missing.json')

    def test_rank_is_independent_of_input_order_and_other_targets(self):
        nodes = [area('B'),area('A'),area('C',urgency=5)]
        before = rank_needs(Graph(nodes,[]))
        after = rank_needs(Graph(list(reversed(nodes))+[area('D',injured=999,affected=1000)],[]))
        self.assertEqual([r.node.id for r in before],['C','A','B'])
        self.assertEqual([(r.node.id,r.score) for r in after if r.node.id!='D'],
                         [(r.node.id,r.score) for r in before])

    def test_tie_break_uses_raw_counts_then_id(self):
        policy = PriorityPolicy(1,0,0)
        nodes = [area('Z',injured=21),area('B',injured=20,affected=101),
                 area('A',injured=20,affected=101),area('C',injured=20,affected=100)]
        self.assertEqual([s.node.id for s in rank_needs(Graph(nodes,[]),policy)],['Z','A','B','C'])

    def test_tie_break_prefers_urgency_when_score_is_equal(self):
        policy = PriorityPolicy(0,1,0)
        nodes = [area('A',urgency=2),area('Z',urgency=3)]
        self.assertEqual([s.node.id for s in rank_needs(Graph(nodes,[]),policy)],['Z','A'])

    def test_no_disaster_points_is_an_explicit_error(self):
        with self.assertRaises(ValidationError):
            rank_needs(Graph([self.scenario.graph.nodes['H0']],[]))

    def test_start_must_be_an_existing_aid_center(self):
        for start in ('missing','A01','K001',None,''):
            with self.assertRaises(ValidationError):
                assess_priorities(self.scenario.graph,start)

    def test_centers_damage_and_algorithms_do_not_change_need_ranking(self):
        expected = [(s.node.id,s.score) for s in rank_needs(self.scenario.graph)]
        costs = {}
        for start in ('H0','H1','H2'):
            for factor in (1,2):
                dj = assess_priorities(self.scenario.graph,start,cost_model=CostModel(factor))
                astar = assess_priorities(self.scenario.graph,start,cost_model=CostModel(factor),algorithm='astar')
                self.assertEqual([(e.need.node.id,e.need.score) for e in dj.entries],expected)
                self.assertEqual([(e.need.node.id,e.need.score) for e in astar.entries],expected)
                for a,b in zip(dj.entries,astar.entries):
                    self.assertEqual(a.route.found,b.route.found)
                    if a.route.found:
                        self.assertAlmostEqual(a.route.cost_min,b.route.cost_min)
                costs[start,factor] = [e.route.cost_min for e in dj.entries]
        self.assertNotEqual(costs['H0',1],costs['H0',2])
        self.assertNotEqual(costs['H0',2],costs['H1',2])

    def test_unreachable_highest_need_stays_first(self):
        graph = self.scenario.graph
        changed = Graph([replace(n,urgency_level=5,injured_count=100,affected_count=500)
                         if n.id=='A12' else n for n in graph.nodes.values()],list(graph.roads.values()))
        result = assess_priorities(changed,'H0')
        self.assertEqual(result.entries[0].need.node.id,'A12')
        self.assertEqual(result.entries[0].need.score,100)
        self.assertFalse(result.entries[0].route.found)
        self.assertIsNone(result.entries[0].route.cost_min)

    def test_all_roads_closed_preserves_all_needs_and_input(self):
        graph = self.scenario.graph
        old = list(graph.roads.values())
        closed = Graph(list(graph.nodes.values()),[replace(r,status=RoadStatus.CLOSED) for r in old])
        result = assess_priorities(closed,'H0')
        self.assertEqual(len(result.entries),12)
        self.assertFalse(any(e.route.found for e in result.entries))
        self.assertEqual(list(graph.roads.values()),old)

    def test_policy_sensitivity_changes_ranking_without_changing_routes(self):
        baseline = assess_priorities(self.scenario.graph,'H0')
        alternative = assess_priorities(self.scenario.graph,'H0',policy=PriorityPolicy(.3,.2,.5))
        self.assertEqual(baseline.entries[0].need.node.id,'A08')
        self.assertEqual(alternative.entries[0].need.node.id,'A11')
        costs = lambda result: {e.need.node.id:e.route.cost_min for e in result.entries}
        self.assertEqual(costs(baseline),costs(alternative))

    def test_json_preserves_inputs_components_and_null_unreachable_cost(self):
        result = assess_priorities(self.scenario.graph,'H0')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'sub/result.json'
            digest = sha256((ROOT/'data/bolgesel_ag.json').read_bytes()).hexdigest()
            write_priority_json(self.scenario,result,path,scenario_sha256=digest)
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['scenario_sha256'],digest)
            self.assertEqual(data['policy'],asdict(PriorityPolicy()))
            for row in data['entries']:
                self.assertAlmostEqual(sum(row['contributions'].values()),row['score'])
                self.assertEqual(row['node']['affected_count'],self.scenario.graph.nodes[row['node']['id']].affected_count)
            blocked = next(e for e in data['entries'] if e['node']['id']=='A12')
            self.assertFalse(blocked['reachable'])
            self.assertIsNone(blocked['route']['cost_min'])
            self.assertEqual(blocked['route']['path'],[])

    def test_svg_matches_ranks_scores_status_and_escapes_text(self):
        scenario = replace(self.scenario,name='A&B <senaryo>')
        result = assess_priorities(scenario.graph,'H0')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'result.svg'
            write_priority_svg(scenario,result,path)
            root = ET.parse(path).getroot()
            rows = [g for g in root.iter() if 'data-node' in g.attrib]
            self.assertEqual(len(rows),12)
            for row,entry in zip(rows,result.entries):
                self.assertEqual(row.get('data-node'),entry.need.node.id)
                self.assertEqual(int(row.get('data-rank')),entry.rank)
                self.assertEqual(float(row.get('data-score')),entry.need.score)
                self.assertEqual(row.get('data-reachable'),str(entry.route.found).lower())
            self.assertIn('A&amp;B &lt;senaryo&gt;',path.read_text(encoding='utf-8'))


class PriorityCliTests(unittest.TestCase):
    def run_cli(self,*args):
        return subprocess.run([sys.executable,'-m','ayros',*map(str,args)],cwd=ROOT,
                              env={**os.environ,'PYTHONIOENCODING':'utf-8'},
                              capture_output=True,text=True,encoding='utf-8')

    def test_cli_valid_mode_and_deterministic_json(self):
        with tempfile.TemporaryDirectory() as folder:
            dest,svg = Path(folder)/'priority.json',Path(folder)/'priority.svg'
            args = ('data/bolgesel_ag.json','--start','H0','--prioritize','--algorithm','astar',
                    '--priority-policy','data/oncelik_politikasi.json','--priority-json',dest,'--priority-svg',svg)
            first = self.run_cli(*args)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertIn('11/12',first.stdout)
            self.assertIn('ULAŞILAMIYOR',first.stdout)
            self.assertTrue(svg.is_file())
            before = dest.read_bytes()
            self.assertEqual(self.run_cli(*args).returncode,0)
            self.assertEqual(dest.read_bytes(),before)

    def test_cli_invalid_option_combinations(self):
        cases = [('--prioritize',),('--priority-json','x.json'),
                 ('--start','H0','--prioritize','--compare'),
                 ('--start','H0','--prioritize','--svg','x.svg'),
                 ('--start','H0','--prioritize','--target','A5'),
                 ('--start','H0','--prioritize','--repeats','2'),
                 ('--start','H0','--prioritize','--priority-json','data/hafta3_genis_ag.json'),
                 ('--start','H0','--prioritize','--priority-json','x','--priority-svg','x')]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode,2,result.stderr)

    def test_cli_invalid_center_and_missing_policy(self):
        for args in (('--start','A5','--prioritize'),
                     ('--start','H0','--prioritize','--priority-policy','missing.json')):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode,1)
            self.assertIn('Hata:',result.stderr)


if __name__ == '__main__':
    unittest.main()
