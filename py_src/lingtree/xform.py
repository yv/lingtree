#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-
import re
import sys

import tree

def find_label(nodes,labelSet):
    '''returns the index of the first node with a label in labelSet
    or -1 if there aren\'t any'''
    for (i,n) in enumerate(nodes):
        if n.cat in labelSet:
            return i
    return -1

def binVC_proc(t):
    # unwrap LK, VC
    binVC(t.roots)
    # classify VXINF, VXFIN according to ...
    # binarize non-finite VXes
##    sys.stderr.write('after BinVC: %s\n'%(
##        ' '.join(map(lambda n:n.to_full([]),tree.roots)),))

def binVC(nodes):
    i=0
    parent=nodes[0].parent
    while i<len(nodes):
        n=nodes[i]
        if n.cat in ['LK','VC']:
            new_nodes=handle_vc(n)
            for n1 in new_nodes: n1.parent=parent
            nodes[i:i+1]=new_nodes
            i+=len(new_nodes)
        else:
            i+=1
        if not n.isTerminal():
            assert n.children,n.to_penn()
            binVC(n.children)

nonfinite_re=re.compile(r'VX.[^F]|VXINF|V.(?:INF|PP|IZU)')
def isNonFinite(node):
    return nonfinite_re.match(node.cat)

def isConjunction(node):
    for n in node.children:
        if n.edge_label=='KONJ': return True
    return False

def handle_vc(parent):
    nodes=parent.children
    # classify the nodes
    for n in nodes:
        if isConjunction(n):
            # nicht behandelt, sondern mitbehandelt
            cat=None
            for n1 in n.children:
                if n1.edge_label=='KONJ':
                    if n1.isTerminal():
                        # hin- und hergeschoben
                        if not cat and n1.cat.startswith('V'):
                            cat=n1.cat
                            cat='VX%s%s'%(cat[1],vx_cat_map[cat[2:]])
                    else:
                        classify_vx(n1)
                        if not cat: cat=n1.cat
            assert cat
            n.cat=cat
        else:
            if n.cat not in ['PTKVZ','TRUNC'] and not n.isTerminal():
                classify_vx(n)
    while len(nodes)>1 and isNonFinite(nodes[0]) and isNonFinite(nodes[1]):
        cat1=nodes[0].cat
        cat2=nodes[1].cat
        #sys.stderr.write('BinVC: %s %s\n'%(cat1,cat2))
        assert cat1.startswith('VX')
        assert cat2.startswith('VX')
        # VXVI + VXMF -> VXVF
        new_node=tree.NontermNode('VX%s%s'%(cat1[2],cat2[3]))
        new_node.start=nodes[0].start
        new_node.end=nodes[1].end
        new_node.edge_label=nodes[1].edge_label
        nodes[1].edge_label='HD'
        nodes[0].parent=new_node
        nodes[1].parent=new_node
        new_node.children=nodes[0:2]
        nodes[0:2]=[new_node]
    return nodes

vx_cat_map={'FIN':'F', 'PP':'P', 'INF':'I', 'IZU':'Z','IMP':'M'}
def classify_vx(node):
    chlds=node.children
    if not chlds: assert False,node.parent.to_penn()
    cat=chlds[0].cat
    running=True
    while running:
        if cat=='ADVX' and len(chlds)>1:
            chlds=chlds[1:]
            cat=chlds[0].cat
        elif cat=='TRUNC' and len(chlds)>2 and chlds[1].cat=='KON':
            chlds=chlds[2:]
            cat=chlds[0].cat
        else:
            running=False
    if cat=='PTKZU':
        if len(chlds)>1:
            new_cat='VX%sZ'%(chlds[1].cat[1],)
        else:
            # most likely an error => treat as PTKVZ
            return
    elif cat=='FM':
        # TODO: "Kafka (VC (FM goes)) Kleinkunst"
        return
    elif cat=='PTKVZ':
        # zusammen passt, bekannt gemacht, bekannt zu machen (Igitt!)
        # TODO: zu weinen an
        assert len(chlds)>1,node.to_penn()
        cat2=chlds[1].cat
        if cat2=='PTKZU':
            new_cat='VX%sZ'%(vx_cat_map[node.children[2].cat[2:]])
        else:
            assert cat2[0]=='V', cat2
            new_cat='VX%s%s'%(cat2[1],vx_cat_map[cat2[2:]])
    elif not(cat.startswith('V')):
        # vom Fußball ab- und dem Feiern wieder zugewandt
        return
    else:
        ##assert cat.startswith('V'), cat
        new_cat='VX%s%s'%(cat[1],vx_cat_map[cat[2:]])
    node.cat=new_cat

def rename_ncx(t):
    for node in t.topdown_enumeration():
        if node.cat=='NCX':
            node.cat='NX'

def is_nx(n):
    if n is None: return False
    return n.cat.startswith('NX') or n.cat.startswith('NCX')

def fix_gmod_app_proc(t):
    for n in t.roots:
        do_gmod_app(n)

def do_gmod_app(n):
    for n1 in n.children:
        do_gmod_app(n1)
    if is_nx(n) and is_nx(n.parent) and n.edge_label=='-':
        if n.cat[:-2] in ['_n','_a','_d']:
            n.edge_label='APP'
        elif n.cat[:-2]=='_g':
            if n.parent.cat[:-2]=='_g':
                # genitive parent. this may be a problem
                if n.cat.startswith('NCX') and len(n.children)==1:
                    n.edge_label='APP'
                else:
                    n.edge_label='GMOD'
            else:
                n.edge_label='GMOD'

def fix_pis_proc(t):
    for n in t.roots:
        do_fix_pis(n)

not_nx_re=re.compile('^(?:SIMPX|ADJX|ADVX)(?:_.*)?$')

# TODO: evtl. auch NX_[ ? Oder EN-ADD einfügen oder ...
def do_fix_pis(n):
    for n1 in n.children:
        do_fix_pis(n1)
    if (n.cat in ['NX_*','NCX_*'] and
        n.edge_label in ['ON','OA','OD','OD','PRED']):
        if n.edge_label=='PRED':
            realcase='n'
        else:
            realcase=n.edge_label[1].lower()
        n1=n
        while n1:
            if n1.cat.endswith('_*'):
                n1.cat=n1.cat[:-1]+realcase
            chlds=n1.children
            n1=None
            for n2 in chlds:
                if n2.edge_label=='HD':
                    n1=n2

def nx_mod_proc(t):
    for n in t.topdown_enumeration():
        do_nx_mod(n)

def do_nx_mod(n):
    if is_nx(n) and n.edge_label in ['MOD','V-MOD']:
        if n.parent.cat=='NF':
            n.edge_label='MOD-APP'
        else:
            n.cat='NX-MOD'

def munge_mf_proc(t):
    for n in t.roots:
        do_munge_mf(n)

def do_munge_mf(n):
    if n.cat.startswith('MF_'):
        args=n.cat[3:].split('_')
        n1=n
        pos=0
        chlds=n.children
        while pos<len(chlds):
            chlds[pos].parent=n1
            do_munge_mf(chlds[pos])
            if chlds[pos].edge_label==args[0]:
                if pos+1<len(chlds):
                    n2=tree.NontermNode("%s<%s"%(n.cat,args[0]),"M-REST")
                    n2.children=chlds[pos+1:]
                    n2.parent=n1
                    del chlds[pos+1:]
                    chlds.append(n2)
                    chlds=n2.children
                    n1=n2
                    pos=0
                else:
                    pos=pos+1
            else:
                pos=pos+1
    else:
        for n1 in n.children:
            do_munge_mf(n1)

def munge_kokom(n):
    if n.cat in ['NX','NCX','PX','ADJX','ADVX']:
        pos=find_label(n.children,['KOKOM'])
        if pos!=-1 and pos+1!=len(n.children):
            n1=tree.NontermNode(n.cat,'cj')
            n1.id=n.id
            n1.children=n.children[pos+1:]
            n.children[pos+1:]=[n1]
            n.cat='KomX'
            n.id=None
            for n2 in n1.children:
                n2.parent=n1
    for n1 in n.children:
        munge_kokom(n1)

def do_kill_en_add(t):
    """removes NEs (both old-style EN-ADD nodes
    and new-style =SEMCLS node suffixes"""
    kill_en_add(t.roots)

def kill_en_add(chlds):
    pos=find_label(chlds,['EN-ADD'])
    while pos!=-1:
        n1=chlds[pos]
        if len(n1.children)==1:
            chlds[pos:pos+1]=n1.children
            n1.children[0].parent=n1.parent
            n1.children[0].edge_label=n1.edge_label
        else:
            chlds[pos:pos+1]=n1.children
            for n2 in n1.children:
                n2.parent=n1.parent
        pos=find_label(chlds,['EN-ADD'])
    for n1 in chlds:
        if '=' in n1.cat:
            n1.cat=n1.cat[:n1.cat.index('=')]
        if n1.edge_label=='-NE':
            n1.edge_label='-'
        kill_en_add(n1.children)

def guess_vc_cat(chlds,pos,cat):
    cat1=chlds[pos].cat
    if cat1[-1] in "FM" and pos>0:
        # finite verb 
        cat0=chlds[pos-1].cat
        if cat0=='VF':
            return pos+1,'LK'
    pos1=pos+1
    while pos1<len(chlds) and chlds[pos1].cat.startswith('VX'):
        pos1+=1
    if pos1<len(chlds):
        cat2=chlds[pos1].cat
        if cat2 in ['MF','PTKVZ']:
            return pos1,'LK'
    return pos1,'VC'
            

def add_lk_vc(n):
    if n.cat in ['SIMPX','R-SIMPX','FKONJ','FKOORD','VF']:
        pos=0
        while pos<len(n.children):
            cat1=n.children[pos].cat
            if cat1.startswith('VX'):
                pos2,catN=guess_vc_cat(n.children,pos,n.cat)
                n1=tree.NontermNode(catN,'-')
                n1.children=n.children[pos:pos2]
                for n2 in n1.children:
                    n2.parent=n1
                n1.parent=n
                n.children[pos:pos2]=[n1]
            if cat1=='PTKVZ':
                n1=tree.NontermNode('VC','-')
                n1.children=[n.children[pos]]
                n.children[pos].parent=n1
                n1.parent=n
                n.children[pos]=n1
            pos+=1
    for n2 in n.children:
        add_lk_vc(n2)

def add_lk_vc_proc(t):
    for n in t.roots:
        add_lk_vc(n)

def unrename_nx(n):
    if '-' in n.cat:
        if n.cat not in ['R-SIMPX','EN-ADD']:
            pos=n.cat.index('-')
            n.cat=n.cat[:pos]
    for n1 in n.children:
        unrename_nx(n1)

def unrename_nx_proc(t):
    for n in t.roots:
        unrename_nx(n)

def fix_gmbh(n):
    """we want GmbH and AG to be postmodifiers, TüBa-D/Z says they're heads"""
    if n.cat=='NX' and len(n.children)==2:
        first=n.children[0]
        second=n.children[1]
        if (first.cat=='NX' and second.edge_label=='HD' and
            second.isTerminal() and second.word in ['AG','GmbH']):
            sys.stderr.write('fix_gmbh: %s\n'%(n.to_penn()))
            first.edge_label='HD'
            second.edge_label='-'
    for n1 in n.children:
        fix_gmbh(n1)

def do_vf_mf(n):
    # TODO: Im Fall von [VF Ausschlaggebend für die Punkteeinbuße aber]
    # muß das "aber" ans Verb
    if n.cat=='MF' and n.parent and n.parent.cat=='VF':
        if n.children[0].cat=='ADJX':
            n.cat=n.children[0].cat
            n.edge_label=n.children[0].edge_label
            n.children[0].edge_label='HD'
    for nn in n.children:
        do_vf_mf(nn)
def vf_mf_proc(t):
    for n in t.roots:
        do_vf_mf(n)
def sanitize_proc(t):
    for n in t.roots:
        munge_kokom(n)
    kill_en_add(t.roots)
    for n in t.roots:
        fix_gmbh(n)
        do_vf_mf(n)
