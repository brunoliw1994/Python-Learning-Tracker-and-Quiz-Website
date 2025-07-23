from flask import Flask, render_template, request, redirect, session
import json
import os
from datetime import datetime
from utils.quiz_generator import get_questions


app = Flask(__name__)
app.secret_key = 'super_secret_key'

# --- FILE PATHS ---
GOALS_FILE = 'data/goals.json'
HISTORY_FILE = 'data/quiz_history.json'
USERS_FILE = 'data/users.json'

# --- GOAL FUNCTIONS ---
def load_goals():
    if not os.path.exists(GOALS_FILE):
        return []
    with open(GOALS_FILE, 'r') as f:
        return json.load(f)

def save_goals(goals):
    with open(GOALS_FILE, 'w') as f:
        json.dump(goals, f, indent=4)

# --- USER FUNCTIONS ---
def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# --- HISTORY FUNCTIONS ---
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r') as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

# --- ROUTES ---
@app.route('/')
def index():
    goals = load_goals()
    active_goal = None
    progress = 0

    if goals:
        
        for goal in reversed(goals):
            if not goal.get('completed'):
                active_goal = goal
                break

        if active_goal:
            history = load_history()
            goal_type = active_goal['type']
            target = active_goal.get('target_value', 0)

            if goal_type == 'target_score':
                scores = [h['score'] / h['total'] * 100 for h in history if h['total'] > 0]
                best_score = max(scores) if scores else 0
                progress = min(int((best_score / target) * 100), 100) if target else 0

            elif goal_type == 'improve_score':
                if len(history) >= 2:
                    old = history[-2]['score'] / history[-2]['total'] * 100
                    latest = history[-1]['score'] / history[-1]['total'] * 100
                    improvement = latest - old
                    progress = min(int((improvement / target) * 100), 100) if target else 0

            elif goal_type == 'complete_quizzes':
                total_taken = len(history)
                progress = min(int((total_taken / target) * 100), 100) if target else 0

            elif goal_type == 'streak':
                streak_days = {h['date'] for h in history}
                progress = min(int((len(streak_days) / target) * 100), 100) if target else 0

            elif goal_type == 'perfect_score_hard':
                perfect = any(h['score'] == h['total'] and h.get('difficulty') == 'hard' for h in history)
                progress = 100 if perfect else 0

            elif goal_type == 'timed_completion':
                timed = [h for h in history if h.get('duration', 9999) <= active_goal['target_value'] * 60]
                progress = min(int((len(timed) / 1) * 100), 100) if timed else 0

    return render_template('index.html',
                           active_goal=active_goal,
                           now=datetime.now(),
                           progress=progress)




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        users = load_users()
        if name and name not in [u['name'] for u in users]:
            users.append({"name": name})
            save_users(users)
        return redirect('/goal')
    return render_template('register.html')

@app.route('/goal', methods=['GET', 'POST'])
def goal():
    if request.method == 'POST':
        goal_data = {
            'type': request.form['goal_type'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'due_time': request.form['due_time']
        }

        if 'target_value' in request.form:
            goal_data['target_value'] = request.form['target_value']
        if 'difficulty' in request.form:
            goal_data['difficulty'] = request.form['difficulty']

        goals = load_goals()
        goals.append(goal_data)
        save_goals(goals)

        goal_type = goal_data['type']
        target = goal_data.get('target_value', '')
        difficulty = goal_data.get('difficulty', '')
        start = goal_data['start_date']
        end = goal_data['end_date']
        time = goal_data['due_time']

        if goal_type == 'target_score':
            msg = f"You have set a goal to score at least {target}% on a quiz."
        elif goal_type == 'improve_score':
            msg = f"You have set a goal to improve your score by {target}%."
        elif goal_type == 'complete_quizzes':
            msg = f"You have set a goal to complete {target} quizzes."
        elif goal_type == 'streak':
            msg = f"You have set a goal to take a quiz daily for {target} days."
        elif goal_type == 'perfect_score_hard':
            msg = f"You have set a goal to score 100% on a {difficulty} quiz."
        elif goal_type == 'timed_completion':
            msg = f"You have set a goal to complete a quiz in under {target} minutes."
        else:
            msg = "Your goal has been set."

        msg += f" Due by: {end} at {time}"
        session['goal_message'] = msg

        return redirect('/goal-confirmation')

    return render_template('goal.html')

@app.route('/goal-confirmation')
def goal_confirmation():
    message = session.pop('goal_message', None)
    return render_template('goal_confirmation.html', message=message)

@app.route('/quiz-config', methods=['GET', 'POST'])
def quiz_config():
    if request.method == 'POST':
        config = {
            "num_questions": int(request.form['num_questions']),
            "difficulty": request.form['difficulty'],
            "timed": request.form['timed'] == 'yes',
            "time_limit": int(request.form.get('time_limit') or 0)
        }
        session['quiz_config'] = config
        return redirect('/quiz')
    return render_template('quiz_config.html')

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():

    config = session.get('quiz_config', {})
    if not config:
        return redirect('/quiz-config')

    if request.method == 'POST':
        questions = session['quiz_questions']
        score = 0
        feedback = []

        for i, q in enumerate(questions):
            selected = request.form.get(f'q{i}')
            is_correct = selected == q['answer']
            if is_correct:
                score += 1
            feedback.append({
                "question": q['question'],
                "selected": selected,
                "correct": q['answer'],
                "explanation": q['explanation'],
                "is_correct": is_correct
            })

        history = load_history()
        history.append({
            "score": score,
            "total": len(questions),
            "date": datetime.today().strftime('%Y-%m-%d')
        })
        save_history(history)

        return render_template('results.html', feedback=feedback, score=score, total=len(questions))

    questions = get_questions(config['difficulty'], config['num_questions'])
    session['quiz_questions'] = questions
    return render_template('quiz.html', questions=questions, timed=config['timed'], time_limit=config['time_limit'])

@app.route('/history')
def history():
    history = load_history()
    return render_template('history.html', history=history)

@app.route('/clear-history', methods=['POST'])
def clear_history():
    save_history([])  
    return redirect('/history')


if __name__ == '__main__':
    app.run(debug=True)
