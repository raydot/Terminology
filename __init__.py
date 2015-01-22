# -*- coding: utf-8 -*-
#####################
#
# © 2013–2014 Autodesk Development Sàrl
#
# Created by Ventsislav Zhechev on 22 Oct 2013
#
# Changelog
# v1.1		Modified on 21 May 2014 by Ventsisalv Zhechev
# Switched to using KVSession for in-memory storage of session data to replace the cookie-based system.
# Updated to use the new recommended method for CSRF protection.
#
# v1.			Modified on 22 Nov 2013 by Ventsisalv Zhechev
# Production version.
#
# v0.1		Modified on 22 Oct 2013 by Ventsislav Zhechev
# Original version.
#
#####################

from flask import Flask

Terminology_staging = Flask(__name__)
Terminology_staging.config.from_object('config')

# from flask_wtf.csrf import CsrfProtect
# CsrfProtect(Terminology_staging)

from simplekv.memory import DictStore
from flaskext.kvsession import KVSessionExtension
store = DictStore()
KVSessionExtension(store, Terminology_staging)

import logging
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler('/var/log/Terminology/Terminology_staging.log', 'a', 1 * 1024 * 1024, 30)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
Terminology_staging.logger.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)
Terminology_staging.logger.addHandler(file_handler)


from Terminology_staging import Service