import json
import os

def get_questions(level, num_questions):
    filepath = f'data/{level}.json'
    if not os.path.exists(filepath):
        return []  

    with open(filepath, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    return questions[:num_questions]
