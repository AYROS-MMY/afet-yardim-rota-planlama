"""30 düğümlü sentetik hafta 3 ağını tekrarlanabilir biçimde üretir."""

import json
from math import hypot
from pathlib import Path


def build_scenario():
    # Altı sütun, beş satır; komşu kavşaklar arası düzlem uzaklığı 2 km.
    special = {(0, 2): "H0", (0, 4): "H1", (5, 4): "A1", (4, 3): "A2",
               (5, 2): "A3", (4, 1): "A4", (5, 0): "A5", (2, 0): "A6"}
    needs = {"A1": (120, 25, 5), "A2": (80, 12, 3), "A3": (160, 32, 5),
             "A4": (60, 8, 2), "A5": (95, 15, 4), "A6": (45, 10, 4)}
    nodes, positions = [], {}
    junction = 0
    for y in range(5):
        for x in range(6):
            node_id = special.get((x, y))
            if node_id is None:
                junction += 1
                node_id = f"K{junction:02}"
            positions[(x, y)] = node_id
            kind = "aid_center" if node_id.startswith("H") else "disaster_area" if node_id.startswith("A") else "intersection"
            name = {"aid_center": "Yardım merkezi", "disaster_area": "Afet noktası", "intersection": "Kavşak"}[kind]
            node = dict(id=node_id, name=f"{name} {node_id}", node_type=kind, x_km=x * 2, y_km=y * 2)
            if node_id in needs:
                node.update(zip(("affected_count", "injured_count", "urgency_level"), needs[node_id]))
            nodes.append(node)

    pairs = []
    for y in range(5):
        for x in range(5):
            pairs.append(((x, y), (x + 1, y)))
    for y in range(4):
        for x in range(6):
            pairs.append(((x, y), (x, y + 1)))
    pairs += [((0, 1), (1, 2)), ((1, 3), (2, 4)), ((2, 2), (3, 3)),
              ((3, 0), (4, 1)), ((3, 2), (4, 3)), ((4, 3), (5, 4))]

    # A6'nın üç bağlantısı kapalıdır; diğer kapanmalar alternatif yol gerektirir.
    closed = {frozenset(p) for p in [((1, 0), (2, 0)), ((2, 0), (3, 0)),
              ((2, 0), (2, 1)), ((2, 2), (3, 2)), ((4, 2), (5, 2)), ((3, 3), (3, 4))]}
    damaged = {frozenset(p) for p in [((1, 2), (2, 2)), ((3, 3), (4, 3)),
               ((4, 3), (5, 3)), ((1, 4), (2, 4)), ((3, 4), (4, 4)),
               ((4, 0), (5, 0)), ((4, 1), (4, 2)), ((5, 1), (5, 2)),
               ((2, 2), (3, 3)), ((4, 3), (5, 4))]}
    roads = []
    for i, (a, b) in enumerate(pairs, 1):
        # Yol uzunluğu düzlem uzaklığının %10 fazlası, hız 24/30/36 km/saat.
        distance = round(hypot(b[0] - a[0], b[1] - a[1]) * 2 * 1.1, 2)
        speed = (24, 30, 36)[(i - 1) % 3]
        status = "closed" if frozenset((a, b)) in closed else "damaged" if frozenset((a, b)) in damaged else "open"
        roads.append(dict(id=f"R{i:02}", source=positions[a], target=positions[b],
                          distance_km=distance, travel_time_min=round(distance / speed * 60, 2), status=status))
    return dict(schema_version=1, name="Üçüncü hafta geniş afet ağı",
                description="Sentetik 6x5 yerleşim: 2 yardım merkezi, 6 afet noktası, 22 kavşak; 49 yatay/dikey ve 6 çapraz yol. Mesafeler düzlem uzaklığının yaklaşık 1,1 katı; temel süreler 24/30/36 km/saat varsayımlarıyla üretilir. A6 girişleri kapalıdır. Gerçek saha verisi değildir.",
                directed=False, coordinate_system="cartesian_km", nodes=nodes, roads=roads)


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "data" / "hafta3_genis_ag.json"
    target.write_text(json.dumps(build_scenario(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)
