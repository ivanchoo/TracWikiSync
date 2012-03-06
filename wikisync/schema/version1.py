# -*- coding: utf-8 -*-
from trac.db import Table, Column, Index, DatabaseManager

def do_upgrade(env, ver, cursor):
    wikisync_table = Table("wikisync", key=("name"))[
        Column("name"),
        Column("ignore", type="int"),
        Column("ignore_attachment", type="int"),
        Column("sync_time", type="int64"),
        Column("sync_remote_version", type="int"),
        Column("sync_local_version", type="int"),
        Column("remote_version", type="int"),
        Index(["name"]),
    ]
    db_backend, _ = DatabaseManager(env).get_connector()
    for stmt in db_backend.to_sql(wikisync_table):
        cursor.execute(stmt)
