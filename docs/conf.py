"""Configuration file for the Sphinx documentation builder.
This file only contains a selection of the most common options. For a full
list see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import sys
from importlib.metadata import version as get_version
from pathlib import Path

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.append(str(Path("../eta_connect").resolve()))  # Insert path to eta_connect


# -- Project information -----------------------------------------------------
project = "eta_connect"
release = get_version(project)  # The full version, including alpha/beta/rc tags
version = ".".join(release.split(".")[:3])  # Top level version
copyright = "Technical University of Darmstadt, Institute for Production Management, Technology and Machine Tools (PTW)"  # noqa: A001

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
    "sphinx_copybutton",
]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Prevent copy button from copying prompt ($, >>>)
copybutton_exclude = ".linenos, .gp"


autodoc_mock_imports = ["opcua", "numpy.random", "pandas", "wetterdienst"]
autodoc_default_options = {"undoc-members": True, "member-order": "bysource"}

intersphinx_mapping = {
    "python": ("https://docs.python.org/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
}

autosummary_generate = True

linkcheck_ignore = [r"https://$", r"https://web-api.tp.entsoe.eu/"]
linkcheck_allowed_redirects = {
    r"https://eta-utility.readthedocs.io/": r"https://eta-utility.readthedocs.io/en/main/",
    r"https://stable-baselines3.readthedocs.io/": r"https://stable-baselines3.readthedocs.io/en/master/",
}
linkcheck_anchors_ignore_for_url = (r"https://docs.python.org/",)
