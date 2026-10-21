#!/usr/bin/env python3
"""
Build handler map from decoded Frida captures.
"""

import json
from collections import Counter, defaultdict

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

def extract_keybuf(cap):
    """Extract keybuf for a capture."""
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    keybuf = {}
    
    for op in cap['ops']:
        i = op['i']
        lo = op['handler_lo']
        hi = op['handler_hi']
        raw = (hi << 32) | (op['handler_lo'] & 0xffffffff)
        base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
        
        target_high = base & 0xffffffff00000000
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
                            return k
            else:
                min_k = 0x80000000 // 0x01010101
                for k in range(0x80000000 // 0x01010101, 256):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern >= 0x80000000:
                        decoded = raw ^ (pattern | 0xffffffff00000000)
                        if base <= decoded < base + 0x200000:
                            return k
    return None

def find_keybuf_for_op(raw, base):
    """Find keybuf value for a single opcode."""
    target_high = base & 0xffffffff00000000
    raw_high = raw & 0xffffffff00000000
    
    diff1 = raw & 0xffffffff00000000 ^ (base & 0xffffffff00000000)
    diff2 = raw & 0xffffffff00000000 ^ ((base + 0x200000) & 0xffffffff00000000)
    
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
                    if base <= raw ^ pattern < base + 0x200000:
                        return k
            else:
                min_k = 0x80000000 // 0x01010101
                for k in range(0x80000000 // 0x01010101, 256):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern >= 0x80000000:
                        decoded = raw ^ (pattern | 0xffffffff00000000)
                        if base <= decoded < base + 0x200000:
                            return k
    return None

# Main
handler_counts = Counter()
handler_details = defaultdict(lambda: {'count': 0, 'keyidxs': set(), 'keybuf_vals': set(), 'oplines': []})

for name, path in [
    ('include_compat', '/home/seyon/dev/ioncube-strip/captures/frida_capture_include_compat.json'),
    ('hash_1', '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_1.json'),
    ('hash_2', '/home/seyon/dev/ioncube-strip/captures/frida_capture_hash_2.json'),
]:
    with open(path) as f:
        cap = json.load(f)
    
    base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
    
    for op in cap['ops']:
        i = op['i']
        raw = (op['handler_hi'] << 32) | (op['handler_lo'] & 0xffffffff)
        base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
        
        k = None
        # Find keybuf for this opline
        target_high = base & 0xffffffff00000000
        raw_high = raw & 0xffffffff00000000
        
        diff1 = raw & 0xffffffff00000000 ^ (base & 0xffffffff00000000)
        diff2 = raw & 0xffffffff00000000 ^ ((base + 0x200000) & 0xffffffff00000000)
        
        possible_ph = set()
        if diff1 in (0, 0xffffffff00000000):
            possible_ph.add(diff1)
        if (raw & 0xffffffff00000000 ^ ((base + 0x200000) & 0xffffffff00000000)) in (0, 0xffffffff00000000):
            possible_ph.add(raw & 0xffffffff00000000 ^ ((base + 0x200000) & 0xffffffff00000000))
        
        k = None
        for ph in possible_ph:
            if ph == 0:
                max_k = 0x80000000 // 0x01010101
                for k in range(max_k + 1):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern < 0x80000000:
                        decoded = raw ^ pattern
                        if base <= decoded < base + 0x200000:
                            k = k
                            break
                if k is not None: break
            else:
                min_k = 0x80000000 // 0x01010101
                for k in range(0x80000000 // 0x01010101, 256):
                    pattern = (k * 0x01010101) & 0xffffffff
                    if pattern >= 0x80000000:
                        decoded = raw ^ (pattern | 0xffffffff00000000)
                        if base <= decoded < base + 0x200000:
                            k = k
                            break
                if k is not None: break
        
        if k is not None:
            base = int(cap['base'], 16) if isinstance(cap['base'], str) else cap['base']
            offset = (raw ^ (k * 0x01010101 & 0xffffffff | (0xffffffff00000000 if (k * 0x01010101 & 0xffffffff) >= 0x80000000 else 0))) - base
            
            pattern = (k * 0x01010101) & 0xffffffff
            if pattern >= 0x80000000:
                pattern |= 0xffffffff00000000
            dec = raw ^ pattern
            offset = dec - base
            
            handler_counts[offset] += 1
            handler_details[offset]['count'] += 1
            handler_details[offset]['keyidxs'].add(cap['keyidx'])
            handler_details[offset]['keybuf_vals'].add(k)
            handler_details[offset]['oplines'].append((name, i))

# Print top handlers
print("=== TOP HANDLERS BY FREQUENCY ===")
for offset, count in handler_counts.most_common(40):
    detail = handler_details[offset]
    print(f"  offset {offset:#08x} (0x{offset:x}): count={count}, keyidxs={detail['keyidxs']}, keybuf_vals={sorted(detail['keybuf_vals'])}")

# Find consistent handlers
print("\n=== CONSISTENT HANDLERS (appear in multiple captures or high frequency) ===")
for offset, detail in handler_details.items():
    if len(detail['keyidxs']) > 1 or detail['count'] > 5:
        print(f"  offset {offset:#08x} (0x{offset:x}): count={detail['count']}, keyidxs={detail['keyidxs']}, keybuf_vals={sorted(detail['keybuf_vals'])}")
