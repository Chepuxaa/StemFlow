"""Check attention lowering against the original ONNX runtime on real tensors."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import onnx
import onnxruntime as ort
from cpu_graph import rewrite_attention, optimized_cpu_graph


class CpuGraphTests(unittest.TestCase):
    def model(self):
        helper = onnx.helper
        inputs = [helper.make_tensor_value_info(name, onnx.TensorProto.FLOAT, shape)
                  for name, shape in [('q',[1,2,3,4]), ('k',[1,2,5,4]), ('v',[1,2,5,6])]]
        nodes = [helper.make_node('Einsum',['q','k'],['scores'],equation='b h i d, b h j d -> b h i j'),
                 helper.make_node('Softmax',['scores'],['probabilities'],axis=-1),
                 helper.make_node('Einsum',['probabilities','v'],['output'],equation='b h i j, b h j d -> b h i d')]
        graph = helper.make_graph(nodes,'attention',inputs,[helper.make_tensor_value_info('output',onnx.TensorProto.FLOAT,[1,2,3,6])])
        model = helper.make_model(graph,ir_version=10,opset_imports=[helper.make_opsetid('',18)])
        model.doc_string = 'Preserve model metadata and existing graph operations.'
        return model

    def test_lowered_model_matches_original_and_preserves_metadata(self):
        model = self.model()
        rewritten, count = rewrite_attention(model.SerializeToString())
        self.assertEqual(count,2)
        converted = onnx.load_model_from_string(rewritten)
        onnx.checker.check_model(converted)
        self.assertEqual(model.doc_string,converted.doc_string)
        rng = np.random.default_rng(1)
        values = {value.name:rng.normal(size=[d.dim_value for d in value.type.tensor_type.shape.dim]).astype(np.float32)
                  for value in model.graph.input}
        original = ort.InferenceSession(model.SerializeToString(),providers=['CPUExecutionProvider'])
        optimized = ort.InferenceSession(rewritten,providers=['CPUExecutionProvider'])
        np.testing.assert_allclose(optimized.run(None,values)[0],original.run(None,values)[0],rtol=1e-6,atol=1e-6)

    def test_damaged_cache_is_regenerated_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'core.onnx'
            data=self.model().SerializeToString()
            source.write_bytes(data)
            target=optimized_cpu_graph(source)
            correct=target.read_bytes()
            target.write_bytes(b'damaged cache')
            self.assertEqual(optimized_cpu_graph(source).read_bytes(),correct)
            self.assertEqual(source.read_bytes(),data)

    def test_truncated_graph_rejected(self):
        with self.assertRaises(ValueError):
            rewrite_attention(b'\x3a\x80')
