"""Tests for customer CSV import (HANDOFF.md §14 roadmap)."""

from app.logic.csv_import import parse_customers


def test_parses_rows_with_aliased_headers():
    text = (
        "Customer Name,Company,E-mail,Telephone\n"
        "Acme Machining,Acme Inc,buyer@acme.com,555-0100\n"
        "Globex,Globex LLC,po@globex.com,555-0200\n"
    )
    rows, errors = parse_customers(text)
    assert errors == []
    assert len(rows) == 2
    assert rows[0]["name"] == "Acme Machining"
    assert rows[0]["email"] == "buyer@acme.com"
    assert rows[0]["phone"] == "555-0100"


def test_skips_rows_without_name_and_reports():
    text = "name,email\n,orphan@x.com\nReal Co,real@x.com\n"
    rows, errors = parse_customers(text)
    assert len(rows) == 1
    assert rows[0]["name"] == "Real Co"
    assert any("Line 2" in e for e in errors)


def test_requires_name_column():
    rows, errors = parse_customers("company,email\nAcme,a@b.com\n")
    assert rows == []
    assert "name" in errors[0].lower()


def test_empty_input():
    rows, errors = parse_customers("")
    assert rows == []
    assert errors


def test_ignores_unknown_columns_and_blank_lines():
    text = "name,favorite_color\nAcme,blue\n\nGlobex,red\n"
    rows, errors = parse_customers(text)
    assert [r["name"] for r in rows] == ["Acme", "Globex"]
    assert errors == []


def test_import_route_creates_customers(client):
    resp = client.post(
        "/customers/import",
        data={"csv_text": "name,email\nAcme,a@acme.com\nGlobex,g@globex.com\n"},
    )
    assert resp.status_code == 200
    assert "Imported 2 customers" in resp.text

    from app.db import engine
    from sqlmodel import Session, select
    from app.models import Customer

    with Session(engine) as s:
        names = {c.name for c in s.exec(select(Customer)).all()}
    assert {"Acme", "Globex"} <= names
