from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import jwt
from datetime import timedelta, datetime
from app.models import User, MealPlan, WorkoutPlan, UserProgress, Exercise, Recipe, db
from app.utils import calculate_bmr, calculate_tdee, calculate_calories, generate_meal_plan, generate_workout_plan, calculate_bju
import re
import logging

# логирование
logging.basicConfig(level=logging.DEBUG)

bp = Blueprint('routes', __name__)

SECRET_KEY = "your_secret_key_here"

# регистрация
@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    error_message, status_code = validate_user_data(data)
    if error_message:
        return jsonify({"msg": error_message}), status_code

    username = data['username'].strip()
    password = data['password']
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"msg": "Этот логин уже занят"}), 400

    try:
        new_user = User(
            username=username,
            password_hash=hashed_password,
            age=data['age'],
            weight=data['weight'],
            height=data['height'],
            activity_level=data['activity_level'],
            goal=data['goal'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            gender=data['gender'],
            diet_preference=data.get('diet_preference', None)
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"msg": "Пользователь успешно зарегистрирован"}), 201
    except Exception as e:
        return handle_db_commit_error(e)
    
# авторизация
@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if 'username' not in data or 'password' not in data:
        return jsonify({"msg": "Отсутствуют поля: username, password"}), 400

    username = data['username'].strip()
    password = data['password']

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"msg": "Неверные логин или пароль"}), 401

    try:
        access_token = create_jwt_token(user)
        return jsonify(access_token=access_token), 200
    except Exception as e:
        return jsonify({"msg": f"Ошибка при создании токена: {str(e)}"}), 500

# получение профиля
@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        return jsonify({"msg": "Пользователь не найден"}), 404

    bmr = calculate_bmr(user)
    tdee = calculate_tdee(user)
    daily_calories = calculate_calories(user)
    bju = calculate_bju(user)

    training_days = user.training_days.split(',') if user.training_days else []

    profile_data = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "age": user.age,
        "weight": user.weight,
        "height": user.height,
        "activity_level": user.activity_level,
        "goal": user.goal,
        "gender": user.gender,
        "diet_preference": user.diet_preference,
        "training_days": training_days,
        "bmr": bmr,
        "tdee": tdee,
        "daily_calories": daily_calories,
        "protein": bju["protein"],
        "fats": bju["fats"],
        "carbs": bju["carbs"]
    }
    return jsonify(profile_data), 200

# обновление профиля
@bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        return jsonify({"msg": "Пользователь не найден"}), 404

    data = request.get_json()

    try:
        update_user_profile(user, data)
        return jsonify({"msg": "Профиль успешно обновлен"}), 200
    except Exception as e:
        return handle_db_commit_error(e)

# смена пароля
@bp.route('/change-password', methods=['PUT'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        return jsonify({"msg": "Пользователь не найден"}), 404

    data = request.get_json()

    required_fields = ['current_password', 'new_password', 'confirm_new_password']
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return jsonify({"msg": f"Отсутствуют поля: {', '.join(missing_fields)}"}), 400

    current_password = data['current_password']
    new_password = data['new_password']
    confirm_new_password = data['confirm_new_password']

    if new_password != confirm_new_password:
        return jsonify({"msg": "Пароли не совпадают"}), 400

    if not check_password_hash(user.password_hash, current_password):
        return jsonify({"msg": "Неверный текущий пароль"}), 401

    hashed_new_password = generate_password_hash(new_password, method='pbkdf2:sha256')
    user.password_hash = hashed_new_password

    try:
        db.session.commit()
        return jsonify({"msg": "Пароль успешно изменен"}), 200
    except Exception as e:
        return handle_db_commit_error(e)

# получение плана питания
@bp.route('/meal-plan', methods=['GET'])
@jwt_required()
def get_meal_plan():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        return jsonify({"msg": "Пользователь не найден"}), 404

    today = datetime.utcnow().date()

    meal_plan = MealPlan.query.filter_by(user_id=user.id, date=today).all()

    if not meal_plan:
        meal_plan = generate_meal_plan(user)
        return jsonify(meal_plan), 200

    meal_plan_response = [meal.to_dict() for meal in meal_plan]

    return jsonify(meal_plan_response), 200

# получение плана тренировок
@bp.route('/workout-plan', methods=['GET'])
@jwt_required()
def get_workout_plan():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        logging.error(f"Пользователь с ID {user_id} не найден.")
        return jsonify({"msg": "Пользователь не найден"}), 404

    today = datetime.utcnow().date()

    today_day_name = today.strftime('%A')

    day_translation = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }
    today_day_name = day_translation[today_day_name]

    logging.debug(f"Получение плана тренировок для пользователя {user.username} на день: {today_day_name}")

    workout_plan_response = generate_workout_plan(user, today_day_name)

    logging.debug(f"Ответ после генерации плана тренировок: {workout_plan_response}")
    return jsonify(workout_plan_response), 200

# получение прогресса пользователя
@bp.route('/user-progress', methods=['GET'])
@jwt_required()
def get_user_progress():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        logging.error(f"Пользователь с ID {user_id} не найден.")
        return jsonify({"msg": "Пользователь не найден"}), 404

    logging.debug(f"Получение прогресса пользователя {user.username} за {datetime.utcnow().date()}.")

    user_progress = UserProgress.query.filter_by(user_id=user.id, date=datetime.utcnow().date()).first()

    if not user_progress:
        logging.info(f"Прогресс для пользователя {user.username} за {datetime.utcnow().date()} не найден, создаем новый.")
        user_progress = UserProgress(
            user_id=user.id,
            date=datetime.utcnow().date(),
            total_calories_consumed=0,
            total_calories_burned=0,
            workouts_completed=0,
            total_protein_consumed=0,
            total_carbs_consumed=0,
            total_fats_consumed=0,
        )
        db.session.add(user_progress)
        db.session.commit()

    meal_plans = MealPlan.query.filter_by(user_id=user.id, date=datetime.utcnow().date(), eaten=True).all()

    total_calories = sum([meal.calories for meal in meal_plans])
    total_protein = sum([meal.protein for meal in meal_plans])
    total_carbs = sum([meal.carbs for meal in meal_plans])
    total_fats = sum([meal.fats for meal in meal_plans])

    user_progress.total_calories_consumed = total_calories
    user_progress.total_protein_consumed = total_protein
    user_progress.total_carbs_consumed = total_carbs
    user_progress.total_fats_consumed = total_fats

    db.session.commit()

    progress_response = {
        "total_calories_consumed": user_progress.total_calories_consumed,
        "total_calories_burned": user_progress.total_calories_burned,
        "workouts_completed": user_progress.workouts_completed,
        "total_protein_consumed": user_progress.total_protein_consumed,
        "total_carbs_consumed": user_progress.total_carbs_consumed,
        "total_fats_consumed": user_progress.total_fats_consumed,
    }

    logging.info(f"Прогресс пользователя {user.username} за {datetime.utcnow().date()} успешно получен.")

    return jsonify(progress_response), 200

# ежедневный сброс прогресса
@bp.route('/user-progress', methods=['POST'])
@jwt_required()
def reset_user_progress():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        logging.error(f"Пользователь с ID {user_id} не найден.")
        return jsonify({"msg": "Пользователь не найден"}), 404

    logging.debug(f"Обнуление прогресса пользователя {user.username} за {datetime.utcnow().date()}.")

    user_progress = UserProgress.query.filter_by(user_id=user.id, date=datetime.utcnow().date()).first()

    if not user_progress:
        user_progress = UserProgress(
            user_id=user.id,
            date=datetime.utcnow().date(),
            total_calories_consumed=0,
            total_calories_burned=0,
            workouts_completed=0,
            total_protein_consumed=0,
            total_carbs_consumed=0,
            total_fats_consumed=0,
        )
        db.session.add(user_progress)
    else:
        user_progress.total_calories_consumed = 0
        user_progress.total_calories_burned = 0
        user_progress.workouts_completed = 0
        user_progress.total_protein_consumed = 0
        user_progress.total_carbs_consumed = 0
        user_progress.total_fats_consumed = 0

    db.session.commit()

    return jsonify({"msg": "Прогресс успешно обнулен"}), 200

# для пометки съеденного приема пищи
@bp.route('/meal-plan/mark-eaten', methods=['POST'])
@jwt_required()
def mark_meal_as_eaten():
    data = request.get_json()
    meal_plan_id = data.get('meal_plan_id')

    meal_plan = MealPlan.query.get(meal_plan_id)
    if not meal_plan:
        return jsonify({"msg": "План питания не найден"}), 404

    meal_plan.eaten = True
    db.session.commit()

    user_progress = UserProgress.query.filter_by(user_id=meal_plan.user_id, date=datetime.utcnow().date()).first()
    if user_progress:
        user_progress.total_calories_consumed += meal_plan.calories
    else:
        new_progress = UserProgress(
            user_id=meal_plan.user_id,
            date=datetime.utcnow().date(),
            total_calories_consumed=meal_plan.calories
        )
        db.session.add(new_progress)

    db.session.commit()

    return jsonify({"msg": "Прием пищи отмечен как съеденный"}), 200

# для пометки выполненной тренировки
@bp.route('/workout-plan/mark-completed', methods=['POST'])
@jwt_required()
def mark_workout_as_completed():
    data = request.get_json()
    workout_plan_id = data.get('workout_plan_id')

    workout_plan = WorkoutPlan.query.get(workout_plan_id)
    if not workout_plan:
        return jsonify({"msg": "План тренировки не найден"}), 404

    if workout_plan.completed:
        return jsonify({"msg": "Тренировка уже завершена."}), 400

    workout_plan.completed = True
    db.session.commit()

    user_progress = UserProgress.query.filter_by(user_id=workout_plan.user_id, date=datetime.utcnow().date()).first()
    if user_progress:
        user_progress.total_calories_burned += workout_plan.duration * 10
        user_progress.workouts_completed += 1 
    else:
        new_progress = UserProgress(
            user_id=workout_plan.user_id,
            date=datetime.utcnow().date(),
            total_calories_burned=workout_plan.duration * 10,
            workouts_completed=1
        )
        db.session.add(new_progress)

    db.session.commit()

    return jsonify({"msg": "Тренировка помечена как завершенная"}), 200

# установка тренировочных дней
@bp.route('/workout-plan/set-days', methods=['POST'])
@jwt_required()
def set_workout_days():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    if not user:
        logging.error(f"Пользователь с ID {user_id} не найден.")
        return jsonify({"msg": "Пользователь не найден"}), 404

    data = request.get_json()
    training_days = data.get("training_days")

    logging.debug(f"Получены дни тренировок от пользователя {user.username}: {training_days}")

    if user.activity_level == "низкая" and len(training_days) != 2:
        logging.error(f"Для низкой активности пользователя {user.username} выбрано {len(training_days)} дня(ей). Ожидается 2 дня.")
        return jsonify({"msg": "Для низкой активности выберите 2 дня для тренировок."}), 400
    elif user.activity_level == "средняя" and len(training_days) != 3:
        logging.error(f"Для средней активности пользователя {user.username} выбрано {len(training_days)} дня(ей). Ожидается 3 дня.")
        return jsonify({"msg": "Для средней активности выберите 3 дня для тренировок."}), 400
    elif user.activity_level == "высокая" and len(training_days) != 5:
        logging.error(f"Для высокой активности пользователя {user.username} выбрано {len(training_days)} дня(ей). Ожидается 5 дней.")
        return jsonify({"msg": "Для высокой активности выберите 5 дней для тренировок."}), 400

    user.training_days = ', '.join(training_days)
    db.session.commit()

    logging.info(f"Дни тренировок для пользователя {user.username} успешно обновлены: {user.training_days}")

    return jsonify({"msg": "Дни тренировок обновлены"}), 200

# получение инструкции по приготовлению рецепта
@bp.route('/recipe-instruction/<int:recipe_id>', methods=['GET'])
@jwt_required()
def get_recipe_instruction(recipe_id):
    recipe = Recipe.query.get(recipe_id)
    
    if not recipe:
        return jsonify({"msg": "Рецепт не найден"}), 404

    return jsonify({
        "recipe_name": recipe.name,
        "cooking_instructions": recipe.cooking_instructions
    }), 200

# получение инструкции по выполнению упражнения
@bp.route('/exercise-instruction/<int:exercise_id>', methods=['GET'])
@jwt_required()
def get_exercise_instruction(exercise_id):
    exercise = Exercise.query.get(exercise_id)
    
    if not exercise:
        return jsonify({"msg": "Упражнение не найдено"}), 404

    return jsonify({
        "exercise_name": exercise.name,
        "execution_instructions": exercise.execution_instructions
    }), 200


# проверка токена
@bp.route('/api/check-token', methods=['GET'])
def check_token():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Токен отсутствует"}), 400
    
    if not is_valid_token(token):
        return jsonify({"error": "Недействительный токен"}), 401
    
    return jsonify({"message": "Токен действителен"}), 200

def is_valid_token(token):
    try:
        if token.startswith("Bearer "):
            token = token[7:]

        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

        if decoded_token and decoded_token.get("exp") > datetime.utcnow().timestamp():
            return True
        return False
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False

# валидация
def validate_user_data(data):
    required_fields = ['username', 'password', 'confirm_password', 'age', 'weight', 'height', 'activity_level', 'goal', 'first_name', 'last_name', 'gender']
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return f"Отсутствуют поля: {', '.join(missing_fields)}", 400

    if re.search('[а-яА-Я]', data['username']):
        return "Логин не может содержать русские буквы", 400

    if data['password'] != data['confirm_password']:
        return "Пароли не совпадают", 400

    if len(data['password']) < 6:
        return "Пароль должен содержать минимум 6 символов", 400

    try:
        age = int(data['age'])
        if age < 1 or age > 100:
            return "Возраст должен быть от 1 до 100 лет", 400
    except ValueError:
        return "Некорректное значение возраста", 400

    if not data['first_name'].istitle():
        return "Имя должно начинаться с заглавной буквы", 400
    if not data['last_name'].istitle():
        return "Фамилия должна начинаться с заглавной буквы", 400

    try:
        weight = float(data['weight'])
        if weight < 1 or weight > 500:
            return "Вес должен быть от 1 до 500 кг", 400
    except ValueError:
        return "Некорректное значение веса", 400

    try:
        height = float(data['height'])
        if height < 50 or height > 250:
            return "Рост должен быть от 50 до 250 см", 400
    except ValueError:
        return "Некорректное значение роста", 400

    return None, None

# обработка ошибок
def handle_db_commit_error(e):
    db.session.rollback()
    return jsonify({"msg": f"Ошибка при обработке данных: {str(e)}"}), 500

# создание токена
def create_jwt_token(user):
    return create_access_token(
        identity=user.id,
        additional_claims={
            "age": user.age,
            "weight": user.weight,
            "height": user.height,
            "activity_level": user.activity_level,
            "goal": user.goal
        },
        expires_delta=timedelta(days=3)
    )

def get_user_profile(user_id):
    return User.query.get(user_id)

def update_user_profile(user, data):
    for field, value in data.items():
        setattr(user, field, value)
    db.session.commit()