# -*- coding: utf-8 -*-
import time
from wikisync.util import safe_int
from collections import namedtuple

class WikiSync(namedtuple("WikiSync", [
        "name", "ignore", "ignore_attachment", 
        "sync_time", "sync_remote_version", "sync_local_version",
        "remote_version", "local_version", "status"
        ])):
    
    __slots__ = ()
    
    def replace(self, *args, **kwargs):
        if len(args):
            kwargs = dict(zip(WikiSync._fields, args))
        o = self._replace(**kwargs)
        status = "unknown"
        if o.ignore:
            status = "ignored"
        elif o.sync_time:
            rv = safe_int(o.remote_version)
            lv = safe_int(o.local_version)
            srv = safe_int(o.sync_remote_version)
            slv = safe_int(o.sync_local_version)
            if rv and not lv:
                # can"t find local copy
                status = "missing"
            elif lv and not rv:
                # can"t find remote copy
                status = "new"
            elif rv > srv and lv > slv:
                # both remote and local are out of sync
                status = "conflict"
            elif rv > srv:
                # local in-sync, but remote out of sync
                status = "outdated"
            elif lv > slv:
                # local out of sync, but remote in sync
                status = "modified"
            elif rv == srv and lv == slv:
                status = "synced"
        return o.status == status and o or o._replace(status=status)
    
    def validate(self):
        assert isinstance(self.name, basestring) and len(self.name) > 0, \
            "name required"
        return True
    
    def synchronized(self):
        assert safe_int(self.remote_version), \
            "Invalid remote_version '%s'" % self.remote_version
        assert safe_int(self.local_version), \
            "Invalid local_version '%s'" % self.local_version
        return self.replace(
            sync_remote_version=self.remote_version,
            sync_local_version=self.local_version,
            sync_time = time.time(),
        )
        
WIKISYNC_FACTORY = WikiSync(
    name=None,
    ignore=None,
    ignore_attachment=None,
    sync_time=None,
    sync_remote_version=None,
    sync_local_version=None,
    remote_version=None,
    local_version=None,
    status="unknown"
)

WIKISYNC_TABLE_FIELDS = [f for f in WikiSync._fields \
    if f not in ("local_version", "status")]
    
class WikiSyncDao(object):
    
    def __init__(self, env):
        self.env = env

    def all(self):
        db = self.env.get_read_db()
        fields = ["ws.%s" % f for f in WIKISYNC_TABLE_FIELDS]
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
                yield WIKISYNC_FACTORY.replace(*row)
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
            self.create(WIKISYNC_FACTORY.replace(name=row[0]))

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
                            item = item.replace(ignore=1)
                    item = item.replace(sync_time=sync_time, **data)
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
                        item = item.replace(
                            remote_version=None,
                            sync_remote_version=None,
                        )
                        self.update(item)

    def factory(self, **kwargs):
        return WIKISYNC_FACTORY.replace(**kwargs)
        
    def find(self, name):
        assert isinstance(name, basestring) and len(name), \
            "String expected, but found '%s'" % name
        db = self.env.get_read_db()
        cursor = db.cursor()
        fields = ["ws.%s" % f for f in WIKISYNC_TABLE_FIELDS]
        sql = """
            SELECT %s, MAX(w.version) FROM wikisync ws
            LEFT JOIN wiki w ON w.name = ws.name
            WHERE ws.name=%%s
            GROUP BY w.name
        """ % ",".join(fields)
        cursor.execute(sql, (name,))
        row = cursor.fetchone()
        return row and WIKISYNC_FACTORY.replace(*row) or None
    
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
        values = [getattr(data, f) for f in WIKISYNC_TABLE_FIELDS]
        sql = "INSERT INTO wikisync(%s) VALUES (%s)" % \
            (",".join(WIKISYNC_TABLE_FIELDS), 
                ",".join(["%s"] * len(WIKISYNC_TABLE_FIELDS)))
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
        values = [getattr(data, f) for f in WIKISYNC_TABLE_FIELDS]
        values.append(data.name)
        sql = """
            UPDATE wikisync SET %s WHERE name=%%s
        """ % ",".join(["%s=%%s" % k for k in WIKISYNC_TABLE_FIELDS])
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
    
        