"""
deals with the TigerXML file format for treebanks.
Currently, only allows reading.
"""
from __future__ import print_function
import sys
from .tree import Tree, TerminalNode, NontermNode
import xml.etree.cElementTree as etree


def get_terminals(graph, term_ref):
    """makes terminals out of all the TigerXML terminals"""
    terminals = []
    for n in graph.find('terminals').findall('t'):
        w = n.attrib['word']
        trm = TerminalNode(n.attrib['pos'], w)
        for k in ['morph', 'lemma']:
            if k in n.attrib:
                setattr(trm, k, n.attrib[k])
        trm.xml_id = n.attrib['id']
        assert not trm.xml_id in term_ref, (term_ref[trm.xml_id], trm)
        term_ref[trm.xml_id] = trm
        terminals.append(trm)
    return terminals

# pylint:disable=C0103


def tiger_sent(node):
    """decodes the TigerXML sentence from the given XML node"""
    t = Tree()
    term_ref = {}
    graph = node.find('graph')
    try:
        t.sent_no = int(node.attrib['id'])
    except ValueError:
        t.sent_no = node.attrib.get('id', None)
    t.terminals = get_terminals(graph, term_ref)
    for n in graph.find('nonterminals').findall('nt'):
        nt = NontermNode(n.attrib['cat'])
        nt.xml_id = n.attrib['id']
        term_ref[nt.xml_id] = nt
    for n in graph.find('nonterminals').findall('nt'):
        nt = term_ref[n.attrib['id']]
        chlds = []
        for e in n.findall('edge'):
            x = term_ref[e.attrib['idref']]
            assert x.parent is None, (nt, x.parent, x)
            x.edge_label = e.attrib['label']
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


def assign_node_ids(t):
    """
    makes sure that a tree, and all its terminal
    and nonterminal nodes, have a suitable xml_id
    attribute.
    """
    if hasattr(t, 'xml_id'):
        sent_id = t.xml_id
    elif hasattr(t, 'sent_no'):
        sent_id = 's%s' % (t.sent_no,)
        t.xml_id = sent_id
    elif hasattr(t, 'sent_id'):
        sent_id = str(t.sent_id)
        t.xml_id = sent_id
    for i, n in enumerate(t.terminals):
        if not hasattr(n, 'xml_id'):
            n.xml_id = '%s_%s' % (sent_id, i+1)
    node_id = 500
    for n in t.bottomup_enumeration():
        if n.isTerminal():
            continue
        if hasattr(n, 'xml_id'):
            continue
        n.xml_id = '%s_n%s' % (sent_id, node_id)
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
    """yields the sequence of trees in an XML file"""
    # pylint:disable=W0612
    for ev, elem in etree.iterparse(fname):
        if elem.tag == 's':
            yield tiger_sent(elem)
            elem.clear()


def encode_tree(t):
    """returns an XML node describing a tree"""
    assign_node_ids(t)
    s_node = etree.Element('s')
    s_node.attrib['id'] = t.xml_id
    graph = etree.SubElement(s_node, 'graph')
    trms_node = etree.SubElement(graph, 'terminals')
    for i, n in enumerate(t.terminals):
        trm = etree.SubElement(trms_node, 't')
        trm.attrib['id'] = n.xml_id
        trm.attrib['word'] = n.word
        trm.attrib['pos'] = n.cat
        trm.attrib['morph'] = make_string(n, 'morph')
    nts_node = etree.SubElement(graph, 'nonterminals')
    for n in t.bottomup_enumeration():
        if n.isTerminal():
            continue
        nt_node = etree.SubElement(nts_node, 'nt')
        nt_node.attrib['id'] = n.xml_id
        nt_node.attrib['cat'] = n.cat
        for chld in n.children:
            edge = etree.SubElement(nt_node, 'edge')
            edge.attrib['label'] = make_string(chld, 'edge_label')
            edge.attrib['idref'] = chld.xml_id
    if len(t.roots) == 1:
        graph.attrib['root'] = t.roots[0].xml_id
    else:
        vroot = etree.SubElement(nts_node, 'nt',
                                 cat='VROOT',
                                 id='%s_VROOT' % (t.xml_id,))
        for n in t.roots:
            edge = etree.SubElement(vroot, 'edge',
                                    label=make_string(n, 'edge_label'),
                                    idref=n.xml_id)
    return s_node


def tiger2export_main(args):
    """converts one file into .export format (body only)"""
    from . import export
    for i, t in enumerate(read_trees(args[0])):
        # BOS ([0-9]+) +[^ ]+ +[^ ]+ ([0-9]+)([ \t]*%%.*)?')
        print("#BOS %d -1 -1 0" % (i + 1,))
        export.write_sentence_tabs(t, sys.stdout)
        print("#EOS %d" % (i + 1,))


if __name__ == '__main__':
    tiger2export_main(sys.argv[1:])
