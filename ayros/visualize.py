"""Ek paket kullanmadan, senaryo verisinden basit SVG çizge üretir."""

from html import escape
from pathlib import Path
from textwrap import wrap

from .model import NodeType, RoadStatus
from .routing import CostModel, RouteResult
from .scenario import Scenario


def write_svg(scenario: Scenario, path: str | Path, *, route: RouteResult | None = None,
              cost_model: CostModel | None = None) -> None:
    nodes = scenario.graph.nodes
    min_x, max_x = min(n.x_km for n in nodes.values()), max(n.x_km for n in nodes.values())
    min_y, max_y = min(n.y_km for n in nodes.values()), max(n.y_km for n in nodes.values())
    width, graph_height = (1280, 640) if len(nodes) > 15 else (960, 350)
    scale = min((width - 200) / max(max_x - min_x, 1), graph_height / max(max_y - min_y, 1))
    offset_x = (width - (max_x - min_x) * scale) / 2
    points = {n.id: (offset_x + (n.x_km - min_x) * scale, 160 + (max_y - n.y_km) * scale)
              for n in nodes.values()}
    colors = {RoadStatus.OPEN: "#247c59", RoadStatus.DAMAGED: "#b66a09", RoadStatus.CLOSED: "#c23e42"}
    fills = {NodeType.AID_CENTER: "#1f4b78", NodeType.INTERSECTION: "#5c6776", NodeType.DISASTER_AREA: "#9e3a57"}
    legend_y = 160 + graph_height + 60
    route_lines = wrap("Rota: " + " → ".join(route.path), width=(width - 96) // 10,
                       break_long_words=False, break_on_hyphens=False) if route is not None and route.found else []
    height = legend_y + 120 if route is None else legend_y + 190 + 26 * max(1, len(route_lines))
    route_roads = set(route.road_ids) if route is not None and route.found else set()
    route_label = "Rota hesaplanmadı" if route is None else "Dijkstra • Mavi çerçeve = Seçilen rota" if route.found else "Dijkstra • Rota bulunamadı"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             f'<title id="title">{escape(scenario.name)}</title>',
             '<desc id="desc">Sentetik afet ağı. Yeşil düz yollar açık, turuncu kesikli yollar hasarlı, kırmızı noktalı yollar kapalıdır. Hesaplanan rota mavi çerçeveyle gösterilir.</desc>',
             f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
             '<g font-family="Arial, sans-serif" fill="#17263c">',
             '<text x="48" y="48" font-size="26" font-weight="bold">AYROS MMY | Afet yol ağı</text>',
             f'<text x="48" y="80" font-size="18">{escape(scenario.name)}</text>',
             f'<text x="48" y="108" font-size="14">Sentetik yerel koordinatlar (km) • {route_label}</text>']
    if cost_model is not None:
        parts.append(f'<text x="48" y="132" font-size="13">Yol etiketleri: kimlik ve hasar dahil süre (dk) • Hasar katsayısı: {cost_model.damaged_factor:g}</text>')
    for road in scenario.graph.roads.values():
        x1, y1 = points[road.source]
        x2, y2 = points[road.target]
        cost = cost_model.cost_minutes(road) if cost_model is not None else None
        cost_label = "kapalı" if road.status == RoadStatus.CLOSED else f"{cost:.2f} dk" if cost is not None else ""
        detail = f"{road.id}: {road.source} ↔ {road.target}; {road.distance_km:g} km; temel süre {road.travel_time_min:g} dk; {road.status.value}"
        parts.append(f'<g data-road-id="{escape(road.id)}"><title>{escape(detail)}</title>')
        dash = {RoadStatus.OPEN: "", RoadStatus.DAMAGED: ' stroke-dasharray="12 5"', RoadStatus.CLOSED: ' stroke-dasharray="3 6"'}[road.status]
        if road.id in route_roads:
            parts.append(f'<path data-route-road="{escape(road.id)}" d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" stroke="#2563eb" stroke-width="10" fill="none"/>')
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colors[road.status]}" stroke-width="4"{dash}/>')
        x, y = (x1 + x2) / 2, (y1 + y2) / 2
        label_width = max(38, max(len(road.id), len(cost_label)) * 6.5 + 8)
        label_height = 30 if cost_label else 20
        parts.append(f'<rect x="{x-label_width/2:.1f}" y="{y-label_height/2:.1f}" width="{label_width:.1f}" height="{label_height}" rx="4" fill="#f8fafc"/>')
        parts.append(f'<text x="{x:.1f}" y="{y-2 if cost_label else y+5:.1f}" text-anchor="middle" font-size="12">{escape(road.id)}</text>')
        if cost_label:
            parts.append(f'<text x="{x:.1f}" y="{y+12:.1f}" text-anchor="middle" font-size="11">{escape(cost_label)}</text>')
        parts.append('</g>')
    for node in nodes.values():
        x, y = points[node.id]
        detail = node.name
        if node.node_type == NodeType.DISASTER_AREA:
            detail += f"; {node.affected_count} afetzede, {node.injured_count} yaralı, aciliyet {node.urgency_level}/5"
        endpoint = route is not None and route.found and node.id in (route.path[0], route.path[-1])
        border = ' stroke="#2563eb" stroke-width="5"' if endpoint else ''
        parts.append(f'<g><title>{escape(detail)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="22" fill="{fills[node.node_type]}"{border}/>')
        parts.append(f'<text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-size="14" fill="white">{escape(node.id)}</text></g>')
    parts.extend([f'<text x="48" y="{legend_y}" font-size="15">Düğümler: Lacivert = Yardım merkezi | Gri = Kavşak | Bordo = Afet noktası</text>',
                  f'<text x="48" y="{legend_y+32}" font-size="15">Yollar: Yeşil düz = Açık | Turuncu kesikli = Hasarlı | Kırmızı noktalı = Kapalı</text>',
                  f'<text x="48" y="{legend_y+64}" font-size="14">{len(nodes)} düğüm · {len(scenario.graph.roads)} çift yönlü yol · Ayrıntı için düğüm/yol üzerine gelin.</text>'])
    if route is not None:
        if route.found:
            for i, line in enumerate(route_lines):
                parts.append(f'<text x="48" y="{legend_y+108+i*26}" font-size="18" font-weight="bold">{escape(line)}</text>')
            parts.append(f'<text x="48" y="{legend_y+122+len(route_lines)*26}" font-size="15">Maliyet / hasar dahil süre: {route.cost_min:.2f} dk | Mesafe: {route.distance_km:.2f} km | İncelenen düğüm: {route.settled_nodes}</text>')
        else:
            parts.append(f'<text x="48" y="{legend_y+108}" font-size="18" font-weight="bold">Rota bulunamadı: Hedefe geçilebilir yollardan ulaşılamıyor.</text>')
    parts.append('</g></svg>')
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(parts) + "\n", encoding="utf-8")
