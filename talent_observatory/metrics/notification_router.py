from __future__ import annotations
import datetime as dt
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class NotificationError(RuntimeError):pass

@dataclass(frozen=True)
class Subscription:
    recipient_id:str
    channels:tuple[str,...]
    topics:tuple[str,...]
    quiet_start:int|None=None
    quiet_end:int|None=None
    locale:str='zh-CN'
    enabled:bool=True

@dataclass(frozen=True)
class Delivery:
    delivery_id:str
    recipient_id:str
    channel:str
    topic:str
    payload:Mapping[str,Any]
    scheduled_at:dt.datetime
    dedupe_key:str

class NotificationRouter:
    CHANNELS={'sms','email','app','wechat'}
    def __init__(self):self.subscriptions:dict[str,Subscription]={};self.sent:set[str]=set();self.failures:dict[str,int]=defaultdict(int)
    def subscribe(self,subscription:Subscription) -> None:
        if not subscription.channels or any(channel not in self.CHANNELS for channel in subscription.channels):raise NotificationError('invalid channels')
        if not subscription.topics:raise NotificationError('topics required')
        self.subscriptions[subscription.recipient_id]=subscription
    def unsubscribe(self,recipient_id:str) -> None:self.subscriptions.pop(recipient_id,None)
    def quiet(self,subscription:Subscription,moment:dt.datetime) -> bool:
        if subscription.quiet_start is None or subscription.quiet_end is None:return False
        hour=moment.hour
        if subscription.quiet_start<subscription.quiet_end:return subscription.quiet_start<=hour<subscription.quiet_end
        return hour>=subscription.quiet_start or hour<subscription.quiet_end
    def next_allowed(self,subscription:Subscription,moment:dt.datetime) -> dt.datetime:
        if not self.quiet(subscription,moment):return moment
        candidate=moment.replace(hour=subscription.quiet_end or 0,minute=0,second=0,microsecond=0)
        if candidate<=moment:candidate+=dt.timedelta(days=1)
        return candidate
    def dedupe(self,recipient_id:str,topic:str,payload:Mapping[str,Any]) -> str:return hashlib.sha256((recipient_id+'|'+topic+'|'+json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)).encode()).hexdigest()
    def route(self,topic:str,payload:Mapping[str,Any],now:dt.datetime,recipients:Iterable[str]|None=None) -> tuple[Delivery,...]:
        selected=set(recipients) if recipients is not None else set(self.subscriptions);deliveries=[]
        for recipient_id in sorted(selected):
            subscription=self.subscriptions.get(recipient_id)
            if subscription is None or not subscription.enabled or topic not in subscription.topics:continue
            dedupe_key=self.dedupe(recipient_id,topic,payload)
            if dedupe_key in self.sent:continue
            scheduled=self.next_allowed(subscription,now)
            for channel in subscription.channels:
                identifier=hashlib.sha256((dedupe_key+'|'+channel).encode()).hexdigest()[:20]
                deliveries.append(Delivery(identifier,recipient_id,channel,topic,dict(payload),scheduled,dedupe_key))
        return tuple(deliveries)
    def mark_sent(self,delivery:Delivery) -> None:self.sent.add(delivery.dedupe_key);self.failures.pop(delivery.delivery_id,None)
    def mark_failed(self,delivery:Delivery) -> int:self.failures[delivery.delivery_id]+=1;return self.failures[delivery.delivery_id]
    def retry_at(self,delivery:Delivery,now:dt.datetime,maximum_attempts:int=4) -> dt.datetime|None:
        attempts=self.failures.get(delivery.delivery_id,0)
        if attempts>=maximum_attempts:return None
        return now+dt.timedelta(minutes=2**attempts)
    def batch_by_channel(self,deliveries:Sequence[Delivery]) -> dict[str,tuple[Delivery,...]]:
        groups=defaultdict(list)
        for delivery in deliveries:groups[delivery.channel].append(delivery)
        return {channel:tuple(values) for channel,values in sorted(groups.items())}
    def receipt(self,delivery:Delivery,status:str,occurred_at:dt.datetime) -> dict[str,Any]:
        if status not in {'sent','delivered','failed','bounced'}:raise NotificationError('invalid receipt status')
        return {'delivery_id':delivery.delivery_id,'recipient_id':delivery.recipient_id,'channel':delivery.channel,'topic':delivery.topic,'status':status,'occurred_at':occurred_at.isoformat()}
