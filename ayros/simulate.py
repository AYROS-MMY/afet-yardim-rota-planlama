"""python -m ayros.simulate ile düğüm adımlı simülasyon."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from .assignment import load_dispatch
from .model import RoadStatus, ValidationError
from .routing import CostModel
from .scenario import load_scenario
from .simulation import Simulation
from .console import safe_console


STATUS_LABELS = {
    "idle": "Görevsiz", "unavailable": "Müsait değil", "ready": "Düğümde / ilerlemeye hazır",
    "en_route": "Yolda", "arrived": "Hedefe ulaştı", "blocked": "Rota yok / bekliyor",
}


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Yinelenen olay alanı: {key}")
        result[key] = value
    return result


def _content_hash(path):
    """Satır sonundan bağımsız SHA-256: Windows (CRLF) ve Linux (LF) kopyası aynı değeri verir."""
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_events(path, graph):
    """after_step bir varış adımıdır, dakika değildir. 0 başlangıçtır."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_keys)
    if not isinstance(data, dict) or set(data) != {"schema_version", "events"}:
        raise ValidationError("Olay dosyası schema_version ve events içermelidir.")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValidationError("Olay şeması 1 olmalıdır.")
    if not isinstance(data["events"], list):
        raise ValidationError("events liste olmalıdır.")
    events = {}
    for event in data["events"]:
        if not isinstance(event, dict) or set(event) != {"after_step", "changes"}:
            raise ValidationError("Olay after_step ve changes içermelidir.")
        step, changes = event["after_step"], event["changes"]
        if type(step) is not int or step < 0 or step in events:
            raise ValidationError("Olay adımı benzersiz, negatif olmayan tam sayı olmalıdır.")
        if not isinstance(changes, dict) or not changes:
            raise ValidationError("changes boş olmayan yol/durum nesnesi olmalıdır.")
        for road, status in changes.items():
            if road not in graph.roads or status not in [item.value for item in RoadStatus]:
                raise ValidationError(f"Geçersiz yol/durum: {road}")
        events[step] = changes
    return events


def main(argv=None):
    safe_console()
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="AYROS | Düğüm adımlı araç simülasyonu")
    parser.add_argument("--scenario", type=Path, default=root / "data/bolgesel_ag.json")
    parser.add_argument("--fleet", type=Path, default=root / "data/gorev_senaryosu_12_arac.json")
    parser.add_argument("--events", type=Path, help="Düğüm adımlarına bağlı yol olayları")
    parser.add_argument("--algorithm", choices=("astar", "dijkstra"), default="astar")
    parser.add_argument("--damage-factor", type=float, default=2)
    parser.add_argument("--steps", type=int, help="Belirtilen varış adımında dur")
    parser.add_argument("--json", type=Path, help="Durum, olay günlüğü ve kontrol noktaları")
    args = parser.parse_args(argv)
    if args.steps is not None and args.steps < 0:
        parser.error("Adım sayısı negatif olamaz.")
    roles = [("scenario", args.scenario), ("fleet", args.fleet)] + ([("events", args.events)] if args.events else [])
    inputs = [path for _, path in roles]
    if args.json and args.json.resolve() in {path.resolve() for path in inputs}:
        parser.error("Çıktı dosyası girdilerden farklı olmalıdır.")
    try:
        scenario = load_scenario(args.scenario)
        fleet = load_dispatch(args.fleet, scenario.graph)
        events = load_events(args.events, scenario.graph) if args.events else {}
        simulation = Simulation(scenario.graph, fleet, algorithm=args.algorithm,
                                cost_model=CostModel(args.damage_factor))
        checkpoints = [{"label": "initial", "state": simulation.snapshot()}]
        limit = args.steps if args.steps is not None else 10000
        while True:
            state = simulation.snapshot()
            if state["step"] in events:
                checkpoints.append({"label": "before_event", "state": state})
                state = simulation.change_roads(events.pop(state["step"]))
                checkpoints.append({"label": "after_event", "state": state})
            if state["step"] >= limit or not state["can_advance"]:
                break
            simulation.step()
        if args.steps is None:
            if state["can_advance"]:
                raise ValidationError("10000 adım sınırı aşıldı; senaryoyu kontrol edin.")
            if events:
                raise ValidationError("Bekleyen yol olayının adımına ulaşılamıyor.")
        checkpoints.append({"label": "final", "state": state})
        print(f'AYROS | 7. hafta | {state["step"]} varış adımı | {state["time_min"]:.3f} dakika')
        for event in state['events']:
            if event['kind'] == 'roads_changed':
                changes = ', '.join(f'{key}={value}' for key, value in event['changes'].items())
                print(f'{event["time_min"]:.3f} dk | Yol olayı: {changes}')
            elif event['kind'] in ('route_changed', 'route_blocked'):
                route = ' -> '.join(event['new_path']) or 'Alternatif rota yok; araç bekliyor'
                print(f'{event["time_min"]:.3f} dk | {event["vehicle_id"]}: {route}')
        for vehicle in state["vehicles"]:
            location = vehicle["node"]
            if vehicle["edge_id"]:
                location += f' -> {vehicle["next_node"]} ({vehicle["edge_id"]})'
            arrival = f' | Varış {vehicle["arrival_at"]:.3f} dk' if vehicle['arrival_at'] is not None else ''
            print(f'{vehicle["id"]}: {STATUS_LABELS[vehicle["status"]]} | '
                  f'Başlangıç {vehicle["origin"]} | Konum {location} | görev {vehicle["task_id"] or "-"}{arrival}')
        totals = state["logistics"]
        print(f'İhtiyaç {totals["requested"]} | Teslim {totals["delivered"]} | '
              f'Araçlara ayrılmış {totals["reserved"]} | Atanmamış {totals["unassigned"]} koli')
        print('Sağlık ve kurtarma sonucu ekibin hedefe ulaşması olarak kaydedilir.')
        if args.json:
            payload = {"schema_version": 1, "algorithm": args.algorithm,
                       "damage_factor": args.damage_factor,
                       # Anahtar dosya adı değil girdinin rolüdür: farklı klasörlerde aynı adlı
                       # dosyalar kullanılsa da hiçbir girdinin özeti kaybolmaz.
                       "input_sha256": {role: {"file": path.name, "sha256": _content_hash(path)}
                                        for role, path in roles},
                       "checkpoints": checkpoints, "final": state}
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            print(f'JSON: {args.json}')
        return 0
    except (ValidationError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
