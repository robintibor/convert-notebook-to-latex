import os
from setuptools import find_packages
from setuptools import setup

version = '0.0.1'

here = os.path.abspath(os.path.dirname(__file__))


setup(
    name="ConvertNotebookToLatex",
    version=version,
    description="Scripts to convert jupyter notebooks to latex or pdf or html.",
    classifiers=[
        "Development Status :: 1 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 2.7",
        "Topic :: Publication :: Jupyter Notebook :: Conversion PDF HTML LATEX",
        ],
    keywords="",
    author="Robin Tibor Schirrmeister",
    author_email="robintibor@googlegroups.com",
    url="https://github.com/robintibor/convert-notebook-to-latex",
    packages=find_packages(),
    include_package_data=False,
    zip_safe=False,
    )