"""JSON dosyasından doğrulanmış bir afet senaryosu yükler."""

import json
from dataclasses import dataclass
from pathlib import Path

from .model import Graph, Node, NodeType, Road, RoadStatus, ValidationError, require_text


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    graph: Graph


def load_scenario(path: str | Path) -> Scenario:
    try:
        with Path(path).open(encoding="utf-8-sig") as source:
            data = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"Senaryo dosyası okunamadı: {error}") from error
    return scenario_from_dict(data)


def scenario_from_dict(data: dict) -> Scenario:
    if not isinstance(data, dict):
        raise ValidationError("Senaryo bir JSON nesnesi olmalıdır.")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValidationError("Desteklenen schema_version değeri 1'dir.")
    if data.get("directed") is not False:
        raise ValidationError("İlk sürüm yalnızca yönsüz (directed: false) yolları destekler.")
    if data.get("coordinate_system") != "cartesian_km":
        raise ValidationError("Koordinat sistemi cartesian_km olmalıdır.")
    require_text(data.get("name"), "Senaryo adı")
    require_text(data.get("description"), "Senaryo açıklaması")
    for field in ("nodes", "roads"):
        if not isinstance(data.get(field), list):
            raise ValidationError(f"{field}: bir liste olmalıdır.")
    nodes, roads = [], []
    for index, item in enumerate(data["nodes"], start=1):
        try:
            if not isinstance(item, dict):
                raise ValidationError("Düğüm kaydı bir nesne olmalıdır.")
            values = dict(item)
            values["node_type"] = NodeType(values["node_type"])
            nodes.append(Node(**values))
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError(f"Düğüm kaydı {index}: {error}") from error
    for index, item in enumerate(data["roads"], start=1):
        try:
            if not isinstance(item, dict):
                raise ValidationError("Yol kaydı bir nesne olmalıdır.")
            values = dict(item)
            values["status"] = RoadStatus(values["status"])
            roads.append(Road(**values))
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError(f"Yol kaydı {index}: {error}") from error
    return Scenario(data["name"], data["description"], Graph(nodes, roads))
