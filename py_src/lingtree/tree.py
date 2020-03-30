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
from builtins import hex
from builtins import str
from builtins import object
import sys
import re

atom_pl = re.compile(r"[a-z][a-zA-Z_0-9]*$")
unwanted_pl = re.compile(r"([\\'])")


def escape_prolog(string):
    if not string:
        return "''"
    if atom_pl.match(string):
        return string
    res = unwanted_pl.sub(r"\\\1", string)
    return "'%s'" % (res,)


unwanted_mrg = re.compile(r"([^A-Za-z0-9\x80-\xff\-_])")


def escape_mrg(string):
    if not string:
        return ''
    return unwanted_mrg.sub(r"\\\1", string)


def bottomup_enumeration(nodes):
    # print "bottomup_enumeration: %s"%(nodes)
    for n in nodes:
        for n1 in bottomup_enumeration(n.children):
            yield n1
        yield n


def descendants(node):
    for n in node.children:
        yield n
        for n1 in descendants(n):
            yield n1
    return


def determine_tokenspan(node):
    if not node.isTerminal():
        assert node.children, (node.cat, node.id)
        node.start = min([x.start for x in node.children])
        node.end = max([x.end for x in node.children])


class Tree(object):
    __slots__ = ['node_table', 'roots', 'terminals', '__dict__']

    def __getstate__(self):
        return (self.node_table,
                self.roots,
                self.terminals,
                self.__dict__)

    def __setstate__(self, state):
        self.node_table, self.roots, self.terminals, self.__dict__ = state
    """represents a syntax tree"""

    def __init__(self):
        self.node_table = {}
        self.roots = []
        self.terminals = []

    def __iter__(self):
        return iter(self.roots)

    def bottomup_enumeration(self):
        return bottomup_enumeration(self.roots)

    def topdown_enumeration(self):
        for n in self.roots:
            yield n
            for n1 in descendants(n):
                yield n1
        return

    def determine_tokenspan_all(self):
        "determines the tokenspan for all nodes and sorts children accordingly"
        for node in self.bottomup_enumeration():
            determine_tokenspan(node)
            node.children.sort(key=lambda x: x.start)
        self.roots.sort(key=lambda x: x.start)

    def check_roots(self):
        for n in self.roots:
            assert n.parent == None
            self.check_nodes(n, [])

    def check_nodes(self, node, parents):
        if node.parent == None:
            assert parents == []
        else:
            assert node.parent == parents[-1]
        parents.append(node)
        for n in node.children:
            assert not n in parents
            self.check_nodes(n, parents)
        del parents[-1]

    def renumber_ids(self, nodes=None, start=500):
        """gives ids to all nonterminal nodes."""
        pos = start
        if nodes == None:
            nodes = self.roots
        for n in nodes:
            if not n.isTerminal():
                # print "Renumber %r: entering %s, pos=%d"%(n.id,pos)
                pos = 1+self.renumber_ids(n.children, pos)
                #sys.stderr.write("Renumber %r: %s => %d\n"%(n,n.id,pos))
                n.id = "%s" % pos
                self.node_table[n.id] = n
        return pos

    def check_nodetable(self):
        for key in self.node_table:
            if self.node_table[key].id != key:
                raise "Nodetable: node %s(%r) has id %s" % (key,
                                                            self.node_table[key], self.node_table[key].id)
            assert self.node_table[key].id == key
            if self.node_table[key].parent == None:
                assert self.node_table[key] in self.roots
            else:
                parent = self.node_table[key].parent
                assert self.node_table[parent.id] == parent

    def discontinuity(self, nodes, index, sent_node):
        """returns True iff there is a discontinuity between
        the Nth and the N+1th member of nodes, ignoring
        punctuation and parentheses."""
        if nodes[index].end == nodes[index+1].start:
            return False
        sys.stderr.write('Looking for a discontinuity between %r and %r' % (
            self.terminals[nodes[index].end],
            self.terminals[nodes[index+1].start]))
        for n in self.terminals[nodes[index].end:nodes[index+1].start]:
            n1 = n
            while n1 != None:
                if n1 == sent_node:
                    return True
                n1 = n1.parent
        return False


# abstract base class for all nodes
class Node(object):
    def __init__(self, cat):
        self.id = None
        self.start = -1
        self.end = -1
        self.cat = cat
        self.children = []
        self.parent = None

    def add_at(self, node, pos):
        self.children[pos:pos] = [node]
        node.set_parent(self)

    def append(self, node):
        self.children.append(node)
        node.set_parent(self)

    def insert(self, node):
        "inserts a node at the appropriate position"
        node.set_parent(self)
        for (i, n) in enumerate(self.children):
            if (n.start >= node.start):
                self.children[i:i] = [node]
                return
        self.append(node)

    def set_parent(self, parent):
        self.parent = parent


class NontermNode(Node):
    "Node class for nonterminal node"

    def __init__(self, cat, edge_label=None):
        Node.__init__(self, cat)
        self.edge_label = edge_label
        self.attr = '--'

    def __repr__(self):
        stuff = ''
        if hasattr(self, 'xml_id'):
            stuff += '#'+self.xml_id
        stuff += ' at '+hex(id(self))
        return '<%s.%s%s>' % (self.cat, self.edge_label, stuff)

    def isTerminal(self):
        return False

    def __str__(self):
        return '<NonTerm %s #%s>' % (self.cat, self.id)

    def to_penn(self):
        if self.edge_label:
            a = "(%s.%s " % (self.cat, self.edge_label)
        else:
            a = "(%s " % (self.cat)
        a += ' '.join([x.to_penn() for x in self.children])
        a += ")"
        return a

    def to_full(self, wanted_attrs):
        pairs = []
        for key in wanted_attrs:
            pairs.append('%s=%s' %
                         (key, escape_mrg(str(getattr(self, key, '--')))))
        a = "(%s" % (escape_mrg(self.cat))
        if pairs:
            a = a+"=#i[%s]" % (' '.join(pairs))
        a += " %s)" % (' '.join([x.to_full(wanted_attrs) for x in self.children]),)
        return a


class TerminalNode(Node):
    "Node class for a preterminal node"

    def __init__(self, cat, word, edge_label=None, morph=None):
        Node.__init__(self, cat)
        self.word = word
        self.edge_label = edge_label
        self.morph = morph

    def __repr__(self):
        if hasattr(self, 'xml_id'):
            stuff = '#'+self.xml_id
        else:
            stuff = '(%d)' % (self.start)
        return '<%s/%s%s at %s>' % (self.word, self.cat, stuff, hex(id(self)))

    def isTerminal(self):
        return True

    def to_penn(self):
        if self.edge_label:
            return "(%s.%s %s)" % (self.cat, self.edge_label, self.word)
        else:
            return "(%s %s)" % (self.cat, self.word)

    def to_full(self, wanted_attrs):
        pairs = []
        for key in wanted_attrs:
            pairs.append('%s=%s' %
                         (key, escape_mrg(str(getattr(self, key, '--')))))
        a = "(%s" % (escape_mrg(self.cat),)
        if pairs:
            a = a+"=#i[%s]" % (' '.join(pairs))
        a += " %s)" % (escape_mrg(self.word),)
        return a
