import unittest
from core.hybrid_retriever import HybridRetriever


class StaticRetriever:
    def __init__(self, chunks, results):
        self.chunks, self.results, self.calls = chunks, results, []

    def retrieve(self, query, top_k=5):
        self.calls.append(top_k)
        return self.results[:top_k]


class HybridTests(unittest.TestCase):
    def test_enlarged_pool_and_non_contiguous_ids(self):
        chunks = [dict(text='图书馆新书展览活动', source='news_xxyw', title='图书馆', global_id=10),
                  dict(text='图书馆开放时间：07:30—22:00，22:00闭馆。', source='library', title='开放时间', global_id=22)]
        sparse = StaticRetriever(chunks, [(chunks[0], .8), (chunks[1], .5)])
        dense = StaticRetriever(chunks, [(chunks[1], .9), (chunks[0], .6)])
        result = HybridRetriever(sparse, dense).retrieve('图书馆几点闭馆？', 1)
        self.assertEqual(result[0][0]['global_id'], 22)
        self.assertGreaterEqual(sparse.calls[0], 20)
        self.assertIn('reranker', result[0][2])


if __name__ == '__main__':
    unittest.main()
