import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile
from PyPDF2 import PdfWriter

spec=importlib.util.spec_from_file_location(
    "mpw_private_audit",
    Path(__file__).resolve().parents[1]/"scripts/mpw_three_sku_private_content_audit_20261026.py",
)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class PrivateContentAuditTests(unittest.TestCase):
    def test_pdf_audit_reports_metrics_without_emitting_text_or_certifying(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"minimal.pdf"
            writer=PdfWriter()
            writer.add_blank_page(width=612,height=792)
            with path.open("wb") as stream:
                writer.write(stream)
            result=audit.audit_pdf(path)
            self.assertEqual(result["format"],"pdf")
            self.assertEqual(result["page_count"],1)
            if not result["visual_render"]["renderer_available"]:
                self.skipTest("PDF renderer is provisioned by the private QA workflow")
            self.assertEqual(result["visual_render"]["rendered_page_count"],1)
            self.assertIsNone(result["visual_render"]["render_failure"])
            self.assertIn("page_text_extraction_coverage_ge_95pct",result["checks"])
            self.assertNotIn("text",result)
            self.assertNotIn("extracted_text",result)
            self.assertGreater(len(result["needs_specialist_review"]),0)
            # Default PDF audits (including the chess research guide) must
            # retain scholarly checks even when SKU 225 uses picture-book gates.
            self.assertIn("bibliography_or_reference_markers_found", result["checks"])
            self.assertIn("structure_markers_found", result["checks"])
            self.assertIn("citation_validity", result["needs_specialist_review"])
            self.assertIn("scientific_depth", result["needs_specialist_review"])

    def test_picturebook_uses_product_specific_page_and_illustration_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"picturebook.pdf"
            writer=PdfWriter()
            writer.add_blank_page(width=612,height=792)
            with path.open("wb") as stream:
                writer.write(stream)
            result=audit.audit_pdf(path,expected_page_count=1,require_illustrations=True)
            self.assertTrue(result["checks"]["page_count_matches_declared_product_spec"])
            self.assertFalse(result["checks"]["graphic_drawing_signals_present"])
            self.assertNotIn("bibliography_or_reference_markers_found", result["checks"])
            self.assertNotIn("structure_markers_found", result["checks"])
            self.assertIn("read_aloud_rhythm", result["needs_specialist_review"])
            self.assertNotIn("citation_validity", result["needs_specialist_review"])
            self.assertIn("image_scan_errors",result)
            self.assertNotIn("extracted_text",result)

    def test_picturebook_vector_signal_threshold(self):
        self.assertTrue(audit.graphic_drawing_signals_present(40,0,40,2544))
        self.assertTrue(audit.graphic_drawing_signals_present(40,3,0,0))
        self.assertFalse(audit.graphic_drawing_signals_present(40,0,0,0))
        self.assertFalse(audit.graphic_drawing_signals_present(40,0,20,160))

    def test_ppm_visual_metrics_detect_colored_and_blank_regions(self):
        raw=b"P6\n2 1\n255\n"+bytes([255,255,255,255,0,0])
        result=audit.ppm_pixel_metrics(raw)
        self.assertEqual(result["width"],2)
        self.assertEqual(result["height"],1)
        self.assertFalse(result["near_blank"])
        self.assertEqual(result["colored_pixel_ratio"],0.5)
        self.assertNotIn("pixels",result)

    def test_pdfium_bitmap_metrics_detect_blank_and_color_without_pixels(self):
        class Bitmap:
            width=2
            height=1
            n_channels=4
            stride=8
            buffer=bytes([255,255,255,255,255,0,0,255])
        result=audit.bitmap_pixel_metrics(Bitmap())
        self.assertFalse(result["near_blank"])
        self.assertEqual(result["colored_pixel_ratio"],0.5)
        self.assertNotIn("pixels",result)

    def test_pdf_audit_reports_vector_graphics_metrics_without_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"vector.pdf"
            writer=PdfWriter()
            writer.add_blank_page(width=612,height=792)
            with path.open("wb") as stream:
                writer.write(stream)
            result=audit.audit_pdf(path,expected_page_count=1,require_illustrations=True)
            self.assertIsInstance(result["vector_drawing_operator_count"],int)
            self.assertIsInstance(result["pages_with_vector_drawing"],int)
            self.assertIsInstance(result["graphics_scan_errors"],int)
            self.assertNotIn("extracted_text",result)

    def test_zip_audit_checks_assets_and_accessibility_without_releasing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"site.zip"
            with zipfile.ZipFile(path,"w") as archive:
                archive.writestr("index.html","<html lang='en'><head><title>Product</title></head><body><h1>Product</h1><img src='hero.png' alt='Product'></body></html>")
                archive.writestr("hero.png",b"not-a-rendered-image")
            result=audit.audit_zip(path)
            self.assertTrue(result["checks"]["crc_passed"])
            self.assertTrue(result["checks"]["html_title_present"])
            self.assertTrue(result["checks"]["accessible_image_alt_present"])
            self.assertTrue(result["checks"]["local_asset_links_resolve"])
            self.assertNotIn("html_content",result)
            self.assertIn("navigation_integrity",result["needs_specialist_review"])
            self.assertNotIn("gameplay",result["needs_specialist_review"])

    def test_zip_missing_media_and_srcset_assets_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"site.zip"
            with zipfile.ZipFile(path,"w") as archive:
                archive.writestr("index.html",
                    "<html><head><title>Kit</title></head><body>"
                    "<img src='missing-hero.png' alt='Hero'>"
                    "<picture><source srcset='absent-1.png 1x, absent-2.png 2x'></picture>"
                    "<video poster='missing-poster.jpg'></video>"
                    "</body></html>")
            result=audit.audit_zip(path)
            self.assertFalse(result["checks"]["local_asset_links_resolve"])
            self.assertEqual(len(result["missing_local_refs"]),4)
            self.assertNotIn("html_content",result)

    def test_unsafe_zip_paths_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"unsafe.zip"
            with zipfile.ZipFile(path,"w") as archive:
                archive.writestr("../escape.txt","x")
                archive.writestr("index.html","<title>x</title>")
            result=audit.audit_zip(path)
            self.assertFalse(result["checks"]["unsafe_members_absent"])

if __name__=="__main__":
    unittest.main()
