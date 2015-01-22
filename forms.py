# -*- coding: utf-8 -*-
#####################
#
# © 2013–2014 Autodesk Development Sàrl
#
# Created by Ventsislav Zhechev in 2013
#
# Changelog
# v1.1		Modified on 21 May 2014 by Ventsisalv Zhechev
# Updated to use the latest version of Flask-WTF.
#
# v1.			Modified in 2013 by Ventsislav Zhechev
# Original production version.
#
#####################

from flask_wtf import Form
from wtforms import TextField, PasswordField, BooleanField, SubmitField, HiddenField
from wtforms.validators import Required

class LoginForm(Form):
	username = TextField('username', validators = [Required()])
	password = PasswordField('password', validators = [Required()])
	remember_me = BooleanField('remember_me', default = False)
	submit = SubmitField('login')
