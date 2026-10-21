#!/usr/bin/env python3
"""
Batch process all ionCube-encoded WHMCS files through the decoder pipeline.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add lib to path
sys.path.insert(0, '/home/seyon/dev/ioncube-strip/lib')

# Configuration
WHMCS_ROOT = '/home/seyon/dev/whmcs-original'
OUTPUT_DIR = '/home/seyon/dev/ioncube-strip/batch_output'
CAPTURE_DIR = '/home/seyon/dev/ioncube-strip/batch_output/captures'
DECODED_DIR = '/home/seyon/dev/ioncube-strip/batch_output/decoded'
MAX_WORKERS = 2  # Frida is resource-intensive
TIMEOUT = 180  # seconds per file

# Ensure directories exist
for d in [OUTPUT_DIR, CAPTURE_DIR, DECODED_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)

# Global state
lock = threading.Lock()
stats = {'processed': 0, 'success': 0, 'failed': 0, 'errors': []}

def find_encoded_files(root):
    """Find all ionCube-encoded PHP files."""
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

def create_harness(php_file):
    """Create a test harness for a PHP file."""
    rel_path = Path(php_file).relative_to('/home/seyon/dev/whmcs-original')
    harness = f'''<?php
define("ROOTDIR", "/var/www/html");
define("WHMCSDIR", "/var/www/html");
error_reporting(0);
// Include the encoded file
include "/var/www/html/{rel_path}";
// Force execution of all functions in this file
$fns = get_defined_functions();
if (isset($fns["user"])) {{
    foreach ($fns["user"] as $fn) {{
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
    harness_path = f'/tmp/harness_{Path(php_file).stem}.php'
    with open(harness_path, 'w') as f:
        f.write(harness)
    return harness_path

def run_frida_capture(php_file, harness_path, output_file):
    """Run Frida capture on a single PHP file."""
    cmd = [
        '/usr/local/bin/frida',
        '-f', '/usr/bin/php5.6',
        '-l', '/home/seyon/dev/ioncube-strip/lib/ioncube_wait.js',
        '-o', output_file,
        '--', '-c', '/tmp/arm56.ini', harness_path
    ]
    
    try:
        result = subprocess.run(cmd, timeout=180, capture_output=True, text=True, cwd='/var/www/html')
        return Path(output_file).exists() and Path(output_file).stat().st_size > 1000
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        return False

def extract_keybuf(capture_path, keyidx):
    """Extract keybuf for a capture using brute-force."""
    keybuf_path = f'/home/seyon/dev/ioncube-strip/captures/keybuf_{keyidx}.json'
    if Path(keybuf_path).exists():
        with open(keybuf_path) as f:
            return json.load(f)
    return None

def decode_capture(capture_path, keyidx, output_path):
    """Decode a Frida capture using the decoder."""
    keybuf_path = f'/home/seyon/dev/ioncube-strip/captures/keybuf_{keyidx}.json'
    handler_map_path = '/home/seyon/dev/ioncube-strip/lib/handler_map_final.json'
    
    cmd = [
        'python3', '/home/seyon/dev/ioncube-strip/lib/decoder_final.py',
        capture_path,
        f'/home/seyon/dev/ioncube-strip/captures/keybuf_{keyidx}.json',
        '/home/seyon/dev/ioncube-strip/lib/handler_map_final.json',
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, timeout=60, capture_output=True, text=True)
        return Path(output_path).exists()
    except Exception as e:
        return False

def process_file(php_file):
    """Process a single encoded PHP file."""
    rel_path = Path(php_file).relative_to('/home/seyon/dev/whmcs-original')
    stem = Path(php_file).stem
    
    with lock:
        stats['processed'] += 1
        current = stats['processed']
    
    print(f"[{current}] Processing: {rel_path}")
    
    # Create harness
    harness_path = create_harness(php_file)
    
    # Frida capture
    capture_file = f'/home/seyon/dev/ioncube-strip/batch_output/captures/capture_{stem}.json'
    print(f"  Running Frida capture...")
    
    success = run_frida_capture(php_file, f'/tmp/harness_{Path(php_file).stem}.php', f'/tmp/frida_capture_{stem}.json')
    
    if not success:
        with lock:
            stats['failed'] += 1
            stats['errors'].append(f"{rel_path}: Frida capture failed")
        print(f"  FAILED: Frida capture failed")
        return False
    
    # Copy capture to batch output
    subprocess.run(['cp', f'/tmp/frida_capture_{stem}.json', capture_file])
    
    # Extract keyidx from capture
    with open(capture_file) as f:
        cap = json.load(f)
    keyidx = cap.get('keyidx', 31)
    
    # Ensure keybuf exists
    keybuf_path = f'/home/seyon/dev/ioncube-strip/captures/keybuf_{keyidx}.json'
    if not Path(keybuf_path).exists():
        print(f"  Keybuf for keyidx {keyidx} not found, using default")
    
    # Decode
    decoded_file = f'/home/seyon/dev/ioncube-strip/batch_output/decoded/decoded_{stem}.php'
    print(f"  Decoding with keyidx={keyidx}...")
    success = decode_capture(capture_file, keyidx, decoded_file)
    
    if success:
        with lock:
            stats['success'] += 1
        print(f"  SUCCESS: Decoded to {decoded_file}")
        return True
    else:
        with lock:
            stats['failed'] += 1
            stats['errors'].append(f"{rel_path}: Decode failed")
        print(f"  FAILED: Decode failed")
        return False

def main():
    print("=" * 60)
    print("BATCH IONCUBE DECODER")
    print("=" * 60)
    
    print("Scanning for encoded files...")
    encoded_files = find_encoded_files(WHMCS_ROOT)
    print(f"Found {len(encoded_files)} encoded files")
    
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        encoded_files = encoded_files[:limit]
        print(f"Limited to {limit} files")
    
    print(f"Processing {len(encoded_files)} files with {MAX_WORKERS} workers...")
    print()
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_file, f): f for f in encoded_files}
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                with lock:
                    stats['failed'] += 1
                    stats['errors'].append(f"Exception: {e}")
    
    elapsed = time.time() - start_time
    
    print()
    print("=" * 60)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Total processed: {stats['processed']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Time elapsed: {elapsed:.1f}s")
    
    if stats['errors']:
        print("\nErrors:")
        for err in stats['errors']:
            print(f"  - {err}")
    
    # Save stats
    with open(f'{OUTPUT_DIR}/batch_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)

if __name__ == '__main__':
    main()
