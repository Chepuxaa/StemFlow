"""Lower two attention Einsums to MatMul without weights or precision changes.

Read only the protobuf fields needed for this rewrite, preserving other bytes.
No ONNX conversion package is needed in the desktop runtime.
"""
import hashlib
from pathlib import Path
import uuid


def _varint(data, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError('Truncated ONNX field')
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            return value, offset
    raise ValueError('Invalid ONNX integer')


def _encode(value):
    output = bytearray()
    while value > 127:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return bytes(output)


def _bytes(field, value):
    return _encode(field * 8 + 2) + _encode(len(value)) + value


def _fields(data):
    offset = 0
    while offset < len(data):
        start = offset
        key, offset = _varint(data, offset)
        field, wire = key >> 3, key & 7
        if not field:
            raise ValueError('Invalid ONNX field')
        if wire == 2:
            size, offset = _varint(data, offset)
            payload = data[offset:offset + size]
            offset += size
        elif wire == 0:
            value, offset = _varint(data, offset)
            payload = value
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            payload = data[offset:offset + size]
            offset += size
        else:
            raise ValueError('Unsupported ONNX field encoding')
        if offset > len(data):
            raise ValueError('Truncated ONNX field')
        yield field, wire, payload, data[start:offset]


def _node(inputs, outputs, name, operation, attribute=None):
    result = b''.join(_bytes(1, value) for value in inputs)
    result += b''.join(_bytes(2, value) for value in outputs)
    result += _bytes(3, name) + _bytes(4, operation)
    if attribute is not None:
        result += _bytes(5, attribute)
    return result


def _rewrite_node(data):
    fields = list(_fields(data))
    if not any(field == 4 and value == b'Einsum' for field, wire, value, raw in fields):
        return [data], 0
    equation = None
    for field, wire, value, raw in fields:
        if field == 5:
            attribute = list(_fields(value))
            if any(f == 1 and v == b'equation' for f, w, v, r in attribute):
                equation = next(v.replace(b' ', b'') for f, w, v, r in attribute if f == 4)
    if equation not in (b'bhid,bhjd->bhij', b'bhij,bhjd->bhid'):
        return [data], 0
    inputs = [value for field, wire, value, raw in fields if field == 1]
    outputs = [value for field, wire, value, raw in fields if field == 2]
    name = next((value for field, wire, value, raw in fields if field == 3), outputs[0])
    if len(inputs) != 2 or len(outputs) != 1:
        raise ValueError('Invalid attention Einsum')
    nodes = []
    if equation == b'bhid,bhjd->bhij':
        transposed = outputs[0] + b'_stemflow_transposed'
        # AttributeProto: name=perm, type=INTS (7), ints=[0,1,3,2].
        attribute = _bytes(1, b'perm') + _encode(20 * 8) + _encode(7) + _bytes(8, bytes([0, 1, 3, 2]))
        nodes.append(_node([inputs[1]], [transposed], name + b'_transpose', b'Transpose', attribute))
        inputs[1] = transposed
    nodes.append(_node(inputs, outputs, name + b'_matmul', b'MatMul'))
    return nodes, 1


def rewrite_attention(model):
    result = []
    count = 0
    for field, wire, value, raw in _fields(model):
        if field != 7 or wire != 2:
            result.append(raw)
            continue
        graph = []
        for number, encoding, payload, original in _fields(value):
            if number == 1 and encoding == 2:
                nodes, changed = _rewrite_node(payload)
                graph.extend(_bytes(1, node) for node in nodes)
                count += changed
            else:
                graph.append(original)
        result.append(_bytes(7, b''.join(graph)))
    return b''.join(result), count


def optimized_cpu_graph(source):
    source = Path(source)
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()[:16]
    # Same directory keeps all external weight references unchanged.
    target = source.with_name(f'{source.stem}-cpu-v1-{digest}.onnx')
    checksum = target.with_suffix('.sha256')
    if target.is_file() and checksum.is_file():
        if hashlib.sha256(target.read_bytes()).hexdigest() == checksum.read_text().strip():
            return target
    data, changed = rewrite_attention(original)
    if not changed:
        return source
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        temporary.write_bytes(data)
        temporary.replace(target)
        checksum.write_text(hashlib.sha256(data).hexdigest(), encoding='ascii')
    finally:
        temporary.unlink(missing_ok=True)
    return target
