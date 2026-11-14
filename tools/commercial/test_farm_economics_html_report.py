import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
from farm_economics_validator import validate_csv,FIELDS
from farm_economics_html_report import render_html,main
BASE=['farm01','wheat','2026-01-01','2026-06-30','USD','kg','100','80','800','20','300','200','50']
def payload(row=None):
    line=','.join(BASE if row is None else row)
    return {'schema_version':1,'records':validate_csv(','.join(FIELDS)+'\n'+line+'\n')}
class FarmReportTests(unittest.TestCase):
    def test_report_renders_period_amounts_and_caveat(self):
        s=render_html(payload())
        for value in ('lang="fa" dir="rtl"','2026-01-01','800','هزینه موجودی فروش‌نرفته','NOT_ATTAINABLE','پیش‌نویس'):
            self.assertIn(value,s)
    def test_malicious_html_like_label_is_escaped(self):
        row=BASE.copy();row[1]='wheat<img src=x onerror=alert(1)>'
        s=render_html(payload(row))
        self.assertIn('&lt;img',s)
        self.assertNotIn('<img src=x',s)
    def test_schema_rejected(self):
        with self.assertRaises(ValueError): render_html({'schema_version': 2,'records':[]})
    def test_missing_evidence_field_rejected(self):
        data=payload();del data['records'][0]['period_start']
        with self.assertRaisesRegex(ValueError,'missing or invalid'): render_html(data)
    def test_normal_fully_sold_economic_break_even_displayed(self):
        row=BASE.copy();row[6]='80'
        self.assertIn('4E+1',render_html(payload(row)))
    def test_cli_emits_html_from_validated_json_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'report.json';path.write_text(json.dumps(payload()),encoding='utf-8')
            out=io.StringIO()
            with redirect_stdout(out):rc=main([str(path)])
            self.assertEqual(rc,0)
            self.assertIn('<!doctype html>',out.getvalue())
    def test_cli_bad_json_emits_no_html(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'report.json';path.write_text('invalid',encoding='utf-8')
            out,err=io.StringIO(),io.StringIO()
            with redirect_stdout(out),redirect_stderr(err):rc=main([str(path)])
            self.assertEqual(rc,2)
            self.assertEqual(out.getvalue(),'')
            self.assertIn('Report rejected:',err.getvalue())
if __name__=='__main__': unittest.main()
