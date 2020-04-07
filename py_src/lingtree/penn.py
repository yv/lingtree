#!/usr/bin/python
# -*- encoding: iso-8859-15 -*-
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
        node.start = start
        for n in node.children:
            pos = number_ids(t, n, pos)
        node.end = pos
        return pos

def number_nodes(node, node_table, start=500):
    if node.isTerminal():
        return start
    for n in node.children:
        start = number_nodes(n, start)
    node.id = start
    node_table[start] = node
    return start+1

def node2tree(node, has_vroot=True):
    t = Tree()
    t.terminals = []
    if has_vroot:
        t.roots = node.children
        for root in t.roots:
            root.parent = None
    else:
        t.roots = [node]
    number_ids(t, node)
    return t


def spmrl2nodes(lst, split_dash=True):
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


def read_spmrl(f, props2morph=None):
    for l in f:
        node = spmrl2nodes(tokenize_penn(l.strip()), props2morph)
        t = node2tree(node, node.cat == 'VROOT')
        yield t
