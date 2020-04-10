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
Performs dependency conversion
"""
import sys
from past.builtins import basestring
from collections import defaultdict

messages = {
    'nolabel': "Could not determine label (%s:%s.%s %s:%s.%s)\n",
    'nohead': "No head for %s\n",
    'no_syn_parent': "syn_parent attribute not set: %s\n",
}


def default_warning_handler(w, args):
    sys.stderr.write(messages[w] % args)


warning_handler = default_warning_handler


class DepsError(Exception):

    def __init__(self, node, msg):
        self.node = node
        self.msg = msg

    def __str__(self):
        return '%s (%s)' % (self.msg, self.node)


class LabelFinder:

    def __init__(self, labelRules):
        self.labelRules = labelRules

    def __call__(self, adjunct, headNode, parentNode):
        assert adjunct.head
        assert headNode.head
        pos1 = adjunct.head.cat
        cat1 = adjunct.cat
        lbl1 = adjunct.edge_label
        pos2 = headNode.head.cat
        cat2 = parentNode.cat
        lbl2 = headNode.edge_label
        for pat1, pat2, label in self.labelRules:
            if pat1:
                if ((pat1[0] is None or pos1 in get_items(pat1[0])) and
                        (pat1[1] is None or cat1 in get_items(pat1[1])) and
                        (pat1[2] is None or lbl1 in get_items(pat1[2]))):
                    pass
                else:
                    continue
            if pat2:
                if ((pat2[0] is None or pos2 in get_items(pat2[0])) and
                        (pat2[1] is None or cat2 in get_items(pat2[1])) and
                        (pat2[2] is None or lbl2 in get_items(pat2[2]))):
                    pass
                else:
                    continue
            return label
        warning_handler('nolabel', (pos1, cat1, lbl1, pos2, cat2, lbl2))
        return '-UNKNOWN-'


def make_labeling_func(rules):
    return LabelFinder(rules)


def get_items(setDescr):
    if setDescr is None or isinstance(setDescr, basestring):
        return [setDescr]
    else:
        return setDescr


class HeadRule:

    def __init__(self, ruleDescr):
        self.table = {}
        self.table1 = {}
        self.table2 = {}
        self.default_pos = 1001
        self.dirs = []
        for pos, descr in enumerate(ruleDescr):
            if len(descr) == 3:
                for n in get_items(descr[0]):
                    for e in get_items(descr[1]):
                        if n is not None:
                            if e is not None:
                                self.table[(n, e)] = pos
                            else:
                                self.table1[n] = pos
                        else:
                            if e is not None:
                                self.table2[e] = pos
                            else:
                                self.default_pos = pos
            else:
                if descr[0] is not None:
                    for n in get_items(descr[0]):
                        self.table1[n] = pos
                else:
                    self.default_pos = pos
            if descr[-1] == 'r':
                self.dirs.append(True)
            elif descr[-1] == 'l':
                self.dirs.append(False)
            else:
                assert False, descr[-1]

    def findHead(self, nodes):
        tpos = 1000
        headPos = None
        table = self.table
        table1 = self.table1
        table2 = self.table2
        default_pos = self.default_pos
        for i, node in enumerate(nodes):
            cat = node.cat
            lbl = node.edge_label
            newpos = min(table.get((cat, lbl), 1001),
                         table1.get(cat, 1001),
                         table2.get(lbl, 1001),
                         default_pos)
            if newpos < tpos or (newpos == tpos and self.dirs[newpos]):
                tpos = newpos
                headPos = i
        return headPos


def make_headrules(hr_table):
    headRules = {}
    for cats, ruleDescr in hr_table:
        rule = HeadRule(ruleDescr)
        for cat in get_items(cats):
            headRules[cat] = rule
    return headRules


class SimpleDepExtractor:

    '''
    Uses a table to do head rule projection
    '''

    def __init__(self, hr_table, punctCats=(), determine_label=None,
                 root_label = None):
        self.headRules = make_headrules(hr_table)
        self.punctCats = punctCats
        if determine_label == None:
            self.determine_label = lambda adj, head, parent: ''
        else:
            self.determine_label = determine_label
        self.root_label = root_label

    def __call__(self, t):
        root_label = self.root_label
        for n in t.roots:
            head = self.treedep(n)
            head.syn_parent = None
            if root_label is not None:
                head.syn_label = root_label
            else:
                if head.cat in self.punctCats:
                    head.syn_label = ''
                else:
                    head.syn_label = 'S'
        self.modify_deps(t)

    def modify_deps(self, t):
        pass

    def treedep(self, node):
        if node.isTerminal():
            node.head = node
            return node
        # try head projection
        if node.cat in self.headRules:
            pos = self.headRules[node.cat].findHead(node.children)
        else:
            pos = self.headRules[None].findHead(node.children)
        #assert pos>=0 and pos<len(node.children)
        if pos is None or pos < 0 or pos >= len(node.children):
            warning_handler('nohead', (node,))
            pos = len(node.children) - 1
        head_node = node.children[pos]
        head = self.treedep(head_node)
        node.head = head
        self.attach(node.children[0:pos], head_node, node)
        self.attach(node.children[pos + 1:], head_node, node)
        return head

    def attach(self, nodes, headNode, parent):
        for n in nodes:
            self.attach1(n, headNode, parent)

    def attach1(self, node, headNode, parent):
        # print "attach1(%s,%s,%s)"%(node,headNode,parent)
        node.head = self.treedep(node)
        label = self.determine_label(node, headNode, parent)
        node.head.syn_parent = headNode.head
        node.head.syn_label = label


def read_headrules(f):
    """
    reads a headrules file similar to those used by rparse
    or disco-dop
    """
    rules = defaultdict(list)
    for s_line in f:
        if s_line[0] == '%':
            continue
        line = s_line.strip().split()
        if len(line) == 0:
            continue
        cat_lhs = line[0].upper()
        if line[1] == 'right-to-left':
            direction = 'r'
        else:
            direction = 'l'
        rules_lhs = rules[cat_lhs]
        cats_rhs = [x.upper() for x in line[2:]]
        rules_lhs.append((cats_rhs, None, direction))
    all_rules = [[[lhs], rhs] for (lhs, rhs) in rules.items()] + [[[None], [(None, 'l')]]]
    return all_rules
