'''
package/program for transforming trees (e.g. to a format needed to
train a parser model)
'''
from __future__ import print_function

import sys
import optparse
from . import export, export2mrg, wrappers, tree, read_trees
from .util import load_plugin

oparse = optparse.OptionParser()
oparse.add_option('--fmt', dest='format',
                  choices=['export', 'tigerxml', 'spmrl'])
oparse.add_option('--encoding', dest='inputenc')
oparse.add_option('--outputenc', dest='outputenc',
                  default='UTF-8')
oparse.add_option('--xform', dest='xform')
oparse.add_option('--tokenfilter', dest='filter',
                  default=[], action='append')
oparse.add_option('--keepquotes', dest='delquotes',
                  action='store_false', default=True)
oparse.add_option('--outfmt', dest='target',
                  choices=['vpf', 'bllip', 'bky', 'bkylab', 'export'],
                  default='bky')
oparse.add_option('--range', dest='range', default=None)


def munge_cats(node):
    """
    adds edge labels to nodes and makes categories compatible with
    penn-style format
    """
    w = '%s:%s' % (node.cat, node.edge_label)
    w = w.replace('(', '-LRB-')
    w = w.replace(')', '-RRB-')
    w = w.replace('-', '_')
    node.cat = w
    if node.isTerminal():
        w = node.word
        w = w.replace('(', '_LRB_')
        w = w.replace(')', '_RRB_')
        node.word = w
    else:
        for n in node.children:
            munge_cats(n)


def munge_cats_nolabel(node):
    """
    makes categories compatible with
    penn-style format
    """
    w = node.cat
    w = w.replace('(', '-LRB-')
    w = w.replace(')', '-RRB-')
    w = w.replace('-', '_')
    node.cat = w
    if node.isTerminal():
        w = node.word
        w = w.replace('(', '_LRB_')
        w = w.replace(')', '_RRB_')
        node.word = w
    else:
        for n in node.children:
            munge_cats_nolabel(n)


PUNCT_TRANSFORMS = [load_plugin('tree_transform', x)
                    for x in 'attach_parens attach_punct_alt'.split()]


def apply_transforms(t, transforms, opts):
    """applies the transforms from transforms"""
    for fn in transforms:
        fn(t)
    if opts.delquotes:
        export2mrg.do_del_quotes(t)
        # is this even necessary?
        t.determine_tokenspan_all()
    for fn in PUNCT_TRANSFORMS:
        fn(t)
    return t


def apply_pipeline(t, pipeline, opts):
    "applies a token pipeline"
    if pipeline is not None:
        line = ' '.join([n.word for n in t.terminals])
        if opts.inputenc != 'UTF-8':
            line = line.decode(opts.inputenc)
            line = line.encode('UTF-8')
        for filt in pipeline:
            line = filt.process_line(line)
        if opts.outputenc != 'UTF-8':
            line = line.decode('UTF-8')
            line = line.encode(opts.outputenc)
        for n, w in zip(t.terminals, line.strip().split()):
            n.word = w
    else:
        if opts.inputenc != opts.outputenc:
            for n in t.terminals:
                n.word = n.word.decode(
                    opts.inputenc).encode(opts.outputenc)


def write_tree_vpf(t, f):
    """writes a tree in the VPF format expected by mkrules"""
    n = tree.NontermNode('Start')
    n.children = t.roots
    print(n.to_full(['edge_label']), file=f)


def write_tree_bky(t, f):
    """writes a tree for the Berkeley parser (ROOT symbol,
       no dashes in node names, no opening/closing parens)"""
    vroot = tree.NontermNode('ROOT')
    vroot.children = t.roots
    munge_cats_nolabel(vroot)
    print(vroot.to_full([]).replace('\\', ''), file=f)


def write_tree_bkylab(t, f):
    """writes a tree for the Berkeley parser (ROOT symbol,
       no dashes in node names, no opening/closing parens)"""
    vroot = tree.NontermNode('ROOT')
    vroot.children = t.roots
    munge_cats(vroot)
    print(vroot.to_full([]).replace('\\', ''), file=f)


def write_tree_bllip(t, f):
    """writes a tree for the BLLIP (Charniak) parser
       (need to check whether this gives the correct
       result
    """
    vroot = tree.NontermNode('S1')
    vroot.children = t.roots
    munge_cats_nolabel(vroot)
    print(vroot.to_full([]).replace('\\', ''), file=f)


def tree_writer(opts):
    """returns the tree writer appropriate for these options"""
    fmt = opts.target
    if fmt == 'vpf':
        write_tree = write_tree_vpf
    elif fmt == 'bky':
        write_tree = write_tree_bky
    elif fmt == 'bllip':
        write_tree = write_tree_bllip
    elif fmt == 'export':
        def write_tree(t, f):
            """we need to add the #EOS, since write_sentence does not."""
            export.write_sentence_tabs(t, f)
            print('#EOS %s' % (t.sent_no,), file=f)
    else:
        raise ValueError('No tree writer for:'+fmt)
    return write_tree


def parse_range(range_expr):
    """parses a range expression and returns a list of tuples"""
    result = []
    for part in range_expr.split(','):
        if '-' in part:
            start_s, end_s = part.split('-')
            result.append((int(start_s), int(end_s) + 1))
        else:
            start = int(part)
            result.append((start, start + 1))
    return result


def trees_in_range(trees, ranges):
    """"given a ranges specification,
    (as a list of start and end points), filters
    the trees from the iterator"""
    r_id = 0
    in_range = False
    for i, t in enumerate(trees):
        if not in_range:
            if i + 1 >= ranges[r_id][0]:
                print("Starting ranges %d-%d" % (
                    ranges[r_id][0], ranges[r_id][1]), file=sys.stderr)
                in_range = True
        else:
            if i + 1 >= ranges[r_id][1]:
                print("Stopped ranges %d-%d" % (
                    ranges[r_id][0], ranges[r_id][1]), file=sys.stderr)
                in_range = False
        if in_range:
            yield t


def find_transforms(opts):
    """retrieves the tree transforms that are needed for the given options"""
    if opts.xform is None:
        return []
    if opts.xform == 'tiger':
        #TODO: complete list of transforms to be used for tiger
        desc_exprs = 'uncross_branches'.split()
    elif opts.xform == 'tueba':
        #TODO: complete list of transforms to be used for Tueba
        desc_exprs = []
    else:
        desc_exprs = opts.xform.split(',')
    xforms = []
    for desc in desc_exprs:
        xforms.append(load_plugin('tree_transform', desc))
    return xforms


def do_transform_main(argv=None):
    """
    puts together a transformation
    pipeline and runs it
    """
    opts, args = oparse.parse_args(argv)
    trees = read_trees(args[0], opts)
    write_tree = tree_writer(opts)
    xforms = find_transforms(opts)
    if opts.filter:
        pipeline = [wrappers.make_token_pipeline(filt) for filt in opts.filter]
    else:
        pipeline = None
    if opts.range:
        ranges = parse_range(opts.range)
        trees = trees_in_range(trees, ranges)
    for t in trees:
        apply_transforms(t, xforms, opts)
        apply_pipeline(t, pipeline, opts)
        write_tree(t)


if __name__ == '__main__':
    do_transform_main()
