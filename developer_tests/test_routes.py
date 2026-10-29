"""Run with Python 3: python developer_tests/test_routes.py"""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'mod/python-packages'))
from stp_guide.core import Model
DATA=json.loads((ROOT/'mod/stp_guide_data.json').read_text(encoding='utf-8'))
class RouteTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.model=Model(DATA['model'])
 def test_every_path_is_enabled_and_reaches_its_rewards(self):
  for r in DATA['routes']:
   with self.subTest(route=r['id']):
    result=self.model.replay(r['steps'])
    self.assertTrue(set(r['goals'])<=set(result['goals']))
 def test_full_achievement_and_gallery_coverage(self):
  covered={g for r in DATA['routes'] for g in r['goals']}
  achievements={a['id'] for a in DATA['achievements']}-{'ACH_GALLERY_FIXED'}
  gallery={'G:'+g['key']+tail for g in DATA['model']['gallery'] for tail in ['']+[':'+str(n) for n in range(1,g['count']+1)]}
  self.assertEqual(len(achievements),130);self.assertEqual(len(gallery),464)
  self.assertTrue(achievements<=covered);self.assertTrue(gallery<=covered)
 def test_event_tables_agree_with_routes(self):
  for r in DATA['routes']:
   self.assertEqual(set(r['goals']),{g for at,goals in r['events'] for g in goals})
   self.assertTrue(all(-1<=at<len(r['steps']) for at,goals in r['events']))
 def test_shadow_simulation_does_not_mutate_input(self):
  s={'loops_finished':0};before=dict(s)
  self.model.replay(DATA['routes'][0]['steps'],state=s)
  self.assertEqual(s,before)
 def test_wrong_step_is_rejected(self):
  with self.assertRaises(ValueError):self.model.replay([[-123,0]])
if __name__=='__main__':unittest.main(verbosity=2)
