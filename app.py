import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from forms import RegistrationForm, LoginForm, MemoryForm, AddFriendForm, ProfileForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mi-secreto-super-seguro'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diario.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Función para incrustar videos de YouTube ---
def get_youtube_embed_url(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    
    match = re.match(youtube_regex, url)
    if match and match.group(6):
        video_id = match.group(6)
        return f"https://www.youtube.com/embed/{video_id}"
    return None

# Esto hace que la función esté disponible en las plantillas HTML
app.jinja_env.globals.update(get_youtube_embed_url=get_youtube_embed_url)

# --- Modelos de la Base de Datos ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    profile_pic_path = db.Column(db.String(128), default='default.jpg')
    sent_requests = db.relationship('Friendship', foreign_keys='Friendship.sender_id', backref='sender', lazy='dynamic')
    received_requests = db.relationship('Friendship', foreign_keys='Friendship.receiver_id', backref='receiver', lazy='dynamic')
    shared_memories = db.relationship('SharedMemory', foreign_keys='SharedMemory.author_id', backref='author', lazy='dynamic')
    shared_links = db.relationship('SharedLink', foreign_keys='SharedLink.author_id', backref='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(10), default='pending')

class SharedMemory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, index=True, default=db.func.now())

class SharedLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, index=True, default=db.func.now())
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Rutas de la Aplicación ---
@app.route('/')
@login_required
def index():
    memories = SharedMemory.query.order_by(SharedMemory.timestamp.desc()).all()
    links = SharedLink.query.order_by(SharedLink.timestamp.desc()).all()
    images = os.listdir(app.config['UPLOAD_FOLDER'])
    form = AddFriendForm()
    return render_template('index.html', memories=memories, form=form, images=images, links=links)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('¡Sesión iniciada!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('¡Registro exitoso! Por favor, inicia sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'success')
    return redirect(url_for('login'))

@app.route('/add_friend', methods=['POST'])
@login_required
def add_friend():
    form = AddFriendForm()
    if form.validate_on_submit():
        friend = User.query.filter_by(username=form.username.data).first()
        if friend:
            if friend == current_user:
                flash("No puedes agregarte a ti mismo.", 'danger')
            elif Friendship.query.filter_by(sender_id=current_user.id, receiver_id=friend.id).first() or \
                 Friendship.query.filter_by(sender_id=friend.id, receiver_id=current_user.id).first():
                flash("Ya eres amigo de este usuario o la solicitud está pendiente.", 'warning')
            else:
                friendship = Friendship(sender_id=current_user.id, receiver_id=friend.id)
                db.session.add(friendship)
                db.session.commit()
                flash(f"Solicitud de amistad enviada a {friend.username}.", 'success')
        else:
            flash("Usuario no encontrado.", 'danger')
    return redirect(url_for('index'))

@app.route('/friends')
@login_required
def friends():
    sent_requests = current_user.sent_requests.filter_by(status='pending').all()
    received_requests = current_user.received_requests.filter_by(status='pending').all()
    my_friends = Friendship.query.filter((Friendship.sender_id == current_user.id) | (Friendship.receiver_id == current_user.id)).filter_by(status='accepted').all()
    return render_template('friends.html', sent_requests=sent_requests, received_requests=received_requests, my_friends=my_friends)

@app.route('/accept_friend/<int:request_id>')
@login_required
def accept_friend(request_id):
    friend_request = Friendship.query.get_or_404(request_id)
    if friend_request.receiver_id == current_user.id:
        friend_request.status = 'accepted'
        db.session.commit()
        flash("Solicitud de amistad aceptada.", 'success')
    return redirect(url_for('friends'))

@app.route('/post_memory', methods=['POST'])
@login_required
def post_memory():
    form = MemoryForm()
    if form.validate_on_submit():
        memory = SharedMemory(content=form.content.data, author_id=current_user.id)
        db.session.add(memory)
        db.session.commit()
        flash('Recuerdo compartido correctamente!', 'success')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            flash('Imagen subida correctamente!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Tipo de archivo no permitido.', 'danger')
    return render_template('upload.html')

@app.route('/post_link', methods=['POST'])
@login_required
def post_link():
    url = request.form.get('link_url')
    if url:
        link = SharedLink(url=url, author_id=current_user.id)
        db.session.add(link)
        db.session.commit()
        flash('Link compartido correctamente!', 'success')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if request.method == 'POST':
        # Lógica para subir una foto de perfil
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                current_user.profile_pic_path = filename
                db.session.commit()
                flash('Foto de perfil actualizada.', 'success')
            else:
                flash('Tipo de archivo no permitido.', 'danger')

        # Lógica para cambiar el nombre de usuario
        if form.validate_on_submit():
            current_user.username = form.username.data
            db.session.commit()
            flash('Nombre de usuario actualizado.', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', form=form)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')