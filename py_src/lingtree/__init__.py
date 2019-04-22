from __future__ import print_function
import sys
from .tree import Tree, TerminalNode, NontermNode

__all__ = ['read_trees', 'Tree',
           'TerminalNode', 'NontermNode']


def read_trees(fname, fmt=None, encoding=None):
    """reads trees in a particular format (SPMRL, Export etc.)"""
    if fmt is None:
        if fname.endswith('.export'):
            fmt = 'export'
        elif fname.endswith('.xml'):
            fmt = 'tigerxml'
        else:
            raise ValueError("Can't guess format for %s" % (fname,))
    if fmt == 'export':
        from lingtree import export
        trees = export.read_trees(open(fname))
        if encoding is None:
            encoding = 'latin1'
    elif fmt == 'spmrl':
        from lingtree import read_spmrl
        trees = read_spmrl.read_spmrl(open(fname))
        if encoding is None:
            encoding = 'UTF-8'
    elif fmt == 'tigerxml':
        from lingtree import tigerxml
        if encoding is None:
            encoding = 'UTF-8'
        trees = tigerxml.read_trees(fname, encoding)
    else:
        print("Input format %s not supported." % (fmt,), file=sys.stderr)
        sys.exit(1)
    return trees
