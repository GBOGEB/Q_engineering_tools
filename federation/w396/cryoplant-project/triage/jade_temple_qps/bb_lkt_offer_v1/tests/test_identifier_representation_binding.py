"""Synthetic clipped underscores reproduce a real PDF extraction boundary."""
from pathlib import Path
import hashlib
import sys
import fitz
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_pdf_source_binding import bind_identifier_representations, digest_file


def fixture(tmp_path, duplicate=False, clip=True):
    path = tmp_path / 'synthetic.pdf'
    d = fitz.open(); p = d.new_page(width=300, height=200)
    for x in ([20, 150] if duplicate else [20]):
        p.insert_text((x, 40), 'SYN_ID_007', fontsize=12)
    if clip:
        for xref in p.get_contents():
            original = d.xref_stream(xref)
            d.update_stream(xref, b'q\n0 160 300 40 re W n\n' + original + b'\nQ')
    d.new_page().insert_text((20, 40), 'Other page')
    d.save(path); d.close()
    with fitz.open(path) as d:
        page_sha = hashlib.sha256(d[0].get_text().encode('utf-8')).hexdigest()
    args = dict(expected_sha256=digest_file(path), page_1based=1,
                expected_page_text_sha256=page_sha, displayed_id='SYN ID 007', encoded_id='SYN_ID_007')
    return path, args


def test_clipped_identifier_keeps_both_forms_without_alias(tmp_path):
    path, args = fixture(tmp_path)
    receipt = bind_identifier_representations(path, **args)
    assert len(receipt['characters']) == 2
    assert receipt['classification'] == 'CLIP_SENSITIVE_UNDERSCORE_TO_SYNTHETIC_SPACE'
    assert receipt['global_alias_created'] is False
    assert receipt['default_text_modified'] is False
    assert receipt['formal_credit_delta'] == 0


@pytest.mark.parametrize('key,value', [('expected_sha256','0'*64),
    ('expected_page_text_sha256','0'*64), ('page_1based',2), ('page_1based',0),
    ('page_1based',True), ('encoded_id','SYN_ID_008'), ('displayed_id','SYN ID 008')])
def test_wrong_source_page_or_identifier_rejected(tmp_path, key, value):
    path, args = fixture(tmp_path); args[key] = value
    with pytest.raises(ValueError):
        bind_identifier_representations(path, **args)


def test_ambiguous_occurrence_rejected(tmp_path):
    path, args = fixture(tmp_path, duplicate=True)
    with pytest.raises(ValueError, match='ambiguous'):
        bind_identifier_representations(path, **args)


def test_global_substitution_is_not_a_proof(tmp_path):
    path, args = fixture(tmp_path, clip=False)
    with pytest.raises(ValueError, match='absent'):
        bind_identifier_representations(path, **args)
