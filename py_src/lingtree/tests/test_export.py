import unittest
from io import StringIO
from mock import mock_open, patch
from lingtree.penn import line2parse, node2tree, number_nodes
from lingtree.export import write_export_file, read_trees, copy_tree

test_s1 = u"(VROOT (S (NE-SB Klaus) (VVFIN-HD mag) (NN-OA Pizza)) ($. .))"
t1 = node2tree(line2parse(test_s1))
node_table = {}
number_nodes(t1.roots[0], node_table)
t1.node_table = node_table
t1.sent_no = 1
print(t1.terminals[-1].parent)

class TestExport(unittest.TestCase):
    def test_writing(self):
        f = StringIO()
        write_export_file(f, [t1, t1])
        text = f.getvalue()
        print(text)
        lines = text.split('\n')
        self.assertTrue(lines[0].startswith('#BOS 1'))
        self.assertEqual(lines[-1], '')
        self.assertEqual(lines[-2], '#EOS 1')
        m = mock_open(read_data=text)
        with m("mock-1.export", "r") as f:
            trees = list(read_trees(f))
        self.assertEqual(len(trees), 2)

    def test_copy(self):
        t2 = copy_tree(t1)
        f = StringIO()
        write_export_file(f, [t1, t1])
        text1 = f.getvalue()
        f = StringIO()
        write_export_file(f, [t2, t2])
        text2 = f.getvalue()
        self.assertEqual(text1, text2)
