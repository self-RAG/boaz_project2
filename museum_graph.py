"""
국립중앙박물관 소장품 → Neo4j 키워드 기반 그래프 구축
노드: 유물, 시대, 재질, 분류, 작가, 전시위치
관계: 속한시대, 재질로만들어짐, 분류됨, 만든작가, 전시위치
"""

import json
import re
import os
import neo4j
from neo4j import GraphDatabase

# ── 설정 ──────────────────────────────────────────
# 환경변수로 관리 (보안): set NEO4J_URI=... 또는 .env 파일 사용
NEO4J_URI      = os.environ.get("NEO4J_URI",      "neo4j+ssc://d9fce9a7.databases.neo4j.io")
NEO4J_USER     = os.environ.get("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
JSON_PATH      = os.environ.get("JSON_PATH",      "museum_collections.json")


def clean(text: str) -> str:
    """괄호 안 한자/영문 제거, 공백 정리"""
    if not text:
        return ""
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip()


def parse_period(raw: str):
    """
    '한국 - 조선' → {'국적': '한국', '시대': '조선'}
    '중국'        → {'국적': '중국', '시대': None}
    """
    if not raw:
        return {"국적": None, "시대": None}
    parts = [p.strip() for p in raw.split(" - ")]
    return {
        "국적": parts[0] if parts else None,
        "시대": parts[1] if len(parts) > 1 else None,
    }


def parse_category(raw: str):
    """
    '종교신앙 - 불교 - 예배 - 불상'
    → ['종교신앙', '불교', '예배', '불상']
    """
    if not raw:
        return []
    return [p.strip() for p in raw.split(" - ") if p.strip()]


def parse_material(raw: str):
    """
    '도자기 - 흑유' → ['도자기', '흑유']
    '종이'          → ['종이']
    """
    if not raw:
        return []
    return [p.strip() for p in raw.split(" - ") if p.strip()]


def build_graph(driver, records):
    with driver.session() as session:

        # ── 인덱스 생성 (최초 1회) ──────────────────
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:유물)      REQUIRE n.소장품번호 IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:시대)      REQUIRE n.name IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:국적)      REQUIRE n.name IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:재질)      REQUIRE n.name IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:분류)      REQUIRE n.name IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:작가)      REQUIRE n.name IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:전시위치)  REQUIRE n.name IS UNIQUE")
        print("인덱스 준비 완료", flush=True)

        ok, skip = 0, 0
        try:
            for rec in records:
                번호 = rec.get("소장품번호")
                if not 번호:
                    skip += 1
                    continue

                period   = parse_period(rec.get("국적/시대", ""))
                cats     = parse_category(rec.get("분류", ""))
                mats     = parse_material(rec.get("재질", ""))
                작가raw  = rec.get("작가", "")
                작가name = clean(작가raw) if 작가raw and 작가raw != "작가미상" else None
                전시위치  = rec.get("전시위치", "").strip() or None

                session.execute_write(
                    _create_artifact,
                    rec, 번호, period, cats, mats, 작가name, 전시위치
                )
                ok += 1
                if ok % 100 == 0:
                    print(f"  {ok}건 처리 중...", flush=True)

        except KeyboardInterrupt:
            print(f"\n중단됨: {ok}건 저장 완료 / 스킵 {skip}건", flush=True)
            return

        print(f"\n완료: 성공 {ok}건 / 스킵 {skip}건", flush=True)


def _create_artifact(tx, rec, 번호, period, cats, mats, 작가name, 전시위치):

    # ── 유물 노드 ──────────────────────────────────
    tx.run("""
        MERGE (u:유물 {소장품번호: $번호})
        SET u.title      = $title,
            u.전시명칭   = $display,
            u.importance = $importance,
            u.has3D      = $has3D,
            u.relicId    = $relicId
    """, 번호=번호,
         title=rec.get("title",""),
         display=rec.get("전시명칭",""),
         importance=rec.get("importance",""),
         has3D=rec.get("has3D", False),
         relicId=rec.get("relicId"))

    # ── 국적 노드 & 관계 ───────────────────────────
    if period["국적"]:
        tx.run("""
            MERGE (g:국적 {name: $name})
            WITH g
            MATCH (u:유물 {소장품번호: $번호})
            MERGE (u)-[:국적]->(g)
        """, name=period["국적"], 번호=번호)

    # ── 시대 노드 & 관계 ───────────────────────────
    if period["시대"]:
        tx.run("""
            MERGE (s:시대 {name: $name})
            WITH s
            MATCH (u:유물 {소장품번호: $번호})
            MERGE (u)-[:속한시대]->(s)
        """, name=period["시대"], 번호=번호)

    # ── 재질 노드 & 관계 (계층 + 전체 연결) ──────────
    prev_mat = None
    for mat in mats:
        tx.run("MERGE (:재질 {name: $name})", name=mat)
        if prev_mat:
            tx.run("""
                MATCH (p:재질 {name: $p}), (c:재질 {name: $c})
                MERGE (p)-[:하위재질]->(c)
            """, p=prev_mat, c=mat)
        tx.run("""
            MATCH (u:유물 {소장품번호: $번호}), (m:재질 {name: $mat})
            MERGE (u)-[:재질로만들어짐]->(m)
        """, 번호=번호, mat=mat)
        prev_mat = mat

    # ── 분류 노드 & 관계 (계층 + 전체 연결) ──────────
    prev_cat = None
    for cat in cats:
        tx.run("MERGE (:분류 {name: $name})", name=cat)
        if prev_cat:
            tx.run("""
                MATCH (p:분류 {name: $p}), (c:분류 {name: $c})
                MERGE (p)-[:하위분류]->(c)
            """, p=prev_cat, c=cat)
        tx.run("""
            MATCH (u:유물 {소장품번호: $번호}), (c:분류 {name: $cat})
            MERGE (u)-[:분류됨]->(c)
        """, 번호=번호, cat=cat)
        prev_cat = cat

    # ── 작가 노드 & 관계 ───────────────────────────
    if 작가name:
        tx.run("""
            MERGE (a:작가 {name: $name})
            WITH a
            MATCH (u:유물 {소장품번호: $번호})
            MERGE (u)-[:만든작가]->(a)
        """, name=작가name, 번호=번호)

    # ── 전시위치 노드 & 관계 ───────────────────────
    if 전시위치:
        tx.run("""
            MERGE (e:전시위치 {name: $name})
            WITH e
            MATCH (u:유물 {소장품번호: $번호})
            MERGE (u)-[:전시위치]->(e)
        """, name=전시위치, 번호=번호)


if __name__ == "__main__":
    if not NEO4J_PASSWORD:
        print("❌ NEO4J_PASSWORD 환경변수가 설정되지 않았습니다.")
        print("   set NEO4J_PASSWORD=your_password  (Windows)")
        print("   export NEO4J_PASSWORD=your_password  (Mac/Linux)")
        exit(1)

    with open(JSON_PATH, encoding="utf-8") as f:
        records = json.load(f)

    print(f"총 {len(records)}건 로드 완료")

    # neo4j+ssc:// : self-signed certificate 허용 (SSL 검증 우회)
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )
    try:
        build_graph(driver, records)
    finally:
        driver.close()
        print("연결 종료")