#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#####################
#
# © 2013–2014 Autodesk Development Sàrl
#
# Created by Ventsislav Zhechev in 2013
#
# Changelog
# v1.			Modified in 2013 by Ventsislav Zhechev
# Original production version.
#
#####################

import sys
sys.path.insert(0, "/usr/lib/cgi-bin/Terminology_staging")
sys.path.insert(0, '/usr/lib/cgi-bin/')


from flup.server.fcgi import WSGIServer
from werkzeug.contrib.fixers import CGIRootFix

from Terminology_staging import Terminology_staging as application


application.wsgi_app = CGIRootFix(application.wsgi_app)
if __name__ == '__main__':
	WSGIServer(application).run()
