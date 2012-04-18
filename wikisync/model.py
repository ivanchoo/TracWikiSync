# -*- coding: utf-8 -*-
import time
from wikisync.util import safe_int
from collections import namedtuple

WIKISYNC_TABLE_FIELDS = (
    "name",
    "ignore",
    "ignore_attachment", 
    "sync_time",
    "sync_remote_version",
    "sync_local_version",
    "remote_version"
)

WIKISYNC_EXTERNAL_FIELDS = (
    "local_version",
    "status"
)
    
class WikiSync(namedtuple("WikiSync", 
    WIKISYNC_TABLE_FIELDS + WIKISYNC_EXTERNAL_FIELDS)):
    """Represents a wiki synchronization state."""
    
    __slots__ = ()
    
    def replace(self, *args, **kwargs):
        """Returns a new instance with the updated properties.
        
        The 'status' property is calculated dynamically, setting this
        property will have no effect in the output.
        
        @param *args: non-keyworded arguments must be in the same order
            as the WikiSync._fields.
        @param **kwargs: An exception will be thrown on non-existent keywords.
        """
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
            elif rv < srv or lv < slv:
                # edge case, local wiki or remote wiki was deleted
                # and re-added, causing the synced version to be higher
                # we mark the status as conflict and prompt user to resolve it
                status = "conflict"
        return o.status == status and o or o._replace(status=status)
    
    def validate(self):
        """Validates if the model can be persisted."""
        assert isinstance(self.name, basestring) and len(self.name) > 0, \
            "name required"
        return True
    
    def synchronized(self):
        """Returns an instance marked as status='synced'"""
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

class WikiSyncDao(object):
    """Persistence interface for WikiSync objects."""
    
    def __init__(self, env):
        self.env = env

    def all(self):
        """Returns all available WikiSync objects."""
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
        """Makes the WikiSync data in sync with the local database."""
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
        """Makes the WikiSync data in sync with the remote wiki states.
        
        @param dataset: an array of dict containing all remote wiki information.
            Primary WikiSync properties should be provided, 
            e.g. 'name' and 'remote_version'.
        @param ignore_filter: an instance of wikisync.util.RegExpFilter, used to
            determine the initial 'ignore' state of new WikiSync.
        """
        sync_time = time.time()
        @self.env.with_transaction()
        def execute(db):
            processed = set()
            for data in dataset:
                name = data.get("name", None)
                item = self.find(name)
                if not item:
                    if ignore_filter and ignore_filter.matches(name):
                        data["ignore"] = 1
                    self.create(self.factory(sync_time=sync_time, **data))
                else:
                    if not item.sync_time:
                        if ignore_filter and ignore_filter.matches(item.name):
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
                            sync_time=sync_time
                        )
                        self.update(item)

    def factory(self, **kwargs):
        """Returns a WikiSync object with default properties"""
        return WIKISYNC_FACTORY.replace(**kwargs)
        
    def find(self, name):
        """Returns a WikiSync object with the corresponding 'name'.
        
        Returns None if non is found."""
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
    
    def findMany(self, *names):
        """Returns an array of WikiSync objects that matches '*names'."""
        items = []
        for name in names:
            item = self.find(name)
            if item:
                items.append(item)
        return items

    def delete(self, item):
        item.validate()
        sql = "DELETE FROM wikisync WHERE name=%s"
        @self.env.with_transaction()
        def execute(db):
            cursor = db.cursor()
            try:
                cursor.execute(sql, (item.name,))
            except Exception, e:
                raise ValueError("Delete failed: %s" % e)
            if not cursor.rowcount:
                raise ValueError("Data does not exist: %s" % item)
        return item

    def create(self, item):
        item.validate()
        values = [getattr(item, f) for f in WIKISYNC_TABLE_FIELDS]
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
        return item
    
    def update(self, item):
        item.validate()
        values = [getattr(item, f) for f in WIKISYNC_TABLE_FIELDS]
        values.append(item.name)
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
                raise ValueError("Data does not exist: %s" % item)
        return item
    
        