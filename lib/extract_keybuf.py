#!/usr/bin/env python3
"""
Extract keybuf arrays from brute-force results and decode all handlers.
"""

import json

def sign_extend_64_from_32(v):
    v &= 0xffffffff
    if v & 0x80000000:
        v |= 0xffffffff00000000
    return v

def decode_handler(raw, k):
    pattern = (k * 0x01010101) & 0xffffffff
    return raw ^ (pattern | (0xffffffff00000000 if pattern >= 0x80000000 else 0))

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
                handler_map[addr] = parts[1]
            except: pass

for name, cap in caps.items():
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    keyidx = cap['keyidx']
    print(f"\n=== {name} (keyidx={keyidx}) ===")
    
    keybuf = {}
    decoded_ops = []
    
    for op in cap['ops']:
        i = op['i']
        lo = op['handler_lo']
        hi = op['handler_hi']
        raw = (hi << 32) | (lo & 0xffffffff)
        base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
        
        # Find the keybuf value that maps this handler into loader range
        loader_start = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
        loader_end = loader_start + 0x200000
        
        target_high = loader_start & 0xffffffff00000000
        target_high_next = target_high + 0x100000000
        
        raw_high = raw & 0xffffffff00000000
        
        diff1 = raw & 0xffffffff00000000 ^ (loader_start & 0xffffffff00000000)
        diff2 = raw & 0xffffffff00000000 ^ ((loader_start + 0x200000) & 0xffffffff00000000)
        
        possible_ph = set()
        if diff1 in (0, 0xffffffff00000000):
            possible_ph.add(diff1)
        if (raw & 0xffffffff00000000 ^ ((loader_start + 0x200000) & 0xffffffff00000000)) in (0, 0xffffffff00000000):
            possible_ph.add(raw & 0xffffffff00000000 ^ ((loader_start + 0x200000) & 0xffffffff00000000))
        
        found_k = None
        for ph in possible_ph:
            if ph == 0:
                max_k = 0x80000000 // 0x01010101
                for k in range(max_k + 1):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern < 0x80000000:
                        decoded = raw ^ pattern
                        if loader_start <= decoded < loader_start + 0x200000:
                            keybuf[i] = k
                            break
            else:
                min_k = 0x80000000 // 0x01010101
                for k in range(0x80000000 // 0x01010101, 256):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern >= 0x80000000:
                        decoded = raw ^ (pattern | 0xffffffff00000000)
                        if loader_start <= decoded < loader_start + 0x200000:
                            keybuf[i] = k
                            break
    
    print(f"\n{name}: extracted {len(keybuf)} keybuf entries")
    
    # Now decode all handlers
    print(f"\nDecoded handlers for {name}:")
    for op in cap['ops']:
        i = op['i']
        raw = (op['handler_hi'] << 32) | (op['handler_lo'] & 0xffffffff)
        if i in keybuf:
            k = keybuf[i]
            pattern = (k * 0x01010101) & 0xffffffff
            if pattern >= 0x80000000:
                pattern |= 0xffffffff00000000
            dec = raw ^ pattern
            handler_name = f"UNKNOWN_{dec:#x}"
            # Try to match with handler_map
            for addr, hname in handler_map.items():
                if dec == 0x100000 + addr:
                    handler_name = hname
                    break
            else:
                handler_name = f"UNKNOWN_{dec:#x}"
            print(f"  op[{i:2d}] k={keybuf[i]:#04x} raw={raw:#018x} -> dec={dec:#018x} ({handler_name})")
        else:
            print(f"  op[{i:2d}] NO KEYBUF raw={raw:#018x}")

# Load handler map
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

for name, cap in caps.items():
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    loader_start = base
    loader_end = base + 0x200000
    keybuf = {}
    
    for op in cap['ops']:
        i = op['i']
        lo = op['handler_lo']
        hi = op['handler_hi']
        raw = (hi << 32) | (lo & 0xffffffff)
        
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
                        if loader_start <= decoded < loader_start + 0x200000:
                            keybuf[i] = k
                            break
            else:
                min_k = 0x80000000 // 0x01010101
                for k in range(0x80000000 // 0x01010101, 256):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern >= 0x80000000:
                        decoded = raw ^ (pattern | 0xffffffff00000000)
                        if loader_start <= decoded < loader_start + 0x200000:
                            keybuf[i] = k
                            break
    
    print(f"\n{name}: extracted {len(keybuf)} keybuf entries")
    # Decode all
    for op in cap['ops']:
        i = op['i']
        raw = (op['handler_hi'] << 32) | (op['handler_lo'] & 0xffffffff)
        if i in keybuf:
            k = keybuf[i]
            pattern = (k * 0x01010101) & 0xffffffff
            if pattern >= 0x80000000:
                pattern |= 0xffffffff00000000
            dec = raw ^ pattern
            print(f"  op[{i:2d}] k={keybuf[i]:#04x} raw={raw:#018x} -> dec={dec:#018x}")
