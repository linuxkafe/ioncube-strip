#!/usr/bin/env python3
"""
Final decoder for ionCube VM captures.
Uses Frida capture JSON + keybuf JSON + handler map -> pseudo-PHP output.
"""

import json
import sys
import struct

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def sext64(val):
    """Sign-extend 32-bit value to 64-bit as per ionCube handler decryption."""
    val = val & 0xFFFFFFFF
    if val & 0x80000000:
        val |= 0xFFFFFFFF00000000
    return val

def decode_handler(raw_lo, raw_hi, keybuf, idx):
    """Decode a single handler using the keybuf."""
    if idx >= len(keybuf):
        return raw_lo, raw_hi, False
    k = keybuf[idx]
    key64 = sext64(k * 0x01010101)
    raw64 = (raw_hi << 32) | raw_lo
    decoded = raw64 ^ key64
    return decoded & 0xFFFFFFFF, (decoded >> 32) & 0xFFFFFFFF, True

# Handler map from lib/handler_map_final.json
HANDLER_MAP = {}

def load_handler_map(path):
    global HANDLER_MAP
    with open(path, 'r') as f:
        data = json.load(f)
    HANDLER_MAP.clear()
    for handler_id_str, info in data.get('handlers', {}).items():
        handler_id = int(handler_id_str, 16)
        HANDLER_MAP[handler_id] = info

def decode_capture(capture_path, keybuf_path, handler_map_path, output_path):
    cap_data = load_json(capture_path)
    keybuf = load_json(keybuf_path)
    load_handler_map(handler_map_path)
    
    filename = cap_data.get('filename', 'unknown')
    last = cap_data.get('last', 0)
    keyidx = cap_data.get('keyidx', 0)
    ops = cap_data.get('ops', [])
    lits = cap_data.get('lits', [])
    bitmap = cap_data.get('bitmap', [])
    base_str = cap_data.get('base', '0x0')
    loader_base = int(base_str, 16)
    loader_base_lower32 = loader_base & 0xFFFFFFFF
    
    print(f"Decoding {filename}: keyidx={keyidx}, last={last}, ops={len(ops)}")
    print(f"  Loader base: {base_str}, lower32: 0x{loader_base_lower32:08x}")
    
    out_lines = []
    out_lines.append(f"<?php")
    out_lines.append(f"// Decoded from {filename}")
    out_lines.append(f"// Keyidx: {keyidx}")
    out_lines.append(f"// Oplines: {last}")
    out_lines.append(f"// Loader base: {base_str}")
    
    matched = 0
    unknown = 0
    
    for i, op in enumerate(ops):
        raw_lo = op.get('handler_lo', 0)
        raw_hi = op.get('handler_hi', 0)
        
        dec_lo, dec_hi, ok = decode_handler(raw_lo, raw_hi, keybuf, i)
        handler_id_64 = (dec_hi << 32) | dec_lo
        handler_id_32 = handler_id_64 & 0xFFFFFFFF
        
        # Subtract loader base lower 32 bits to get offset for handler map
        offset_32 = (handler_id_32 - loader_base_lower32) & 0xFFFFFFFF
        
        handler_info = HANDLER_MAP.get(offset_32)
        if handler_info:
            name = handler_info.get('name', f'UNKNOWN_0x{offset_32:08x}')
            confidence = handler_info.get('confidence', 'unknown')
            matched += 1
        else:
            name = f'UNKNOWN_0x{offset_32:08x}'
            confidence = 'unknown'
            unknown += 1
        
        op1 = op.get('op1', '0x0')
        op2 = op.get('op2', '0x0')
        result = op.get('result', '0x0')
        ext = op.get('ext', 0)
        lineno = op.get('lineno', 0)
        op1_type = op.get('op1_type', 0)
        op2_type = op.get('op2_type', 0)
        result_type = op.get('result_type', 0)
        bm = op.get('bitmap', 0)
        
        def fmt_op(ptr, typ):
            if ptr == '0x0':
                return 'NULL'
            if typ == 1:
                return f'CONST({ptr})'
            elif typ == 2:
                return f'TMP({ptr})'
            elif typ == 4:
                return f'VAR({ptr})'
            elif typ == 8:
                return f'CV({ptr})'
            elif typ == 16:
                return 'UNUSED'
            return f'OP_{typ}({ptr})'
        
        out_lines.append(f"    {i:3d}: {name:30s} {fmt_op(op1, op1_type):20s} {fmt_op(op2, op2_type):20s} {fmt_op(result, result_type):20s} ext={ext} ln={lineno} bm={bm}")
    
    out_lines.append(f"// Matched handlers: {matched}, Unknown: {unknown}")
    out_lines.append(f"?>")
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(out_lines))
    
    print(f"Written to {output_path}")
    print(f"Matched handlers: {matched}, Unknown: {unknown}")
    return True

def main():
    if len(sys.argv) != 5:
        print("Usage: decoder_final.py <capture.json> <keybuf.json> <handler_map.json> <output.php>")
        sys.exit(1)
    
    decode_capture(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

if __name__ == '__main__':
    main()
