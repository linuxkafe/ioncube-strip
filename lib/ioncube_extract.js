// ioncube_extract.js — capture decoded op_arrays + RUNTIME KEYBUF from ionCube VM.
//
// Hooks:
//  1. VM loop at loader+0x87205 — captures OPARRAY with raw handlers
//  2. After OPARRAY captured, DIRECTLY READ keybuf from memory using known pointer chain

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
function u8(x, o) { try { return x.add(o).readU8(); } catch (e) { return null; } }
function inL(pt) { try { return pt.compare(loaderBase) >= 0 && pt.compare(loaderEnd) < 0; } catch (e) { return false; } }
function off(pt) { return '0x' + pt.sub(loaderBase).toString(16); }

var seen = {};
var keybufsCaptured = {};  // keyidx -> [256 uint32]

// Keybuf pointer chain:
// loader+0x37ec68 → struct_ptr (pointer)
// struct_ptr + 0xd0 → keybuf_ptr_array (array of 256 pointers)
// keybuf_ptr_array[keyidx] → keybuf (256 uint32s)
function readKeybufDirect(keyidx) {
  if (keybufsCaptured[keyidx]) return keybufsCaptured[keyidx];
  
  // struct_ptr is at loader+0x37ec68
  var struct_ptr = p(loaderBase, 0x37ec68);
  if (!struct_ptr) { console.log("[!] readKeybufDirect: failed at struct_ptr (0x37ec68)"); return null; }
  
  // keybuf_ptr_array is at struct_ptr + 0xd0 (NOT a pointer at that offset!)
  var keybuf_ptr_array = struct_ptr.add(0xd0);
  
  // Read keybuf pointer for this keyidx
  var keybuf_ptr = p(keybuf_ptr_array, keyidx * 8);
  if (!keybuf_ptr || keybuf_ptr.isNull()) { 
    console.log("[!] readKeybufDirect: keybuf_ptr null for keyidx=" + keyidx); 
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

var seen = {};

function onEnter(a) {
  var ed = a[0];
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
  
  var key = fn + '|' + last + '|' + (u32(oa, 0x10) || 0) + '|' + (u32(oa, 0x60) || 0);
  if (seen[key]) return;
  seen[key] = true;

  var keyidx = u32(res3, 8);
  var flagsPtr = p(res3, 0x90);
  var flags = flagsPtr ? u32(flagsPtr, 0xa4) : 0;
  
  // CAPTURE KEYBUF for this keyidx (direct memory read)
  if (!keybufsCaptured[keyidx]) {
    readKeybufDirect(keyidx);
  }
  
  var literals = p(oa, 0xb8);
  var nlits = u32(oa, 0xc0);
  
  var bitmapPtr = p(res3, 0x20);
  var bitmap = [];
  if (bitmapPtr && !bitmapPtr.isNull()) {
    try {
      var bm = new Uint8Array(bitmapPtr.readByteArray(Math.min(last, 256)));
      for (var i = 0; i < bm.length; i++) bitmap[i] = bm[i];
    } catch (e) {}
  }

  var ops = [];
  for (var i = 0; i < last; i++) {
    var o = opcodes.add(i * 48);
    var lo = u32(o, 0), hi = u32(o, 4);
    
    var op1_ptr = o.add(8).readPointer();
    var op2_ptr = o.add(0x10).readPointer();
    var result_ptr = o.add(0x18).readPointer();
    
    var op1t = u8(o, 0x28);
    var op2t = u8(o, 0x2c);
    var res_t = u8(o, 0x30);
    
    var bm_val = (i < bitmap.length) ? bitmap[i] : 0;
    
    ops.push({
      i: i,
      handler_lo: lo,
      handler_hi: hi,
      op1: op1_ptr.toString(),
      op2: op2_ptr.toString(),
      result: result_ptr.toString(),
      ext: u32(o, 0x20),
      lineno: u32(o, 0x24),
      op1_type: op1t,
      op2_type: op2t,
      result_type: res_t,
      bitmap: bm_val
    });
  }

  var lits = [];
  for (var j = 0; j < nlits; j++) {
    try {
      var entry = literals.add(j * 32);
      var bytes = entry.readByteArray(32);
      var arr = Array.from(new Uint8Array(bytes));
      var val_ptr = entry.add(0x18).readPointer();
      lits.push({
        index: j,
        raw_bytes: arr,
        val_ptr: val_ptr.toString()
      });
    } catch (e) {
      lits.push({ index: j, error: e.toString() });
    }
  }

  var meta = null;
  try { meta = u32(oa, 0x18); } catch (e) {}

  console.log('OPARRAY ' + JSON.stringify({
    filename: fn,
    last: last,
    last_literal: nlits,
    flags_a4: '0x' + (flags >>> 0).toString(16),
    keyidx: keyidx,
    keybuf: keybufsCaptured[keyidx] || null,
    base: loaderBase.toString(),
    aflags: meta,
    ops: ops,
    lits: lits,
    bitmap: bitmap
  }));
}

function install() {
  if (!findLoader()) { setTimeout(install, 200); return; }
  console.log('LOADER ' + loaderBase);
  Interceptor.attach(loaderBase.add(0x87205), { onEnter: onEnter });
  console.log('HOOKED ' + loaderBase.add(0x87205));
}
setTimeout(install, 200);