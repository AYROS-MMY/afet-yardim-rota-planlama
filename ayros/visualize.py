"""Ek paket kullanmadan, senaryo verisinden basit SVG çizge üretir."""

from html import escape
from pathlib import Path

from .model import NodeType, RoadStatus
from .routing import RouteResult
from .scenario import Scenario


def write_svg(scenario: Scenario, path: str | Path, *, route: RouteResult | None = None) -> None:
    nodes = scenario.graph.nodes
    min_x, max_x = min(n.x_km for n in nodes.values()), max(n.x_km for n in nodes.values())
    min_y, max_y = min(n.y_km for n in nodes.values()), max(n.y_km for n in nodes.values())
    scale = min(740 / max(max_x - min_x, 1), 350 / max(max_y - min_y, 1))
    offset_x = (960 - (max_x - min_x) * scale) / 2
    points = {n.id: (offset_x + (n.x_km - min_x) * scale, 160 + (max_y - n.y_km) * scale)
              for n in nodes.values()}
    colors = {RoadStatus.OPEN: "#247c59", RoadStatus.DAMAGED: "#b66a09", RoadStatus.CLOSED: "#c23e42"}
    fills = {NodeType.AID_CENTER: "#1f4b78", NodeType.INTERSECTION: "#5c6776", NodeType.DISASTER_AREA: "#9e3a57"}
    height = 760 if route is not None else 680
    route_roads = set(route.road_ids) if route is not None and route.found else set()
    route_label = "Rota hesaplanmadı" if route is None else "Dijkstra • Mavi çerçeve = Seçilen rota"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc">',
             f'<title id="title">{escape(scenario.name)}</title>',
             '<desc id="desc">Sentetik afet ağı. Yeşil düz yollar açık, turuncu kesikli yollar hasarlı, kırmızı noktalı yollar kapalıdır. Hesaplanan rota mavi çerçeveyle gösterilir.</desc>',
             f'<rect width="960" height="{height}" fill="#f8fafc"/>',
             '<g font-family="Arial, sans-serif" fill="#17263c">',
             '<text x="48" y="48" font-size="26" font-weight="bold">AYROS MMY | Afet yol ağı</text>',
             f'<text x="48" y="80" font-size="18">{escape(scenario.name)}</text>',
             f'<text x="48" y="108" font-size="14">Yerel x/y koordinatları (km) • {route_label}</text>']
    for road in scenario.graph.roads.values():
        x1, y1 = points[road.source]
        x2, y2 = points[road.target]
        dash = {RoadStatus.OPEN: "", RoadStatus.DAMAGED: ' stroke-dasharray="12 5"', RoadStatus.CLOSED: ' stroke-dasharray="3 6"'}[road.status]
        if road.id in route_roads:
            parts.append(f'<path data-route-road="{escape(road.id)}" d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" stroke="#2563eb" stroke-width="10" fill="none"/>')
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colors[road.status]}" stroke-width="4"{dash}/>')
        x, y = (x1 + x2) / 2, (y1 + y2) / 2
        parts.append(f'<rect x="{x-19:.1f}" y="{y-10:.1f}" width="38" height="20" rx="4" fill="#f8fafc"/>')
        parts.append(f'<text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-size="12">{escape(road.id)}</text>')
    for node in nodes.values():
        x, y = points[node.id]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="22" fill="{fills[node.node_type]}"/>')
        parts.append(f'<text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-size="14" fill="white">{escape(node.id)}</text>')
    parts.extend(['<text x="48" y="570" font-size="15">Düğümler: Lacivert = Yardım merkezi | Gri = Kavşak | Bordo = Afet noktası</text>',
                  '<text x="48" y="602" font-size="15">Yollar: Yeşil düz = Açık | Turuncu kesikli = Hasarlı | Kırmızı noktalı = Kapalı</text>',
                  f'<text x="48" y="634" font-size="14">{len(nodes)} düğüm · {len(scenario.graph.roads)} çift yönlü yol · Yol etiketleri JSON kaydıyla eşleşir.</text>'])
    if route is not None:
        if route.found:
            parts.append(f'<text x="48" y="678" font-size="18" font-weight="bold">Rota: {escape(" → ".join(route.path))}</text>')
            parts.append(f'<text x="48" y="708" font-size="15">Maliyet / hasar dahil süre: {route.cost_min:.2f} dk | Mesafe: {route.distance_km:.2f} km | İncelenen düğüm: {route.settled_nodes}</text>')
        else:
            parts.append('<text x="48" y="678" font-size="18" font-weight="bold">Rota bulunamadı: Hedefe geçilebilir yollardan ulaşılamıyor.</text>')
    parts.append('</g></svg>')
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(parts) + "\n", encoding="utf-8")
