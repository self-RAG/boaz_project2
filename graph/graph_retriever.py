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