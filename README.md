# LingTree -- conversion and transformation of linguistic trees

This is a small library that started out as part of PyTree, but which is
convenient to have as a standalone library without external dependencies.

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

