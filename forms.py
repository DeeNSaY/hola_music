from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length

class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя',
                          validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email',
                       validators=[DataRequired(), Email()])
    password = PasswordField('Пароль',
                            validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтверждение пароля',
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    email = StringField('Email',
                       validators=[DataRequired(), Email()])
    password = PasswordField('Пароль',
                            validators=[DataRequired()])
    submit = SubmitField('Войти')

class ChatForm(FlaskForm):
    message = TextAreaField('Сообщение',
                           validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField('Отправить')