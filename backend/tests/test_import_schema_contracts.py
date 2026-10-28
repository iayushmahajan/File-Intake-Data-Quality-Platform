"""Characterize the public import/correction models before moving them."""

import json

import pytest
from app.schemas.imports import CorrectionRequest, FieldRule, ImportOptions, TemplateWrite
from app.services.validator import REQUIRED_COLUMNS
from pydantic import ValidationError


def test_canonical_field_order():
    fields = [
        "customer_id", "email", "country", "signup_date", "order_amount", "currency",
        "payment_method", "order_status", "product_category", "quantity",
        "discount_percent", "last_login_date",
    ]
    assert REQUIRED_COLUMNS == fields


def test_import_rule_defaults_and_default_options_round_trip():
    assert FieldRule().model_dump() == {
        "required": False, "allowed_values": [], "minimum": None,
        "maximum": None, "date_format": None,
    }
    options = ImportOptions()
    assert options.model_dump() == {
        "mapping": {}, "rules": {}, "template_id": None, "template_version": None,
    }
    assert ImportOptions.model_validate_json(options.model_dump_json()) == options


def test_populated_import_and_template_serialization_round_trip():
    mapping = {field: field.replace("_", " ").title() for field in REQUIRED_COLUMNS}
    options = ImportOptions(
        mapping=mapping,
        rules={"order_amount": FieldRule(minimum=0, maximum=100)},
        template_id=1,
        template_version=2,
    )
    expected = {
        "mapping": mapping,
        "rules": {"order_amount": {
            "required": False, "allowed_values": [], "minimum": 0.0,
            "maximum": 100.0, "date_format": None,
        }},
        "template_id": 1,
        "template_version": 2,
    }
    assert json.loads(options.model_dump_json()) == expected
    assert ImportOptions.model_validate_json(options.model_dump_json()) == options
    template = TemplateWrite(name="Partner", options=options)
    assert template.expected_version is None
    assert TemplateWrite.model_validate_json(template.model_dump_json()) == template


@pytest.mark.parametrize("values", [
    {"template_id": 1}, {"template_version": 1},
    {"template_id": 0, "template_version": 1},
    {"template_id": 1, "template_version": 0},
])
def test_template_identity_requires_two_positive_values(values):
    with pytest.raises(ValidationError):
        ImportOptions(**values)


@pytest.mark.parametrize("model,body", [
    (FieldRule, {"unexpected": True}),
    (ImportOptions, {"unexpected": True}),
    (ImportOptions, {"rules": {"email": {"unexpected": True}}}),
    (TemplateWrite, {"name": "Partner", "options": {}, "unexpected": True}),
    (CorrectionRequest, {"patches": {2: {"email": "fixed@example.com"}}, "unexpected": True}),
])
def test_unknown_model_fields_are_forbidden(model, body):
    with pytest.raises(ValidationError) as error:
        model.model_validate(body)
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_rule_and_template_accepted_boundaries():
    rule = FieldRule(allowed_values=["x" * 500] * 100, minimum=0, maximum=0)
    assert FieldRule.model_validate_json(rule.model_dump_json()) == rule
    mapping = {field: field for field in REQUIRED_COLUMNS}
    mapping["email"] = "e" * 200
    options = ImportOptions(mapping=mapping, template_id=1, template_version=1)
    for name in ("P", "P" * 80):
        template = TemplateWrite(name=name, options=options, expected_version=1)
        assert TemplateWrite.model_validate_json(template.model_dump_json()) == template


@pytest.mark.parametrize("values", [
    {"allowed_values": ["x"] * 101}, {"allowed_values": ["x" * 501]},
    {"minimum": float("nan")}, {"maximum": float("inf")},
    {"minimum": 2, "maximum": 1},
])
def test_rule_rejected_boundaries(values):
    with pytest.raises(ValidationError):
        FieldRule(**values)


@pytest.mark.parametrize("name,version", [("", 1), ("P" * 81, 1), ("Partner", 0)])
def test_template_rejected_boundaries(name, version):
    with pytest.raises(ValidationError):
        TemplateWrite(name=name, options=ImportOptions(), expected_version=version)


def test_source_column_length_boundary():
    mapping = {field: field for field in REQUIRED_COLUMNS}
    for source in ("", "e" * 201):
        with pytest.raises(ValidationError):
            ImportOptions(mapping={**mapping, "email": source})


def test_correction_row_cell_and_batch_boundaries_round_trip():
    patches = {row: {"email": ""} for row in range(2, 201)}
    patches[2147483647] = {"customer_id": "x" * 10000}
    correction = CorrectionRequest(patches=patches)
    assert len(correction.patches) == 200
    serialized = json.loads(correction.model_dump_json())
    assert serialized == {"patches": {str(row): values for row, values in patches.items()}}
    assert CorrectionRequest.model_validate_json(correction.model_dump_json()) == correction


def test_correction_payload_limit_counts_utf8_bytes():
    # 104 * 10,000 + 8,576 = exactly 1 MiB; each cell is under 10,000 characters.
    patches = {row: {"email": "é" * 5000} for row in range(2, 106)}
    patches[106] = {"email": "é" * 4288}
    correction = CorrectionRequest(patches=patches)
    assert CorrectionRequest.model_validate_json(correction.model_dump_json()) == correction
    patches[106]["email"] += "a"
    with pytest.raises(ValidationError, match="Correction batch exceeds 1 MiB"):
        CorrectionRequest(patches=patches)
