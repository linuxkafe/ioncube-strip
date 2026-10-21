// ioncube_capture_v9.js — VM loop hook, read keybuf on subsequent hits
//
// Strategy:
//  1. VM loop at loader+0x87205 — captures OPARRAY (lightweight)
//  2. On first hit of a function: capture OPARRAY, keybuf=null
//  3. On subsequent hits: keybuf should be loaded, read it from pointer chain
//
// Instruction analysis:
//  0x87205: push r15                              -> VM loop entry
//  Keybuf pointer chain:
//  loader+0x37ec68 → struct_ptr (pointer)
//  struct_ptr + 0xd0 → keybuf_ptr_array (array of 256 pointers)
//  keybuf_ptr_array[keyidx] → keybuf (256 uint32s)

var loaderBase = null, loaderEnd = null;
function findLoader() {
  var m = Process.enumerateModules();
  for (var i = 0; i < m.length; i++) {
    if (m[i].name.toLowerCase().indexOf('ioncube') !== -1) {
      loaderBase = m[i].base; loaderEnd = m[i].base.add(m[i].size); return true;
    }
  }
  return false;
}
function p(x, o) { try { return x.add(o).readPointer(); } catch (e) { return null; } }
function u32(x, o) { try { return x.add(o).readU32(); } catch (e) { return null; } }

var seen = {};           // key -> true (first hit captured)
var keybufsCaptured = {};  // keyidx -> [256 uint32]

function readKeybuf(keyidx) {
  if (keybufsCaptured[keyidx]) return keybufsCaptured[keyidx];
  
  var struct_ptr = p(loaderBase, 0x37ec68);
  if (!struct_ptr) { console.log("[!] readKeybuf: failed at struct_ptr (0x37ec68)"); return null; }
  
  var keybuf_ptr_array = struct_ptr.add(0xd0);
  var keybuf_ptr = p(keybuf_ptr_array, keyidx * 8);
  if (!keybuf_ptr || keybuf_ptr.isNull()) { 
    console.log("[!] readKeybuf: keybuf_ptr null for keyidx=" + keyidx); 
    return null; 
  }
  
  console.log("[*] Reading keybuf for keyidx=" + keyidx + " at " + keybuf_ptr);
  
  var out = [];
  var kb = new NativePointer(keybuf_ptr);
  for (var i = 0; i < 256; i++) {
    out.push(kb.add(i * 4).readU32() >>> 0);
  }
  keybufsCaptured[keyidx] = out;
  console.log('KEYBUF ' + keyidx + ' ' + JSON.stringify(out));
  return out;
}

function onEnter(args) {
  var ed = args[0];
  if (!ed || ed.isNull()) return;
  var oa = p(ed, 0x18);
  if (!oa || oa.isNull()) return;
  
  var fnp = p(oa, 0x98);
  var fn = (fnp && !fnp.isNull()) ? fnp.readCString(200).split('\x00')[0] : '';
  var res3 = p(oa, 0xf0);
  if (!res3) return;
  
  var opcodes = p(oa, 0x40);
  var last = u32(oa, 0x48);
  if (!opcodes || !last || last > 5000) return;
  
  var keyidx = u32(res3, 8);
  var key = fn + '|' + last + '|' + keyidx;
  var isFirstHit = !seen[key];
  seen[key] = true;

  // Try to read keybuf on EVERY hit (first hit will likely be null, subsequent hits should have it)
  if (!keybufsCaptured[keyidx]) {
    readKeybuf(keyidx);
  }
  
  // LIGHTWEIGHT: only capture handler_lo/hi
  var ops = [];
  for (var i = 0; i < last; i++) {
    var o = opcodes.add(i * 48);
    var lo = u32(o, 0), hi = u32(o, 4);
    ops.push({ i: i, handler_lo: lo, handler_hi: hi });
  }

  console.log('OPARRAY ' + JSON.stringify({
    filename: fn,
    last: last,
    keyidx: keyidx,
    keybuf: keybufsCaptured[keyidx] || null,
    base: loaderBase.toString(),
    ops: ops
  }));
}

function install() {
  if (!findLoader()) { setTimeout(install, 200); return; }
  console.log('LOADER ' + loaderBase);
  
  // VM loop hook - LIGHTWEIGHT
  Interceptor.attach(loaderBase.add(0x87205), { onEnter: onEnter });
  console.log('HOOKED VM Loop at ' + loaderBase.add(0x87205));
}
setTimeout(install, 200);