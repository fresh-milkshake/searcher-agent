Browsing
========

Overview
--------

The browsing package provides two complementary layers:

- Manual sources: lightweight, stateless classes to perform provider-specific searches and return normalized `SearchItem` results.
- Agent tools: functions decorated for the Agents SDK that wrap manual sources (or the arXiv parser) and return JSON-serializable dictionaries for tool calling.

Exports
-------

The top-level `agent.browsing` exposes a curated set of utilities:

- `ArxivBrowser`: high-level arXiv helper built on `shared.arxiv_parser`
- `arxiv_search_tool`, `arxiv_get_paper_tool`: arXiv tools
- `web_search_tool`: DuckDuckGo web search tool
- `google_scholar_search_tool`, `pubmed_search_tool`, `github_repo_search_tool`: manual-source backed agent tools

Manual Sources
--------------

.. automodule:: agent.browsing.manual.sources.base
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: agent.browsing.manual.sources.google_scholar
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: agent.browsing.manual.sources.pubmed
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: agent.browsing.manual.sources.github
   :members:
   :undoc-members:
   :show-inheritance:

ArXiv Manual Browser
--------------------

.. automodule:: agent.browsing.manual.manual
   :members:
   :undoc-members:
   :show-inheritance:

Agent Tools
-----------

.. automodule:: agent.browsing.tools.arxiv
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: agent.browsing.tools.duckduckgo
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: agent.browsing.tools.google_scholar
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: agent.browsing.tools.pubmed
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: agent.browsing.tools.github
   :members:
   :undoc-members:
   :show-inheritance:

