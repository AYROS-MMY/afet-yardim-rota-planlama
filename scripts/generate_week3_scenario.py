"""Düzensiz mahalleler, iki köprü ve çıkmazlarla sentetik yol ağı üretir."""

import json
from math import ceil, hypot
from pathlib import Path


def build_scenario():
    # Düğümler ızgaradan türetilmez; mahalle ve koridorlara göre yerleştirilir.
    west = [(1.2, 7.7), (2.6, 8.3), (4.1, 7.8), (5.5, 8.4),
            (0.9, 5.6), (2.2, 6.4), (3.6, 5.9), (5.4, 6.8),
            (1.6, 3.7), (3.2, 4.4), (5.3, 4.8), (0.9, 1.8),
            (2.5, 2.4), (4.4, 2.1), (5.7, 2.8), (3.7, 0.8)]
    east = [(7.4, 8.2), (9.2, 8.8), (11.0, 8.2), (12.6, 7.1),
            (7.6, 6.5), (9.0, 7.0), (10.2, 6.2), (11.8, 5.8),
            (7.3, 4.9), (8.8, 4.4), (10.5, 4.5), (12.4, 3.4),
            (7.6, 2.5), (9.3, 2.0), (11.1, 2.6), (10.1, 0.7)]
    positions = {f"K{i:02}": point for i, point in enumerate(west + east, 1)}
    positions.update(H0=(0.25, 4.6), H1=(8.0, 0.9), A1=(3.2, 9.3),
                     A2=(4.7, 6.3), A3=(13.3, 5.4), A4=(10.5, 9.4),
                     A5=(12.6, 1.0), A6=(0.45, 0.6))
    needs = {"A1": (120, 25, 5), "A2": (80, 12, 3), "A3": (160, 32, 5),
             "A4": (60, 8, 2), "A5": (95, 15, 4), "A6": (45, 10, 4)}
    nodes = []
    for node_id, (x, y) in positions.items():
        kind = "aid_center" if node_id.startswith("H") else "disaster_area" if node_id.startswith("A") else "intersection"
        name = {"aid_center": "Yardım merkezi", "disaster_area": "Afet noktası", "intersection": "Kavşak"}[kind]
        node = dict(id=node_id, name=f"{name} {node_id}", node_type=kind, x_km=x, y_km=y)
        if node_id in needs:
            node.update(zip(("affected_count", "injured_count", "urgency_level"), needs[node_id]))
        nodes.append(node)
    groups = {
        "main": "H0-K05 K05-K06 K06-K02 K02-K03 K03-K04 H0-K09 K09-K10 K10-K11 "
                "K17-K18 K18-K19 K19-K20 K25-K26 K26-K27 K27-K28 K28-A3",
        "bridge": "K04-K17 K11-K25",
        "secondary": "K05-K01 K01-K02 K06-K07 K07-K03 K03-K08 K08-K04 K07-K10 K11-K08 "
                     "K09-K12 K12-K13 K13-K10 K13-K14 K14-K15 K15-K11 K10-K14 "
                     "K17-K21 K21-K22 K22-K18 K22-K23 K23-K19 K23-K24 K24-K20 K21-K25 "
                     "K26-K23 K27-K24 K25-K29 K29-K30 K30-K26 K30-K31 K31-K27 K31-K28 K30-H1",
        "local": "K02-A1 A1-K03 K07-A2 A2-K08 A2-K11 K14-K16 K12-A6 K13-A6 "
                 "K18-A4 A4-K19 K24-A3 K20-A3 K29-H1 K30-K32 K31-A5 K28-A5",
    }
    closed = {frozenset(s.split("-")) for s in "K12-A6 K13-A6 K03-K08 K21-K22 K27-K28".split()}
    damaged = {frozenset(s.split("-")) for s in "K04-K17 K10-K11 K06-K07 K07-A2 K13-K14 K18-K19 K23-K24 K26-K27 K31-A5".split()}
    speeds = {"main": 40, "secondary": 30, "local": 20, "bridge": 25}
    roads = []
    for road_type, connections in groups.items():
        for connection in connections.split():
            source, target = connection.split("-")
            a, b = positions[source], positions[target]
            dx, dy = b[0]-a[0], b[1]-a[1]
            direct = hypot(dx, dy)
            # Ara noktalar kavşak değildir; aynı yolun kırımlarıdır.
            bend = 0 if road_type == "bridge" else (0.10 if len(roads) % 2 else -0.13)
            if connection == "K13-A6":
                bend = 0.20  # K12-K13 yolunun altından yaklaşır; düğümsüz kesişmez.
            via = [[round(a[0] + dx*t - dy/direct*bend, 3),
                    round(a[1] + dy*t + dx/direct*bend, 3)] for t in (0.32, 0.68)]
            geometry = [a, *via, b]
            length = sum(hypot(q[0]-p[0], q[1]-p[1]) for p, q in zip(geometry, geometry[1:]))
            distance = ceil(length * 100) / 100
            status = "closed" if frozenset((source, target)) in closed else "damaged" if frozenset((source, target)) in damaged else "open"
            roads.append(dict(id=f"R{len(roads)+1:02}", source=source, target=target,
                              distance_km=distance, travel_time_min=round(distance / speeds[road_type] * 60, 2),
                              status=status, road_type=road_type, via=via))
    return dict(schema_version=1, name="Üçüncü hafta düzensiz yerleşim ağı",
                description="İki yaka, iki köprü, düzensiz mahalle halkaları ve çıkmaz sokaklar içeren sentetik ağ. Yol mesafeleri çizilen kırımlı geometri üzerinden hesaplanır; ana yol 40, ikincil yol 30, sokak 20, köprü 25 km/saat varsayılır. A6'nın iki girişi kapalıdır. Gerçek şehir veya saha verisi değildir.",
                directed=False, coordinate_system="cartesian_km", nodes=nodes, roads=roads,
                river=[[6.4, -0.4], [6.2, 2.2], [6.5, 4.4], [6.3, 6.5], [6.6, 8.4], [6.4, 10.0]])


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "data" / "hafta3_genis_ag.json"
    target.write_text(json.dumps(build_scenario(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)
