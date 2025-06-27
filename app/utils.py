from app.models import Recipe, MealPlan, WorkoutPlan, Exercise, db
import random
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.DEBUG)

# функция для расчета BMR
def calculate_bmr(user):
    if user.gender == 'male':
        return 10 * user.weight + 6.25 * user.height - 5 * user.age + 5
    else:
        return 10 * user.weight + 6.25 * user.height - 5 * user.age - 161

# функция для расчета TDEE
def calculate_tdee(user):
    activity_multiplier = {
        "низкая": 1.2,
        "средняя": 1.55,
        "высокая": 1.9
    }
    return calculate_bmr(user) * activity_multiplier.get(user.activity_level, 1.2)

# функция для расчета калорий
def calculate_calories(user):
    tdee = calculate_tdee(user)
    if user.goal == 'похудение':
        return tdee - 500
    elif user.goal == 'набор массы':
        return tdee + 500
    else:
        return tdee

# функция для расчета БЖУ
def calculate_bju(user):
    tdee = calculate_tdee(user)
    protein = (tdee * 0.30) / 4
    fats = (tdee * 0.25) / 9
    carbs = (tdee * 0.45) / 4

    return {
        "protein": round(protein, 0),
        "fats": round(fats, 0),
        "carbs": round(carbs, 0)
    }

# фильтрация рецептов по предпочтениям пользователя
def filter_recipes(user):
    filters = []
    
    if user.diet_preference == "вегетарианский":
        filters.append(Recipe.diet == "вегетарианский")
    elif user.diet_preference == "веганский":
        filters.append(Recipe.diet == "веганский")
    elif user.diet_preference == "безглютеновый":
        filters.append(Recipe.diet == "безглютеновый")

    if filters:
        return Recipe.query.filter(*filters).all()
    else:
        return Recipe.query.all()

# генерация плана питания
def generate_meal_plan(user):
    filtered_recipes = filter_recipes(user)
    if not filtered_recipes:
        return {"msg": "Нет доступных рецептов для выбранной диеты. Пожалуйста, добавьте рецепты в базу данных."}

    daily_calories = calculate_calories(user)
    bju = calculate_bju(user)

    meals = {
        "завтрак": daily_calories * 0.25,
        "обед": daily_calories * 0.35,
        "ужин": daily_calories * 0.25,
        "перекус": daily_calories * 0.15
    }

    meal_plan = []
    for meal, calories in meals.items():
        selected_recipe = random.choice(filtered_recipes)

        protein = (selected_recipe.protein / selected_recipe.calories) * calories
        fats = (selected_recipe.fats / selected_recipe.calories) * calories
        carbs = (selected_recipe.carbs / selected_recipe.calories) * calories

        if user.goal == 'похудение':
            protein = min(protein, bju['protein'])
            fats = min(fats, bju['fats'])
            carbs = min(carbs, bju['carbs'])
        elif user.goal == 'набор массы':
            protein = max(protein, bju['protein'])
            fats = max(fats, bju['fats'])
            carbs = max(carbs, bju['carbs'])

        meal_plan_entry = MealPlan(
            user_id=user.id,
            date=datetime.utcnow().date(),
            meal_type=meal,
            recipe_id=selected_recipe.id,
            calories=calories,
            protein=round(protein, 0),
            carbs=round(carbs, 0),
            fats=round(fats, 0)
        )

        meal_plan_entry.cooking_instructions = selected_recipe.cooking_instructions
        meal_plan.append(meal_plan_entry)

    db.session.add_all(meal_plan)
    db.session.commit()

    return {"msg": "План питания успешно сгенерирован", "meal_plan": [meal.to_dict() for meal in meal_plan]}

# генерация плана тренировок
def generate_workout_plan(user, target_day):
    workout_plan = []

    if not user.training_days:
        logging.error("Ошибка: пользователю не заданы дни тренировок.")
        return {"msg": "Пожалуйста, выберите дни недели для тренировок."}

    logging.debug(f"Пользователь {user.username} выбрал дни для тренировок: {user.training_days}")

    days_of_week = user.training_days.split(', ')

    exercise_filters = []
    if user.goal == "похудение":
        exercise_filters.append(Exercise.intensity.in_(['средняя', 'высокая']))
    elif user.goal == "набор массы":
        exercise_filters.append(Exercise.intensity == 'высокая')
    else:
        exercise_filters.append(Exercise.intensity.in_(['средняя', 'низкая']))

    exercises = Exercise.query.filter(*exercise_filters).all()

    logging.debug(f"Найдено {len(exercises)} доступных упражнений для выбранной цели.")

    if not exercises:
        logging.error("Ошибка: Нет доступных упражнений для выбранной цели.")
        return {"msg": "Нет доступных упражнений для выбранной цели."}

    today = datetime.utcnow().date()
    logging.debug(f"Текущая дата: {today}")

    day_mapping = {
        'Понедельник': 0,
        'Вторник': 1,
        'Среда': 2,
        'Четверг': 3,
        'Пятница': 4,
        'Суббота': 5,
        'Воскресенье': 6
    }

    existing_workout_plan = WorkoutPlan.query.filter(
        WorkoutPlan.user_id == user.id,
        WorkoutPlan.date == today + timedelta(days=day_mapping.get(target_day))
    ).all()

    if existing_workout_plan:
        logging.debug(f"Тренировки для {target_day} уже существуют, возвращаем их.")
        return [workout.to_dict() for workout in existing_workout_plan]

    if target_day not in days_of_week:
        logging.debug(f"{target_day}: Сегодня отдыхаем")
        return [{"msg": f"Сегодня {target_day}, день отдыха."}]

    for _ in range(2):
        selected_exercise = random.choice(exercises)

        day_num = day_mapping.get(target_day)
        workout_plan_entry = WorkoutPlan(
            user_id=user.id,
            date=datetime.utcnow().date() + timedelta(days=day_num),
            exercise_id=selected_exercise.id,
            duration=selected_exercise.duration,
            intensity=selected_exercise.intensity,
            completed=False
        )

        workout_plan_entry.execution_instructions = selected_exercise.execution_instructions
        workout_plan.append(workout_plan_entry)

    logging.debug(f"Добавлено {len(workout_plan)} тренировок для дня {target_day}.")

    db.session.add_all(workout_plan)
    db.session.commit()

    logging.info(f"План тренировок для дня {target_day} успешно сгенерирован и сохранен в базе данных.")

    return [workout.to_dict() for workout in workout_plan]