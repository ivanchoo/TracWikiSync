# -*- coding: utf-8 -*-
import zlib, base64, os, tempfile, cookielib, urllib2, \
    urllib, itertools, re
from hashlib import md5
from StringIO import StringIO
from genshi.input import HTMLParser
from urlparse import urlparse, parse_qs
try:
    import simplejson as json
except ImportError:
    import json

def jsonify(obj):
    """Returns a jsonified string"""
    return json.dumps(obj)

def safe_url(prefix, *paths):
    """Safely encode a url path, ensuring the prefix has no tailing slash
    and the path fragment is uses the %%xx escape."""
    if prefix.endswith("/"):
        prefix = host[-1]
    if paths:
        suffix = "/".join(paths)
        if suffix.startswith("/"):
            suffix = suffix[1:]
        return "%s/%s" % (prefix, urllib.quote(suffix.encode("utf-8")))
    return host
    
def safe_unicode(obj, encoding="utf-8"):
    """Returns a unicode object, suppressing all errors"""
    t = type(obj)
    if t is unicode:
        return obj
    elif t is str:
        return obj.decode(encoding)
    elif t in [int, float, bool]:
        return unicode(obj)
    else:
        if hasattr(obj, "__unicode__"):
            return unicode(obj)
        else:
            return str(obj).decode(encoding)
    
def safe_str(obj, encoding="utf-8"):
    """Returns a string object, suppressing all errors"""
    if isinstance(obj, unicode):
        return obj.encode(encoding)
    elif isinstance(obj, str):
        return obj
    elif hasattr(obj, "next") and hasattr(obj, "__iter__"): # iterator
        return itertools.imap(safe_str, obj)
    else:
        return str(obj)

def safe_int(value):
    """Returns an int object, suppressing all errors, default to 0"""
    try:
        return int(value)
    except:
        return 0
        
def str_mask(message):
    """Masks a string to make it unreadable.
    This is not to be used as a mean of encryption"""
    assert isinstance(message, basestring) and len(message), \
        "Expect string, got '%s'" % message
    return base64.b64encode(zlib.compress(message))

def str_unmask(masked):
    """Opposite of str_mask()"""
    assert isinstance(masked, basestring) and len(masked), \
        "Expect string, got '%s'" % masked
    try:
        return zlib.decompress(base64.b64decode(masked))
    except Exception, e:
        raise ValueError("Unable to unmask string: %s" % e)

def safe_urlencode(data):
    """Returns an url encoded string, safely handles string encodings"""
    safe = {}
    for k, v in data.items():
        safe[safe_str(k)] = safe_str(v)
    return urllib.urlencode(safe)

def server_name(url):
    """Returns a readable server name"""
    info = urlparse(url)
    name = info.hostname
    if info.port and info.port not in (80, 443):
        name = "%s:%s" % (name, info.port)
    return name
    
def parse_form_params(source, form_id=None, exclude=None):
    """Returns the values of a HTML form in a dict"""
    if isinstance(source, basestring):
        f = StringIO(source)
    elif hasattr(source, "read"):
        f = source
    else:
        raise AssertionError("Expect file like object, got %s" % source)
    parser = HTMLParser(f)
    params = {}
    def parse_input(kind, data):
        if kind == "END":
            if data == "form":
                return True
        elif kind == "START":
            qname, attrs = data
            localname = qname.localname
            name = attrs.get("name", None)
            if not name:
                return
            elif exclude and name in exclude:
                return
            if localname == "input":
                params[name] = attrs.get("value", "")
            elif localname == "textarea":
                params["__textarea__"] = name
        elif kind == "TEXT" and "__textarea__" in params:
            params[params["__textarea__"]] = data
            del params["__textarea__"]
    
    parse_form_params.handler = parse_input
    if form_id:
        def parse_form(kind, data):
            if kind == "START":
                qname, attrs = data
                if qname.localname == "form" \
                    and attrs.get("id", None) == form_id:
                    parse_form_params.handler = parse_input
        parse_form_params.handler = parse_form
    for kind, data, pos in parser:
        if parse_form_params.handler(kind, data):
            break
    return params
    
def parse_recent_changes(source, path_prefix="/wiki"):
    """Parses the 'RecentChanges' HTML source and return an array of dict
    containing the wiki 'name' and 'remote_version'"""
    return _parse_html_version_links(source, 
        lambda data: data[1].get("id", None) == "wikipage", 
        path_prefix
    )

def parse_timeline(source, path_prefix="/wiki"):
    """Parses the 'Timeline' HTML source and return an array of dict
    containing the wiki 'name' and 'remote_version'"""
    return _parse_html_version_links(source, 
        lambda data: data[1].get("id", None) == "content", 
        path_prefix
    )

def parse_wiki(source, path_prefix="/wiki"):
    """Parses a wiki pageit HTML source and return an array of dict
    containing the wiki 'name' and 'remote_version'"""
    return _parse_html_version_links(source, 
        lambda data: data[1].get("class", None) == "trac-modifiedby", 
        path_prefix
    )
    
def _parse_html_version_links(source, check_data, path_prefix):
    if isinstance(source, basestring):
        f = StringIO(source)
    elif hasattr(source, "read"):
        f = source
    else:
        raise AssertionError("Expect file like object, got %s" % source)
    parser = HTMLParser(f)
    counter = 0
    found_level = -1
    handler = None
    map = {}
    path_prefix = path_prefix or "/"
    if not path_prefix.endswith("/"):
        path_prefix = "%s/" % path_prefix
    path_prefix_len = len(path_prefix)
    for kind, data, pos in parser:
        if kind == "START":
            counter += 1
            if found_level != -1:
                href = data[1].get("href", None)
                if href and href.startswith(path_prefix):
                    url = urlparse(href)
                    path = safe_unicode(
                        urllib.unquote(
                            safe_str(url.path[path_prefix_len:])
                        ).decode("utf-8")
                    )
                    if path in map:
                        item = map[path]
                    else:
                        item = map[path] = {
                            "name":path,
                            "remote_version":1
                        }
                    if url.query:
                        qs = parse_qs(url.query)
                        version = "version" in qs and int(qs["version"][0]) or 0
                        if item["remote_version"] < version:
                            item["remote_version"] = version
            elif check_data(data):
               found_level = counter
        elif kind == "END":
            counter -= 1
            if found_level and counter < found_level:
                break
    return map.values()

class RegExpFilter(object):
    """Helper class to match a string to multiple regular expressions."""
    
    def __init__(self, filters):
        if isinstance(filters, basestring):
            filters = filters.split()
        self._regexes = filters and [re.compile(f) for f in filters] or []
    
    def matches(self, name):
        for r in self._regexes:
            if r.match(name):
                return True
        return False
        
class WebClient(object):

    def __init__(self, baseurl, username=None, password=None, debug=False):
        assert isinstance(baseurl, basestring) and len(baseurl), \
            "'baseurl' expects string, got '%s'" % baseurl
        if baseurl.endswith("/"):
            baseurl = baseurl[0:-1]
        self.baseurl = baseurl
        self.username = username
        self.password = password
        self.debug = debug
        self._cookie_jar = None
        self._opener = None
        self._authenticated = False
    
    def open(self, path, data=None, method="GET"):
        self.authenticate()
        url = self.url(path)
        qs = data and safe_urlencode(data) or None
        try:
            if qs and method == "GET":
                url = "%s?%s" % (url, qs)
                qs = None
            req = urllib2.Request(url)
            return self.opener().open(req, qs)
        except urllib2.HTTPError, e:
            if e.code in (401,):
                self.authenticate()
                return self.opener().open(req, data)
            else:
                raise e
                
    def opener(self, no_cache=False):
        if not self._opener:
            m = md5()
            m.update(self.baseurl)
            m.update(self.username or "username")
            m.update(self.password or "password")
            hash = m.hexdigest()
            cookie_file = os.path.join(tempfile.gettempdir(), hash)
            if no_cache and os.path.isfile(cookie_file):
                os.remove(cookie_file)
            has_cookie = os.path.isfile(cookie_file)
            cookie_jar = cookielib.LWPCookieJar(cookie_file)
            handlers = [urllib2.HTTPCookieProcessor(cookie_jar)]
            if self.debug:
                handlers.append(urllib2.HTTPHandler(debuglevel=1))
            if has_cookie:
                cookie_jar.load(ignore_discard=True)
            opener = urllib2.build_opener(*handlers)
            self._require_authentication = False
            if self.username and self.password:
                password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
                password_mgr.add_password(None, self.baseurl, 
                    self.username, self.password)
                opener.add_handler(urllib2.HTTPBasicAuthHandler(password_mgr))
                opener.add_handler(urllib2.HTTPDigestAuthHandler(password_mgr))
                self._require_authentication = not has_cookie
            self._opener = opener
            self._cookie_jar = cookie_jar
        return self._opener
    
    def close(self):
        self.save_cookie()
        self._cookie_jar = None
        self._opener = None
    
    def test(self):
        self.close()
        self.opener(no_cache=True)
        return self.open("wiki")
        
    def authenticate(self):
        opener = self.opener()
        if self._require_authentication:
            try:
                opener.open(urllib2.Request(self.url("login")))
                self.save_cookie()
                self._require_authentication = False
            except Exception, e:
                self.close()
                raise e
         
    def save_cookie(self):
        if self._cookie_jar:
            self._cookie_jar.save(ignore_discard=True)

    def url(self, path=""):
        return safe_url(self.baseurl, path)
        
    def basepath(self, path=""):
        return urlparse(self.url(path)).path
    
    def get_remote_list(self):
        return parse_recent_changes(
            self.open("wiki/RecentChanges"), self.basepath("wiki"))
    
    def get_remote_updates(self, date, days=10):
        data = {
            "wiki": "on",
        }
        return parse_timeline(
            self.open("timeline", data, "GET"), self.basepath("wiki"))
    
    def get_remote_version(self, name):
        return parse_wiki(
            self.open("wiki/%s" % name), self.basepath("wiki"))
        
    def pull(self, name, version=None):
        data = { "format":"txt" }
        if version:
            data["version"] = version
        f = self.open("wiki/%s" % name, data, "GET")
        return safe_unicode(f.read())
    
    def push(self, name, text, comments=None):
        data = { "action":"edit" }
        params = parse_form_params(
            self.open("wiki/%s" % name, data, "GET"), 
            form_id="edit", 
            exclude=("cancel", "preview", "diff", "merge")
        )
        if not params:
            raise RuntimeError("Cannot parse form parameters from '%s'" % \
                self.url(path))
        params["text"] = text
        params["comment"] = self._format_comment(comments)
        info = parse_wiki(
            self.open("wiki/%s" % name, params, "POST"),
            self.basepath("wiki")
        )
        if not info:
            raise RuntimeError("Unable to post data to remote server")
        return info[0]
    
    def _format_comment(self, comments=""):
        from wikisync.plugin import DEFAULT_SIGNATURE
        marker = DEFAULT_SIGNATURE
        if not isinstance(comments, basestring):
            return marker
        return "%s\n%s" % (comments, marker)