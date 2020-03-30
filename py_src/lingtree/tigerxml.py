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
deals with the TigerXML file format for treebanks.
Reading support is limited to "standard" attributes.
Writing support requires lxml, also limited to "standard"
attributes
"""
from __future__ import print_function
from builtins import str, bytes
import sys
from .tree import Tree, TerminalNode, NontermNode
try:
    from lxml import etree
    def write_node(f_out, s_node, encoding):
        f_out.write(etree.tostring(s_node, pretty_print=True,
                                   encoding=encoding))
except ImportError:
    import xml.etree.cElementTree as etree
    def add_some_space(node, indent=''):
        chlds = list(node)
        if chlds:
            node.text = '\n  '+indent
            for n in chlds:
                add_some_space(n, indent+'  ')
            chlds[-1].tail = '\n'+indent
        node.tail = '\n'+indent
    def write_node(f_out, s_node, encoding):
        # add some basic formatting
        add_some_space(s_node)
        s_result = etree.tostring(s_node, encoding=encoding)
        # strip xml header.
        if '<?' in s_result:
            idx = s_result.index('?>')
            s_result = s_result[idx+2:]
        f_out.write(s_result)
from xml.sax.saxutils import quoteattr, escape

def encoded_attrib(n, att, default_val):
    att_val = n.attrib.get(att, default_val)
    return att_val


def get_terminals(graph, term_ref):
    '''makes terminals out of all the TigerXML terminals'''
    terminals = []
    for n in graph.find('terminals').findall('t'):
        try:
            w = n.attrib['word']
        except KeyError:
            w = n.attrib['orth']
        trm = TerminalNode(encoded_attrib(n, 'pos', '--'), w)
        for k in ['morph', 'lemma']:
            if k in n.attrib:
                val = n.attrib[k]
                setattr(trm, k, val)
        trm.xml_id = n.attrib['id']
        assert not trm.xml_id in term_ref, (term_ref[trm.xml_id], trm)
        term_ref[trm.xml_id] = trm
        terminals.append(trm)
    return terminals



#pylint:disable=C0103
def tiger_sent(node):
    'decodes the TigerXML sentence from the given XML node'
    t = Tree()
    term_ref = {}
    graph = node.find('graph')
    try:
        node_id = node.attrib['id']
        if node_id[0] == 's':
            node_id = node_id[1:]
        t.sent_no = int(node_id)
    except ValueError:
        t.sent_no = node.attrib.get('id', None)
    t.terminals = get_terminals(graph, term_ref)
    for n in graph.find('nonterminals').findall('nt'):
        nt = NontermNode(encoded_attrib(n, 'cat', '--'))
        nt.xml_id = n.attrib['id']
        term_ref[nt.xml_id] = nt
    for n in graph.find('nonterminals').findall('nt'):
        nt = term_ref[n.attrib['id']]
        chlds = []
        for e in n.findall('edge'):
            x = term_ref[e.attrib['idref']]
            assert x.parent is None, (nt, x.parent, x)
            x.edge_label = encoded_attrib(e, 'label', None)
            x.parent = nt
            chlds.append(x)
        nt.children = chlds
    for n in graph.find('nonterminals').findall('nt'):
        nt = term_ref[n.attrib['id']]
        if (not hasattr(nt, 'parent') or nt.parent is None or
                nt.parent.cat == 'VROOT'):
            nt.parent = None
            if nt.cat != 'VROOT':
                t.roots.append(nt)
    for i, n in enumerate(graph.find('terminals').findall('t')):
        trm = term_ref[n.attrib['id']]
        trm.start = i
        trm.end = i + 1
        if (not hasattr(trm, 'parent') or trm.parent is None or
                trm.parent.cat == 'VROOT'):
            trm.parent = None
            trm.edge_label = '--'
            if trm.cat != 'VROOT':
                t.roots.append(trm)
    t.renumber_ids()
    t.determine_tokenspan_all()
    return t


def assign_node_ids(t, suffix=''):
    """
    makes sure that a tree, and all its terminal
    and nonterminal nodes, have a suitable xml_id
    attribute.
    """
    if hasattr(t, 'xml_id'):
        sent_id = t.xml_id
    elif hasattr(t, 'sent_no'):
        sent_id = 's%s'%(t.sent_no,)
        if sent_id[:2] == 'ss':
            sent_id = sent_id[1:]
        t.xml_id = sent_id
    elif hasattr(t, 'sent_id'):
        sent_id = str(t.sent_id)
        t.xml_id = sent_id
    for i, n in enumerate(t.terminals):
        if not hasattr(n, 'xml_id'):
            n.xml_id = '%s_%s'%(sent_id, i+1)
    node_id = 500
    for n in t.bottomup_enumeration():
        if n.isTerminal():
            continue
        if hasattr(n, 'xml_id'):
            continue
        n.xml_id = '%s_n%s%s'%(sent_id, node_id, suffix)
        node_id += 1

def make_string(n, attname):
    """look for an attribute of a node and returns the attribute, or --"""
    if hasattr(n, attname):
        val = getattr(n, attname, None)
        if val is None:
            return '--'
        else:
            return str(val)

def read_trees(fname):
    '''yields the sequence of trees in an XML file'''
    #pylint:disable=W0612
    for ev, elem in etree.iterparse(fname):
        if elem.tag == 's':
            yield tiger_sent(elem)
            elem.clear()

def read_kbest_lists(fname):
    '''
    reads kbest lists of trees
    '''
    for ev, elem in etree.iterparse(fname):
        if elem.tag == 'sentence':
            node_gold = elem.find('gold-tree')
            node_gold_s = node_gold.find('s')
            t_gold = tiger_sent(node_gold_s)
            kbest = []
            for node_kbest in elem.findall('kbest-tree'):
                node_kbest_s = node_kbest.find('s')
                assert node_kbest_s is not None, node_kbest
                t = tiger_sent(node_kbest_s)
                if 'model-score' in node_kbest.attrib:
                    t.score = float(node_kbest.attrib['model-score'])
                if 'score' in node_kbest.attrib:
                    t.eval_score = float(node_kbest.attrib['score'])
                kbest.append(t)
            yield (t_gold, kbest)
            elem.clear()

def encode_tree(t, encoding=None, always_vroot=True,
                id_suffix='', extra_term_att=None,
                extra_nt_att=None):
    '''returns an XML node describing a tree'''
    if encoding is None:
        encoding = t.encoding
    assign_node_ids(t, suffix=id_suffix)
    s_node = etree.Element('s')
    s_node.attrib['id'] = t.xml_id
    graph = etree.SubElement(s_node, 'graph')
    trms_node = etree.SubElement(graph, 'terminals')
    for n in t.terminals:
        trm = etree.SubElement(trms_node, 't')
        trm.attrib['id'] = n.xml_id
        trm.attrib['word'] = n.word
        trm.attrib['pos'] = n.cat
        trm.attrib['morph'] = make_string(n, 'morph')
        if hasattr(n, 'lemma') and n.lemma is not None:
            trm.attrib['lemma'] = n.lemma
        if extra_term_att:
            for att in extra_term_att:
                if hasattr(n, att) and getattr(n, att) is not None:
                    trm.attrib[att] = make_string(n, att)
    nts_node = etree.SubElement(graph, 'nonterminals')
    for n in t.bottomup_enumeration():
        if n.isTerminal():
            continue
        nt_node = etree.SubElement(nts_node, 'nt')
        nt_node.attrib['id'] = n.xml_id
        nt_node.attrib['cat'] = n.cat
        if extra_nt_att:
            for att in extra_nt_att:
                if hasattr(n, att) and getattr(n, att) is not None:
                    nt_node.attrib[att] = make_string(n, att)
        for chld in n.children:
            edge = etree.SubElement(nt_node, 'edge')
            edge.attrib['label'] = make_string(chld, 'edge_label')
            edge.attrib['idref'] = chld.xml_id
    if always_vroot or len(t.roots) > 1:
        vroot = etree.SubElement(nts_node, 'nt',
                                 cat='VROOT',
                                 id='%s_VROOT'%(t.xml_id,))
        for n in t.roots:
            edge = etree.SubElement(vroot, 'edge',
                                    label=make_string(n, 'edge_label'),
                                    idref=n.xml_id)
        graph.attrib['root'] = '%s_VROOT'%(t.xml_id,)
    else:
        graph.attrib['root'] = t.roots[0].xml_id
    return s_node

def describe_schema(f_out, schema, domain, encoding):
    for attr in schema.attributes:
        if hasattr(attr, 'names'):
            if attr.name == 'func':
                if domain == 'NT':
                    continue
                else:
                    print('    <edgelabel>', file=f_out)
            else:
                print('    <feature name="%s" domain="%s">'%(
                    attr.name, domain), file=f_out)
            for name in attr.names:
                print('      <value name=%s>%s</value>'%(
                    quoteattr(name),
                    escape(attr.descriptions[name].encode(encoding))), file=f_out)
            if attr.name == 'func':
                print('    </edgelabel>', file=f_out)
            else:
                print('    </feature>', file=f_out)
        else:
            print('    <feature name="%s" domain="%s"/>'%(
                attr.name, domain), file=f_out)

def write_tiger_file(f_out, trees, meta=None, encoding="UTF-8",
                     corpus_id="pytree_output"):
    print('<?xml version="1.0" encoding="%s" standalone="yes"?>'%(encoding,), file=f_out)
    print('<corpus id="%s">'%(corpus_id,), file=f_out)
    print('<head>', file=f_out)
    #TODO print meta information
    if meta:
        print('  <annotation>', file=f_out)
        nt_cat = meta['NT'].attribute_by_name('cat')
        if 'VROOT' not in nt_cat.descriptions:
            nt_cat.add_item('VROOT', 'virtual root node')
        describe_schema(f_out, meta['T'], 'T', encoding)
        describe_schema(f_out, meta['NT'], 'NT', encoding)
        print('  </annotation>', file=f_out)
    print('</head>', file=f_out)
    print('<body>', file=f_out)
    for t in trees:
        s_node = encode_tree(t, None)
        write_node(f_out, s_node, encoding)
    print("</body>", file=f_out)
    print("</corpus>", file=f_out)


def tiger2export_main(args):
    '''converts one file into .export format (body only)'''
    from . import export
    for i, t in enumerate(read_trees(args[0])):
        # BOS ([0-9]+) +[^ ]+ +[^ ]+ ([0-9]+)([ \t]*%%.*)?')
        print("#BOS %d -1 -1 0" % (i + 1,))
        export.write_sentence_tabs(t, sys.stdout)
        print("#EOS %d" % (i + 1,))

if __name__ == '__main__':
    tiger2export_main(sys.argv[1:])
