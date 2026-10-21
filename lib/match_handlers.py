#!/usr/bin/env python3
"""
Match decoded handlers to handler_map and build complete keybuf arrays.
"""

import json

def load_capture(path):
    with open(path) as f:
        return json.load(f)

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

for name, path in [
    ('include_compat', '/home/seyon/dev/ioncube-strip/captures/frida_capture_include_compat.json'),
    ('hash_1', '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_1.json'),
    ('hash_2', '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_2.json'),
]:
    with open(path) as f:
        cap = json.load(f)
    
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    keybuf = {}
    
    for op in cap['ops']:
        i = op['i']
        lo = op['handler_lo']
        hi = op['handler_hi']
        raw = (hi << 32) | (lo & 0xffffffff)
        base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
        loader_start = base
        loader_end = base + 0x200000
        
        target_high = base & 0xffffffff00000000
        target_high_next = target_high + 0x100000000
        raw_high = raw & 0xffffffff00000000
        
        diff1 = raw_high ^ (base & 0xffffffff00000000)
        diff2 = raw_high ^ ((base + 0x200000) & 0xffffffff00000000)
        
        possible_ph = set()
        if diff1 in (0, 0xffffffff00000000):
            possible_ph.add(diff1)
        if (raw & 0xffffffff00000000 ^ ((base + 0x200000) & 0xffffffff00000000)) in (0, 0xffffffff00000000):
            possible_ph.add(raw & 0xffffffff00000000 ^ ((base + 0x200000) & 0xffffffff00000000))
        
        for ph in possible_ph:
            if ph == 0:
                max_k = 0x80000000 // 0x01010101
                for k in range(max_k + 1):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern < 0x80000000:
                        decoded = raw ^ pattern
                        if base <= decoded < base + 0x200000:
                            keybuf[i] = k
                            break
            else:
                min_k = 0x80000000 // 0x01010101
                for k in range(0x80000000 // 0x01010101, 256):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern >= 0x80000000:
                        decoded = raw ^ (pattern | 0xffffffff00000000)
                        if base <= decoded < base + 0x200000:
                            keybuf[i] = k
                            break
    
    # Now build the complete keybuf array (256 entries)
    full_keybuf = [0] * 256
    for i, k in keybuf.items():
        full_keybuf[i] = k
    
    # Save keybuf
    out_path = f'/home/seyon/dev/ioncube-strip/captures/keybuf_{cap["keyidx"]}.json'
    with open(out_path, 'w') as f:
        json.dump(full_keybuf, f)
    print(f"Saved keybuf for keyidx={cap['keyidx']} to {out_path}")

