#!/usr/bin/env python3
"""
lib/full_decoder.py — Complete decoder pipeline for ionCube VM op_arrays.

Combines:
- Frida capture parsing (OPARRAY JSON)
- Handler decryption (using keybuf)
- Operand type decryption (using bitmap)
- Literal resolution (val_ptr -> string pool)
- Pseudo-PHP emission
"""

import json
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import sys

# Import existing modules
sys.path.insert(0, '/home/seyon/dev/ioncube-strip')
from lib.body_stream import ZendOp
from lib.opcode_decoder import decode_handler, decode_operand_type, load_handler_map, load_keybuf


@dataclass
class FridaOp:
    """Opcode from Frida capture."""
    i: int
    handler_lo: int
    handler_hi: int
    op1: int
    op2: int
    result: int
    ext: int
    lineno: int
    op1_type: int
    op2_type: int
    result_type: int
    bitmap: int


@dataclass
class FridaLiteral:
    """Literal from Frida capture."""
    index: int
    raw_bytes: List[int]
    val_ptr: int


@dataclass
class DecodedOp:
    """Fully decoded opcode."""
    index: int
    handler_name: str
    handler_addr: int
    op1: int
    op2: int
    result: int
    ext: int
    lineno: int
    op1_type: int
    op2_type: int
    decoded_op1_type: int
    decoded_op2_type: int
    op1_type_name: str
    op2_type_name: str


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


def parse_frida_capture(json_path: Path) -> Dict[str, Any]:
    """Parse Frida OPARRAY capture JSON."""
    with open(json_path) as f:
        return json.load(f)


def frida_ops_to_zendops(cap: Dict) -> List[ZendOp]:
    """Convert Frida ops to ZendOp structs."""
    ops = []
    for op in cap['ops']:
        handler_lo = op['handler_lo']
        handler_hi = op['handler_hi']
        raw_handler = (handler_hi << 32) | (handler_lo & 0xffffffff)
        ops.append(ZendOp(
            handler=raw_handler,
            op1=int(op['op1'], 16),
            op2=int(op['op2'], 16),
            result=int(op['result'], 16),
            extended_value=op['ext'],
            lineno=op['lineno'],
            op1_type=op['op1_type'],
            op2_type=op['op2_type'],
            raw_handler=raw_handler,
            raw_op1=int(op['op1'], 16),
            raw_op2=int(op['op2'], 16),
            raw_result=int(op['result'], 16),
        ))
    return ops


def decode_frida_capture(
    cap: Dict,
    keybuf: List[int],
    handler_map: Dict[int, str],
    string_pool: Optional[Dict[int, str]] = None
) -> List[DecodedOp]:
    """Decode a Frida capture using keybuf and handler_map."""
    
    ops = frida_ops_to_zendops(cap)
    bitmap = cap.get('bitmap', [])
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    
    decoded = []
    
    for i, op in enumerate(ops):
        # Decode handler
        dec_handler = decode_handler(op.raw_handler, keybuf, i)
        handler_name = handler_map.get(dec_handler, f"UNKNOWN_{dec_handler:#x}")
        
        # Decode operand types
        dec_op1_type = op.op1_type
        dec_op2_type = op.op2_type
        if i < len(bitmap) and bitmap[i] != 0:
            dec_op1_type = decode_operand_type(op.op1_type, keybuf, i)
            dec_op2_type = decode_operand_type(op.op2_type, keybuf, i)
        
        op1_type_name = OP_TYPE_NAMES.get(dec_op1_type, f"TYPE_{dec_op1_type}")
        op2_type_name = OP_TYPE_NAMES.get(dec_op2_type, f"TYPE_{dec_op2_type}")
        
        decoded.append(DecodedOp(
            index=i,
            handler_name=handler_name,
            handler_addr=dec_handler,
            op1=op.raw_op1,
            op2=op.raw_op2,
            result=op.raw_result,
            ext=op.extended_value,
            lineno=op.lineno,
            op1_type=op.op1_type,
            op2_type=op.op2_type,
            decoded_op1_type=dec_op1_type,
            decoded_op2_type=dec_op2_type,
            op1_type_name=op1_type_name,
            op2_type_name=op2_type_name,
        ))
    
    return decoded


def extract_string_pool(cap: Dict) -> Dict[int, str]:
    """Extract string pool from literals' val_ptr.
    
    The string pool is a separate heap allocation containing decoded strings.
    The val_ptr of literals that have been decrypted point into this pool.
    """
    pool = {}
    for lit in cap.get('lits', []):
        try:
            val_ptr = int(lit['val_ptr'], 16) if isinstance(lit['val_ptr'], str) else lit['val_ptr']
            # We can't read the actual string from val_ptr without Frida
            # But we can extract strings from the literal raw_bytes
            if lit['raw_bytes']:
                # Look for ASCII strings in the raw bytes
                bytes_arr = bytes(lit['raw_bytes'])
                # The string value is at offset 0x18 in the 32-byte literal
                # For now, just note the val_ptr
                pool[val_ptr] = f"<ptr:{val_ptr:#x}>"
        except:
            pass
    return pool


def emit_pseudo_php(decoded: List[DecodedOp], cap: Dict, string_pool: Dict[int, str]) -> str:
    """Emit pseudo-PHP from decoded ops."""
    lines = []
    lines.append(f"<?php")
    lines.append(f"// Decoded from: {cap.get('filename', 'unknown')}")
    lines.append(f"// Function: {cap.get('filename', '').split('/')[-1].replace('.php', '')}")
    lines.append(f"// Oplines: {cap.get('last', 0)}")
    lines.append(f"// Keyidx: {cap.get('keyidx', '?')}")
    lines.append(f"")
    
    # Group ops by basic blocks (simple heuristic: JMP targets)
    jump_targets = set()
    for op in decoded:
        if op.handler_name.startswith('JMP') or 'JMP' in op.handler_name:
            # Try to extract target from ext or result
            if op.ext:
                jump_targets.add(op.ext)
    
    for op in decoded:
        # Label if jump target
        if op.index in jump_targets:
            lines.append(f"L{op.index}:")
        
        # Format operands
        def fmt_operand(val: int, typ: int, name: str) -> str:
            if typ == 1:  # CONST
                return f"CONST({val:#x})"
            elif typ == 2:  # TMP_VAR
                return f"TMP({val:#x})"
            elif typ == 4:  # VAR
                return f"VAR({val:#x})"
            elif typ == 8:  # CV
                return f"CV({val:#x})"
            else:
                return f"{name}({val:#x})"
        
        op1_str = fmt_operand(op.op1, op.decoded_op1_type, 'OP1')
        op2_str = fmt_operand(op.op2, op.decoded_op2_type, 'OP2')
        res_str = fmt_operand(op.result, 0, 'RES') if op.result else ''
        
        ext_str = f" ext={op.ext}" if op.ext else ""
        line_str = f" line={op.lineno}" if op.lineno else ""
        
        lines.append(
            f"  {op.index:3d}: {op.handler_name:30s} "
            f"{op1_str:15s} {op2_str:15s} {res_str:15s} "
            f"[{op.op1_type_name}/{op.op2_type_name}]"
            f"{ext_str}{line_str}"
        )
    
    return "\n".join(lines)


def process_capture(
    capture_path: Path,
    keybuf_path: Path,
    handler_map_path: Path,
    output_dir: Path
) -> Dict[str, Any]:
    """Process a single Frida capture through the full decoder pipeline."""
    
    cap = parse_frida_capture(capture_path)
    keybuf = load_keybuf(keybuf_path)
    handler_map = load_handler_map(handler_map_path)
    
    decoded = decode_frida_capture(cap, keybuf, handler_map)
    string_pool = extract_string_pool(cap)
    pseudo_php = emit_pseudo_php(decoded, cap, string_pool)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = capture_path.stem
    
    # Save decoded ops
    decoded_data = {
        'filename': cap.get('filename'),
        'last': cap.get('last'),
        'keyidx': cap.get('keyidx'),
        'base': cap.get('base'),
        'flags_a4': cap.get('flags_a4'),
        'ops': [
            {
                'index': op.index,
                'handler_name': op.handler_name,
                'handler_addr': hex(op.handler_addr),
                'op1': hex(op.op1),
                'op2': hex(op.op2),
                'result': hex(op.result),
                'ext': op.ext,
                'lineno': op.lineno,
                'op1_type': op.decoded_op1_type,
                'op2_type': op.decoded_op2_type,
                'op1_type_name': op.op1_type_name,
                'op2_type_name': op.op2_type_name,
            }
            for op in decoded
        ],
        'literals': cap.get('lits', []),
        'bitmap': cap.get('bitmap', []),
    }
    
    with open(output_dir / f"{base_name}_decoded.json", 'w') as f:
        json.dump(decoded_data, f, indent=2)
    
    with open(output_dir / f"{base_name}_pseudo.php", 'w') as f:
        f.write(pseudo_php)
    
    return {
        'capture': str(capture_path),
        'decoded_count': len(decoded),
        'handler_map_hits': sum(1 for op in decoded if not op.handler_name.startswith('UNKNOWN')),
        'output_dir': str(output_dir),
    }


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python3 full_decoder.py <capture.json> <keybuf.json> <handler_map.txt> [output_dir]")
        sys.exit(1)
    
    capture_path = Path(sys.argv[1])
    keybuf_path = Path(sys.argv[2])
    handler_map_path = Path(sys.argv[3])
    output_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else Path('/tmp/opencode/decoded')
    
    result = process_capture(capture_path, keybuf_path, handler_map_path, output_dir)
    print(json.dumps(result, indent=2))