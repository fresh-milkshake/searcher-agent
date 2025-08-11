"""Sphinx configuration for the searcher-agent project.

The configuration enables MyST Markdown, autosummary, autodoc, and other
useful extensions. It is set up to discover project modules from the
repository root so that API documentation can be generated for `agent`,
`bot`, and `shared` packages without additional path tweaks during builds.
"""

import os
import sys
from datetime import datetime


# -- Path setup --------------------------------------------------------------
# Add project root to sys.path to allow Sphinx to import the packages
PROJECT_ROOT = os.path.abspath("..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# -- Project information -----------------------------------------------------
project = "searcher-agent"
author = "fresh-milkshake"
current_year = str(datetime.utcnow().year)
copyright = f"{current_year}, {author}"


# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
]

autosummary_generate = True
autodoc_typehints = "description"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# Mock heavy third-party imports to speed up doc builds and avoid runtime deps
autodoc_mock_imports = [
    "aiogram",
    "openai",
    "sqlalchemy",
    "aiosqlite",
    "alembic",
    "dotenv",
    "requests",
    "arxiv",
    "feedparser",
    "PyPDF2",
    "bs4",
    "lxml",
    "duckduckgo_search",
    "loguru",
    "peewee",
    "agents",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "api/generated/*",
    "api/generated/**",
]

# MyST configuration
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
    "attrs_block",
    "attrs_inline",
]


# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
html_title = project

html_theme_options = {
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/fresh-milkshake",
            "html": """
<svg viewBox=\"0 0 24 24\" fill=\"currentColor\" aria-hidden=\"true\" width=\"24\" height=\"24\">
  <path d=\"M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.02c-3.34.73-4.04-1.61-4.04-1.61-.55-1.4-1.34-1.77-1.34-1.77-1.1-.75.08-.73.08-.73 1.22.09 1.86 1.25 1.86 1.25 1.08 1.85 2.83 1.31 3.52 1 .11-.78.42-1.31.76-1.61-2.66-.3-5.46-1.33-5.46-5.93 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.24 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.8 5.62-5.47 5.92.43.37.82 1.1.82 2.22v3.29c0 .32.21.69.83.57A12 12 0 0 0 12 .5Z\"/>
</svg>
""",
            "class": "",
        }
    ]
}


# -- Intersphinx -------------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}


# -- Autosummary target dir --------------------------------------------------
autosummary_imported_members = True

# Ensure environment required by modules is present to avoid import-time errors
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "DUMMY")
