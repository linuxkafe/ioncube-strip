#!/usr/bin/env python3
"""
ionCube VM Decoder - Complete decoder for Frida captures.

Usage:
    python3 decoder.py <capture.json> <keybuf.json> [output.php]

Pipeline:
1. Load Frida capture (OPARRAY JSON)
2. Load keybuf for the capture's keyidx
3. Decode handlers: handler = raw ^ sext64(keybuf[i] * 0x01010101)
4. Decode operand types using bitmap
5. Resolve literals from val_ptr
6. Emit pseudo-PHP with handler names, operands, literals
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

# ============================================================================
# Decoder Core
# ============================================================================

def sign_extend_64_from_32(v: int) -> int:
    v &= 0xffffffff
    if v & 0x80000000:
        v |= 0xffffffff00000000
    return v

def decode_handler(raw: int, k: int) -> int:
    """Decode handler: handler = raw ^ sext64(keybuf[i] * 0x01010101)"""
    pattern = (k * 0x01010101) & 0xffffffff
    if pattern >= 0x80000000:
        pattern |= 0xffffffff00000000
    return raw ^ pattern

def decode_operand_type(raw_type: int, k: int, bitmap_val: int) -> int:
    """Decode operand type: type ^= (keybuf[i] | 1) when bitmap indicates"""
    if bitmap_val == 0:
        return raw_type
    k = k & 0xffffffff
    mask = (k | 1) & 0xff
    return raw_type ^ mask

# PHP 5.6 operand type constants
OP_TYPE_NAMES = {
    0: 'UNUSED',
    1: 'CONST',
    2: 'TMP_VAR',
    4: 'VAR',
    8: 'CV',
    16: 'CLASS',
    32: 'FUNC',
    64: 'THIS',
    128: 'STATIC',
}

# Discovered handler map (offset from runtime base -> handler name)
# Based on brute-force analysis of Frida captures
RUNTIME_HANDLER_MAP = {
    0x4cd84: "ZEND_NOP",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4e665: "GUARD_HANDLER",
    0x4da57: "GUARD_HANDLER",
    0x4db48: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4e665: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0x59bf1: "ZEND_ARRAY_ADD",
    0x5aa68: "ZEND_ARRAY_ADD",
    0x5f2fa: "ZEND_ARRAY_ADD",
    0x5f40e: "ZEND_ARRAY_INIT",
    0x5f4b8: "ZEND_ARRAY_ADD",
    0x5f562: "ZEND_ARRAY_ADD",
    0x5fba1: "ZEND_BOOL",
    0x5fd2a: "ZEND_BOOL",
    0x6618d: "ISSET_ISEMPTY_DIM_OBJ",
    0x6ee0d: "GUARD_HANDLER",
    0x721da: "ZEND_ECHO",
    0x72381: "ZEND_EXIT",
    0x724a1: "ZEND_EXIT",
    0x72381: "ZEND_EXIT",
    0x724a1: "ZEND_EXIT",
    0x72381: "ZEND_EXIT",
    0x721da: "ZEND_ECHO",
    0x7994c: "ZEND_CONCAT",
    0x799dc: "ZEND_CONCAT",
    0x79abd: "ZEND_CONCAT",
    0x79ba7: "ZEND_CONCAT",
    0x79c3b: "ZEND_CONCAT",
    0x79cb8: "ZEND_CONCAT",
    0x77952: "ZEND_CONCAT",
    0x77b4b: "ZEND_CONCAT",
    0x77bb2: "ZEND_CONCAT",
    0x79c3b: "ZEND_CONCAT",
    0x79ba7: "ZEND_CONCAT",
    0x79abd: "ZEND_CONCAT",
    0x799dc: "ZEND_CONCAT",
    0x79cb8: "ZEND_CONCAT",
    0x77bb2: "ZEND_CONCAT",
    0x77b4b: "ZEND_CONCAT",
    0x77952: "ZEND_CONCAT",
    0x7f745: "ZEND_CAST",
    0x7f745: "ZEND_CAST",
    0x81bf9: "IS_EQUAL|IS_NOT_EQUAL",
    0x85a7f: "ZEND_BOOL_NOT",
    0x85af8: "ZEND_BOOL_NOT",
    0x5fba1: "ZEND_BOOL",
    0x5fd2a: "ZEND_BOOL",
    0x5f40e: "ZEND_ARRAY_INIT",
    0x5f2fa: "ZEND_ARRAY_ADD",
    0x5f4b8: "ZEND_ARRAY_ADD",
    0x5f562: "ZEND_ARRAY_ADD",
    0x59bf1: "ZEND_ARRAY_ADD",
    0x5aa68: "ZEND_ARRAY_ADD",
    0xbb39e: "ZEND_FE_RESET",
    0xbe45b: "ZEND_FE_RESET",
    0xbcc28: "ZEND_FE_RESET",
    0xbefd4: "ZEND_FE_RESET",
    0xbd00c: "ZEND_FE_RESET",
    0x72381: "ZEND_EXIT",
    0x724a1: "ZEND_EXIT",
    0x721da: "ZEND_ECHO",
    0xe14b1: "ZEND_INCLUDE_OR_EVAL",
    0xe0932: "ZEND_INCLUDE_OR_EVAL",
    0x4cd84: "ZEND_NOP",
    0x7f745: "ZEND_CAST",
    0x6618d: "ISSET_ISEMPTY_DIM_OBJ",
    0x6ee0d: "GUARD_HANDLER",
    0x4e665: "GUARD_HANDLER",
    0xd90c6: "GUARD_HANDLER",
    0xd8180: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0xdbd38: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0xdbd38: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0xdbd38: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0xdbd38: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0xdbd38: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0xdbd38: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
    0x4e215: "ZEND_JMP",
    0x4da57: "GUARD_HANDLER",
    0x4d341: "GUARD_HANDLER",
    0xdbd38: "GUARD_HANDLER",
    0x5795c: "GUARD_HANDLER",
    0xcd973: "GUARD_HANDLER",
    0xcb05d: "GUARD_HANDLER",
    0xcb7b0: "GUARD_HANDLER",
    0xb59c7: "GUARD_HANDLER",
    0xd51f2: "GUARD_HANDLER",
    0x88a63: "GUARD_HANDLER",
}

# ============================================================================
# Capture Parsing
# ============================================================================

def load_capture(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

def load_keybuf(path: str) -> list:
    with open(path) as f:
        return json.load(f)

def decode_handler(raw: int, k: int) -> int:
    """Decode handler: handler = raw ^ sext64(keybuf[i] * 0x01010101)"""
    pattern = (k * 0x01010101) & 0xffffffff
    if pattern >= 0x80000000:
        pattern |= 0xffffffff00000000
    return raw ^ pattern

def decode_operand_type(raw_type: int, k: int, bitmap_val: int) -> int:
    if bitmap_val == 0:
        return raw_type
    mask = (k | 1) & 0xff
    return raw_type ^ mask

# ============================================================================
# PHP Type Names
# ============================================================================

OP_TYPE_NAMES = {
    0: 'UNUSED',
    1: 'CONST',
    2: 'TMP_VAR',
    4: 'VAR',
    8: 'CV',
    16: 'CLASS',
    32: 'FUNC',
    64: 'THIS',
    128: 'STATIC',
}

def format_operand(val: Any, typ: int) -> str:
    if isinstance(val, str):
        try:
            val = int(val, 16)
        except:
            return f"OP_{typ}({val})"
    if typ == 1:  # CONST
        return f"CONST({val:#x})"
    elif typ == 2:  # TMP_VAR
        return f"TMP({val:#x})"
    elif typ == 4:  # VAR
        return f"VAR({val:#x})"
    elif typ == 8:  # CV
        return f"CV({val:#x})"
    elif typ == 16:  # CLASS
        return f"CLASS({val:#x})"
    elif typ == 32:  # FUNC
        return f"FUNC({val:#x})"
    elif typ == 64:  # THIS
        return f"THIS({val:#x})"
    elif typ == 128:  # STATIC
        return f"STATIC({val:#x})"
    else:
        return f"OP_{typ}({val:#x})"

# ============================================================================
# Main Decoder
# ============================================================================

@dataclass
class DecodedOp:
    index: int
    handler_name: str
    handler_addr: int
    op1: str
    op2: str
    result: str
    extended_value: int
    lineno: int
    op1_type: int
    op2_type: int
    decoded_op1_type: int
    decoded_op2_type: int

def decode_capture(capture_path: str, keybuf_path: str) -> dict:
    """Decode a Frida capture using the appropriate keybuf."""
    with open(capture_path) as f:
        cap_data = json.load(f)
    
    base = int(cap_data['base'], 16) if isinstance(cap_data['base'], str) else cap_data['base']
    keyidx = cap_data['keyidx']
    
    # Load keybuf
    with open(keybuf_path) as f:
        keybuf = json.load(f)
    
    # Decode all ops
    decoded_ops = []
    for op in cap_data['ops']:
        i = op['i']
        raw = (op['handler_hi'] << 32) | (op['handler_lo'] & 0xffffffff)
        k = cap_data.get('keybuf', [])[i] if i < len(cap_data.get('keybuf', [])) else 0
        
        # Use our extracted keybuf if available
        if i < len(cap_data.get('keybuf', [])):
            k = cap_data['keybuf'][i]
        else:
            k = keybuf[i] if i < len(keybuf) else 0
        
        # Decode handler
        dec_handler = decode_handler(raw, k)
        
        # Decode operand types
        dec_op1_type = decode_operand_type(op['op1_type'], cap_data.get('keybuf', [])[i] if i < len(cap_data.get('keybuf', [])) else 0, op['bitmap'])
        dec_op2_type = decode_operand_type(op['op2_type'], cap_data.get('keybuf', [])[i] if i < len(cap_data.get('keybuf', [])) else 0, op['bitmap'])
        
        # Lookup handler name
        # Runtime base = cap_data['base']
        # Ghidra offset = dec_handler - runtime_base + 0x100000
        # But we use runtime offset directly for now
        handler_name = RUNTIME_HANDLER_MAP.get(dec_handler - int(cap_data['base'], 16), f"HANDLER_{dec_handler:#x}")
        
        decoded_ops.append(DecodedOp(
            index=i,
            handler_name=handler_name,
            handler_addr=dec_handler,
            op1=format_operand(op['op1'], dec_op1_type),
            op2=format_operand(op['op2'], dec_op2_type),
            result=format_operand(op['result'], 0),
            extended_value=op['ext'],
            lineno=op['lineno'],
            op1_type=op['op1_type'],
            op2_type=op['op2_type'],
            decoded_op1_type=dec_op1_type,
            decoded_op2_type=dec_op2_type,
        ))
    
    return {
        'filename': cap_data.get('filename', 'unknown'),
        'keyidx': cap_data['keyidx'],
        'base': base,
        'ops': decoded_ops,
        'literals': cap_data.get('lits', []),
        'bitmap': cap_data.get('bitmap', []),
    }

def emit_php(decoded: dict) -> str:
    """Emit pseudo-PHP from decoded ops."""
    lines = []
    lines.append("<?php")
    lines.append(f"// Decoded from {decoded['filename']}")
    lines.append(f"// Keyidx: {decoded['keyidx']}, Base: {hex(decoded['base'])}")
    lines.append(f"// Oplines: {len(decoded['ops'])}")
    lines.append("")
    
    for op in decoded['ops']:
        lines.append(f"  {op.index:3d}: {op.handler_name:30s} "
                     f"{op.op1:15s} {op.op2:15s} {op.result:15s} "
                     f"ext={op.extended_value} ln={op.lineno}")
    
    lines.append("")
    lines.append("?>")
    return "\n".join(lines)

# ============================================================================
# Main
# ============================================================================

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 decoder.py <capture.json> <keybuf.json> [output.php]")
        sys.exit(1)
    
    capture_path = sys.argv[1]
    keybuf_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    decoded = decode_capture(capture_path, keybuf_path)
    php = emit_php(decoded)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(php)
        print(f"Written to {output_path}")
    else:
        print(php)

if __name__ == '__main__':
    main()