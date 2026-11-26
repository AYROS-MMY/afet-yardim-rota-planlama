"""Deterministik, tek seferlik araç hareketi ve düğümde yeniden rotalama.

Her step tüm filoyu en yakın düğüme varış zamanına ilerletir. Yol değişimi
iki adım arasında uygulanır. Üzerinde araç bulunan yol değiştirilemez.
Atama bir kez yapılır; rota değişimi araç/görev eşleşmesini değiştirmez.
"""

from copy import deepcopy
from dataclasses import dataclass, replace

from .assignment import DispatchInput, assign_vehicles
from .model import Graph, RoadStatus, ValidationError, require_number
from .priority import PriorityPolicy
from .routing import CostModel, find_shortest_path


@dataclass
class _VehicleState:
    id: str
    origin: str
    node: str
    task_id: str | None
    status: str
    path: tuple[str, ...] = ()
    roads: tuple[str, ...] = ()
    edge_id: str | None = None
    edge_started_at: float | None = None
    edge_arrival_at: float | None = None
    arrival_at: float | None = None
    reroutes: int = 0
    distance_km: float = 0.0
    reroute_pending: bool = False


class Simulation:
    """Hesap motoru. snapshot() değiştirilebilir iç durumu dışarı vermez."""

    def __init__(self, graph: Graph, fleet: DispatchInput, *,
                 algorithm: str = "astar", cost_model: CostModel | None = None,
                 policy: PriorityPolicy | None = None):
        self._graph = Graph(list(graph.nodes.values()), list(graph.roads.values()))
        self._cost_model = cost_model or CostModel()
        self._algorithm = algorithm
        entries = assign_vehicles(self._graph, fleet, algorithm=algorithm,
                                  cost_model=self._cost_model, policy=policy)
        self._time = 0.0
        self._step = 0
        self._events: list[dict] = []
        self._tasks: dict[str, dict] = {}
        self._vehicles: dict[str, _VehicleState] = {}
        assigned = {}
        for entry in entries:
            task_id = entry.task.id if entry.task else entry.need.node.id
            vehicle_id = entry.vehicle.id if entry.vehicle else None
            self._tasks[task_id] = {
                "id": task_id, "target": entry.need.node.id,
                "service": entry.service, "unit": entry.unit,
                "requested": entry.demand, "reserved": entry.demand if vehicle_id else 0,
                "delivered": 0, "team_arrived": False,
                "vehicle_id": vehicle_id,
                "status": "assigned" if vehicle_id else "unassigned",
                "reason": None if vehicle_id else entry.status,
            }
            if vehicle_id:
                assigned[vehicle_id] = (task_id, entry.route)
        for vehicle in sorted(fleet.vehicles, key=lambda item: item.id):
            state = _VehicleState(vehicle.id, vehicle.center, vehicle.center, None,
                                  "idle" if vehicle.available else "unavailable")
            if vehicle.id in assigned:
                state.task_id, route = assigned[vehicle.id]
                state.path, state.roads = route.path, route.road_ids
                state.status = "ready"
            self._vehicles[vehicle.id] = state
        self._record("initialized", assigned=len(assigned), tasks=len(entries))

    @property
    def graph(self) -> Graph:
        return Graph(list(self._graph.nodes.values()), list(self._graph.roads.values()))

    def _record(self, kind: str, **values) -> None:
        self._events.append({"sequence": len(self._events), "step": self._step,
                             "time_min": self._time, "kind": kind, **values})

    def _replan(self, state: _VehicleState) -> None:
        task = self._tasks[state.task_id]
        old_path = state.path
        route = find_shortest_path(self._graph, state.node, task["target"],
                                   algorithm=self._algorithm, cost_model=self._cost_model)
        state.path, state.roads = route.path, route.road_ids
        state.reroute_pending = False
        state.reroutes += 1
        state.status = "ready" if route.found else "blocked"
        task["status"] = "assigned" if route.found else "blocked"
        task["reason"] = None if route.found else "no_route_from_current_node"
        self._record("route_changed" if route.found else "route_blocked",
                     vehicle_id=state.id, task_id=state.task_id, node=state.node,
                     old_path=list(old_path), new_path=list(route.path),
                     remaining_time_min=route.cost_min)

    def change_roads(self, changes: dict[str, str]) -> dict:
        """Bir grup yol değişimini doğruladıktan sonra birlikte uygula.

        Aynı değerleri tekrar göndermek etkisizdir. Etkin kenar değişimi
        reddedilir; araç o kenarın sonuna ulaştıktan sonra yeniden denenebilir.
        """
        if not isinstance(changes, dict):
            raise ValidationError("Yol değişimleri kimlik/durum nesnesi olmalıdır.")
        updates = {}
        occupied = {state.edge_id for state in self._vehicles.values() if state.edge_id}
        for road_id, value in changes.items():
            if road_id not in self._graph.roads:
                raise ValidationError(f"Yol bulunamadı: {road_id}")
            try:
                status = RoadStatus(value)
            except (ValueError, TypeError) as error:
                raise ValidationError(f"{road_id}: geçersiz yol durumu.") from error
            if status == self._graph.roads[road_id].status:
                continue
            if road_id in occupied:
                raise ValidationError(f"{road_id} üzerinde araç var; düğüme varışını bekleyin.")
            road = replace(self._graph.roads[road_id], status=status)
            self._cost_model.cost_minutes(road)
            updates[road_id] = road
        if not updates:
            return self.snapshot()
        candidate = Graph(list(self._graph.nodes.values()),
                          [updates.get(road.id, road) for road in self._graph.roads.values()])
        # Rota hesaplaması sayısal hata üretirse tüm olay geri alınır.
        old_graph = self._graph
        old_vehicles, old_tasks = deepcopy(self._vehicles), deepcopy(self._tasks)
        event_count = len(self._events)
        self._graph = candidate
        try:
            self._record("roads_changed", changes={key: updates[key].status.value
                                                   for key in sorted(updates)})
            for state in self._vehicles.values():
                affected = bool(set(state.roads).intersection(updates))
                if state.status == "blocked" or affected:
                    if state.edge_id:
                        state.reroute_pending = True
                    else:
                        self._replan(state)
        except Exception:
            self._graph = old_graph
            self._vehicles, self._tasks = old_vehicles, old_tasks
            del self._events[event_count:]
            raise
        return self.snapshot()

    def step(self) -> dict:
        """Sıradaki düğüme varışı işle. İlerleme yoksa aynı durumu döndür."""
        previous = (self._time, self._step, deepcopy(self._vehicles), deepcopy(self._tasks))
        event_count = len(self._events)
        try:
            return self._advance()
        except Exception:
            self._time, self._step, self._vehicles, self._tasks = previous
            del self._events[event_count:]
            raise

    def _advance(self) -> dict:
        for state in self._vehicles.values():
            if state.status != "ready":
                continue
            road_id = state.roads[0]
            duration = self._cost_model.cost_minutes(self._graph.roads[road_id])
            if duration is None:
                raise RuntimeError("Geçersiz kalan rota: kapalı yola giriş.")
            state.edge_id = road_id
            state.edge_started_at = self._time
            state.edge_arrival_at = self._time + duration
            require_number(state.edge_arrival_at, "Simülasyon varış zamanı")
            state.status = "en_route"
            self._tasks[state.task_id]["status"] = "en_route"
            self._record("departed", vehicle_id=state.id, road_id=road_id,
                         source=state.node, target=state.path[1])
        arrivals = [state.edge_arrival_at for state in self._vehicles.values() if state.edge_id]
        if not arrivals:
            return self.snapshot()
        self._time = min(arrivals)
        self._step += 1
        for state in self._vehicles.values():
            if state.edge_id is None or state.edge_arrival_at != self._time:
                continue
            state.distance_km += self._graph.roads[state.edge_id].distance_km
            state.node = state.path[1]
            state.path, state.roads = state.path[1:], state.roads[1:]
            state.edge_id = state.edge_started_at = state.edge_arrival_at = None
            self._record("node_reached", vehicle_id=state.id, node=state.node)
            task = self._tasks[state.task_id]
            if state.node == task["target"]:
                state.status = "arrived"
                state.arrival_at = self._time
                task["reserved"] = 0
                if task["service"] == "logistics":
                    task["delivered"] = task["requested"]
                    task["status"] = "delivered"
                else:
                    task["team_arrived"] = True
                    task["status"] = "team_arrived"
                self._record(task["status"], vehicle_id=state.id, task_id=state.task_id,
                             quantity=task["requested"], unit=task["unit"])
            elif state.reroute_pending:
                self._replan(state)
            else:
                state.status = "ready"
        return self.snapshot()

    def snapshot(self) -> dict:
        tasks = []
        for task in self._tasks.values():
            item = dict(task)
            completed = item["delivered"] if item["service"] == "logistics" else int(item["team_arrived"])
            item["remaining"] = item["requested"] - completed
            item["unassigned"] = item["remaining"] - item["reserved"]
            tasks.append(item)
        vehicles = []
        for state in self._vehicles.values():
            eta = None
            if state.status in ("ready", "en_route") and not state.reroute_pending:
                roads = state.roads[1:] if state.edge_id else state.roads
                remaining = sum(self._cost_model.cost_minutes(self._graph.roads[r]) for r in roads)
                if state.edge_id:
                    remaining += state.edge_arrival_at - self._time
                eta = self._time + remaining
            vehicles.append({
                "id": state.id, "origin": state.origin, "node": state.node,
                "task_id": state.task_id, "status": state.status,
                "edge_id": state.edge_id, "next_node": state.path[1] if state.edge_id else None,
                "edge_started_at": state.edge_started_at, "edge_arrival_at": state.edge_arrival_at,
                "remaining_path": list(state.path), "remaining_roads": list(state.roads),
                "arrival_at": state.arrival_at, "eta_min": eta,
                "reroute_pending": state.reroute_pending, "reroutes": state.reroutes,
                "completed_distance_km": state.distance_km,
            })
        logistics = [task for task in tasks if task["service"] == "logistics"]
        return {"schema_version": 1, "time_min": self._time, "step": self._step,
                "can_advance": any(v["status"] in ("ready", "en_route") for v in vehicles),
                "vehicles": vehicles, "tasks": tasks,
                "roads": {key: road.status.value for key, road in self._graph.roads.items()},
                "logistics": {key: sum(t[key] for t in logistics)
                              for key in ("requested", "delivered", "reserved", "unassigned", "remaining")},
                "events": deepcopy(self._events)}
