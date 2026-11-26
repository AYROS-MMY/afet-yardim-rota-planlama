"""Çalıştırma: py -3.11 -m ayros.dispatch --help."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

from .assignment import REASONS, SERVICES, assign_vehicles, load_dispatch
from .assignment_output import write_assignment_svg
from .assignment_viewer import write_assignment_html
from .model import ValidationError
from .priority import PriorityPolicy, load_priority_policy
from .routing import CostModel
from .scenario import load_scenario


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='AYROS | Tek turluk araç görev dağıtımı')
    parser.add_argument('--scenario', type=Path, default=root / 'data/bolgesel_ag.json')
    parser.add_argument('--fleet', type=Path, default=root / 'data/gorev_senaryosu_12_arac.json')
    parser.add_argument('--priority-policy', type=Path)
    parser.add_argument('--algorithm', choices=('astar', 'dijkstra'), default='astar')
    parser.add_argument('--damage-factor', type=float, default=2)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--svg', type=Path)
    parser.add_argument('--html', type=Path, help='Çevrimdışı araç seçilebilir görev planı')
    args = parser.parse_args()
    inputs = {p.resolve() for p in (args.scenario, args.fleet, args.priority_policy) if p}
    outputs = [p.resolve() for p in (args.json, args.svg, args.html) if p]
    if inputs.intersection(outputs) or len(outputs) != len(set(outputs)):
        parser.error('Çıktılar girdilerden ve birbirinden farklı olmalıdır.')
    try:
        scenario = load_scenario(args.scenario)
        fleet = load_dispatch(args.fleet, scenario.graph)
        policy = load_priority_policy(args.priority_policy) if args.priority_policy else PriorityPolicy()
        model = CostModel(args.damage_factor)
        entries = assign_vehicles(scenario.graph, fleet, policy=policy, cost_model=model, algorithm=args.algorithm)
        print('AYROS MMY | 6. hafta | Tek turluk araç atama')
        print('Görev aciliyeti -> bölge puanı -> uygun tür/kapasite -> en kısa ulaşım süresi')
        for e in entries:
            detail = (f'{e.vehicle.id} ({e.vehicle.center}) | {e.demand}/{e.vehicle.capacity} {e.unit}'
                      f' | {e.route.cost_min:.2f} dk | {e.route.distance_km:.2f} km'
                      if e.vehicle else REASONS[e.status])
            print(f'{e.rank:2}. {e.need.node.id} | {SERVICES[e.service]} | Puan {e.need.score:.2f} | Talep {e.demand} {e.unit} | {detail}')
        assigned = sum(e.vehicle is not None for e in entries)
        print(f'Atanan: {assigned}/{len(entries)} | Planlanan yük: {sum(e.demand for e in entries if e.vehicle and e.service == "logistics")} koli')
        print('Her araç tek görev alır. Global optimum, teslimat gerçekleşmesi veya araç hareketi gösterilmez.')
        if args.json:
            payload = {
                'schema_version': 2, 'strategy': 'task_urgency_then_area_score_greedy_single_round',
                'algorithm': args.algorithm, 'cost_model': asdict(model), 'policy': asdict(policy),
                'scenario_sha256': sha256(args.scenario.read_bytes()).hexdigest(),
                'fleet_sha256': sha256(args.fleet.read_bytes()).hexdigest(),
                'vehicles': [asdict(v) for v in fleet.vehicles],
                'entries': [{'rank': e.rank, 'target': e.need.node.id, 'score': e.need.score,
                             'demand': e.demand, 'unit': e.unit, 'service': e.service,
                             'task': asdict(e.task) if e.task else None, 'status': e.status,
                             'vehicle': asdict(e.vehicle) if e.vehicle else None,
                             'route': asdict(e.route) if e.route else None} for e in entries],
            }
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
            print(f'JSON: {args.json}')
        if args.svg:
            write_assignment_svg(scenario, entries, args.svg, fleet=fleet)
            print(f'Harita: {args.svg}')
        if args.html:
            write_assignment_html(scenario, entries, fleet, args.html)
            print(f'Araç seçilebilir görünüm: {args.html}')
        return 0
    except (ValidationError, OSError) as error:
        print(f'Hata: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
