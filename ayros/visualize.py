"""Verideki yol geometrisini, yol durumlarını ve hesaplanan rotayı SVG'ye çizer."""

from html import escape
from pathlib import Path
from textwrap import wrap

from .model import NodeType, RoadStatus
from .routing import CostModel, RouteResult
from .scenario import Scenario


def write_svg(scenario: Scenario, path: str | Path, *, route: RouteResult | None = None,
              cost_model: CostModel | None = None) -> None:
    nodes = scenario.graph.nodes
    detailed = any(road.via for road in scenario.graph.roads.values())
    coordinates = [(n.x_km, n.y_km) for n in nodes.values()]
    coordinates += [p for road in scenario.graph.roads.values() for p in road.via]
    coordinates += list(scenario.river)
    min_x, max_x = min(p[0] for p in coordinates), max(p[0] for p in coordinates)
    min_y, max_y = min(p[1] for p in coordinates), max(p[1] for p in coordinates)
    width, graph_height = (1400, 780) if detailed else (1280, 640) if len(nodes) > 15 else (960, 350)
    scale = min((width - 180) / max(max_x - min_x, 1), graph_height / max(max_y - min_y, 1))
    offset_x = (width - (max_x - min_x) * scale) / 2

    def project(p):
        return offset_x + (p[0] - min_x) * scale, 165 + (max_y - p[1]) * scale

    points = {n.id: project((n.x_km, n.y_km)) for n in nodes.values()}
    colors = {RoadStatus.OPEN: "#39775c", RoadStatus.DAMAGED: "#be720e", RoadStatus.CLOSED: "#c23e42"}
    fills = {NodeType.AID_CENTER: "#1f4b78", NodeType.INTERSECTION: "#65746e", NodeType.DISASTER_AREA: "#9e3a57"}
    type_names = {"main": "Ana yol", "secondary": "İkincil yol", "local": "Mahalle sokağı", "bridge": "Köprü"}
    line_widths = {"main": 7, "secondary": 4, "local": 2.5, "bridge": 7}
    legend_y = 165 + graph_height + 40
    route_lines = wrap("Rota: " + " → ".join(route.path), width=(width - 96) // 10,
                       break_long_words=False, break_on_hyphens=False) if route is not None and route.found else []
    height = legend_y + 140 if route is None else legend_y + 200 + 26 * max(1, len(route_lines))
    route_roads = set(route.road_ids) if route is not None and route.found else set()
    route_label = "Rota hesaplanmadı" if route is None else "Mavi çerçeve = Dijkstra rotası" if route.found else "Dijkstra • Rota bulunamadı"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             f'<title id="title">{escape(scenario.name)}</title>',
             '<desc id="desc">Sentetik afet ağı. Yeşil yollar açık, turuncu kesikli yollar hasarlı, kırmızı noktalı yollar kapalıdır. Yol ayrıntıları üzerine gelince gösterilir.</desc>',
             f'<rect width="{width}" height="{height}" fill="#f8faf7"/>',
             '<g font-family="Arial, sans-serif" fill="#17263c">',
             '<text x="48" y="48" font-size="26" font-weight="bold">AYROS MMY | Afet yol ağı</text>',
             f'<text x="48" y="80" font-size="18">{escape(scenario.name)}</text>',
             f'<text x="48" y="108" font-size="14">Sentetik yerel koordinatlar (km) • {route_label}</text>']
    if cost_model is not None:
        parts.append(f'<text x="48" y="132" font-size="13">Hasar katsayısı: {cost_model.damaged_factor:g} • Yol üzerine gelin: tür, mesafe ve süre • Rota üzerindeki süreler dakika</text>')
    if scenario.river:
        river_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(project, scenario.river))
        parts.extend([f'<polyline data-map-feature="river" points="{river_points}" stroke="#d9e8df" stroke-width="{scale*0.85:.1f}" fill="none" stroke-linejoin="round"/>',
                      f'<polyline points="{river_points}" stroke="#add9e8" stroke-width="{scale*0.45:.1f}" fill="none" stroke-linejoin="round"><title>Sentetik dere koridoru; yakalar yalnızca iki köprüyle bağlıdır.</title></polyline>',
                      '<text x="65" y="200" font-size="12" fill="#73867b" letter-spacing="2">BATI YERLEŞİMİ</text>',
                      f'<text x="{width-225}" y="200" font-size="12" fill="#73867b" letter-spacing="2">DOĞU YERLEŞİMİ</text>'])

    # Etiketler daha sonra çizilir; çizgiler yazıların üstünü örtemez.
    labels = []
    occupied = [(x-28, y-28, x+28, y+28) for x, y in points.values()]
    for road in scenario.graph.roads.values():
        geometry = [points[road.source], *map(project, road.via), points[road.target]]
        cost = cost_model.cost_minutes(road) if cost_model is not None else None
        cost_label = "kapalı" if road.status == RoadStatus.CLOSED else f"{cost:.2f} dk" if cost is not None else ""
        detail = f"{road.id}: {road.source} ↔ {road.target}; {type_names[road.road_type]}; {road.distance_km:g} km; temel {road.travel_time_min:g} dk; maliyet {cost_label or 'hesaplanmadı'}"
        parts.append(f'<g data-road-id="{escape(road.id)}"><title>{escape(detail)}</title>')
        vertices = " ".join(f"{x:.1f},{y:.1f}" for x, y in geometry)
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in geometry)
        stroke_width = line_widths[road.road_type] if detailed else 4
        if road.road_type == "bridge":
            parts.append(f'<path d="{d}" stroke="#8c9da0" stroke-width="13" fill="none"/>')
        if road.id in route_roads:
            parts.append(f'<path data-route-road="{escape(road.id)}" d="{d}" stroke="#2563eb" stroke-width="{stroke_width+7}" fill="none" stroke-linejoin="round"/>')
        dash = {RoadStatus.OPEN: "", RoadStatus.DAMAGED: ' stroke-dasharray="10 5"', RoadStatus.CLOSED: ' stroke-dasharray="3 6"'}[road.status]
        style = f'stroke="{colors[road.status]}" stroke-width="{stroke_width}" fill="none" stroke-linecap="round" stroke-linejoin="round"{dash}'
        if road.via:
            parts.append(f'<polyline data-road-geometry="{escape(road.id)}" points="{vertices}" {style}/>')
        else:
            (x1, y1), (x2, y2) = geometry
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" {style}/>')
        parts.append('</g>')
        # Yoğun ağda süre yalnızca rota üzerinde görünür; tüm süreler başlıkta saklıdır.
        secondary = cost_label if not detailed or road.id in route_roads else ""
        label_width = max(30, max(len(road.id), len(secondary)) * 6.5 + 8)
        label_height = 29 if secondary else 17
        center = ((geometry[1][0]+geometry[-2][0])/2, (geometry[1][1]+geometry[-2][1])/2)
        x, y = center
        for dx, dy in ((0, 0), (0, -20), (0, 20), (-22, 0), (22, 0), (-22, -20), (22, 20)):
            box = (center[0]+dx-label_width/2, center[1]+dy-label_height/2,
                   center[0]+dx+label_width/2, center[1]+dy+label_height/2)
            if not any(box[0] < b[2]+3 and box[2] > b[0]-3 and box[1] < b[3]+3 and box[3] > b[1]-3 for b in occupied):
                x, y = center[0]+dx, center[1]+dy
                break
        occupied.append((x-label_width/2, y-label_height/2, x+label_width/2, y+label_height/2))
        labels.extend([f'<g data-road-label="{escape(road.id)}"><title>{escape(detail)}</title>',
                       f'<rect x="{x-label_width/2:.1f}" y="{y-label_height/2:.1f}" width="{label_width:.1f}" height="{label_height}" rx="3" fill="#f8faf7" fill-opacity="0.95"/>',
                       f'<text x="{x:.1f}" y="{y-2 if secondary else y+4:.1f}" text-anchor="middle" font-size="11">{escape(road.id)}</text>'])
        if secondary:
            labels.append(f'<text x="{x:.1f}" y="{y+11:.1f}" text-anchor="middle" font-size="10">{escape(secondary)}</text>')
        labels.append('</g>')
    parts.extend(labels)
    for node in nodes.values():
        x, y = points[node.id]
        detail = node.name
        if node.node_type == NodeType.DISASTER_AREA:
            detail += f"; {node.affected_count} afetzede, {node.injured_count} yaralı, aciliyet {node.urgency_level}/5"
        endpoint = route is not None and route.found and node.id in (route.path[0], route.path[-1])
        border = ' stroke="#2563eb" stroke-width="4"' if endpoint else ' stroke="#f8faf7" stroke-width="2"'
        radius = 14 if detailed and node.node_type == NodeType.INTERSECTION else 21
        font_size = 10 if radius == 14 else 14
        parts.append(f'<g><title>{escape(detail)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fills[node.node_type]}"{border}/>')
        parts.append(f'<text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" font-size="{font_size}" fill="white">{escape(node.id)}</text></g>')
    road_legend = " · Kalın çizgi ana yol, ince çizgi mahalle sokağı." if detailed else ""
    parts.extend([f'<text x="48" y="{legend_y}" font-size="14">Düğümler: Lacivert = Yardım merkezi | Gri = Kavşak | Bordo = Afet noktası</text>',
                  f'<text x="48" y="{legend_y+28}" font-size="14">Yollar: Yeşil = Açık | Turuncu kesikli = Hasarlı | Kırmızı noktalı = Kapalı</text>',
                  f'<text x="48" y="{legend_y+56}" font-size="14">{len(nodes)} düğüm · {len(scenario.graph.roads)} çift yönlü yol{road_legend}</text>'])
    if scenario.river:
        parts.append(f'<text x="48" y="{legend_y+80}" font-size="13">Mavi şerit dere, gri kenarlı geçiş köprüdür. Yol kırımları yeni kavşak değildir. Gerçek şehir verisi kullanılmamıştır.</text>')
    if route is not None:
        if route.found:
            for i, line in enumerate(route_lines):
                parts.append(f'<text x="48" y="{legend_y+116+i*26}" font-size="17" font-weight="bold">{escape(line)}</text>')
            parts.append(f'<text x="48" y="{legend_y+130+len(route_lines)*26}" font-size="15">Maliyet / hasar dahil süre: {route.cost_min:.2f} dk | Mesafe: {route.distance_km:.2f} km | İncelenen düğüm: {route.settled_nodes}</text>')
        else:
            parts.append(f'<text x="48" y="{legend_y+116}" font-size="18" font-weight="bold">Rota bulunamadı: Hedefe geçilebilir yollardan ulaşılamıyor.</text>')
    parts.append('</g></svg>')
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(parts) + "\n", encoding="utf-8")
