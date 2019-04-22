#!/usr/bin/python
# -*- encoding: iso-8859-15 -*-
"""
Utility functions to deal with normal bracketed format
"""
from __future__ import print_function
import sys
import re
from .tree import TerminalNode, NontermNode, Tree

tokens_table = [(code, re.compile(rgx))
                for (code, rgx) in
                [('(', '\\(([^\\s]+) *'),
                 ('( ', '\\( +'),
                 ('W', '([^\\(\\)\\s]+) *'),
                 (')', '\\) *')]]


def tokenize_penn(s):
    idx = 0
    result = []
    while idx < len(s):
        for code, rgx in tokens_table:
            m = rgx.match(s, idx)
            if m:
                result.append((code,)+m.groups())
                idx = m.end()
                break
        if not m:
            result.append(('?', s[idx]))
            idx += 1
    return result


def number_ids(t, node, start=0):
    """
    assigns start and end positions to
    _node_ and all its descendants
    """
    if node.isTerminal():
        node.start = start
        node.end = start+1
        t.terminals.append(node)
        return start+1
    else:
        pos = start
        for n in node.children:
            pos = number_ids(t, n, pos)
        return pos


def node2tree(node, has_vroot=True):
    t = Tree()
    t.terminals = []
    if has_vroot:
        t.roots = node.children
    else:
        t.roots = [node]
    number_ids(t, node)
    return t


def spmrl2nodes(lst, recode_word=None, split_dash=True):
    idx = 0
    result = []
    while idx < len(lst):
        code = lst[idx][0]
        if code == '(':
            lab = lst[idx][1]
            if split_dash and '-' in lab:
                (lab, elabel) = lab.split('-')
            else:
                elabel = None
            if lst[idx+1][0] == 'W':
                # terminal symbol
                word = lst[idx+1][1]
                if recode_word is not None:
                    word = recode_word(word)
                n = TerminalNode(lab, word)
                n.edge_label = elabel
                result.append(n)
                idx += 2
            else:
                n = NontermNode(lab)
                n.edge_label = elabel
                result.append(n)
                idx += 1
        elif code == '( ':
            n = NontermNode('VROOT')
            result.append(n)
            idx += 1
        elif code == ')':
            x = result.pop()
            if len(result) == 0:
                assert idx+1 == len(lst), (lst[idx+1:], result, x)
                return x
            x.parent = result[-1]
            result[-1].children.append(x)
            idx += 1
        else:
            raise ValueError("Unknown:" + lst[idx])


def line2parse(s):
    """
    given a line with a bracketed parse, returns
    a node corresponding to that parse
    """
    lst = tokenize_penn(s.strip())
    node = spmrl2nodes(lst)
    return node


def recode_utf8_latin1(w):
    return w.decode('UTF-8').encode('ISO-8859-15')


def read_spmrl(f, props2morph=None, encoding=None):
    if encoding in [None, 'UTF-8']:
        recode_fn = None
    elif encoding in ['ISO-8859-15']:
        recode_fn = recode_utf8_latin1
    for l in f:
        node = spmrl2nodes(tokenize_spmrl(l.strip()), recode_fn, props2morph)
        t = node2tree(node, node.cat == 'VROOT')
        yield t
