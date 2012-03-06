TracWikiSync
============

Introduction
------------
This [Trac](http://trac.edgewall.org/) plugin allows you to synchronize wiki entries between to separate Trac installations. 

Common use case is be to install a local Trac project on your workstation and synchronizing the wiki entires from your remote Trac server. This is especially useful when working over slow VPN connections and/or working offline, editing the wikies and doing batch synchronizing when you're ready to commit.

Some features are:

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

 - Implement single wiki synchronization
 
 - Implement attachment synchronization

Installation and Requirements
-----------------------------

Minimum requirements:

 - Trac 0.12 >=
 
 - Python 2.6 >=
 
### Per Trac Project ###

 1. Via the Trac Admin > Plugins web interface or
 
 1. See http://trac.edgewall.org/wiki/TracPlugins#Forasingleproject
 
### For All Trac Projects ###
 
 1. http://trac.edgewall.org/wiki/TracPlugins#Forallprojects
 
 1. Enabling the plugin in `trac.ini`:<blockquote>
[components]
wikisync.* = enabled`
</blockquote>

Usage
-----

Develop
-------

Bugs
----

Version History
---------------

TODO