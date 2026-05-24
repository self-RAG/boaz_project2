from graph.neo4j_client import Neo4jClient
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
llm = LLMGenerator()

query = input("질문: ")

query = query.replace("알려줘", "").strip()

result = retriever.retrieve_subgraph(query)

artifact = result[0]["u"]

context = ""

context += f"유물명: {artifact['title']}\n"
context += f"소장품번호: {artifact['소장품번호']}\n"

if "전시명칭" in artifact:
    context += f"전시명칭: {artifact['전시명칭']}\n"

if "다른명칭" in artifact:
    context += f"다른명칭: {artifact['다른명칭']}\n"

context += "\n"

mapping = {
    "재질로만들어짐": "재질",
    "분류됨": "분류"
}

for item in result:

    relation = item["r"][1]

    if relation in mapping:
        relation = mapping[relation]

    node_name = item["n"]["name"]

    context += f"{relation}: {node_name}\n"

answer = llm.generate(query, context)

print("\n===== 최종 답변 =====\n")
print(answer)