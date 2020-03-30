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
import re
import sys

class SimpleFolder(object):
    def est_length(self, n):
        '''
        estimate the number of trees in each fold
        '''
        return n
    def apply_filter(self, tree_no, fold_no, t):
        return (tree_no, fold_no, t)

class RangeSel(SimpleFolder):
    def __init__(self, ranges):
        self.ranges = ranges
    def est_length(self, n):
        s = 0
        for (start, end) in self.ranges:
            s += end - start + 1
        return [s]
    def apply_filter(self, tree_no, fold_no, t):
        ranges = self.ranges
        while ranges and tree_no > ranges[0][1]:
            del ranges[0]
        if not ranges:
            return None
        if tree_no < ranges[0][0]:
            return None
        return (tree_no, 0, t)

class FoldOnly(SimpleFolder):
    def __init__(self, folds):
        if isinstance(folds, int):
            self.folds = {folds}
        else:
            self.folds = set(folds)
    def est_length(self, n):
        if n[0] is None:
            return [None]
        s = 0
        new_folds = set()
        for fold in self.folds:
            if fold >= len(n):
                print("Map fold# %d to %d"%(fold, fold%len(n)), file=sys.stderr)
                fold = fold%len(n)
            s += n[fold]
            new_folds.add(fold)
        self.folds = new_folds
        return [s]

    def apply_filter(self, tree_no, fold_no, t):
        if fold_no in self.folds:
            return (tree_no, 0, t)
        else:
            return None

class FoldExcept(SimpleFolder):
    def __init__(self, folds):
        if isinstance(folds, int):
            self.folds = {folds}
        else:
            self.folds = set(folds)
    def est_length(self, n):
        if n[0] is None:
            return [None]
        s = sum(n)
        new_folds = set()
        for fold in self.folds:
            if fold >= len(n):
                print("Map fold# %d to %d"%(fold, fold%len(n)), file=sys.stderr)
                fold = fold%len(n)
            s -= n[fold]
            new_folds.add(fold)
        self.folds = new_folds
        return [s]
    def apply_filter(self, tree_no, fold_no, t):
        if fold_no not in self.folds:
            return (tree_no, 0, t)
        else:
            return None

class FoldAlternating(SimpleFolder):
    def __init__(self, num_folds):
        self.num_folds = num_folds
    def est_length(self, n):
        if n[0] is None:
            return [None] * self.num_folds
        total = sum(n)
        div = int(total) / self.num_folds
        mod = int(total) % self.num_folds
        result = []
        for i in range(self.num_folds):
            if i < mod:
                result.append(div+1)
            else:
                result.append(div)
        return result
    def apply_filter(self, tree_no, fold_no, t):
        return (tree_no, tree_no%self.num_folds, t)

class FoldSlices(SimpleFolder):
    def __init__(self, num_folds):
        self.num_folds = num_folds
    def est_length(self, n):
        if n[0] is None:
            raise ValueError('Need to know number of trees. Use range() if in doubt')
        total = sum(n)
        self.num_total = total
        nf = self.num_folds
        result = []
        for i in range(nf):
            result.append((i+1)*total/nf - i*total/nf)
        return result
    def apply_filter(self, tree_no, fold_no, t):
        return (tree_no,
                (tree_no * self.num_folds) / self.num_total,
                t)

class Folder(object):
    def __init__(self):
        self.xform = []
    def apply_filter(self, trees):
        # first: see if we need to determine length
        est_len = [None]
        try:
            for xf in self.xform:
                est_len = xf.est_length(est_len)
        except ValueError:
            trees = list(trees)
            est_len = [len(trees)]
            for xf in self.xform:
                est_len = xf.est_length(est_len)
        if est_len[0] is not None:
            print("Estimated output size: %d"%(sum(est_len),), file=sys.stderr)
        for i, t in enumerate(trees):
            result = self.apply_all(i, 0, t)
            if result is None:
                continue
            yield t
    def apply_all(self, tno, fold, t):
        for xf in self.xform:
            result = xf.apply_filter(tno, fold, t)
            if result is None:
                return None
            else:
                tno, fold, t = result
        return tno, fold, t

tokens_table = [(code, re.compile(rgx)) for
                (code, rgx) in [
                    ('ranges', r'([0-9]+-[0-9]+(?:,[0-9]+-[0-9]+)*)'),
                    ('range', r'range\(([0-9]+),([0-9]+)\)'),
                    ('alternating', r'alternating\(([0-9]+)\)'),
                    ('slices', r'slices\(([0-9]+)\)'),
                    ('only', r'only\(([0-9]+(?:,[0-9]+)*)\)'),
                    ('except', r'except\(([0-9]+(?:,[0-9]+)*)\)'),
                    ('trainfold', r'(train|test)(dev|final)([0-9]+)/([0-9]+)')]]

def interpret(code, arg):
    if code == 'ranges':
        # convert to 0-based indices
        def split_part(part):
            x = part.split('-')
            return (int(x[0])-1, int(x[1])-1)
        ranges = [split_part(part)
                  for part in arg[0].split(',')]
        return [RangeSel(ranges)]
    elif code == 'range':
        # convert to 0-based indices
        return [RangeSel([[int(arg[0])-1, int(arg[1])-1]])]
    elif code == 'alternating':
        return [FoldAlternating(int(arg[0]))]
    elif code == 'slices':
        return [FoldSlices(int(arg[0]))]
    elif code == 'only':
        return [FoldOnly([int(x) for x in arg[0].split(',')])]
    elif code == 'except':
        return [FoldExcept([int(x) for x in arg[0].split(',')])]
    elif code == 'trainfold':
        # n-1: test fold
        # n-2: devtest fold
        # others: train
        n_folds = int(arg[3])
        offset = int(arg[2]) - 1
        finaltest_fold = (n_folds + offset - 1) % n_folds
        devtest_fold = (n_folds + offset - 2) % n_folds
        if arg[1] == 'dev':
            if arg[0] == 'train':
                sel = FoldExcept([devtest_fold, finaltest_fold])
            else:
                sel = FoldOnly([devtest_fold])
        else:
            if arg[0] == 'train':
                sel = FoldExcept([finaltest_fold])
            else:
                sel = FoldOnly([finaltest_fold])
        return [FoldAlternating(int(arg[3])), sel]
    else:
        assert False, code

def parse_foldspec(spec):
    f = Folder()
    idx = 0
    while idx < len(spec):
        if spec[idx] in './;:':
            idx += 1
            continue
        for code, rgx in tokens_table:
            m = rgx.match(spec, idx)
            if m:
                x = interpret(code, m.groups())
                f.xform += x
                idx = m.end()
    return f

def do_recombine(tree_seqs, init=1):
    '''
    given trees that were distributed in round-robin fashion,
    produces a sequence of trees from the re-combined sequences.

    To combine testfinal folds, use init=1, for testdev
    folds, use init=2
    '''
    iters = [iter(trees) for trees in tree_seqs]
    n_iters = len(tree_seqs)
    i = (init + n_iters)%n_iters
    while True:
        yield next(iters[i])
        i = (i+1)%n_iters

