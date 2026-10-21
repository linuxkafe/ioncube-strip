#!/usr/bin/env python3
"""
Batch process WHMCS admin files - v1
Strategy: stub out enough of WHMCS bootstrap that ionCube VM runs
and the Frida hook captures OPARRAYs even if the admin file dies.
"""
import json, os, subprocess, sys, time
from pathlib import Path

WHMCS_ROOT = "/var/www/html"
ADMIN_DIR = "/var/www/html/admin"
OUTPUT_DIR = "/tmp/batch_admin"
FRIDA_SCRIPT = "/home/seyon/dev/ioncube-strip/lib/ioncube_wait.js"
HANDLER_MAP = "/home/seyon/dev/ioncube-strip/lib/handler_map_final.json"
DECODER = "/home/seyon/dev/ioncube-strip/lib/decoder_final.py"
KNOWN_KEYBUFS = {
    0: "/home/seyon/dev/ioncube-strip/captures/keybuf_0.json",
    31: "/home/seyon/dev/ioncube-strip/captures/keybuf_31.json",
    63: "/home/seyon/dev/ioncube-strip/captures/keybuf_63.json",
}

for d in [OUTPUT_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)

# Build harness that stubs enough of the WHMCS env
def create_admin_harness(admin_rel_path):
    stem = Path(admin_rel_path).stem
    rel = admin_rel_path.replace(".php", "")
    
    harness = """<?php
// Admin harness - v1 (stubs WHMCS bootstrap to let VM run)
define("ROOTDIR", "/var/www/html");
define("WHMCSDIR", "/var/www/html");
define("ADMINDIR", "/var/www/html/admin");
define("DB_HOST", "localhost");
define("DB_PORT", "3306");
define("DB_USERNAME", "root");
define("DB_PASSWORD", "");
define("DB_NAME", "whmcs");
define("TWO_FA", 0);

error_reporting(0);
ini_set("max_execution_time", "60");
ini_set("socket.timeout", "5");

// Stub out functions that init.php would normally provide
// We want the ionCube VM to execute but skip the actual DB calls
if (!function_exists("init")) {
    function init() {}
}

$_SERVER["REMOTE_ADDR"] = "127.0.0.1";
$_SERVER["SERVER_NAME"] = "localhost";
$_SERVER["HTTP_HOST"] = "localhost";
$_SERVER["REQUEST_METHOD"] = "GET";
$_SERVER["REQUEST_URI"] = "/admin/%s";
$_SERVER["QUERY_STRING"] = "";
$_SERVER["SCRIPT_NAME"] = "/admin/%s";
$_SERVER["PHP_SELF"] = "/admin/%s";
$_SESSION = [];
$_GET = [];
$_POST = [];
$_FILES = [];
$_REQUEST = [];
$_COOKIE = [];

$GLOBALS["TWO_FA"] = 0;
$GLOBALS["DB"] = null;

// The target file will include init.php or dbconnect.php
// which will die, but if we define enough stubs, the VM might still
// register the admin file's own functions before dying.

try {
    chdir(WHMCS_ROOT);
    include WHMCS_ROOT . "/admin/%s";
} catch (Throwable $e) {}
catch (Exception $e) {}

echo "HARNESS_DONE\\n";
sleep(5);
""" % (rel, rel, rel, admin_rel_path)
    
    path = "/tmp/harness_%s.php" % stem
    with open(path, "w") as f:
        f.write(harness)
    return path


def find_admin_encoded():
    """Find ionCube-encoded admin PHP files."""
    results = []
    admin_path = Path(ADMIN_DIR)
    if not admin_path.exists():
        return results
    for f in admin_path.rglob("*.php"):
        try:
            data = f.read_bytes()
            if b"ionCube" in data[:500] or b"_il_exec" in data[:500]:
                results.append(str(f.relative_to(WHMCS_ROOT)))
        except Exception:
            pass
    results.sort()
    return results


def frida_run(harness_path, stem, timeout=120):
    """Run harness under Frida and capture stdout."""
    cmd = [
        "/usr/local/bin/frida",
        "-f", "/usr/bin/php5.6",
        "-l", FRIDA_SCRIPT,
        "--",
        "-c", "/tmp/arm56.ini",
        harness_path
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + "\n" + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        print("  frida_err: %s" % e, file=sys.stderr)
        return ""


def save_captures(raw_output, stem):
    """Extract message: blocks and save them as JSON files."""
    import re, ast
    out_dir = os.path.join(OUTPUT_DIR, stem)
    os.makedirs(out_dir, exist_ok=True)
    
    # Split on "message:" delimiter
    lines = raw_output.split("message:")
    saved = 0
    for i, block in enumerate(lines[1:]):  # skip first (before first "message:")
        block = block.strip()
        if not block:
            continue
        # The block should start with { and end before the next "message:"
        try:
            # Find the JSON object
            brace_start = block.find("{")
            if brace_start < 0:
                continue
            # Find matching closing brace (simplified: find first complete JSON)
            depth = 0
            end = brace_start
            for j in range(brace_start, len(block)):
                if block[j] == "{":
                    depth += 1
                elif block[j] == "}":
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
            json_str = block[brace_start:end]
            obj = json.loads(json_str)
            
            typ = obj.get("type", "unk")
            fname = "%s_op%03d_%s.json" % (stem, i, typ)
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "w") as f:
                json.dump(obj, f, indent=2)
            saved += 1
            keyidx = obj.get("keyidx", "?")
            last = obj.get("last", "?")
            print("  saved %s keyidx=%s last=%s" % (fname, keyidx, last))
        except (json.JSONDecodeError, Exception) as e:
            pass
    return saved


def main():
    if len(sys.argv) > 2:
        limit = int(sys.argv[1])
        offset = int(sys.argv[2])
    else:
        limit = 10
        offset = 0
    
    print("=" * 60)
    print("BATCH ADMIN PROCESSOR v1")
    print("=" * 60)
    
    files = find_admin_encoded()
    print("Found %d encoded admin files" % len(files))
    files = files[offset:offset+limit]
    print("Processing %d files (offset=%d)" % (len(files), offset))
    
    stats = {"processed": 0, "captured": 0, "failed": 0}
    
    for i, rel in enumerate(files):
        stem = Path(rel).stem
        stats["processed"] += 1
        print("\n[%d/%d] %s" % (i+1, len(files), rel))
        
        harness = create_admin_harness(rel)
        print("  harness: %s" % harness)
        
        raw = frida_run(harness, stem)
        if not raw or "message:" not in raw:
            print("  FAILED: no captures")
            stats["failed"] += 1
            continue
        
        saved = save_captures(raw, stem)
        if saved > 0:
            stats["captured"] += 1
        else:
            stats["failed"] += 1
    
    print("\n" + "=" * 60)
    print("BATCH COMPLETE")
    print("=" * 60)
    print("Processed: %d" % stats["processed"])
    print("Captured:  %d" % stats["captured"])
    print("Failed:    %d" % stats["failed"])
    
    with open(os.path.join(OUTPUT_DIR, "batch_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)


if __name__ == "__main__":
    main()
