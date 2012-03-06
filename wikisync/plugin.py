# -*- coding: utf-8 -*-
import re, time
from itertools import groupby
from wikisync.model import WikiSyncDao
from wikisync.util import str_mask, str_unmask, safe_str, jsonify, \
    WikiSyncRpc, WikiSyncIgnoreFilter
from genshi.builder import tag
from trac.core import *
from trac.util import get_reporter_id
from trac.env import IEnvironmentSetupParticipant
from trac.web import IRequestHandler
from trac.web.chrome import INavigationContributor, ITemplateProvider, \
    ITemplateStreamFilter, add_ctxtnav, add_notice, add_warning, \
    add_stylesheet, add_script, Chrome
from trac.admin.api import IAdminPanelProvider
from trac.wiki.model import WikiPage
from pkg_resources import resource_filename


__all__ = ["WikiSyncEnvironment", "WikiSyncPlugin", "WikiSyncAdminPanel"]

CONFIG_SECTION = "wikisync"
DB_VERSION = 1
RE_SPLIT_CAMELCASE = re.compile(r"([A-Z][A-Z][a-z])|([a-z][A-Z])")
RE_SPLIT = re.compile(r"(/| )")
RE_NUM_SPLIT = re.compile(r"([0-9.]+)")
DEFAULT_SIGNATURE = "(Updated by wikisync)"
DEFAULT_IGNORELIST = """CamelCase
PageTemplates
RecentChanges
SandBox
TitleIndex
Trac*
Inter*
(?!^WikiStart$)Wiki.*"""

class WikiSyncMixin(object):
		
    def _get_dao(self):
        return WikiSyncDao(self.env)
    
    def _get_rpc(self):
        baseurl = self._get_config("url")
        assert baseurl, "Cannot perform remote actions with setting url config."
        username = self._get_config("username")
        password = self._get_config("password")
        if password:
            try:
                password = str_unmask(password)
            except ValueError:
                # assume its in clear text
                pass
        return WikiSyncRpc(baseurl, username, password, debug=True)
        
    def _get_ignore_filter(self):
        return WikiSyncIgnoreFilter(self._get_config("ignorelist"))
        
    def _get_config(self, key, default=None):
        return self.env.config.get(CONFIG_SECTION, key, default)
        
    def _set_config(self, key, value):
        return self.env.config.set(CONFIG_SECTION, key, value)
    
    def _save_config(self, req=None):
        try:
            self.config.save()
            if req:
                add_notice(req,"Setting saved.")
        except Exception, e:
            self.log.error("Error writing config: %s", e)
            if req:
                add_warning(req, "Error writing configuration")

class WikiSyncEnvironment(Component, WikiSyncMixin):
    """WikiSync environment setup"""
    
    implements(IEnvironmentSetupParticipant)
    required = True
    
    # IEnvironmentSetupParticipant
    def environment_created(self):
        pass
            
    def environment_needs_upgrade(self, db):
        return self.get_db_version() != DB_VERSION

    def upgrade_environment(self, db):
        # borrowed from trac.env
        dao = WikiSyncDao(self.env)
        v = self.get_db_version(db) or 0
        cursor = db.cursor()
        for i in range(v + 1, DB_VERSION + 1):
            name = "version%i" % i
            try:
                schema = __import__("schema", globals(), locals(), [name])
                script = getattr(schema, name)
            except AttributeError:
                raise TracError("Invalid schema version %s" % i)
            script.do_upgrade(self.env, i, cursor)
            cursor.execute("""
                UPDATE system SET value=%s 
                WHERE name='wikisync.schema.version'
            """, (i,))
            if cursor.rowcount < 1:
                cursor.execute("""
                    INSERT INTO system(name, value) 
                    VALUES('wikisync.schema.version', %s)
                """, (i,))
            db.commit()
            self.log.info("Upgraded wikisync schema to version %s" % i)
        dao.sync_wiki_data()
        if not self._get_config("ignorelist"):
            self._set_config("ignorelist", DEFAULT_IGNORELIST)
            self._save_config()

    def get_db_version(self, db=None):
        if not db:
            db = self.env.get_read_db()
        cursor = db.cursor()
        row = cursor.execute("""
            SELECT value FROM system 
            WHERE name='wikisync.schema.version'
        """).fetchone()
        return row and int(row[0]) or 0

class WikiSyncAdminPanel(Component, WikiSyncMixin):
    """Disabling this option will require manual editing of the trac.init."""
    
    implements(IAdminPanelProvider)

    def get_admin_panels(self, req):
        if "TRAC_ADMIN" in req.perm:
            yield ("general", "General", 
                "wikisync", "Wiki Synchronization")

    def render_admin_panel(self, req, cat, page, path_info):
        req.perm.require("TRAC_ADMIN")
        password_stud = "********"
        if req.method == "POST":
            for key in ("url", "username", "password", "ignorelist"):
                value = req.args.get(key)
                if key == "password":
                    if value == password_stud:
                        continue
                    value = str_mask(value)
                self._set_config(key, value)
            self._save_config(req)
            req.redirect(req.href.admin(cat, page))
        password = self._get_config("password", "") and password_stud or ""
        data = {
            "url": self._get_config("url", ""),
            "username": self._get_config("username", ""),
            "password": password,
            "ignorelist": self._get_config("ignorelist", ""),
        }
        Chrome(self.env).add_textarea_grips(req)
        return "wikisync_admin.html", { "data":data }
    
    def _get_config(self, key, default=""):
        return self.env.config.get(CONFIG_SECTION, key, default)
        
class WikiSyncPlugin(Component, WikiSyncMixin):
    """Central interface to manage wiki syncronization"""

    implements(INavigationContributor, IRequestHandler, ITemplateProvider,
        ITemplateStreamFilter)
        
    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        return "wikisync"
    
    def get_navigation_items(self, req):
        if "WIKI_ADMIN" in req.perm:
            yield ("mainnav", "wikisync",
                   tag.a("Wiki Sync", href=req.href.wikisync()))
    
    # IRequestHandler methods
    def match_request(self, req):
        return req.path_info == "/wikisync"
    
    # ITemplateProvider
    def get_templates_dirs(self):
        return [resource_filename(__name__, "templates")]
    
    def get_htdocs_dirs(self):
        return [("wikisync", resource_filename(__name__, "htdocs"))]
    
    # ITemplateStreamFilter
    def filter_stream(self, req, method, filename, stream, data):
        if "WIKI_ADMIN" in req.perm:
            # TODO: Render individual page controls via add_ctxtnav
            pass
        return stream
        
    def process_request(self, req):
        req.perm.require("WIKI_ADMIN")
        redirect = False
        dao = self._get_dao()
        action = req.args.get("action")
        names = req.args.get("name")
        items = []
        if isinstance(names, basestring):
            names = [names]
        if names:
            for name in names:
                if not name:
                    continue
                item = dao.find(name)
                if item:
                    items.append(item)
        if action:
            rpc = self._get_rpc()
            try:
                if action == "refresh" and not items:
                    dao.sync_wiki_data()
                    ignore = self._get_ignore_filter()
                    results = rpc.get_remote_list()
                    dao.sync_remote_data(results, ignore)
                    redirect = True
                else:
                    assert items, "Missing items '%s'" % names
                for item in items:
                    if action == "refresh" and item:
                        info = rpc.get_remote_version(item.name)
                        if info:
                            item = item.merge(sync_time=time.time(), **info[0])
                            dao.update(item)
                    elif action == "pull":
                        author = get_reporter_id(req)
                        addr = req.remote_addr
                        wiki = WikiPage(self.env, item.name)
                        wiki.text = rpc.pull_wiki(item.name,
                            item.remote_version)
                        try:
                            wiki.save(author, DEFAULT_SIGNATURE, addr)
                        except TracError, e:
                            if wiki.text != wiki.old_text:
                                raise e
                        item = item.merge(
                            local_version=wiki.version
                        ).synchronized()
                        dao.update(item)
                    elif action == "push":
                        wiki = WikiPage(self.env, item.name)
                        assert wiki.version > 0, "Cannot find wiki '%s'" % item.name
                        item = item.merge(
                            **rpc.post_wiki(
                                item.name, 
                                wiki.text,
                                wiki.comment
                            )
                        ).synchronized()
                        dao.update(item)
                    elif action == "resolve":
                        status = req.args.get("status")
                        if status == "ignore":
                            item = item.merge(ignore=1)
                        elif status == "unignore":
                            item = item.merge(ignore=None)
                        elif status == "local":
                            item = item.merge(
                                sync_remote_version=item.remote_version
                            )
                        elif status == "remote":
                            item = item.merge(
                                sync_local_version=item.local_version
                            )
                        else:
                            raise RuntimeError(
                                "Unsupported resolution: '%s'" % status
                            )
                        dao.update(item)
            finally:
               rpc.close()
        if items:
            self._render_json(req, [dao.find(item.name) for item in items])
        elif redirect:
            req.redirect(req.href.wikisync())
        else:
            add_stylesheet(req, "wikisync/wikisync.css")
            add_script(req, "wikisync/underscore.js")
            add_script(req, "wikisync/backbone.js")
            add_script(req, "wikisync/wikisync.js")
            return "wikisync.html", {
                "collection": [o for o in dao.all()],
                "local_url": req.href.wiki(),
                "remote_url": self._get_config("url"),
                "endpoint": req.href.wikisync(),
            }, None 

    def _render_json(self, req, data):
        payload = safe_str(jsonify(data))
        req.send_header('Content-Type', 'text/json')
        req.send_header('Content-Length', str(len(payload)))
        req.end_headers()
        req.write(payload)
