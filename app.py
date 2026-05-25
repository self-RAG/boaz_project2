from graph.neo4j_client import Neo4jClient
from vector_db.vector_retriever import VectorRetriever
from llm.llm_generator import LLMGenerator

class GraphRetriever:

    def __init__(self, neo4j_client):
        self.neo4j = neo4j_client

    def retrieve_subgraph(self, keyword):

        query = """
        MATCH (u:유물)-[r]-(n)
        WHERE u.title CONTAINS $keyword
           OR u.전시명칭 CONTAINS $keyword
           OR u.다른명칭 CONTAINS $keyword
           OR u.소장품번호 CONTAINS $keyword

        RETURN u, r, n
        LIMIT 20
        """

        return self.neo4j.run_query(
            query,
            {"keyword": keyword}
        )


neo4j_client = Neo4jClient()

retriever = GraphRetriever(neo4j_client)

vector_retriever = VectorRetriever()

llm = LLMGenerator()


# 사용자 질문
query = input("질문: ")

query = query.replace("알려줘", "").strip()


# ---------------- GRAPH RETRIEVAL ----------------

graph_result = retriever.retrieve_subgraph(query)

artifact = graph_result[0]["u"]

graph_context = ""

graph_context += f"유물명: {artifact['title']}\n"
graph_context += f"소장품번호: {artifact['소장품번호']}\n"

if "전시명칭" in artifact:
    graph_context += (
        f"전시명칭: "
        f"{artifact['전시명칭']}\n"
    )

if "다른명칭" in artifact:
    graph_context += (
        f"다른명칭: "
        f"{artifact['다른명칭']}\n"
    )

graph_context += "\n"

mapping = {
    "재질로만들어짐": "재질",
    "분류됨": "분류"
}

for item in graph_result:

    relation = item["r"][1]

    if relation in mapping:
        relation = mapping[relation]

    node_name = item["n"]["name"]

    graph_context += (
        f"{relation}: "
        f"{node_name}\n"
    )


# ---------------- VECTOR RETRIEVAL ----------------

vector_result = vector_retriever.search(query)

vector_context = ""

metas = vector_result["metadatas"][0]

for meta in metas:

    vector_context += (
        f"설명문: "
        f"{meta['description']}\n\n"
    )


# ---------------- CONTEXT MERGE ----------------

final_context = ""

final_context += "[Graph 정보]\n"
final_context += graph_context

final_context += "\n[설명문 정보]\n"
final_context += vector_context


print(final_context)


# ---------------- LLM GENERATION ----------------

answer = llm.generate(
    query,
    final_context
)

print("\n===== 최종 답변 =====\n")

print(answer)