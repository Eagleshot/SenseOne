"""SQLite control-plane package.

All control-plane data lives in a local SQLite database: the ORM schema
(`models`), the engine/session factory + schema bootstrap (`session`), and the
repository (`sqlite_repo`) the route/service layer calls through `store.py`.
"""
