"""İhtiyaç puanı ve merkezden erişim; araç ataması veya tıbbi triyaj değildir."""

from dataclasses import dataclass
import json
from math import fsum, isclose
from pathlib import Path

from .model import Graph, Node, NodeType, ValidationError, require_number, require_text
from .routing import CostModel, RouteResult, find_shortest_path


@dataclass(frozen=True)
class PriorityPolicy:
    """Sabit referanslarla 0-100 arası deneysel puan; diğer hedeflerden bağımsız.

    Referans, sayısal katkının doyduğu değerdir; hedef sayısı değişince değişmez.
    Ağırlıkların toplamı 1 olmalıdır. Aciliyet 1/5 de olsa pozitif katkı verir.
    """

    urgency_weight: float = 0.5
    injured_weight: float = 0.3
    affected_weight: float = 0.2
    injured_reference: int = 100
    affected_reference: int = 500

    def __post_init__(self) -> None:
        for field in ('urgency_weight', 'injured_weight', 'affected_weight'):
            value = getattr(self, field)
            require_number(value, field)
            if not 0 <= value <= 1:
                raise ValidationError(f'{field}: 0 ile 1 arasında olmalıdır.')
        if not isclose(self.weight_sum, 1.0, rel_tol=0, abs_tol=1e-12):
            raise ValidationError('Öncelik ağırlıklarının toplamı 1 olmalıdır.')
        for field in ('injured_reference', 'affected_reference'):
            value = getattr(self, field)
            if type(value) is not int or value <= 0:
                raise ValidationError(f'{field}: pozitif tam sayı olmalıdır.')

    @property
    def weight_sum(self) -> float:
        return fsum((self.urgency_weight, self.injured_weight, self.affected_weight))


def load_priority_policy(path: str | Path) -> PriorityPolicy:
    """Tam ve sürümlü politika dosyası; yazım hatalı alanları sessizce yok saymaz."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f'Öncelik politikası okunamadı: {error}') from error
    fields = set(PriorityPolicy.__dataclass_fields__)
    if not isinstance(data, dict) or set(data) != fields | {'schema_version'}:
        raise ValidationError('Politika schema_version ve beş ağırlık/referans alanını içermelidir.')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValidationError('Öncelik politikası schema_version değeri 1 olmalıdır.')
    return PriorityPolicy(**{key: data[key] for key in fields})


@dataclass(frozen=True)
class NeedScore:
    node: Node
    urgency_points: float
    injured_points: float
    affected_points: float
    injured_capped: bool
    affected_capped: bool

    @property
    def score(self) -> float:
        return min(100.0, fsum((self.urgency_points, self.injured_points, self.affected_points)))


def score_need(node: Node, policy: PriorityPolicy | None = None) -> NeedScore:
    if node.node_type != NodeType.DISASTER_AREA:
        raise ValidationError('İhtiyaç puanı yalnızca afet noktası için hesaplanabilir.')
    policy = policy if policy is not None else PriorityPolicy()
    # Büyük tamsayıları float'a çevirmeden önce doyur: geçerli sayılar taşmaz.
    injured = min(node.injured_count, policy.injured_reference) / policy.injured_reference
    affected = min(node.affected_count, policy.affected_reference) / policy.affected_reference
    scale = 100 / policy.weight_sum
    return NeedScore(node, scale * policy.urgency_weight * (node.urgency_level / 5),
                     scale * policy.injured_weight * injured,
                     scale * policy.affected_weight * affected,
                     node.injured_count > policy.injured_reference,
                     node.affected_count > policy.affected_reference)


def rank_needs(graph: Graph, policy: PriorityPolicy | None = None) -> tuple[NeedScore, ...]:
    """Azalan puan, aciliyet, yaralı, afetzede; son eşitlikte artan kimlik.

    Rota, merkez ve hasar katsayısı bu sıralamaya girmez. Yuvarlama yalnızca
    gösterim içindir. Eşit puanlı ihtiyaçlar da kararlı sıra numarası alır.
    """
    scores = [score_need(node, policy) for node in graph.nodes.values()
              if node.node_type == NodeType.DISASTER_AREA]
    if not scores:
        raise ValidationError('Önceliklendirme için en az bir afet noktası gerekir.')
    return tuple(sorted(scores, key=lambda item: (-item.score, -item.node.urgency_level,
                        -item.node.injured_count, -item.node.affected_count, item.node.id)))


@dataclass(frozen=True)
class PriorityEntry:
    rank: int
    need: NeedScore
    route: RouteResult


@dataclass(frozen=True)
class PriorityAssessment:
    start: str
    policy: PriorityPolicy
    cost_model: CostModel
    algorithm: str
    entries: tuple[PriorityEntry, ...]


def assess_priorities(graph: Graph, start: str, *, policy: PriorityPolicy | None = None,
                      cost_model: CostModel | None = None,
                      algorithm: str = 'dijkstra') -> PriorityAssessment:
    require_text(start, 'Yardım merkezi')
    if start not in graph.nodes or graph.nodes[start].node_type != NodeType.AID_CENTER:
        raise ValidationError('Öncelik değerlendirmesinin başlangıcı bir yardım merkezi olmalıdır.')
    policy = policy if policy is not None else PriorityPolicy()
    model = cost_model if cost_model is not None else CostModel()
    entries = tuple(PriorityEntry(rank, need, find_shortest_path(
        graph, start, need.node.id, cost_model=model, algorithm=algorithm))
        for rank, need in enumerate(rank_needs(graph, policy), 1))
    return PriorityAssessment(start, policy, model, algorithm, entries)
