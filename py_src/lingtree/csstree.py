#!/usr/bin/env python

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
from builtins import open
import optparse
from lingtree import read_trees, tree, export
from io import StringIO

css_stylesheet = """
<style type="text/css">
.treebox {
   background: #eeeeee;
   position: relative;
   width: 640px;
   height: 480px;
}
.node {
   background: white;
   position: absolute;
   font-size: 13px;
   font-family: sans-serif;
   text-align: center;
   border-width: 2px;
   border-color: black;
   border-style: solid;
   padding: 3px;
   z-index: 2;
}
.vroot {
   background: white;
   position: absolute;
   font-size: 13px;
   font-family: sans-serif;
   text-align: center;
   border-width: 2px;
   border-color: #666666;
   border-style: solid;
   color: #666666;
   padding: 3px;
   z-index: 2;
}
.edgelabel {
   background: #eeeeee;
   position: absolute;
   border-width: 1px;
   border-color: black;
   border-style: solid;
   padding: 3px;
   z-index: 2;
   font-size: 9px;
   font-family: sans-serif;
   text-align: center;
}
.hline {
   position: absolute;
   height: 0px;
   border-width: 2px 0 0 0;
   border-style: solid;
   z-index:1;
}
.vline {
   position: absolute;
   border-color: #aaaaaa;
   border-width: 0 2px 0 0;
   border-style: solid;
   width: 0px;
   z-index:1;
}
.hlineR {
   position: absolute;
   border-color: #cccccc;
   height: 0px;
   border-width: 2px 0 0 0;
   border-style: solid;
}
.vlineR {
   position: absolute;
   border-color: #cccccc;
   border-width: 0 2px 0 0;
   border-style: solid;
   width: 0px;
   z-index:1;
}
</style>
"""

LETTER_WIDTH = 7.7
EL_LETTER_WIDTH = 9
NODE_SPACE = 15
LAYER_HEIGHT = 75


def determine_textwidth(txt):
    """approximate textwidth for variable-width fonts.
    The real width varies with the font."""
    w = 0
    for c in txt:
        factor = 1.0
        if c in '.il':
            factor = 0.5
        elif c in 'If':
            factor = 0.7
        elif c in 'wmABCDEFGHJKLNOPQRSTUVXYZ':
            factor = 1.2
        elif c in 'MW':
            factor = 1.5
        w += factor * LETTER_WIDTH
    return w


def layout_tree(t, extra_attrs_t=None, crossing=False):
    if len(t.roots) > 1:
        root = tree.NontermNode("VROOT")
        root.children = t.roots
        root.start = min((n.start for n in root.children))
        root.end = max((n.end for n in root.children))
    else:
        root = t.roots[0]
    layout_terminals(t.terminals, extra_attrs_t)
    if not crossing:
        depth = layout_topdown(root)
    else:
        depth = layout_crossing(root)
    for n in t.terminals:
        n.y_pos = depth
    if not crossing:
        layout_bottomup(root)
    return (root, depth)


def layout_terminals(nodes, extra_attrs_t=None):
    xpos = 0
    for n in nodes:
        w = max(determine_textwidth(n.cat), determine_textwidth(n.word))
        if extra_attrs_t is not None:
            for k in extra_attrs_t:
                w = max(w, determine_textwidth(getattr(n, k)))
        w += 4
        n.x_pos = xpos + w // 2
        n.width = w
        xpos += w + NODE_SPACE


def layout_crossing(node_root):
    assert node_root.start >= 0
    assert node_root.end > 0
    lst = []
    height = [0] * node_root.end
    lst.append((node_root.end - node_root.start, 1, node_root))
    for i, n in enumerate(tree.descendants(node_root)):
        lst.append((n.end - n.start, -i, n))
    lst.sort()
    for width, k, n in lst:
        maxh = 1 + max([height[i] for i in range(n.start, n.end)])
        n.height = maxh
        for i in range(n.start, n.end):
            height[i] = maxh
    maxh = node_root.height
    for width, k, n in lst:
        n.y_pos = maxh - n.height
        if not n.isTerminal():
            n.width = determine_textwidth(n.cat)
            n.x_pos = (n.children[0].x_pos + n.children[-1].x_pos) // 2
    return maxh - 1


def layout_topdown(node, depth=0):
    node.y_pos = depth
    if node.isTerminal():
        return depth
    maxdepth = depth
    for n in node.children:
        cdepth = layout_topdown(n, depth + 1)
        maxdepth = max(maxdepth, cdepth)
    w = determine_textwidth(node.cat)
    node.x_pos = (node.children[0].x_pos + node.children[-1].x_pos) // 2
    node.width = w
    node.y_pos = depth
    return maxdepth


def layout_bottomup(node):
    if node.isTerminal():
        return
    mindepth = 100
    is_coord = False
    for n in node.children:
        layout_bottomup(n)
        mindepth = min(mindepth, n.y_pos)
        if (n.edge_label == 'KONJ' or
                n.cat in ['MF', 'VF']):
            is_coord = True
    node.y_pos = mindepth - 1
    if is_coord:
        for n in node.children:
            if not n.isTerminal():
                n.y_pos = mindepth


def write_html(t, out, extra_attrs_t=None, crossing=False, **attrs):
    (root, depth) = layout_tree(t, extra_attrs_t, crossing)
    n = t.terminals[-1]
    width = n.x_pos + n.width / 2 + NODE_SPACE
    if attrs:
        attr_out = StringIO()
        style_out = StringIO()
        for k, v in attrs.iteritems():
            if k.startswith('_style_'):
                style_out.write(';%s:%s' % (k[7:], v))
            elif k == '_id':
                attr_out.write(' id=\"%s\"' % (v,))
            else:
                attr_out.write(' %s="%s"' % (k, v))
        out.write('<div class="treebox" style="width:%spx;height:%spx%s"%s>\n' % (
            width,
            (depth + 1) * LAYER_HEIGHT,
            style_out.getvalue(),
            attr_out.getvalue()))
    else:
        out.write('<div class="treebox" style="width:%spx;height:%spx">\n' % (
            width,
            (depth + 1) * LAYER_HEIGHT))
    write_node_html(root, out, None, extra_attrs_t)
    out.write('</div>\n')


def write_node_html(node, out, parent, extra_attrs_t=None):
    if parent:
        if node.parent:
            lstyle = 'vline'
        else:
            lstyle = 'vlineR'
        out.write('<div class="%s" style="top:%spx;left:%spx;height:%spx"></div>\n' % (
            lstyle,
            parent.y_pos * LAYER_HEIGHT + 5,
            node.x_pos,
            (node.y_pos - parent.y_pos) * LAYER_HEIGHT))
    if node.cat == 'VROOT':
        style = 'vroot'
    else:
        style = 'node'
    out.write('<div class="%s" style="top:%spx;left:%spx;width:%spx">\n' % (
        style,
        node.y_pos * LAYER_HEIGHT - 5,
        node.x_pos - node.width / 2,
        node.width))
    if node.isTerminal():
        if extra_attrs_t is None:
            out.write('%s<br>%s' % (node.word, node.cat))
        else:
            out.write('<br>'.join(getattr(node, k)
                      for k in ['word', 'cat'] + extra_attrs_t))
    else:
        out.write('%s' % (node.cat,))
    out.write('</div>\n')
    if node.edge_label and node.edge_label != '--':
        el_width = len(node.edge_label) * EL_LETTER_WIDTH
        out.write('<div class="edgelabel" style="top:%spx;left:%spx;width:%spx">%s</div>\n' % (
            node.y_pos * LAYER_HEIGHT - 30,
            node.x_pos - el_width / 2 - 2,
            el_width,
            node.edge_label))
    if not node.isTerminal():
        posns = [n.x_pos for n in node.children]
        left = min(posns)
        right = max(posns)
        if parent:
            lstyle = "hline"
        else:
            lstyle = "hlineR"
        out.write('<div class="%s" style="top:%spx;left:%spx;width:%spx"></div>\n' % (
            lstyle,
            node.y_pos * LAYER_HEIGHT + 5,
            left,
            right - left
        ))
        for n in node.children:
            write_node_html(n, out, node, extra_attrs_t)


def split_trees_to_files(instream, prefix):
    part_no = 0
    from_no = None
    old_doc = 0
    outstream = None
    for t in export.read_trees(instream):
        if from_no is None or (int(t.sent_no) > from_no + 1000 and
                               t.doc_no != old_doc):
            if outstream is not None:
                outstream.write('</body>\n</html>\n')
                outstream.close()
                print('%s-%s.html: sentence %d-%d' % (
                    prefix, part_no, from_no, int(t.sent_no) - 1))
            part_no += 1
            outstream = open('%s-%s.html' % (prefix, part_no), 'w')
            outstream.write('''
<html>
<head>
<title>csstree output</title>
''')
            outstream.write(css_stylesheet)
            from_no = int(t.sent_no)
            from_doc = t.doc_no
        old_doc = t.doc_no
        outstream.write('<p>%s: %s</p>\n' % (
            t.sent_no, ' '.join([n.word for n in t.terminals])))
        write_html(t, outstream)
    if outstream:
        outstream.write('</body>\n</html>\n')
        outstream.close()
        print('%s-%s.html: sentence %d-%d' % (
            prefix, part_no, from_no, int(t.sent_no) - 1))


oparse = optparse.OptionParser()
oparse.add_option('--fmt', dest='format',
                  choices=['export', 'tigerxml', 'spmrl'])
oparse.add_option('-C', '--crossing', dest='crossing',
                  action='store_true', default=False)


def write_html_header(f_html):
    f_html.write(css_stylesheet)
    f_html.write('</head>\n<body>\n')


def csstree_main(argv=None):
    """converts a file with syntax trees to HTML"""
    opts, args = oparse.parse_args(argv)
    fname_exp, fname_html = args
    f_html = open(fname_html, 'w', encoding='UTF-8')
    f_html.write('''
<html>
<head>
<title>csstree output</title>
''')
    write_html_header(f_html)
    for t in read_trees(fname_exp, opts.format):
        f_html.write('<p>%s: %s</p>\n' % (
            t.sent_no, ' '.join([n.word for n in t.terminals])))
        write_html(t, f_html, crossing=opts.crossing)
    f_html.write('</body>\n</html>\n')
    f_html.close()


if __name__ == '__main__':
    csstree_main()
