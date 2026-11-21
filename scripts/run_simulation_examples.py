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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/hafta7')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    cases = {}
    for key, event in [('normal', None), ('kapanma', 'hafta7_yol_kapanmasi.json'),
                       ('izolasyon', 'hafta7_yol_izolasyon.json'), ('bolgesel', None)]:
        command = ['--json', str(args.output / f'{key}.json')]
        if key != 'bolgesel':
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
        }
    (args.output/'sonuclar.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    graph = load_scenario(ROOT/'data/hafta7_mikro_ag.json').graph
    (args.output/'simulasyon.svg').write_text(draw_examples(graph, cases), encoding='utf-8')
    print(f'Deney özeti ve görsel: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
