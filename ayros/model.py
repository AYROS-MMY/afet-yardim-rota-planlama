"""İkinci hafta: yönsüz çizge, düğüm ve yol modeli. Henüz rota hesabı yoktur."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class ValidationError(ValueError):
    """Senaryo verisi model kurallarına uymadığında oluşur."""


class NodeType(str, Enum):
    INTERSECTION = "intersection"
    AID_CENTER = "aid_center"
    DISASTER_AREA = "disaster_area"


class RoadStatus(str, Enum):
    OPEN = "open"
    DAMAGED = "damaged"
    CLOSED = "closed"


def require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field}: boş olmayan bir metin olmalıdır.")


def require_number(value: float, field: str, *, positive: bool = False) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not isfinite(value)):
        raise ValidationError(f"{field}: sonlu bir sayı olmalıdır.")
    if positive and value <= 0:
        raise ValidationError(f"{field}: sıfırdan büyük olmalıdır.")


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    node_type: NodeType
    x_km: float
    y_km: float
    affected_count: int = 0
    injured_count: int = 0
    urgency_level: int = 0

    def __post_init__(self) -> None:
        require_text(self.id, "Düğüm kimliği")
        require_text(self.name, "Düğüm adı")
        if not isinstance(self.node_type, NodeType):
            raise ValidationError("Geçersiz düğüm türü.")
        require_number(self.x_km, "x_km")
        require_number(self.y_km, "y_km")
        for field in ("affected_count", "injured_count", "urgency_level"):
            value = getattr(self, field)
            if type(value) is not int or value < 0:
                raise ValidationError(f"{field}: negatif olmayan tam sayı olmalıdır.")
        if self.injured_count > self.affected_count:
            raise ValidationError("Yaralı sayısı afetzede sayısını aşamaz.")
        if self.node_type == NodeType.DISASTER_AREA:
            if not 1 <= self.urgency_level <= 5:
                raise ValidationError("Afet noktası aciliyeti 1 ile 5 arasında olmalıdır.")
        elif any((self.affected_count, self.injured_count, self.urgency_level)):
            raise ValidationError("İhtiyaç bilgileri yalnızca afet noktalarında tutulabilir.")


@dataclass(frozen=True)
class Road:
    id: str
    source: str
    target: str
    distance_km: float
    travel_time_min: float
    status: RoadStatus

    def __post_init__(self) -> None:
        for field in ("id", "source", "target"):
            require_text(getattr(self, field), f"Yol {field}")
        if self.source == self.target:
            raise ValidationError("Yol iki farklı düğümü bağlamalıdır.")
        require_number(self.distance_km, "distance_km", positive=True)
        require_number(self.travel_time_min, "travel_time_min", positive=True)
        if not isinstance(self.status, RoadStatus):
            raise ValidationError("Geçersiz yol durumu.")


class Graph:
    """Yolları iki yönde saklayan basit komşuluk listesi.

    Kapalı yollar modelde korunur, geçilebilir komşu sorgusunda filtrelenir.
    Hasarlı yollar geçilebilirdir; hasar maliyeti sonraki aşamada eklenecektir.
    """

    def __init__(self, nodes: list[Node], roads: list[Road]) -> None:
        if not nodes:
            raise ValidationError("Senaryo en az bir düğüm içermelidir.")
        self.nodes: dict[str, Node] = {}
        self.roads: dict[str, Road] = {}
        self._adjacency: dict[str, list[tuple[str, Road]]] = {}
        for node in nodes:
            if node.id in self.nodes:
                raise ValidationError(f"Tekrarlanan düğüm kimliği: {node.id}")
            self.nodes[node.id] = node
            self._adjacency[node.id] = []
        pairs = set()
        for road in roads:
            if road.id in self.roads:
                raise ValidationError(f"Tekrarlanan yol kimliği: {road.id}")
            if road.source not in self.nodes or road.target not in self.nodes:
                raise ValidationError(f"{road.id}: yolun bağlandığı düğüm bulunamadı.")
            pair = frozenset((road.source, road.target))
            if pair in pairs:
                raise ValidationError(f"{road.id}: aynı iki düğüm arasında ikinci yol var.")
            pairs.add(pair)
            self.roads[road.id] = road
            self._adjacency[road.source].append((road.target, road))
            self._adjacency[road.target].append((road.source, road))

    def neighbors(self, node_id: str, *, traversable_only: bool = True) -> list[tuple[str, Road]]:
        """Komşu kimliği ve yol bilgisini döndürür; rota araması yapmaz."""
        if node_id not in self.nodes:
            raise ValidationError(f"Düğüm bulunamadı: {node_id}")
        return [(neighbor, road) for neighbor, road in self._adjacency[node_id]
                if not traversable_only or road.status != RoadStatus.CLOSED]
