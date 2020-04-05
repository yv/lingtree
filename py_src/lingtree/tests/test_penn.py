import unittest
from mock import mock_open, patch
from lingtree.penn import line2parse, node2tree
from lingtree import read_mrg_trees

sample_mrg = u"""(ROOT (S (NP (DT the) (NN cat)) (VBD sat) (PP (IN on) (NP (DT the) (NN mat)))) (. .))
(NP (JJ weird )(NN   spacing) )
"""

test_s1 = u"(VROOT (S (NE-SB Klaus) (VVFIN-HD mag) (NN-OA Pizza)) ($. .))"

class TestPenn(unittest.TestCase):
    def test_reading(self):
        m = mock_open(read_data=sample_mrg)
        with patch('lingtree.open', m, create=True):
            trees = list(read_mrg_trees('mock_me.mrg', 'UTF-8'))
            self.assertEqual(len(trees), 2)
            t1 = trees[0]
            self.assertEqual(len(t1.roots), 1)
            self.assertEqual(t1.roots[0].cat, 'ROOT')
            self.assertEqual(len(t1.terminals), 6)
            self.assertEqual(t1.terminals[1].cat, 'NN')
            np1 = trees[0].terminals[1].parent
            self.assertEqual(np1.start, 0)
            self.assertEqual(np1.end, 2)
            t2 = trees[1]
            self.assertEqual(len(t2.roots), 1)

    def test_line2parse(self):
        node = line2parse(test_s1)
        self.assertEqual(node.cat,'VROOT')
        t1 = node2tree(node)
        term1 = t1.terminals[0]
        self.assertEqual(term1.cat, 'NE')
        self.assertEqual(term1.edge_label, 'SB')
        self.assertEqual(t1.roots[0].edge_label, None)
