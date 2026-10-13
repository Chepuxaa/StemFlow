"""Local dynamic U8U8 linear conversion for the optional fast CPU mode."""
import hashlib
import json
from pathlib import Path
import uuid

import numpy as np
from scripts.download_model import model_manifest


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024**2):
            digest.update(block)
    return digest.hexdigest()


def _linear_specs(model):
    initializers = {tensor.name: tensor for tensor in model.graph.initializer}
    producers = {output: node for node in model.graph.node for output in node.output}
    result = {}
    for node in model.graph.node:
        trans = producers.get(node.input[1]) if node.op_type == 'MatMul' else None
        tensor = initializers.get(trans.input[0]) if trans is not None and trans.op_type == 'Transpose' else None
        if tensor is not None:
            result[node.name] = tensor
    return result


def _quantized_weights(graph, specs):
    digest = model_manifest()['weights_sha256'][:16]
    destination = graph.parent / f'cpu-int8-v1-{digest}.data'
    index = destination.with_suffix('.json')
    if destination.is_file() and index.is_file():
        try:
            record = json.loads(index.read_text())
            if destination.stat().st_size == record['bytes'] and _hash_file(destination) == record['sha256']:
                if all(tensor.name in record['weights'] and list(reversed(tensor.dims)) == record['weights'][tensor.name]['shape']
                       for tensor in specs.values()):
                    return destination, record['weights']
        except (ValueError, KeyError, TypeError):
            pass
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.partial')
    records = {}
    offset = 0
    checksum = hashlib.sha256()
    try:
        with temporary.open('xb') as stream:
            for tensor in specs.values():
                if tensor.name in records:
                    continue
                if tensor.data_type != 10:  # TensorProto.FLOAT16
                    raise ValueError('Fast CPU conversion requires FP16 linear weights.')
                external = {entry.key: entry.value for entry in tensor.external_data}
                weights = np.memmap(graph.parent / external['location'], dtype=np.float16, mode='r',
                                    offset=int(external.get('offset',0)), shape=tuple(tensor.dims)).T.astype(np.float32)
                scale = np.maximum(np.abs(weights).max(axis=0) / 127, np.finfo(np.float32).tiny)
                quantized = np.clip(np.rint(weights / scale) + 128, 0, 255).astype(np.uint8)
                raw = quantized.tobytes()
                stream.write(raw)
                checksum.update(raw)
                records[tensor.name] = {'offset': offset, 'length': len(raw), 'shape': list(quantized.shape),
                                        'scale': scale.tolist()}
                offset += len(raw)
        temporary.replace(destination)
        index.write_text(json.dumps({'bytes':offset,'sha256':checksum.hexdigest(),'weights':records}),encoding='utf-8')
    finally:
        temporary.unlink(missing_ok=True)
    return destination, records


def fast_cpu_graph(graph):
    import onnx
    graph = Path(graph)
    original = graph.read_bytes()
    digest = hashlib.sha256(original).hexdigest()[:16]
    target = graph.with_name(f'{graph.stem}-int8-v1-{digest}.onnx')
    checksum = target.with_suffix('.sha256')
    model = onnx.load_model_from_string(original)
    specs = _linear_specs(model)
    if not specs:
        raise ValueError('No supported linear layers found for fast CPU conversion.')
    weight_path, records = _quantized_weights(graph, specs)
    if target.is_file() and checksum.is_file() and _hash_file(target) == checksum.read_text().strip():
        return target
    nodes = []
    initializers = []
    for node in model.graph.node:
        tensor = specs.get(node.name)
        if tensor is None:
            nodes.append(node)
            continue
        record = records[tensor.name]
        prefix = node.name + '_u8'
        weight = onnx.TensorProto(name=prefix+'_weight',data_type=onnx.TensorProto.UINT8,
                                  dims=record['shape'],data_location=onnx.TensorProto.EXTERNAL)
        for key,value in [('location',weight_path.name),('offset',str(record['offset'])),('length',str(record['length']))]:
            entry=weight.external_data.add();entry.key=key;entry.value=value
        initializers.extend([weight,onnx.numpy_helper.from_array(np.array(record['scale'],dtype=np.float32),prefix+'_scale'),
                             onnx.numpy_helper.from_array(np.array(128,dtype=np.uint8),prefix+'_zero')])
        make=onnx.helper.make_node
        nodes.extend([
            make('Cast',[node.input[0]],[prefix+'_fp32'],name=prefix+'_cast_in',to=onnx.TensorProto.FLOAT),
            make('DynamicQuantizeLinear',[prefix+'_fp32'],[prefix+'_input',prefix+'_input_scale',prefix+'_input_zero'],name=prefix+'_quantize'),
            make('MatMulInteger',[prefix+'_input',prefix+'_weight',prefix+'_input_zero',prefix+'_zero'],[prefix+'_integer'],name=prefix+'_matmul'),
            make('Cast',[prefix+'_integer'],[prefix+'_product'],name=prefix+'_cast_product',to=onnx.TensorProto.FLOAT),
            make('Mul',[prefix+'_input_scale',prefix+'_scale'],[prefix+'_combined_scale'],name=prefix+'_scales'),
            make('Mul',[prefix+'_product',prefix+'_combined_scale'],[prefix+'_output'],name=prefix+'_dequantize'),
            make('Cast',[prefix+'_output'],list(node.output),name=prefix+'_cast_out',to=onnx.TensorProto.FLOAT16),
        ])
    needed={value.name for value in model.graph.output}
    live=[]
    for node in reversed(nodes):
        if any(output in needed for output in node.output):
            live.append(node);needed.update(node.input)
    model.graph.ClearField('node');model.graph.node.extend(reversed(live))
    tensors=list(model.graph.initializer)+initializers
    model.graph.ClearField('initializer');model.graph.initializer.extend(tensor for tensor in tensors if tensor.name in needed)
    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        onnx.save_model(model,temporary)
        temporary.replace(target)
        checksum.write_text(_hash_file(target),encoding='ascii')
    finally:
        temporary.unlink(missing_ok=True)
    return target
