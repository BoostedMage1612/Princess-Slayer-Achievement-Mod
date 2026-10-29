"""Run: python developer_tests/test_engine_location.py /path/to/renpy-8.0.3-sdk

Creates a temporary, asset-free test game. Exercises the actual engine loader,
Menu.execute, menu callback and ChoiceReturn values in source, compiled-only
and RPA archive modes. Never touches an installed game or real Steam account.
"""
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

DRIVER=r'''
init python:
    import renpy as _test_engine
    from types import SimpleNamespace as _TestNamespace
    from stp_guide.controller import Guide as _TestGuide
    def _test_store(guide, state, route):
        target_store = _TestNamespace()
        for key,value in dict(guide.model.defaults, **state).items():
            target = target_store
            parts = key.split('.')
            for part in parts[:-1]:
                if not hasattr(target,part):setattr(target,part,_TestNamespace())
                target = getattr(target,part)
            setattr(target,parts[-1],value)
        target_store.stpg_route_id=route['id']
        target_store.stpg_cursor=0
        target_store.stpg_paused=False
        return target_store
    def _test_engine_menu():
        _test_engine.arguments.takes_no_arguments()
        api = _test_engine.exports
        fake_steam = _TestNamespace(list_achievements=lambda:[],get_achievement=lambda _:False)
        fake_store = _TestNamespace(persistent=_TestNamespace())
        guide = _TestGuide(api,fake_store,_test_engine.config,_TestNamespace(steam=fake_steam))
        assert guide.compatible and not guide.error, guide.error
        node = next(n for n in _test_engine.game.script.namemap.values()
                    if isinstance(n,_test_engine.ast.Menu) and n.linenumber==1498)
        _test_engine.config.menu_arguments_callback=guide.menu_callback
        # The capture replaces display only. Menu.execute and argument dispatch
        # still run in the actual engine and use its real ChoiceReturn objects.
        def capture(items):
            args,kwargs=api.get_menu_args()
            assert kwargs.get('screen')=='stpg_choice', (api.get_filename_line(),guide.message)
            recommended=[(caption,action) for caption,action in items
                         if guide.is_recommended(_TestNamespace(action=action))]
            assert len(recommended)==1
            value=recommended[0][1].value
            assert value==guide.by_id[guide.store.stpg_route_id]['steps'][0][1]
            guide.chosen(value)
            assert guide.store.stpg_cursor==1
            return value
        _test_engine.store.menu=capture
        _test_engine.config.statement_callbacks=[]
        first_pc,state,_,_,_=guide.model.advance(guide.model.labels['start'],{})
        for route in guide.routes:
            guide.store=_test_store(guide,state,route)
            _test_engine.game.context().current=node.name
            assert guide.location()==first_pc, (api.get_filename_line(),guide.location())
            node.execute()
        print('PASS_ENGINE_MENUS',len(guide.routes),repr(node.filename),node.linenumber)
        return False
    _test_engine.arguments.register_command('stpg_engine_menu',_test_engine_menu)
'''

def run(engine,project,mode):
    result=subprocess.run([str(engine),str(project),'stpg_engine_menu'],text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    if result.returncode or 'PASS_ENGINE_MENUS 562' not in result.stdout:
        raise AssertionError(mode+' failed:\n'+result.stdout)
    print(mode+': '+result.stdout.strip(),flush=True)

def make_archive(path,files):
    # Standard RPA-3.0 archive with an unencrypted zero XOR key, test data only.
    with path.open('wb') as stream:
        stream.write(b'RPA-3.0 0000000000000000 00000000\n')
        index={}
        for name,data in files.items():
            index[name]=[(stream.tell(),len(data),b'')]
            stream.write(data)
        offset=stream.tell()
        stream.write(zlib.compress(pickle.dumps(index,protocol=2)))
        stream.seek(0)
        stream.write(('RPA-3.0 %016x 00000000\n'%offset).encode('ascii'))

def main():
    sdk=Path(sys.argv[1]).resolve()
    engine=sdk/('renpy.exe' if os.name=='nt' else 'renpy.sh')
    if not engine.is_file():raise SystemExit('Pass the matching Ren\'Py 8.0.3 SDK directory.')
    data=json.loads((ROOT/'mod/stp_guide_data.json').read_text(encoding='utf-8'))
    first=data['model']['nodes'][str(data['routes'][0]['steps'][0][0])]
    lines=['']*1495+['label start:','    pass','    menu:']
    for choice in first['choices']:
        lines.extend(['        '+json.dumps(choice['text'],ensure_ascii=False)+':','            pass'])
    lines.append('    return')
    fixture=('\n'.join(lines)+'\n').encode('utf-8')
    # This fixture has its own checked source manifest; the production manifest
    # and route database in mod/ remain untouched.
    data['source_manifest']=[{'path':'fixture_source.txt','sha256':hashlib.sha256(fixture).hexdigest(),'size':len(fixture)}]
    fixture_signature=[[c['text'],'True',True] for c in first['choices']]
    data['runtime_menus'][str(first['id'])]['signature']=hashlib.sha256(json.dumps(fixture_signature,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
    with tempfile.TemporaryDirectory(prefix='stpg_engine_test_') as temporary:
        project=Path(temporary);game=project/'game';script=game/'scripts/ch_1/script.rpy'
        script.parent.mkdir(parents=True)
        script.write_bytes(fixture)
        (game/'fixture_source.txt').write_bytes(fixture)
        (game/'driver.rpy').write_text(DRIVER,encoding='utf-8')
        (game/'stp_guide_data.json').write_text(json.dumps(data),encoding='utf-8')
        shutil.copytree(ROOT/'mod/python-packages',game/'python-packages',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        run(engine,project,'Source files')
        compiled=script.with_suffix('.rpyc')
        compiled_bytes=compiled.read_bytes()
        script.unlink()
        run(engine,project,'Compiled files only')
        make_archive(game/'archive.rpa',{'scripts/ch_1/script.rpy':fixture,'scripts/ch_1/script.rpyc':compiled_bytes})
        compiled.unlink()
        run(engine,project,'Archived source and compiled files')

if __name__=='__main__':main()
