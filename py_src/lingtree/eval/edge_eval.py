import argparse
from collections import defaultdict
from lingtree import read_trees
from .util import assign_yields

class EvalResult:
    def __init__(self, wanted_labels=None):
        if wanted_labels is None:
            wanted_labels = ['SB', 'EP', 'PD', 'OA', 'OA2', 'DA', 'OG', 'OP', 'OC']
        self.wanted_labels = wanted_labels
        stats_lab = dict([(lab, [0,0,0]) for lab in wanted_labels])
        self.stats_lab = stats_lab
        self.stats = [0,0,0]

    def extract_labels(self, t):
        assign_yields(t)
        labels = defaultdict(set)
        for node in t.topdown_enumeration():
            labels[node.node_yield].add(node.edge_label)
        return labels

    def compare_trees(self, t_gold, t_pred):
        labels_gold = self.extract_labels(t_gold)
        labels_pred = self.extract_labels(t_pred)
        common_yields = set(labels_gold.keys()).intersection(labels_pred.keys())
        for span in common_yields:
            l_gold = labels_gold[span]
            l_pred = labels_pred[span]
            for lab in l_gold:
                if lab in self.wanted_labels:
                    if lab in l_pred:
                        self.stats_lab[lab][0] += 1
                        self.stats[0] += 1
                    else:
                        self.stats_lab[lab][1] += 1
                        self.stats[1] += 1
            for lab in l_pred:
                if lab in self.wanted_labels:
                    if lab not in l_gold:
                        self.stats_lab[lab][2] += 1
                        self.stats[2] += 1

    def summarize(self):
        print("STATS_LAB", self.stats_lab)
        print("STATS", self.stats)
        for lab, stat in self.stats_lab.items():
            tp, fn, fp = stat
            if tp:
                prec = tp / (tp + fp)
                recl = tp / (tp + fn)
                f1 = 2*prec*recl / (prec + recl)
            else:
                prec = recl = f1 = 0
            print("%-10s  N %5d  Prec %.3f  Recl %.3f  F1 %.4f"%(lab, (tp + fn), prec, recl, f1))
        tp, fn, fp = self.stats
        if tp:
            prec = tp / (tp + fp)
            recl = tp / (tp + fn)
            f1 = 2 * prec * recl / (prec + recl)
        else:
            prec = recl = f1 = 0
        print("%-10s  N %5d  Prec %.3f  Recl %.3f  F1 %.4f" % ("**ALL**", tp + fn, prec, recl, f1))


aparse = argparse.ArgumentParser()
aparse.add_argument('gold_file')
aparse.add_argument('pred_file')

def edge_eval_main(args=None):
    opts = aparse.parse_args(args)
    trees_gold = list(read_trees(opts.gold_file))
    trees_pred = list(read_trees(opts.pred_file))
    assert len(trees_gold) == len(trees_pred), (len(trees_gold), len(trees_pred))
    result = EvalResult()
    for t_gold, t_pred in zip(trees_gold, trees_pred):
        assert len(t_gold.terminals) == len(t_pred.terminals)
        result.compare_trees(t_gold, t_pred)
    result.summarize()

if __name__ == '__main__':
    edge_eval_main()