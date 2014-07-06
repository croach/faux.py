"""
faux.py
--------------

A library for creating database fixtures using a data serialization format.
"""

import os
import subprocess
from setuptools import setup


root_dir = os.path.abspath(os.path.dirname(__file__))
package_dir = os.path.join(root_dir, 'faux')


# Try to get the long description from the README file or the module's
# docstring if the README isn't available.
try:
    README = open(os.path.join(root_dir, 'README.md')).read()
except:
    README = __doc__

# Try to read in the change log as well
try:
    CHANGES = open(os.path.join(root_dir, 'CHANGES.md')).read()
except:
    CHANGES = ''

setup(
    name='Faux',
    version='0.3.1',
    url='http://github.com/croach/faux.py',
    license='Apache License 2.0',
    author='Christopher Roach',
    author_email='vthakr@gmail.com',
    maintainer='Christopher Roach',
    maintainer_email='vthakr@gmail.com',
    description='A library for creating database fixtures using a data serialization format.',
    long_description=README + '\n\n' + CHANGES,
    packages=['faux'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    # install_requires=[
    #     'sqlalchemy'
    # ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Testing'
    ]
)
