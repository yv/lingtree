#!/usr/bin/env python
from __future__ import absolute_import
import sys
import re
import getopt

from . import tree
from . import export
from . import xform

xform_procs = {'binvc': xform.binVC_proc, 'rename_ncx': xform.rename_ncx}
xform_init = {}


def do_addlabels(t):
    for n in t.topdown_enumeration():
        n.cat = '%s_%s' % (n.cat, n.edge_label)


xform_procs['addlabels'] = do_addlabels


def insert_material(node, nodes, pos):
    """inserts a node into a list of nodes, possibly recursing into
        child nodes. The result should be projective."""
    index = pos-1
    #sys.stderr.write('Insert %r into %r[0:%d]\n'%(node,nodes,pos))
    assert nodes, (nodes, node)
    assert nodes[0].start <= node.start, node.to_full()
    assert len(nodes) >= pos
    assert max([n.end for n in nodes[:pos]]
               ) >= node.end, "node=%s,nodes=%s,pos=%d" % (node, nodes, pos)
    while index >= 0:
        if nodes[index].start > node.start:
            index -= 1
            continue
        if node.end <= nodes[index].end:
            new_nodes = nodes[index].children
            return insert_material(node, new_nodes, len(new_nodes))
        elif (nodes[index].end <= node.start and
                node.end <= nodes[index+1].start):
            nodes[index+1:index+1] = [node]
            # sys.stderr.write('Inserted %r between %r and %r.\n'%(
            #    nodes[index+1],nodes[index],nodes[index+2]))
            return True
    sys.stderr.write('Cannot insert %r into %r\n' % (node, nodes))
    assert False


def do_attach_par(t):
    """attaches parenthetic material with a PAR node"""
    # find parenthetic material
    # i.e. nonterminals that break projectivity
    i = 0
    pos = 0
    while i < len(t.roots):
        n = t.roots[i]
        if n.start < pos:
            par_node = tree.NontermNode('PAR', 'PAR')
            par_node.children = [n]
            par_node.start = n.start
            par_node.end = n.end
            n.parent = par_node
            # reattach it
            del t.roots[i]
            insert_material(par_node, t.roots, i)
        else:
            pos = n.end
            i += 1


xform_procs['attach_par'] = do_attach_par


def attach_parens(t):
    """attaches parentheses"""
    # gather parentheses pairwise
    pars = []
    parstack = []
    for (i, n) in t.roots:
        if n.isTerminal():
            if n.word == '(':
                parstack.append((i, n))
            elif n.word == ')':
                if parstack:
                    pars.append((parstack.pop(), (i, n)))
                else:
                    sys.stderr.write('Lonely closing paren!')
    # make an intermediary node
    # find a matching node
    # insert in parent iff edge_label=APP or parent.cat=PAR
    pass


def do_attach_punct(t):
    """attach punctuation"""
    # find parenthetic material
    # i.e. nonterminals that break projectivity
    i = 0
    pos = 0
    # find material that breaks projectivity
    while i < len(t.roots):
        n = t.roots[i]
        if n.start < pos:
            # reattach it
            del t.roots[i]
            # sys.stderr.write('%s\n'%(n.to_full(['start','end']),))
            # sys.stderr.write(
            #     'Reattaching punctuation: %r (index=%d start=%d pos=%d)\n'%(
            #         n,i,n.start,pos))
            # sys.stderr.write('%r\n'%(t.roots,))
            insert_material(n, t.roots, i)
        else:
            pos = n.end
            i += 1


xform_procs['attach_punct'] = do_attach_punct

quotes_re = re.compile(r'["\'`]|\.\.\.')


def do_del_quotes(t):
    """removes quotes and ellipses"""
    i = 0
    while i < len(t.roots):
        n = t.roots[i]
        if n.isTerminal() and quotes_re.match(n.word):
            del t.roots[i]
        else:
            i += 1


xform_procs['del_quotes'] = do_del_quotes


def usage():
    sys.stderr.write('''
Usage: export2mrg.py [options] sourcefile.export
Options:
    -o      specify output file (default: stdout)
    -h
    --help  display this message
    -x
    --xform apply the specified transformation(s)
            addlabels:    appends the edge labels to the node
            attach_par:   attach parenthetic material via a "PAR" node
            attach_punct: attach punctuation and other dangling stuff
            del_quotes:   remove quotes and ellipses (...)
            rename_ncx:   rename NCX to NX
''')
    sys.exit(0)


if __name__ == '__main__':
    xforms = []
    output = sys.stdout
    wanted_attrs = ['edge_label', 'morph']
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'hd:x:o:a:',
                                   ['help', 'xform=', 'attrs=', 'no-attrs'])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, a in opts:
        # TODO: support sentence ranges (e.g. 1-3000,15000-15020)
        if o == '-o':
            output = file(a, 'w')
        elif o in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif o in ('-x', '--xform'):
            for xname in a.split(','):
                xforms.append(xform_procs[xname])
                if xname in xform_init:
                    xform_init[xname]()
        elif o in ('-a', '--attrs'):
            wanted_attrs = a.split(',')
        elif o == '--no-attrs':
            wanted_attrs = []
    if args:
        for fname in args:
            f = file(fname, 'r')
            line = f.readline()
            while line != '':
                line = line.strip()
                m = export.bos_pattern.match(line)
                if m:
                    sys.stderr.write('\rSentence %s' % (m.group(1),))
                    t = export.read_sentence(f)
                    t.determine_tokenspan_all()
                    for proc in xforms:
                        proc(t)
                    output.write('(Start')
                    for n in t.roots:
                        output.write(' ')
                        output.write(n.to_full(wanted_attrs))
                    output.write(')\n')
                line = f.readline()
            sys.stderr.write('\ndone.\n')
    output.close()
