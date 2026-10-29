"""Ren'Py adapter. Reads story/achievement state; writes guide metadata only."""
import hashlib
import json
import os
import datetime
import re
import posixpath
from .core import Model, UnknownValue
from .location import MenuLocator

GUIDE_VERSION = '0.2.3'

def canonical_story_path(filename):
    """Match engine source/compiled paths without guessing a choice by its text."""
    path=posixpath.normpath(str(filename).replace('\\','/')).casefold()
    if '/game/' in path:path=path.rsplit('/game/',1)[1]
    elif path.startswith('game/'):path=path[5:]
    # Ren'Py 8.0.3 rewrites node filenames to .rpyc when loading compiled-only
    # scripts or archives. Their line numbers still refer to the .rpy source.
    if path.endswith('.rpyc'):path=path[:-1]
    return path

class Guide:
    def __init__(self,renpy,store,config,achievement):
        self.renpy=renpy;self.store=store;self.config=config;self.achievement=achievement
        self.error='';self.compatible=False;self.pending=None;self.menu_pc=None
        self.recommended=None;self.message='Press F8 to choose a route.';self.current_index=None
        self.next_text=''
        self.last_location=None;self.validation_issue=None;self.diagnostic_events=[]
        self.rows=[];self.earned=set();self.unknown=set();self.gallery_earned=set();self.ranked=[]
        self.mode='runs';self.filter='';self.old_menu_callback=config.menu_arguments_callback
        self.old_label_callback=config.label_callback
        try:
            with renpy.file('stp_guide_data.json') as stream:self.data=json.load(stream)
            self.model=Model(self.data['model']);self.routes=self.data['routes']
            self.by_id={r['id']:r for r in self.routes}
            self.catalog=self.data['achievements'];self.titles={x['id']:x['title'] for x in self.catalog}
            self.goal_routes={}
            for r in self.routes:
                for goal in r['goals']:self.goal_routes.setdefault(goal,[]).append(r)
            self.locations={(canonical_story_path(n['file']),n['line']):i for i,n in self.model.nodes.items() if n['op']=='menu'}
            self.story_paths={path for path,line in self.locations}
            self.locator=MenuLocator(self.model.nodes,self.data.get('runtime_menus',{}))
            self.read_names=set(self.model.defaults)
            for n in self.model.nodes.values():
                for a in n.get('actions',[]):
                    if a[0]=='set':self.read_names.add(a[1])
            self.gallery_flags={}
            for g in self.data['model']['gallery']:
                self.gallery_flags['G:'+g['key']]=g['flag']
                for i in range(1,g['count']+1):self.gallery_flags['G:'+g['key']+':'+str(i)]='gallery_'+g['key']+'_'+str(i)
            self.verify()
            self.refresh()
        except Exception as exc:self.error='Guide could not load: '+type(exc).__name__+': '+str(exc)
        self.record_event('startup')

    def record_event(self,event,detail=None):
        """Bounded guide-only diagnostics; never export story state or saves."""
        try:
            rid=getattr(self.store,'stpg_route_id',None)
            index=getattr(self.store,'stpg_cursor',0)
            row={'event':event,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'route_id':rid,'cursor':index,'location':self.last_location,
                 'menu_pc':self.menu_pc,'recommended':self.recommended,
                 'message':self.message,'validation_issue':self.validation_issue}
            route=getattr(self,'by_id',{}).get(rid)
            if route and isinstance(index,int) and 0<=index<len(route['steps']):
                node=self.model.nodes[route['steps'][index][0]]
                row['expected_location']={'file':node['file'],'line':node['line']}
            if detail is not None:row['detail']=str(detail)[:240]
            self.diagnostic_events.append(row)
            self.diagnostic_events=self.diagnostic_events[-32:]
            payload={'product':'stp-achievement-guide','version':GUIDE_VERSION,
                     'compatible':self.compatible,'error':self.error,
                     'events':self.diagnostic_events}
            path=os.path.join(self.config.basedir,'stp_guide_diagnostics.json')
            if os.path.exists(path):
                if os.path.getsize(path)>262144:return
                with open(path,'r',encoding='utf-8') as stream:old=json.load(stream)
                if old.get('product')!='stp-achievement-guide':return
            temp=path+'.tmp'
            try:
                with open(temp,'w',encoding='utf-8') as stream:json.dump(payload,stream,ensure_ascii=True,indent=2)
                os.replace(temp,path)
            finally:
                if os.path.exists(temp):os.remove(temp)
        except Exception:
            # A read-only installation must never interrupt play for logging.
            pass

    def verify(self):
        bad=[]
        for f in self.data['source_manifest']:
            try:
                with self.renpy.file(f['path']) as stream:digest=hashlib.sha256(stream.read()).hexdigest()
                if digest!=f['sha256']:bad.append(f['path'])
            except Exception:bad.append(f['path'])
        if bad:
            self.error='This guide does not match the installed story files ('+str(len(bad))+' differences). Highlighting is disabled. First difference: '+bad[0]
            return
        self.compatible=True

    def live_state(self):
        state={}
        for key in self.read_names:
            try:
                value=self.store
                for part in key.split('.'):value=getattr(value,part)
            except AttributeError:continue
            if isinstance(value,(datetime.date,datetime.timedelta)):value=0
            if value is None or isinstance(value,(bool,int,float,str)):
                self.model.put(state,key,value)
        return state

    def refresh(self):
        self.earned=set();self.unknown=set();steam=getattr(self.achievement,'steam',None)
        available=set()
        try:available=set(steam.list_achievements()) if steam else set()
        except Exception:pass
        self.rows=[]
        local=getattr(self.store.persistent,'_achievements',set()) or set()
        for a in self.catalog:
            status=None
            if a['id'] in available:
                try:
                    v=steam.get_achievement(a['id'])
                    if v is True or v is False:status=v
                except Exception:pass
            if status is True:self.earned.add(a['id'])
            elif status is None:self.unknown.add(a['id'])
            self.rows.append(dict(a,status='earned' if status is True else 'missing' if status is False else 'unknown',local=a['id'] in local))
        self.extra_ids=sorted(available-set(self.titles))
        self.gallery_earned={k for k,f in self.gallery_flags.items() if bool(getattr(self.store.persistent,f,False))}
        self.plan_cache={}
        self.rank()

    def rank(self):
        missing=set(self.titles)-self.earned
        galleries=set() if 'ACH_GALLERY_FIXED' in self.earned else set(self.gallery_flags)-self.gallery_earned
        self.ranked=[]
        remaining=list(self.routes)
        while remaining and (missing or galleries):
            def score(r):
                goals=set(r['goals']);ac=len(goals&missing);gc=len(goals&galleries)
                if galleries<=goals and 'ACH_GALLERY_FIXED' in missing and any(g.startswith('G:') and g.count(':')==2 for g in goals):ac+=1
                return ac,gc,-len(r['steps'])
            best=max(remaining,key=score);ac,gc,_=score(best)
            if ac==0 and gc==0:break
            self.ranked.append(dict(route=best,ach=ac,gallery=gc,missing=sorted(set(best['goals'])&missing)))
            missing-=set(best['goals']);galleries-=set(best['goals']);remaining.remove(best)
            if not galleries and any(g.startswith('G:') and g.count(':')==2 for g in best['goals']):missing.discard('ACH_GALLERY_FIXED')
        self.uncovered_ach=sorted(missing);self.uncovered_gallery=sorted(galleries)

    def score_now(self,r):
        goals=set(r['goals']);ac=len((set(self.titles)-self.earned)&goals)
        gc=len((set(self.gallery_flags)-self.gallery_earned)&goals)
        if self.finishes_gallery(r):ac+=1
        return ac,gc

    def finishes_gallery(self,r):
        goals=set(r['goals'])
        return ('ACH_GALLERY_FIXED' not in self.earned and
                (set(self.gallery_flags)-self.gallery_earned)<=goals and
                any(g.startswith('G:') and g.count(':')==2 for g in goals))

    def plans_for(self,goal):
        if goal not in self.plan_cache:
            found=self.goal_routes.get(goal,[])
            self.plan_cache[goal]=sorted(found,key=lambda r:(-self.score_now(r)[0],-self.score_now(r)[1],len(r['steps'])))
        return self.plan_cache[goal]

    def title(self,goal):
        if goal in self.titles:return self.titles[goal]
        bits=goal.split(':')
        title=next((g['title'] for g in self.data['model']['gallery'] if g['key']==bits[1]),bits[1])
        return title+(' — gallery image '+bits[2] if len(bits)>2 else ' — gallery chapter')

    def start_new(self,route_id):
        if not self.compatible:return
        self.renpy.session['stpg_pending_route']=route_id
        self.message='Starting the selected guided run.'
        self.record_event('start_requested',route_id)
        self.renpy.full_restart(label='start')

    def label_callback(self,name,abnormal):
        if self.old_label_callback:self.old_label_callback(name,abnormal)
        if name=='start' and self.renpy.session.get('stpg_pending_route'):
            self.store.stpg_route_id=self.renpy.session.pop('stpg_pending_route');self.store.stpg_cursor=0
            self.store.stpg_paused=False
            self.message='Advance the dialogue normally. Gold marks the next choice.'
            self.menu_pc=None;self.recommended=None;self.current_index=None
            self.next_text='';self.last_location=None;self.validation_issue=None
            self.record_event('run_started')

    def location(self):
        pc,info=self.locator.locate(self.renpy)
        path=info.get('file','unknown')
        safe=path if path in self.story_paths else posixpath.basename(path)
        self.last_location=dict(info,file=safe,pc=pc)
        # Keep the latest diagnostic schema while adding recognition evidence.
        try:
            self.last_location['compiled']=str(self.renpy.get_filename_line()[0]).casefold().endswith('.rpyc')
        except Exception:
            self.last_location['compiled']=False
        return pc

    def validate_suffix(self,r,index,state):
        try:
            check=self.model.replay(r['steps'][index:],start=r['steps'][index][0],state=state)
            expected=set(g for at,goals in r['events'] if at>=index for g in goals)
            missing=expected-set(check['goals'])
            self.validation_issue=('Unreached rewards: '+', '.join(sorted(missing)[:8])) if missing else None
            return not missing,check
        except (UnknownValue,ValueError,TypeError,KeyError,ZeroDivisionError) as exc:
            self.validation_issue=type(exc).__name__+': '+str(exc)[:200]
            return False,None

    def compatible_index(self,r,pc,state,minimum=0):
        for index in range(minimum,len(r['steps'])):
            if r['steps'][index][0]!=pc:continue
            okay,_=self.validate_suffix(r,index,state)
            if okay:return index
        return None

    def can_join(self,route_id):
        if self.menu_pc is None or not self.compatible:return False
        return self.compatible_index(self.by_id[route_id],self.menu_pc,self.live_state()) is not None

    def join(self,route_id):
        r=self.by_id[route_id]
        index=self.compatible_index(r,self.menu_pc,self.live_state())
        if index is None:return
        self.store.stpg_route_id=route_id;self.store.stpg_cursor=index;self.store.stpg_paused=False
        self.update_menu(self.menu_pc)
        self.renpy.restart_interaction()

    def update_menu(self,pc):
        self.menu_pc=pc;self.recommended=None;self.current_index=None
        self.next_text=''
        self.validation_issue=None
        if not self.compatible:return
        rid=getattr(self.store,'stpg_route_id',None)
        if rid not in self.by_id:
            self.message='Press F8 to choose a guided run.';return
        if getattr(self.store,'stpg_paused',False):
            self.message='Guide paused. F8 opens the route panel.';return
        r=self.by_id[rid];index=getattr(self.store,'stpg_cursor',0)
        if pc is None:
            self.message='This menu could not be identified. Guidance is waiting; the reason has been logged.';return
        state=self.live_state()
        check=None;okay=False
        if index<len(r['steps']) and r['steps'][index][0]==pc:
            okay,check=self.validate_suffix(r,index,state)
        if not okay:
            # Loading and roll-forward can bypass button Actions. Recover from
            # the actual source location and prove every remaining reward again.
            found=self.compatible_index(r,pc,state,minimum=min(index,len(r['steps'])))
            if found is None:found=self.compatible_index(r,pc,state)
            if found is not None:
                index=found;okay,check=self.validate_suffix(r,index,state)
                self.store.stpg_cursor=index
            elif index>=len(r['steps']) or pc==r.get('end_pc'):
                self.store.stpg_cursor=len(r['steps'])
                self.message='Planned choices complete. Continue the scene, then press F8 to refresh progress.';return
        if not okay:
            self.message='The remaining route does not match this save. Press F8 to choose a compatible route.';return
        self.current_index=index;self.recommended=r['steps'][index][1]
        caption=self.model.nodes[pc]['choices'][self.recommended]['text']
        self.next_text=re.sub(r'\{[^}]*\}','',caption).replace('[[','[')
        self.message='Choice '+str(index+1)+' / '+str(len(r['steps']))+' — '+r['name']
        if any(sp.get('kind')=='relaunch' for sp in check.get('special',[])):
            # Warn only when the next choice reaches the game's intentional quit.
            c=self.model.nodes[pc]['choices'][self.recommended]
            try:
                _,_,_,special,_=self.model.advance(c['next'],state.copy())
                if special:self.message='This choice intentionally closes the game. Relaunch through Steam to continue.'
            except Exception:pass

    def menu_callback(self,*args,**kwargs):
        if self.old_menu_callback:args,kwargs=self.old_menu_callback(*args,**kwargs)
        try:
            self.update_menu(self.location())
            if self.recommended is not None:kwargs['screen']='stpg_choice'
            self.record_event('menu')
        except Exception as exc:
            self.recommended=None;self.message='Guidance paused: '+type(exc).__name__+'. The original menu is available.'
            self.record_event('menu_error',type(exc).__name__+': '+str(exc))
        return args,kwargs

    def chosen(self,value):
        # This records a user's click. It never invokes a game action.
        if self.current_index is None:return
        if value==self.recommended:
            self.store.stpg_cursor=self.current_index+1
            self.message='Advance the dialogue normally.'
        else:
            self.store.stpg_paused=True
            self.message='You chose another branch. F8 can find a compatible route.'
        self.recommended=None;self.current_index=None;self.menu_pc=None
        self.next_text=''
        self.record_event('choice_clicked',value)

    def is_recommended(self,item):
        return self.recommended is not None and getattr(item.action,'value',None)==self.recommended

    def scroll_to_choice(self,adjustment,items):
        """Bring the gold button into view; never invoke its action."""
        try:
            box=self.renpy.get_widget('stpg_choice','stpg_choice_box')
            index=next(i for i,item in enumerate(items) if self.is_recommended(item))
            adjustment.change(max(0,box.offsets[index][1]-18))
        except (AttributeError,IndexError,StopIteration,TypeError):pass

    def active_name(self):
        r=self.by_id.get(getattr(self.store,'stpg_route_id',None));return r['name'] if r else 'No route selected'

    def open(self):
        self.refresh();self.renpy.show_screen('stpg_panel');self.renpy.restart_interaction()

    def after_load(self):
        self.menu_pc=None;self.recommended=None;self.current_index=None
        self.next_text=''
        self.last_location=None;self.validation_issue=None
        self.message='Save loaded. Advance to the next choice to resume guidance.'
        self.record_event('save_loaded')

    def toggle_pause(self):
        self.store.stpg_paused=not self.store.stpg_paused
        if self.menu_pc is not None:self.update_menu(self.menu_pc)
        self.renpy.restart_interaction()
