import os
from setuptools import setup

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-fleepanel',
    version='0.1',
    packages=['fleepanel'],
    include_package_data=True,
    description='Fleepanel for Fleeshell...',
    author='CUI Hao',
    author_email='cuihao.leo@gmail.com',
)
