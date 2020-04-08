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

from __future__ import print_function
from builtins import open, str, bytes
import optparse
import sys
import re
from .conll import detect_encoding, encoding_equivalent, merge_trees_generic
from itertools import chain

def add_tree_options(oparse):
    '''
    include options that read_trees wants to see
    '''
    oparse.add_option('-F', '--fmt',
                      dest='format',
                      choices=['json', 'export', 'export4', 'mrg', 'tigerxml'],
                      default=None)
    oparse.add_option('-I',
                      help='assume that input file(s) is in this encoding',
                      dest='inputenc',
                      default=None)
    oparse.add_option('--fold', dest='foldspec',
                      help='selected range/fold, e.g. 1-40000 or trainfinal1/5')

default_oparse = optparse.OptionParser()
add_tree_options(default_oparse)
default_opts = default_oparse.parse_args([])[0]

stag_re = re.compile('<s(?: ([0-9a-z]+))?> *')

def read_mrg_trees(fname, encoding=None):
    sent_no = 1
    if encoding is None:
        encoding = detect_encoding(fname)
    for l in open(fname, 'r', encoding=encoding):
        from . import penn, tree
        if l[:2] == '<s':
            m = stag_re.match(l)
            assert m, l
            if m.group(1) is not None:
                sent_no = int(m.group(1))
            l = l[m.end():].strip()
            if l.endswith(' </s>'):
                l = l[:-4]
        n = penn.line2parse(l)
        t = tree.Tree()
        penn.number_ids(t, n)
        t.roots = n.children
        for nn in n.children:
            nn.parent = None
        t.sent_no = sent_no
        sent_no += 1
        yield t

def read_trees(fname, opts=None):
    """
    reads trees in a particular format (SPMRL, Export etc.)

    ``fname`` -- the name of the input file

    ``opts`` (default: ``None``)
    an options object that contains additional information

    The :func:`add_tree_options` function offers a convenent way to add such
    options to an existing OptionParser object::

        oparse = OptionParser()
        add_tree_options(oparse)
        oparse.add_option('--frobnicate', action='store_true',
                          help='Another interesting option')


    returns an iterator over the trees of the treebank (i.e., read_trees
    has to be called again or the sequence has to be put into a list if you
    want to be able to jump back and forth within the sequence.
    """
    if opts is None:
        opts = default_oparse.parse_args([])[0]
    opt_format = opts.format
    if opt_format is None:
        if fname.endswith('.export3'):
            opt_format = 'export'
        elif fname.endswith('.export'):
            opt_format = 'export_guess'
        elif fname.endswith('.export4'):
            opt_format = 'export4'
        elif fname.endswith('.xml'):
            opt_format = 'tigerxml'
        elif fname.endswith('.mrg'):
            opt_format = 'mrg'
        elif fname.endswith('.ptb'):
            opt_format = 'spmrl'
        elif fname.endswith('.json'):
            opt_format = 'json'
        else:
            raise ValueError("Can't guess format for %s (specify -F ...)"%(fname,))
    if opt_format == 'export_guess':
        from . import export
        opt_format = export.guess_format_version(fname)
        print("%s: guessed %s"%(fname, opt_format), file=sys.stderr)
    if opt_format == 'export3':
        from . import export
        inputenc = opts.inputenc
        if inputenc is None:
            inputenc = detect_encoding(fname)
        trees = export.read_trees(open(fname, 'r', encoding=inputenc),
                                  fmt=3)
    elif opt_format == 'export4':
        from . import export
        inputenc = opts.inputenc
        if inputenc is None:
            inputenc = detect_encoding(fname)
        trees = export.read_trees(open(fname, 'r', encoding=inputenc), fmt=4)
    elif opt_format == 'spmrl':
        from . import spmrl
        trees = spmrl.read_spmrl(open(fname, 'r', encoding='UTF-8'))
    elif opt_format == 'tigerxml':
        from . import tigerxml
        trees = tigerxml.read_trees(fname)
    elif opt_format == 'json':
        if opts.tree_enc is None:
            opts.tree_enc = 'UTF-8'
        from . import export
        trees = export.read_trees_json(open(fname, 'r', encoding='UTF-8'))
    elif opt_format == 'mrg':
        trees = read_mrg_trees(fname, opts.inputenc)
    else:
        print("Input format %s not supported."%(opt_format,), file=sys.stderr)
        sys.exit(1)
    if opts.foldspec:
        from .folds import parse_foldspec
        folder = parse_foldspec(opts.foldspec)
        trees = folder.apply_filter(trees)
    return trees

def read_trees_meta(fname, opts=None):
    """
    reads trees in a particular format (SPMRL, Export etc.),
    returning both metadata and a sequence of trees

    ``fname`` -- the name of the input file

    ``opts`` (default: ``None``)
    an options object that contains additional information

    The :func:`add_tree_options` function offers a convenent way to add such
    options to an existing OptionParser object::

        oparse = OptionParser()
        add_tree_options(oparse)
        oparse.add_option('--frobnicate', action='store_true',
                          help='Another interesting option')


    returns an iterator over the trees of the treebank (i.e., read_trees
    has to be called again or the sequence has to be put into a list if you
    want to be able to jump back and forth within the sequence.
    """
    if opts is None:
        opts = default_oparse.parse_args([])[0]
    opt_format = opts.format
    if opt_format is None:
        if fname.endswith('.export3'):
            opt_format = 'export'
        elif fname.endswith('.export4'):
            opt_format = 'export4'
        elif fname.endswith('.export'):
            opt_format = 'export_guess'
        elif fname.endswith('.xml'):
            opt_format = 'tigerxml'
        elif fname.endswith('.mrg'):
            opt_format = 'mrg'
        elif fname.endswith('.ptb'):
            opt_format = 'spmrl'
        elif fname.endswith('.json'):
            opt_format = 'json'
        else:
            raise ValueError("Can't guess format for %s (specify -F ...)"%(fname,))
    if opt_format == 'export_guess':
        from . import export
        opt_format = export.guess_format_version(fname)
        print("%s guessed %s"%(fname, opt_format), file=sys.stderr)
    meta = None
    if opt_format == 'export4':
        from . import export
        if opts.inputenc is None:
            opts.inputenc = detect_encoding(fname)
        f = open(fname, 'r', encoding=opts.inputenc)
        meta, bos_l = export.read_export_header(f, fmt=4,)
        trees = export.read_trees(f, fmt=meta['FMT'], last_bos=bos_l)
    elif opt_format == 'export3':
        from . import export
        if opts.inputenc is None:
            opts.inputenc = detect_encoding(fname)
        f = open(fname, 'r', encoding=opts.inputenc)
        meta, bos_l = export.read_export_header(f, fmt=3)
        trees = export.read_trees(f, fmt=3, last_bos=bos_l)
    elif opts.format == 'spmrl':
        from . import spmrl
        trees = spmrl.read_spmrl(open(fname, 'r', encoding='UTF-8'))
    elif opts.format == 'tigerxml':
        from . import tigerxml
        trees = tigerxml.read_trees(fname)
    elif opts.format == 'json':
        from . import export
        trees = export.read_trees_json(open(fname, 'r', encoding='UTF-8'))
    elif opts.format == 'mrg':
        trees = read_mrg_trees(fname, opts.inputenc)
    else:
        print("Input format %s not supported."%(opts.format,), file=sys.stderr)
        sys.exit(1)
    if opts.foldspec:
        from .folds import parse_foldspec
        folder = parse_foldspec(opts.foldspec)
        trees = folder.apply_filter(trees)
    return (meta, trees)

def write_trees_meta(fname, trees, meta=None, fmt=None, **kw):
    if fmt == 'tigerxml':
        from . import tigerxml
        with open(fname, 'w', encoding='UTF-8') as f_out:
            tigerxml.write_tiger_file(f_out, trees, meta)
    else:
        from . import export
        with open(fname, 'w', encoding='UTF-8') as f_out:
            if fmt in ['export3', 'export4']:
                export.write_export_file(f_out, trees, meta, fmt)
            else:
                export.write_json_file(f_out, trees)

oparse_convert = optparse.OptionParser(usage='%prog [options] input out.json')
add_tree_options(oparse_convert)
oparse_convert.add_option('--outfmt', dest='outfmt',
                          help='output format (default:json)',
                          default='json',
                          choices=['json', 'export', 'export4', 'mrg',
                                   'tigerxml', 'pml'])
oparse_convert.add_option('--preproc', dest='preproc',
                          help='file with preprocessing')
oparse_convert.add_option('--preproc-fmt', dest='preproc_fmt',
                          help='file format of preprocessed data',
                          default='plain',
                          choices=['plain', 'conllx', 'conll09'])

def transformed_trees(trees, xforms):
    '''
    takes a tree iterator and yields transformed trees
    '''
    for t in trees:
        for xform in xforms:
            xform(t)
        yield t

def convert_main(argv=None):
    from . import export
    opts, args = oparse_convert.parse_args(argv)
    if len(args) != 2:
        oparse_convert.print_help()
        sys.exit(1)
    meta, trees = read_trees_meta(args[0], opts)
    if opts.preproc is not None:
        trees = merge_trees_generic(trees, opts.preproc, opts.preproc_fmt)
    write_trees_meta(args[1], trees, meta, opts.outfmt,
                     **opts.__dict__)

def merge_meta(all_meta):
    return all_meta[0]

def join_main(argv=None):
    '''
    merge several treebanks into a single file.
    '''
    opts, args = oparse_convert.parse_args(argv)
    if len(args) < 2:
        oparse_convert.print_help()
        sys.exit(1)
    all_meta = []
    all_trees = []
    for arg in args[:-1]:
        meta, trees = read_trees_meta(arg, opts)
        all_meta.append(meta)
        all_trees.append(trees)
    meta = merge_meta(all_meta)
    trees = chain(*all_trees)
    write_trees_meta(args[-1], trees, meta, opts.outfmt,
                     **opts.__dict__)

oparse_totext = optparse.OptionParser(usage='%prog [options] input out.json')
add_tree_options(oparse_totext)
oparse_totext.add_option('-P', dest='attrs',
                         help='additional attribute',
                         default=[], action='append')
oparse_totext.add_option('--outfmt', dest='outfmt',
                         help='output format (default:txt)',
                         default='txt',
                         choices=['txt', 'line', 'cqp', 'chk', 'conll'])

def totext_main(argv=None):
    opts, args = oparse_totext.parse_args(argv)
    if len(args) != 2:
        oparse_totext.print_help()
        sys.exit(1)
    if opts.outfmt in ['line', 'chk']:
        field_sep = '_'
        line_sep = ' '
    else:
        field_sep = '\t'
        line_sep = '\n'
    trees = read_trees(args[0], opts)
    with open(args[1], 'w', encoding='UTF-8') as f_out:
        for t in trees:
            lines = []
            if opts.outfmt == 'cqp':
                if hasattr(t, 'sent_no'):
                    lines.append('<s id="%s">'%(t.sent_no))
                else:
                    lines.append('<s>')
            elif opts.outfmt == 'chk':
                if hasattr(t, 'sent_no'):
                    lines.append('<s %s>'%(t.sent_no))
                else:
                    lines.append('<s>')
            for n in t.terminals:
                w = n.word
                if opts.outfmt == 'conll':
                    cols = [str(n.start+1), n.word]
                else:
                    cols = [n.word]
                for col in opts.attrs:
                    col_val = getattr(n, col, '_')
                    if col_val is None:
                        col_val = '_'
                    cols.append(col_val)
                lines.append(field_sep.join(cols))
            if opts.outfmt in ['cqp', 'chk']:
                lines.append('</s>')
            f_out.write(line_sep.join(lines))
            if opts.outfmt in ['line', 'cqp', 'chk']:
                f_out.write('\n')
            elif opts.outfmt in ['txt', 'conll']:
                f_out.write('\n\n')
