#!/usr/bin/env python
from setuptools import setup

__doc__='''
PyTree version that only includes the pytree library
(reading and writing of mrg, tigerxml/export trees and MMAX2)
which should run fine on plain Python (including Win+Anaconda)
'''

setup(name='LingTree',
      version='0.6',
      description='Python Package for Eclectic Linguistic Processing',
      author='Yannick Versley',
      author_email='versley@cl.uni-heidelberg.de',
      packages=['lingtree'],
      package_dir={'':'py_src'},
      install_requires=['future', 'PyYAML']
      )
