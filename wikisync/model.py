# -*- coding: utf-8 -*-
import time
from wikisync.util import safe_int
from collections import namedtuple

class WikiSync(namedtuple("WikiSync", [
        "name", "ignore", "ignore_attachment", 
        "sync_time", "sync_remote_version", "sync_local_version",
        "remote_version", "local_version",
        ])):
    
    __slots__ = ()
    
    def merge(self, **kwargs):
        return self._replace(**kwargs)
    
    def validate(self):
        assert isinstance(self.name, basestring) and len(self.name) > 0, \
            "name required"
        return True
    
    def synchronized(self):
        assert safe_int(self.remote_version), \
            "Invalid remote_version '%s'" % self.remote_version
        assert safe_int(self.local_version), \
            "Invalid local_version '%s'" % self.local_version
        return self.merge(
            sync_remote_version=self.remote_version,
            sync_local_version=self.local_version,
            sync_time = time.time(),
        )
        
_default_wikisync = WikiSync(
    name=None,
    ignore=None,
    ignore_attachment=None,
    sync_time=None,
    sync_remote_version=None,
    sync_local_version=None,
    remote_version=None,
    local_version=None,
)

class WikiSyncDao(object):
    
    def __init__(self, env):
        self.env = env

    def all(self):
        db = self.env.get_read_db()
        fields = ["ws.%s" % f for f in WikiSync._fields \
            if not f.startswith("local_")]
        sql = """
            SELECT %s, MAX(w.version) FROM wikisync ws
            LEFT JOIN wiki w ON w.name = ws.name
            GROUP BY ws.name
        """ % ",".join(fields)
        cursor = db.cursor()
        cursor.execute(sql)
        while True:
            row = cursor.fetchone()
            if row:
                yield WikiSync._make(row)
            else:
                raise StopIteration()
    
    def sync_wiki_data(self):
        db = self.env.get_read_db()
        sql = """
            SELECT DISTINCT w.name FROM wiki w
            WHERE NOT EXISTS(
                SELECT ws.name FROM wikisync ws
                WHERE ws.name = w.name
            )
        """
        cursor = db.cursor()
        cursor.execute(sql)
        for row in cursor.fetchall():
            self.create(_default_wikisync.merge(name=row[0]))

    def sync_remote_data(self, dataset, ignore_filter=None):
        sync_time = time.time()
        @self.env.with_transaction()
        def execute(db):
            processed = set()
            for data in dataset:
                name = data.get("name", None)
                item = self.find(name)
                if not item:
                    if ignore_filter and ignore_filter.ignore(name):
                        data["ignore"] = 1
                    self.create(self.factory(sync_time=sync_time, **data))
                else:
                    if not item.sync_time:
                        if ignore_filter and ignore_filter.ignore(item.name):
                            item = item.merge(ignore=1)
                    item = item.merge(sync_time=sync_time, **data)
                    self.update(item)
                processed.add(name)
            if processed:
                cursor = db.cursor()
                cursor.execute("SELECT name FROM wikisync")
                current = set([row[0] for row in cursor.fetchall()])
                for name in (current - processed):
                    item = self.find(name)
                    if not item.local_version:
                        self.delete(item)
                    else:
                        item = item.merge(
                            remote_version=None,
                            sync_remote_version=None,
                        )
                        self.update(item)

    def factory(self, **kwargs):
        return _default_wikisync.merge(**kwargs)
        
    def find(self, name):
        assert isinstance(name, basestring) and len(name), \
            "String expected, but found '%s'" % name
        db = self.env.get_read_db()
        cursor = db.cursor()
        fields = ["ws.%s" % f for f in WikiSync._fields \
            if not f.startswith("local_")]
        sql = """
            SELECT %s, MAX(w.version) FROM wikisync ws
            LEFT JOIN wiki w ON w.name = ws.name
            WHERE ws.name=%%s
            GROUP BY w.name
        """ % ",".join(fields)

        cursor.execute(sql, (name,))
        row = cursor.fetchone()
        return row and WikiSync._make(row) or None
    
    def delete(self, data):
        data.validate()
        sql = "DELETE FROM wikisync WHERE name=%s"
        @self.env.with_transaction()
        def execute(db):
            cursor = db.cursor()
            try:
                cursor.execute(sql, (data.name,))
            except Exception, e:
                raise ValueError("Delete failed: %s" % e)
            if not cursor.rowcount:
                raise ValueError("Data does not exist: %s" % data)
        return data

    def create(self, data):
        data.validate()
        fields = [f for f in WikiSync._fields if not f.startswith("local_")]
        values = [getattr(data, f) for f in fields]
        sql = "INSERT INTO wikisync(%s) VALUES (%s)" % \
            (",".join(fields), ",".join(["%s"] * len(fields)))
        @self.env.with_transaction()
        def execute(db):
            cursor = db.cursor()
            try:
                cursor.execute(sql, values)
            except Exception, e:
                raise ValueError("Insert failed: %s" % e)
        return data
    
    def update(self, data):
        data.validate()
        fields = [f for f in WikiSync._fields if not f.startswith("local_")]
        values = [getattr(data, f) for f in fields]
        values.append(data.name)
        sql = """
            UPDATE wikisync SET %s WHERE name=%%s
        """ % ",".join(["%s=%%s" % k for k in fields])
        @self.env.with_transaction()
        def execute(db):
            cursor = db.cursor()
            try:
                cursor.execute(sql, values)
            except Exception, e:
                raise ValueError("Updated failed: %s" % e)
            if not cursor.rowcount:
                raise ValueError("Data does not exist: %s" % data)
        return data
    
        