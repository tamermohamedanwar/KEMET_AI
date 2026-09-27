from app import db
from app.models import Document, DocumentChunk


class RAGIndexer:

    def add_document(
        self,
        document_id: int,
        chunks: list[str],
        organization_id: int,
    ):
        organization_id = int(organization_id or 0)
        if organization_id <= 0:
            raise ValueError("organization_required")

        document = Document.query.filter_by(
            id=document_id,
            organization_id=organization_id,
        ).first()

        if not document:
            raise ValueError("document_not_found_or_tenant_mismatch")

        DocumentChunk.query.filter_by(
            document_id=document.id
        ).delete(
            synchronize_session=False
        )

        for index, content in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=content,
            )

            db.session.add(chunk)

        db.session.commit()

        return {
            "document_id": document.id,
            "organization_id": document.organization_id,
            "chunks": len(chunks),
        }

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
