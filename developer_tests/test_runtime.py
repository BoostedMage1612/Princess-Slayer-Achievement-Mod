"""Portable runtime regression checks; no game, Steam or real saves are modified."""
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'mod/python-packages'))
from stp_guide.controller import Guide, canonical_story_path

DATA=json.loads((ROOT/'mod/stp_guide_data.json').read_text(encoding='utf-8'))

class TestGuide(Guide):
    def verify(self):
        # The portable tests ship no licensed game scripts. Only the source-hash
        # check is stubbed here; location resolution and route validation are real.
        self.compatible=True

class Engine:
    def __init__(self):
        self.current=('game/scripts/ch_1/script.rpyc',1498)
        self.session={}
    def file(self,name):
        return open(ROOT/'mod'/name,'rb')
    def get_filename_line(self):return self.current
    def restart_interaction(self):pass
    def full_restart(self,**kwargs):self.restart_request=kwargs

def state_store(defaults,state,metadata=None):
    store=SimpleNamespace()
    for key,value in dict(defaults,**state).items():
        target=store
        parts=key.split('.')
        for part in parts[:-1]:
            if not hasattr(target,part):setattr(target,part,SimpleNamespace())
            target=getattr(target,part)
        setattr(target,parts[-1],value)
    store.persistent=getattr(store,'persistent',SimpleNamespace())
    store.stpg_route_id=None;store.stpg_cursor=0;store.stpg_paused=False
    for key,value in (metadata or {}).items():setattr(store,key,value)
    return store

class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        engine=Engine()
        config=SimpleNamespace(menu_arguments_callback=None,label_callback=None,basedir=cls.temp.name)
        steam=SimpleNamespace(list_achievements=lambda:[a['id'] for a in DATA['achievements']],get_achievement=lambda _:False)
        cls.guide=TestGuide(engine,SimpleNamespace(persistent=SimpleNamespace()),config,SimpleNamespace(steam=steam))
        assert cls.guide.compatible and not cls.guide.error
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.g=self.guide
        self.g.old_menu_callback=None
        self.g.diagnostic_events=[]
        self.g.menu_pc=None;self.g.recommended=None;self.g.current_index=None
    def select(self,r,index,state):
        self.g.store=state_store(self.g.model.defaults,state,{'stpg_route_id':r['id'],'stpg_cursor':index})
        node=self.g.model.nodes[r['steps'][index][0]]
        self.g.renpy.current=('game/'+node['file']+'c',node['line'])

    def test_compiled_and_windows_paths(self):
        want='scripts/ch_1/script.rpy'
        variants=['scripts/ch_1/script.rpy','scripts/ch_1/script.rpyc',
                  'game/scripts/ch_1/script.rpyc',r'game\scripts\ch_1\script.rpyc',
                  r'C:\Program Files (x86)\Steam\steamapps\common\Slay the Princess\game\SCRIPTS\ch_1\script.RPYC',
                  'D:/game/Games/STP/game/scripts/ch_1/script.rpyc',
                  './game/scripts/ch_1/../ch_1/script.rpyc']
        for value in variants:self.assertEqual(canonical_story_path(value),want)
        self.assertNotEqual(canonical_story_path('unrelated/script.rpyc'),want)
        self.assertNotEqual(canonical_story_path('scripts/ch_1/script.rpyc.bak'),want)

    def test_all_556_menu_locations_in_source_and_compiled_forms(self):
        for (path,line),pc in self.g.locations.items():
            for prefix,suffix in [('',''),('game/','c'),('C:/Games/STP/GAME/','C')]:
                self.g.renpy.current=(prefix+path+suffix,line)
                self.assertEqual(self.g.location(),pc)
            self.g.renpy.current=('game/'+path+'c',-999)
            self.assertIsNone(self.g.location())
        self.assertEqual(len(self.g.locations),556)

    def test_every_route_highlights_its_first_compiled_choice(self):
        for r in self.g.routes:
            pc,state,_,_,_=self.g.model.advance(self.g.model.labels['start'],{})
            self.select(r,0,state)
            before=copy.deepcopy(vars(self.g.store))
            args,kwargs=self.g.menu_callback()
            with self.subTest(route=r['name']):
                self.assertEqual(kwargs.get('screen'),'stpg_choice',self.g.message)
                self.assertEqual(self.g.recommended,r['steps'][0][1])
                self.assertEqual(vars(self.g.store),before)
                self.assertTrue(self.g.next_text)

    def test_save_load_resynchronizes_on_compiled_menu(self):
        r=max(self.g.routes,key=lambda route:len(route['steps']))
        result=self.g.model.replay(r['steps'])
        index=len(r['steps'])//2
        self.select(r,index,result['snapshots'][index])
        self.g.after_load()
        _,kwargs=self.g.menu_callback()
        self.assertEqual(kwargs.get('screen'),'stpg_choice',self.g.message)
        self.assertEqual(self.g.current_index,index)
        self.g.store.stpg_cursor=index-1
        self.g.after_load()
        _,kwargs=self.g.menu_callback()
        self.assertEqual(kwargs.get('screen'),'stpg_choice',self.g.message)
        self.assertEqual(self.g.current_index,index)

    def test_unknown_location_does_not_guess_or_modify_original_menu(self):
        r=self.g.routes[0]
        self.select(r,0,{})
        self.g.renpy.current=('C:/Users/TestPerson/other/script.rpyc',1498)
        args,kwargs=self.g.menu_callback('custom',screen='original_choice')
        self.assertEqual(args,('custom',));self.assertEqual(kwargs,{'screen':'original_choice'})
        self.assertIsNone(self.g.recommended)
        self.assertIn('could not be identified',self.g.message)
        payload=json.loads((Path(self.temp.name)/'stp_guide_diagnostics.json').read_text())
        self.assertNotIn('TestPerson',json.dumps(payload))
        self.assertEqual(payload['events'][-1]['location']['file'],'script.rpy')

    def test_pause_and_original_callback_are_preserved(self):
        r=self.g.routes[0]
        self.select(r,0,{})
        self.g.store.stpg_paused=True
        self.g.old_menu_callback=lambda *args,**kwargs:(args,dict(kwargs,custom_option=True))
        _,kwargs=self.g.menu_callback()
        self.assertTrue(kwargs['custom_option']);self.assertNotIn('screen',kwargs)
        self.assertIsNone(self.g.recommended)

    def test_diagnostics_are_bounded_and_collect_no_story_state(self):
        r=self.g.routes[0]
        self.select(r,0,{})
        for _ in range(40):self.g.menu_callback()
        payload=json.loads((Path(self.temp.name)/'stp_guide_diagnostics.json').read_text())
        self.assertEqual(len(payload['events']),32)
        self.assertTrue(payload['events'][-1]['location']['compiled'])
        self.assertEqual(payload['events'][-1]['location']['pc'],r['steps'][0][0])
        self.assertNotIn('persistent',json.dumps(payload))
        self.assertNotIn('steam_id',json.dumps(payload))
        self.assertNotIn('state',payload)

    def test_unwritable_diagnostics_do_not_stop_guidance(self):
        r=self.g.routes[0];self.select(r,0,{})
        previous=self.g.config.basedir
        try:
            self.g.config.basedir=str(Path(self.temp.name)/'does-not-exist')
            _,kwargs=self.g.menu_callback()
            self.assertEqual(kwargs.get('screen'),'stpg_choice')
        finally:self.g.config.basedir=previous

if __name__=='__main__':unittest.main(verbosity=2)
