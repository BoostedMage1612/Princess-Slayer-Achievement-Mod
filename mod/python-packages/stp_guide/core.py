"""Pure data interpreter for the supplied STP scripts. Never executes game code."""
import heapq
import itertools
import time
from collections import defaultdict, deque

class UnknownValue(Exception): pass

class Model:
    def __init__(self,data):
        self.data=data
        self.nodes={int(k):v for k,v in data['nodes'].items()}
        self.labels=data['labels']
        self.defaults={'_preferences.language':None,'preferences.self_voicing':False}
        pending=dict(data['defaults'])
        for repeat in range(8):
            progress=0
            for name,value in list(pending.items()):
                try:self.defaults[name]=self.eval(value,{})
                except (UnknownValue,TypeError):continue
                del pending[name];progress+=1
            if not progress:break
        self.pending_defaults=pending
        self.reverse=defaultdict(list)
        self.goals=defaultdict(list)
        self.menu_ids=[]
        for i,n in self.nodes.items():
            if n['op']=='menu':self.menu_ids.append(i)
            for j in self.targets(n):
                if j is not None and j != self.labels['start']:self.reverse[j].append((i,1 if n['op']=='menu' else 0))
            for a in n.get('actions',[]):
                if a[0]=='goal':self.goals[a[1]].append(i)
        self.dist_cache={}
        self.failures=defaultdict(int)
        self.stats={}

    def val(self,key,s):
        if key in s:return s[key]
        if key in self.defaults:return self.defaults[key]
        raise UnknownValue(key)

    def eval(self,e,s):
        op=e[0]
        if op=='c':return e[1]
        if op=='v':return self.val(e[1],s)
        if op=='and':
            value=True
            for x in e[1:]:
                value=self.eval(x,s)
                if not value:return value
            return value
        if op=='or':
            value=False
            for x in e[1:]:
                value=self.eval(x,s)
                if value:return value
            return value
        if op=='not':return not self.eval(e[1],s)
        if op=='neg':return -self.eval(e[1],s)
        if op=='pos':return self.eval(e[1],s)
        if op=='days':return self.eval(e[1],s)
        if op=='cmp':
            left=self.eval(e[1],s)
            for cmp,rightcode in e[2]:
                right=self.eval(rightcode,s)
                if cmp=='==':v=left==right
                elif cmp=='!=':v=left!=right
                elif cmp=='<':v=left<right
                elif cmp=='<=':v=left<=right
                elif cmp=='>':v=left>right
                elif cmp=='>=':v=left>=right
                elif cmp=='is':v=left is right
                elif cmp=='isnot':v=left is not right
                elif cmp=='in':v=left in right
                elif cmp=='notin':v=left not in right
                else:raise UnknownValue('comparison '+cmp)
                if not v:return False
                left=right
            return True
        if op=='seq':return tuple(self.eval(x,s) for x in e[1:])
        if op in ('+','-','*','/','//','%'):
            a=self.eval(e[1],s);b=self.eval(e[2],s)
            if op=='+':return a+b
            if op=='-':return a-b
            if op=='*':return a*b
            if op=='/':return a/b
            if op=='//':return a//b
            return a%b
        if op in ('int','bool','str','len','min','max'):
            fun={'int':int,'bool':bool,'str':str,'len':len,'min':min,'max':max}[op]
            return fun(*[self.eval(x,s) for x in e[1:]])
        raise UnknownValue('operator '+op)

    @staticmethod
    def targets(n):
        if n['op']=='menu':return [c['next'] for c in n['choices']]
        if n['op']=='if':return [b[1] for b in n['branches']]+[n['next']]
        return [n['next']]

    def put(self,s,k,v):
        if k in self.defaults and v==self.defaults[k]:s.pop(k,None)
        else:s[k]=v

    def advance(self,pc,s,goal=None,max_cycles=None,stop_start=False):
        """Mutates a private shadow dictionary only. Returns next decision + rewards."""
        gained=set();special=[]
        for counter in range(20000):
            if pc is None:return None,s,gained,special,'end'
            if max_cycles is not None and self.val('loops_finished',s)>max_cycles:return pc,s,gained,special,'limit'
            if stop_start and pc==self.labels['start']:return pc,s,gained,special,'boundary'
            n=self.nodes[pc];op=n['op']
            if op=='menu':return pc,s,gained,special,'menu'
            if op=='end':return None,s,gained,special,'end'
            if op=='if':
                target=n['next']
                for cond,dest in n['branches']:
                    if self.eval(cond,s):target=dest;break
                pc=target;continue
            if op=='actions':
                for a in n['actions']:
                    if a[0]=='set':self.put(s,a[1],self.eval(a[2],s))
                    elif a[0]=='goal':gained.add(a[1])
                    elif a[0]=='relaunch':
                        special.append({'kind':'relaunch','at':pc,'text':'The game intentionally closes here. Relaunch it through Steam; its own saved scene will resume.'})
                        # The game's splashscreen sets this before loading its own gimmick save.
                        self.put(s,'persistent.quiet_gimmick_stage_2',True)
                    elif a[0]=='external_link':return None,s,gained,special,'external'
                pc=n['next']
                if goal and goal in gained:return pc,s,gained,special,'goal'
                continue
            raise UnknownValue('unsupported '+str(pc))
        raise UnknownValue('deterministic instruction limit')

    def distances(self,goal):
        if goal in self.dist_cache:return self.dist_cache[goal]
        starts=self.goals.get(goal,[]) if isinstance(goal,str) else goal
        dist={i:0 for i in starts};q=deque(starts)
        while q:
            j=q.popleft()
            for i,cost in self.reverse[j]:
                v=dist[j]+cost
                if v<dist.get(i,10**9):
                    dist[i]=v
                    if cost:q.append(i)
                    else:q.appendleft(i)
        if isinstance(goal,str):self.dist_cache[goal]=dist
        return dist

    def solve(self,goal,start=None,state=None,max_states=60000,seconds=8,max_choices=100,max_cycles=0,weight=1.5):
        start=self.labels['start'] if start is None else start
        state=dict(state or {})
        if getattr(self,'stage_graph',None):
            dist=self.stage_graph.distance(goal)
            distance=lambda pc,s:self.stage_graph.lookup(dist,pc,s)
        else:
            dist=self.distances(goal)
            distance=lambda pc,s:dist.get(pc,10**9)
        if distance(start,state)>=10**9:return None
        q=[];counter=itertools.count();seen={};visited=0;began=time.monotonic()
        # records: priority, depth, tie, pc, shadow, path, rewards, specials
        heapq.heappush(q,(distance(start,state),0,next(counter),start,state,[],set(),[]))
        while q and visited<max_states:
            if time.monotonic()-began>seconds:break
            _,depth,_,pc,s,path,rewards,specials=heapq.heappop(q)
            try:pc,s,g,sp,reason=self.advance(pc,s,goal,max_cycles)
            except (UnknownValue,TypeError,ZeroDivisionError) as e:
                self.failures[str(e)]+=1;continue
            rewards=rewards|g;specials=specials+sp
            if reason=='goal':
                result={'steps':path,'goals':sorted(rewards),'state':s,'pc':pc,'special':specials,'target':goal}
                self.stats[goal]={'states':visited,'seconds':round(time.monotonic()-began,3),'steps':len(path)}
                return result
            if reason!='menu' or depth>=max_choices or distance(pc,s)>=10**9:continue
            key=(pc,tuple(sorted(s.items())))
            if seen.get(key,10**9)<=depth:continue
            seen[key]=depth;visited+=1
            node=self.nodes[pc]
            for j,c in enumerate(node['choices']):
                if distance(c['next'],s)>=10**9:continue
                try:available=self.eval(c['when'],s)
                except (UnknownValue,TypeError):continue
                if not available:continue
                newpath=path+[[pc,j]]
                heapq.heappush(q,(depth+1+distance(c['next'],s)*weight,depth+1,next(counter),c['next'],s.copy(),newpath,rewards,specials))
        self.stats[goal]={'states':visited,'seconds':round(time.monotonic()-began,3),'failed':True,'queued':len(q)}
        return None

    def replay(self,steps,start=None,state=None):
        pc=self.labels['start'] if start is None else start
        s=dict(state or {});gained=set();snapshots=[];special=[]
        for want,choice in steps:
            pc,s,g,sp,reason=self.advance(pc,s)
            gained.update(g);special.extend(sp)
            if reason!='menu' or pc!=want:raise ValueError('route divergence %s expected %s (%s)'%(pc,want,reason))
            c=self.nodes[pc]['choices'][choice]
            if not self.eval(c['when'],s):raise ValueError('disabled choice '+str(pc))
            snapshots.append(s.copy())
            pc=c['next']
        pc,s,g,sp,reason=self.advance(pc,s)
        gained.update(g);special.extend(sp)
        return {'pc':pc,'state':s,'goals':sorted(gained),'snapshots':snapshots,'special':special,'reason':reason}
