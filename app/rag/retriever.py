from app import db
from app.models import DocumentChunk, Document


class RAGRetriever:

    def search(
        self,
        query: str,
        limit: int = 5,
        organization_id=None,
    ):
        query = (query or "").strip()

        if not query:
            return []

        search_query = (
            db.session.query(
                Document.filename,
                DocumentChunk.chunk_index,
                DocumentChunk.content,
            )
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
        )

        # Tenant isolation
        if organization_id is not None:
            search_query = search_query.filter(
                Document.organization_id == organization_id
            )

        # Split query into useful words.
        words = [
            w.strip(".,!?;:()[]{}\"'")
            for w in query.split()
            if len(w.strip(".,!?;:()[]{}\"'")) > 2
        ]

        # Try keyword matching first.
        if words:
            conditions = [
                DocumentChunk.content.ilike(f"%{word}%")
                for word in words
            ]

            matched = (
                search_query
                .filter(db.or_(*conditions))
                .limit(limit)
                .all()
            )

            if matched:
                return matched

        # Fallback:
        # If the query does not contain words matching the documents,
        # return chunks from the user's organization.
        return (
            search_query
            .order_by(
                DocumentChunk.document_id.asc(),
                DocumentChunk.chunk_index.asc(),
            )
            .limit(limit)
            .all()
        )

    def count(self, organization_id=None):
        query = (
            db.session.query(DocumentChunk)
            .join(Document)
        )

        if organization_id is not None:
            query = query.filter(
                Document.organization_id == organization_id
            )

        return query.count()
