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
'''
Classes that realize simple schemes as they are used in
TigerXML or PML
'''

class SimpleSchema(object):
    def __init__(self, name, cls=None, kind="Markable"):
        self.name = name
        self.attributes = []
        self.edges = []

    def attribute_by_name(self, att_name):
        for att in self.attributes:
            if att.name == att_name:
                return att
        raise KeyError(att_name)
    def add_attribute(self, att):
        self.attributes.append(att)

    def edge_by_name(self, name):
        for edge in self.edges:
            if edge.name == name:
                return edge
        raise KeyError(name)
    def add_edge(self, edge):
        self.edges.append(edge)

class SimpleAttribute(object):
    def __init__(self, name):
        self.name = name
        self.names = []
        self.descriptions = {}
    def add_item(self, name, description=None):
        if name not in self.descriptions:
            self.names.append(name)
        if description is not None:
            self.descriptions[name] = description

def make_export_schema():
    '''
    returns a terminal and nonterminal schema
    that corresponds to the information encoded
    in Negra Export
    '''
    t_schema = SimpleSchema("word")
    for att_name in ['word', 'lemma', 'pos', 'morph', 'func']:
        att = SimpleAttribute(att_name)
        t_schema.add_attribute(att)
    nt_schema = SimpleSchema('node')
    for att_name in ['cat', 'func']:
        att = SimpleAttribute(att_name)
        nt_schema.add_attribute(att)
    secedge = SimpleSchema('secedge')
    secedge.add_attribute(SimpleAttribute('func'))
    nt_schema.add_edge(secedge)
    return (t_schema, nt_schema)
