#!/usr/bin/env python
from setuptools import setup

__doc__='''
PyTree version that only includes the pytree library
(reading and writing of mrg, tigerxml/export trees)
which should run fine on plain Python3 (including Win+Anaconda)
'''

setup(name='LingTree',
      version='0.7',
      description='Python Package for Eclectic Linguistic Processing',
      author='Yannick Versley',
      author_email='yannick@inteligile.com',
      packages=['lingtree'],
      package_dir={'':'py_src'},
      install_requires=['future', 'PyYAML'],
      entry_points={
            'console_scripts': [

            ]}
      )
