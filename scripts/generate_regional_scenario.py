"""Sabit tohumla düzlemsel sokaklar ve üç köprü içeren 180 düğümlü ağ üretir.

En yakın bağlantılardan her yakada önce bir ağaç, sonra yerel çevrimler
kurulur. Düğümsüz yol kesişimi ve dereyi köprü dışında geçmek engellenir.
Veri sentetiktir; gerçek bir şehrin yol ağı değildir.
"""

import json
from math import ceil, hypot
from pathlib import Path
from random import Random

SEED = 20261026


def crosses(a, b, c, d):
    """Ortak uç taşımayan iki doğru parçasının iç kesişimi."""
    def turn(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    return turn(a, b, c)*turn(a, b, d) < 0 and turn(c, d, a)*turn(c, d, b) < 0


def build_scenario(seed=SEED):
    rng = Random(seed)
    positions = dict(H0=(1.0, 8.0), H1=(24.0, 2.0), H2=(23.0, 15.0))
    for i, xy in enumerate(((2, 14), (6, 12), (10, 15), (4, 7), (9, 4), (5, 2),
                            (16, 14), (21, 11), (24, 8), (17, 6), (20, 2), (0.4, 0.4)), 1):
        positions[f'A{i:02}'] = xy
    for i, xy in enumerate(((12, 3), (14, 3), (12, 8), (14, 8), (12, 13), (14, 13)), 1):
        positions[f'K{i:03}'] = xy
    for i in range(7, 166):
        left, right = (0.7, 11.5) if i % 2 else (14.5, 25.3)
        for _ in range(10000):
            xy = (round(rng.uniform(left, right), 3), round(rng.uniform(0.8, 15.5), 3))
            if all(hypot(xy[0]-p[0], xy[1]-p[1]) >= 0.7 for p in positions.values()):
                positions[f'K{i:03}'] = xy
                break
        else:
            raise ValueError('Düğüm yerleşimi için yeterli alan bulunamadı.')

    edges = []
    degrees = dict.fromkeys(positions, 0)
    parent = {n: n for n in positions}

    def root(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def clear(a, b):
        return not any(crosses(positions[a], positions[b], positions[c], positions[d])
                       for c, d, _ in edges if not {a, b} & {c, d})

    def add(a, b, kind):
        edges.append((a, b, kind))
        degrees[a] += 1
        degrees[b] += 1

    candidates = sorted((hypot(p[0]-q[0], p[1]-q[1]), a, b)
                        for a, p in positions.items() for b, q in positions.items()
                        if a < b and 'A12' not in (a, b) and (p[0] < 13) == (q[0] < 13))
    # Her yakanın açık omurgası; kapalı yan yollar omurgayı bozmaz.
    for _, a, b in candidates:
        if root(a) != root(b) and clear(a, b):
            parent[root(a)] = root(b)
            add(a, b, 'secondary')
    backbone = {frozenset((a, b)) for a, b, _ in edges}
    for a, b in (('K001', 'K002'), ('K003', 'K004'), ('K005', 'K006')):
        assert clear(a, b)
        add(a, b, 'bridge')
    # Kontrollü erişilemez bölge: iki bağlantısı da kapalı; transit düğüm değil.
    for _, b in sorted((hypot(p[0]-0.4, p[1]-0.4), n) for n, p in positions.items()
                       if n != 'A12' and p[0] < 13):
        if clear('A12', b):
            add('A12', b, 'local')
            if degrees['A12'] == 2:
                break
    used = {frozenset((a, b)) for a, b, _ in edges}
    for length, a, b in candidates:
        if length <= 3.5 and degrees[a] < 4 and degrees[b] < 4 and frozenset((a, b)) not in used and clear(a, b):
            add(a, b, 'local')
            used.add(frozenset((a, b)))

    nodes = []
    for n, (x, y) in positions.items():
        kind = 'aid_center' if n.startswith('H') else 'disaster_area' if n.startswith('A') else 'intersection'
        node = dict(id=n, name=n, node_type=kind, x_km=x, y_km=y)
        if kind == 'disaster_area':
            i = int(n[1:])
            node.update(affected_count=45+17*i, injured_count=6+(i*7)%42, urgency_level=1+(i*3)%5)
        nodes.append(node)
    roads = []
    speeds = dict(main=40, secondary=30, local=20, bridge=25)
    for i, (a, b, kind) in enumerate(edges, 1):
        distance = ceil(hypot(positions[a][0]-positions[b][0], positions[a][1]-positions[b][1])*100)/100
        if kind == 'secondary' and i % 4 == 0:
            kind = 'main'
        pair = frozenset((a, b))
        status = 'closed' if 'A12' in pair or (pair not in backbone and kind != 'bridge' and i % 13 == 0) else 'damaged' if i % 7 == 0 else 'open'
        roads.append(dict(id=f'R{i:03}', source=a, target=b, distance_km=distance,
                          travel_time_min=round(distance/speeds[kind]*60, 3), status=status, road_type=kind))
    return dict(schema_version=1, name='Bölgesel afet ağı',
                description=f'Sabit tohum {seed}; 180 düğüm, 3 merkez, 12 afet noktası, 165 kavşak. Düzlemsel düzensiz sokaklar ve 3 köprü. A12 iki kapalı girişle yalıtılmıştır. Sentetik yerel koordinatlar; saha verisi değildir. Hızlar ana/ikincil/yerel/köprü için 40/30/20/25 km/saat.',
                directed=False, coordinate_system='cartesian_km', nodes=nodes, roads=roads,
                river=[[13, -0.4], [13, 16.3]])


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1]/'data/bolgesel_ag.json'
    target.write_text(json.dumps(build_scenario(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(target)
