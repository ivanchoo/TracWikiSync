# -*- coding: utf-8 -*-
import re, time
from itertools import groupby
from wikisync.model import WikiSyncDao
from wikisync.util import str_mask, str_unmask, safe_str, safe_unicode, \
    jsonify, WebClient, RegExpFilter
from genshi.builder import tag
from genshi.core import Markup
from genshi.filters import Transformer
from trac.core import *
from trac.util import get_reporter_id
from trac.env import IEnvironmentSetupParticipant
from trac.web import IRequestHandler
from trac.wiki.api import IWikiChangeListener
from trac.web.chrome import INavigationContributor, ITemplateProvider, \
    ITemplateStreamFilter, add_ctxtnav, add_notice, add_warning, \
    add_stylesheet, add_script, Chrome
from trac.admin.api import IAdminPanelProvider
from trac.wiki.model import WikiPage
from pkg_resources import resource_filename

__all__ = [
    "WikiSyncEnvironment", 
    "WikiSyncPlugin", 
    "WikiSyncPagePlugin", 
    "WikiSyncAdminPanel"
]

CONFIG_SECTION = "wikisync"

DB_VERSION = 1

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
    """Component mixin provides common utility methods"""
        
    def _get_config(self, key, default=None):
        return self.env.config.get(CONFIG_SECTION, key, default)
        
    def _set_config(self, key, value):
        return self.env.config.set(CONFIG_SECTION, key, value)
    
    def _save_config(self, req=None):
        try:
            self.config.save()
            if req:
                add_notice(req,"Setting saved")
        except Exception, e:
            self.log.error("Error writing config: %s", e)
            if req:
                add_warning(req, "Error writing configuration")

    def _get_db_version(self, db=None):
        if not db:
            db = self.env.get_read_db()
        cursor = db.cursor()
        row = cursor.execute("""
            SELECT value FROM system 
            WHERE name='wikisync.schema.version'
        """).fetchone()
        return row and int(row[0]) or 0
    
    def _render_assets(self, req):
        add_stylesheet(req, "wikisync/wikisync.css")
        add_script(req, "wikisync/underscore.js")
        add_script(req, "wikisync/backbone.js")
        add_script(req, "wikisync/wikisync.js")

class WikiSyncEnvironment(Component, WikiSyncMixin):
    """WikiSync environment setup"""
    
    implements(IEnvironmentSetupParticipant, IWikiChangeListener)
    
    # Component cannot be turn off
    required = True
    
    # IEnvironmentSetupParticipant
    def environment_created(self):
        pass
            
    def environment_needs_upgrade(self, db):
        return self._get_db_version() != DB_VERSION

    def upgrade_environment(self, db):
        # borrowed from trac.env
        dao = WikiSyncDao(self.env)
        v = self._get_db_version(db) or 0
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

    # IWikiChangeListener
    def wiki_page_added(self, page):
        dao = WikiSyncDao(self.env)
        item = dao.find(page.name)
        if not item:
            ignore_filter = RegExpFilter(
                self._get_config("ignorelist")
            )
            item = dao.factory(
                name=page.name,
                ignore=ignore_filter.matches(page.name)
            )
            dao.create(item)
            self.log.debug("Created wikisync '%s'" % item.name)

    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        pass

    def wiki_page_deleted(self, page):
        dao = WikiSyncDao(self.env)
        item = dao.find(page.name)
        if not item:
            return
        if not item.remote_version:
            dao.delete(item)
            self.log.debug("Removed wikisync '%s'" % item.name)

    def wiki_page_version_deleted(self, page):
        self.wiki_page_version_deleted(page)
        
    def wiki_page_renamed(self, page, old_name): 
        # Treat as new page
        self.wiki_page_added(page)
        
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
            remote_server_changed = False
            url = req.args.get("url", "")
            username = req.args.get("username", "")
            password = req.args.get("password", "")
            if password == password_stud:
                password = self._get_config("password")
            ignorelist = req.args.get("ignorelist", "")
            is_error = False
            server_info_changed = False
            for key in ("url", "username", "password"):
                if locals()[key] != self._get_config(key, ""):
                    server_info_changed = True
                    break
            if server_info_changed and url:
                # remote server info has changed, test connection
                try:
                    wc = WebClient(url, username, password, True)
                    wc.test()
                except Exception, e:
                    if hasattr(e, "code") and e.code == 401:
                        add_warning(req, "Authentication failed, "
                            "settings are not saved")
                    else:
                        add_warning(req, "Cannot connect to remote server, "
                            "settings are not saved")
                    is_error = True
            if not is_error:
                self._set_config("url", url)
                self._set_config("username", username)
                self._set_config("password", password)
                self._set_config("ignorelist", ignorelist)
                self._save_config(req)
                if not url:
                    add_warning(req, "Remote server not set, "
                        "Wiki Sync is disabled")
                elif not username or not password:
                    add_warning(req, "No authentication will be performed "
                        "when communicating with remote server")
                else:
                    add_notice(req, "Remember to refresh the "
                        "synchronization status")
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
    

class WikiSyncPagePlugin(Component, WikiSyncMixin):
    """Provides additional controls in the context menu 
    of individual wiki page.
    
    Requires WikiSyncPlugin."""
    implements(ITemplateStreamFilter)
    
    # ITemplateStreamFilter
    def filter_stream(self, req, method, filename, stream, data):
        if "WIKI_ADMIN" in req.perm and filename == "wiki_view.html":
            remote_url = self._get_config("url", "")
            if remote_url:
                pagename = req.args.get("page", "WikiStart")
                dao = WikiSyncDao(self.env)
                item = dao.find(pagename)
                if not item:
                    item = dao.factory(name=pagename)
                params = {
                    "model": item,
                    "remote_url": remote_url,
                    "req": req
                }
                add_ctxtnav(req,
                    tag.span(
                        tag.a(
                            tag.i(
                                item.status.upper(),
                                class_="status"
                            ),
                            Markup("&darr;"),
                            href="#", 
                            class_=item.status,
                            id_="wikisync-panel-toggle"
                        ),
                        class_="wikisync"
                    )
                )
                self._render_assets(req)
                stream |= Transformer('.//body').prepend(
                    Chrome(self.env).load_template(
                        "wikisync_page.html"
                    ).generate(**params)
                )
        return stream
        
class WikiSyncPlugin(Component, WikiSyncMixin):
    """Central interface for managing wiki syncronization"""

    implements(INavigationContributor, IRequestHandler, ITemplateProvider)
    
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
        
    def process_request(self, req):
        req.perm.require("WIKI_ADMIN")
        if req.args.get("action"):
            return self._process_action(req)
        else:
            return self._process_main(req)
    
    def _process_main(self, req):
        dao = WikiSyncDao(self.env)
        self._render_assets(req)
        return "wikisync.html", {
            "collection": [o for o in dao.all()],
            "local_url": req.href.wiki(),
            "remote_url": self._get_config("url"),
            "action_url": req.href.wikisync(),
        }, None

    def _process_action(self, req):
        dao = WikiSyncDao(self.env)
        action = req.args.get("action")
        assert len(action), "'action' required"
        names = req.args.get("name", [])
        if isinstance(names, basestring):
            if names:
                names = [names]
        else:
            names = [name for name in names if name]
        error = None
        wc = None
        try:
            wc = self._get_web_client()
            if action == "refresh":
                if names:
                    for name in names:
                        info = wc.get_remote_version(name)
                        item = dao.find(name)
                        if not item:
                            wiki = WikiPage(self.env, name)
                            if wiki.exists:
                                item = dao.factory(
                                    name=name,
                                    local_version=wiki.version,
                                    sync_time=time.time()
                                )
                                item = dao.create(item)
                                self.log.debug("Created '%s' wikisync" % name)
                        if info:
                            info = info[0]
                            info["sync_time"] = time.time()
                            if item:
                                item = dao.update(item.replace(**info))
                            else:
                                item = dao.create(dao.factory(**info))
                            self.log.debug("Updated '%s' wikisync info %s" % \
                                (name, info))
                        elif item:
                            item = dao.update(
                                item.replace(sync_time=time.time())
                            )
                else:
                    # update local and remote data
                    dao.sync_wiki_data()
                    ignore_filter = RegExpFilter(
                        self._get_config("ignorelist")
                    )
                    results = wc.get_remote_list()
                    dao.sync_remote_data(results, ignore_filter)
            elif action in ("pull", "push", "resolve"):
                items = []
                for name in names:
                    item = dao.find(name)
                    if not item:
                        raise ValueError("Missing wiki '%s'" % name)
                    if action == "pull":
                        author = get_reporter_id(req)
                        addr = req.remote_addr
                        wiki = WikiPage(self.env, item.name)
                        wiki.text = wc.pull(item.name,
                            item.remote_version)
                        if not len(wiki.text) and not wiki.version:
                            # BUGFIX: account for empy remote wiki Page,
                            # which throws a Page not modified exception when
                            # saving for the first time (default wiki.text = '')
                            wiki.text = " "
                        try:
                            wiki.save(author, DEFAULT_SIGNATURE, addr)
                        except TracError, e:
                            if wiki.text != wiki.old_text:
                                raise e
                            else:
                                self.log.debug("Content has not changed, "
                                               "skipping '%s'" % item.name)
                        item = item.replace(
                            local_version=wiki.version
                        ).synchronized()
                        dao.update(item)
                        self.log.debug("Pulled wiki '%s'" % item.name)
                    elif action == "push":
                        wiki = WikiPage(self.env, item.name)
                        assert wiki.version > 0, "Cannot find wiki '%s'" % item.name
                        item = item.replace(
                            **wc.push(
                                item.name, 
                                wiki.text,
                                wiki.comment
                            )
                        ).synchronized()
                        dao.update(item)
                        self.log.debug("Pushed wiki '%s'" % item.name)
                    elif action == "resolve":
                        status = req.args.get("status")
                        if status == "ignore":
                            item = item.replace(ignore=1)
                        elif status == "unignore":
                            item = item.replace(ignore=None)
                        elif status == "modified":
                            item = item.replace(
                                sync_remote_version=item.remote_version
                            )
                        elif status == "outdated":
                            item = item.replace(
                                sync_local_version=item.local_version
                            )
                        else:
                            raise RuntimeError(
                                "Unsupported resolution: '%s'" % status
                            )
                        dao.update(item)
                        self.log.debug("Resolved wiki '%s' as %s" % \
                            (item.name, status))
                        
            else:
                raise ValueError("Unsupported action '%s'" % action)
        except Exception, e:
            error = e
            self.log.exception(e)
        finally:
            if wc:
                wc.close()
        if req.get_header("X-Requested-With") == "XMLHttpRequest" or \
            req.get_header("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            if error:
                payload = safe_str(error);
                req.send(payload, "text/plain", 500)
            else:
                payload = safe_str(jsonify(dao.findMany(*names)))
                req.send(payload, "text/json", 200)
        else:
            if error:
                add_warning(req, "An error has occurred: %s" % error)
            if names:
                req.redirect(req.href.wiki(names[0]))
            else:
                req.redirect(req.href.wikisync())

    def _get_web_client(self):
        baseurl = self._get_config("url")
        assert baseurl, ("Cannot perform synchronization "
                        "without url configuration.")
        username = self._get_config("username")
        password = self._get_config("password")
        if password:
            try:
                password = str_unmask(password)
            except ValueError:
                # assume its in clear text
                pass
        return WebClient(baseurl, username, password, debug=False)