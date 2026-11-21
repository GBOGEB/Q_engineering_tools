#!/usr/bin/env python3
"""Bind private review page text to exact on-disk PDF bytes and source windows.

Only a candidate Library/native PDF is proven here; proof is not the W43 archive,
contract precedence, or engineering/owner approval. The receipt stores digests
and locators, never supplier source paragraphs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = 'qps.bb.jade.native-pdf-source-binding/1.0'
MARKER = re.compile(r'<PARSED TEXT FOR PAGE:\s*(\d+)\s*/\s*(\d+)>')
SHA256 = re.compile(r'^[0-9a-f]{64}$')


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024*1024):
            h.update(chunk)
    return h.hexdigest()


def normalized_digest(text: str) -> str:
    return hashlib.sha256(re.sub(r'\s+', ' ', text).strip().encode('utf-8')).hexdigest()


def decode_projection(text: str, total_pages: int) -> dict[int, str]:
    if not isinstance(text, str) or not text:
        raise ValueError('nonempty extracted source text required')
    markers = list(MARKER.finditer(text))
    if not markers or text[:markers[0].start()].strip():
        raise ValueError('page markers absent or leading unidentified content')
    pages: dict[int, str] = {}
    for i, mark in enumerate(markers):
        p, t = int(mark.group(1)), int(mark.group(2))
        if t != total_pages or p < 1 or p > total_pages or p in pages:
            raise ValueError('page bounds, denominator or duplicate source page invalid')
        segment = text[mark.end():markers[i+1].start() if i+1 < len(markers) else len(text)]
        pages[p] = segment
    if list(pages) != sorted(pages):
        raise ValueError('out of order projection pages')
    return pages


def _selected(windows: list[list[int]], total_pages: int) -> set[int]:
    if not isinstance(windows, list) or not windows:
        raise ValueError('explicit page review windows required')
    selected: set[int] = set()
    for span in windows:
        if not isinstance(span, list) or len(span)!=2:
            raise ValueError('page window must be a pair')
        a,b=span
        if (any(isinstance(x,bool) or not isinstance(x,int) for x in span)
                or not 1 <= a <= b <= total_pages):
            raise ValueError('page window bounds invalid')
        candidate = set(range(a,b+1))
        if selected & candidate:
            raise ValueError('duplicate / overlapping page windows')
        selected.update(candidate)
    return selected


def bind_source(pdf_path: Path, text_projection: str, *, expected_sha256: str,
                windows: list[list[int]]) -> dict[str, Any]:
    if not isinstance(expected_sha256,str) or not SHA256.fullmatch(expected_sha256):
        raise ValueError('expected native PDF SHA256 must be 64 lowercase hex digits')
    src=Path(pdf_path)
    if not src.is_file() or not src.name.lower().endswith('.pdf'):
        raise ValueError('native PDF file path required')
    snapshot=src.read_bytes()
    observed=hashlib.sha256(snapshot).hexdigest()
    if observed != expected_sha256:
        raise ValueError('original PDF SHA256 mismatch: stop, do not produce receipt')
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError('PyMuPDF required for independent native source binding') from exc
    with fitz.open(stream=snapshot,filetype='pdf') as doc:
        if doc.needs_pass or doc.is_repaired:
            raise ValueError('password protected or repaired PDF requires independent QA')
        selected=_selected(windows, len(doc))
        pages=decode_projection(text_projection,len(doc))
        if set(pages) != selected:
            raise ValueError('projection incomplete or contains undeclared review pages')
        results=[]
        for p in sorted(selected):
            actual=doc[p-1].get_text('text')
            expected=pages[p]
            a,b=normalized_digest(actual),normalized_digest(expected)
            if a!=b:
                raise ValueError(f'page {p} source text differs from candidate PDF')
            results.append({'page_1based':p,'normalized_text_sha256':a,'text_projection_match':True})
            results[-1].update({
                'raw_native_text_sha256': hashlib.sha256(actual.encode('utf-8')).hexdigest(),
                'raw_projection_text_sha256': hashlib.sha256(expected.encode('utf-8')).hexdigest(),
                'normalization_method': 'python-re-whitespace-collapse-strip/1',
                'extractor': 'PyMuPDF', 'extractor_version': fitz.VersionBind,
                'extractor_flags': fitz.TEXTFLAGS_TEXT,
            })
        page_count=len(doc)
    return {'schema':SCHEMA,'source_role':'LIBRARY_COMPILED_APPLICANT_CANDIDATE',
            'source_binary_sha256':observed,'source_binary_sha256_verified':True,
            'source_read_mode':'IMMUTABLE_BYTES_SNAPSHOT',
            'native_pdf_pages':page_count,
            'selected_windows':windows,'selected_page_count':len(results),
            'page_projection_parity':'PASS_EXACT_NORMALIZED_TEXT_PER_PAGE',
            'page_receipts':results,
            'w43_original_archive_sha256_verified':False,
            'supplier_revision_authority':'UNVERIFIED',
            'native_binary_visual_page_QA':'DEFERRED',
            'owner_review_disposition':'AWAIT_OWNER',
            'engineering_acceptance':'WITHHELD','formal_credit_delta':0}


def bind_identifier_representations(pdf_path: Path, *, expected_sha256: str,
                                    page_1based: int, expected_page_text_sha256: str,
                                    displayed_id: str, encoded_id: str) -> dict[str, Any]:
    """Prove one clipped/synthetic-space spelling against source character geometry.

    This deliberately narrow adapter never rewrites the default extraction or
    creates an alias. Only a unique, complete, horizontal identifier span is
    supported. Clipping-disabled text is diagnostic content, not visual truth.
    Both spellings, explicit extraction flags and the original page digest are
    retained so a later renderer/parser can replay the same observation.
    """
    import fitz
    for value in (expected_sha256, expected_page_text_sha256):
        if not isinstance(value, str) or not SHA256.fullmatch(value):
            raise ValueError('source and raw page SHA256 required')
    src = Path(pdf_path)
    if not src.is_file() or src.suffix.lower() != '.pdf':
        raise ValueError('native PDF file path required')
    snapshot = src.read_bytes()
    if hashlib.sha256(snapshot).hexdigest() != expected_sha256:
        raise ValueError('original PDF SHA256 mismatch')
    if isinstance(page_1based, bool) or not isinstance(page_1based, int):
        raise ValueError('physical page must be an integer')
    if (not all(isinstance(x, str) and 0 < len(x) <= 256 for x in (displayed_id, encoded_id))
            or len(displayed_id) != len(encoded_id) or displayed_id == encoded_id):
        raise ValueError('two distinct, equal-length identifier forms required')

    def exact_spans(page, flags, target):
        return [span for block in page.get_text('rawdict', flags=flags)['blocks']
                for line in block.get('lines', []) if tuple(line['dir']) == (1.0, 0.0)
                for span in line['spans']
                if ''.join(c['c'] for c in span['chars']) == target]

    with fitz.open(stream=snapshot, filetype='pdf') as doc:
        if doc.needs_pass or doc.is_repaired or not 1 <= page_1based <= len(doc):
            raise ValueError('unsupported PDF or physical page')
        page = doc[page_1based - 1]
        page_sha = hashlib.sha256(page.get_text('text').encode('utf-8')).hexdigest()
        if page_sha != expected_page_text_sha256:
            raise ValueError('raw page text SHA256 mismatch')
        default_flags = fitz.TEXTFLAGS_RAWDICT
        diagnostic_flags = default_flags & ~fitz.TEXT_MEDIABOX_CLIP
        clipped = exact_spans(page, default_flags, displayed_id)
        unclipped = exact_spans(page, diagnostic_flags, encoded_id)
        traces = [s for s in page.get_texttrace()
                  if ''.join(chr(c[0]) for c in s['chars']) == encoded_id]
        if len(clipped) != 1 or len(unclipped) != 1 or len(traces) != 1:
            raise ValueError('identifier span absent, split or ambiguous')
        a, b, trace = clipped[0], unclipped[0], traces[0]
        if trace['type'] not in (0, 1) or trace['opacity'] <= 0:
            raise ValueError('nonpainting text trace unsupported')
        if not (len(a['chars']) == len(b['chars']) == len(trace['chars']) == len(encoded_id)):
            raise ValueError('character count differs')
        changes = []
        for i, (ca, cb, ct) in enumerate(zip(a['chars'], b['chars'], trace['chars'])):
            # Match coordinates character by character, not just the whole line.
            if any(abs(cb['origin'][j] - ct[2][j]) > 0.2 for j in (0, 1)):
                raise ValueError('trace geometry differs')
            if ca['c'] == cb['c']:
                if any(abs(ca['origin'][j] - cb['origin'][j]) > 0.2 for j in (0, 1)):
                    raise ValueError('default extraction geometry differs')
            else:
                if not (ca['c'] == ' ' and ca.get('synthetic') is True and cb['c'] == '_'
                        and not cb.get('synthetic', False) and ct[0] == ord('_')):
                    raise ValueError('unsupported representation difference')
                if abs(ca['origin'][1] - cb['origin'][1]) > 0.2 or not (
                        ca['bbox'][0] < cb['bbox'][2] and cb['bbox'][0] < ca['bbox'][2]):
                    raise ValueError('synthetic space does not overlap encoded character')
                changes.append({'character_index_0based': i,
                                'default_character': ca['c'], 'default_synthetic': True,
                                'encoded_character': cb['c'], 'glyph_id': ct[1],
                                'encoded_origin_pt': list(cb['origin']),
                                'encoded_bbox_pt': list(cb['bbox'])})
        if not changes:
            raise ValueError('no clipping-sensitive characters found')
        return {
            'schema': 'qps.pdf.identifier-representation-binding/1.0',
            'source_binary_sha256': expected_sha256, 'page_1based': page_1based,
            'source_read_mode': 'IMMUTABLE_BYTES_SNAPSHOT',
            'raw_native_page_text_sha256': page_sha,
            'displayed_id_verbatim': displayed_id, 'encoded_id_verbatim': encoded_id,
            'default_rawdict_flags': default_flags, 'diagnostic_rawdict_flags': diagnostic_flags,
            'extractor': 'PyMuPDF', 'extractor_version': fitz.VersionBind,
            'span_bbox_pt': list(a['bbox']), 'trace_sequence_number': trace['seqno'],
            'characters': changes,
            'classification': 'CLIP_SENSITIVE_UNDERSCORE_TO_SYNTHETIC_SPACE',
            'scope': 'SOURCE_HASH_PHYSICAL_PAGE_RAW_PAGE_DIGEST_AND_CHARACTER_GEOMETRY',
            'default_text_modified': False, 'global_alias_created': False,
            'visual_spelling_authority': 'NOT_ASSERTED_BY_TEXT_TRACE',
            'engineering_acceptance': 'WITHHELD', 'formal_credit_delta': 0,
        }


def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pdf',type=Path,required=True)
    ap.add_argument('--projection',type=Path,required=True)
    ap.add_argument('--expected-sha256',required=True)
    ap.add_argument('--window',action='append',required=True,help='START-END in 1-based PDF page numbers')
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args(argv)
    windows=[]
    for spec in args.window:
        m=re.fullmatch(r'(\d+)-(\d+)',spec)
        if not m:raise ValueError('invalid page span')
        windows.append([int(m.group(1)),int(m.group(2))])
    source,projection,out=args.pdf.resolve(),args.projection.resolve(),args.out.resolve()
    if out in (source,projection) or out.parent in (source.parent,projection.parent) or source.parent in out.parents or projection.parent in out.parents:
        raise SystemExit('Refusing to write review output into native source or projection area')
    receipt=bind_source(source,projection.read_text(encoding='utf-8'),
                        expected_sha256=args.expected_sha256,windows=windows)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':raise SystemExit(main())

