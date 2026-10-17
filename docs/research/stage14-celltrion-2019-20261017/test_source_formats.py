"""Source-quarantine safety only; synthetic HTML is not issuer evidence."""
import io
import unittest
import zipfile
from collect_sources import inspect_archive


def archive(*texts):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w") as z:
        for i,text in enumerate(texts): z.writestr(f"{i}.htm",text)
    return stream.getvalue()


class SourceFormats(unittest.TestCase):
    def test_html_notice_is_not_annual_report_xml(self):
        raw=archive('<!doctype html><html><br><table><tr><td>기준일</td><td>2019-12-31</td></tr></table></html>')
        members,texts=inspect_archive(raw,"a"*40)
        self.assertEqual(members[0]["format"],"HTML")
        self.assertFalse(members[0]["strict_xml_valid"])
        self.assertIn("2019-12-31",texts["0.htm"])
    def test_all_members_must_be_safe_before_return(self):
        with self.assertRaisesRegex(Exception,"CREDENTIAL_ECHO_BLOCKED"):
            inspect_archive(archive('<html>safe</html>','<html>'+"a"*40+'</html>'),"a"*40)
    def test_entity_escaped_credential_is_rejected(self):
        with self.assertRaisesRegex(Exception,"CREDENTIAL_ECHO_BLOCKED"):
            inspect_archive(archive('<html>'+"&#97;"*40+'</html>'),"a"*40)
    def test_nonarchive_not_promoted_to_document(self):
        with self.assertRaisesRegex(ValueError,"NOT_DOCUMENT_ARCHIVE"):
            inspect_archive(b'<result><status>014</status></result>',"a"*40)


if __name__=="__main__": unittest.main(verbosity=2)
