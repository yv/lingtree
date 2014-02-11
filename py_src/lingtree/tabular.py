'''
Reading and writing tabular formats
'''
from lingtree import TerminalNode
from itertools import izip

class AttrColumn(object):
    #TODO: is this needed? Can we emulate elkfed.mmax.tabular? should we?
    def __init__(self, name, name_alt=None, null_val='--'):
        self.name = name
        self.name_alt = name_alt
        self.null_val = null_val
    def get(self, obj):
        val = None
        if hasattr(obj, self.name):
            val = getattr(obj, self.name)
        elif hasattr(obj, self.name_alt):
            val = getattr(obj, self.name_alt)
        if val is None:
            return self.null_val
        else:
            return val
    def put(self, obj, s):
        setattr(obj, self.name, s)

class IDColumn(object):
    def __init__(self):
        pass
    def get(self, obj):
        return obj.start+1
    def put(self, obj, s):
        idx = int(s)
        assert idx >= 1
        obj.start = idx-1

class CoNLLReader(object):
    '''
    reads in CoNLL09 files
    '''
    def __init__(self, columns, have_phead=True):
        self.columns = columns
    def process_rows(self, rows):
        terminals = []
        for i, row in enumerate(rows):
            trm = TerminalNode(row[4], row[1])
            trm.start = i
            trm.end = i+1
            trm.syn_label = row[10]
            terminals.append(trm)
        for row, trm in izip(rows, terminals):
            head = row[8]
            if head == '0':
                trm.syn_parent = None
            else:
                trm.syn_parent = terminals[int(head)-1]
        return terminals
    def read_sentences(self, f):
        rows = []
        while True:
            l = f.readline()
            if l == '':
                return
            elif l == '\n':
                if rows:
                    yield self.process_rows(rows)
                    rows=[]
            else:
                rows.append(l.strip().split())

