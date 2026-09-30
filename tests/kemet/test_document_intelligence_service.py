from app.services.document_intelligence_service import document_intelligence_service


def test_olmocr_provider_is_external_and_non_executing(tmp_path, monkeypatch):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"pdf")
    monkeypatch.delenv("KEMET_OLMOCR_EXECUTABLE", raising=False)
    result = document_intelligence_service.plan_pdf(organization_id=7, input_path=str(pdf))
    assert result["success"] is True
    assert result["plan"]["provider_id"] == "olmocr"
    assert result["plan"]["provider_configured"] is False
    assert result["plan"]["governance"]["execution_authority"] is False


def test_pdf_plan_rejects_unsafe_inputs(tmp_path):
    txt = tmp_path / "report.txt"
    txt.write_text("x")
    result = document_intelligence_service.plan_pdf(organization_id=7, input_path=str(txt))
    assert result["status"] == "blocked"
    assert result["error"] == "pdf_required"


def test_structure_aware_chunking_preserves_markdown_boundaries():
    text = "# Title\n\nIntro\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n## Next\n\n\\[x^2\\]"
    chunks = document_intelligence_service.chunk_markdown(text, chunk_size=35, overlap=5)
    assert chunks
    profile = document_intelligence_service.quality_profile(text)
    assert profile["headings"] == 2
    assert profile["tables"] is True
    assert profile["equations"] is True
