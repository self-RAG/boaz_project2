from graph.neo4j_client import Neo4jClient
from graph.graph_retriever import GraphRetriever

from vector_db.vector_retriever import VectorRetriever

from llm.llm_generator import LLMGenerator


# ==================================================
# 객체 생성
# ==================================================

neo4j_client = Neo4jClient()

graph_retriever = GraphRetriever(
    neo4j_client
)

vector_retriever = VectorRetriever()

llm = LLMGenerator()

chat_history = []


# ==================================================
# 채팅 루프
# ==================================================

while True:

    query = input("질문: ")

    if query == "exit":
        break

    # ==================================================
    # history 저장
    # ==================================================

    chat_history.append({
        "role": "user",
        "content": query
    })

    # ==================================================
    # 질문 전처리
    # ==================================================

    artifact_name = (
        query
        .replace("알려줘", "")
        .replace("설명해줘", "")
        .strip()
    )

    # ==================================================
    # GRAPH RETRIEVAL
    # ==================================================

    graph_result = (
        graph_retriever.retrieve_subgraph(
            artifact_name
        )
    )

    graph_context = ""

    if graph_result:

        artifact = graph_result[0]["u"]

        graph_context += (
            f"유물명: "
            f"{artifact.get('title', '')}\n"
        )

        graph_context += (
            f"소장품번호: "
            f"{artifact.get('소장품번호', '')}\n"
        )

        if "전시명칭" in artifact:

            graph_context += (
                f"전시명칭: "
                f"{artifact.get('전시명칭', '')}\n"
            )

        if "다른명칭" in artifact:

            graph_context += (
                f"다른명칭: "
                f"{artifact.get('다른명칭', '')}\n"
            )

        graph_context += "\n"

        for item in graph_result:

            relation = item["r"][1]
            node_name = item["n"]["name"]

            graph_context += (
                f"{relation}: "
                f"{node_name}\n"
            )

    # ==================================================
    # VECTOR RETRIEVAL
    # ==================================================

    vector_result = vector_retriever.search(
        artifact_name
    )

    vector_context = ""

    metas = vector_result["metadatas"][0]

    for meta in metas:

        vector_context += (
            f"설명문: "
            f"{meta['description']}\n\n"
        )

    # ==================================================
    # CONTEXT MERGE
    # ==================================================

    final_context = f"""
[Graph 정보]
{graph_context}

[설명문 정보]
{vector_context}
"""

    print(final_context)

    # ==================================================
    # LLM
    # ==================================================

    answer = llm.generate(
        query,
        final_context,
        chat_history
    )

    print("\n===== 최종 답변 =====\n")

    print(answer)

    # ==================================================
    # 답변 저장
    # ==================================================

    chat_history.append({
        "role": "assistant",
        "content": answer
    })