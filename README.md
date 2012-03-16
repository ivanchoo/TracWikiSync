TracWikiSync
============

This [Trac](http://trac.edgewall.org/) plugin allows you to synchronize wiki pages between to separate Trac installations. 

A common use case is to install a local Trac project on your workstation and synchronize the wiki pages with your remote Trac server. This allows you to bring the wiki content offline, or edit the content locally before batch updating to the remote server (useful when working over slow Internet/VPN connections).


Features
------------

 - Supports various type of synchronization states:
 
  - `MODIFED`: Local page has been modified and will be updated to the remote server 
  
  - `NEW`: Local page is new and will be updated to the remote server
  
  - `OUTDATED`: Remote page has been modified and will be copied from the remote server
  
  - `MISSING`: Remote page exists and will be copied from the remote server
  
  - `CONFLICT`: Both local and remote pages have been modified, you can choose to either update to or copy from the remote server
  
  - `SYNCED`: Both local and remote pages are identitical
  
  - `IGNORED`: Skip these pages during synchronization
  
 - Uses standard `GET` and `POST` methods for synchronization, no other Trac plugins required
 
 - Supports `BASIC`/`DIGEST` authentication
 
 - Supports batch synchronization

TODO
----
 
 - Implement attachment synchronization

Installation and Requirements
-----------------------------

Minimum requirements:

 - Trac 0.12 >=
 
 - Python 2.6 >=

Instructions:

 1. Install Trac and the latest [TracWikiSync](https://github.com/ivanchoo/TracWikiSync/zipball/master) (highly recommend using [virtualenvwrapper](http://www.doughellmann.com/projects/virtualenvwrapper/))<pre>
$ pip install trac
...
$ pip install TracWikiSync-xxx.zip
</pre>
 
 2. Create a new Trac environment<pre>
$ trac-admin /path/to/myproject initenv
$ trac-admin /path/to/myproject permission add admin TRAC_ADMIN
$ htdigest -c /path/to/myproject/.htpasswd myproject admin
...
</pre>

 3. Enable the plugin by adding the following lines in `myproject/conf/trac.ini`<pre>
[components]
wikisync.* = enabled
</pre>

 4. Upgrade the Trac environment<pre>
$ trac-admin /path/to/myproject upgrade
...
</pre>

 5. Start Trac<pre>
$ tracd --port=8080 \
  --auth=*,/path/to/myproject/.htpasswd,myproject \
  /path/to/myproject
</pre>

User Permissions
----------------

Trac users require the following permissions:

 - `TRAC_ADMIN`: To configure the remote server information in the admin panels
 
 - `WIKI_ADMIN`: To perform synchronization

Bugs
----

Please use [Issues](https://github.com/ivanchoo/TracWikiSync/issues)

Version History
---------------

 - v0.1: Initial release.