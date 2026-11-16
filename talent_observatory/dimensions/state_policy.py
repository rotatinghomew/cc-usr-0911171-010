from __future__ import annotations
import datetime as dt
from collections import defaultdict,deque
from dataclasses import dataclass
from typing import Any,Callable,Iterable,Mapping,Sequence

class StatePolicyError(RuntimeError):pass

@dataclass(frozen=True)
class Transition:
    source:str
    target:str
    action:str
    roles:frozenset[str]
    guard:str|None=None
    terminal:bool=False

@dataclass(frozen=True)
class TransitionDecision:
    allowed:bool
    reasons:tuple[str,...]
    transition:Transition|None
    effects:tuple[Mapping[str,Any],...]

class StatePolicy:
    def __init__(self,initial:str,transitions:Sequence[Transition],guards:Mapping[str,Callable[[Mapping[str,Any],Mapping[str,Any]],bool]]|None=None):
        self.initial=initial;self.transitions=tuple(transitions);self.guards=dict(guards or {});self._by_action=defaultdict(list);self._by_source=defaultdict(list)
        for transition in transitions:
            self._by_action[transition.action].append(transition);self._by_source[transition.source].append(transition)
            if transition.guard and transition.guard not in self.guards:raise StatePolicyError(f'unknown guard {transition.guard}')
        if not initial:raise StatePolicyError('initial state required')
    def decide(self,state:str,action:str,role:str,facts:Mapping[str,Any],context:Mapping[str,Any]|None=None) -> TransitionDecision:
        candidates=[transition for transition in self._by_action.get(action,()) if transition.source==state]
        if not candidates:return TransitionDecision(False,('action_not_allowed_from_state',),None,())
        authorized=[transition for transition in candidates if not transition.roles or role in transition.roles]
        if not authorized:return TransitionDecision(False,('role_not_authorized',),None,())
        reasons=[]
        for transition in authorized:
            if transition.guard and not self.guards[transition.guard](facts,context or {}):reasons.append(f'guard_failed:{transition.guard}');continue
            effects=({'kind':'state_changed','from':state,'to':transition.target,'action':action,'role':role},{'kind':'terminal_reached','state':transition.target} if transition.terminal else {'kind':'workflow_continues','state':transition.target})
            return TransitionDecision(True,(),transition,effects)
        return TransitionDecision(False,tuple(reasons) or ('guard_failed',),None,())
    def apply(self,record:Mapping[str,Any],action:str,role:str,context:Mapping[str,Any]|None=None) -> tuple[dict[str,Any],TransitionDecision]:
        state=str(record.get('state',self.initial));decision=self.decide(state,action,role,record,context)
        if not decision.allowed:raise StatePolicyError(';'.join(decision.reasons))
        result=dict(record);result['state']=decision.transition.target;result['version']=int(record.get('version',0))+1;result['updated_at']=(context or {}).get('now',dt.datetime.now(dt.timezone.utc)).isoformat();result['last_action']=action
        return result,decision
    def actions(self,state:str,role:str|None=None) -> tuple[str,...]:return tuple(sorted({transition.action for transition in self._by_source.get(state,()) if role is None or not transition.roles or role in transition.roles}))
    def terminal_states(self) -> tuple[str,...]:return tuple(sorted({transition.target for transition in self.transitions if transition.terminal}))
    def reachable(self,start:str|None=None) -> tuple[str,...]:
        root=start or self.initial;seen={root};queue=deque([root])
        while queue:
            current=queue.popleft()
            for transition in self._by_source.get(current,()):
                if transition.target not in seen:seen.add(transition.target);queue.append(transition.target)
        return tuple(sorted(seen))
    def shortest_actions(self,start:str,target:str,role:str|None=None) -> tuple[str,...]:
        queue=deque([(start,())]);seen={start}
        while queue:
            state,path=queue.popleft()
            if state==target:return path
            for transition in self._by_source.get(state,()):
                if role is not None and transition.roles and role not in transition.roles:continue
                if transition.target not in seen:seen.add(transition.target);queue.append((transition.target,path+(transition.action,)))
        return ()
    def validate(self) -> tuple[str,...]:
        problems=[];reachable=set(self.reachable())
        for transition in self.transitions:
            if transition.source not in reachable:problems.append(f'unreachable_source:{transition.source}')
            if transition.source==transition.target:problems.append(f'self_transition:{transition.source}:{transition.action}')
        terminal=set(self.terminal_states())
        for state in terminal:
            if self._by_source.get(state):problems.append(f'terminal_has_outgoing:{state}')
        duplicates=defaultdict(int)
        for transition in self.transitions:duplicates[(transition.source,transition.action,tuple(sorted(transition.roles)))]+=1
        for key,count in duplicates.items():
            if count>1:problems.append('ambiguous:'+':'.join([key[0],key[1],','.join(key[2])]))
        return tuple(problems)
