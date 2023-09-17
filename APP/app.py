from flask import Flask, render_template, request, session
import openai
import mysql.connector
import hashlib
import random
from config import MYSQL_CONFIG, OPENAI_API_KEY, CHATGPT_MODEL, SECRET_KEY, MODEL_TEMP, MAX_TOKENS, STOP_PROMPT

app = Flask(__name__)
app.secret_key = SECRET_KEY

openai.api_key = OPENAI_API_KEY

# Connect to MySQL database
mysql_connection = mysql.connector.connect(**MYSQL_CONFIG)
mysql_cursor = mysql_connection.cursor()

messages = []
initial_system_message = "Hello! I'm Practy, your personal assistant. I can help you with your daily tasks. "
conversation_id = 0

# Function to select a persona based on persona_id
def persona_select(persona_id):
    persona_paths = {
        "0": "/Users/melihbulut/Documents/PractyAI WebApp/APP/Personas/Practy.txt",
        "1": "/Users/melihbulut/Documents/PractyAI WebApp/APP/Personas/Businessman.txt",
        "2": "/Users/melihbulut/Documents/PractyAI WebApp/APP/Personas/Teacher.txt",
        "3": "/Users/melihbulut/Documents/PractyAI WebApp/APP/Personas/Student.txt",
        "4": "/Users/melihbulut/Documents/PractyAI WebApp/APP/Personas/Athlete.txt",
        "5": "/Users/melihbulut/Documents/PractyAI WebApp/APP/Personas/Singer.txt",
    }

    try:    
        path = persona_paths[persona_id]
        with open(path, "r", encoding="utf-8") as persona_file:
            persona = persona_file.read()
            print(f"Persona selected: {persona_id}")  # Debug statement
            return persona

    except KeyError:
        return f"Persona '{persona_id}' not found in persona_paths."

    except FileNotFoundError:
        return f"Persona file for '{persona_id}' not found."

    except Exception as e:
        return f"An error occurred while loading the persona: {str(e)}"

# Function to generate a unique conversation ID
def create_conversation_id():
    random_num = random.randint(0, 100000)
    conversation_id = hashlib.md5((str(random_num).encode())).hexdigest()
    query = "SELECT * FROM conversationlog WHERE conversation_id = %s"
    values = (conversation_id,)
    mysql_cursor.execute(query, values)
    result = mysql_cursor.fetchone()
    if result:
        print(f"Generated conversation_id '{conversation_id}' already exists. Generating a new one.")  # Debug statement
        return create_conversation_id()
    else:
        return conversation_id

# Function to generate a token based on user ID and conversation ID
def token(userid, conversation_id):
    random_num = random.randint(0, 100000)
    token = hashlib.md5((userid + conversation_id + str(random_num)).encode()).hexdigest()
    return token

# Function to log the conversation in the database
def log_conversation(user_id, system_message, user_message, bot_answer, conversation_id):
    query = "INSERT INTO conversationlog (userid, systemmessage, usermessage, botsanswer,conversation_id) " \
            "VALUES (%s, %s, %s, %s, %s)"
    values = (user_id, system_message, user_message, bot_answer, conversation_id)
    mysql_cursor.execute(query, values)
    mysql_connection.commit()
    print("Conversation logged successfully.")  # Debug statement

# Function to process the user's message
def process_user_message(user_id, user_message, conversation_id, persona_id):

    # Add the user's message
    messages.append({"role": "user", "content": user_message})

    chat = openai.ChatCompletion.create(
        model=CHATGPT_MODEL,
        messages=messages,
        temperature=MODEL_TEMP,
        max_tokens=MAX_TOKENS,
        stop=STOP_PROMPT
    )
    bot_answer = chat.choices[0].message.content
    messages[-1]["role"] = "user"
    messages.append({"role": "assistant", "content": bot_answer})

    return bot_answer


@app.route('/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_id = request.form['user_id']
        user_message = request.form['user_message']
        persona_id = request.form['persona_id']

        # Generate or retrieve the conversation_id
        conversation_id = create_conversation_id()

        # Initialize the system message based on persona
        initial_system_message = persona_select(persona_id)
        messages.append({"role": "system", "content": initial_system_message})

        bot_answer = process_user_message(user_id, user_message, conversation_id, persona_id)

        # Log the initial system message
        log_conversation(user_id, initial_system_message, user_message, bot_answer, conversation_id)

        # Generate the token
        token_value = token(user_id, conversation_id)

        return render_template('index.html', user_id=user_id, user_message=user_message, bot_answer=bot_answer, token=token_value)

    return render_template('index.html', user_id=None, user_message=None)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8443, ssl_context="adhoc")
