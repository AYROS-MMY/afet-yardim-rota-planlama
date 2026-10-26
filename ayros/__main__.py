"""Senaryo, Dijkstra/A* rotası ve tekrarlı karşılaştırma komutları."""

import argparse
import sys
from collections import Counter
from pathlib import Path

from .model import NodeType, RoadStatus, ValidationError
from .scenario import load_scenario
from .routing import CostModel, find_shortest_path
from .visualize import write_svg
from .search_visualize import write_search_svg
from .benchmark import ComparisonResult, compare_algorithms


def print_comparison(target: str, result: ComparisonResult) -> None:
    found = result.dijkstra.route.found
    print(f"\n{target}: " + (f"Ortak en düşük maliyet: {result.dijkstra.route.cost_min:.2f} dk" if found else "Rota bulunamadı"))
    for name, measurement in (("Dijkstra", result.dijkstra), ("A*", result.astar)):
        route = measurement.route
        print(f"  {name}: {route.settled_nodes} düğüm | Medyan: {measurement.median_ms:.4f} ms")
        if route.found:
            print("    " + " -> ".join(route.path))


def main() -> int:
    parser = argparse.ArgumentParser(description="AYROS MMY senaryosu, Dijkstra/A* ve karşılaştırma")
    parser.add_argument("scenario", nargs="?", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "hafta3_genis_ag.json")
    parser.add_argument("--svg", type=Path, help="Çizge görselinin kaydedileceği SVG dosyası")
    parser.add_argument("--search-svg", type=Path, help="--compare ile tek hedefin yan yana arama görseli")
    parser.add_argument("--start", help="Başlangıç düğüm kimliği")
    destinations = parser.add_mutually_exclusive_group()
    destinations.add_argument("--target", help="Hedef düğüm kimliği")
    destinations.add_argument("--all-targets", action="store_true",
                              help="Başlangıçtan tüm afet noktalarına ayrı ayrı rota özeti")
    parser.add_argument("--damage-factor", type=float, default=2.0,
                        help="Hasarlı yol süresi çarpanı (en az 1, varsayılan 2)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--algorithm", choices=("dijkstra", "astar"), default="dijkstra",
                      help="Rota algoritması (varsayılan dijkstra)")
    mode.add_argument("--compare", action="store_true", help="Dijkstra ve A* için tekrarlı karşılaştırma")
    parser.add_argument("--repeats", type=int, help="Karşılaştırmada 1-1000 tekrar (varsayılan 30)")
    args = parser.parse_args()
    if args.search_svg and (not args.compare or args.target is None):
        parser.error("--search-svg için --compare ve tek bir --target gerekir.")
    if (args.start is None) != (args.target is None and not args.all_targets):
        parser.error("--start ile --target veya --all-targets birlikte verilmelidir.")
    if args.all_targets and args.svg:
        parser.error("SVG için tek bir --target seçin; --all-targets terminal özeti üretir.")
    if args.compare and (args.start is None or args.svg):
        parser.error("Karşılaştırma için başlangıç ve hedef gerekir; SVG için tek bir algoritma seçin.")
    if args.repeats is not None and (not args.compare or not 1 <= args.repeats <= 1000):
        parser.error("--repeats yalnızca --compare ile ve 1-1000 aralığında kullanılır.")
    if args.algorithm == "astar" and args.start is None:
        parser.error("A* için başlangıç ve hedef birlikte verilmelidir.")
    try:
        cost_model = CostModel(args.damage_factor)
        scenario = load_scenario(args.scenario)
        graph = scenario.graph
        counts = Counter(road.status for road in graph.roads.values())
        print(f"AYROS MMY | {scenario.name}")
        print(f"Düğüm: {len(graph.nodes)} | Yol: {len(graph.roads)}")
        print(f"Açık: {counts[RoadStatus.OPEN]} | Hasarlı: {counts[RoadStatus.DAMAGED]}"
              f" | Kapalı: {counts[RoadStatus.CLOSED]}")
        if not args.all_targets and not args.compare:
            print("\nGeçilebilir komşular (kapalı yollar hariç):")
            for node in graph.nodes.values():
                neighbors = ", ".join(f"{other} ({road.id})" for other, road in graph.neighbors(node.id))
                print(f"  {node.id}: {neighbors or 'yok'}")
        print("\nAfet noktaları (henüz öncelik puanı hesaplanmıyor):")
        for node in graph.nodes.values():
            if node.node_type == NodeType.DISASTER_AREA:
                print(f"  {node.id}: {node.affected_count} afetzede, "
                      f"{node.injured_count} yaralı, aciliyet {node.urgency_level}/5")
        route = None
        if args.compare:
            graph.neighbors(args.start)
            targets = sorted(n.id for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA) if args.all_targets else [args.target]
            print(f"\nDijkstra / A* karşılaştırması | Hasar katsayısı: {cost_model.damaged_factor:g}")
            print(f"{args.repeats or 30} ölçüm/algoritma, 2 ısınma, dönüşümlü sıra; hazırlık dahil medyan süre.")
            reachable = 0
            for target in targets:
                comparison = compare_algorithms(graph, args.start, target, cost_model=cost_model,
                                                repeats=args.repeats or 30)
                print_comparison(target, comparison)
                route = comparison.dijkstra.route
                reachable += route.found
            if args.all_targets:
                print(f"Erişilebilir afet noktası: {reachable}/{len(targets)}")
            print("Süreler bu bilgisayardaki deneydir; daha az düğüm daha kısa toplam süreyi garanti etmez.")
            if args.search_svg:
                traced = {name: find_shortest_path(graph, args.start, args.target, cost_model=cost_model,
                                                   algorithm=name, record_search=True)
                          for name in ("dijkstra", "astar")}
                write_search_svg(scenario, args.search_svg, start=args.start, target=args.target, cost_model=cost_model, **traced)
                print(f"Arama karşılaştırma görseli: {args.search_svg}")
        elif args.all_targets:
            # Her hedef bağımsız bir sorgudur; araç atama/ziyaret sırası değildir.
            graph.neighbors(args.start)  # Afet noktası olmasa bile kimliği doğrula.
            targets = sorted(n.id for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA)
            print(f"\n{args.start} -> tüm afet noktaları | Hasar katsayısı: {cost_model.damaged_factor:g}")
            reachable = 0
            for target in targets:
                result = find_shortest_path(graph, args.start, target, cost_model=cost_model, algorithm=args.algorithm)
                if result.found:
                    reachable += 1
                    print(f"  {target}: {result.cost_min:.2f} dk | {result.distance_km:.2f} km | "
                          + " -> ".join(result.path))
                else:
                    print(f"  {target}: Rota bulunamadı")
            print(f"Erişilebilir afet noktası: {reachable}/{len(targets)}")
            print("Hedefler bağımsız hesaplandı; araç atama veya öncelik sıralaması yapılmadı.")
        elif args.start is not None:
            route = find_shortest_path(graph, args.start, args.target, cost_model=cost_model, algorithm=args.algorithm)
            name = "A*" if args.algorithm == "astar" else "Dijkstra"
            print(f"\n{name} | {args.start} -> {args.target} | Hasar katsayısı: {cost_model.damaged_factor:g}")
            if route.found:
                print("Rota: " + " -> ".join(route.path))
                print("Yollar: " + (", ".join(route.road_ids) or "yol geçişi yok"))
                print(f"Maliyet / hasar dahil tahmini süre: {route.cost_min:.2f} dk")
                print(f"Temel süre (hasar etkisi hariç): {route.base_time_min:.2f} dk")
                print(f"Toplam mesafe: {route.distance_km:.2f} km")
            else:
                print("Rota bulunamadı: hedefe geçilebilir yollardan ulaşılamıyor.")
            print(f"İncelenen düğüm: {route.settled_nodes}")
            print(f"Hesaplama süresi: {route.elapsed_ms:.3f} ms (tek çalıştırma)")
        if args.svg:
            write_svg(scenario, args.svg, route=route, cost_model=cost_model)
            print(f"\nÇizge görseli: {args.svg}")
        if route is None and not args.all_targets:
            print("\nRota için --start ve --target kullanın. Araç atama henüz yoktur.")
        return 3 if route is not None and not route.found and not args.all_targets else 0
    except (ValidationError, OSError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
