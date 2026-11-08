"""Gerçek atama sonuçları ve yol geometrisinden SVG haritası üretir."""

from html import escape
from pathlib import Path

from .assignment import REASONS, SERVICES
from .model import NodeType, RoadStatus


def assignment_svg(scenario, entries, *, fleet=None, report=False):
    graph = scenario.graph
    coords = [(n.x_km, n.y_km) for n in graph.nodes.values()]
    coords += [p for r in graph.roads.values() for p in r.via]
    coords += list(scenario.river)
    xmin, xmax = min(x for x, y in coords), max(x for x, y in coords)
    ymin, ymax = min(y for x, y in coords), max(y for x, y in coords)
    scale = min(1080 / max(xmax-xmin, 1), 560 / max(ymax-ymin, 1))

    def project(p):
        return (600 + (p[0]-(xmin+xmax)/2)*scale, 425 - (p[1]-(ymin+ymax)/2)*scale)

    def vertices(geometry):
        return ' '.join(f'{x:.2f},{y:.2f}' for x, y in map(project, geometry))

    def node_point(id):
        n = graph.nodes[id]
        return n.x_km, n.y_km

    table_entries = [e for e in entries if e.vehicle] if report else entries
    height = 930 + 43 * len(table_entries) if report else 865 + 37 * len(entries)
    palette = ('#2563eb', '#7c3aed', '#0f766e', '#c2410c', '#be185d', '#0369a1', '#854d0e', '#334155')
    colors = {e.vehicle.id: palette[i % len(palette)] for i, e in enumerate(e for e in entries if e.vehicle)}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {height}" width="1200" height="{height}" role="img" aria-labelledby="map-title">',
             '<title id="map-title">AYROS MMY — Araçların başlangıç merkezleri ve hedef rotaları</title>',
             f'<rect width="1200" height="{height}" fill="#ffffff"/>',
             '<g font-family="Arial, sans-serif" fill="#172033">']
    parts.append('<defs>')
    # Numeric marker IDs keep arbitrary vehicle names out of URL fragments.
    marker_ids = {vid: f'arrow-{i}' for i, vid in enumerate(colors)}
    for vid, color in colors.items():
        parts.append(f'<marker id="{marker_ids[vid]}" viewBox="0 0 10 10" refX="8" refY="5" '
                     f'markerWidth="4" markerHeight="4" orient="auto-start-reverse">'
                     f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>')
    parts.append('</defs>')

    def text(x, y, value, size=16, color='#172033'):
        if report and size < 18:
            size = 17
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{escape(str(value))}</text>')

    text(40, 44, 'AYROS MMY | Öncelikten araç görevine', 28)
    assigned = sum(e.vehicle is not None for e in entries)
    text(40, 77, f'{assigned} görev atandı • {len(entries)-assigned} görev bekliyor • '
         f'{sum(e.demand for e in entries if e.vehicle and e.service == "logistics")} koli planlandı', 19)
    text(40, 108, 'Başlangıç anı: araçlar merkezlerinde • Kare = çıkış merkezi • Halka = hedef • Oklar = gidiş yönü', 15)
    parts.append('<rect x="30" y="130" width="1140" height="600" rx="12" fill="#f8fafc" stroke="#dbe3ed"/>')
    if scenario.river:
        parts.append(f'<polyline points="{vertices(scenario.river)}" stroke="#dbeafe" stroke-width="18" fill="none"/>')
    for r in graph.roads.values():
        color = {RoadStatus.OPEN: '#b6c3d0', RoadStatus.DAMAGED: '#b45309', RoadStatus.CLOSED: '#e11d48'}[r.status]
        dash = '' if r.status == RoadStatus.OPEN else ' stroke-dasharray="5 4"'
        parts.append(f'<polyline points="{vertices([node_point(r.source), *r.via, node_point(r.target)])}" '
                     f'stroke="{color}" stroke-width="1.5" fill="none"{dash}/>')
    for e in entries:
        if not e.vehicle:
            continue
        parts.append(f'<g data-route-vehicle="{escape(e.vehicle.id)}" data-route-target="{escape(e.need.node.id)}">')
        for index, rid in enumerate(e.route.road_ids):
            r = graph.roads[rid]
            via = r.via if r.source == e.route.path[index] else tuple(reversed(r.via))
            geometry = [node_point(e.route.path[index]), *via, node_point(e.route.path[index+1])]
            arrow = f' marker-end="url(#{marker_ids[e.vehicle.id]})"' if index % 4 == 2 or index == len(e.route.road_ids)-1 else ''
            parts.append(f'<polyline data-vehicle="{escape(e.vehicle.id)}" data-road="{escape(rid)}" '
                         f'points="{vertices(geometry)}" stroke="{colors[e.vehicle.id]}" stroke-width="4" '
                         f'fill="none" stroke-linejoin="round"{arrow}><title>{escape(e.vehicle.id)}: {escape(e.vehicle.center)} → {escape(e.need.node.id)}</title></polyline>')
        parts.append('</g>')
    by_target = {}
    for entry in entries:
        by_target.setdefault(entry.need.node.id, []).append(entry)
    for n in graph.nodes.values():
        x, y = project(node_point(n.id))
        if n.node_type == NodeType.INTERSECTION:
            continue
        target_entries = by_target.get(n.id, [])
        e = next((item for item in target_entries if item.vehicle), next(iter(target_entries),None))
        color = "#334155" if len(target_entries)>1 else colors[e.vehicle.id] if e and e.vehicle else '#e11d48' if e and e.status == 'unreachable' else '#334155'
        if n.node_type == NodeType.AID_CENTER:
            parts.append(f'<rect x="{x-8}" y="{y-8}" width="16" height="16" fill="#172033" stroke="white" stroke-width="2"/>')
        else:
            parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{color}" stroke="white" stroke-width="2"/>')
            for e in target_entries:
                if not e.vehicle:
                    continue
                color=colors[e.vehicle.id]
                parts.append(f'<circle data-target-vehicle="{escape(e.vehicle.id)}" data-target-region="{escape(e.need.node.id)}" cx="{x}" cy="{y}" r="12" fill="none" stroke="{color}" stroke-width="2"/>')
        text(round(x+10, 2), round(y-10, 2), n.id, 15, color)
    vehicles = fleet.vehicles if fleet is not None else tuple(e.vehicle for e in entries if e.vehicle)
    assigned_by_vehicle = {e.vehicle.id: e for e in entries if e.vehicle}
    for center in sorted({v.center for v in vehicles}):
        x, y = project(node_point(center))
        members = sorted((v for v in vehicles if v.center == center), key=lambda v: v.id)
        bx = 32 if x < 600 else 987
        by = max(140, min(y+20 if x >= 600 and y > 500 else y-35, 720-(32+20*len(members))))
        bw = 160 if x < 600 else 176
        parts.append(f'<path d="M {x} {y} L {bx+bw if x<600 else bx} {by+15}" stroke="#64748b" fill="none"/>')
        parts.append(f'<g data-center="{escape(center)}"><rect x="{bx}" y="{by}" width="{bw}" height="{32+20*len(members)}" rx="5" fill="white" stroke="#94a3b8"/>')
        text(bx+8, by+19, f'BAŞLANGIÇ {center}', 13)
        for i, v in enumerate(members):
            e = assigned_by_vehicle.get(v.id)
            label = f'{v.id} → {e.need.node.id}' if e else f'{v.id} müsait değil' if not v.available else f'{v.id} görev atanmadı'
            text(bx+8, by+40+i*20, label, 13, colors.get(v.id, '#64748b'))
        parts.append('</g>')
    text(40, 759, 'Yollar: gri açık • turuncu kesikli hasarlı • kırmızı kesikli kapalı. Ağ sentetiktir.', 15)
    text(40, 785, 'Bu bir görev planıdır; araçlar henüz hareket etmez. Ortak yollarda renkler örtüşebilir.', 14)
    if report:
        columns = (40, 130, 280, 520, 760, 980)
        for x, label in zip(columns, ('Sıra', 'Araç', 'Çıkış → hedef', 'Görev / miktar', 'Süre (dk)', 'Mesafe (km)')):
            text(x, 822, label, 20)
        for i, e in enumerate(table_entries):
            y = 855 + i*43
            parts.append(f'<rect x="30" y="{y-23}" width="1140" height="43" fill="{"#f1f5f9" if i%2 == 0 else "#ffffff"}"/>')
            values = (e.rank, e.vehicle.id, f'{e.vehicle.center} → {e.need.node.id}',
                      f'{SERVICES[e.service]} {e.demand} {e.unit}', f'{e.route.cost_min:.3f}', f'{e.route.distance_km:.2f}')
            for x, value in zip(columns, values):
                text(x, y+3, value, 21, colors[e.vehicle.id])
        text(40, height-28, 'Tablo atanan görevleri gösterir; bekleyen hedeflerin nedenleri sonuçlar bölümünde açıklanır.', 19)
        parts.append('</g></svg>')
        return '\n'.join(parts)+'\n'
    columns = (40, 100, 190, 275, 375, 510, 680)
    for x, label in zip(columns, ('Sıra', 'Hedef', 'Görev', 'Talep', 'Araç', 'Çıkış → hedef', 'Sonuç / tahmini süre')):
        text(x, 822, label, 16)
    for i, e in enumerate(entries):
        y = 850 + i*37
        parts.append(f'<rect x="30" y="{y-20}" width="1140" height="37" fill="{"#f1f5f9" if i%2 == 0 else "#ffffff"}"/>')
        values = (e.rank, e.need.node.id, SERVICES[e.service], f'{e.demand} {e.unit}',
                  e.vehicle.id if e.vehicle else '—', f'{e.vehicle.center} → {e.need.node.id}' if e.vehicle else '—',
                  f'{e.route.cost_min:.2f} dk • {e.route.distance_km:.2f} km • kapasite {e.vehicle.capacity}' if e.vehicle else REASONS[e.status])
        for x, value in zip(columns, values):
            text(x, y+3, value, 15, colors[e.vehicle.id] if e.vehicle else '#475569')
    parts.append('</g></svg>')
    return '\n'.join(parts)+'\n'


def write_assignment_svg(scenario, entries, path, *, fleet=None):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(assignment_svg(scenario, entries, fleet=fleet), encoding='utf-8')
