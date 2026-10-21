#!/usr/bin/env python3
"""
Decode all captured OPARRAYs using extracted keybufs and match to handler_map.
"""

import json

def sign_extend_64_from_32(v):
    v &= 0xffffffff
    if v & 0x80000000:
        v |= 0xffffffff00000000
    return v

def decode_handler(raw, k):
    pattern = (k * 0x01010101) & 0xffffffff
    if pattern >= 0x80000000:
        pattern |= 0xffffffff00000000
    return raw ^ pattern

# Load handler map (Ghidra offsets from base 0x100000)
handler_map = {}
with open('/home/seyon/dev/ioncube-strip/lib/handler_map.txt') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                addr = int(parts[0], 0)
                handler_map[addr] = parts[1]
            except: pass

caps = {
    'include_compat': '/home/seyon/dev/ioncube-strip/captures/frida_capture_include_compat.json',
    'hash_1': '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_1.json',
    'hash_2': '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_2.json',
}

keybufs = {}
for kidx in [31, 63]:
    with open(f'/home/seyon/dev/ioncube-strip/captures/keybuf_{kidx}.json') as f:
        keybufs[kidx] = json.load(f)

print("=== DECODING ALL CAPTURES ===\n")

for name, path in [
    ('include_compat', '/home/seyon/dev/ioncube-strip/captures/frida_capture_include_compat.json'),
    ('hash_1', '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_1.json'),
    ('hash_2', '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_2.json'),
]:
    with open(path) as f:
        cap = json.load(f)
    
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    keyidx = cap['keyidx']
    keybuf = keybufs[cap['keyidx']]
    
    print(f"\n{'='*60}")
    print(f"=== {name} (keyidx={cap['keyidx']}, base={hex(base)}) ===")
    print(f"{'='*60}")
    
    matched = 0
    unknown = 0
    
    for op in cap['ops']:
        i = op['i']
        raw = (op['handler_hi'] << 32) | (op['handler_lo'] & 0xffffffff)
        
        k = keybuf[i] if i < len(keybuf) else 0
        pattern = (k * 0x01010101) & 0xffffffff
        if pattern >= 0x80000000:
            pattern |= 0xffffffff00000000
        dec = raw ^ pattern
        
        # Convert runtime address to Ghidra offset
        # Runtime address = runtime_base + offset
        # Ghidra offset = runtime_address - runtime_base + 0x100000
        ghidra_offset = dec - int(cap['base'], 16) + 0x100000
        
        handler_name = handler_map.get(ghidra_offset, f"UNKNOWN_{ghidra_offset:#x}")
        
        if ghidra_offset in handler_map:
            matched += 1
            status = "MATCH"
        else:
            unknown += 1
            status = "UNKNOWN"
        
        print(f"  op[{i:2d}] k={k:#04x} raw={raw:#018x} -> dec={dec:#018x} ghidra_off={ghidra_offset:#x} {status}: {handler_name}")

