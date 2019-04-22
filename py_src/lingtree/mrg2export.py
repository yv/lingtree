#!/usr/bin/env python
from __future__ import absolute_import
import sys
import re
import getopt

from . import tree
from . import export
from . import penn
from . import xform
from . import util

xform_procs = {
    'fix_gmod_app': xform.fix_gmod_app_proc,
    'fix_pis': xform.fix_pis_proc,
    'nx_mod': xform.nx_mod_proc,
    'munge_mf': xform.munge_mf_proc,
    'add_lk_vc': xform.add_lk_vc_proc,
    'unrename_nx': xform.unrename_nx_proc}
xform_init = {}

relabel_rules = {}


def strip_deco_proc(t):
    do_strip_deco(t.roots)


deco_re = re.compile('_.*')


def do_strip_deco(nodes):
    for n in nodes:
        n.cat = deco_re.sub('', n.cat)
        if not n.isTerminal():
            do_strip_deco(n.children)


xform_procs['strip'] = strip_deco_proc


def unmarkovize_proc(t):
    do_unmarkovize(t.roots)


def do_unmarkovize(nodes):
    parent = nodes[0].parent
    i = 0
    while i < len(nodes):
        n = nodes[i]
        if not n.isTerminal():
            do_unmarkovize(n.children)
        if n.edge_label in ['M-REST', 'M-HD']:
            for n1 in n.children:
                n1.parent = parent
            nodes[i:i+1] = n.children
        else:
            i += 1


xform_procs['unmarkovize'] = unmarkovize_proc

xform_procs['binvc'] = xform.binVC_proc


def unattach_proc(t):
    do_unattach(t.roots[:], t.roots)


def do_unattach(nodes, roots):
    punct = []
    for i, n in enumerate(nodes):
        if n.isTerminal() and n.cat in ['$.', '$,', '$(']:
            punct.append(i)
        elif n.edge_label == 'PAR':
            punct.append(i)
        do_unattach(n.children, roots)
    punct.reverse()
    for i in punct:
        n = nodes[i]
        n.parent = None
        roots.append(n)
        del nodes[i]


xform_procs['unattach'] = unattach_proc


def undecorate_proc(t):
    do_undecorate(t.roots)


undecorate_re = re.compile(r'([^_]+)_.*')


def do_undecorate(nodes):
    for n in nodes:
        n.cat = undecorate_re.sub(r'\1', n.cat)
        do_undecorate(n.children)


xform_procs['undecorate'] = undecorate_proc


def usage():
    sys.stderr.write('''
Usage: mrg2export [ opts ] file.mrg
Options:
    -d Dir
    --dir Dir   set grammar directory (for relabeling)
    -p          output prolog terms
    -x Transform(s)
    --xform Transform(s)
                Transform the trees. Possible transforms:
        relabel:        relabel according to grammar file
        unmarkovize:    unmarkovize the trees
        unattach:       unattach punctuation
    -n SentNum  start with SentNum instead of 1
''')


if __name__ == '__main__':
    prolog = False
    sentnum = 1
    xforms = []
    output = sys.stdout
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'hpd:x:n:o:',
                                   ['help', 'prolog', 'xform=', 'num='])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, a in opts:
        if o == '-o':
            output = open(a, 'w')
        elif o in ('-d', '--dir'):
            pass
        elif o in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif o in ('-n', '--num'):
            sentnum = int(a)
        elif o in ('-p', '--prolog'):
            prolog = True
        elif o in ('-x', '--xform'):
            for xname in a.split(','):
                xforms.append(xform_procs[xname])
                if xname in xform_init:
                    xform_init[xname]()
    if args:
        for fname in args:
            for line in open(fname, 'r'):
                if line.startswith('No parse for'):
                    # TODO: put unparsed sentences into the export file
                    if prolog:
                        output.write(
                            'parsed_sentence(%d,[],unparsed).\n' % (sentnum,))
                    sentnum += 1
                else:
                    try:
                        t = tree.Tree()
                        parsed = penn.line2parse(line)
                        t.terminals = []
                        penn.number_ids(t, parsed)
                        parsed.id = 0
                        t.roots = parsed.children
                        for xform in xforms:
                            xform(t)
                        tree.node_table = {}
                        t.renumber_ids()
                        if prolog:
                            t.determine_tokenspan_all()
                            output.write('parsed_sentence(%d,[],' % (sentnum,))
                            export.write_sentence_prolog(output, t.roots, 2)
                            output.write(').\n')
                        else:
                            output.write('#BOS %d 0 0 0\n' % (sentnum,))
                            export.write_sentence(t, output)
                            output.write('#EOS %d\n' % (sentnum,))
                    except ValueError:
                        sys.stderr.write('ERROR: Could not parse sentence %s:%d\n' % (
                            fname, sentnum))
                    sentnum += 1
    else:
        sys.stderr.write('No input files specified.\n')
        sys.exit(1)
    output.close()
