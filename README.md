TracWikiSync
============

This [Trac](http://trac.edgewall.org/) plugin allows you to synchronize wiki entries between to separate Trac installations. 

Common use case is be to install a local Trac project on your workstation and synchronizing the wiki entires from your remote Trac server. This is especially useful when working over slow VPN connections and/or working offline, editing the wikies and doing batch synchronizing when you're ready to commit.

Features
------------

 - Supports the following type of synchronization:
 
  - `MODIFED`: Local wiki has been modified and will be pushed to the remote server 
  
  - `NEW`: Local wiki is new and will be pushed to the remote server
  
  - `OUTDATED`: Remote wiki has been modified and will be pulled from the remote server
  - `MISSING`: Remote wiki is missing and will be pulled from the remote server
  
  - `CONFLICT`: Both local and remote wiki has been modified, you can choose to either push to or pull from the remote server
  
  - `SYNCED`: Both local and remote wiki are identitical
  
  - `IGNORED`: Ignored wikies will be skipped during synchronization
  
 - Uses standard `GET` and `POST` methods, no other plugins required
 
 - Supports `BASIC`/`DIGEST` authentication on the remote server
 
 - Supports batch synchronization

TODO
----

 - Fix GUI to solve screen lock ups and show better progress status

 - Implement quick filter for batch synchronization screen
 
 - Implement refresh from last sync for faster status detection
 
 - Implement single wiki synchronization
 
 - Implement attachment synchronization
 
 - Implement IWikiChangeListener to catch deleted and renamed wiki changes

Installation and Requirements
-----------------------------

TODO

Minimum requirements:

 - Trac 0.12 >=
 
 - Python 2.6 >=

 - Enabling the plugin in `trac.ini`:<pre>
[components]
wikisync.* = enabled`
</pre>

Usage
-----

Trac users require the following permissions:

 - `TRAC_ADMIN`: To configure the remote server information in the admin panels
 
 - `WIKI_ADMIN`: To perform synchronization

Develop
-------

TODO

Bugs
----

Please use [Issues](https://github.com/ivanchoo/TracWikiSync/issues)

Version History
---------------

TODO