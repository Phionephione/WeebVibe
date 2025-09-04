import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate

# --- App and Database Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-super-secret-key-for-development')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///anime_platform.db').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Helper Function ---
def generate_affiliate_link(original_url, service_name):
    CRUNCHYROLL_AFFILIATE_ID = "?af_id=YOUR_CRUNCHYROLL_ID"
    if "crunchyroll" in service_name.lower():
        return original_url + CRUNCHYROLL_AFFILIATE_ID
    return original_url
app.jinja_env.globals.update(generate_affiliate_link=generate_affiliate_link)

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Models ---
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_like = db.Column(db.Boolean, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    anime_mal_id = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'anime_mal_id', name='_user_anime_uc'),)

class CommentLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='_user_comment_uc'),)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    comments = db.relationship('Comment', backref='author', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='user', lazy=True, cascade="all, delete-orphan")
    comment_likes = db.relationship('CommentLike', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mal_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(250), nullable=False)
    synopsis = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(250), nullable=True)
    score = db.Column(db.Float, nullable=True)
    streaming_links = db.Column(db.JSON, nullable=True)
    genres = db.Column(db.JSON, nullable=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    anime_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('CommentLike', backref='comment', lazy=True, cascade="all, delete-orphan")

# --- Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('home'))
    api_results = []
    try:
        response = requests.get(f"https://api.jikan.moe/v4/anime?q={query}&limit=24")
        response.raise_for_status()
        api_data = response.json()
        api_results = api_data.get('data', [])
    except requests.exceptions.RequestException as e:
        flash(f"Error communicating with the anime database API: {e}", "error")
        api_results = []
    return render_template('search_results.html', results=api_results, query=query)

@app.route('/anime/<int:mal_id>')
def anime_details(mal_id):
    anime = Anime.query.filter_by(mal_id=mal_id).first()
    if not anime:
        try:
            response = requests.get(f"https://api.jikan.moe/v4/anime/{mal_id}")
            response.raise_for_status()
            api_data = response.json()['data']
            response_streaming = requests.get(f"https://api.jikan.moe/v4/anime/{mal_id}/streaming")
            response_streaming.raise_for_status()
            streaming_data = response_streaming.json().get('data', [])
            anime = Anime(
                mal_id=api_data['mal_id'],
                title=api_data['title'],
                synopsis=api_data['synopsis'],
                image_url=api_data['images']['jpg']['large_image_url'],
                score=api_data['score'],
                streaming_links=streaming_data,
                genres=api_data.get('genres', [])
            )
            db.session.add(anime)
            db.session.commit()
        except requests.exceptions.RequestException as e:
            flash(f"Error fetching from Jikan API: {e}", "error")
            return redirect(url_for('home'))

    recommendations = []
    if anime.genres:
        genre_names = [genre['name'] for genre in anime.genres]
        
        # THIS IS THE CORRECTED LINE FOR POSTGRESQL
        genre_queries = [db.cast(Anime.genres, db.String).like(f'%{name}%') for name in genre_names]
        
        recommendations = Anime.query.filter(
            or_(*genre_queries),
            Anime.mal_id != mal_id
        ).limit(7).all()
        
    initial_likes = Like.query.filter_by(anime_mal_id=mal_id, is_like=True).count()
    initial_dislikes = Like.query.filter_by(anime_mal_id=mal_id, is_like=False).count()
    comments = Comment.query.filter_by(anime_id=mal_id).all()
    
    return render_template('anime-details.html', 
                           anime_data=anime, 
                           comments=comments,
                           initial_likes=initial_likes,
                           initial_dislikes=initial_dislikes,
                           recommendations=recommendations)

@app.route('/anime/<int:mal_id>/add_comment', methods=['POST'])
@login_required
def add_comment(mal_id):
    comment_text = request.form['comment_text']
    new_comment = Comment(text=comment_text, anime_id=mal_id, author=current_user)
    db.session.add(new_comment)
    db.session.commit()
    return redirect(url_for('anime_details', mal_id=mal_id))

@app.route('/anime/<int:mal_id>/vote', methods=['POST'])
@login_required
def vote(mal_id):
    data = request.get_json()
    is_like_vote = data['is_like']
    existing_vote = Like.query.filter_by(user_id=current_user.id, anime_mal_id=mal_id).first()
    if existing_vote:
        if existing_vote.is_like == is_like_vote:
            db.session.delete(existing_vote)
        else:
            existing_vote.is_like = is_like_vote
    else:
        new_vote = Like(user_id=current_user.id, anime_mal_id=mal_id, is_like=is_like_vote)
        db.session.add(new_vote)
    db.session.commit()
    like_count = Like.query.filter_by(anime_mal_id=mal_id, is_like=True).count()
    dislike_count = Like.query.filter_by(anime_mal_id=mal_id, is_like=False).count()
    return {'success': True, 'likes': like_count, 'dislikes': dislike_count}

@app.route('/comment/<int:comment_id>/like', methods=['POST'])
@login_required
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment.id).first()
    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = CommentLike(user_id=current_user.id, comment_id=comment.id)
        db.session.add(new_like)
    db.session.commit()
    return {'success': True, 'likes': len(comment.likes)}

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author.id != current_user.id:
        flash('You are not authorized to delete this comment.', 'error')
        return redirect(url_for('anime_details', mal_id=comment.anime_id))
    anime_id_redirect = comment.anime_id
    db.session.delete(comment)
    db.session.commit()
    flash('Your comment has been deleted.', 'success')
    return redirect(url_for('anime_details', mal_id=anime_id_redirect))

@app.route('/browse')
def browse_genres():
    genres = []
    try:
        response = requests.get("https://api.jikan.moe/v4/genres/anime")
        response.raise_for_status()
        genres = response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        flash(f"Could not load genres from the API: {e}", "error")
    return render_template('browse.html', genres=genres)

@app.route('/genre/<int:genre_id>/<genre_name>')
def genre_results(genre_id, genre_name):
    results = []
    try:
        response = requests.get(f"https://api.jikan.moe/v4/anime?genres={genre_id}&limit=24")
        response.raise_for_status()
        results = response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        flash(f"Could not load anime for this genre: {e}", "error")
    
    return render_template('search_results.html', results=results, query=genre_name)

if __name__ == '__main__':
    app.run(debug=True)