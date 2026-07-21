"""Integration tests for the bulk CSV draft import endpoint."""

from __future__ import annotations

import io

import pytest


@pytest.fixture
def team_user(db, test_user):
    """Ensure test_user is a member of a team — required for @team_required routes."""
    from socialposter.web.models import Team, TeamMember
    team = Team.query.first()
    if team is None:
        team = Team(
            name="Test Team", slug="test-team", created_by=test_user.id,
        )
        db.session.add(team)
        db.session.flush()
    membership = TeamMember.query.filter_by(
        user_id=test_user.id, team_id=team.id,
    ).first()
    if membership is None:
        db.session.add(TeamMember(
            team_id=team.id, user_id=test_user.id, role="admin",
        ))
        db.session.commit()
    yield test_user
    # Don't tear down team membership — other tests in this module may need it.


SAMPLE_CSV_OK = (
    "name,platforms,text,status\n"
    '"Q1 launch","linkedin,twitter","Big news today!","draft"\n'
    '"Holiday promo","facebook,instagram","Free shipping all weekend.","pending_approval"\n'
)

SAMPLE_CSV_MIXED = (
    "name,platforms,text,status\n"
    '"Good row","linkedin","valid post","draft"\n'
    ',twitter,"missing name",draft\n'
    '"Empty platforms",,,draft\n'
    '"Bad status","linkedin","valid","invented"\n'
    '"Another good","twitter","also valid",\n'
)


def _delete_team_drafts(db, team_id):
    from socialposter.web.models import DraftPost
    DraftPost.query.filter_by(team_id=team_id).delete()
    db.session.commit()


def _team_id_for(user_id):
    from socialposter.utils.team import get_current_team_id
    return get_current_team_id(user_id)


def test_bulk_import_creates_drafts(client, db, team_user):
    team_id = _team_id_for(team_user.id)
    try:
        resp = client.post(
            "/api/drafts/bulk-import",
            data={"file": (io.BytesIO(SAMPLE_CSV_OK.encode("utf-8")), "drafts.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["created_count"] == 2
        assert body["error_count"] == 0
        assert {item["name"] for item in body["created"]} == {
            "Q1 launch",
            "Holiday promo",
        }

        from socialposter.web.models import DraftPost
        rows = DraftPost.query.filter_by(team_id=team_id).all()
        assert len(rows) == 2
        statuses = {r.name: r.status for r in rows}
        assert statuses["Q1 launch"] == "draft"
        assert statuses["Holiday promo"] == "pending_approval"
        platforms = {r.name: r.platforms for r in rows}
        assert platforms["Q1 launch"] == ["linkedin", "twitter"]
    finally:
        _delete_team_drafts(db, team_id)


def test_bulk_import_partial_success_with_errors(client, db, team_user):
    team_id = _team_id_for(team_user.id)
    try:
        resp = client.post(
            "/api/drafts/bulk-import",
            data={"file": (io.BytesIO(SAMPLE_CSV_MIXED.encode("utf-8")), "drafts.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # 2 valid rows: "Good row" and "Another good".
        assert body["created_count"] == 2
        # 3 errors: missing name, empty platforms, bad status.
        assert body["error_count"] == 3
        assert len(body["errors"]) == 3
        # Errors carry the row number (header is row 1, data starts at 2).
        assert all("row" in e and e["row"] >= 2 for e in body["errors"])

        from socialposter.web.models import DraftPost
        names = {r.name for r in DraftPost.query.filter_by(team_id=team_id).all()}
        assert names == {"Good row", "Another good"}
    finally:
        _delete_team_drafts(db, team_id)


def test_bulk_import_rejects_missing_required_column(client, team_user):
    """CSV missing a required column fails fast with a 400."""
    bad = "name,text\nfoo,bar\n"
    resp = client.post(
        "/api/drafts/bulk-import",
        data={"file": (io.BytesIO(bad.encode("utf-8")), "x.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    error = (resp.get_json() or {}).get("error", "")
    assert "platforms" in error


def test_bulk_import_handles_utf8_bom(client, db, team_user):
    """Excel exports often include a UTF-8 BOM; we must decode tolerantly."""
    team_id = _team_id_for(team_user.id)
    # `utf-8-sig` encoding adds a single BOM at the start. Don't prepend
    # another one — that would result in two BOMs and a corrupt header.
    body_bytes = SAMPLE_CSV_OK.encode("utf-8-sig")
    assert body_bytes.startswith(b"\xef\xbb\xbf")  # sanity: one BOM
    try:
        resp = client.post(
            "/api/drafts/bulk-import",
            data={"file": (io.BytesIO(body_bytes), "drafts.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["created_count"] == 2
    finally:
        _delete_team_drafts(db, team_id)


def test_bulk_import_no_file_returns_400(client, team_user):
    resp = client.post(
        "/api/drafts/bulk-import",
        data={},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "no file" in (resp.get_json() or {}).get("error", "").lower()


def test_bulk_import_empty_file_returns_400(client, team_user):
    resp = client.post(
        "/api/drafts/bulk-import",
        data={"file": (io.BytesIO(b""), "empty.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "empty" in (resp.get_json() or {}).get("error", "").lower()
