#!/usr/bin/env python3
"""
Batch process WHMCS ionCube files through the decoder pipeline.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Configuration
WHMCS_ROOT = '/home/seyon/dev/whmcs-original'
OUTPUT_DIR = '/home/seyon/dev/ioncube-strip/batch_output'
CAPTURE_DIR = os.path.join(OUTPUT_DIR, 'captures')
DECODED_DIR = os.path.join(OUTPUT_DIR, 'decoded')
KEYBUF_DIR = '/home/seyon/dev/ioncube-strip/captures'
HANDLER_MAP = '/home/seyon/dev/ioncube-strip/lib/handler_map_final.json'
DECODER = '/home/seyon/dev/ioncube-strip/lib/decoder_final.py'
FRIDA_SCRIPT = '/home/seyon/dev/ioncube-strip/lib/ioncube_json_capture2.js'

# Known working keybufs
KNOWN_KEYBUFS = {
    31: os.path.join(KEYBUF_DIR, 'keybuf_31.json'),
    63: os.path.join(KEYBUF_DIR, 'keybuf_63.json'),
}

for d in [OUTPUT_DIR, CAPTURE_DIR, DECODED_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)

def find_encoded_files(root):
    encoded = []
    for php_file in Path(root).rglob('*.php'):
        try:
            with open(php_file, 'rb') as f:
                content = f.read(5000)
                if b'ionCube Loader' in content or b'_il_exec' in content:
                    encoded.append(str(php_file))
        except:
            pass
    return encoded

def create_harness(php_file, stem):
    rel_path = Path(php_file).relative_to(WHMCS_ROOT)
    harness = f'''<?php
define("ROOTDIR", "/var/www/html");
define("WHMCSDIR", "/var/www/html");
error_reporting(0);
sleep(5);
include "{rel_path}";
$funcs = get_defined_functions();
if (isset($funcs["user"])) {{
    foreach ($funcs["user"] as $fn) {{
        try {{
            $r = new ReflectionFunction($fn);
            if ($r->getFileName() === realpath("/var/www/html/{rel_path}") && $r->getNumberOfRequiredParameters() === 0) {{
                @call_user_func($fn);
            }}
        }} catch (Throwable $e) {{}}
    }}
}}
echo "DONE\\n";
sleep(30);
'''
    harness_path = f'/tmp/harness_{stem}.php'
    with open(harness_path, 'w') as f:
        f.write(harness)
    return harness_path

def run_frida_capture(harness_path, stem):
    capture_file = f'/tmp/frida_capture_{stem}.txt'
    cmd = [
        '/usr/local/bin/frida',
        '-f', '/usr/bin/php5.6',
        '-l', FRIDA_SCRIPT,
        '--', '-c', '/tmp/arm56.ini', harness_path
    ]
    try:
        result = subprocess.run(cmd, timeout=180, capture_output=True, text=True, cwd='/var/www/html')
        # Save stdout to capture file
        with open(capture_file, 'w') as f:
            f.write(result.stdout)
        return capture_file if os.path.exists(capture_file) and os.path.getsize(capture_file) > 1000 else None
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        print(f"Frida error: {e}")
        return None

def extract_captures(capture_file, stem, output_dir):
    """Extract OPARRAYs and keybufs from Frida output."""
    with open(capture_file, 'r') as f:
        content = f.read()
    
    import re, ast
    positions = [m.start() for m in re.finditer(r"message:", content)]
    
    oparray_count = 0
    keybuf_saved = set()
    
    for i, pos in enumerate(positions):
        end_pos = positions[i+1] if i+1 < len(positions) else len(content)
        message_text = content[pos:end_pos]
        
        msg_start = message_text.find("{")
        if msg_start == -1:
            continue
        msg_end = message_text.find("}}")
        if msg_end == -1:
            continue
        msg_dict_str = message_text[msg_start:msg_end+2]
        
        try:
            msg_dict = ast.literal_eval(msg_dict_str)
            payload = msg_dict.get("payload", {})
            data_type = payload.get("type")
            
            if data_type == "oparray":
                out_file = os.path.join(output_dir, f"capture_{stem}_{oparray_count}.json")
                with open(out_file, 'w') as f:
                    json.dump(payload, f, indent=2)
                print(f"  Saved OPARRAY {oparray_count}: keyidx={payload.get('keyidx')} last={payload.get('last')}")
                oparray_count += 1
            elif data_type == "keybuf":
                keyidx = payload.get("keyidx")
                if keyidx not in keybuf_saved:
                    out_file = os.path.join(output_dir, f"keybuf_{keyidx}.json")
                    with open(out_file, 'w') as f:
                        json.dump(payload["data"], f, indent=2)
                    print(f"  Saved KEYBUF keyidx={keyidx}: {len(payload['data'])} entries")
                    keybuf_saved.add(keyidx)
        except Exception as e:
            pass
    
    return oparray_count

def decode_capture(capture_path, keyidx, output_path):
    """Decode a capture using the appropriate keybuf."""
    keybuf_path = KNOWN_KEYBUFS.get(keyidx)
    if not keybuf_path or not os.path.exists(keybuf_path):
        # Try captured keybuf in capture dir
        keybuf_path = os.path.join(CAPTURE_DIR, f'keybuf_{keyidx}.json')
        if not os.path.exists(keybuf_path):
            print(f"  No keybuf for keyidx={keyidx}")
            return False
    
    cmd = [
        'python3', DECODER,
        capture_path,
        keybuf_path,
        HANDLER_MAP,
        output_path
    ]
    try:
        result = subprocess.run(cmd, timeout=60, capture_output=True, text=True)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        print(f"Decode error: {e}")
        return False

def process_file(php_file):
    stem = Path(php_file).stem
    rel_path = Path(php_file).relative_to(WHMCS_ROOT)
    print(f"\nProcessing: {rel_path}")
    
    # Create harness
    harness_path = create_harness(php_file, stem)
    
    # Run Frida capture
    print("  Running Frida capture...")
    capture_file = run_frida_capture(harness_path, stem)
    if not capture_file:
        print("  FAILED: Frida capture failed")
        return False
    
    # Extract captures
    print("  Extracting captures...")
    oparray_count = extract_captures(capture_file, stem, CAPTURE_DIR)
    if oparray_count == 0:
        print("  FAILED: No OPARRAYs captured")
        return False
    
    # Decode each OPARRAY
    success_count = 0
    for i in range(oparray_count):
        capture_path = os.path.join(CAPTURE_DIR, f"capture_{stem}_{i}.json")
        if not os.path.exists(capture_path):
            continue
        
        with open(capture_path, 'r') as f:
            cap_data = json.load(f)
        keyidx = cap_data.get('keyidx', 0)
        
        output_path = os.path.join(DECODED_DIR, f"decoded_{stem}_{i}.php")
        print(f"  Decoding OPARRAY {i} (keyidx={keyidx})...")
        if decode_capture(capture_path, keyidx, output_path):
            success_count += 1
            print(f"  SUCCESS: {output_path}")
        else:
            print(f"  FAILED: keyidx={keyidx}")
    
    return success_count > 0

def main():
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    else:
        limit = 10
    
    print("=" * 60)
    print("BATCH IONCUBE DECODER - PRODUCTION")
    print("=" * 60)
    
    print("Scanning for encoded files...")
    encoded_files = find_encoded_files(WHMCS_ROOT)
    print(f"Found {len(encoded_files)} encoded files")
    
    encoded_files = encoded_files[:limit]
    print(f"Processing {limit} files...")
    
    start_time = time.time()
    stats = {'processed': 0, 'success': 0, 'failed': 0}
    
    for i, php_file in enumerate(encoded_files):
        stats['processed'] += 1
        print(f"\n[{i+1}/{len(encoded_files)}] {Path(php_file).relative_to(WHMCS_ROOT)}")
        
        try:
            if process_file(php_file):
                stats['success'] += 1
            else:
                stats['failed'] += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            stats['failed'] += 1
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Total processed: {stats['processed']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Time elapsed: {elapsed:.1f}s")
    
    with open(os.path.join(OUTPUT_DIR, 'batch_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)

if __name__ == '__main__':
    main()
