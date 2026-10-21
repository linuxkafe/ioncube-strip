#!/usr/bin/env python3
"""
lib/body_stream.py — Parse RESERVED[3] body stream from arm56 dumps.

The RESERVED[3] slot points to a per-function structure allocated by the
ionCube loader. Key layout (from _su3jdmx disassembly and empirical dumps):

  +0x00  ptr to something (vtable?)
  +0x08  keyidx (int32)  — selects keybuf from loader's keybuf_ptr_array[keyidx]
  +0x10  ?
  +0x18  0xffffffff
  +0x20  bitmap_ptr  — operand-type decryption bitmap
  +0x28  encrypted_opcodes_ptr  — ^ pad = real opcode array
  +0x30  extra_buffer_ptr
  +0x38  packed: low=last, high=?
  +0x40  ?
  +0x48  ?
  +0x50  ?
  +0x58  ?
  +0x60  ?
  +0x68  runtime_opcodes_ptr  — after XOR decode
  +0x70  encrypted_opcodes_ptr (duplicate of +0x28)
  +0x78  pad_source_ptr  — used in _su3jdmx XOR
  +0x80  ?
  +0x88  ?
  +0x90  flags_ptr
  +0x98  last (int32)  — number of oplines
  +0xa0  section_len_1 (e.g., 0x41 = 65)
  +0xa8  section_len_2 (e.g., 0xb1 = 177)
  +0xb0  string_section_ptr  — inline filename + decoded strings
  +0xb8  string_section_ptr (duplicate)
  +0xc0  ?
  +0xd0  ?
  +0xd8  ?
  +0xe0  section_len_3 (e.g., 0x89 = 137)
  +0xe8  section_len_4 (e.g., 0x41 = 65)
  +0xf0  inline_string_start  — e.g., "registered_", build path

The opcode array is at runtime_opcodes_ptr (+0x68 value), containing
last * 48-byte zend_op structs.

The handlers in the opcode array are XOR-encrypted:
  decoded = raw ^ sign_extend64(keybuf[opline_index] * 0x01010101)

Operand types are XOR-encrypted per opline using bitmap at +0x20.

This module parses the arm56 dump file and extracts:
- keyidx
- section lengths
- opcode array pointer
- string section pointer
- raw opcode stream (for external decoder)
"""

import re
import struct
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Reserved3Header:
    """Parsed header fields from RESERVED[3] structure."""
    slot_addr: int
    keyidx: int
    bitmap_ptr: int
    encrypted_opcodes_ptr: int
    extra_buffer_ptr: int
    runtime_opcodes_ptr: int
    pad_source_ptr: int
    flags_ptr: int
    last: int
    section_len_1: int
    section_len_2: int
    section_len_3: int
    section_len_4: int
    string_section_ptr: int
    inline_string_offset: int  # offset from slot where inline strings start


@dataclass
class ZendOp:
    """PHP 5.6 zend_op (48 bytes)."""
    handler: int
    op1: int
    op2: int
    result: int
    extended_value: int
    lineno: int
    op1_type: int
    op2_type: int
    raw_handler: int  # before decryption
    raw_op1: int
    raw_op2: int
    raw_result: int


def parse_hex_dump(dump_path: Path) -> bytes:
    """Parse arm56 hex dump file into raw bytes with signed offsets from slot."""
    buf = {}
    slot = None
    
    with open(dump_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            # Header: [RESERVED[3]=0x71f1aa28b080] window back=131072 fwd=1048576
            m = re.match(r'\[RESERVED\[3\]=0x([0-9a-f]+)\] window back=(\d+) fwd=(\d+)', line)
            if m:
                slot = int(m.group(1), 16)
                continue
            
            # Old format: [RESERVED[3]=0x771a841ef7c8] 32KB snapshot
            m = re.match(r'\[RESERVED\[3\]=0x([0-9a-f]+)\] 32KB snapshot', line)
            if m:
                slot = int(m.group(1), 16)
                continue
            
            # Data lines:   ffff0100: 76 61 6c 69 64 54 61 62 6c 65 73 00 ...
            m = re.match(r'^\s+([0-9a-f]{8}):((?: [0-9a-f]{2})+)', line)
            if m:
                offs = int(m.group(1), 16)
                # Signed 32-bit offset from slot
                if offs >= 0x80000000:
                    offs -= 0x100000000
                hex_bytes = m.group(2).strip().split()
                buf[offs] = bytes(int(x, 16) for x in hex_bytes)
    
    if slot is None:
        raise ValueError(f"No slot address found in {dump_path}")
    
    # Reconstruct contiguous byte array
    if not buf:
        return b''
    
    lo = min(buf.keys())
    hi = max(buf.keys()) + len(buf[max(buf.keys())])
    blob = bytearray(hi - lo)
    for offs, by in buf.items():
        blob[offs - lo:offs - lo + len(by)] = by
    
    return bytes(blob), slot, lo


def read_qword(blob: bytes, base: int, offset: int) -> int:
    """Read little-endian qword at base+offset."""
    return struct.unpack_from('<Q', blob, base + offset)[0]


def read_dword(blob: bytes, base: int, offset: int) -> int:
    """Read little-endian dword at base+offset."""
    return struct.unpack_from('<I', blob, base + offset)[0]


def parse_reserved3(blob: bytes, slot: int, lo: int) -> Reserved3Header:
    """Parse RESERVED[3] header from blob."""
    base = -lo  # slot is at offset -lo in blob
    
    def q(off): return read_qword(blob, base, off)
    def d(off): return read_dword(blob, base, off)
    
    keyidx = d(0x08)
    bitmap_ptr = q(0x20)
    encrypted_opcodes_ptr = q(0x28)
    extra_buffer_ptr = q(0x30)
    runtime_opcodes_ptr = q(0x68)
    pad_source_ptr = q(0x78)
    flags_ptr = q(0x90)
    last = d(0x98)
    section_len_1 = d(0xa0)
    section_len_2 = d(0xa8)
    section_len_3 = d(0xe0)
    section_len_4 = d(0xe8)
    string_section_ptr = q(0xb0)
    
    # Find inline string start (first non-zero after +0xf0)
    inline_string_offset = 0
    for off in range(0xf0, min(0x200, len(blob) - base)):
        if q(off) != 0:
            inline_string_offset = off
            break
    
    return Reserved3Header(
        slot_addr=slot,
        keyidx=keyidx,
        bitmap_ptr=bitmap_ptr,
        encrypted_opcodes_ptr=encrypted_opcodes_ptr,
        extra_buffer_ptr=extra_buffer_ptr,
        runtime_opcodes_ptr=runtime_opcodes_ptr,
        pad_source_ptr=pad_source_ptr,
        flags_ptr=flags_ptr,
        last=last,
        section_len_1=section_len_1,
        section_len_2=section_len_2,
        section_len_3=section_len_3,
        section_len_4=section_len_4,
        string_section_ptr=string_section_ptr,
        inline_string_offset=inline_string_offset,
    )


def extract_opcode_array(blob: bytes, base: int, header: Reserved3Header) -> bytes:
    """Extract the opcode array bytes from runtime_opcodes_ptr."""
    opcodes_rel = header.runtime_opcodes_ptr - header.slot_addr
    if opcodes_rel < 0:
        abs_off = base + opcodes_rel
    else:
        abs_off = base + opcodes_rel
    
    size = header.last * 48
    if abs_off < 0 or abs_off + size > len(blob):
        raise ValueError(f"Opcode array out of bounds: off={abs_off}, size={size}, blob={len(blob)}")
    
    return blob[abs_off:abs_off + size]


def parse_opcode_array(opcode_bytes: bytes) -> List[ZendOp]:
    """Parse raw opcode array into ZendOp structs."""
    ops = []
    for i in range(0, len(opcode_bytes), 48):
        chunk = opcode_bytes[i:i+48]
        if len(chunk) < 48:
            break
        handler, op1, op2, result = struct.unpack_from('<QQQQ', chunk, 0)
        extended_value, lineno = struct.unpack_from('<II', chunk, 32)
        op1_type = chunk[40]
        op2_type = chunk[44]
        ops.append(ZendOp(
            handler=handler, op1=op1, op2=op2, result=result,
            extended_value=extended_value, lineno=lineno,
            op1_type=op1_type, op2_type=op2_type,
            raw_handler=handler, raw_op1=op1, raw_op2=op2, raw_result=result,
        ))
    return ops


def extract_string_section(blob: bytes, base: int, header: Reserved3Header) -> bytes:
    """Extract the string section from string_section_ptr."""
    str_rel = header.string_section_ptr - header.slot_addr
    abs_off = base + str_rel
    
    # Read until double null or reasonable limit
    max_len = 8192
    if abs_off < 0 or abs_off >= len(blob):
        return b''
    
    end = abs_off
    while end < len(blob) and end < abs_off + max_len:
        if end + 1 < len(blob) and blob[end] == 0 and blob[end + 1] == 0:
            break
        end += 1
    
    return blob[abs_off:end]


def extract_inline_strings(blob: bytes, base: int, header: Reserved3Header) -> bytes:
    """Extract inline strings starting at inline_string_offset."""
    off = header.inline_string_offset
    if off == 0:
        return b''
    abs_off = base + off
    if abs_off < 0 or abs_off >= len(blob):
        return b''
    
    max_len = 4096
    end = abs_off
    while end < len(blob) and end < abs_off + max_len:
        if end + 1 < len(blob) and blob[end] == 0 and blob[end + 1] == 0:
            break
        end += 1
    
    return blob[abs_off:end]


def parse_dump(dump_path: Path) -> Dict[str, Any]:
    """Full parse of an arm56 RESERVED[3] dump file."""
    blob, slot, lo = parse_hex_dump(dump_path)
    base = -lo
    header = parse_reserved3(blob, slot, lo)
    
    # Extract components
    opcode_bytes = extract_opcode_array(blob, base, header)
    ops = parse_opcode_array(opcode_bytes)
    string_section = extract_string_section(blob, base, header)
    inline_strings = extract_inline_strings(blob, base, header)
    
    return {
        'dump_path': str(dump_path),
        'slot': hex(slot),
        'header': {
            'keyidx': header.keyidx,
            'bitmap_ptr': hex(header.bitmap_ptr),
            'encrypted_opcodes_ptr': hex(header.encrypted_opcodes_ptr),
            'runtime_opcodes_ptr': hex(header.runtime_opcodes_ptr),
            'pad_source_ptr': hex(header.pad_source_ptr),
            'flags_ptr': hex(header.flags_ptr),
            'last': header.last,
            'section_len_1': header.section_len_1,
            'section_len_2': header.section_len_2,
            'section_len_3': header.section_len_3,
            'section_len_4': header.section_len_4,
            'string_section_ptr': hex(header.string_section_ptr),
            'inline_string_offset': header.inline_string_offset,
        },
        'opcodes': [
            {
                'index': i,
                'handler': hex(op.raw_handler),
                'op1': hex(op.raw_op1),
                'op2': hex(op.raw_op2),
                'result': hex(op.raw_result),
                'extended_value': op.extended_value,
                'lineno': op.lineno,
                'op1_type': op.op1_type,
                'op2_type': op.op2_type,
            }
            for i, op in enumerate(ops)
        ],
        'string_section': string_section.decode('utf-8', errors='replace'),
        'inline_strings': inline_strings.decode('utf-8', errors='replace'),
    }


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 body_stream.py <dump_file>")
        sys.exit(1)
    
    result = parse_dump(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))