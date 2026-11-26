"""İki ağ, üç politika ve farklı merkezlerde tekrarlanabilir ihtiyaç deneyi."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from ayros.model import NodeType
from ayros.priority import PriorityPolicy, assess_priorities
from ayros.priority_output import assessment_dict
from ayros.routing import CostModel
from ayros.scenario import load_scenario


def run_experiment() -> dict:
    profiles = {'baseline':PriorityPolicy(), 'urgency_focused':PriorityPolicy(.7,.2,.1),
                'affected_focused':PriorityPolicy(.3,.2,.5)}
    networks, results = [], []
    for name in ('hafta3_genis_ag','bolgesel_ag'):
        source = ROOT/'data'/f'{name}.json'
        scenario = load_scenario(source)
        networks.append({'id':name,'sha256':sha256(source.read_bytes()).hexdigest(),
                         'nodes':len(scenario.graph.nodes),'roads':len(scenario.graph.roads)})
        centers = sorted(n.id for n in scenario.graph.nodes.values() if n.node_type==NodeType.AID_CENTER)
        for profile,policy in profiles.items():
            fixed_order = None
            for center in centers:
                for factor in (1,2):
                    assessments = [assess_priorities(scenario.graph,center,policy=policy,
                                   cost_model=CostModel(factor),algorithm=algorithm)
                                   for algorithm in ('dijkstra','astar')]
                    for assessment in assessments:
                        order = [(e.need.node.id,e.need.score) for e in assessment.entries]
                        if fixed_order is not None and fixed_order != order:
                            raise AssertionError('İhtiyaç sırası merkez/yol/algoritma ile değişti.')
                        fixed_order = order
                        results.append({'scenario':name,'profile':profile,**assessment_dict(assessment)})
                    for a,b in zip(assessments[0].entries,assessments[1].entries):
                        if a.route.found != b.route.found or (a.route.found and
                                not isclose(a.route.cost_min,b.route.cost_min,rel_tol=1e-9,abs_tol=1e-9)):
                            raise AssertionError('Rota sonuçları uyuşmadı.')
    return {'schema_version':1,'profiles':{name:asdict(p) for name,p in profiles.items()},
            'scenarios':networks,'assessment_count':len(results),
            'target_evaluations':sum(len(r['entries']) for r in results),'results':results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/oncelik_deneyi.json')
    args = parser.parse_args()
    if args.output.resolve() in {(ROOT/'data'/f'{name}.json').resolve()
                                 for name in ('hafta3_genis_ag','bolgesel_ag')}:
        parser.error('Deney çıktısı kaynak senaryonun üzerine yazılamaz.')
    data = run_experiment()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(f"{data['assessment_count']} değerlendirme, {data['target_evaluations']} hedef kaydı; kontroller başarılı.")
    for network in data['scenarios']:
        for profile in data['profiles']:
            sample = next(r for r in data['results'] if r['scenario']==network['id'] and r['profile']==profile)
            print(network['id'],profile,[(e['node']['id'],round(e['score'],2)) for e in sample['entries'][:3]])
    print(args.output)


if __name__ == '__main__':
    main()
