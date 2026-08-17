from app.rag.retriever import RAGRetriever


class RAGService:

    def __init__(self):
        self.retriever = RAGRetriever()

    def get_context(
        self,
        query: str,
        limit: int = 5,
        organization_id=None,
    ):
        results = self.retriever.search(
            query,
            limit=limit,
            organization_id=organization_id,
        )

        if not results:
            return ""

        context = []

        for filename, index, content in results:
            context.append(
                f"File: {filename}\n{content}"
            )

        return "\n\n".join(context)


rag_service = RAGService()
