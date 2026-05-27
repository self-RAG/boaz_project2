"""
국립중앙박물관 AI 도슨트 - Streamlit UI
실행: streamlit run chatbot_app.py
"""

import streamlit as st
import sys
import os
import requests
sys.path.insert(0, os.path.dirname(__file__))
from prompts.style_prompt import get_style_prompt, Persona, PERSONA_GUIDES

# ── API 설정 ──────────────────────────────────────────────────────────────────
API_URLS = {
    "Graph RAG":            "http://localhost:8002/chat",
    "Graph RAG + Self RAG": "http://localhost:8001/chat",
}

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="국립중앙박물관 AI 도슨트",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

* { font-family: 'Noto Sans KR', sans-serif; }

/* 전체 배경 */
.stApp { background-color: #f8f5f0; }

/* 사이드바 */
[data-testid="stSidebar"] {
    background-color: #1a2744;
}
[data-testid="stSidebar"] * { color: #e8dcc8 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #c9a84c !important; }

/* 헤더 숨기기 */
[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

/* 채팅 입력창 */
[data-testid="stChatInput"] textarea {
    border-radius: 24px !important;
    border: 2px solid #c9a84c !important;
    background-color: #ffffff !important;
    font-size: 15px !important;
    padding: 12px 20px !important;
}
[data-testid="stChatInput"] textarea:focus {
    box-shadow: 0 0 0 3px rgba(201,168,76,0.2) !important;
}

/* 어시스턴트 메시지 */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background-color: #ffffff;
    border-radius: 16px;
    padding: 4px 12px;
    border-left: 4px solid #c9a84c;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-bottom: 12px;
}

/* 유저 메시지 */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background-color: #eef2fb;
    border-radius: 16px;
    padding: 4px 12px;
    margin-bottom: 12px;
}

/* 유물 카드 */
.artifact-card {
    background: #ffffff;
    border: 1px solid #e0d8c8;
    border-radius: 12px;
    padding: 14px 18px;
    margin: 8px 0;
    border-left: 4px solid #1a2744;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}
.artifact-card h4 {
    color: #1a2744;
    margin: 0 0 8px 0;
    font-size: 15px;
    font-weight: 700;
}
.artifact-tag {
    display: inline-block;
    background: #f0ece3;
    color: #5a4a2a;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 12px;
    margin: 2px 3px 2px 0;
    border: 1px solid #d4c9a8;
}
.artifact-tag.era   { background: #e8f0fb; color: #1a2744; border-color: #b8c8e8; }
.artifact-tag.mat   { background: #fdf3e3; color: #7a5a20; border-color: #e8d4a0; }
.artifact-tag.loc   { background: #edf7ed; color: #2a5a2a; border-color: #a8d4a8; }

/* 추천 질문 버튼 */
.stButton button {
    background-color: rgba(201,168,76,0.15) !important;
    color: #e8dcc8 !important;
    border: 1px solid rgba(201,168,76,0.4) !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    padding: 6px 12px !important;
    text-align: left !important;
    width: 100% !important;
    white-space: normal !important;
    height: auto !important;
    transition: all 0.2s !important;
}
.stButton button:hover {
    background-color: rgba(201,168,76,0.35) !important;
    border-color: #c9a84c !important;
}

/* 타이틀 영역 */
.main-title {
    text-align: center;
    padding: 20px 0 8px 0;
    color: #1a2744;
}
.main-title h1 { font-size: 26px; font-weight: 700; margin-bottom: 4px; }
.main-title p  { font-size: 14px; color: #7a6a50; margin: 0; }

.divider {
    border: none;
    border-top: 1px solid #e0d8c8;
    margin: 12px 0;
}
</style>
""", unsafe_allow_html=True)


# ── 세션 초기화 ───────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "persona" not in st.session_state:
    st.session_state.persona = Persona.BEGINNER
if "rag_mode" not in st.session_state:
    st.session_state.rag_mode = "Graph RAG"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🏛️ AI 도슨트")
    st.markdown("**국립중앙박물관** 유물 안내 서비스")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── 페르소나 선택 ──────────────────────────────────────────────────────
    st.markdown("### 👤 관람객 유형")
    persona_labels = {
        Persona.CHILD:    "🧒 어린이",
        Persona.BEGINNER: "🙂 초보",
        Persona.EXPERT:   "🎓 역사 전문가",
    }
    persona_descriptions = {
        Persona.CHILD:    "쉬운 말로 재미있게!",
        Persona.BEGINNER: "친절하게 기본 설명",
        Persona.EXPERT:   "깊이 있는 학술 정보",
    }

    selected_label = st.radio(
        label="유형 선택",
        options=list(persona_labels.values()),
        index=list(persona_labels.keys()).index(st.session_state.persona),
        label_visibility="collapsed",
    )
    # label → Persona 역변환
    selected_persona = next(p for p, l in persona_labels.items() if l == selected_label)
    if selected_persona != st.session_state.persona:
        st.session_state.persona = selected_persona

    st.caption(persona_descriptions[st.session_state.persona])
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── RAG 모드 선택 ──────────────────────────────────────────────────────
    st.markdown("### ⚙️ RAG 모드")
    rag_mode = st.radio(
        label="모드 선택",
        options=["Graph RAG", "Graph RAG + Self RAG"],
        index=["Graph RAG", "Graph RAG + Self RAG"].index(st.session_state.rag_mode),
        label_visibility="collapsed",
    )
    if rag_mode != st.session_state.rag_mode:
        st.session_state.rag_mode = rag_mode
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()

    mode_desc = {
        "Graph RAG":            "그래프 + 벡터 검색 기반 답변",
        "Graph RAG + Self RAG": "Self-RAG로 환각 검증 포함",
    }
    st.caption(mode_desc[st.session_state.rag_mode])
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown("### 📊 DB 현황")
    st.markdown("""
    | 항목 | 수량 |
    |------|------|
    | 유물 | 2,560개 |
    | 시대 | 72종 |
    | 재질 | 60종 |
    | 분류 | 373종 |
    """)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    if st.button("🗑️ 대화 초기화", key="clear"):
        st.session_state.messages = []
        st.rerun()


# ── 메인 영역 ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-title">
    <h1>🏛️ 국립중앙박물관 AI 도슨트</h1>
    <p>유물에 대해 무엇이든 물어보세요</p>
</div>
<hr class="divider">
""", unsafe_allow_html=True)


# 유물 카드 렌더링 함수
def render_artifact_card(artifact: dict, rank: int):
    graph = artifact.get("graph", {})
    tags_era = "".join([f'<span class="artifact-tag era">{v}</span>' for v in graph.get("시대", [])])
    tags_mat = "".join([f'<span class="artifact-tag mat">{v}</span>' for v in graph.get("재질", [])[:3]])
    tags_loc = "".join([f'<span class="artifact-tag loc">{v}</span>' for v in graph.get("전시위치", [])])
    tags_cat = "".join([f'<span class="artifact-tag">{v}</span>' for v in graph.get("분류", [])[:2]])

    st.markdown(f"""
    <div class="artifact-card">
        <h4>#{rank} {artifact.get('title', '')}
            <span style="font-size:12px; color:#999; font-weight:400; margin-left:8px;">
                {artifact.get('소장품번호', '')}
            </span>
        </h4>
        {tags_era}{tags_mat}{tags_loc}{tags_cat}
    </div>
    """, unsafe_allow_html=True)


# 메시지 없을 때 환영 화면
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #9a8a70;">
        <div style="font-size: 56px; margin-bottom: 16px;">🏺</div>
        <div style="font-size: 18px; font-weight: 500; color: #3a3020; margin-bottom: 8px;">
            안녕하세요! 국립중앙박물관 AI 도슨트입니다.
        </div>
        <div style="font-size: 14px; line-height: 1.8;">
            유물의 역사, 시대적 배경, 제작 방식 등<br>
            궁금한 것을 자유롭게 질문해보세요.<br><br>
        </div>
    </div>
    """, unsafe_allow_html=True)


# 채팅 히스토리 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🏛️" if msg["role"] == "assistant" else "👤"):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "sources" in msg:
            with st.expander(f"📚 참고 유물 {len(msg['sources'])}건", expanded=False):
                for art in msg["sources"]:
                    render_artifact_card(art, art.get("rank", 1))


# ── 입력 처리 ─────────────────────────────────────────────────────────────────

user_input = st.chat_input("유물에 대해 무엇이든 물어보세요...")


@st.cache_resource
def get_neo4j_driver():
    """Neo4j 드라이버 (앱 전체에서 한 번만 생성)"""
    from neo4j import GraphDatabase
    return GraphDatabase.driver(
        "neo4j+ssc://9bc6beed.databases.neo4j.io",
        auth=("9bc6beed", "UHtFuBP-iUd4gV1KEd4xGxRFO1I6trRfgxXBYwWuErg"),
    )


def search_graph(message: str, limit: int = 5) -> list[dict]:
    """
    Neo4j에서 키워드 기반으로 유물 검색.
    질문에서 주요 키워드를 추출해 title / 시대 / 재질 / 분류 노드를 탐색.
    """
    driver = get_neo4j_driver()

    query = """
        MATCH (u:유물)
        WHERE u.title           CONTAINS $kw
           OR u.다른명칭         CONTAINS $kw
           OR EXISTS {
               MATCH (u)-[:속한시대]->(s:시대) WHERE s.name CONTAINS $kw
           }
           OR EXISTS {
               MATCH (u)-[:재질로만들어짐]->(m:재질) WHERE m.name CONTAINS $kw
           }
           OR EXISTS {
               MATCH (u)-[:분류됨]->(c:분류) WHERE c.name CONTAINS $kw
           }
           OR EXISTS {
               MATCH (u)-[:국적]->(n:국적) WHERE n.name CONTAINS $kw
           }
        WITH u LIMIT $limit

        OPTIONAL MATCH (u)-[:국적]->(g:국적)
        OPTIONAL MATCH (u)-[:속한시대]->(s:시대)
        OPTIONAL MATCH (u)-[:재질로만들어짐]->(m:재질)
        OPTIONAL MATCH (u)-[:분류됨]->(c:분류)
        OPTIONAL MATCH (u)-[:만든작가]->(a:작가)
        OPTIONAL MATCH (u)-[:전시위치]->(e:전시위치)

        RETURN u.title AS title,
               u.소장품번호 AS 소장품번호,
               u.전시명칭 AS 전시명칭,
               collect(DISTINCT g.name) AS 국적,
               collect(DISTINCT s.name) AS 시대,
               collect(DISTINCT m.name) AS 재질,
               collect(DISTINCT c.name) AS 분류,
               collect(DISTINCT a.name) AS 작가,
               collect(DISTINCT e.name) AS 전시위치
    """

    # 질문에서 핵심 키워드 추출 (2글자 이상 단어)
    import re
    words = re.findall(r'[가-힣a-zA-Z]{2,}', message)

    results = []
    seen = set()

    with driver.session() as session:
        for word in words:
            rows = session.run(query, kw=word, limit=limit).data()
            for row in rows:
                key = row["소장품번호"]
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "rank":   len(results) + 1,
                        "title":  row["title"],
                        "소장품번호": row["소장품번호"],
                        "전시명칭":  row["전시명칭"] or "",
                        "graph": {
                            "국적":    row["국적"],
                            "시대":    row["시대"],
                            "재질":    row["재질"],
                            "분류":    row["분류"][:3],  # 최대 3개
                            "작가":    row["작가"],
                            "전시위치": row["전시위치"],
                        },
                    })
            if len(results) >= limit:
                break

    return results[:limit]


PERSONA_EMOJI = {
    Persona.CHILD:    "🧒",
    Persona.BEGINNER: "🙂",
    Persona.EXPERT:   "🎓",
}


def build_answer(message: str, sources: list[dict], persona: Persona) -> str:
    """검색 결과를 바탕으로 텍스트 응답 생성 (LLM 없는 버전)"""
    emoji = PERSONA_EMOJI.get(persona, "🙂")

    if not sources:
        if persona == Persona.CHILD:
            return f"앗, **'{message}'** 관련 유물을 못 찾았어요! \n\n다른 말로 다시 물어봐요! (예: 청자, 금동불상, 조선 그림)"
        elif persona == Persona.EXPERT:
            return f"**'{message}'** 에 해당하는 유물이 데이터베이스에 존재하지 않습니다.\n\n검색어를 변경하거나 관련 시대·재질명으로 재시도하십시오."
        else:
            return f"**'{message}'** 관련 유물을 찾지 못했어요.\n\n다른 키워드로 검색해보세요. (예: 청자, 조선, 금동, 불상 등)"

    if persona == Persona.CHILD:
        lines = [f"우와! **'{message}'** 랑 관련된 유물을 {len(sources)}개나 찾았어요! {emoji}\n"]
        for r in sources:
            g = r["graph"]
            era  = ', '.join(g['시대']) if g['시대'] else "옛날"
            mat  = ', '.join(g['재질'][:1]) if g['재질'] else ""
            loc  = ', '.join(g['전시위치']) if g['전시위치'] else ""
            lines.append(f"**{r['rank']}. {r['title']}**\n   ➡ {era}에 만들어진 {mat} 유물이에요! {f'({loc}에서 볼 수 있어요)' if loc else ''}")

    elif persona == Persona.EXPERT:
        lines = [f"**'{message}'** 관련 유물 **{len(sources)}건** 검색 결과입니다. {emoji}\n"]
        for r in sources:
            g = r["graph"]
            parts = []
            if g['국적']:   parts.append(f"국적: {', '.join(g['국적'])}")
            if g['시대']:   parts.append(f"시대: {', '.join(g['시대'])}")
            if g['재질']:   parts.append(f"재질: {', '.join(g['재질'])}")
            if g['분류']:   parts.append(f"분류: {' > '.join(g['분류'])}")
            if g['작가']:   parts.append(f"작가: {', '.join(g['작가'])}")
            if g['전시위치']: parts.append(f"전시위치: {', '.join(g['전시위치'])}")
            lines.append(f"**{r['rank']}. {r['title']}** `{r['소장품번호']}`\n   " + " | ".join(parts))

    else:  # BEGINNER
        lines = [f"**'{message}'** 관련 유물 **{len(sources)}건**을 찾았어요. {emoji}\n"]
        for r in sources:
            g = r["graph"]
            info_parts = []
            if g["시대"]:    info_parts.append(f"시대: {', '.join(g['시대'])}")
            if g["재질"]:    info_parts.append(f"재질: {', '.join(g['재질'][:2])}")
            if g["전시위치"]: info_parts.append(f"전시: {', '.join(g['전시위치'])}")
            info_str = " | ".join(info_parts) if info_parts else "정보 없음"
            lines.append(f"**{r['rank']}. {r['title']}** ({r['소장품번호']})\n   _{info_str}_")

    lines.append("\n> 아래 카드에서 상세 정보를 확인하세요.")
    return "\n\n".join(lines)


def get_response(message: str, persona: Persona):
    """선택된 RAG 모드 API 호출 → 응답 반환"""
    url = API_URLS[st.session_state.rag_mode]
    try:
        resp = requests.post(
            url,
            json={
                "query":        message,
                "chat_history": st.session_state.chat_history,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data    = resp.json()
        answer  = data.get("answer", "답변을 생성하지 못했습니다.")
        sources = data.get("sources", [])
    except requests.exceptions.ConnectionError:
        mode = st.session_state.rag_mode
        port = 8000 if mode == "Graph RAG" else 8001
        answer  = f"⚠️ API 서버에 연결할 수 없습니다.\n\n`python api_graph_rag.py` 또는 `python api_self_rag.py` 를 먼저 실행해주세요. (포트: {port})"
        sources = []
    except Exception as e:
        answer  = f"⚠️ 오류 발생: {e}"
        sources = []
    return answer, sources


if user_input:
    # 유저 메시지 추가
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # 어시스턴트 응답
    with st.chat_message("assistant", avatar="🏛️"):
        with st.spinner("유물 정보를 검색하는 중..."):
            answer, sources = get_response(user_input, st.session_state.persona)

        st.markdown(answer)
        with st.expander(f"📚 참고 유물 {len(sources)}건", expanded=True):
            for art in sources:
                render_artifact_card(art, art.get("rank", 1))

    # 히스토리 저장
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": sources,
    })
    st.session_state.chat_history.append({"role": "user",      "content": user_input})
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
