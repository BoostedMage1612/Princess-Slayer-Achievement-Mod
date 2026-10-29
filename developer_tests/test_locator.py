"""Adapter regression tests. Optional STPG_SCAN points to an extracted scan/game_code."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'mod/python-packages'))
from stp_guide.controller import Guide
from stp_guide.core import Model
from stp_guide.location import MenuLocator,fingerprint,normalized_file
DATA=json.loads((ROOT/'mod/stp_guide_data.json').read_text(encoding='utf-8'))
class Menu:
    def __init__(self,filename,line,name,items):
        self.filename=filename;self.linenumber=line;self.name=name;self.items=items
class Api:
    def __init__(self,node=None,location=None):
        self.node=node;self.override=location;self.session={};self.calls=[]
        self.game=NS(script=NS(namemap={node.name:node} if node else {}),context=lambda:NS(current=node.name if node else None))
    def get_filename_line(self):return self.override or (self.node.filename,self.node.linenumber)
    def restart_interaction(self):self.calls.append('restart')
    def full_restart(self,**kw):self.calls.append(kw)
class LocatorTests(unittest.TestCase):
    def setUp(self):
        self.items=[('A','available',[object()]),('B','True',[object()])]
        self.nodes={1:dict(op='menu',file='scripts/start.rpy',line=10),2:dict(op='menu',file='scripts/start.rpy',line=20)}
        self.runtime={'1':dict(name=['game/scripts/start.rpy',123,1],signature=fingerprint(self.items)),
                      '2':dict(name=['game/scripts/start.rpy',123,2],signature=fingerprint([('C','True',[object()])]))}
        self.locator=MenuLocator(self.nodes,self.runtime)
    def node(self,**kw):
        return Menu(kw.get('file','game/scripts/start.rpy'),kw.get('line',10),kw.get('name',('game/scripts/start.rpy',123,1)),kw.get('items',self.items))
    def test_compiled_node_survives_missing_debug_location(self):
        self.assertEqual(self.locator.locate(Api(self.node(),('unknown',0)))[0],1)
    def test_exports_facade_exposes_engine_indirectly(self):
        api=Api(self.node(),('unknown',0))
        facade=NS(get_filename_line=api.get_filename_line,renpy=api)
        pc,info=self.locator.locate(facade)
        self.assertEqual(pc,1);self.assertEqual(info['method'],'compiled_menu')
    def test_windows_paths_case_slashes_and_compiled_extension(self):
        for path in [r'C:\Games\Slay The Princess\GAME\SCRIPTS\START.RPYC',r'.\game\\scripts\\start.rpy','./game/scripts/start.rpy']:
            self.assertEqual(self.locator.locate(Api(self.node(file=path,name=(path,123,1))))[0],1)
    def test_unique_full_menu_survives_recompiled_names_and_line_drift(self):
        pc,info=self.locator.locate(Api(self.node(line=200,name=('game/scripts/start.rpy',999,99))))
        self.assertEqual(pc,1);self.assertEqual(info['method'],'unique_menu_signature')
    def test_changed_condition_or_caption_is_rejected(self):
        for items in [[('A','other',[1]),('B','True',[1])],[('Wrong','available',[1]),('B','True',[1])]]:
            self.assertIsNone(self.locator.locate(Api(self.node(items=items)))[0])
    def test_ambiguous_full_menu_is_rejected(self):
        self.runtime['2']['signature']=self.runtime['1']['signature']
        locator=MenuLocator(self.nodes,self.runtime)
        self.assertIsNone(locator.locate(Api(self.node(line=99,name=('game/scripts/start.rpy',999,99))))[0])
    def test_unrelated_script_and_nonmenu_rejected(self):
        self.assertIsNone(self.locator.locate(Api(self.node(file='other.rpy',name=('other.rpy',4,2))))[0])
        node=NS(filename='game/scripts/start.rpy',linenumber=10,name=('game/scripts/start.rpy',123,1))
        self.assertIsNone(self.locator.locate(Api(node))[0])
    def test_documented_api_fallback_is_normalized(self):
        api=NS(get_filename_line=lambda:(r'C:\Games\STP\game\scripts\start.rpy',10))
        self.assertEqual(self.locator.locate(api)[0],1)
if __name__=='__main__':unittest.main()
