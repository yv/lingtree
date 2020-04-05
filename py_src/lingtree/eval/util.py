def assign_yields(t):
    for node in t.roots:
        assign_node_yield(node)

def assign_node_yield(node):
    if node.isTerminal():
        node_yield = frozenset([node.start])
    else:
        node_yield = set()
        for n in node.children:
            node_yield.update(assign_node_yield(n))
        node_yield = frozenset(node_yield)
    node.node_yield = node_yield
    return node_yield