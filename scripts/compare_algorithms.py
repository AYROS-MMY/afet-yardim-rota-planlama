"""İki merkez, altı hedef ve iki katsayıyla tekrar edilebilir ölçüm çıktısı üretir."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from hashlib import sha256
from pathlib import Path
import platform
import sys

# Doğrudan `python scripts/compare_algorithms.py` çağrısını destekle.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ayros.benchmark import compare_algorithms
from ayros.model import NodeType, ValidationError
from ayros.routing import CostModel
from ayros.scenario import load_scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("output/algorithm_comparison.json"))
    args = parser.parse_args()
    if not 1 <= args.repeats <= 1000:
        parser.error("Tekrar sayısı 1 ile 1000 arasında olmalıdır.")
    try:
        scenario_path = ROOT / "data/hafta3_genis_ag.json"
        graph = load_scenario(scenario_path).graph
        centers = sorted(n.id for n in graph.nodes.values() if n.node_type == NodeType.AID_CENTER)
        targets = sorted(n.id for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA)
        rows = []
        for factor in (1, 2):
            for start in centers:
                for target in targets:
                    result = compare_algorithms(graph, start, target, cost_model=CostModel(factor), repeats=args.repeats)
                    row = dict(start=start, target=target, damage_factor=factor,
                               repeats=result.repeats, warmups=result.warmups)
                    for key in ("dijkstra", "astar"):
                        measurement = getattr(result, key)
                        row[key] = dict(route=asdict(measurement.route),
                                        median_ms=measurement.median_ms, samples_ms=measurement.samples_ms)
                    rows.append(row)
        payload = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
                       platform=platform.platform(), scenario="data/hafta3_genis_ag.json",
                       scenario_sha256=sha256(scenario_path.read_bytes()).hexdigest(),
                       timing_scope="Cost preparation, heuristic preparation, search and route reconstruction; excludes JSON/SVG/printing.",
                       results=rows)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(rows)} sorgu; her algoritma için {args.repeats} ölçüm ve 2 ısınma. Çıktı: {args.output}")
        return 0
    except (OSError, ValidationError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
