#!/usr/bin/env python3
"""
Batch decode multiple ionCube-encoded files using Frida + decoder pipeline.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add lib to path
sys.path.insert(0, '/home/seyon/dev/ioncube-strip/lib')

import decoder_final

def load_keybufs():
    """Load all keybufs."""
    keybufs = {}
    for kidx in [31, 63]:
        with open(f'/home/seyon/dev/ioncube-strip/captures/keybuf_{kidx}.json') as f:
            keybufs[kidx] = json.load(f)
    return keybufs

def run_frida_capture(php_file: str, output_dir: str) -> bool:
    """Run Frida capture on a single PHP file."""
    # Create a test harness that includes the file and invokes its symbols
    harness = f'''<?php
define("ROOTDIR", "/var/www/html");
define("WHMCSDIR", "/var/www/html");
register_shutdown_function(function() {{ sleep(30); }});
include "{php_file}";
// Force execution of all functions in this file
$fns = get_defined_functions();
if (isset($fns["user"])) {{
    foreach ($fns["user"] as $fn) {{
        try {{
            $r = new ReflectionFunction($fn);
            if ($r->getFileName() === realpath("{php_file}") && $r->getNumberOfRequiredParameters() === 0) {{
                @call_user_func($fn);
            }}
        }} catch (Throwable $e) {{}}
    }}
}}
sleep(5);
'''
    
    harness_path = f'/tmp/harness_{Path(php_file).stem}.php'
    with open(harness_path, 'w') as f:
        f.write(harness)
    
    output_file = Path(output_dir) / f'capture_{Path(php_file).stem}.json'
    
    # Run Frida
    cmd = [
        '/usr/local/bin/frida',
        '-f', '/usr/bin/php5.6',
        '-l', '/home/seyon/dev/ioncube-strip/lib/ioncube_extract.js',
        '-o', str(output_file),
        '--', '-c', '/tmp/arm56.ini', harness_path
    ]
    
    try:
        result = subprocess.run(cmd, timeout=120, capture_output=True, text=True, cwd='/work/whmcs')
        return output_file.exists()
    except subprocess.TimeoutExpired:
        print(f"Timeout on {php_file}")
        return False
    except Exception as e:
        print(f"Error on {php_file}: {e}")
        return False

def decode_capture_file(capture_path: str, keyidx: int, output_dir: str) -> bool:
    """Decode a captured Frida output."""
    keybuf_path = f'/home/seyon/dev/ioncube-strip/captures/keybuf_{keyidx}.json'
    handler_map_path = '/home/seyon/dev/ioncube-strip/lib/handler_map_final.json'
    output_path = Path(output_dir) / f'decoded_{Path(capture_path).stem}.php'
    
    try:
        # For now, just use the decoder directly
        cmd = [
            'python3', '/home/seyon/dev/ioncube-strip/lib/decoder_final.py',
            capture_path,
            f'/home/seyon/dev/ioncube-strip/captures/keybuf_{keyidx}.json',
            '/home/seyon/dev/ioncube-strip/lib/handler_map_final.json',
            str(output_path)
        ]
        result = subprocess.run(cmd, timeout=60, capture_output=True, text=True)
        return output_path.exists()
    except Exception as e:
        print(f"Decode error: {e}")
        return False

def find_encoded_files(root: str) -> list:
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 batch_decode.py <whmcs_root> [output_dir] [max_files]")
        sys.exit(1)
    
    whmcs_root = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '/home/seyon/dev/ioncube-strip/batch_output'
    max_files = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f'{output_dir}/captures', exist_ok=True)
    os.makedirs(f'{output_dir}/decoded', exist_ok=True)
    
    print(f"Scanning for encoded files in {whmcs_root}...")
    encoded_files = find_encoded_files(whmcs_root)
    print(f"Found {len(encoded_files)} encoded files")
    
    # Limit to max_files
    encoded_files = encoded_files[:max_files]
    
    print(f"Processing {len(encoded_files)} files...")
    
    for i, php_file in enumerate(encoded_files):
        print(f"\n[{i+1}/{len(encoded_files)}] Processing {php_file}")
        
        # Run Frida capture
        print("  Running Frida capture...")
        success = run_frida_capture(php_file, f'{output_dir}/captures')
        if not success:
            print(f"  FAILED: Frida capture failed")
            continue
        
        # Find the capture file
        capture_files = list(Path(f'{output_dir}/captures').glob(f'capture_{Path(php_file).stem}.json'))
        if not capture_files:
            print(f"  FAILED: No capture file generated")
            continue
        
        capture_file = capture_files[0]
        print(f"  Capture saved: {capture_file}")
        
        # Determine keyidx from capture
        with open(capture_file) as f:
            cap = json.load(f)
        keyidx = cap.get('keyidx', 31)
        
        # Decode
        print(f"  Decoding with keyidx={keyidx}...")
        success = decode_capture_file(str(capture_file), keyidx, f'{output_dir}/decoded')
        if success:
            print(f"  SUCCESS: Decoded to {output_dir}/decoded/")
        else:
            print(f"  FAILED: Decode failed")

if __name__ == '__main__':
    main()
