"""Kullanım: python -m ayros [senaryo.json] [--svg cikti.svg]"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from .model import NodeType, RoadStatus, ValidationError
from .scenario import load_scenario
from .visualize import write_svg


def main() -> int:
    parser = argparse.ArgumentParser(description="AYROS MMY ikinci hafta senaryo incelemesi")
    parser.add_argument("scenario", nargs="?", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "hafta2_senaryo.json")
    parser.add_argument("--svg", type=Path, help="Çizge görselinin kaydedileceği SVG dosyası")
    args = parser.parse_args()
    try:
        scenario = load_scenario(args.scenario)
        graph = scenario.graph
        counts = Counter(road.status for road in graph.roads.values())
        print(f"AYROS MMY | {scenario.name}")
        print(f"Düğüm: {len(graph.nodes)} | Yol: {len(graph.roads)}")
        print(f"Açık: {counts[RoadStatus.OPEN]} | Hasarlı: {counts[RoadStatus.DAMAGED]}"
              f" | Kapalı: {counts[RoadStatus.CLOSED]}")
        print("\nGeçilebilir komşular (kapalı yollar hariç):")
        for node in graph.nodes.values():
            neighbors = ", ".join(f"{other} ({road.id})" for other, road in graph.neighbors(node.id))
            print(f"  {node.id}: {neighbors or 'yok'}")
        print("\nAfet noktaları (henüz öncelik puanı hesaplanmıyor):")
        for node in graph.nodes.values():
            if node.node_type == NodeType.DISASTER_AREA:
                print(f"  {node.id}: {node.affected_count} afetzede, "
                      f"{node.injured_count} yaralı, aciliyet {node.urgency_level}/5")
        if args.svg:
            write_svg(scenario, args.svg)
            print(f"\nÇizge görseli: {args.svg}")
        print("\nBu sürüm veri modelini gösterir; rota ve araç atama hesabı içermez.")
        return 0
    except (ValidationError, OSError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
