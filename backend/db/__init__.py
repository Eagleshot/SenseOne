"""SQLite control-plane package.

All control-plane data lives in a local SQLite database: the ORM schema
(`models`), the engine/session factory + schema bootstrap (`session`), and the
repositories the routes and helper modules call directly — `station_repo`
(stations, images, readings, device secrets) and `user_repo` (users, auth
sessions).
"""
