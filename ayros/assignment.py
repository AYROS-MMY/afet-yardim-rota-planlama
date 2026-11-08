"""İhtiyaç sırasını koruyan, tek turluk ve kapasite kısıtlı açgözlü atama."""

from dataclasses import dataclass
import json
from pathlib import Path

from .model import Graph, NodeType, ValidationError, require_text
from .priority import NeedScore, PriorityPolicy, rank_needs
from .routing import CostModel, RouteResult, find_shortest_path


SERVICES = {'logistics': 'Lojistik', 'medical': 'Sağlık', 'rescue': 'Kurtarma'}


@dataclass(frozen=True)
class Vehicle:
    id: str
    center: str
    capacity: int
    available: bool = True
    service: str = 'logistics'

    def __post_init__(self):
        if not isinstance(self.service,str) or self.service not in SERVICES:
            raise ValidationError('Geçersiz araç hizmet türü.')
        if self.service != 'logistics' and self.capacity != 1:
            raise ValidationError('Sağlık/kurtarma aracı tek ekip görevi taşır.')
        require_text(self.id, 'Araç kimliği')
        require_text(self.center, 'Araç merkezi')
        if type(self.capacity) is not int or self.capacity <= 0:
            raise ValidationError('Araç kapasitesi pozitif tam sayı olmalıdır.')
        if type(self.available) is not bool:
            raise ValidationError('Araç uygunluğu true/false olmalıdır.')


@dataclass(frozen=True)
class Task:
    id: str
    target: str
    service: str
    quantity: int
    urgency: int

    def __post_init__(self):
        require_text(self.id, 'Görev kimliği')
        require_text(self.target, 'Görev hedefi')
        if not isinstance(self.service,str) or self.service not in SERVICES:
            raise ValidationError('Geçersiz görev hizmet türü.')
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValidationError('Görev miktarı pozitif tam sayı olmalıdır.')
        if self.service != 'logistics' and self.quantity != 1:
            raise ValidationError('Sağlık/kurtarma görevi bir ekip talebidir.')
        if type(self.urgency) is not int or not 1 <= self.urgency <= 5:
            raise ValidationError('Görev aciliyeti 1–5 olmalıdır.')

    @property
    def unit(self):
        return 'koli' if self.service == 'logistics' else 'ekip'


@dataclass(frozen=True)
class DispatchInput:
    vehicles: tuple[Vehicle, ...]
    demands: dict[str, int]
    tasks: tuple[Task, ...] | None = None

    def validate(self, graph: Graph):
        ids = [v.id for v in self.vehicles]
        if len(ids) != len(set(ids)):
            raise ValidationError('Araç kimlikleri benzersiz olmalıdır.')
        for vehicle in self.vehicles:
            if vehicle.center not in graph.nodes or graph.nodes[vehicle.center].node_type != NodeType.AID_CENTER:
                raise ValidationError(f'{vehicle.id}: başlangıç bir yardım merkezi olmalıdır.')
        targets = {n.id for n in graph.nodes.values() if n.node_type == NodeType.DISASTER_AREA}
        if self.tasks is not None:
            if self.demands:
                raise ValidationError('Görevler ve eski talepler birlikte kullanılamaz.')
            if len({t.id for t in self.tasks}) != len(self.tasks):
                raise ValidationError('Görev kimlikleri benzersiz olmalıdır.')
            if len({(t.target,t.service) for t in self.tasks}) != len(self.tasks):
                raise ValidationError('Aynı bölge ve tür için tek görev tanımlayın.')
            if any(t.target not in targets for t in self.tasks):
                raise ValidationError('Görev hedefi afet noktası olmalıdır.')
            return
        if set(self.demands) != targets:
            raise ValidationError('Her afet noktası için tam bir talep kaydı gerekir; fazladan kimlik olamaz.')
        if any(type(value) is not int or value <= 0 for value in self.demands.values()):
            raise ValidationError('Koli talepleri pozitif tam sayı olmalıdır.')


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f'Araç senaryosunda yinelenen JSON alanı: {key}')
        result[key] = value
    return result


def load_dispatch(path: str | Path, graph: Graph) -> DispatchInput:
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=_unique_fields)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f'Araç senaryosu okunamadı: {error}') from error
    if isinstance(data, dict) and type(data.get('schema_version')) is int and data['schema_version'] == 2:
        if set(data) != {'schema_version','vehicles','tasks'} or not isinstance(data['vehicles'],list) or not isinstance(data['tasks'],list):
            raise ValidationError('Sürüm 2 vehicles ve tasks listeleri içermelidir.')
        for item in data['vehicles']:
            if not isinstance(item,dict) or set(item) != {'id','center','capacity','available','service'}:
                raise ValidationError('Araç alanları eksik veya fazla.')
        for item in data['tasks']:
            if not isinstance(item,dict) or set(item) != {'id','target','service','quantity','urgency'}:
                raise ValidationError('Görev alanları eksik veya fazla.')
        result = DispatchInput(tuple(Vehicle(**v) for v in data['vehicles']), {}, tuple(Task(**t) for t in data['tasks']))
        result.validate(graph)
        return result
    if not isinstance(data, dict) or set(data) != {'schema_version', 'unit', 'vehicles', 'demands'}:
        raise ValidationError('Araç senaryosu schema_version, unit, vehicles ve demands içermelidir.')
    if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['unit'] != 'standard_aid_box':
        raise ValidationError('Sürüm 1 ve birim standard_aid_box olmalıdır.')
    if not isinstance(data['vehicles'], list) or not isinstance(data['demands'], dict):
        raise ValidationError('vehicles liste, demands nesne olmalıdır.')
    vehicles = []
    for item in data['vehicles']:
        if not isinstance(item, dict) or set(item) != {'id', 'center', 'capacity', 'available'}:
            raise ValidationError('Her araç id, center, capacity ve available içermelidir.')
        vehicles.append(Vehicle(**item))
    result = DispatchInput(tuple(vehicles), data['demands'])
    result.validate(graph)
    return result


REASONS = {
    'assigned': 'Atandı',
    'no_matching_vehicle': 'Uygun türde araç yok',
    'unreachable': 'Hiçbir merkezden ulaşılamıyor',
    'no_available_vehicle': 'Boş ve uygun araç yok',
    'insufficient_capacity': 'Boş araçların kapasitesi yetersiz',
    'no_reachable_vehicle': 'Kapasitesi yeterli boş araçtan rota yok',
}


@dataclass(frozen=True)
class Assignment:
    rank: int
    need: NeedScore
    demand: int
    status: str
    vehicle: Vehicle | None = None
    route: RouteResult | None = None
    task: Task | None = None

    @property
    def service(self):
        return self.task.service if self.task else 'logistics'

    @property
    def unit(self):
        return 'koli' if self.service == 'logistics' else 'ekip'



def assign_vehicles(graph: Graph, dispatch: DispatchInput, *,
                    policy: PriorityPolicy | None = None,
                    cost_model: CostModel | None = None,
                    algorithm: str = 'astar') -> tuple[Assignment, ...]:
    """Görev aciliyeti, bölge puanı ve uygun türden en kısa süreli araç.

    Eski şemada bölge sırası korunur; yeni şemada son görev eşitliği
    hedef/görev kimliğiyle, araç süresi eşitliği araç kimliğiyle çözülür.

    Talep bölünmez. Araç ilk görevinden sonra bu turda kullanılamaz.
    Global filo optimumu, stok takibi veya çok duraklı tur çözümü değildir.
    """
    dispatch.validate(graph)
    if algorithm not in ('astar', 'dijkstra'):
        raise ValidationError('Algoritma dijkstra veya astar olmalıdır.')
    model = cost_model or CostModel()
    centers = sorted(n.id for n in graph.nodes.values() if n.node_type == NodeType.AID_CENTER)
    if not centers:
        raise ValidationError('Atama için en az bir yardım merkezi gerekir.')
    used = set()
    entries = []
    needs = rank_needs(graph, policy)
    lookup = {n.node.id:n for n in needs}
    tasks = dispatch.tasks
    if tasks is None:
        work = [(None,n,dispatch.demands[n.node.id]) for n in needs]
    else:
        tasks = sorted(tasks,key=lambda t:(-t.urgency,-lookup[t.target].score,t.target,t.id))
        work = [(t,lookup[t.target],t.quantity) for t in tasks]
    cache = {}
    for rank, (task,need,demand) in enumerate(work, 1):
        if need.node.id not in cache:
            cache[need.node.id] = {c: find_shortest_path(graph,c,need.node.id,cost_model=model,algorithm=algorithm) for c in centers}
        routes = cache[need.node.id]
        matching = [v for v in dispatch.vehicles if v.service == (task.service if task else 'logistics')]
        free = [v for v in matching if v.available and v.id not in used]
        capable = [v for v in free if v.capacity >= demand]
        candidates = [v for v in capable if routes[v.center].found]
        if candidates:
            vehicle = min(candidates, key=lambda v: (routes[v.center].cost_min, v.id))
            used.add(vehicle.id)
            entries.append(Assignment(rank, need, demand, 'assigned', vehicle, routes[vehicle.center], task))
            continue
        if not any(r.found for r in routes.values()):
            status = 'unreachable'
        elif task is not None and not matching:
            status = 'no_matching_vehicle'
        elif not free:
            status = 'no_available_vehicle'
        elif not capable:
            status = 'insufficient_capacity'
        else:
            status = 'no_reachable_vehicle'
        entries.append(Assignment(rank, need, demand, status, task=task))
    return tuple(entries)
