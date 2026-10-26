"""Aynı ağdaki iki aramanın kesinleştirdiği düğümleri yan yana gösterir."""

from html import escape
from pathlib import Path

from .model import NodeType, RoadStatus, ValidationError
from .routing import CostModel, RouteResult
from .scenario import Scenario


def write_search_svg(scenario: Scenario, path: str | Path, *,
                     start: str, target: str, dijkstra: RouteResult, astar: RouteResult,
                     cost_model: CostModel | None = None) -> None:
    """Ölçüm dışındaki record_search=True sonuçlarını kullanır; ağ değişmez."""
    results = (dijkstra, astar)
    if start not in scenario.graph.nodes or target not in scenario.graph.nodes:
        raise ValidationError('Arama görselinin başlangıç veya hedefi bulunamadı.')
    for route, name in zip(results, ('dijkstra', 'astar')):
        if route.algorithm != name or not route.settled_order or len(route.settled_order) != route.settled_nodes:
            raise ValidationError('Arama görseli için iki algoritmanın tam düğüm kaydı gerekir.')
        if len(set(route.settled_order)) != route.settled_nodes or any(n not in scenario.graph.nodes for n in route.settled_order):
            raise ValidationError('Arama kaydında geçersiz veya tekrarlanan düğüm var.')
        if route.settled_order[0] != start or (route.found and (not route.path or route.path[0] != start or route.path[-1] != target)):
            raise ValidationError('Arama kaydı seçilen başlangıç ve hedefle uyuşmuyor.')
    if dijkstra.settled_order[0] != astar.settled_order[0] or dijkstra.found != astar.found:
        raise ValidationError('Arama kayıtları aynı sorguya ait olmalıdır.')
    if dijkstra.found and dijkstra.path[-1] != astar.path[-1]:
        raise ValidationError('Arama kayıtlarının hedefleri farklı.')
    nodes = scenario.graph.nodes
    coords = [(n.x_km, n.y_km) for n in nodes.values()] + list(scenario.river)
    coords += [p for r in scenario.graph.roads.values() for p in r.via]
    lo_x, hi_x = min(p[0] for p in coords), max(p[0] for p in coords)
    lo_y, hi_y = min(p[1] for p in coords), max(p[1] for p in coords)
    scale = min(780/max(hi_x-lo_x, 1), 540/max(hi_y-lo_y, 1))
    offset = (900-(hi_x-lo_x)*scale)/2

    def project(p):
        return offset+(p[0]-lo_x)*scale, 175+(hi_y-p[1])*scale

    points = {n.id: project((n.x_km, n.y_km)) for n in nodes.values()}
    factor = (cost_model or CostModel()).damaged_factor
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="840" viewBox="0 0 1800 840" role="img" aria-labelledby="title desc">',
             f'<title id="title">{escape(scenario.name)} — Dijkstra ve A* arama karşılaştırması</title>',
             '<desc id="desc">İki panel aynı ölçek ve aynı yol ağıdır. Sarı halkalar maliyeti kesinleştirilen düğümleri, mavi çizgiler rotayı gösterir.</desc>',
             '<rect width="1800" height="840" fill="#f8fafc"/>',
             '<g font-family="Arial, sans-serif" fill="#17263c">',
             f'<text x="36" y="36" font-size="25" font-weight="bold">{escape(scenario.name)} | Aramanın incelediği düğümler</text>',
             f'<text x="36" y="64" font-size="16">{escape(start)} → {escape(target)} · Hasar katsayısı {factor:g} · {len(nodes)} düğüm · {len(scenario.graph.roads)} yol · Sentetik yerel koordinatlar (km) · İki panel aynı ölçek</text>',
             '<path d="M900 85 V745" stroke="#cbd5e1"/>']
    for i, (result, label) in enumerate(zip(results, ('Dijkstra', 'A*'))):
        parts.append(f'<g data-algorithm="{result.algorithm}" transform="translate({i*900} 0)">')
        status = f'{result.cost_min:.2f} dk' if result.found else 'Rota bulunamadı'
        parts.append(f'<text x="36" y="106" font-size="24" font-weight="bold">{label}</text>')
        parts.append(f'<text x="36" y="134" font-size="17">{result.settled_nodes} düğüm incelendi · {status}</text>')
        if scenario.river:
            vertices = ' '.join(f'{x:.2f},{y:.2f}' for x,y in map(project, scenario.river))
            parts.append(f'<polyline points="{vertices}" fill="none" stroke="#c4e5f0" stroke-width="{0.45*scale:.2f}"/>')
        for road in scenario.graph.roads.values():
            vertices = ' '.join(f'{x:.2f},{y:.2f}' for x,y in [points[road.source], *map(project, road.via), points[road.target]])
            color = '#dc6262' if road.status == RoadStatus.CLOSED else '#c18b37' if road.status == RoadStatus.DAMAGED else '#a4adb9'
            dash = ' stroke-dasharray="3 4"' if road.status != RoadStatus.OPEN else ''
            width = 4 if road.road_type == 'bridge' else 2
            parts.append(f'<polyline data-road="{escape(road.id)}" points="{vertices}" fill="none" stroke="{color}" stroke-width="{width}"{dash}><title>{escape(road.id)} · {escape(road.source)} ↔ {escape(road.target)} · {road.status.value}</title></polyline>')
        for road_id in result.road_ids:
            road = scenario.graph.roads[road_id]
            vertices = ' '.join(f'{x:.2f},{y:.2f}' for x,y in [points[road.source], *map(project, road.via), points[road.target]])
            parts.append(f'<polyline data-route-road="{escape(road.id)}" points="{vertices}" fill="none" stroke="#2563eb" stroke-width="4"/>')
        order = {n: j+1 for j,n in enumerate(result.settled_order)}
        labels = []
        occupied = [(x-8,y-8,x+8,y+8) for x,y in points.values()]
        for node in nodes.values():
            x,y = points[node.id]
            special = node.node_type != NodeType.INTERSECTION
            radius = 7 if special else 3.2
            if node.id in order:
                parts.append(f'<circle data-settled-node="{escape(node.id)}" data-order="{order[node.id]}" cx="{x:.2f}" cy="{y:.2f}" r="{radius+3}" fill="#f3c75b"/>')
            fill = '#1f4b78' if node.node_type == NodeType.AID_CENTER else '#9e3a57' if special else '#64748b'
            detail = f'{node.id}; '+(f"kesinleştirme sırası {order[node.id]}" if node.id in order else 'kesinleştirilmedi')
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}"><title>{escape(detail)}</title></circle>')
            if special:
                lx,ly = x+11,y-9
                for dx,dy in ((11,-9),(11,18),(-38,-9),(-38,18),(11,-21),(-38,-21)):
                    box = (x+dx,y+dy-13,x+dx+29,y+dy+3)
                    if not any(box[0]<b[2] and box[2]>b[0] and box[1]<b[3] and box[3]>b[1] for b in occupied):
                        lx,ly = x+dx,y+dy
                        break
                occupied.append((lx,ly-13,lx+29,ly+3))
                labels.append(f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="13" font-weight="bold" stroke="#f8fafc" stroke-width="3" paint-order="stroke">{escape(node.id)}</text>')
        parts.extend(labels)
        parts.append('</g>')
    parts.extend(['<text x="36" y="770" font-size="16">Sarı halka = kesinleştirilen düğüm · Mavi çizgi = rota · Lacivert = merkez · Bordo = afet noktası</text>',
                  '<text x="36" y="796" font-size="15">Yollar: gri açık, turuncu kesikli hasarlı, kırmızı kesikli kapalı. Düğüm üzerine gelerek arama sırasını görebilirsiniz.</text>',
                  '<text x="36" y="822" font-size="14">Bu görselin kayıtları süre ölçümünden ayrı çalıştırmada alınır. Aynı maliyetli rotalar farklı olabilir; az düğüm daha kısa süreyi garanti etmez.</text>',
                  '</g></svg>'])
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(parts)+'\n', encoding='utf-8')
