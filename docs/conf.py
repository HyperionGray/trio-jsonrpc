# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# To support import of the `example` package during RTD builds, we need to add
# the parent directory to the path.
import os, sys

sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
import subprocess

version_proc = subprocess.run(["poetry", "version"], stdout=subprocess.PIPE)
version = version_proc.stdout.split()[1].decode("ascii")

project = "Trio JSON-RPC"
copyright = "2020, Hyperion Gray"
author = "Mark E. Haase"

# The full version, including alpha/beta/rc tags
release = version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinxcontrib_trio",
    "sphinx.ext.autodoc",
    "sphinx_rtd_theme",
    "trio_jsonrpc.sphinx_ext",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
