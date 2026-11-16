from __future__ import annotations
from collections import defaultdict,deque
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class LineageError(RuntimeError):pass

@dataclass(frozen=True)
class Node:
    node_id:str
    kind:str
    attributes:Mapping[str,Any]

@dataclass(frozen=True)
class Edge:
    source:str
    target:str
    relation:str
    attributes:Mapping[str,Any]

class LineageGraph:
    def __init__(self):self.nodes:dict[str,Node]={};self.outgoing:dict[str,list[Edge]]=defaultdict(list);self.incoming:dict[str,list[Edge]]=defaultdict(list)
    def add_node(self,node_id:str,kind:str,attributes:Mapping[str,Any]|None=None) -> Node:
        if node_id in self.nodes:
            existing=self.nodes[node_id]
            if existing.kind!=kind:raise LineageError('node kind cannot change')
            return existing
        node=Node(node_id,kind,dict(attributes or {}));self.nodes[node_id]=node;return node
    def add_edge(self,source:str,target:str,relation:str,attributes:Mapping[str,Any]|None=None,allow_cycle:bool=False) -> Edge:
        if source not in self.nodes or target not in self.nodes:raise LineageError('edge endpoint missing')
        edge=Edge(source,target,relation,dict(attributes or {}))
        if edge in self.outgoing[source]:return edge
        self.outgoing[source].append(edge);self.incoming[target].append(edge)
        if not allow_cycle and self.cycles():self.outgoing[source].remove(edge);self.incoming[target].remove(edge);raise LineageError('edge creates cycle')
        return edge
    def remove_node(self,node_id:str) -> None:
        if node_id not in self.nodes:raise LineageError('unknown node')
        for edge in list(self.outgoing.get(node_id,())):self.incoming[edge.target].remove(edge)
        for edge in list(self.incoming.get(node_id,())):self.outgoing[edge.source].remove(edge)
        self.outgoing.pop(node_id,None);self.incoming.pop(node_id,None);del self.nodes[node_id]
    def ancestors(self,node_id:str,relations:Iterable[str]|None=None) -> tuple[str,...]:return self._walk(node_id,self.incoming,True,relations)
    def descendants(self,node_id:str,relations:Iterable[str]|None=None) -> tuple[str,...]:return self._walk(node_id,self.outgoing,False,relations)
    def _walk(self,node_id:str,edges:Mapping[str,Sequence[Edge]],reverse:bool,relations:Iterable[str]|None) -> tuple[str,...]:
        if node_id not in self.nodes:raise LineageError('unknown node')
        allowed=set(relations) if relations else None;seen=set();queue=deque([node_id])
        while queue:
            current=queue.popleft()
            for edge in edges.get(current,()):
                if allowed is not None and edge.relation not in allowed:continue
                neighbor=edge.source if reverse else edge.target
                if neighbor not in seen and neighbor!=node_id:seen.add(neighbor);queue.append(neighbor)
        return tuple(sorted(seen))
    def path(self,source:str,target:str) -> tuple[str,...]:
        queue=deque([(source,(source,))]);seen={source}
        while queue:
            current,path=queue.popleft()
            if current==target:return path
            for edge in self.outgoing.get(current,()):
                if edge.target not in seen:seen.add(edge.target);queue.append((edge.target,path+(edge.target,)))
        return ()
    def cycles(self) -> tuple[tuple[str,...],...]:
        cycles=[];temporary=set();permanent=set();stack=[]
        def visit(node_id):
            if node_id in permanent:return
            if node_id in temporary:
                position=stack.index(node_id);cycles.append(tuple(stack[position:]+[node_id]));return
            temporary.add(node_id);stack.append(node_id)
            for edge in self.outgoing.get(node_id,()):visit(edge.target)
            stack.pop();temporary.remove(node_id);permanent.add(node_id)
        for node_id in sorted(self.nodes):visit(node_id)
        return tuple(cycles)
    def topological(self) -> tuple[str,...]:
        indegree={node_id:len(self.incoming.get(node_id,())) for node_id in self.nodes};queue=deque(sorted(node for node,value in indegree.items() if value==0));result=[]
        while queue:
            current=queue.popleft();result.append(current)
            for edge in sorted(self.outgoing.get(current,()),key=lambda item:item.target):
                indegree[edge.target]-=1
                if indegree[edge.target]==0:queue.append(edge.target)
        if len(result)!=len(self.nodes):raise LineageError('graph contains cycle')
        return tuple(result)
    def impacted(self,changed:Iterable[str],kinds:Iterable[str]|None=None) -> tuple[str,...]:
        allowed=set(kinds) if kinds else None;result=set()
        for node_id in changed:
            for descendant in self.descendants(node_id):
                if allowed is None or self.nodes[descendant].kind in allowed:result.add(descendant)
        return tuple(sorted(result))
    def validate(self) -> tuple[str,...]:
        problems=[]
        for source,edges in self.outgoing.items():
            if source not in self.nodes:problems.append(f'missing_source:{source}')
            for edge in edges:
                if edge.target not in self.nodes:problems.append(f'missing_target:{edge.target}')
                if edge not in self.incoming.get(edge.target,()):problems.append(f'asymmetric_edge:{edge.source}:{edge.target}')
        for cycle in self.cycles():problems.append('cycle:'+'>'.join(cycle))
        return tuple(problems)
    def export(self) -> dict[str,Any]:return {'nodes':[{'node_id':node.node_id,'kind':node.kind,'attributes':dict(node.attributes)} for node in sorted(self.nodes.values(),key=lambda item:item.node_id)],'edges':[{'source':edge.source,'target':edge.target,'relation':edge.relation,'attributes':dict(edge.attributes)} for source in sorted(self.outgoing) for edge in sorted(self.outgoing[source],key=lambda item:(item.target,item.relation))]}
