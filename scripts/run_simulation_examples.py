"""7. hafta deneylerini ve gerçek kontrol noktalarından açıklayıcı SVG'yi üret."""

import argparse
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ayros.simulate import main as simulate
from ayros.scenario import load_scenario

# Bölgesel ağda köprü olayları. Hepsi ilk varış adımından sonra uygulanır.
REGIONAL_EVENTS = {
    'kopru_kapanmasi': 'R178 köprüsü kapalı',
    'kopruler_hasarli': 'R178 ve R180 köprüleri hasarlı',
    'tum_kopruler_kapali': 'Üç köprü de kapalı',
}


def number(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.').replace('.', ',')


def draw_examples(graph, cases):
    """Şematik yerleşim; süreler, yol durumları ve rotalar motor çıktısıdır."""
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="900" viewBox="0 0 1120 900" role="img" aria-labelledby="title desc">',
           '<title id="title">Yol değişince araç ne yapar</title>',
           '<desc id="desc">Aynı 100 koli görevinin normal, alternatif rotalı ve yolu kapalı üç koşulu. Mavi kalan rota, gri açık yol, kırmızı kapalı yol.</desc>',
           '<rect width="1120" height="900" fill="white"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#162438} .body{font-size:21px} .small{font-size:18px;fill:#43536b} .head{font-size:24px;font-weight:700}</style>',
           '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#2453d6"/></marker></defs>']

    def text(x, y, value, cls='body'):
        svg.append(f'<text x="{x}" y="{y}" class="{cls}">{escape(str(value))}</text>')

    text(12, 32, 'Yol değişince araç ne yapar?', 'head')
    text(12, 65, 'V1: 120 koli kapasiteli lojistik araç  |  Görev A-L: A bölgesine 100 koli', 'small')
    config = [('normal', '1  Yol açık', 'initial'),
              ('kapanma', '2  K noktasında R2 kapanır', 'after_event'),
              ('izolasyon', '3  K noktasında R2 ve R3 kapanır', 'after_event')]
    for i, (key, title, label) in enumerate(config):
        top = 90 + i * 235
        state = next(c['state'] for c in cases[key]['checkpoints'] if c['label'] == label)
        final = cases[key]['final']
        vehicle = state['vehicles'][0]
        svg.append(f'<rect x="8" y="{top}" width="1104" height="220" rx="8" fill="#f6f8fc" stroke="#ced7e5"/>')
        text(25, top+32, title, 'head')
        # Coordinates follow the input graph, with y up and a schematic aspect ratio.
        coords = {n.id: (60 + n.x_km*215, top+168-n.y_km*95) for n in graph.nodes.values()}
        for road in graph.roads.values():
            x1,y1=coords[road.source]; x2,y2=coords[road.target]
            closed = state['roads'][road.id] == 'closed'
            color, dash = ('#c52835', '8 5') if closed else ('#b2bdcd', 'none')
            svg.append(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="4" stroke-dasharray="{dash}"/>')
            label_x, label_y = (x1+x2)/2, (y1+y2)/2
            if road.id == 'R3': label_x -= 115
            elif road.id == 'R2': label_y += 28
            else: label_y -= 12
            text(label_x, label_y, f'{road.id} · {number(road.travel_time_min)} dk', 'small')
        for a,b in zip(vehicle['remaining_path'], vehicle['remaining_path'][1:]):
            x1,y1=coords[a];x2,y2=coords[b]
            # Stop the arrow before the target node to keep its direction visible.
            ratio = 0.9
            svg.append(f'<path d="M{x1} {y1} L{x1+(x2-x1)*ratio} {y1+(y2-y1)*ratio}" fill="none" stroke="#2453d6" stroke-width="5" marker-end="url(#arrow)"/>')
        for node,(x,y) in coords.items():
            if node == 'H0':
                svg.append(f'<rect x="{x-8}" y="{y-8}" width="16" height="16" fill="#18273d"/>')
            else:
                svg.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#18273d"/>')
            text(x+13, y+24 if node != 'B' else y-12, node, 'small')
        vx,vy = coords[vehicle['node']]
        svg.append(f'<circle cx="{vx}" cy="{vy}" r="16" fill="white" stroke="#2453d6" stroke-width="4"/>')
        text(vx-10,vy+6,'V1','small')
        text(600,top+69, f'Gösterilen an: {number(state["time_min"])} dakika')
        text(600,top+101, f'Araç konumu: {vehicle["node"]}  |  Hedef: A')
        if key == 'normal':
            text(600,top+133, 'Kalan rota: H0 → K → A')
            text(600,top+170, f'Sonuç: {number(final["time_min"])}. dakikada 100 koli teslim')
        elif key == 'kapanma':
            text(600,top+133, 'Yeni rota: K → B → A')
            text(600,top+170, f'Sonuç: {number(final["time_min"])}. dakikada 100 koli teslim')
        else:
            text(600,top+133, 'Uygun rota yok: araç K noktasında bekler')
            text(600,top+170, f'Teslim: {final["logistics"]["delivered"]}  |  Araçta ayrılmış: {final["logistics"]["reserved"]} koli')
        text(600,top+200, 'Aynı araç ve görev korunur; merkeze geri dönülmez.', 'small')
    text(12, 824, 'Mavi ok: kalan rota     Mavi halka V1: mevcut konum     Kırmızı kesik: kapalı yol', 'small')
    text(12, 853, 'Normal ve olaylı koşullar ayrı deneylerdir. Şemadaki küçük ağ doğrulama içindir.', 'small')
    text(12, 882, 'Ana bölgesel ağ korunur: 180 düğüm, 348 yol, 12 araç ve 16 görev.', 'small')
    svg.append('</svg>')
    return '\n'.join(svg) + '\n'


def draw_bridge_experiment(scenario, cases):
    """Bölgesel ağda R178 kapanınca S02'nin ilk ve yeni rotası; dört koşulun sonuç tablosu."""
    graph = scenario.graph
    points = [(n.x_km, n.y_km) for n in graph.nodes.values()] + list(scenario.river)
    points += [p for road in graph.roads.values() for p in road.via]
    xmin, xmax = min(x for x, _ in points), max(x for x, _ in points)
    ymin, ymax = min(y for _, y in points), max(y for _, y in points)
    scale = min(1100 / (xmax - xmin), 560 / (ymax - ymin))

    def project(point):
        return 50 + (point[0] - xmin) * scale, 690 - (point[1] - ymin) * scale

    def road_points(road_id, start):
        road = graph.roads[road_id]
        via = road.via if road.source == start else tuple(reversed(road.via))
        end = road.target if road.source == start else road.source
        geometry = [(graph.nodes[start].x_km, graph.nodes[start].y_km), *via,
                    (graph.nodes[end].x_km, graph.nodes[end].y_km)]
        return ' '.join(f'{x:.1f},{y:.1f}' for x, y in map(project, geometry))

    def path_lines(path, roads, color, width, dash=''):
        dash = f' stroke-dasharray="{dash}"' if dash else ''
        for start, road_id in zip(path, roads):
            svg.append(f'<polyline points="{road_points(road_id, start)}" fill="none" stroke="{color}" '
                       f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"{dash}/>')

    def text(x, y, value, size=17, weight='400', color='#162438', anchor='start'):
        svg.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" '
                   f'text-anchor="{anchor}">{escape(str(value))}</text>')

    case = cases['kopru_kapanmasi']
    initial = next(c['state'] for c in case['checkpoints'] if c['label'] == 'initial')
    s02_initial = next(v for v in initial['vehicles'] if v['id'] == 'S02')
    change = next(e for e in case['final']['events'] if e['kind'] == 'route_changed' and e['vehicle_id'] == 'S02')
    old_path, old_roads = s02_initial['remaining_path'], s02_initial['remaining_roads']
    index = old_path.index(change['node'])
    done_path, done_roads = old_path[:index + 1], old_roads[:index]
    new_path = change['new_path']
    final_roads = case['final']['roads']

    def connecting_road(a, b):
        # Yeni yol kimlikleri, olay günlüğündeki düğüm dizisinden ve son yol durumlarından bulunur.
        options = [r for r in graph.roads.values() if {r.source, r.target} == {a, b}
                   and final_roads[r.id] != 'closed']
        return min(options, key=lambda r: (r.travel_time_min, r.id)).id

    new_roads = [connecting_road(a, b) for a, b in zip(new_path, new_path[1:])]
    arrivals = {key: cases[key]['final'] for key in ('bolgesel', *REGIONAL_EVENTS)}

    def arrival(key, vehicle_id):
        vehicle = next(v for v in arrivals[key]['vehicles'] if v['id'] == vehicle_id)
        if vehicle['arrival_at'] is None:
            return 'Ulaşamadı, bekliyor'
        return f'{number(vehicle["arrival_at"])} dk'

    height = 1010
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" '
           'role="img" aria-labelledby="title desc">',
           '<title id="title">Bölgesel ağda köprü kapanınca yeniden rota</title>',
           '<desc id="desc">R178 köprüsü kapanınca S02 sağlık aracının ilk ve yeni rotası ile dört koşulun varış süreleri.</desc>',
           f'<rect width="1200" height="{height}" fill="white"/>', '<g font-family="Arial, sans-serif">']
    text(30, 40, 'Bölgesel ağda köprü kapanınca ne olur?', 26, '700')
    text(30, 72, '180 düğüm, 348 yol, 3 köprü. S02 sağlık aracı H0 merkezinden A11 bölgesine gidiyor.', 17, color='#43536b')
    svg.append('<rect x="20" y="90" width="1160" height="620" rx="10" fill="#f8fafc" stroke="#d6deea"/>')
    river = ' '.join(f'{x:.1f},{y:.1f}' for x, y in map(project, scenario.river))
    svg.append(f'<polyline points="{river}" fill="none" stroke="#dbeafe" stroke-width="26"/>')
    for road in graph.roads.values():
        bridge = road.road_type == 'bridge'
        svg.append(f'<polyline points="{road_points(road.id, road.source)}" fill="none" '
                   f'stroke="{"#64748b" if bridge else "#c7d0dc"}" stroke-width="{5 if bridge else 1.4}"/>')
    path_lines(old_path, old_roads, '#ea580c', 5, '10 7')
    path_lines(done_path, done_roads, '#2453d6', 6)
    path_lines(new_path, new_roads, '#2453d6', 6)
    for road_id in ('R178', 'R179', 'R180'):
        road = graph.roads[road_id]
        x1, y1 = project((graph.nodes[road.source].x_km, graph.nodes[road.source].y_km))
        x2, y2 = project((graph.nodes[road.target].x_km, graph.nodes[road.target].y_km))
        if road_id == 'R178':
            svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#c52835" '
                       'stroke-width="7" stroke-dasharray="7 5"/>')
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            svg.append(f'<path d="M{cx-11:.1f} {cy-11:.1f} L{cx+11:.1f} {cy+11:.1f} M{cx+11:.1f} {cy-11:.1f} '
                       f'L{cx-11:.1f} {cy+11:.1f}" stroke="#c52835" stroke-width="5"/>')
        text((x1 + x2) / 2, min(y1, y2) - 16, f'{road_id} köprü', 15, '700',
             '#c52835' if road_id == 'R178' else '#475569', 'middle')
    for node in graph.nodes.values():
        x, y = project((node.x_km, node.y_km))
        if node.node_type.value == 'aid_center':
            svg.append(f'<rect x="{x-9:.1f}" y="{y-9:.1f}" width="18" height="18" fill="#18273d"/>')
            text(x + 14, y + 6, node.id, 16, '700')
        elif node.id == 'A11':
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="white" stroke="#18273d" stroke-width="4"/>')
            text(x + 18, y + 6, 'A11 hedef', 16, '700')
    vx, vy = project((graph.nodes[change['node']].x_km, graph.nodes[change['node']].y_km))
    svg.append(f'<circle cx="{vx:.1f}" cy="{vy:.1f}" r="14" fill="white" stroke="#2453d6" stroke-width="4"/>')
    text(vx - 10, vy + 38, f'S02 burada yeni rota buldu ({number(change["time_min"])}. dk)', 15, '700', '#2453d6')
    svg[-1] = svg[-1].replace('<text ', '<text paint-order="stroke" stroke="white" stroke-width="5" ', 1)
    legend = [('#ea580c', '10 7', f'İlk rota: varış {arrival("bolgesel", "S02")}'),
              ('#2453d6', '', f'Gerçekleşen rota: varış {arrival("kopru_kapanmasi", "S02")}'),
              ('#c52835', '7 5', 'Kapanan köprü (R178)')]
    for i, (color, dash, label) in enumerate(legend):
        y = 112 + i * 26
        dash = f' stroke-dasharray="{dash}"' if dash else ''
        svg.append(f'<line x1="40" y1="{y}" x2="88" y2="{y}" stroke="{color}" stroke-width="5"{dash}/>')
        text(98, y + 6, label, 16)
    top = 740
    text(30, top, 'Dört koşulun sonucu (yol olayı ilk varış adımından sonra, 1,65. dakikada uygulanır)', 19, '700')
    columns = (30, 370, 640, 900)
    headers = ('Koşul', 'S02 sağlık, H0→A11', 'V04 lojistik, H2→A04', 'Teslim edilen koli')
    svg.append(f'<rect x="20" y="{top+14}" width="1160" height="38" fill="#e7eef8"/>')
    for x, value in zip(columns, headers):
        text(x, top + 40, value, 16, '700')
    rows = [('Olay yok', 'bolgesel')] + [(label, key) for key, label in REGIONAL_EVENTS.items()]
    for i, (label, key) in enumerate(rows):
        y = top + 82 + i * 40
        svg.append(f'<line x1="20" y1="{y+14}" x2="1180" y2="{y+14}" stroke="#d6deea"/>')
        values = (label, arrival(key, 'S02'), arrival(key, 'V04'),
                  f'{arrivals[key]["logistics"]["delivered"]} / {arrivals[key]["logistics"]["requested"]}')
        for x, value in zip(columns, values):
            text(x, y, value, 16, color='#c52835' if 'Ulaşamadı' in value else '#162438')
    text(30, height - 18, 'Hasarlı köprüde geçiş süresi 2 katına çıkar, rota aynı kalır. Köprüyü kullanmayan araçların rotası değişmez.',
         15, color='#43536b')
    svg.append('</g></svg>')
    return '\n'.join(svg) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/hafta7')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    cases = {}
    for key, event in [('normal', None), ('kapanma', 'hafta7_yol_kapanmasi.json'),
                       ('izolasyon', 'hafta7_yol_izolasyon.json'), ('bolgesel', None),
                       *[(key, f'hafta7_bolgesel_{key}.json') for key in REGIONAL_EVENTS]]:
        command = ['--json', str(args.output / f'{key}.json')]
        if key not in ('bolgesel', *REGIONAL_EVENTS):
            command += ['--scenario', str(ROOT/'data/hafta7_mikro_ag.json'),
                        '--fleet', str(ROOT/'data/hafta7_mikro_arac.json')]
        if event:
            command += ['--events', str(ROOT/'data'/event)]
        if simulate(command):
            return 1
        cases[key] = json.loads((args.output/f'{key}.json').read_text(encoding='utf-8'))
    summary = {'schema_version': 1, 'algorithm': 'astar', 'damage_factor': 2, 'cases': {}}
    for key, payload in cases.items():
        state = payload['final']
        summary['cases'][key] = {
            'input_sha256': payload['input_sha256'], 'time_min': state['time_min'],
            'steps': state['step'], 'logistics': state['logistics'],
            'arrived_vehicles': sum(v['status'] == 'arrived' for v in state['vehicles']),
            'blocked_vehicles': sum(v['status'] == 'blocked' for v in state['vehicles']),
            'teams_arrived': sum(t['team_arrived'] for t in state['tasks']),
            'unassigned_tasks': sum(t['status'] == 'unassigned' for t in state['tasks']),
            'rerouted_vehicles': sorted(v['id'] for v in state['vehicles'] if v['reroutes']),
            'vehicle_arrivals': {v['id']: v['arrival_at'] for v in state['vehicles'] if v['task_id']},
        }
    (args.output/'sonuclar.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    graph = load_scenario(ROOT/'data/hafta7_mikro_ag.json').graph
    (args.output/'simulasyon.svg').write_text(draw_examples(graph, cases), encoding='utf-8')
    regional = load_scenario(ROOT/'data/bolgesel_ag.json')
    (args.output/'bolgesel_kopru.svg').write_text(draw_bridge_experiment(regional, cases), encoding='utf-8')
    print(f'Deney özeti ve görsel: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
