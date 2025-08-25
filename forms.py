from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo

class RegistrationForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField('Confirma Contraseña', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Registrarse')

class LoginForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class MemoryForm(FlaskForm):
    content = TextAreaField('Recuerdo', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Compartir')

class AddFriendForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[DataRequired()])
    submit = SubmitField('Enviar Solicitud')

class ProfileForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[DataRequired(), Length(min=2, max=20)])
    submit = SubmitField('Guardar')