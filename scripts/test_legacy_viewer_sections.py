"""Offline evidence-transport boundaries; synthetic responses are not audits."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import capture_legacy_viewer_sections as m


class Response(io.BytesIO):
    def getcode(self):
        return 200


class Opener:
    def __init__(self, raw=b'<p>source only</p>', error=None):
        self.raw, self.error, self.calls = raw, error, []

    def open(self, url, timeout):
        self.calls.append((url, timeout))
        if self.error:
            raise self.error
        return Response(self.raw)


class ViewerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(m.ROUTES.read_text())
        self.routes = m.validated_routes(self.document)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reports, self.artifacts = Path(self.temp.name)/'reports', Path(self.temp.name)/'raw'

    def control(self, **kwargs):
        return m.CollectionControl(max_requests=kwargs.get('max_requests', 12), max_seconds=30, min_interval=0)

    def test_real_artifact_supplies_twelve_routes_without_reinventing_offsets(self):
        self.assertEqual(len(self.routes), 12)
        self.assertIn('offset=392377&length=738954', self.routes[0]['url'])
        self.assertEqual(self.routes[0]['rcept_no'], '20010103000052')

    def test_mismatched_receipt_url_and_duplicate_route_are_rejected(self):
        for damage in ('receipt', 'url', 'duplicate'):
            with self.subTest(damage=damage):
                document=copy.deepcopy(self.document)
                section=document['receipts'][0]['financial_section_pointers'][0]
                if damage == 'receipt': section['parameters']['rcpNo']='20010104000076'
                elif damage == 'url': section['url']='https://example.org/'
                else: document['receipts'][0]['financial_section_pointers'].append(section)
                with self.assertRaises(ValueError): m.validated_routes(document)

    def test_raw_bytes_precede_report_and_second_run_is_noop(self):
        opener=Opener(raw='<p>자본총계 123</p>'.encode())
        real_publish=m.publish
        def verify_publication(path, data):
            if path.suffix == '.json':
                report=json.loads(data)
                self.assertTrue((self.artifacts/report['artifact_file']).exists())
                self.assertFalse(report['source_absence_confirmed'])
                self.assertEqual(report['independent_financial_audit'], 'NOT_RUN')
            real_publish(path,data)
        with patch.object(m,'publish',verify_publication):
            self.assertEqual(m.capture(self.routes[:1],self.reports,self.artifacts,self.control(),opener),1)
        self.assertEqual(m.capture(self.routes[:1],self.reports,self.artifacts,self.control(),opener),0)
        self.assertEqual(len(opener.calls),1)
        self.assertEqual(next(self.artifacts.glob('*.html')).read_bytes(),opener.raw)

    def test_transport_failure_stops_and_is_not_automatically_retried(self):
        opener=Opener(error=URLError('offline'))
        control=self.control()
        self.assertEqual(m.capture(self.routes,self.reports,self.artifacts,control,opener),1)
        self.assertEqual(len(opener.calls),1)
        self.assertEqual(control.stop_reason,'VIEWER_TRANSPORT_ERROR')
        report=json.loads(next(self.reports.glob('*.json')).read_text())
        self.assertEqual(report['download_status'],'TRANSPORT_ERROR')
        self.assertEqual(m.capture(self.routes[:1],self.reports,self.artifacts,self.control(),opener),0)

    def test_redirect_is_not_followed_and_http_error_is_source_evidence_only(self):
        handler=m.NoRedirects()
        self.assertIsNone(handler.redirect_request(None,None,302,'redirect',{},'https://example.org/'))
        error=HTTPError(self.routes[0]['url'],403,'blocked',{},io.BytesIO(b'Access denied'))
        control=self.control()
        m.capture(self.routes,self.reports,self.artifacts,control,Opener(error=error))
        self.assertEqual(control.requests,1)
        self.assertEqual(control.stop_reason,'VIEWER_ACCESS_BLOCKED')
        report=json.loads(next(self.reports.glob('*.json')).read_text())
        self.assertEqual(report['http_status'],403)
        self.assertEqual(report['download_status'],'HTTP_RESPONSE_CAPTURED')
        self.assertFalse(report['source_absence_confirmed'])

    def test_body_limit_and_request_deadline_bound_reads(self):
        with self.assertRaises(ValueError): m.read_response(Response(b'12345'),self.control(),4)
        control=self.control(); control.stop('DEADLINE')
        with self.assertRaises(m.CollectionPaused): m.read_response(Response(b'1'),control,4)

    def test_request_budget_never_submits_additional_calls(self):
        opener=Opener()
        control=self.control(max_requests=1)
        m.capture(self.routes,self.reports,self.artifacts,control,opener)
        self.assertEqual(len(opener.calls),1)
        self.assertEqual(control.requests,1)

    def test_publication_failure_cannot_leave_complete_report(self):
        with patch.object(m,'publish',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                m.capture(self.routes[:1],self.reports,self.artifacts,self.control(),Opener())
        self.assertFalse(list(self.reports.glob('*.json')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
