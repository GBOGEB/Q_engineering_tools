"""Scope guards for source-position evidence and proposed authority instruments.

Source bytes and locators can be verified here. Actor authority, authenticity,
contract effectiveness and owner approval cannot be created by this module.
"""
from __future__ import annotations
import hashlib
import io
import re
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as etree

HEX64 = re.compile(r'^[0-9a-f]{64}$')
W = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
SCOPE_FIELDS = ('namespace','native_id','source_variant_sha256','physical_role','section')

def _xml_policy_text(raw):
    """Decode XML encodings before checking declarations; unknowns fail closed."""
    if raw.startswith((b'\xff\xfe\x00\x00',b'\x00\x00\xfe\xff')):
        encoding='utf-32'
    elif raw.startswith((b'\xff\xfe',b'\xfe\xff')):
        encoding='utf-16'
    elif raw.startswith(b'\x00\x00\x00<'):
        encoding='utf-32-be'
    elif raw.startswith(b'<\x00\x00\x00'):
        encoding='utf-32-le'
    elif raw.startswith(b'\x00<'):
        encoding='utf-16-be'
    elif raw.startswith(b'<\x00'):
        encoding='utf-16-le'
    else:
        encoding='utf-8-sig'
    try:
        return raw.decode(encoding,errors='strict')
    except UnicodeError as e:
        raise ValueError('unsupported or malformed XML encoding') from e

def extract_bound_docx(path, expected_sha256, paragraphs_1based, *, emit_private_text=False):
    """Bind exact body paragraph ordinals, including empty paragraphs, to bytes."""
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if not isinstance(expected_sha256,str) or not HEX64.fullmatch(expected_sha256) or actual != expected_sha256:
        raise ValueError('source byte identity mismatch')
    if not paragraphs_1based or any(type(x) is not int or x < 1 for x in paragraphs_1based):
        raise ValueError('positive paragraph ordinals required')
    if len(set(paragraphs_1based)) != len(paragraphs_1based):
        raise ValueError('duplicate paragraph ordinal')
    # Parse exactly the immutable snapshot whose hash was checked. Reopening the
    # path here would allow a replace/restore race to bind different source text.
    with ZipFile(io.BytesIO(data)) as z:
        if sum(info.filename == 'word/document.xml' for info in z.infolist()) != 1:
            raise ValueError('exactly one word/document.xml entry required')
        raw = z.read('word/document.xml')
        # Check decoded declarations, not raw ASCII bytes. ElementTree does not
        # resolve external entities; this also blocks internal entity expansion.
        markup=_xml_policy_text(raw).upper()
        if '<!DOCTYPE' in markup or '<!ENTITY' in markup:
            raise ValueError('DTD or entity declaration not permitted')
        doc = etree.fromstring(raw)
        paragraphs = doc.findall('.//w:body/w:p',W)
        if max(paragraphs_1based)>len(paragraphs):
            raise ValueError('paragraph outside document')
        records=[]
        revision_tags={
            f"{{{W['w']}}}ins",f"{{{W['w']}}}del",
            f"{{{W['w']}}}moveFrom",f"{{{W['w']}}}moveTo",
            f"{{{W['w']}}}moveFromRangeStart",f"{{{W['w']}}}moveFromRangeEnd",
            f"{{{W['w']}}}moveToRangeStart",f"{{{W['w']}}}moveToRangeEnd",
        }
        for num in paragraphs_1based:
            p=paragraphs[num-1]
            if any(el.tag in revision_tags for el in p.iter()):
                raise ValueError('tracked anchor needs explicit revision view')
            parts=[]
            visible_fail_closed={
                f"{{{W['w']}}}sym",f"{{{W['w']}}}drawing",f"{{{W['w']}}}pict",
                f"{{{W['w']}}}object",f"{{{W['w']}}}ptab",
                f"{{{W['w']}}}footnoteReference",f"{{{W['w']}}}endnoteReference",
                f"{{{W['w']}}}separator",f"{{{W['w']}}}continuationSeparator",
            }
            for el in p.iter():
                if el.tag==f"{{{W['w']}}}t":
                    parts.append(el.text or '')
                elif el.tag==f"{{{W['w']}}}tab":
                    parts.append('\t')
                elif el.tag in (f"{{{W['w']}}}br",f"{{{W['w']}}}cr"):
                    parts.append('\n')
                elif el.tag==f"{{{W['w']}}}noBreakHyphen":
                    parts.append('\u2011')
                elif el.tag==f"{{{W['w']}}}softHyphen":
                    parts.append('\u00ad')
                elif el.tag in visible_fail_closed:
                    raise ValueError('unsupported visible Word control in anchor')
            text=''.join(parts)
            record={'paragraph_1based':num,'locator':f'word/document.xml#/w:document/w:body/w:p[{num}]',
                'text_sha256':hashlib.sha256(text.encode()).hexdigest()}
            if emit_private_text:
                record['text_verbatim']=text
            records.append(record)
        return {'schema':'qps-bound-docx-statements/1','source_sha256':actual,
            'part_sha256':hashlib.sha256(raw).hexdigest(),'paragraph_ordinal_method':'DIRECT_BODY_P_INCLUDING_EMPTY',
            'paragraphs':records,'signature_parts':[x for x in z.namelist()if x.startswith('_xmlsignatures/')],
            'identity_state':'EXACT_SOURCE_BYTES_AND_LOCATORS','authority_effect':'NONE'}

def same_occurrence(a,b):
    """Native string equality never substitutes for full scope equality."""
    if not isinstance(a,dict) or not isinstance(b,dict):return False
    return (isinstance(a.get('source_variant_sha256'),str)
        and HEX64.fullmatch(a['source_variant_sha256']) is not None
        and all(isinstance(a.get(k),str) and a[k] and a[k]==b.get(k) for k in SCOPE_FIELDS))

def qualify_effect(evidence_scope,target_scope,requested_effect):
    base={'schema':'qps-scoped-evidence-effect/1','authority_validated':False,'formal_credit_delta':0}
    if requested_effect!='RECORD_SOURCE_POSITION':
        return {**base,'state':'HOLD_EFFECT_EXCEEDS_SOURCE_POSITION','applied':False}
    if not same_occurrence(evidence_scope,target_scope):
        return {**base,'state':'HOLD_OCCURRENCE_SCOPE_MISMATCH','applied':False}
    return {**base,'state':'SOURCE_POSITION_SCOPE_COMPATIBLE','applied':True,
        'qualification':'Scope compatibility only. The caller must bind source bytes and attribution evidence separately.'}

def validate_variant_instrument(submitted_hashes,instrument):
    """Validate completeness; a complete declaration is still not authenticated."""
    if (not isinstance(submitted_hashes,(list,tuple))
            or any(not isinstance(x,str) or not HEX64.fullmatch(x) for x in submitted_hashes)):
        raise ValueError('submitted hashes must be a list or tuple of exact SHA256 strings')
    variants=sorted(set(submitted_hashes))
    if len(variants)<2:
        raise ValueError('two or more distinct exact submitted hashes required')
    i=instrument if isinstance(instrument,dict)else {}
    missing=[]
    if i.get('governing_variant_sha256') not in variants:missing.append('governing_variant_sha256')
    considered=i.get('considered_variant_sha256')
    if (not isinstance(considered,list) or any(not isinstance(x,str) or not HEX64.fullmatch(x)for x in considered)
            or sorted(set(considered))!=variants):missing.append('considered_variant_sha256')
    if not isinstance(i.get('instrument_sha256'),str) or not HEX64.fullmatch(i['instrument_sha256']):missing.append('instrument_sha256')
    for key in ('instrument_locator','attributable_actor','actor_role','authority_basis'):
        if not isinstance(i.get(key),str) or not i[key].strip():missing.append(key)
    try: date.fromisoformat(i.get('effective_date',''))
    except (ValueError,TypeError):missing.append('effective_date')
    try:
        dt=datetime.fromisoformat(i.get('issued_at','').replace('Z','+00:00'))
        if dt.tzinfo is None:raise ValueError()
    except (ValueError,TypeError,AttributeError):missing.append('issued_at')
    scope=i.get('scope',{}) if isinstance(i.get('scope',{}),dict) else {}
    if scope.get('kind')!='FULL_MATRIX':missing.append('scope_full_matrix')
    return {'schema':'qps-variant-instrument-shape/1','state':'INCOMPLETE_INSTRUMENT'if missing else'COMPLETE_CALLER_DECLARATION_UNAUTHENTICATED',
        'missing':missing,'candidate_sha256':i.get('governing_variant_sha256')if not missing else None,
        'selected_effective_sha256':None,'authority_validated':False,'formal_credit_delta':0,
        'qualification':'A clause-scoped record cannot select a governing whole matrix. Authentication and authorized effectiveness require separate evidence.'}
