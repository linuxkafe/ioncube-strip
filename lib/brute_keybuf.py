#!/usr/bin/env python3
"""
Brute-force keybuf by finding values that map raw handlers into the loader range.
"""

import json

def sign_extend_64_from_32(v):
    v &= 0xffffffff
    if v & 0x80000000:
        v |= 0xffffffff00000000
    return v

def decode_handler(raw, k):
    pattern = (k * 0x01010101) & 0xffffffff
    return raw ^ sign_extend_64_from_32(pattern)

def load_handler_map():
    hm = {}
    with open('/home/seyon/dev/ioncube-strip/lib/handler_map.txt') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    addr = int(parts[0], 0)
                    hm[addr] = parts[1]
                except: pass
    return hm

def load_capture(path):
    with open(path) as f:
        return json.load(f)

caps = {
    'include_compat': load_capture('/home/seyon/dev/ioncube-strip/captures/frida_capture_include_compat.json'),
    'hash_1': load_capture('/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_1.json'),
    'hash_2': load_capture('/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_2.json'),
}

handler_map = {}
with open('/home/seyon/dev/ioncube-strip/lib/handler_map.txt') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                addr = int(parts[0], 0)
                hm[addr] = parts[1]
            except: pass

ghidra_base = 0x100000

print("=== Finding keybuf by checking which values map handlers into loader range ===\n")

for name, cap in caps.items():
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    keyidx = cap['keyidx']
    print(f"\n=== {name} (keyidx={cap['keyidx']}, base={hex(base)}) ===")
    
    loader_start = base
    loader_end = base + 0x200000
    
    for op in cap['ops']:
        i = op['i']
        lo = op['handler_lo']
        hi = op['handler_hi']
        raw = (hi << 32) | (lo & 0xffffffff)
        
        valid_k = set()
        loader_start = base
        loader_end = base + 0x200000
        
        target_high = base & 0xffffffff00000000
        target_high_next = target_high + 0x100000000
        
        raw_high = raw & 0xffffffff00000000
        
        diff1 = raw & 0xffffffff00000000 ^ target_high
        diff2 = raw & 0xffffffff00000000 ^ (target_high + 0x100000000)
        
        possible_pattern_high = set()
        if diff1 in (0, 0xffffffff00000000):
            possible_pattern_high.add(diff1)
        if (raw & 0xffffffff00000000 ^ (target_high + 0x100000000)) in (0, 0xffffffff00000000):
            possible_pattern_high.add(raw & 0xffffffff00000000 ^ (target_high + 0x100000000))
        
        if not possible_pattern_high:
            continue
        
        valid_k = set()
        for ph in possible_pattern_high:
            if ph == 0:
                max_k = 0x80000000 // 0x01010101
                for k in range(max_k + 1):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern < 0x80000000:
                        decoded = raw ^ pattern
                        if base <= decoded < base + 0x200000:
                            valid_k.add(k)
            else:
                min_k = 0x80000000 // 0x01010101
                for k in range(0x80000000 // 0x01010101, 256):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern >= 0x80000000:
                        decoded = raw ^ (pattern | 0xffffffff00000000)
                        if base <= decoded < base + 0x200000:
                            valid_k.add(k)
        
        if valid_k:
            print(f"  opline {i}: {len(valid_k)} valid keybuf values")
            for k in sorted(valid_k)[:5]:
                pattern = (k * 0x01010101) & 0xffffffff
                if pattern >= 0x80000000:
                    decoded = raw ^ (pattern | 0xffffffff00000000)
                else:
                    decoded = raw ^ pattern
                print(f"  k={hex(k)} -> decoded={hex(decoded)}")

print("\n=== Checking first few oplines of _hash against known handlers ===")
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

ghidra_base = 0x100000

for name in ['hash_1', 'hash_2']:
    cap = caps[name]
    print(f"\n{name}:")
    for op in cap['ops'][:10]:
        i = op['i']
        raw = (op['handler_hi'] << 32) | (op['handler_lo'] & 0xffffffff)
        for addr, hname in sorted(handler_map.items()):
            for pattern_high in [0, 0xffffffff00000000]:
                target_addr = 0x100000 + addr
                pattern = raw ^ target_addr
                if (pattern & 0xffffffff00000000) != 0 and (pattern & 0xffffffff00000000) != 0xffffffff00000000:
                    continue
                pattern32 = pattern & 0xffffffff
                inv = pow(0x01010101, -1, 2**32)
                k = (pattern32 * inv) % (2**32)
                test_pattern = (k * 0x01010101) & 0xffffffff
                if test_pattern == (pattern & 0xffffffff):
                    if pattern_high == 0 and test_pattern < 0x80000000:
                        print(f"  op[{i}] k={hex(k)} -> {addr:#x} ({handler_map.get(addr, 'UNKNOWN')})")
                    elif pattern_high != 0 and test_pattern >= 0x80000000:
                        print(f"  op[{i}] k={hex(k)} -> {addr:#x} ({handler_map.get(addr, 'UNKNOWN')})")

