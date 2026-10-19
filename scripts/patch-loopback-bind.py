#!/usr/bin/env python3
"""Ard.ESignature.jar icindeki ArdHttpServer'i yalnizca 127.0.0.1 (loopback) adresine
baglanacak sekilde yamar.

UHAP, ayni makinedeki tarayici sayfalarindan konusur; yerel imza servisinin
yerel agdaki diger cihazlara acik olmasi gerekmez. Yama:

    new InetSocketAddress(HTTP_SERVER_PORT)
->  new InetSocketAddress(InetAddress.getLoopbackAddress(), HTTP_SERVER_PORT)

Kullanim: python3 patch_bind.py <Ard.ESignature.jar>
Basari: cikis 0 ve "bind yamasi OK" mesaji. Kalip eslesmezse cikis 1 (derleme durur).
"""
import struct
import sys
import os
import subprocess
import tempfile
import zipfile

CLASS = "utilities/http/server/ArdHttpServer.class"

def rd_u2(b, o): return struct.unpack_from('>H', b, o)[0], o + 2
def rd_u4(b, o): return struct.unpack_from('>I', b, o)[0], o + 4
def pk_u2(v): return struct.pack('>H', v)

def parse_cp(data, o):
    count, o = rd_u2(data, o)
    cp = [None]
    while len(cp) < count:
        tag = data[o]
        start = o
        u = None
        if tag == 1:
            ln, _ = rd_u2(data, o + 1)
            o = start + 3 + ln
            u = data[start + 3:o].decode('utf-8', 'surrogateescape')
        elif tag in (3, 4):
            o += 5
        elif tag in (5, 6):
            o += 9
            cp.append({'tag': tag, 'raw': data[start:o]})
            cp.append(None)
            continue
        elif tag in (7, 8, 16, 19, 20):
            o += 3
        elif tag in (9, 10, 11, 12, 17, 18):
            o += 5
        elif tag == 15:
            o += 4
        else:
            raise SystemExit("HATA: bilinmeyen cp tag %d @%d" % (tag, start))
        cp.append({'tag': tag, 'raw': data[start:o], 'u': u})
    return cp, o

def cp_utf8(cp, s):
    for i in range(1, len(cp)):
        e = cp[i]
        if e and e['tag'] == 1 and e['u'] == s:
            return i
    b = s.encode()
    cp.append({'tag': 1, 'raw': bytes([1]) + pk_u2(len(b)) + b, 'u': s})
    return len(cp) - 1

def cp_class(cp, name):
    ui = cp_utf8(cp, name)
    for i in range(1, len(cp)):
        e = cp[i]
        if e and e['tag'] == 7 and e['raw'][1:3] == pk_u2(ui):
            return i
    cp.append({'tag': 7, 'raw': bytes([7]) + pk_u2(ui)})
    return len(cp) - 1

def cp_nameandtype(cp, n, d):
    ni, di = cp_utf8(cp, n), cp_utf8(cp, d)
    for i in range(1, len(cp)):
        e = cp[i]
        if e and e['tag'] == 12 and e['raw'][1:5] == pk_u2(ni) + pk_u2(di):
            return i
    cp.append({'tag': 12, 'raw': bytes([12]) + pk_u2(ni) + pk_u2(di)})
    return len(cp) - 1

def cp_methodref(cp, cls, n, d):
    ci, nti = cp_class(cp, cls), cp_nameandtype(cp, n, d)
    for i in range(1, len(cp)):
        e = cp[i]
        if e and e['tag'] == 10 and e['raw'][1:5] == pk_u2(ci) + pk_u2(nti):
            return i
    cp.append({'tag': 10, 'raw': bytes([10]) + pk_u2(ci) + pk_u2(nti)})
    return len(cp) - 1

def utf8_of(cp, idx): return cp[idx]['u']
def cls_name(cp, idx): return cp[struct.unpack('>H', cp[idx]['raw'][1:3])[0]]['u']
def ref_parts(cp, idx):
    c, nt = struct.unpack('>HH', cp[idx]['raw'][1:5])
    a, b = struct.unpack('>HH', cp[nt]['raw'][1:5])
    return cls_name(cp, c), cp[a]['u'], cp[b]['u']

def find_ref(cp, tag, cls, name, desc):
    for i in range(1, len(cp)):
        e = cp[i]
        if e and e['tag'] == tag:
            c, n, d = ref_parts(cp, i)
            if (c, n, d) == (cls, name, desc):
                return i
    raise SystemExit("HATA: cp referansi bulunamadi: %s.%s:%s" % (cls, name, desc))

def parse_attrs(data, o):
    n, o = rd_u2(data, o)
    attrs = []
    for _ in range(n):
        ni, o = rd_u2(data, o)
        ln, o = rd_u4(data, o)
        attrs.append({'ni': ni, 'data': data[o:o + ln]})
        o += ln
    return attrs, o

def ser_attrs(cp, attrs):
    out = bytearray(pk_u2(len(attrs)))
    for a in attrs:
        out += pk_u2(a['ni']) + struct.pack('>I', len(a['data'])) + a['data']
    return bytes(out)

def parse_vti(d, o):
    tag = d[o]
    o += 1
    extra = None
    if tag in (7, 8):
        extra, o = rd_u2(d, o)
    return {'tag': tag, 'extra': extra}, o

def ser_vti(v):
    if v['tag'] in (7, 8):
        return bytes([v['tag']]) + pk_u2(v['extra'])
    return bytes([v['tag']])

def parse_smt(d):
    n, o = rd_u2(d, 0)
    frames = []
    prev = -1
    for _ in range(n):
        ft = d[o]
        o += 1
        kind, delta, chomp, locals_, stack = 'same', None, 0, [], []
        if ft <= 63:
            delta = ft
        elif ft <= 127:
            delta = ft - 64
            kind = 'stack1'
            v, o = parse_vti(d, o)
            stack.append(v)
        elif ft == 247:
            delta, o = rd_u2(d, o)
            kind = 'stack1'
            v, o = parse_vti(d, o)
            stack.append(v)
        elif 248 <= ft <= 250:
            delta, o = rd_u2(d, o)
            kind = 'chop'
            chomp = 251 - ft
        elif ft == 251:
            delta, o = rd_u2(d, o)
        elif 252 <= ft <= 254:
            delta, o = rd_u2(d, o)
            kind = 'append'
            for _ in range(ft - 251):
                v, o = parse_vti(d, o)
                locals_.append(v)
        elif ft == 255:
            delta, o = rd_u2(d, o)
            kind = 'full'
            nl, o = rd_u2(d, o)
            for _ in range(nl):
                v, o = parse_vti(d, o)
                locals_.append(v)
            ns, o = rd_u2(d, o)
            for _ in range(ns):
                v, o = parse_vti(d, o)
                stack.append(v)
        else:
            raise SystemExit("HATA: gecersiz stack map frame tipi %d" % ft)
        abs_off = delta if prev < 0 else prev + delta + 1
        frames.append({'kind': kind, 'abs': abs_off, 'chomp': chomp,
                       'locals': locals_, 'stack': stack})
        prev = abs_off
    return frames

def ser_smt(frames, shift):
    out = bytearray(pk_u2(len(frames)))
    prev = -1
    for f in frames:
        new_abs = shift(f['abs'])
        delta = new_abs if prev < 0 else new_abs - prev - 1
        if delta < 0:
            raise SystemExit("HATA: negatif stack map delta")
        if f['kind'] == 'same':
            if delta <= 63:
                out += bytes([delta])
            else:
                out += bytes([251]) + pk_u2(delta)
        elif f['kind'] == 'stack1':
            if delta <= 63:
                out += bytes([64 + delta])
            else:
                out += bytes([247]) + pk_u2(delta)
            out += ser_vti(f['stack'][0])
        elif f['kind'] == 'chop':
            out += bytes([251 - f['chomp']]) + pk_u2(delta)
        elif f['kind'] == 'append':
            out += bytes([251 + len(f['locals'])]) + pk_u2(delta)
            for v in f['locals']:
                out += ser_vti(v)
        else:
            out += bytes([255]) + pk_u2(delta)
            out += pk_u2(len(f['locals']))
            for v in f['locals']:
                out += ser_vti(v)
            out += pk_u2(len(f['stack']))
            for v in f['stack']:
                out += ser_vti(v)
        prev = new_abs
    return bytes(out)

def patch_class(data):
    if data[0:4] != b'\xca\xfe\xba\xbe':
        raise SystemExit("HATA: class dosyasi degil")
    if struct.unpack('>H', data[6:8])[0] != 55:
        raise SystemExit("HATA: beklenen class major 55")
    cp, o = parse_cp(data, 8)
    head6 = data[o:o + 6]
    o += 6
    ifc_n, _ = rd_u2(data, o)
    ifc_raw = data[o:o + 2 + 2 * ifc_n]
    o += 2 + 2 * ifc_n
    fields_start = o
    fields_n, o = rd_u2(data, o)
    for _ in range(fields_n):
        o += 6
        _, o = parse_attrs(data, o)
    fields_raw = data[fields_start:o]
    methods_n, o = rd_u2(data, o)
    methods = []
    for _ in range(methods_n):
        flags, o = rd_u2(data, o)
        ni, o = rd_u2(data, o)
        di, o = rd_u2(data, o)
        attrs, o = parse_attrs(data, o)
        methods.append({'flags': flags, 'ni': ni, 'di': di, 'attrs': attrs})
    class_attrs, o = parse_attrs(data, o)

    gs_idx = find_ref(cp, 9, 'contacts/constants', 'HTTP_SERVER_PORT', 'I')
    ctor_idx = find_ref(cp, 10, 'java/net/InetSocketAddress', '<init>', '(I)V')
    find_ref(cp, 10, 'com/sun/net/httpserver/HttpServer', 'create',
             '(Ljava/net/InetSocketAddress;I)Lcom/sun/net/httpserver/HttpServer;')

    target = None
    for m in methods:
        if utf8_of(cp, m['ni']) == '<init>' and \
           utf8_of(cp, m['di']) == '(Lorg/slf4j/Logger;Lroot/App;)V':
            target = m
            break
    if target is None:
        raise SystemExit("HATA: ArdHttpServer kurucu metodu bulunamadi")
    code_attr = None
    for a in target['attrs']:
        if utf8_of(cp, a['ni']) == 'Code':
            code_attr = a
            break
    if code_attr is None:
        raise SystemExit("HATA: Code attribute bulunamadi")

    d = code_attr['data']
    max_stack, max_locals = struct.unpack_from('>HH', d, 0)
    code_len = struct.unpack_from('>I', d, 4)[0]
    code = bytearray(d[8:8 + code_len])
    o2 = 8 + code_len
    exc_n, o2 = rd_u2(d, o2)
    exc = []
    for _ in range(exc_n):
        exc.append(list(struct.unpack_from('>HHHH', d, o2)))
        o2 += 8
    subattrs, o2 = parse_attrs(d, o2)

    pattern = bytes([0xB2]) + pk_u2(gs_idx) + bytes([0xB7]) + pk_u2(ctor_idx)
    hits = [i for i in range(0, len(code) - len(pattern) + 1)
            if bytes(code[i:i + len(pattern)]) == pattern]
    if len(hits) != 1:
        raise SystemExit("HATA: bind kalibi %d kez bulundu (beklenen 1)" % len(hits))
    pos = hits[0]
    if pos < 4 or code[pos - 1] != 0x59 or code[pos - 4] != 0xBB:
        raise SystemExit("HATA: kalip oncesi new+dup dizilimi beklenen gibi degil")

    for e in exc:
        for v in e[:3]:
            if pos <= v < pos + 6:
                raise SystemExit("HATA: istisna tablosu referansi yama bolgesinde")
    for a in subattrs:
        if utf8_of(cp, a['ni']) == 'StackMapTable':
            for f in parse_smt(a['data']):
                if pos <= f['abs'] < pos + 6:
                    raise SystemExit("HATA: stack map referansi yama bolgesinde")

    getloop = cp_methodref(cp, 'java/net/InetAddress', 'getLoopbackAddress',
                           '()Ljava/net/InetAddress;')
    newctor = cp_methodref(cp, 'java/net/InetSocketAddress', '<init>',
                           '(Ljava/net/InetAddress;I)V')

    code[pos:pos + 6] = (bytes([0xB8]) + pk_u2(getloop) +
                         bytes([0xB2]) + pk_u2(gs_idx) +
                         bytes([0xB7]) + pk_u2(newctor))

    def shift(v):
        return v + 3 if v >= pos + 6 else v

    new_exc = [[shift(e[0]), shift(e[1]), shift(e[2]), e[3]] for e in exc]
    new_subattrs = []
    for a in subattrs:
        name = utf8_of(cp, a['ni'])
        if name == 'StackMapTable':
            a = {'ni': a['ni'], 'data': ser_smt(parse_smt(a['data']), shift)}
        elif name == 'LineNumberTable':
            n, oo = rd_u2(a['data'], 0)
            out = bytearray(pk_u2(n))
            for _ in range(n):
                pc, lineno = struct.unpack_from('>HH', a['data'], oo)
                oo += 4
                out += pk_u2(shift(pc)) + pk_u2(lineno)
            a = {'ni': a['ni'], 'data': bytes(out)}
        elif name in ('LocalVariableTable', 'LocalVariableTypeTable'):
            n, oo = rd_u2(a['data'], 0)
            out = bytearray(pk_u2(n))
            for _ in range(n):
                sp, ln2, ui, di2, slot = struct.unpack_from('>HHHHH', a['data'], oo)
                oo += 10
                if sp <= pos < sp + ln2:
                    ln2 += 3
                else:
                    sp = shift(sp)
                out += pk_u2(sp) + pk_u2(ln2) + pk_u2(ui) + pk_u2(di2) + pk_u2(slot)
            a = {'ni': a['ni'], 'data': bytes(out)}
        new_subattrs.append(a)

    nd = bytearray()
    nd += struct.pack('>HH', max_stack, max_locals)
    nd += struct.pack('>I', len(code)) + code
    nd += pk_u2(len(new_exc))
    for e in new_exc:
        nd += struct.pack('>HHHH', *e)
    nd += ser_attrs(cp, new_subattrs)
    code_attr['data'] = bytes(nd)

    out = bytearray(data[:8])
    out += pk_u2(len(cp))
    for e in cp[1:]:
        if e:
            out += e['raw']
    out += head6 + ifc_raw + fields_raw
    out += pk_u2(len(methods))
    for m in methods:
        out += pk_u2(m['flags']) + pk_u2(m['ni']) + pk_u2(m['di'])
        out += ser_attrs(cp, m['attrs'])
    out += ser_attrs(cp, class_attrs)
    return bytes(out)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Kullanim: patch_bind.py <Ard.ESignature.jar>")
    jar = sys.argv[1]
    with zipfile.ZipFile(jar) as z:
        data = z.read(CLASS)
    patched = patch_class(data)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, CLASS)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(patched)
        subprocess.check_call(["zip", "-q", os.path.abspath(jar), CLASS], cwd=tmp)
    print("bind yamasi OK: ArdHttpServer -> 127.0.0.1 (loopback)")

if __name__ == '__main__':
    main()
