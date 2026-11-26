"""Senaryo özeti ve isteğe bağlı Dijkstra rotası: --start H0 --target A1."""

import argparse
import sys
from collections import Counter
from pathlib import Path

from .model import NodeType, RoadStatus, ValidationError
from .scenario import load_scenario
from .routing import CostModel, find_shortest_path
from .visualize import write_svg


def main() -> int:
    parser = argparse.ArgumentParser(description="AYROS MMY senaryo incelemesi ve Dijkstra rotası")
    parser.add_argument("scenario", nargs="?", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "hafta3_genis_ag.json")
    parser.add_argument("--svg", type=Path, help="Çizge görselinin kaydedileceği SVG dosyası")
    parser.add_argument("--start", help="Başlangıç düğüm kimliği")
    destinations = parser.add_mutually_exclusive_group()
    destinations.add_argument("--target", help="Hedef düğüm kimliği")
    destinations.add_argument("--all-targets", action="store_true",
                              help="Başlangıçtan tüm afet noktalarına ayrı ayrı rota özeti")
    parser.add_argument("--damage-factor", type=float, default=2.0,
                        help="Hasarlı yol süresi çarpanı (en az 1, varsayılan 2)")
    args = parser.parse_args()
    if (args.start is None) != (args.target is None and not args.all_targets):
        parser.error("--start ile --target veya --all-targets birlikte verilmelidir.")
    if args.all_targets and args.svg:
        parser.error("SVG için tek bir --target seçin; --all-targets terminal özeti üretir.")
    try:
        cost_model = CostModel(args.damage_factor)
        scenario = load_scenario(args.scenario)
        graph = scenario.graph
        counts = Counter(road.status for road in graph.roads.values())
        print(f"AYROS MMY | {scenario.name}")
        print(f"Düğüm: {len(graph.nodes)} | Yol: {len(graph.roads)}")
        print(f"Açık: {counts[RoadStatus.OPEN]} | Hasarlı: {counts[RoadStatus.DAMAGED]}"
              f" | Kapalı: {counts[RoadStatus.CLOSED]}")
        if not args.all_targets:
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
        if args.all_targets:
            # Her hedef bağımsız bir sorgudur; araç atama/ziyaret sırası değildir.
            graph.neighbors(args.start)  # Afet noktası olmasa bile kimliği doğrula.
            targets = sorted(n.id for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA)
            print(f"\n{args.start} -> tüm afet noktaları | Hasar katsayısı: {cost_model.damaged_factor:g}")
            reachable = 0
            for target in targets:
                result = find_shortest_path(graph, args.start, target, cost_model=cost_model)
                if result.found:
                    reachable += 1
                    print(f"  {target}: {result.cost_min:.2f} dk | {result.distance_km:.2f} km | "
                          + " -> ".join(result.path))
                else:
                    print(f"  {target}: Rota bulunamadı")
            print(f"Erişilebilir afet noktası: {reachable}/{len(targets)}")
            print("Hedefler bağımsız hesaplandı; araç atama veya öncelik sıralaması yapılmadı.")
        elif args.start is not None:
            route = find_shortest_path(graph, args.start, args.target, cost_model=cost_model)
            print(f"\nDijkstra | {args.start} -> {args.target} | Hasar katsayısı: {cost_model.damaged_factor:g}")
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
        return 3 if route is not None and not route.found else 0
    except (ValidationError, OSError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
