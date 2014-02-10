#!/usr/bin/python
# -*- encoding: iso-8859-15 -*-
'''
Utility functions to deal with SPMRL format
'''

import optparse
import re
import sys
from lingtree import penn, tree
from lingtree.tree import TerminalNode, NontermNode, Tree

tokens_table=[(code, re.compile(rgx))
              for (code, rgx) in
               [('(','\(([^\s#]+)(?:##(\S+)*##)? *'),
                ('( ','\( +'),
                ('W','([^\(\)\s]+) *'),
                (')','\) *')]]
def tokenize_spmrl(s):
    idx=0
    result=[]
    while idx<len(s):
        for code, rgx in tokens_table:
            m=rgx.match(s,idx)
            if m:
                result.append((code,)+m.groups())
                idx=m.end()
                break
        if not m:
            result.append(('?',s[idx]))
            idx+=1
    return result

def spmrl2nodes(lst, recode_word=None, props2morph=None):
    idx=0
    result=[]
    while idx<len(lst):
        code=lst[idx][0]
        if code=='(':
            lab=lst[idx][1]
            if '-' in lab:
                (lab,elabel)=lab.split('-')
            else:
                elabel=None
            if lst[idx][2]:
                props=dict([x.split('=',1) for x in lst[idx][2].split('|') if '=' in x])
            else:
                props={}
            if lst[idx+1][0]=='W':
                # terminal symbol
                word=lst[idx+1][1]
                if recode_word is not None:
                    word=recode_word(word)
                n=TerminalNode(lab,word)
                n.edge_label=elabel
                n.props=props
                if props2morph is not None:
                    props2morph(n)
                result.append(n)
                idx+=2
            else:
                n=NontermNode(lab)
                n.edge_label=elabel
                if lst[idx][2]:
                    n.props=dict([x.split('=',1) for x in lst[idx][2].split('|') if '=' in x])
                result.append(n)
                idx+=1
        elif code=='( ':
            n=NontermNode('VROOT')
            result.append(n)
            idx+=1
        elif code==')':
            x=result.pop()
            if len(result)==0:
                assert idx+1==len(lst), (lst[idx+1:],result,x)
                return x
            x.parent=result[-1]
            result[-1].children.append(x)
            idx+=1
        else:
            print >>sys.stderr, "Unknown:",lst[idx]

def recode_utf8_latin1(w):
    return w.decode('UTF-8').encode('ISO-8859-15')

def read_spmrl(f, props2morph=None, encoding=None):
    if encoding in [None,'UTF-8']:
        recode_fn=None
    elif encoding in ['ISO-8859-15']:
        recode_fn=recode_utf8_latin1
    for l in f:
        node=spmrl2nodes(tokenize_spmrl(l.strip()), recode_fn, props2morph)
        t=penn.node2tree(node, node.cat=='VROOT')
        yield t


def read_lattices(f, props2morph=None, encoding=None):
    if encoding in [None,'UTF-8']:
        recode_fn=None
    elif encoding in ['ISO-8859-15']:
        recode_fn=recode_utf8_latin1
    result=[]
    for l in f:
        line=l.strip().split()
        if line==[]:
            if result:
                t=tree.Tree()
                t.terminals=result
                yield t
                result=[]
        else:
            s_start, s_end, word, lemma, cpos, pos, props0, w_idx = line
            if recode_fn is not None:
                word=recode_fn(word)
            n=TerminalNode(pos, word)
            n.lemma=lemma
            n.start=int(s_start)
            n.end=int(s_end)
            n.props=dict([p.split('=',1) for p in props0.split('|') if '=' in p])
            result.append(n)
    if result:
        t=tree.Tree()
        t.terminals=result
        yield t

def spmrl2cqp(f, columns, want_morph=False, exclude_morph=frozenset(),
              f_out=None):
    if f_out is None:
        f_out = sys.stdout
    for t in read_spmrl(f):
        print >>f_out, "<s>"
        for n in t.terminals:
            cols=[n.props.get(col,'--') for col in columns]
            if want_morph:
                prop=[(k,v) for (k,v) in n.props.iteritems() if k not in exclude_morph]
                prop.sort()
                cols.append('|'.join(['%s=%s'%p for p in prop]))
            print >>f_out, "%s\t%s\t%s"%(n.word, n.cat, '\t'.join(cols))
        print >>f_out, "</s>"

spmrl2cqp_opt=optparse.OptionParser()
spmrl2cqp_opt.add_option('-P', action='append',
                         dest='columns', default=[])
spmrl2cqp_opt.add_option('-X', action='append',
                         dest='exclude', default=[])
spmrl2cqp_opt.add_option('-M', action='store_true',
                         dest='want_morph', default=False)
def spmrl2cqp_main(argv=None):
    (opts,args)=spmrl2cqp_opt.parse_args(argv)
    spmrl2cqp(file(args[0]),opts.columns, opts.want_morph,
              set(opts.columns+opts.exclude))
