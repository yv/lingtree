#!/usr/bin/env python
# Copyright 2008-2020 Yannick Versley
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
# TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
"""
this module performs conversion from and to the Negra-Export
and JSON-export formats
"""
from __future__ import print_function, division
import sys
import re
import json
from builtins import bytes, str
from .schema import SimpleSchema, SimpleAttribute, make_export_schema
from . import tree

allowable_secedge = {'refint', 'refvc', 'refmod', 'refcontr', 'EN', 'HD', 'SB', 'OA', 'DA', 'CP', 'MO', 'EP', 'SVP',
                     'PPROJ'}

hash_token_re = re.compile('^#+\\s')
# reads lines in an export file and creates a nodes structure
# reads up to and including the #EOS

kill_spaces_tr = str.maketrans(' ', '_')

def read_sentence(f, format=3):
    '''
    reads a sentence in export format from the file descriptor f
    :param format: the Negra-Export version
    :param encoding: if a value is supplied here, the file will
      be assumed to have this encoding
    :param tree_encoding: passing None here means that the tree will
      contain unicode strings in the word, lemma, and comment fields,
      otherwise they will follow this encoding
    '''
    t = tree.Tree()
    secedges = []
    pos = 0
    l = f.readline().strip()
    while not l.startswith('#EOS'):
        if l.startswith('#') and not hash_token_re.match(l):
            # nonterminal node
            fields = l[1:].split()
            if format == 4:
                lemma_field = fields[1]
                del fields[1]
            assert len(fields) > 4, fields
            n = tree.NontermNode(fields[1], fields[3])
            n.id = fields[0]
            n.attr = fields[2]
            n.parent_id = fields[4]
            t.node_table[fields[0]] = n
            while len(fields) > 5:
                if fields[5] == '%%':
                    n.comment = ' '.join(fields[6:])
                    del fields[5:]
                else:
                    assert len(fields) > 6, fields[5:]
                    secedges.append((fields[0], fields[5], fields[6]))
                    del fields[5:7]
        else:
            # terminal node
            fields = l.split()
            if format == 4:
                lemma_field = fields[1]
                del fields[1]
            assert len(fields) > 4, (l, f.name, f.tell())
            word = fields[0]
            n = tree.TerminalNode(fields[1], word, fields[3], fields[2])
            n.parent_id = fields[4]
            n.id = 'T:%d'%(pos,)
            n.start = pos
            n.end = pos + 1
            if format == 4:
                n.lemma = lemma_field
            else:
                n.lemma = None
            while len(fields) > 5:
                if fields[5] == '%%':
                    n.comment = ' '.join(fields[6:])
                    del fields[5:]
                else:
                    assert len(fields) > 6, (fields[5:], fields)
                    secedges.append((pos, fields[5], fields[6]))
                    del fields[5:7]
            t.terminals.append(n)
            pos += 1
        l = f.readline().strip()
    for n in t.terminals:
        if n.parent_id == '0':
            n.parent = None
            t.roots.append(n)
        else:
            assert n.parent_id in t.node_table, (n.parent_id, f.name, f.tell())
            n.parent = t.node_table[n.parent_id]
            n.parent.children.append(n)
        del(n.parent_id)
    for n in t.node_table.values():
        if n.parent_id == '0':
            n.parent = None
            t.roots.append(n)
        else:
            assert n.parent_id in t.node_table, (n.parent_id, f.name, f.tell())
            n.parent = t.node_table[n.parent_id]
            n.parent.children.append(n)
        del(n.parent_id)
        n.secedge = None
    for a, rel, b in secedges:
        try:
            n_a = t.node_table[a]
        except KeyError:
            n_a = t.terminals[int(a)]
        try:
            n_b = t.node_table[b]
        except KeyError:
            n_b = t.terminals[int(b)]
        old_secedge = getattr(n_a, 'secedge', None)
        if old_secedge is None:
            old_secedge = []
        old_secedge.append((rel, n_b))
        n_a.secedge = old_secedge
    t.determine_tokenspan_all()
    return t


def comment2attrs(cm):
    if cm is None or cm == '':
        return {}
    attrs = {}
    zzspell = []
    for w in cm.split():
        try:
            idx = w.index('=', 1)
            attrs[w[:idx]] = w[idx + 1:]
        except ValueError:
            zzspell.append(w)
    if zzspell:
        attrs['~'] = ' '.join(zzspell)
    return attrs

sorting_dict = dict(((x, i)
                    for (i, x) in enumerate(['LM', 'R', 'DC', 'LU', '~'])))


def sort_fn(key):
    return sorting_dict.get(key, key)


def attrs2comment(attrs):
    keys = sorted(attrs.keys(), key=sort_fn)
    items = []
    for k in keys:
        if k != '~':
            items.append('%s=%s' % (k, attrs[k]))
    if '~' in attrs:
        items.append(attrs['~'])
    return ' '.join(items)


def secedge2nonprojective(t):
    for n in t.roots:
        reattach_secedge(n)
    t.determine_tokenspan_all()


def delete_empty_nodes(n):
    """deletes nodes that have become empty after reattachment of a phrase"""
    if n.children:
        pass
    elif n.parent:
        pos = n.parent.children.index(n)
        del n.parent.children[pos:pos + 1]
        delete_empty_nodes(n.parent)


def reattach_secedge(n):
    try:
        if n.secedge is not None:
            for edge in sorted(n.secedge, key=lambda x: x[1].start):
                rel, n2 = edge
                #print "secedge: %s: %s -> %s"%(n,rel,n2)
                if rel in ['refint', 'refmod'] and n.cat in ['NCX', 'NX']:
                    pos1 = n.parent.children.index(n)
                    pos2 = n2.parent.children.index(n2)
                    n1 = tree.NontermNode(n.cat, n.edge_label)
                    n.parent.children[pos1:pos1 + 1] = [n1]
                    del n2.parent.children[pos2:pos2 + 1]
                    delete_empty_nodes(n2.parent)
                    n1.parent = n.parent
                    n1.children = [n, n2]
                    n1.start = n.start
                    n1.end = n2.end
                    n1.edge_label = n.edge_label
                    n.parent = n1
                    n.edge_label = 'HD'
                    n2.edge_label = '-'
                    # print "created synthetic node"
                    n.secedge = None
                    # print n.parent.to_penn()
                    n2.parent = n1
                for nn in n2.children:
                    reattach_secedge(nn)
    except AttributeError:
        pass
    for nn in n.children:
        reattach_secedge(nn)


def write_sentence(t, f):
    """writes a sentence in export format
        and does NOT write the #EOS"""
    for n in t.terminals:
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        extra = ''
        if hasattr(n, 'secedge') and n.secedge is not None:
            for secedge in n.secedge:
                tgt = secedge[1]
                if tgt.isTerminal():
                    tgt_id = tgt.start
                else:
                    tgt_id = tgt.id
                extra += '\t%s %s' % (secedge[0], tgt_id)
        if hasattr(n, 'comment') and n.comment:
            if extra:
                extra += ' '
            else:
                extra = '     '
            extra += '%% ' + n.comment
        f.write('%-23s %-7s %-15s %-7s %s%s\n' % (n.word, n.cat, n.morph,
                                                  n.edge_label, parent_id, extra))
    all_nodes = t.node_table.values()
    all_nodes.sort(key=lambda n: n.id)
    for n in all_nodes:
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        extra = ''
        if hasattr(n, 'secedge') and n.secedge is not None:
            extra = '     %-7s %s' % (n.secedge[0], n.secedge[1].id)
        f.write('#%-22s %-7s %-15s %-7s %s%s\n' % (n.id, n.cat, n.attr,
                                                   n.edge_label, parent_id, extra))


def pad_with_tabs(s, n=1):
    if s is None:
        s = '--'
    s = s.translate(kill_spaces_tr)
    if len(s) >= 8 * n:
        return s + '\t'
    else:
        return s + '\t' * (n - len(s) // 8)

def write_sentence_tabs(t, f, fmt=3):
    """writes a sentence in export format
        and does NOT write the #EOS
    """
    for n in t.terminals:
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        extra = ''
        if hasattr(n, 'secedge') and n.secedge is not None:
            for secedge in n.secedge:
                tgt = secedge[1]
                if tgt.isTerminal():
                    tgt_id = tgt.start
                else:
                    tgt_id = tgt.id
                extra += '\t%s\t%s' % (secedge[0], tgt_id)
        if hasattr(n, 'comment') and n.comment:
            if extra:
                extra += ' '
            else:
                extra = '\t'
            extra += '%% ' + n.comment
        if fmt == 4:
            lem = getattr(n, 'lemma', None)
            if lem is None:
                lem = '--'
            lemma_column = pad_with_tabs(lem, 3)
        else:
            lemma_column = ''
        n_word = n.word
        f.write('%s%s%s%s%s%s%s\n'%(pad_with_tabs(n_word, 3),
                                    lemma_column,
                                    pad_with_tabs(n.cat, 1),
                                    pad_with_tabs(n.morph, 2),
                                    pad_with_tabs(n.edge_label, 1),
                                    parent_id, extra))
    all_nodes = list(t.node_table.values())
    all_nodes.sort(key=lambda n: n.id)
    if fmt == 4:
        lemma_column = pad_with_tabs('--', 3)
    else:
        lemma_column = ''
    for n in all_nodes:
        if n is not t.node_table[n.id]:
            print("%s: node %s may be duplicate"%(
                getattr(t, 'sent_no'), n.id), file=sys.stderr)
            assert False
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        extra = ''
        if hasattr(n, 'secedge') and n.secedge is not None:
            for secedge in n.secedge:
                tgt = secedge[1]
                if tgt.isTerminal():
                    tgt_id = tgt.start
                else:
                    tgt_id = tgt.id
                extra += '\t%s\t%s' % (secedge[0], tgt_id)
        if hasattr(n, 'comment') and n.comment is not None:
            if extra:
                extra += ' '
            else:
                extra = ' '
            extra += '%% ' + n.comment
        f.write('%s%s%s%s%s%s%s\n' % (pad_with_tabs('#%s' % (n.id,), 3),
                                      lemma_column,
                                      pad_with_tabs(n.cat, 1),
                                      pad_with_tabs(n.attr, 2),
                                      pad_with_tabs(n.edge_label, 1),
                                      parent_id, extra))


def to_json(t):
    '''
    converts a tree to JSON-export data,
    using the specified encoding for
    non-unicode strings
    '''
    terms = []
    for n in t.terminals:
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        extras = []
        if hasattr(n, 'secedge') and n.secedge is not None:
            extra = []
            for secedge in n.secedge:
                tgt = secedge[1]
                if tgt.isTerminal():
                    tgt_id = tgt.start
                else:
                    tgt_id = tgt.id
                extra.append([secedge[0], tgt_id])
            if extra:
                extras = [extra]
        terms.append([n.word, n.cat, n.morph,
                      n.edge_label, parent_id,
                      getattr(n, 'lemma', None)]+extras)
    nonterms = []
    all_nodes = sorted(t.node_table.values(), key=lambda n: n.id)
    for n in all_nodes:
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        extras = []
        if hasattr(n, 'secedge') and n.secedge is not None:
            extra = []
            for secedge in n.secedge:
                tgt = secedge[1]
                if tgt.isTerminal():
                    tgt_id = tgt.start
                else:
                    tgt_id = tgt.id
                extra.append([secedge[0], tgt_id])
            if extra:
                extras = [extra]
        nonterms.append([n.id, n.cat, n.attr,
                         n.edge_label, parent_id]+extras)
    result = {'terminals': terms, 'nonterminals': nonterms}
    if hasattr(t, 'sent_no'):
        result['_id'] = str(t.sent_no)
    return result


def from_json(values):
    '''
    decodes a JSON-export object to a pytree Tree
    object, using the specified encoding.
    '''
    t = tree.Tree()
    secedges = []
    for (pos, fields) in enumerate(values['terminals']):
        n = tree.TerminalNode(fields[1], fields[0], fields[3], fields[2])
        n.parent_id = fields[4]
        if len(fields) > 5:
            n.lemma = fields[5]
        n.id = 'T:%d' % (pos,)
        if len(fields) > 6:
            for (b, c) in fields[6]:
                secedges.append((pos, b, c))
        n.start = pos
        n.end = pos + 1
        t.terminals.append(n)
        pos += 1
    for fields in values['nonterminals']:
        n = tree.NontermNode(fields[1], fields[3])
        n.id = fields[0]
        n.attr = fields[2]
        n.parent_id = fields[4]
        t.node_table[fields[0]] = n
        if len(fields) > 5:
            for (b, c) in fields[5]:
                secedges.append((fields[0], b, c))
    for n in t.terminals:
        if n.parent_id == '0' or n.parent_id == 0:
            n.parent = None
            t.roots.append(n)
        else:
            assert n.parent_id in t.node_table, (n.parent_id, values)
            n.parent = t.node_table[n.parent_id]
            n.parent.children.append(n)
        del n.parent_id
    for n in t.node_table.values():
        if n.parent_id == '0' or n.parent_id == 0:
            n.parent = None
            t.roots.append(n)
        else:
            assert n.parent_id in t.node_table, (n.parent_id, values)
            n.parent = t.node_table[n.parent_id]
            n.parent.children.append(n)
        del n.parent_id
        n.secedge = None
    for a, rel, b in secedges:
        try:
            n_a = t.node_table[a]
        except KeyError:
            n_a = t.terminals[int(a)]
        try:
            n_b = t.node_table[b]
        except KeyError:
            n_b = t.terminals[int(b)]
        old_secedge = getattr(n_a, 'secedge', None)
        if old_secedge is None:
            old_secedge = []
        old_secedge.append((rel, n_b))
        n_a.secedge = old_secedge
    t.determine_tokenspan_all()
    if '_id' in values:
        t.sent_no = values['_id']
    return t


def copy_tree(t):
    """duplicates a tree by converting it to Negra export
    and reading it back again."""
    js = to_json(t)
    t2 = from_json(js)
    return t2

bos_pattern = re.compile('#BOS ([0-9]+) +[^ ]+ +[^ ]+ ([0-9]+)([ \t]*%%.*)?')


def transform_filter(fname, proc):
    """reads in an export file and processes the tree with proc"""
    f = open(fname, 'r')
    l = f.readline()
    while (l != ''):
        sys.stdout.write(l)
        m = bos_pattern.match(l)
        if m:
            sent_no = m.group(1)
            t = read_sentence(f)
            proc(t)
            write_sentence(t, sys.stdout)
            sys.stdout.write('#EOS %s\n' % (sent_no))
        l = f.readline()
    f.close()

bot_re = re.compile('^#BOT ([A-Z]+)')
def read_export_header(f, t_schema=None, nt_schema=None, fmt=3):
    '''
    reads the header portion of a Negra Export file and
    returns the header data and the first BOS line
    '''
    tables = {
        'ORIGIN': {},
        'FMT': fmt,
        'EDITOR': SimpleAttribute('editor')
    }
    if t_schema is None:
        t_schema, new_nt = make_export_schema()
        if nt_schema is None:
            nt_schema = new_nt
    tables['T'] = t_schema
    tables['WORDTAG'] = t_schema.attribute_by_name('pos')
    tables['MORPHTAG'] = t_schema.attribute_by_name('morph')
    if nt_schema is None:
        new_t, nt_schema = make_export_schema()
    tables['NT'] = nt_schema
    tables['NODETAG'] = nt_schema.attribute_by_name('cat')
    tables['EDGETAG'] = nt_schema.attribute_by_name('func')
    tables['SECEDGETAG'] = nt_schema.edges[0].attributes[0]
    where = None
    while True:
        l = f.readline()
        if l.strip() == '#FORMAT 4':
            tables['FMT'] = 4
        m = bot_re.match(l)
        if m:
            where = m.group(1)
        elif l.startswith('#EOT'):
            where = None
        elif where and where in tables and where != 'ORIGIN':
            line = l.strip().split(None, 2)
            if len(line) < 3:
                comment = ''
            else:
                comment = line[2]
            what = line[1]
            tables[where].add_item(what, comment)
        elif where == 'ORIGIN':
            line = l.strip().split(None, 2)
            tables['ORIGIN'][int(line[0])] = line[1]
        elif l.startswith('#BOS'):
            return (tables, l)


node_id_re = re.compile(b'0|5[12][0-9]')
def guess_format_version(fname):
    '''
    given a file name, looks at the file content to guess
    the export version
    '''
    in_sent = False
    num_lines = 0
    for l in open(fname, 'rb'):
        if l.startswith(b'#FORMAT 3'):
            return 'export3'
        elif l.startswith(b'#FORMAT 4'):
            return 'export4'
        elif l.startswith(b'#BOS '):
            in_sent = True
            continue
        elif l.startswith(b'#EOS '):
            in_sent = False
            continue
        if in_sent:
            line = l.strip().split()
            if b'%%' in line:
                line = line[:line.index(b'%%')]
            if len(line) == 5 and node_id_re.match(line[4]):
                return 'export3'
            elif len(line) == 6 and node_id_re.match(line[5]):
                return 'export4'
        num_lines += 1
        if num_lines >= 100:
            print("giving up guessing %s"%(fname,), file=sys.stderr)
            return 'export3'

def write_export_header(f, meta, fmt=None):
    '''
    writes a mostly-conformant header for a Negra-Export file
    '''
    print('%% generated using LingTree', file=f)
    if fmt is None:
        try:
            fmt = meta['FMT']
        except KeyError:
            fmt = 4
    print('#FORMAT %s'%(fmt,), file=f)
    if 'ORIGIN' in meta:
        print('#BOT ORIGIN', file=f)
        tab = meta['ORIGIN']
        for i in sorted(tab.keys()):
            print("%s\t%s"%(i, tab[i]), file=f)
        print('#EOT ORIGIN', file=f)
    for tab_name in ['EDITOR', 'WORDTAG', 'MORPHTAG', 'NODETAG', 'EDGETAG',
                     'SECEDGETAG']:
        print('#BOT %s'%(tab_name,), file=f)
        tab = meta[tab_name]
        for i, name in enumerate(tab.names):
            print("%s%s%s"%(pad_with_tabs(str(i-1), 1),
                                 pad_with_tabs(name, 1),
                                 tab.descriptions[name]), file=f)
        print('#EOT %s'%(tab_name,), file=f)
    if fmt == 3:
        lemma_column = ''
    else:
        lemma_column = pad_with_tabs('lemma', 3)
    f.write('%s%s%s%s%s%s%s%s\n' % (
        pad_with_tabs('%% word', 3),
        lemma_column,
        pad_with_tabs('tag', 1),
        pad_with_tabs('morph', 2),
        pad_with_tabs('edge', 1),
        pad_with_tabs('parent', 1),
        pad_with_tabs('secedge', 1),
        'comment'))

def write_bos(t, f_out):
    '''
    writes a BOS line for Negra Export
    '''
    if hasattr(t, 'doc_no'):
        doc_no = t.doc_no
    else:
        doc_no = 0
    if hasattr(t, 'comment') and t.comment:
        cm = ' %% '+t.comment
    else:
        cm = ''
    print("#BOS %s %s 0 0%s"%(t.sent_no, doc_no, cm), file=f_out)

def write_export_file(f_out, trees, meta=None, fmt=3):
    '''
    writes the trees from the sequence in trees to a file in Negra
    export format.
    '''
    # write header
    if fmt in [3, 'export3']:
        fmt = 3
        if meta is not None:
            write_export_header(f_out, meta, 4)
    elif fmt in [4, 'export4']:
        fmt = 4
        if meta is not None:
            write_export_header(f_out, meta, 3)
    #write body
    for t in trees:
        if fmt == 'json':
            print(json.dumps({'release':to_json(t)}), file=f_out)
        elif fmt == 4:
            write_bos(t, f_out)
            write_sentence_tabs(t, f_out, fmt=4)
            print("#EOS %s"%(t.sent_no,), file=f_out)
        else:
            write_bos(t, f_out)
            write_sentence_tabs(t, f_out)
            print("#EOS %s"%(t.sent_no,), file=f_out)

def write_json_file(f_out, trees):
    '''
    writes the trees from the sequence in trees to a file in Negra
    export format.
    '''
    import json
    #write body
    for t in trees:
            print(json.dumps({'release':to_json(t)}), file=f_out)

def read_trees(f, fmt=3, last_bos=None):
    '''
    reads trees from an export-format file
    '''
    global doc_no
    if last_bos is None:
        l = f.readline()
    else:
        l = last_bos
    while(l != ''):
        if l.strip() == '#FORMAT 4':
            fmt = 4
        m = bos_pattern.match(l)
        if m:
            sent_no = m.group(1)
            doc_no = m.group(2)
            t = read_sentence(f, fmt)
            t.sent_no = sent_no
            t.doc_no = doc_no
            t.comment = m.group(3)
            if t.comment:
                t.comment = t.comment.lstrip()
            yield t
        elif l.startswith('#BOS '):
            # still do something useful with incomplete format
            sent_no = l[5:].split()[0]
            t = read_sentence(f, fmt)
            t.sent_no = sent_no
            yield t
        l = f.readline()
    return

def read_trees_json(f, want_parser=None):
    import json
    warn_multiple = set()
    for line_no, l in enumerate(f):
        obj = json.loads(l)
        if '_id' in obj:
            sent_id = obj['_id']
        else:
            sent_id = 'line_%s'%(line_no+1,)
        if want_parser is not None and want_parser in obj:
            obj1 = obj[want_parser]
        else:
            objs = [obj[k] for k in sorted(obj.keys()) if k != '_id']
            if len(objs) > 1:
                for k in obj.keys():
                    if k not in warn_multiple:
                        print("Warning: several keys in read_trees_json(%s)"%(k,), file=sys.stderr)
                        warn_multiple.add(k)
            obj1 = objs[0]
        t = from_json(obj1)
        if sent_id is not None:
            t.sent_no = sent_id
        yield t
