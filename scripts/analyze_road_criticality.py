"""7. hafta: bölgesel ağda hangi yolun kapanması yardımı en çok geciktirir?

Başlangıç planındaki araçların kullandığı her açık veya hasarlı yol, araçlar
merkezden çıkmadan önce tek başına kapatılır. Simülasyon sonuna kadar yürütülür
ve olay yokken elde edilen varış zamanlarıyla karşılaştırılır. Hesap tamamen
simülasyon motoruna aittir; bu betik yalnız sonuçları sıralar ve çizer.
"""

import argparse
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ayros.assignment import load_dispatch
from ayros.console import safe_console
from ayros.model import RoadStatus
from ayros.scenario import load_scenario
from ayros.simulation import Simulation

SCENARIO = 'data/bolgesel_ag.json'
FLEET = 'data/gorev_senaryosu_12_arac.json'


def _finish(graph, fleet, closed=None):
    sim = Simulation(graph, fleet)
    if closed:
        sim.change_roads({closed: 'closed'})
    state = sim.snapshot()
    while state['can_advance']:
        state = sim.step()
    return state


def analyze(scenario, fleet):
    graph = scenario.graph
    base = _finish(graph, fleet)
    base_arrival = {v['id']: v['arrival_at'] for v in base['vehicles'] if v['task_id']}
    used = sorted({e['road_id'] for e in base['events'] if e['kind'] == 'departed'})
    roads = []
    for road_id in used:
        if graph.roads[road_id].status == RoadStatus.CLOSED:
            continue
        state = _finish(graph, fleet, road_id)
        arrival = {v['id']: v['arrival_at'] for v in state['vehicles'] if v['task_id']}
        blocked = sorted(k for k, value in arrival.items() if value is None)
        delays = {k: round(arrival[k] - base_arrival[k], 3) for k in arrival
                  if arrival[k] is not None and arrival[k] - base_arrival[k] > 1e-9}
        road = graph.roads[road_id]
        roads.append({
            'road_id': road_id, 'source': road.source, 'target': road.target,
            'road_type': road.road_type, 'status': road.status.value,
            'affected_vehicles': sorted(set(delays) | set(blocked)),
            'blocked_vehicles': blocked,
            'total_delay_min': round(sum(delays.values()), 3),
            'max_delay_min': max(delays.values(), default=0),
            'lost_delivery_boxes': base['logistics']['delivered'] - state['logistics']['delivered'],
        })
    roads.sort(key=lambda r: (-len(r['blocked_vehicles']), -r['lost_delivery_boxes'],
                              -r['total_delay_min'], r['road_id']))
    for rank, road in enumerate(roads, 1):
        road['rank'] = rank
    return {
        'schema_version': 1, 'scenario': SCENARIO, 'fleet': FLEET,
        'method': 'Her yol araçlar merkezden çıkmadan önce tek başına kapatılır; A*, hasar katsayısı 2.',
        'baseline': {'time_min': base['time_min'], 'delivered_boxes': base['logistics']['delivered'],
                     'vehicle_arrivals': base_arrival},
        'tested_roads': len(roads),
        'roads_blocking_a_vehicle': sum(bool(r['blocked_vehicles']) for r in roads),
        'roads': roads,
    }


def draw(scenario, result, top=10):
    """Yolları toplam gecikmeye göre renklendiren harita ve ilk 10 yol tablosu."""
    graph = scenario.graph
    points = [(n.x_km, n.y_km) for n in graph.nodes.values()] + list(scenario.river)
    points += [p for road in graph.roads.values() for p in road.via]
    xmin, xmax = min(x for x, _ in points), max(x for x, _ in points)
    ymin, ymax = min(y for _, y in points), max(y for _, y in points)
    scale = min(1100 / (xmax - xmin), 520 / (ymax - ymin))

    def project(point):
        return 50 + (point[0] - xmin) * scale, 640 - (point[1] - ymin) * scale

    def line(road):
        geometry = [(graph.nodes[road.source].x_km, graph.nodes[road.source].y_km), *road.via,
                    (graph.nodes[road.target].x_km, graph.nodes[road.target].y_km)]
        return ' '.join(f'{x:.1f},{y:.1f}' for x, y in map(project, geometry))

    def text(x, y, value, size=16, weight='400', color='#162438', anchor='start'):
        svg.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" '
                   f'text-anchor="{anchor}">{escape(str(value))}</text>')

    def number(value):
        return f'{value:.2f}'.rstrip('0').rstrip('.').replace('.', ',')

    delay = {r['road_id']: r['total_delay_min'] for r in result['roads']}
    worst = max(delay.values())
    bands = [(10, '#b91c1c', 7, '10 dk ve üzeri'), (5, '#ea580c', 5.5, '5–10 dk'),
             (0, '#facc15', 4, '5 dk altı')]
    leaders = result['roads'][:top]
    height = 712 + 78 + 34 * len(leaders) + 30
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" '
           'role="img" aria-labelledby="title desc">',
           '<title id="title">Bölgesel ağda yol kritikliği</title>',
           '<desc id="desc">Kullanılan her yol tek başına kapatıldığında araçların toplam varış gecikmesi.</desc>',
           f'<rect width="1200" height="{height}" fill="white"/>', '<g font-family="Arial, sans-serif">']
    text(30, 40, 'Hangi yol kapanırsa yardım en çok gecikir?', 26, '700')
    text(30, 70, f'Araçların kullandığı {result["tested_roads"]} yol tek tek kapatıldı. Renk, o yol kapanınca '
         'tüm araçların toplam gecikmesidir.', 16, color='#43536b')
    svg.append('<rect x="20" y="88" width="1160" height="590" rx="10" fill="#f8fafc" stroke="#d6deea"/>')
    river = ' '.join(f'{x:.1f},{y:.1f}' for x, y in map(project, scenario.river))
    svg.append(f'<polyline points="{river}" fill="none" stroke="#dbeafe" stroke-width="26"/>')
    for road in graph.roads.values():
        if road.id not in delay:
            svg.append(f'<polyline points="{line(road)}" fill="none" stroke="#d3dae4" stroke-width="1.3"/>')
    for road_id in sorted(delay, key=delay.get):
        color, width = next((c, w) for limit, c, w, _ in bands if delay[road_id] >= limit)
        svg.append(f'<polyline points="{line(graph.roads[road_id])}" fill="none" stroke="{color}" '
                   f'stroke-width="{width}" stroke-linecap="round"><title>{road_id}: '
                   f'{number(delay[road_id])} dk</title></polyline>')
    for rank, road in enumerate(leaders[:5], 1):
        r = graph.roads[road['road_id']]
        x1, y1 = project((graph.nodes[r.source].x_km, graph.nodes[r.source].y_km))
        x2, y2 = project((graph.nodes[r.target].x_km, graph.nodes[r.target].y_km))
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="13" fill="#162438"/>')
        text(cx, cy + 5, rank, 14, '700', 'white', 'middle')
    for node in graph.nodes.values():
        if node.node_type.value == 'aid_center':
            x, y = project((node.x_km, node.y_km))
            svg.append(f'<rect x="{x-9:.1f}" y="{y-9:.1f}" width="18" height="18" fill="#18273d"/>')
            text(x + 14, y + 6, node.id, 16, '700')
    svg.append('<rect x="30" y="96" width="300" height="106" rx="6" fill="white" fill-opacity="0.92" stroke="#d6deea"/>')
    for i, (_, color, width, label) in enumerate(bands):
        y = 110 + i * 26
        svg.append(f'<line x1="40" y1="{y}" x2="86" y2="{y}" stroke="{color}" stroke-width="{width}"/>')
        text(96, y + 6, label, 15)
    svg.append(f'<line x1="40" y1="188" x2="86" y2="188" stroke="#d3dae4" stroke-width="2"/>')
    text(96, 194, 'Hiçbir aracın kullanmadığı yol', 15)
    top_y = 712
    text(30, top_y, f'En kritik {len(leaders)} yol (siyah numaralar haritadaki ilk 5 yoldur)', 19, '700')
    columns = (30, 110, 250, 400, 560, 760)
    headers = ('Sıra', 'Yol', 'Tür', 'Toplam gecikme', 'En büyük gecikme', 'Etkilenen araçlar')
    svg.append(f'<rect x="20" y="{top_y+14}" width="1160" height="36" fill="#e7eef8"/>')
    for x, value in zip(columns, headers):
        text(x, top_y + 38, value, 15, '700')
    kinds = {'main': 'Ana yol', 'secondary': 'İkincil yol', 'local': 'Mahalle sokağı', 'bridge': 'Köprü'}
    for i, road in enumerate(leaders):
        y = top_y + 78 + i * 34
        svg.append(f'<line x1="20" y1="{y+12}" x2="1180" y2="{y+12}" stroke="#d6deea"/>')
        values = (road['rank'], road['road_id'], kinds.get(road['road_type'], road['road_type']),
                  f'{number(road["total_delay_min"])} dk', f'{number(road["max_delay_min"])} dk',
                  ', '.join(road['affected_vehicles']))
        for x, value in zip(columns, values):
            text(x, y, value, 15)
    if result['roads_blocking_a_vehicle']:
        note = f'{result["roads_blocking_a_vehicle"]} yolun kapanması en az bir aracı hedefine ulaşamaz bıraktı.'
    else:
        note = 'Hiçbir yolun tek başına kapanması bir aracı hedefsiz bırakmadı: kullanılan her yolun alternatifi var.'
    text(30, height - 14, f'{note} En büyük toplam gecikme {number(worst)} dk.', 15, color='#43536b')
    svg.append('</g></svg>')
    return '\n'.join(svg) + '\n'


def main(argv=None):
    safe_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/hafta7')
    args = parser.parse_args(argv)
    scenario = load_scenario(ROOT / SCENARIO)
    fleet = load_dispatch(ROOT / FLEET, scenario.graph)
    result = analyze(scenario, fleet)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'yol_kritikligi.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output / 'yol_kritikligi.svg').write_text(draw(scenario, result), encoding='utf-8')
    for road in result['roads'][:5]:
        print(f'{road["rank"]}. {road["road_id"]} ({road["road_type"]}): toplam {road["total_delay_min"]:.2f} dk, '
              f'araçlar {", ".join(road["affected_vehicles"])}')
    print(f'Sonuçlar: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
