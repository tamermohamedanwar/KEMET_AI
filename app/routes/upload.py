from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app import csrf, db
from app.models import Document, Conversation

from app.services.file_service import save_file
from app.rag.indexer import RAGIndexer


upload_bp = Blueprint("upload", __name__)


@csrf.exempt
@login_required
@upload_bp.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({
            "success": False,
            "error": "No file"
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "success": False,
            "error": "Empty filename"
        }), 400

    organization_id = getattr(
        current_user,
        "organization_id",
        None
    )

    if not organization_id:
        return jsonify({
            "success": False,
            "error": "No organization assigned"
        }), 403

    result = save_file(file)

    conversation = Conversation(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        title=f"Document: {file.filename}",
    )

    db.session.add(conversation)
    db.session.flush()

    document = Document(
        organization_id=organization_id,
        conversation_id=conversation.id,
        filename=file.filename,
        file_type=(
            file.filename.rsplit(".", 1)[-1].lower()
            if "." in file.filename
            else "unknown"
        ),
        file_size=len(
            result.get("text", "").encode("utf-8")
        ),
    )

    db.session.add(document)
    db.session.commit()

    RAGIndexer().add_document(
        document.id,
        result["chunks"]
    )

    return jsonify({
        "success": True,
        "document_id": document.id,
        "organization_id": organization_id,
        "filename": file.filename,
        "chunks": result["chunks_count"],
        "preview": result["text"][:500]
    })
