"""Aynı sorguyu dönüşümlü çalıştırarak Dijkstra ve A* ölçümlerini karşılaştırır."""

from dataclasses import dataclass
from math import isclose
from statistics import median

from .model import Graph, ValidationError
from .routing import CostModel, RouteResult, find_shortest_path


@dataclass(frozen=True)
class BenchmarkResult:
    route: RouteResult
    samples_ms: tuple[float, ...]

    @property
    def median_ms(self) -> float:
        return median(self.samples_ms)


@dataclass(frozen=True)
class ComparisonResult:
    dijkstra: BenchmarkResult
    astar: BenchmarkResult
    repeats: int
    warmups: int


def compare_algorithms(graph: Graph, start: str, target: str, *,
                       cost_model: CostModel | None = None, repeats: int = 30,
                       warmups: int = 2) -> ComparisonResult:
    """Ölçüm rota API'sinin iç zamanını kullanır; A* hazırlığı da dahildir.

    Isınma ölçümleri örneklere alınmaz. Sıra her turda değiştirilir.
    Süre üstünlüğü veya hızlanma eşiği dayatılmaz; küçük ağda gürültü olabilir.
    """
    if type(repeats) is not int or not 1 <= repeats <= 1000:
        raise ValidationError("Tekrar sayısı 1 ile 1000 arasında tam sayı olmalıdır.")
    if type(warmups) is not int or not 0 <= warmups <= 100:
        raise ValidationError("Isınma sayısı 0 ile 100 arasında tam sayı olmalıdır.")
    samples = {"dijkstra": [], "astar": []}
    routes = {}
    for iteration in range(warmups + repeats):
        order = ("dijkstra", "astar") if iteration % 2 == 0 else ("astar", "dijkstra")
        for algorithm in order:
            route = find_shortest_path(graph, start, target, cost_model=cost_model, algorithm=algorithm)
            if iteration >= warmups:
                routes[algorithm] = route
                samples[algorithm].append(route.elapsed_ms)
    a, b = routes["dijkstra"], routes["astar"]
    if a.found != b.found or (a.found and not isclose(a.cost_min, b.cost_min, rel_tol=1e-12, abs_tol=1e-9)):
        raise ValidationError("Algoritmaların erişim veya maliyet sonuçları uyuşmuyor.")
    return ComparisonResult(BenchmarkResult(a, tuple(samples["dijkstra"])),
                            BenchmarkResult(b, tuple(samples["astar"])), repeats, warmups)
