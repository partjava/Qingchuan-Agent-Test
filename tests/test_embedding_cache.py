import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from core.bge_retriever import corpus_model_fingerprint, valid_cached_embeddings


class CacheTests(unittest.TestCase):
    def test_middle_content_and_model_identity_change_fingerprint(self):
        corpus = ['same', 'middle', 'same']
        sig = corpus_model_fingerprint(corpus, 'model-a')
        self.assertNotEqual(sig, corpus_model_fingerprint(['same', 'changed', 'same'], 'model-a'))
        self.assertNotEqual(sig, corpus_model_fingerprint(corpus, 'model-b'))

    def test_local_configuration_changes_fingerprint(self):
        with TemporaryDirectory() as folder:
            config = Path(folder, 'config.json')
            config.write_text('{"hidden_size": 2}')
            sig = corpus_model_fingerprint(['text'], folder)
            config.write_text('{"hidden_size": 3}')
            self.assertNotEqual(sig, corpus_model_fingerprint(['text'], folder))

    def test_rejects_wrong_shape_and_nonfinite_cache(self):
        self.assertTrue(valid_cached_embeddings(np.ones((2, 3)), 2, 3))
        for value in [np.ones(2), np.ones((2, 4)), np.ones((1, 3)), np.full((2, 3), np.nan)]:
            self.assertFalse(valid_cached_embeddings(value, 2, 3))


if __name__ == '__main__':
    unittest.main()
