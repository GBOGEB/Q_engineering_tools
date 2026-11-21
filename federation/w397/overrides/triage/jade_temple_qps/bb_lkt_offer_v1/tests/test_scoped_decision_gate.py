import copy,hashlib,io,tempfile,unittest,warnings
from unittest.mock import patch
from pathlib import Path
from zipfile import ZipFile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scoped_decision_gate import extract_bound_docx,qualify_effect,validate_variant_instrument

class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.scope={'namespace':'APPLICANT:COMMERCIAL','native_id':'NATIVE-085','source_variant_sha256':'a'*64,'physical_role':'CLAUSE','section':'22.1'}
    def test_position_kept_in_own_occurrence(self):
        self.assertTrue(qualify_effect(self.scope,self.scope,'RECORD_SOURCE_POSITION')['applied'])
    def test_variant_promotion_rejected(self):
        self.assertFalse(qualify_effect(self.scope,self.scope,'SELECT_GOVERNING_VARIANT')['applied'])
    def test_same_id_different_variant_rejected(self):
        b={**self.scope,'source_variant_sha256':'b'*64,'section':'23.2'}
        self.assertFalse(qualify_effect(self.scope,b,'RECORD_SOURCE_POSITION')['applied'])
    def test_duplicate_id_heading_clause_rejected(self):
        b={**self.scope,'physical_role':'HEADING'}
        self.assertFalse(qualify_effect(self.scope,b,'RECORD_SOURCE_POSITION')['applied'])
    def test_adjacent_native_id_rejected(self):
        b={**self.scope,'native_id':'NATIVE-154'}
        self.assertFalse(qualify_effect(self.scope,b,'RECORD_SOURCE_POSITION')['applied'])
    def test_same_label_other_namespace_rejected(self):
        b={**self.scope,'namespace':'ACTION_REGISTER'}
        self.assertFalse(qualify_effect(self.scope,b,'RECORD_SOURCE_POSITION')['applied'])
    def test_scope_requires_real_sha_shape(self):
        b={**self.scope,'source_variant_sha256':'not-a-digest'}
        self.assertFalse(qualify_effect(b,b,'RECORD_SOURCE_POSITION')['applied'])
    def test_malformed_instrument_fails_closed(self):
        r=validate_variant_instrument(['a'*64,'b'*64],{'considered_variant_sha256':None,'scope':'FULL_MATRIX'})
        self.assertIn('considered_variant_sha256',r['missing']);self.assertIn('scope_full_matrix',r['missing'])
    def test_malformed_submitted_hash_container_fails_explicitly(self):
        for bad in [None,'a'*64,{'a'*64:'b'*64},set(['a'*64,'b'*64]),[None,'b'*64],[{},'b'*64],['a'*64,1],['invalid','b'*64],['a'*64,'a'*64]]:
            with self.subTest(value=repr(bad)),self.assertRaises(ValueError):
                validate_variant_instrument(bad,{})
    def test_incomplete_instrument_held(self):
        r=validate_variant_instrument(['a'*64,'b'*64],{'governing_variant_sha256':'a'*64,'scope':{'kind':'CLAUSE'}})
        self.assertIn('effective_date',r['missing']);self.assertIn('scope_full_matrix',r['missing']);self.assertIsNone(r['selected_effective_sha256'])
    def test_complete_declaration_does_not_invent_authority(self):
        i={'governing_variant_sha256':'a'*64,'considered_variant_sha256':['a'*64,'b'*64],'instrument_sha256':'c'*64,'instrument_locator':'source:1','attributable_actor':'test actor','actor_role':'test owner','authority_basis':'synthetic fixture','effective_date':'2026-11-20','issued_at':'2026-11-20T12:00:00Z','scope':{'kind':'FULL_MATRIX'}}
        r=validate_variant_instrument(['a'*64,'b'*64],i);self.assertFalse(r['missing']);self.assertFalse(r['authority_validated']);self.assertIsNone(r['selected_effective_sha256'])
    def test_docx_empty_paragraph_ordinals_and_wrong_hash(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'source.docx'
            with ZipFile(p,'w')as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Question</w:t></w:r></w:p><w:p/><w:p><w:r><w:t>Reply</w:t></w:r></w:p></w:body></w:document>')
            h=hashlib.sha256(p.read_bytes()).hexdigest();r=extract_bound_docx(p,h,[1,3],emit_private_text=True);self.assertEqual(r['paragraphs'][1]['text_verbatim'],'Reply')
            self.assertNotIn('text_verbatim',extract_bound_docx(p,h,[3])['paragraphs'][0])
            with self.assertRaises(ValueError):extract_bound_docx(p,'0'*64,[1])
            with self.assertRaises(ValueError):extract_bound_docx(p,h,[4])
    def test_changed_anchor_requires_revision_view(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'source.docx'
            with ZipFile(p,'w')as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:ins><w:r><w:t>Reply</w:t></w:r></w:ins></w:p></w:body></w:document>')
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):extract_bound_docx(p,h,[1])
    def test_tracked_move_containers_and_ranges_require_revision_view(self):
        tags=[
            '<w:moveFrom><w:r><w:t>Moved</w:t></w:r></w:moveFrom>',
            '<w:moveTo><w:r><w:t>Moved</w:t></w:r></w:moveTo>',
            '<w:moveFromRangeStart w:id="1"/><w:r><w:t>Moved</w:t></w:r><w:moveFromRangeEnd w:id="1"/>',
            '<w:moveToRangeStart w:id="1"/><w:r><w:t>Moved</w:t></w:r><w:moveToRangeEnd w:id="1"/>',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.docx'
            for body in tags:
                with ZipFile(p,'w') as z:
                    z.writestr('word/document.xml',
                        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                        f'<w:body><w:p>{body}</w:p></w:body></w:document>')
                h=hashlib.sha256(p.read_bytes()).hexdigest()
                with self.subTest(body=body),self.assertRaisesRegex(ValueError,'revision view'):
                    extract_bound_docx(p,h,[1])

    def test_visible_tabs_and_breaks_are_bound_in_text_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.docx'
            xml=(
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>A</w:t><w:tab/><w:t>B</w:t><w:br/>'
                '<w:t>C</w:t><w:cr/><w:t>D</w:t></w:r></w:p></w:body></w:document>'
            )
            with ZipFile(p,'w') as z:z.writestr('word/document.xml',xml)
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            r=extract_bound_docx(p,h,[1],emit_private_text=True)['paragraphs'][0]
            self.assertEqual(r['text_verbatim'],'A\tB\nC\nD')
            self.assertEqual(r['text_sha256'],hashlib.sha256('A\tB\nC\nD'.encode()).hexdigest())
            self.assertNotEqual(r['text_sha256'],hashlib.sha256('ABCD'.encode()).hexdigest())

    def test_visible_hyphen_controls_are_canonical_and_symbol_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.docx'
            xml=(
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>A</w:t><w:noBreakHyphen/><w:t>B</w:t>'
                '<w:softHyphen/><w:t>C</w:t></w:r></w:p></w:body></w:document>'
            )
            with ZipFile(p,'w') as z:z.writestr('word/document.xml',xml)
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            r=extract_bound_docx(p,h,[1],emit_private_text=True)['paragraphs'][0]
            expected='A\u2011B\u00adC'
            self.assertEqual(r['text_verbatim'],expected)
            self.assertEqual(r['text_sha256'],hashlib.sha256(expected.encode()).hexdigest())

            xml=(
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>A</w:t><w:sym w:font="Symbol" w:char="F061"/>'
                '<w:t>B</w:t></w:r></w:p></w:body></w:document>'
            )
            with ZipFile(p,'w') as z:z.writestr('word/document.xml',xml)
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'unsupported visible Word control'):
                extract_bound_docx(p,h,[1])

    def test_docx_replace_restore_cannot_change_hashed_snapshot(self):
        def package(text):
            stream=io.BytesIO()
            with ZipFile(stream,'w') as z:
                z.writestr('word/document.xml',f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
            return stream.getvalue()
        original=package('Pinned statement');replacement=package('Unbound replacement')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.docx';p.write_bytes(original)
            expected=hashlib.sha256(original).hexdigest()
            real_read=Path.read_bytes
            def read_then_replace(path):
                snapshot=real_read(path)
                path.write_bytes(replacement)
                return snapshot
            try:
                with patch.object(Path,'read_bytes',new=read_then_replace):
                    result=extract_bound_docx(p,expected,[1],emit_private_text=True)
            finally:
                p.write_bytes(original)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),expected)
            self.assertEqual(result['paragraphs'][0]['text_verbatim'],'Pinned statement')
            self.assertEqual(result['source_sha256'],expected)
    def test_duplicate_document_parts_rejected(self):
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/></w:body></w:document>'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.docx'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with ZipFile(p,'w') as z:
                    z.writestr('word/document.xml',xml)
                    z.writestr('word/document.xml',xml)
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'exactly one word/document.xml'):
                extract_bound_docx(p,h,[1])
    def test_entity_declaration_rejected_across_xml_encodings(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'source.docx'
            for encoding in ['utf-8','utf-8-sig','utf-16','utf-16-le','utf-16-be','utf-32','utf-32-le','utf-32-be']:
                xml='<!DOCTYPE w:document [<!ENTITY sample "Expanded">]><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&sample;</w:t></w:r></w:p></w:body></w:document>'
                with ZipFile(p,'w')as z:z.writestr('word/document.xml',xml.encode(encoding))
                h=hashlib.sha256(p.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError,'DTD or entity'):extract_bound_docx(p,h,[1])

if __name__=='__main__':unittest.main()
