"""Dijkstra ve A* ile iki düğüm arasında en düşük süre maliyetli rota.

Kendi uygulamamızdır; heapq yalnızca öncelik kuyruğunu sağlar.
Bu modül arayüzden bağımsızdır ve çizge verisini değiştirmez.
"""

from dataclasses import dataclass
from heapq import heappop, heappush
from math import fsum, hypot, isfinite, nextafter
from time import perf_counter

from .model import Graph, Road, RoadStatus, ValidationError, require_number, require_text


@dataclass(frozen=True)
class CostModel:
    """Hasarlı yol süresini çarpar; katsayı deneysel bir varsayımdır."""

    damaged_factor: float = 2.0

    def __post_init__(self) -> None:
        require_number(self.damaged_factor, "Hasar katsayısı", positive=True)
        if self.damaged_factor < 1:
            raise ValidationError("Hasar katsayısı en az 1 olmalıdır.")

    def cost_minutes(self, road: Road) -> float | None:
        """Kapalı yol için None, diğer yollar için dakika cinsinden maliyet."""
        if road.status == RoadStatus.CLOSED:
            return None
        factor = self.damaged_factor if road.status == RoadStatus.DAMAGED else 1.0
        cost = road.travel_time_min * factor
        require_number(cost, f"{road.id} yol maliyeti", positive=True)
        return cost


@dataclass(frozen=True)
class RouteResult:
    found: bool
    path: tuple[str, ...]
    road_ids: tuple[str, ...]
    cost_min: float | None
    distance_km: float | None
    base_time_min: float | None
    settled_nodes: int
    elapsed_ms: float
    algorithm: str = "dijkstra"
    settled_order: tuple[str, ...] = ()


def _time_heuristic(graph: Graph, target: str, costs: dict[str, float | None]) -> dict[str, float]:
    """h(n)=alpha*Öklid(n,hedef), alpha=min(geçilebilir yol maliyeti/Öklid).

    alpha dk/km birimindedir. Her kenarda alpha*d(u,v)<=c(u,v) olduğu
    için üçgen eşitsizliği h(u)<=c(u,v)+h(v) verir. Dolayısıyla tahmin
    tutarlıdır ve kalan süreyi aşmaz. Eski, farklı hızdaki senaryolar da
    desteklenir. Koordinatlar sayısal sınırı aşarsa tüm tahminler sıfırdır.
    """
    zero = {node_id: 0.0 for node_id in graph.nodes}
    scale = float("inf")
    for road in graph.roads.values():
        cost = costs[road.id]
        if cost is None:
            continue
        a, b = graph.nodes[road.source], graph.nodes[road.target]
        direct = hypot(a.x_km - b.x_km, a.y_km - b.y_km)
        if not isfinite(direct):
            return zero
        if direct > 0:
            scale = min(scale, cost / direct)
    if not isfinite(scale) or scale <= 0:
        return zero
    scale = nextafter(scale, 0.0)  # Bölme yuvarlamasında alt sınır yönünde kal.
    goal = graph.nodes[target]
    estimates = {node_id: scale * hypot(node.x_km - goal.x_km, node.y_km - goal.y_km)
                 for node_id, node in graph.nodes.items()}
    return estimates if all(isfinite(h) for h in estimates.values()) else zero


def find_shortest_path(
    graph: Graph, start: str, target: str, *, cost_model: CostModel | None = None,
    algorithm: str = "dijkstra", record_search: bool = False
) -> RouteResult:
    """En düşük maliyetli rotayı ve ölçümleri döndürür.

    İncelenen düğüm: Kuyruktan alınıp maliyeti kesinleştirilen benzersiz
    düğüm sayısıdır; başlangıç ve erişildiyse hedef de sayılır.
    Hedef ilk keşfedildiğinde değil, kuyruktan alındığında arama sonlanır.
    record_search=True kesinleştirme sırasını kaydeder. Karşılaştırmalı
    süre deneylerinde kapalı tutulur; görsel için ayrı sorguda açılır.
    """
    if algorithm not in ("dijkstra", "astar"):
        raise ValidationError("Algoritma dijkstra veya astar olmalıdır.")
    for name, node_id in (("Başlangıç", start), ("Hedef", target)):
        require_text(node_id, name)
        if node_id not in graph.nodes:
            raise ValidationError(f"{name} düğümü bulunamadı: {node_id}")
    model = cost_model if cost_model is not None else CostModel()
    started = perf_counter()
    # Her yolun maliyetini bir kez doğrula ve hesapla.
    costs = {road.id: model.cost_minutes(road) for road in graph.roads.values()}
    heuristic = _time_heuristic(graph, target, costs) if algorithm == "astar" else dict.fromkeys(graph.nodes, 0.0)
    distances = {start: 0.0}
    previous: dict[str, tuple[str, str]] = {}
    settled: set[str] = set()
    settled_order: list[str] = []
    queue = [(heuristic[start], 0.0, start)]

    while queue:
        _, current_cost, current = heappop(queue)
        if current in settled:
            continue  # Daha pahalı eski kuyruk kayıtları yeniden incelenmez.
        settled.add(current)
        if record_search:
            settled_order.append(current)
        if current == target:
            break
        for neighbor, road in graph.neighbors(current):
            cost = costs[road.id]
            if cost is None or neighbor in settled:
                continue
            candidate = current_cost + cost
            require_number(candidate, "Toplam rota maliyeti")
            if candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                previous[neighbor] = (current, road.id)
                heappush(queue, (candidate + heuristic[neighbor], candidate, neighbor))

    if target not in settled:
        return RouteResult(False, (), (), None, None, None, len(settled),
                           (perf_counter() - started) * 1000, algorithm, tuple(settled_order))

    # Hedeften başlangıca ebeveynleri izleyerek yolu geri kur.
    path, road_ids = [target], []
    while path[-1] != start:
        parent, road_id = previous[path[-1]]
        path.append(parent)
        road_ids.append(road_id)
    path.reverse()
    road_ids.reverse()
    try:
        distance = fsum(graph.roads[r].distance_km for r in road_ids)
        base_time = fsum(graph.roads[r].travel_time_min for r in road_ids)
    except OverflowError as error:
        raise ValidationError("Rota toplamları desteklenen sayısal aralığı aşıyor.") from error
    require_number(distance, "Toplam mesafe")
    require_number(base_time, "Toplam temel süre")
    return RouteResult(True, tuple(path), tuple(road_ids), distances[target],
                       distance, base_time, len(settled), (perf_counter() - started) * 1000, algorithm, tuple(settled_order))
