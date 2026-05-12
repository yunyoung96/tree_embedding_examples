# -*- coding: utf-8 -*-
"""ChromaDB 3분 가이드"""
import chromadb
import os

client = chromadb.PersistentClient(path="./db")
col = client.get_or_create_collection("data")

# 기존 DB 로드 또는 새로 저장
if col.count() > 0:
    print("✓ 기존 DB 로드:", col.get()['documents'])
else:
    col.add(ids=["1","2"], embeddings=[[0.1,0.2],[0.4,0.5]], documents=["a","b"])
    print("✓ 새로 저장:", col.get()['documents'])

# 유사 검색
sim = col.query(query_embeddings=[[0.15,0.25]], n_results=1)
print("✓ 유사:", sim['documents'][0])

# 메타 필터링
col.upsert(ids=["3"], embeddings=[[0.7,0.8]], documents=["c"], metadatas=[{"type":"fruit"}])
filt = col.query(query_embeddings=[[0,0]], where={"type":"fruit"}, n_results=10)
print("✓ 필터:", filt['documents'][0])

# 업데이트 & 삭제
col.upsert(ids=["1"], embeddings=[[0.9,0.9]], documents=["a_new"])
print("✓ 최종:", col.get()['documents'])

# 메모리 (임시용)
temp = chromadb.EphemeralClient().get_or_create_collection("tmp")
temp.add(ids=["x"], embeddings=[[1,2]], documents=["temp"])
print("✓ 메모리:", temp.get()['documents'])

