from dataclasses import replace
from pathlib import Path
import unittest
from ayros.assignment import Task, Vehicle, DispatchInput, load_dispatch, assign_vehicles
from ayros.model import ValidationError
from ayros.scenario import load_scenario
ROOT=Path(__file__).resolve().parents[1]
class TaskTests(unittest.TestCase):
 def setUp(self):
  self.graph=load_scenario(ROOT/'data/bolgesel_ag.json').graph
  self.fleet=load_dispatch(ROOT/'data/gorev_senaryosu.json',self.graph)
 def test_same_region_has_independent_tasks(self):
  items=[e for e in assign_vehicles(self.graph,self.fleet) if e.need.node.id=='A08']
  self.assertEqual(len(items),3)
  self.assertEqual({e.service:e.status for e in items},{'logistics':'assigned','medical':'assigned','rescue':'no_available_vehicle'})
 def test_service_capacity_units_and_unique_assignments(self):
  entries=assign_vehicles(self.graph,self.fleet);ids=[]
  for e in entries:
   if e.vehicle:
    self.assertEqual(e.service,e.vehicle.service);self.assertLessEqual(e.demand,e.vehicle.capacity);ids.append(e.vehicle.id)
   self.assertEqual(e.unit,'koli' if e.service=='logistics' else 'ekip')
  self.assertEqual(len(ids),len(set(ids)));self.assertEqual(len(ids),8)
 def test_urgency_precedes_area_score(self):
  entries=assign_vehicles(self.graph,self.fleet)
  self.assertLess(next(e.rank for e in entries if e.task.id=='A03-K'),next(e.rank for e in entries if e.task.id=='A08-K'))
 def test_wrong_type_vehicle_cannot_take_medical_task(self):
  fleet=DispatchInput((Vehicle('V','H1',999),),{},(Task('T','A08','medical',1,5),))
  self.assertEqual(assign_vehicles(self.graph,fleet)[0].status,'no_matching_vehicle')
 def test_empty_tasks_is_valid(self):
  self.assertEqual(assign_vehicles(self.graph,replace(self.fleet,tasks=())),())
 def test_invalid_task_values(self):
  for change in ({'urgency':True},{'urgency':6},{'service':[]},{'quantity':0},{'service':'medical','quantity':2}):
   with self.subTest(change=change),self.assertRaises(ValidationError):
    replace(Task('T','A08','logistics',10,3),**change)
 def test_duplicate_task_id_and_pair_rejected(self):
  t=Task('T','A08','medical',1,5)
  for tasks in ((t,t),(t,replace(t,id='OTHER')),(replace(t,target='H0'),)):
   with self.assertRaises(ValidationError):assign_vehicles(self.graph,replace(self.fleet,tasks=tasks))
 def test_vehicle_service_validation(self):
  for service,cap in [('medical',10),('rescue',2),('unknown',1),([],1)]:
   with self.assertRaises(ValidationError):Vehicle('V','H0',cap,True,service)
 def test_task_input_order_independent(self):
  a=assign_vehicles(self.graph,self.fleet)
  b=assign_vehicles(self.graph,replace(self.fleet,tasks=tuple(reversed(self.fleet.tasks)),vehicles=tuple(reversed(self.fleet.vehicles))))
  self.assertEqual([(e.task,e.vehicle,e.status) for e in a],[(e.task,e.vehicle,e.status) for e in b])
 def test_algorithms_agree_for_mixed_services(self):
  a=assign_vehicles(self.graph,self.fleet,algorithm='astar');b=assign_vehicles(self.graph,self.fleet,algorithm='dijkstra')
  for x,y in zip(a,b):
   self.assertEqual((x.task,x.vehicle,x.status),(y.task,y.vehicle,y.status))
   if x.route:self.assertAlmostEqual(x.route.cost_min,y.route.cost_min)
