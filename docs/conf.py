# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sphinx_rtd_theme
import sys

sys.path.insert(0, os.path.abspath('../'))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Pose app'
copyright = '2023, Matt Whiteway and Dan Biderman'
author = 'Matt Whiteway and Dan Biderman'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',  # allows automatic parsing of docstrings
    'sphinx.ext.mathjax',  # allows mathjax in documentation
    'sphinx.ext.viewcode',  # links documentation to source code
    'sphinx.ext.githubpages',  # allows integration with github
    'sphinx.ext.napoleon',  # parsing of different docstring styles
    'sphinx.ext.intersphinx',  # for youtube embedding
    'sphinxcontrib.youtube',
    'sphinx_automodapi.automodapi',
    'sphinx_copybutton',  # add copy button to code blocks
    'sphinx_design',  # dropdowns
    'sphinx_rtd_dark_mode',
    'sphinx'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_static_path = ['_static']
html_logo = "https://github.com/danbider/lightning-pose/raw/main/docs/images/LightningPose_logo_light.png"
html_favicon = "https://github.com/danbider/lightning-pose/raw/main/docs/images/favicon.ico"

# user starts in dark mode
default_dark_mode = True
