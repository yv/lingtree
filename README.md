# LingTree -- conversion and transformation of linguistic trees

This is a small library that started out as part of PyTree, but which is
convenient to have as a standalone library without external dependencies.

While the main goal is to have idiomatic Python 3 code, LingTree aims to
be an option for Python 2 as well. The code was re-licensed under the MIT
license.

## Entry points

You can create a HTML display out of trees in Negra Export or TigerXML
format by means of the lingtree.csstree package:

   python -m lingtree.csstree sample.export sample.html

## API

You can get a sequence of the trees in a file by calling

   trees = lingtree.read_trees('sample.export')

A tree object has a *roots* property that contains the root nodes of
a tree (normally the sentence(s) and any punctuation) and a *terminals*
property that contains the terminal nodes for that sentence.

