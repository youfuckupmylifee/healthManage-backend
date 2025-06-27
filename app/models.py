from .extensions import db

# модель для пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    height = db.Column(db.Float, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    activity_level = db.Column(db.String(20), nullable=False)
    diet_preference = db.Column(db.String(50), nullable=True)
    goal = db.Column(db.String(20), nullable=False)
    training_days = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<Пользователь {self.username}>'

# модель для рецептов
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    protein = db.Column(db.Integer, nullable=False)
    carbs = db.Column(db.Integer, nullable=False)
    fats = db.Column(db.Integer, nullable=False)
    diet = db.Column(db.String(50), nullable=False)
    cooking_instructions = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Рецепт {self.name}>'

# модель для упражнений
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    intensity = db.Column(db.String(20), nullable=False)
    calories_burned_per_minute = db.Column(db.Float, nullable=False)
    execution_instructions = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Упражнение {self.name}>'


# модель для плана питания
class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(50), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    protein = db.Column(db.Integer, nullable=False)
    carbs = db.Column(db.Integer, nullable=False)
    fats = db.Column(db.Integer, nullable=False)
    eaten = db.Column(db.Boolean, default=False)

    recipe = db.relationship('Recipe', backref='meal_plans')
    user = db.relationship('User', backref='meal_plans')

    def to_dict(self):
        return {
            'id': self.id,
            'meal_type': self.meal_type,
            'recipe': self.recipe.name,
            'calories': self.calories,
            'protein': self.protein,
            'carbs': self.carbs,
            'fats': self.fats,
            'eaten': self.eaten
        }

    def __repr__(self):
        return f'<План питания {self.meal_type} для пользователя {self.user_id}>'

# модель для плана тренировок
class WorkoutPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    intensity = db.Column(db.String(20), nullable=False)
    completed = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='workout_plans')
    exercise = db.relationship('Exercise', backref='workout_plans')

    def to_dict(self):
        return {
            'id': self.id,
            'workout_type': self.exercise.name,
            'duration': self.duration,
            'intensity': self.intensity,
            'completed': self.completed
        }

    def __repr__(self):
        return f'<Тренировка {self.exercise.name} для пользователя {self.user_id}>'

# модель для прогресса пользователя
class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_calories_consumed = db.Column(db.Integer, nullable=False, default=0)
    total_calories_burned = db.Column(db.Integer, nullable=False, default=0)
    workouts_completed = db.Column(db.Integer, nullable=False, default=0)
    total_protein_consumed = db.Column(db.Integer, nullable=False, default=0)
    total_carbs_consumed = db.Column(db.Integer, nullable=False, default=0)
    total_fats_consumed = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship('User', backref='progress')

    def __repr__(self):
        return f'<Прогресс пользователя {self.user_id} за {self.date}>'