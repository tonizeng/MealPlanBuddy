from flask import Flask, render_template, request, redirect, url_for, session
import requests
from urllib.parse import unquote
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
import json


# SQL extension
db = SQLAlchemy()

# create the flask app
app = Flask(__name__, static_url_path='/static')

# secret key for session management
app.secret_key = "your_secret_key"  

# configure SQLLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"

migrate = Migrate(app, db)

# initialize the app with the extension
db.init_app(app)

# replace with your Spoonacular API key
API_KEY = '8b8ddfb40b074d15b422cba05279a1db'

# model for meal plan
class WeeklyMealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    week = db.Column(db.String(50))
    meal_content = db.Column(db.String(255))

    def __init__(self, user_id, week, meal_content):
        self.user_id = user_id
        self.week = week
        self.meal_content = meal_content

# model for user system
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)  
    last_name = db.Column(db.String(50), nullable=False)   
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    saved_recipes = db.relationship('SavedRecipe', backref='user', lazy=True)
    weekly_meal_plans = db.relationship('WeeklyMealPlan', backref='user', lazy=True)

# model for saved recipes
class SavedRecipe(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(255), nullable = False)
    instructions = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

def is_authenticated():
    return 'user_id' in session

# route for registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='sha256')

        new_user = User(first_name=first_name, last_name=last_name, username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')

# route for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')


        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            print("log in true")
            session['user_id'] = user.id
            return redirect(url_for('profile'))
        print("false")
    return render_template('login.html')

# route for profile
@app.route('/profile')
def profile():
    if 'user_id' in session:
        # user is logged in
        user = User.query.get(session['user_id'])
        username = user.username
        first_name = user.first_name
        last_name = user.last_name
        return render_template('profile.html',  user = user, username = username, first_name = first_name, last_name = last_name)
    else:
        return redirect(url_for('login'))

# route for updating user profile
@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if 'user_id' in session:
        user_id = session['user_id']
        user = User.query.get(user_id)

        if request.method == 'POST':
            new_first_name = request.form.get('first_name')
            new_last_name = request.form.get('last_name')

            # Update the user's first name and last name
            user.first_name = new_first_name
            user.last_name = new_last_name
            db.session.commit()

        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

# route for logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    # session.pop('logged_in', False)
    return redirect(url_for('login'))

# route for home
@app.route('/home', methods=['GET'])
def home():
    # render the main page with empty recipe list and search query
    return render_template('index.html', recipes=[], search_query='')

# main route for app
@app.route('/', methods=['GET', 'POST'])
def index():
    if is_authenticated():
        if request.method == 'POST':
            # if a form is submitted
            query = request.form.get('search_query', '')
            # perform a search for recipes with the given query
            recipes = search_recipes(query)
            # render the main page with the search results and the search query
            return render_template('index.html', recipes=recipes, search_query=query)
        
        # if it's a GET request or no form submitted
        search_query = request.args.get('search_query', '')
        decoded_search_query = unquote(search_query)
        # perform a search for recipes with the decoded search query
        recipes = search_recipes(decoded_search_query)
        # render the main page
        return render_template('index.html', recipes=recipes, search_query=decoded_search_query)
    else:
        return redirect(url_for('login'))

# function to search for recipes based on the provided query
def search_recipes(query):
    url = f'https://api.spoonacular.com/recipes/complexSearch'
    params = {
        'apiKey': API_KEY,
        'query': query,
        'number': 10,
        'instructionsRequired': True,
        'addRecipeInformation': True,
        'fillIngredients': True,
    }

    # send a GET request to the Spoonacular API with the query parameters
    response = requests.get(url, params=params)
    # if the API call is successful
    if response.status_code == 200:
        # parse the API response as JSON data
        data = response.json()
        # return the list of recipe results
        return data['results']
    # if the API call is not successful
    return []

# route to view a specific recipe with a given recipe ID
@app.route('/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    # get the search query from the URL query parameters
    search_query = request.args.get('search_query', '')
    # build the URL to get information about the specific recipe ID from Spoonacular API
    url = f'https://api.spoonacular.com/recipes/{recipe_id}/information'
    params = {
        'apiKey': API_KEY,
    }

    # send a GET request to the Spoonacular API to get the recipe information
    response = requests.get(url, params=params)
    # if the API call is successful
    if response.status_code == 200:
        recipe = response.json()
        # print(recipe)
        return render_template('view_recipe.html', recipe=recipe, search_query=search_query)
    return "Recipe not found", 404

# route to save recipe to database
@app.route('/save_recipe', methods=['POST'])
def save_recipe():
    if 'user_id' in session:
        user_id = session['user_id']
        recipe_id = request.form.get('recipe_id')

        url = f'https://api.spoonacular.com/recipes/{recipe_id}/information'
        params = {'apiKey': API_KEY}
        response = requests.get(url, params=params)

        if response.status_code == 200:
            try:
                recipe_data = response.json()
                saved_recipe = SavedRecipe(
                    id=recipe_id,
                    title=recipe_data['title'],
                    instructions=recipe_data['instructions'],
                    user_id=user_id
                )
                db.session.add(saved_recipe)
                db.session.commit()

                # Get the search query from the form or URL query parameters
                search_query = request.form.get('search_query') or request.args.get('search_query', '')
                # Redirect back to the main page with the search query
                return redirect(url_for('index', search_query=search_query))
            except Exception as e:
                print("Error:", e)
                return "Failed to save recipe"
        else:
            print("API Error:", response.status_code, response.text)
            return "Failed to fetch recipe details from the API"
    else:
        return redirect(url_for('login'))

# route to view saved recipes
@app.route('/saved_recipes', methods=['GET'])
def view_saved_recipes():
    if 'user_id' in session:
        user_id = session['user_id']
        saved_recipe_data = SavedRecipe.query.filter_by(user_id=user_id).all()
        return render_template('saved_recipes.html', saved_recipes=saved_recipe_data)
    else:
        return redirect(url_for('login'))

# route to view original recipe from the saved recipes
@app.route('/saved_recipe/<int:saved_recipe_id>/view_original', methods=['GET'])
def view_saved_recipe_original(saved_recipe_id):
    saved_recipe = SavedRecipe.query.get(saved_recipe_id)
    if saved_recipe:
        return view_recipe(saved_recipe.id)
    return "Recipe not found", 404

# route to delete recipe
@app.route('/delete_recipe/<int:saved_recipe_id>', methods=['POST', 'GET'])
def delete_recipe(saved_recipe_id):
    if request.method == 'POST':
        saved_recipe = SavedRecipe.query.get(saved_recipe_id)
    
        if saved_recipe:
            try:
                db.session.delete(saved_recipe)
                db.session.commit()
                return "Recipe deleted successfully"
            except Exception as e:
                print("Error:", e)
                return "Failed to delete recipe"
        else:
            return "Recipe not found", 404
    else:
        return view_recipe(saved_recipe_id)

# route to view meal plan
@app.route('/mealplan/<int:record_id>', methods=['GET', 'POST'])
@app.route('/mealplan', methods=['GET', 'POST'])
def mealplan(record_id=None):
    if is_authenticated():
        # get saved recipes information
        saved_recipes = SavedRecipe.query.filter_by(user_id=session['user_id']).all()

        # get past meal plan records for dropdown
        past_records = WeeklyMealPlan.query.filter_by(user_id=session['user_id']).all()
        # print(past_records)
        if record_id:
            record = WeeklyMealPlan.query.get(record_id)
            if record:
                record.meal_content = json.loads(record.meal_content)
        else:
            record = None

        past_records_data = []
        for past_record in past_records:

            past_record_data = {
                'id': past_record.id,
                'week': past_record.week,
                **json.loads(past_record.meal_content)
            }
            past_records_data.append(past_record_data)

        if request.method == 'POST':
            user_id = session.get('user_id')
            week = request.form.get('week')

            meal_content = {
                'sunday': request.form.get('meal_content_sunday'),
                'monday': request.form.get('meal_content_monday'),
                'tuesday': request.form.get('meal_content_tuesday'),
                'wednesday': request.form.get('meal_content_wednesday'),
                'thursday': request.form.get('meal_content_thursday'),
                'friday': request.form.get('meal_content_friday'),
                'saturday': request.form.get('meal_content_saturday'),
            }
            meal_content_json = json.dumps(meal_content)
            

            # check if a record with the same week name already exists for the user
            existing_record = WeeklyMealPlan.query.filter_by(user_id=user_id, week=week).first()

            if existing_record:
                # update the existing record
                existing_record.meal_content = meal_content_json
            else:
                # create a new record
                record = WeeklyMealPlan(user_id=user_id, week=week, meal_content=meal_content_json)
                db.session.add(record)

            db.session.commit()

            return redirect('/mealplan')

        return render_template('mealplan.html', record=record, saved_recipes=saved_recipes, past_records_data=past_records_data, past_records=past_records)
    else:
        return redirect(url_for('login'))

# run the app in debug mode if executed directly
if __name__ == '__main__':
    app.run(debug=True, port=5011)

