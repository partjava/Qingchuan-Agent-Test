"""The rendered overview must use the loaded corpus size, not a stale literal."""
import unittest
from unittest.mock import patch
from web import app as web_app


class KnowledgeDisplayTests(unittest.TestCase):
    def test_welcome_and_modal_follow_loaded_chunk_count(self):
        for count in (0, 1234):
            with self.subTest(count=count), patch.object(web_app, 'chunks', [None]*count):
                html = web_app.index().body.decode('utf-8')
                self.assertIn(f'{count:,} 个语义文本块', html)
                self.assertIn(f'<strong>{count:,} 块</strong>', html)
                self.assertNotIn('24,082', html)
                self.assertNotIn('{{KB_TOTAL_CHUNKS}}', html)


if __name__ == '__main__':
    unittest.main()
