from flask.ext.wtf import Form
from wtforms import TextField, PasswordField, BooleanField, SubmitField, HiddenField
from wtforms.validators import Required

class LoginForm(Form):
	username = TextField('username', validators = [Required()])
	password = PasswordField('password', validators = [Required()])
	remember_me = BooleanField('remember_me', default = False)
	submit = SubmitField('login')

