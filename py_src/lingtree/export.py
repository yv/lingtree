#!/usr/bin/env python
"""
this module performs conversion from and to the Negra-Export
and JSON-export formats
"""
from __future__ import division
from builtins import str
from . import tree
import sys
import re

allowable_secedge = {
    'refint', 'refvc', 'refmod', 'refcontr',
    'EN', 'HD', 'SB', 'OA', 'DA', 'CP', 'MO', 'EP', 'SVP'}

hash_token_re = re.compile('^#\\s')
# reads lines in an export file and creates a nodes structure
# reads up to and including the #EOS


def read_sentence(f, format=3):
    "reads a sentence in export format from the file descriptor f"
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
            n = tree.TerminalNode(fields[1], fields[0], fields[3], fields[2])
            n.parent_id = fields[4]
            n.id = 'Terminal:%d' % (pos)
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
        del n.parent_id
    for n in t.node_table.values():
        if n.parent_id == '0':
            n.parent = None
            t.roots.append(n)
        else:
            assert n.parent_id in t.node_table, (n.parent_id, f.name, f.tell())
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
                # print "secedge: %s: %s -> %s"%(n,rel,n2)
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
    all_nodes = sorted(t.node_table.values(), key=lambda n: n.id)
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
    if len(s) >= 8 * n:
        return s + '\t'
    else:
        return s + '\t' * (n - len(s) // 8)


def write_sentence_tabs(t, f, fmt=3, encoding='ISO-8859-15'):
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
            lemma_column=''
        n_word = n.word
        if type(n_word) == str:
            n_word = n_word.encode(encoding)
        f.write('%s%s%s%s%s%s%s\n'%(pad_with_tabs(n_word, 3),
                                    lemma_column,
                                    pad_with_tabs(n.cat, 1),
                                    pad_with_tabs(n.morph, 2),
                                    pad_with_tabs(n.edge_label, 1), parent_id, extra))
    all_nodes = sorted(t.node_table.values(), key=lambda n: n.id)
    if fmt == 4:
        lemma_column = pad_with_tabs('--', 3)
    else:
        lemma_column = ''
    for n in all_nodes:
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


def latin2utf(s):
    if s is None:
        return None
    if isinstance(s, str):
        us = s
    else:
        us = s.decode('ISO-8859-15')
    return us.encode('UTF-8')


def utf2latin(s):
    if isinstance(s, str):
        us = s
    elif isinstance(s, bytes):
        us = s.decode('UTF-8')
    else:
        return s
    return us.encode('ISO-8859-15', 'replace')


def uni2str(s, encoding):
    if encoding is None:
        return s
    if isinstance(s, str):
        return s.encode(encoding)
    return s


def str2uni(s, encoding):
    if isinstance(s, bytes):
        return s.decode(encoding)
    return s


def to_json(t, encoding='ISO-8859-15'):
    """
    converts a tree to JSON-export data,
    using the specified encoding for
    non-unicode strings
    """
    terms = []
    for n in t.terminals:
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        terms.append([str2uni(n.word, encoding), n.cat, n.morph,
                      n.edge_label, parent_id,
                      str2uni(getattr(n, 'lemma', None), encoding)])
    nonterms = []
    all_nodes = t.node_table.values()
    all_nodes.sort(key=lambda n: n.id)
    for n in all_nodes:
        if n.parent:
            parent_id = n.parent.id
        else:
            parent_id = '0'
        nonterms.append([n.id, n.cat, n.attr,
                         n.edge_label, parent_id])
    return {'terminals': terms, 'nonterminals': nonterms}


def from_json(values, encoding='ISO-8859-15'):
    """
    decodes a JSON-export object to a pytree Tree
    object, using the specified encoding.
    """
    t = tree.Tree()
    for (pos, fields_u) in enumerate(values['terminals']):
        fields = [uni2str(s, encoding) for s in fields_u]
        n = tree.TerminalNode(fields[1], fields[0], fields[3], fields[2])
        n.parent_id = fields[4]
        if len(fields) > 5:
            n.lemma = utf2latin(fields[5])
        n.id = 'Terminal:%d' % (pos)
        n.start = pos
        n.end = pos + 1
        t.terminals.append(n)
        pos += 1
    for fields_u in values['nonterminals']:
        fields = [utf2latin(s) for s in fields_u]
        n = tree.NontermNode(fields[1], fields[3])
        n.id = fields[0]
        n.attr = fields[2]
        n.parent_id = fields[4]
        t.node_table[fields[0]] = n
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
    t.determine_tokenspan_all()
    return t


def write_sentence_prolog(f, nodes, indent=0):
    comma = False
    f.write('[\n')
    for node in nodes:
        if comma:
            f.write(',\n' + ' ' * indent)
        else:
            f.write(' ' * indent)
        if node.parent:
            parent_id = node.parent.id
        else:
            parent_id = 0
        if node.isTerminal():
            f.write('token(%s,%s,%s,%s,%s,%s)' % (
                node.start,
                tree.escape_prolog(node.word),
                tree.escape_prolog(node.cat),
                tree.escape_prolog(node.morph),
                tree.escape_prolog(node.edge_label),
                parent_id))
        else:
            f.write('node(%s,%s,%s,%s,' % (
                node.id,
                tree.escape_prolog(node.cat),
                parent_id,
                tree.escape_prolog(node.edge_label)))
            write_sentence_prolog(f, node.children, indent + 1)
            f.write(',%d,%d)' % (node.start, node.end))
        comma = True
    f.write(']')


bos_pattern = re.compile('#BOS ([0-9]+) +[^ ]+ +[^ ]+ ([0-9]+)([ \t]*%%.*)?')


def transform_filter(fname, proc):
    """reads in an export file and processes the tree with proc"""
    f = open(fname, 'r')
    l = f.readline()
    while l != '':
        sys.stdout.write(l)
        m = bos_pattern.match(l)
        if m:
            sent_no = m.group(1)
            t = read_sentence(f)
            proc(t)
            write_sentence(t, sys.stdout)
            sys.stdout.write('#EOS %s\n' % (sent_no,))
        l = f.readline()
    f.close()


def read_trees(f, fmt=3):
    global doc_no
    l = f.readline()
    while l != '':
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
        l = f.readline()
    return
