from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from docx import Document
from PyPDF2 import PdfReader

import web.app as app_module
from web.services.workspace import WorkspaceStore


def make_client(root: Path) -> tuple[TestClient, WorkspaceStore]:
    store = WorkspaceStore(root)
    previous = app_module.STORE
    app_module.STORE = store
    client = TestClient(app_module.app)
    client._previous_store = previous  # type: ignore[attr-defined]
    return client, store


def restore_store(client: TestClient) -> None:
    previous = getattr(client, "_previous_store", None)
    if previous is not None:
        app_module.STORE = previous


def test_firm_profile_staff_directory_and_authority_stamp_persist():
    with tempfile.TemporaryDirectory() as td:
        client, store = make_client(Path(td))
        try:
            firm = client.post(
                "/firm-profile",
                json={
                    "id": "acme-litigation",
                    "name": "Acme Litigation Group",
                    "office_name": "Downtown Office",
                    "office_address": "100 Main St, Suite 200",
                    "phone": "(555) 010-0100",
                    "email": "firm@example.com",
                    "website": "https://example.com",
                    "confidentiality_notice": "CONFIDENTIAL AND ATTORNEY WORK PRODUCT.",
                    "default_footer": "Acme Litigation Group",
                },
            )
            assert firm.status_code == 200
            assert firm.json()["firm_profile"]["name"] == "Acme Litigation Group"

            attorney = client.post(
                "/staff-directory",
                json={
                    "full_name": "Jordan Lee",
                    "role": "attorney",
                    "title": "Partner",
                    "bar_number": "CA12345",
                    "office": "Downtown Office",
                    "email": "jordan@example.com",
                    "phone": "(555) 010-0101",
                    "initials": "JL",
                    "signature_block": "Jordan Lee\nPartner",
                },
            ).json()["staff_member"]
            reviewer = client.post(
                "/staff-directory",
                json={
                    "full_name": "Casey Morgan",
                    "role": "reviewer",
                    "title": "Senior Reviewer",
                    "office": "Downtown Office",
                    "email": "casey@example.com",
                    "initials": "CM",
                    "signature_block": "Casey Morgan\nSenior Reviewer",
                },
            ).json()["staff_member"]
            paralegal = client.post(
                "/staff-directory",
                json={
                    "full_name": "Taylor Quinn",
                    "role": "paralegal",
                    "title": "Paralegal",
                    "office": "Downtown Office",
                    "email": "taylor@example.com",
                    "initials": "TQ",
                    "signature_block": "Taylor Quinn\nParalegal",
                },
            ).json()["staff_member"]

            matter = client.post(
                "/matter",
                json={
                    "case_id": "acme-v-opponent",
                    "title": "Acme v. Opponent",
                    "court_profile_id": "federal_district_civil",
                    "firm_profile_id": "acme-litigation",
                    "prepared_by_id": paralegal["id"],
                    "reviewed_by_id": reviewer["id"],
                    "approved_by_id": attorney["id"],
                    "signed_by_id": attorney["id"],
                    "filed_by_id": paralegal["id"],
                },
            )
            assert matter.status_code == 200

            authority = client.get("/authority", params={"case_id": "acme-v-opponent"})
            assert authority.status_code == 200
            payload = authority.json()
            assert payload["firm_profile"]["name"] == "Acme Litigation Group"
            assert payload["valid"] is True
            assert payload["assignments"]["approved_by"]["full_name"] == "Jordan Lee"
            assert "Prepared by: Taylor Quinn" in payload["responsibility_stamp"]
            assert "Reviewed by: Casey Morgan" in payload["responsibility_stamp"]
        finally:
            restore_store(client)


def test_firm_branded_docx_and_pdf_include_stamp():
    with tempfile.TemporaryDirectory() as td:
        client, store = make_client(Path(td))
        try:
            client.post(
                "/firm-profile",
                json={
                    "id": "acme-litigation",
                    "name": "Acme Litigation Group",
                    "office_name": "Downtown Office",
                    "confidentiality_notice": "CONFIDENTIAL AND ATTORNEY WORK PRODUCT.",
                },
            )
            attorney = client.post("/staff-directory", json={"full_name": "Jordan Lee", "role": "attorney"}).json()["staff_member"]
            reviewer = client.post("/staff-directory", json={"full_name": "Casey Morgan", "role": "reviewer"}).json()["staff_member"]
            client.post(
                "/matter",
                json={
                    "case_id": "acme-v-opponent",
                    "title": "Acme v. Opponent",
                    "court_profile_id": "federal_district_civil",
                    "firm_profile_id": "acme-litigation",
                    "prepared_by_id": attorney["id"],
                    "reviewed_by_id": reviewer["id"],
                    "approved_by_id": attorney["id"],
                    "signed_by_id": attorney["id"],
                    "filed_by_id": attorney["id"],
                },
            )
            client.post("/ingest", json={"case_id": "acme-v-opponent", "case_title": "Acme v. Opponent", "text": "On 2013-03-15 Sean James cited CCR 4331 in a notice."})

            docx_resp = client.post(
                "/export_packet_docx",
                json={"case_id": "acme-v-opponent", "template_id": "case_theory_memo", "query": "Sean James", "format": "docx", "redact": False},
            )
            assert docx_resp.status_code == 200
            docx = Document(BytesIO(docx_resp.content))
            docx_text = "\n".join(p.text for p in docx.paragraphs)
            assert "Acme Litigation Group" in docx_text
            assert "Responsibility Stamp" in docx_text
            assert "Prepared by: Jordan Lee" in docx_text

            pdf_resp = client.post(
                "/export_packet_pdf",
                json={"case_id": "acme-v-opponent", "template_id": "case_theory_memo", "query": "Sean James", "format": "pdf", "redact": False},
            )
            assert pdf_resp.status_code == 200
            pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_resp.content)).pages)
            assert "Acme Litigation Group" in pdf_text
            assert "Prepared by: Jordan Lee" in pdf_text
            assert "CONFIDENTIAL AND ATTORNEY WORK PRODUCT." in pdf_text
        finally:
            restore_store(client)


def test_invalid_responsibility_stamp_blocks_export():
    with tempfile.TemporaryDirectory() as td:
        client, store = make_client(Path(td))
        try:
            attorney = client.post("/staff-directory", json={"full_name": "Jordan Lee", "role": "attorney"}).json()["staff_member"]
            paralegal = client.post("/staff-directory", json={"full_name": "Taylor Quinn", "role": "paralegal"}).json()["staff_member"]
            client.post(
                "/matter",
                json={
                    "case_id": "invalid-stamp",
                    "title": "Invalid Stamp Matter",
                    "approved_by_id": paralegal["id"],
                    "signed_by_id": attorney["id"],
                },
            )
            response = client.post(
                "/export_packet",
                json={"case_id": "invalid-stamp", "template_id": "case_theory_memo", "query": "test", "format": "markdown", "redact": False},
            )
            assert response.status_code == 409
            assert "Document authority assignments are invalid" in response.text
        finally:
            restore_store(client)
