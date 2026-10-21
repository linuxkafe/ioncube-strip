#!/usr/bin/env python3
"""
lib/opcode_decoder.py — Decode ionCube VM handlers and operand types.

Handler decryption (verified 916/916):
  decoded = raw ^ sign_extend64(keybuf[opline_index] * 0x01010101)

Operand type decryption:
  op1_type ^= keybuf32[(opline - opcodes)/48] | 1  (when flags[0xa4] & 0x400)
  op2_type ^= keybuf32[(opline - opcodes)/48] | 1  (when flags[0xa4] & 0x400)
  Tracked by byte bitmap at res3+0x20

The keybuf is per-function (selected by keyidx from loader's keybuf_ptr_array).
"""

import json
from dataclasses import dataclass
from typing import List, Dict, Optional
from lib.body_stream import ZendOp


@dataclass
class DecodedOp:
    """Decoded zend_op with handler name and resolved operands."""
    index: int
    raw_handler: int
    decoded_handler: int
    handler_name: str
    raw_op1: int
    raw_op2: int
    raw_result: int
    op1: int
    op2: int
    result: int
    extended_value: int
    lineno: int
    op1_type: int
    op2_type: int
    decoded_op1_type: int
    decoded_op2_type: int


def sign_extend_64_from_32(v: int) -> int:
    """Sign-extend 32-bit value to 64-bit."""
    v &= 0xffffffff
    if v & 0x80000000:
        v |= 0xffffffff00000000
    return v


def decode_handler(raw: int, keybuf: List[int], opline_index: int) -> int:
    """
    Decode handler using the verified formula:
      decoded = raw ^ sign_extend64(keybuf[i] * 0x01010101)
    """
    if opline_index >= len(keybuf):
        return raw
    k = keybuf[opline_index] & 0xffffffff
    pattern = (k * 0x01010101) & 0xffffffff
    return raw ^ sign_extend_64_from_32(pattern)


def decode_operand_type(raw_type: int, keybuf: List[int], opline_index: int) -> int:
    """
    Decode operand type:
      decoded = raw ^ (keybuf32[i] | 1)  (sign-extended to 8-bit)
    """
    if opline_index >= len(keybuf):
        return raw_type
    k = keybuf[opline_index] & 0xffffffff
    mask = (k | 1) & 0xff
    return raw_type ^ mask


def load_handler_map(map_path: str) -> Dict[int, str]:
    """Load handler address -> ZEND opcode name map from handler_map.txt."""
    handler_map = {}
    with open(map_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Format: 0x8b0a0 ZEND_SOME_OPCODE [confidence]
            parts = line.split()
            if len(parts) >= 2:
                try:
                    addr = int(parts[0], 0)
                    name = parts[1]
                    handler_map[addr] = name
                except ValueError:
                    pass
    return handler_map


def decode_opcodes(
    ops: List[ZendOp],
    keybuf: List[int],
    handler_map: Dict[int, str],
    bitmap_bytes: Optional[bytes] = None
) -> List[DecodedOp]:
    """Decode a list of ZendOp using keybuf and handler_map."""
    decoded = []
    
    for i, op in enumerate(ops):
        # Decode handler
        dec_handler = decode_handler(op.raw_handler, keybuf, i)
        handler_name = handler_map.get(dec_handler, f"UNKNOWN_{dec_handler:#x}")
        
        # Decode operand types (bitmap at res3+0x20 indicates which oplines are encrypted)
        # The bitmap is a byte per opline; non-zero means decrypt
        dec_op1_type = op.op1_type
        dec_op2_type = op.op2_type
        
        if bitmap_bytes and i < len(bitmap_bytes):
            if bitmap_bytes[i] != 0:
                dec_op1_type = decode_operand_type(op.op1_type, keybuf, i)
                dec_op2_type = decode_operand_type(op.op2_type, keybuf, i)
        
        decoded.append(DecodedOp(
            index=i,
            raw_handler=op.raw_handler,
            decoded_handler=dec_handler,
            handler_name=handler_name,
            raw_op1=op.raw_op1,
            raw_op2=op.raw_op2,
            raw_result=op.raw_result,
            op1=op.raw_op1,  # TODO: resolve op1/op2/result pointers
            op2=op.raw_op2,
            result=op.raw_result,
            extended_value=op.extended_value,
            lineno=op.lineno,
            op1_type=op.op1_type,
            op2_type=op.op2_type,
            decoded_op1_type=dec_op1_type,
            decoded_op2_type=dec_op2_type,
        ))
    
    return decoded


def load_keybuf(keybuf_path: str) -> List[int]:
    """Load keybuf from arm56_keybuf_<keyidx>.json.
    Supports both formats:
    - Original format: list of 256 bytes (integers 0-255 or hex strings)
    - New format: dict with 'keybuf' key containing list of 256 uint32
    """
    with open(keybuf_path) as f:
        data = json.load(f)
    if isinstance(data, list):
        keybuf = data
    else:
        keybuf = data.get('keybuf', [])
    # Convert hex strings to int if needed
    return [int(x, 16) if isinstance(x, str) else int(x) for x in keybuf]


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 4:
        print("Usage: python3 opcode_decoder.py <keybuf.json> <handler_map.txt> <parsed_dump.json>")
        sys.exit(1)
    
    keybuf = load_keybuf(sys.argv[1])
    handler_map = load_handler_map(sys.argv[2])
    
    with open(sys.argv[3]) as f:
        dump = json.load(f)
    
    from lib.body_stream import ZendOp
    ops = [ZendOp(
        handler=int(o['handler'], 16),
        op1=int(o['op1'], 16),
        op2=int(o['op2'], 16),
        result=int(o['result'], 16),
        extended_value=o['extended_value'],
        lineno=o['lineno'],
        op1_type=o['op1_type'],
        op2_type=o['op2_type'],
        raw_handler=int(o['handler'], 16),
        raw_op1=int(o['op1'], 16),
        raw_op2=int(o['op2'], 16),
        raw_result=int(o['result'], 16),
    ) for o in dump['opcodes']]
    
    decoded = decode_opcodes(ops, keybuf, handler_map)
    
    for d in decoded:
        print(f"op[{d.index:2d}] {d.handler_name:25s} "
              f"raw={d.raw_handler:#018x} dec={d.decoded_handler:#018x} "
              f"op1={d.raw_op1:#018x} op2={d.raw_op2:#018x} "
              f"res={d.raw_result:#018x} "
              f"o1t={d.op1_type:3d}->{d.decoded_op1_type:3d} "
              f"o2t={d.op2_type:3d}->{d.decoded_op2_type:3d}")