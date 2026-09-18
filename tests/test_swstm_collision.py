#!/usr/bin/env python3
"""
SWSTM Collision Resistance Stress Test - CI version
Simulates naive single-slot vs bucketed slot memory.
Validates Recallspection claim: bucketed slots reduce overwrite-based catastrophic forgetting.
"""

import hashlib
from collections import Counter

NUM_SLOTS = 2000
NUM_FACTS = 10000
BUCKET_CAP_5 = 5
BUCKET_CAP_8 = 8

def slot_idx(key: str, n=NUM_SLOTS):
    h = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
    return h % n

class NaiveSlotMemory:
    def __init__(self, n):
        self.n=n; self.slots=[None]*n; self.collisions=0
    def add(self,k,v):
        idx=slot_idx(k,self.n)
        if self.slots[idx] is not None and self.slots[idx][0]!=k:
            self.collisions+=1
        self.slots[idx]=(k,v)
    def get_exact(self,k):
        idx=slot_idx(k,self.n); e=self.slots[idx]
        if e and e[0]==k: return e[1],"ok"
        return None,"missing"
    def get_raw(self,k):
        idx=slot_idx(k,self.n); e=self.slots[idx]
        if e is None: return None,"missing"
        if e[0]==k: return e[1],"ok"
        return e[1],"silent_wrong"

class BucketedSlotMemory:
    def __init__(self,n,cap):
        self.n=n; self.cap=cap; self.slots=[[] for _ in range(n)]; self.collisions=0; self.evictions=0
    def add(self,k,v):
        idx=slot_idx(k,self.n); b=self.slots[idx]
        for i,(ek,_) in enumerate(b):
            if ek==k: b[i]=(k,v); return
        if len(b)>0: self.collisions+=1
        if len(b)<self.cap: b.append((k,v))
        else: self.evictions+=1; b.pop(0); b.append((k,v))
    def get(self,k):
        idx=slot_idx(k,self.n)
        for ek,ev in self.slots[idx]:
            if ek==k: return ev,"ok"
        return None,"missing"

def evaluate_exact(store,facts):
    c=0
    for k,v in facts:
        rv,st=store.get_exact(k)
        if st=="ok" and rv==v: c+=1
    return c

def evaluate_bucket(store,facts):
    c=0
    for k,v in facts:
        rv,st=store.get(k)
        if st=="ok" and rv==v: c+=1
    return c

def test_swstm_collision_resistance():
    facts=[(f"key_{i}",f"value_{i}") for i in range(NUM_FACTS)]
    naive=NaiveSlotMemory(NUM_SLOTS)
    b5=BucketedSlotMemory(NUM_SLOTS,BUCKET_CAP_5)
    b8=BucketedSlotMemory(NUM_SLOTS,BUCKET_CAP_8)
    for k,v in facts:
        naive.add(k,v); b5.add(k,v); b8.add(k,v)
    c_naive=evaluate_exact(naive,facts)
    c_b5=evaluate_bucket(b5,facts)
    c_b8=evaluate_bucket(b8,facts)
    # Assertions: naive must be <25% at 10k/2k, bucket must be >80% and >95%
    assert c_naive/NUM_FACTS < 0.25, f"naive recall {c_naive/NUM_FACTS} should be <25% (proves collision problem)"
    assert c_b5/NUM_FACTS > 0.80, f"bucket5 recall {c_b5/NUM_FACTS} should be >80%"
    assert c_b8/NUM_FACTS > 0.95, f"bucket8 recall {c_b8/NUM_FACTS} should be >95%"
    # Silent wrong check for raw naive
    silent=0
    for k,v in facts:
        _,st=naive.get_raw(k)
        if st=="silent_wrong": silent+=1
    assert silent/NUM_FACTS > 0.75, f"naive silent_wrong {silent/NUM_FACTS} should be >75% without exact check"
    print(f"SWSTM collision: naive {c_naive/NUM_FACTS*100:.1f}% | b5 {c_b5/NUM_FACTS*100:.1f}% | b8 {c_b8/NUM_FACTS*100:.1f}% | silent_wrong {silent/NUM_FACTS*100:.1f}% - VERIFIED")

if __name__=="__main__":
    test_swstm_collision_resistance()
