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
import sys
import re
import codecs
import optparse
from gzip import GzipFile
from six.moves import zip_longest
from .tree import Tree, TerminalNode
from .folds import do_recombine

def detect_encoding(fname):
    try:
        from cchardet import detect
        method = 'cchardet'
    except ImportError:
        def detect(s):
            try:
                s.decode('UTF-8')
                return {'encoding':'UTF-8'}
            except UnicodeDecodeError:
                return {'encoding':'ISO-8859-15'}
        method = 'stupid [no cchardet detected]'
    if fname.endswith('.gz'):
        open_fn = GzipFile
    else:
        open_fn = open
    f = open_fn(fname, 'rb')
    data = f.read(100000)
    f.close()
    val = detect(data)
    encoding = val['encoding']
    print("%s: %s detected encoding %s"%(
        fname, method, encoding), file=sys.stderr)
    return encoding

latin1_encodings = {'iso8859-1', 'iso8859-15', 'cp1252'}

def encoding_equivalent(enc1, enc2):
    if enc1 is None:
        return enc2 is None
    else:
        if enc2 is None:
            return False
    enc1 = codecs.lookup(enc1).name
    enc2 = codecs.lookup(enc2).name
    if enc1 == enc2:
        return True
    elif enc1 in latin1_encodings and enc2 in latin1_encodings:
        return True
    else:
        return False

sno_re = re.compile('<s ([^ >]*)>(.*)</s>')
def read_conll(fname, encoding=None, use_fmt=None,
               tree_encoding=None,
               f_sno=None, sno_words=True,
               use_pdep=False,
               error_treatment='strict'):
    '''
    reads in a conll file, possibly autodetecting
    the format, and returns a sequence of trees.
    If f_sno is a file (in Charniak-like format with
    <s ID> words words words </s>
    the sentence numbers are attached to the trees returned
    and the words are stored in the orig_word attribute.
    With the use_pdep argument, the predicted (instead of gold)
    dependencies would be read
    '''
    #print("read_conll use_fmt", use_fmt, file=sys.stderr)
    lines = []
    if tree_encoding is None:
        encode_fn = lambda x: x
    else:
        encode_fn = lambda x: x.encode(tree_encoding)
    if encoding is None:
        encoding = detect_encoding(fname)
    if fname.endswith('.gz'):
        open_fn = GzipFile
    else:
        open_fn = open
    if use_fmt is None:
        with open_fn(fname, "rb") as f_guess:
            l = f_guess.readline()
            num_fields = len(l.strip().split())
            if num_fields == 10:
                use_fmt = 'conll06'
            elif num_fields == 14:
                use_fmt = 'conll09'
            elif num_fields == 8:
                use_fmt = 'conll06'
            elif num_fields == 6:
                # CoNLL-X without dep/attach columns
                use_fmt = 'conll06'
            else:
                print("Cannot guess format of %s (%d columns)"%(
                    fname, len(l.strip().split())), file=sys.stderr)
                raise ValueError()
    if use_fmt == 'conll06':
        cat_idx = 4
        mor_idx = 5
        lem_idx = 2
        if use_pdep:
            gov_idx = 8
            lbl_idx = 9
        else:
            gov_idx = 6
            lbl_idx = 7
    elif use_fmt == 'conll09':
        cat_idx = 5
        mor_idx = 7
        lem_idx = 3
        if use_pdep:
            gov_idx = 9
            lbl_idx = 11
        else:
            gov_idx = 8
            lbl_idx = 10
    elif use_fmt == 'conll09g':
        cat_idx = 4
        mor_idx = 6
        lem_idx = 2
        if use_pdep:
            gov_idx = 9
            lbl_idx = 11
        else:
            gov_idx = 8
            lbl_idx = 10
    else:
        print("Unknown format: %s"%(use_fmt,), file=sys.stderr)
        raise ValueError()
    reader_fn = codecs.getreader(encoding)
    line_no = old_line_no = 0
    for l in reader_fn(open_fn(fname, "rb"), error_treatment):
        line = l.strip().split()
        line_no += 1
        if not line:
            # careful: this code is duplicated below for the
            # case where there is no empty line at the end of the
            # .conll file
            t = Tree()
            if tree_encoding is None:
                t.encoding = encoding
            else:
                t.encoding = tree_encoding
            nodes = []
            for i, item in enumerate(lines):
                if len(item) < lem_idx:
                    print("[line %d] conll format error: not enough fields in %s"%(
                        old_line_no+i, item,), file=sys.stderr)
                    break
                n = TerminalNode(encode_fn(item[cat_idx]), encode_fn(item[1]))
                n.start = i
                n.end = i+1
                n.morph = encode_fn(item[mor_idx])
                n.lemma = encode_fn(item[lem_idx])
                nodes.append(n)
            for n, item in zip(nodes, lines):
                if len(item) < lbl_idx:
                    item += ['_']*(lbl_idx-len(item))
                try:
                    parent_id = item[gov_idx]
                except IndexError:
                    parent_id = '0'
                if parent_id in ['0', '_']:
                    n.syn_parent = None
                else:
                    try:
                        n.syn_parent = nodes[int(parent_id)-1]
                    except ValueError:
                        print("[line %d] conll format error: %s is not a node reference"%(
                            old_line_no+n.start, parent_id,), file=sys.stderr)
                        n.syn_parent = None
                    except IndexError:
                        print("[line %d] conll format error: %s is not a node reference"%(
                            old_line_no+n.start, parent_id,), file=sys.stderr)
                        n.syn_parent = None
                try:
                    n.syn_label = encode_fn(item[lbl_idx])
                except IndexError:
                    n.syn_label = '_'
            t.terminals = nodes
            t.roots = nodes[:]
            if f_sno:
                l_sno = f_sno.readline()
                m = sno_re.match(l_sno)
                assert m
                t.sent_no = m.group(1)
                words = m.group(2).strip().split(' ')
                assert len(words) == len(t.terminals)
                if sno_words:
                    for w, n in zip(words, t.terminals):
                        n.word = w
                else:
                    for w, n in zip(words, t.terminals):
                        n.sno_word = w
            yield t
            lines = []
            old_line_no = line_no
        else:
            lines.append(line)
    if lines:
        t = Tree()
        if tree_encoding is None:
            t.encoding = encoding
        else:
            t.encoding = tree_encoding
        nodes = []
        for i, item in enumerate(lines):
            n = TerminalNode(encode_fn(item[cat_idx]), encode_fn(item[1]))
            n.start = i
            n.end = i+1
            n.morph = encode_fn(item[mor_idx])
            n.lemma = encode_fn(item[lem_idx])
            nodes.append(n)
        for n, item in zip(nodes, lines):
            try:
                parent_id = item[gov_idx]
            except IndexError:
                parent_id = '0'
            if parent_id in ['0', '_']:
                n.syn_parent = None
            else:
                try:
                    n.syn_parent = nodes[int(parent_id)-1]
                except ValueError:
                    print("conll format error: %s is not a node reference"%(parent_id,), file=sys.stderr)
                    n.syn_parent = None
            try:
                n.syn_label = item[lbl_idx]
            except IndexError:
                n.syn_label = '_'
        t.terminals = nodes
        t.roots = nodes[:]
        if f_sno:
            l_sno = f_sno.readline()
            m = sno_re.match(l_sno)
            assert m
            t.sent_no = m.group(1)
            words = m.group(2).strip().split(' ')
            assert len(words) == len(t.terminals)
            if sno_words:
                for w, n in zip(words, t.terminals):
                    n.word = w
            else:
                for w, n in zip(words, t.terminals):
                    n.sno_word = w
        yield t

def read_tabular(fname, att_columns, encoding=None,
                 tree_encoding=None,
                 error_treatment='strict'):
    '''
    reads a (generic) tabular format into trees.

    :param att_columns: a list of property names, or None if the column
    does not correspond to a property
    '''
    cat_idx = att_columns.index('cat')
    word_idx = att_columns.index('word')
    lines = []
    if tree_encoding is None:
        encode_fn = lambda x: x
    else:
        encode_fn = lambda x: x.encode(tree_encoding)
    if encoding is None:
        encoding = detect_encoding(fname)
    if fname.endswith('.gz'):
        open_fn = GzipFile
    else:
        open_fn = open
    reader_fn = codecs.getreader(encoding)
    line_no = old_line_no = 0
    for l in reader_fn(open_fn(fname, "rb"), error_treatment):
        line = l.strip().split()
        line_no += 1
        if not line:
            # careful: this code is duplicated below for the
            # case where there is no empty line at the end of the
            # .conll file
            t = Tree()
            if tree_encoding is None:
                t.encoding = encoding
            else:
                t.encoding = tree_encoding
            nodes = []
            for i, item in enumerate(lines):
                if len(item) < len(att_columns):
                    print("[line %d] tabular format error: not enough fields in %s"%(
                        old_line_no+i, item,), file=sys.stderr)
                n = TerminalNode(encode_fn(item[cat_idx]), encode_fn(item[word_idx]))
                n.start = i
                n.end = i+1
                for i, att_name in enumerate(att_columns):
                    if att_name is not None:
                        setattr(n, att_name, encode_fn(item[i]))
                nodes.append(n)
            t.terminals = nodes
            t.roots = nodes[:]
            yield t
            lines = []
            old_line_no = line_no
        else:
            lines.append(line)
    if lines:
        t = Tree()
        if tree_encoding is None:
            t.encoding = encoding
        else:
            t.encoding = tree_encoding
        nodes = []
        t = Tree()
        if tree_encoding is None:
            t.encoding = encoding
        else:
            t.encoding = tree_encoding
        nodes = []
        for i, item in enumerate(lines):
            if len(item) < len(att_columns):
                print("[line %d] tabular format error: not enough fields in %s"%(
                    old_line_no+i, item,), file=sys.stderr)
            n = TerminalNode(encode_fn(item[cat_idx]), encode_fn(item[1]))
            n.start = i
            n.end = i+1
            for i, att_name in enumerate(att_columns):
                if att_name is not None:
                    setattr(n, att_name, encode_fn(item[i]))
            nodes.append(n)
        t.terminals = nodes
        t.roots = nodes[:]
        yield t

def from_unicode(s, encoding):
    if isinstance(s, bytes):
        return s
    else:
        return s.encode(encoding)

class TabularWriter(object):
    '''
    writes dependency trees in CoNLL format. In contrast to
    pytree_totext, this can also write the dependency column
    and not just text attributes...
    '''
    def __init__(self, f, att_columns, dep_idx=None,
                 id_idx=0):
        self.f = f
        self.att_columns = att_columns
        n_cols = len(att_columns)
        if dep_idx is not None and dep_idx >= n_cols:
            n_cols = dep_idx + 1
        self.dep_idx = dep_idx
        self.id_idx = id_idx
        self.n_cols = n_cols
    def write_tree(self, t):
        '''
        writes one tree in the selected format
        '''
        encoding = t.encoding
        nodes = t.terminals
        cols = []
        id_idx = self.id_idx
        dep_idx = self.dep_idx
        att_columns = self.att_columns
        f = self.f
        for i in range(self.n_cols):
            if i == id_idx:
                cols.append([str(j+1) for j in range(len(nodes))])
            elif i == dep_idx:
                parents = []
                for n in nodes:
                    if n.syn_parent is None:
                        parents.append('0')
                    else:
                        parents.append(str(n.syn_parent.start + 1))
                cols.append(parents)
            elif i == dep_idx + 1:
                dep_labels = [from_unicode(getattr(n, 'syn_label', '_'), encoding)
                              for n in nodes]
                cols.append(dep_labels)
            else:
                att = att_columns[i]
                if att is None:
                    cols.append(['_' for n in nodes])
                else:
                    cols.append([from_unicode(getattr(n, att, '_'), encoding) for n in nodes])
        for row in zip(*cols):
            try:
                print('\t'.join(row), file=f)
            except:
                print(row, file=sys.stderr)
                raise
        print(file=f)
    def write_trees(self, trees):
        '''
        writes a number of trees in the selected format
        '''
        for t in trees:
            self.write_tree(t)

def read_generic(fname, encoding=None,
                 tree_encoding=None,
                 error_treatment='strict'):
    '''
    reads any generic tabular format into a sequence of tables.
    '''
    lines = []
    if tree_encoding is None:
        encode_fn = lambda x: x
    else:
        encode_fn = lambda x: x.encode(tree_encoding)
    if encoding is None:
        encoding = detect_encoding(fname)
    if encoding_equivalent(encoding, tree_encoding):
        encode_fn = lambda x: x
        reader_fn = lambda x,y : x
    else:
        reader_fn = codecs.getreader(encoding)
    if fname.endswith('.gz'):
        open_fn = GzipFile
    else:
        open_fn = open
    line_no = old_line_no = 0
    for l in reader_fn(open_fn(fname, "rb"), error_treatment):
        line = [encode_fn(x) for x in l.strip().split()]
        line_no += 1
        if not line:
            if lines:
                yield lines
            lines = []
        else:
            lines.append(line)
    if lines:
        yield lines

def write_generic_single(f, lines):
    for line in lines:
        f.write('\t'.join(line)+'\n')
    f.write('\n')


def do_merge(fname_orig, fname_merge, preproc_atts,
             cpos_map=None, use_words=False, fmt_orig=None):
    #print("fmt_orig:", fmt_orig, file=sys.stderr)
    trees_orig = read_conll(fname_orig, use_fmt=fmt_orig)
    trees_merge = read_tabular(fname_merge, preproc_atts)
    need_cpos = not ('cpos' in preproc_atts)
    for t_orig, t_merge in zip_longest(trees_orig, trees_merge):
        if t_orig is None:
            words2 = [n.word for n in t_merge.terminals]
            print("more trees in merge: %s"%(
                words2,), file=sys.stderr)
            sys.exit(1)
        elif t_merge is None:
            words1 = [n.word for n in t_orig.terminals]
            print("more trees in original: %s"%(
                words1,), file=sys.stderr)
            sys.exit(1)
        words1 = [n.word for n in t_orig.terminals]
        words2 = [n.word for n in t_merge.terminals]
        if len(words1) != len(words2):
            print("Sequences do not match: %s vs %s"%(
                words1, words2), file=sys.stderr)
            sys.exit(1)
        elif words1 != words2:
            print("Sequences differ: %s vs %s"%(
                words1, words2), file=sys.stderr)
        for n, n_merge in zip(t_orig.terminals, t_merge.terminals):
            for att in preproc_atts:
                if att is not None:
                    if att != 'word' or use_words==True:
                        setattr(n, att, getattr(n_merge, att))
            # assign cpos if a pos map is given
            if cpos_map is not None:
                n.cpos = cpos_map.get(n.cat, n.cat)
            elif need_cpos:
                n.cpos = n.cat
        yield t_orig


def make_conllx_writer(fname):
    '''
    creates a TabularWriter instance suitable for writing CoNLL-X format.
    '''
    f = open(fname, 'w')
    w = TabularWriter(f,
                      [None, 'word', 'lemma', 'cpos', 'cat', 'morph',
                       None, 'syn_label', None, None],
                      dep_idx=6)
    return w

def read_mapping(fname, encoding='UTF-8'):
    result = {}
    with open(fname, 'r', encoding=encoding) as f:
        for l in f:
            line = l.strip().split()
            result[line[0]] = line[1]
    return result

oparse_merge = optparse.OptionParser(
    usage="usage: %prog [options] src.conll preproc.txt dest.conll")
oparse_merge.add_option('-F', dest='preproc_fmt',
                        choices=['plain', 'txt',
                                 'conllx', 'conll09', 'conll09g'],
                        default='plain')
oparse_merge.add_option('--fmt-orig', dest='fmt_orig',
                        choices=['conllx', 'conll09', 'conll09g'],
                        default=None)
oparse_merge.add_option('--unimap', dest='cpos_map')
oparse_merge.add_option('--use-words', dest='use_words',
                        default=False, action='store_true')

PREPROC_COLUMNS = {
    'plain': [None, 'word', 'lemma', 'cat', 'morph'],
    'txt': ['word', 'cat'],
    'conll09': [None, 'word', None, 'lemma', None, 'cat', None, 'morph'],
    'conll09g': [None, 'word', 'lemma', None, 'cat', None, 'morph'],
    'conllx': [None, 'word', 'lemma', 'cpos', 'cat', 'morph']
    }


def merge_main(argv=None):
    opts, args = oparse_merge.parse_args(argv)
    if len(args) != 3:
        oparse_merge.print_help()
        sys.exit(1)
    preproc_atts = PREPROC_COLUMNS[opts.preproc_fmt]
    if opts.cpos_map is None:
        cpos_map = None
    else:
        cpos_map = read_mapping(opts.cpos_map)
    trees = do_merge(args[0], args[1], preproc_atts,
                     fmt_orig=opts.fmt_orig,
                     cpos_map=cpos_map)
    # TODO: heuristic fix for tag assignment?
    # TODO: add word-specific part of uniset features
    # TODO: add generic filtering mechanism
    w = make_conllx_writer(args[2])
    w.write_trees(trees)

def merge_trees_generic(trees, fname_merge,
                        fmt_preproc='conllx',
                        fmt_orig=None,
                        use_words=False,
                        cpos_map=None):
    preproc_atts = PREPROC_COLUMNS[fmt_preproc]
    trees_merge = read_tabular(fname_merge, preproc_atts)
    for t_orig, t_merge in zip_longest(trees, trees_merge):
        if t_orig is None:
            words2 = [n.word for n in t_merge.terminals]
            print("more trees in merge: %s"%(
                words2,), file=sys.stderr)
            sys.exit(1)
        elif t_merge is None:
            words1 = [n.word for n in t_orig.terminals]
            print("more trees in original: %s"%(
                words1,), file=sys.stderr)
            sys.exit(1)
        words1 = [n.word for n in t_orig.terminals]
        words2 = [n.word for n in t_merge.terminals]
        if len(words1) != len(words2):
            print("Sequences do not match: %s vs %s"%(
                words1, words2), file=sys.stderr)
            sys.exit(1)
        elif words1 != words2:
            pass
            #print >>sys.stderr, "Sequences differ: %s vs %s"%(
            #    words1, words2)
        for n, n_merge in zip(t_orig.terminals, t_merge.terminals):
            for att in preproc_atts:
                if att is not None:
                    if att != 'word' or use_words==True:
                        setattr(n, att, getattr(n_merge, att))
            # assign cpos if a pos map is given
            if cpos_map is not None:
                n.cpos = cpos_map.get(n.cat, n.cat)
            elif hasattr(n, 'cpos'):
                n.cpos = n.cat
        yield t_orig


oparse_recombine = optparse.OptionParser(
    usage="usage: %prog [options] N_FOLDS TEMPLATE dest.conll")

def recombine_main(argv=None):
    opts, args = oparse_recombine.parse_args(argv)
    if len(args) != 3:
        oparse_recombine.print_help()
        sys.exit(1)
    n_folds = int(args[0])
    template = args[1]
    assert '%(fold)s' in template
    tree_seqs = []
    for i in range(n_folds):
        fname = template%{'fold': i+1}
        tree_seqs.append(read_generic(fname))
    trees = do_recombine(tree_seqs)
    with open(args[2], 'w', encoding='UTF-8') as f_out:
        for lines in trees:
            write_generic_single(f_out, lines)

