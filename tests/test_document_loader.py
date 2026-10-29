import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.document_loader import load_and_chunk_documents, split_text_with_overlap


class ChunkTests(unittest.TestCase):
    def test_nested_college_headings_have_separate_context(self):
        with TemporaryDirectory() as folder:
            Path(folder, 'campus_organizations.md').write_text(
                '# 学校组织\n\n## 院系\n\n### 计算机学院\n软件工程专业，电话111。\n来源：https://example.com/computing\n\n### 商学院\n会计专业，电话222。', encoding='utf-8')
            chunks = load_and_chunk_documents(folder)
            computing = next(c for c in chunks if c['title'] == '计算机学院')
            business = next(c for c in chunks if c['title'] == '商学院')
            self.assertNotEqual(computing['section_id'], business['section_id'])
            self.assertNotIn('会计', computing['context_text'])
            self.assertNotIn('软件工程', business['context_text'])
            self.assertEqual(computing['url'], 'https://example.com/computing')

    def test_short_heading_does_not_create_tiny_repeated_chunks(self):
        text = '# 标题\n\n' + '校园服务内容介绍' * 40
        chunks = split_text_with_overlap(text, 's', 't', chunk_size=100, overlap=40)
        self.assertLessEqual(len(chunks), 7)
        self.assertTrue(all(len(c['text']) >= 50 for c in chunks[:-1]))

    def test_decimal_and_time_remain_whole_at_fallback_boundary(self):
        text = '说明内容内容0.12345以及08:30开放。'
        chunks = split_text_with_overlap(text, 's', 't', chunk_size=8, overlap=0)
        self.assertTrue(any('0.12345' in c['text'] for c in chunks))
        self.assertTrue(any('08:30' in c['text'] for c in chunks))

    def test_late_chunk_context_contains_chunk_and_title(self):
        with TemporaryDirectory() as folder:
            text = '# 服务指南\n\n' + '办理说明内容。' * 400 + '最终办理地点为行政楼。'
            Path(folder, 'guide.md').write_text(text, encoding='utf-8')
            chunks = load_and_chunk_documents(folder)
            last = chunks[-1]
            self.assertIn('最终办理地点为行政楼', last['context_text'])
            self.assertIn('服务指南', last['context_text'])
            self.assertLessEqual(len(last['context_text']), 1800)

    def test_sentence_boundaries(self):
        chunks = split_text_with_overlap('第一句结束。第二句结束。第三句结束。', 's', 't', chunk_size=13, overlap=0)
        self.assertEqual(chunks[0]['text'], '第一句结束。第二句结束。')

    def test_word_boundaries_and_content(self):
        text = 'alpha bravo charlie delta echo foxtrot golf'
        chunks = split_text_with_overlap(text, 's', 't', chunk_size=16, overlap=0)
        self.assertEqual(''.join(re.sub(r'\s', '', c['text']) for c in chunks), re.sub(r'\s', '', text))
        self.assertTrue(all(word in text.split() for c in chunks for word in c['text'].split()))

    def test_invalid_arguments_even_for_empty_text(self):
        for size, overlap in [(0, 0), (5, -1), (5, 5), (5, 6)]:
            with self.assertRaises(ValueError):
                split_text_with_overlap('', 's', 't', chunk_size=size, overlap=overlap)

    def test_empty_directory_still_validates_chunk_arguments(self):
        with TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                load_and_chunk_documents(folder, chunk_size=10, overlap=10)

    def test_long_word_is_preserved_whole(self):
        text = 'prefix extraordinarilylongword suffix'
        chunks = split_text_with_overlap(text, 's', 't', chunk_size=10, overlap=3)
        self.assertTrue(any('extraordinarilylongword' in c['text'] for c in chunks))
        self.assertTrue(all(word in text.split() for c in chunks for word in c['text'].split()))

    def test_section_metadata_and_landmark(self):
        with TemporaryDirectory() as folder:
            Path(folder, 'campus_landmarks.md').write_text('# 校园\n\n## 图书馆 (地标编号: library)\n\n开放时间。\n来源：https://example.com/article\n', encoding='utf-8')
            chunks = load_and_chunk_documents(folder, chunk_size=30, overlap=5)
            landmark = [c for c in chunks if c['landmark_id']]
            self.assertTrue(landmark)
            self.assertEqual(landmark[0]['title'], '图书馆')
            self.assertEqual(len({c['section_id'] for c in landmark}), 1)
            self.assertIn('开放时间', landmark[0]['context_text'])
            self.assertEqual(landmark[0]['url'], 'https://example.com/article')
            self.assertTrue(all('global_id' in c for c in chunks))


if __name__ == '__main__':
    unittest.main()
