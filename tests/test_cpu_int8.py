"""Exercise local quantization, cache recovery and CPU mode changes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import onnx
import onnxruntime as ort
from cpu_int8 import fast_cpu_graph
from inference_runtime import ModelCache


class CpuInt8Tests(unittest.TestCase):
    def test_conversion_and_recovery_leave_original_weights_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            weights=np.array([[.1,-.2,.3,.4],[-.3,.2,.1,-.4],[.2,.4,-.1,.3]],dtype=np.float16)
            h=onnx.helper
            graph=h.make_graph([h.make_node('Transpose',['weight'],['transposed'],perm=[1,0]),
                                h.make_node('MatMul',['input','transposed'],['output'],name='projection')],
                               'linear',[h.make_tensor_value_info('input',onnx.TensorProto.FLOAT16,[2,4])],
                               [h.make_tensor_value_info('output',onnx.TensorProto.FLOAT16,[2,3])],
                               [onnx.numpy_helper.from_array(weights,'weight')])
            model=h.make_model(graph,ir_version=10,opset_imports=[h.make_opsetid('',18)])
            source=folder/'core.onnx'
            onnx.save_model(model,source,save_as_external_data=True,all_tensors_to_one_file=True,location='weights.data',size_threshold=0)
            before=(folder/'weights.data').read_bytes()
            target=fast_cpu_graph(source)
            onnx.checker.check_model(str(target))
            values={'input':np.array([[.3,.1,-.2,.4],[.1,-.4,.2,.3]],dtype=np.float16)}
            original=ort.InferenceSession(str(source),providers=['CPUExecutionProvider']).run(None,values)[0]
            actual=ort.InferenceSession(str(target),providers=['CPUExecutionProvider']).run(None,values)[0]
            np.testing.assert_allclose(actual,original,atol=.004,rtol=.03)
            data=next(folder.glob('cpu-int8-*.data'))
            length=data.stat().st_size
            data.write_bytes(b'damaged')
            self.assertEqual(fast_cpu_graph(source),target)
            self.assertEqual(data.stat().st_size,length)
            self.assertEqual((folder/'weights.data').read_bytes(),before)

    def test_cpu_mode_change_reloads_but_gpu_ignores_fast_cpu_choice(self):
        class Model:
            def close(self):
                pass
        cache=ModelCache()
        with patch('inference_runtime.load_model',side_effect=lambda *args,**kwargs:(Model(),{})) as loader:
            _,_,reuse=cache.get('cpu',6)
            self.assertFalse(reuse)
            _,_,reuse=cache.get('cpu',6,cpu_fast=True)
            self.assertFalse(reuse)
            _,_,reuse=cache.get('cpu',6,cpu_fast=True)
            self.assertTrue(reuse)
            cache.get('cuda:0',6,cpu_fast=True)
            _,_,reuse=cache.get('cuda:0',6,cpu_fast=False)
            self.assertTrue(reuse)
            self.assertEqual(loader.call_count,3)
        cache.clear()
