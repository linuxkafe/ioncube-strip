#!/usr/bin/env python3
"""Extract JSON from Frida output."""
import re
import json
import sys
import ast

def extract_frida_output(input_file, output_dir):
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Find all Frida message lines
    pattern = r"message: \{'type': 'send', 'payload': (\{.*?\}) data: None"
    matches = re.findall(pattern, content, re.DOTALL)
    
    for i, match in enumerate(matches):
        try:
            # Parse Python dict to JSON
            data = ast.literal_eval(match)
            if data.get('type') == 'oparray':
                output_file = f"{output_dir}/capture_oparray_{i}.json"
                with open(output_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"Saved OPARRAY {i}: {data.get('filename', 'unknown')[:50]}... keyidx={data.get('keyidx')} last={data.get('last')}")
            elif data.get('type') == 'keybuf':
                output_file = f"{output_dir}/capture_keybuf_{data.get('keyidx')}.json"
                with open(output_file, 'w') as f:
                    json.dump(data['data'], f, indent=2)
                print(f"Saved KEYBUF keyidx={data.get('keyidx')}: {len(data['data'])} entries")
        except Exception as e:
            print(f"Error parsing match {i}: {e}")

if __name__ == '__main__':
    input_file = sys.argv[1] if len(sys.argv) > 1 else '/tmp/frida_batch_capture.txt'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '/home/seyon/dev/ioncube-strip/batch_output/captures'
    extract_frida_output(input_file, output_dir)
