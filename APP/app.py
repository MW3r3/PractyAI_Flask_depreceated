from flask import Flask, render_template, request, session
import openai
import mysql.connector
import hashlib
import random
from config import MYSQL_CONFIG, OPENAI_API_KEY, CHATGPT_MODEL, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Connect to MySQL database
mysql_connection = mysql.connector.connect(**MYSQL_CONFIG)
mysql_cursor = mysql_connection.cursor()

# Initialize the messages list to store the conversation
messages = []
initial_system_message = "Hello! I'm Practy, your personal assistant. I can help you with your daily tasks. "

# Initialize conversation ID and message count
conversation_id = 0
msgcount = 0

# Function to get summarized texts from the database based on persona
def get_summarized_texts(user_id, persona_id):
    query = "SELECT summarized_text FROM summarized_messages WHERE user_id = %s AND persona_id = %s"
    values = (user_id, persona_id)
    mysql_cursor.execute(query, values)
    summarized_texts = mysql_cursor.fetchall()

    for summarized_text in summarized_texts:
        messages.append({"role": "system", "content": summarized_text[0]})

# Function to summarize the last 50 messages in the conversation
# Function to summarize the last 50 messages in the conversation
def sum_50(messages):
    global msgcount
    last_50_messages = messages[-5:]  # Get the last 50 messages

    # Extract and concatenate the content of the last 50 messages
    last_50_content = "\n".join([message['content'] for message in last_50_messages])

    response = openai.Completion.create(
        engine=babbage,
        prompt=last_50_content,
        max_tokens=20,  # Adjust max_tokens as needed for summary length
        n=1,
        stop=None,
        temperature=0.3
    )

    summarized_text = response.choices[0].text

    msgcount = 0
    return summarized_text


# Function to save summarized text to the database
def save_summarized_text(user_id, persona_id, summarized_text):
    query = "INSERT INTO summarized_messages (user_id, persona_id, summarized_text) " \
            "VALUES (%s, %s, %s)"
    values = (user_id, persona_id, summarized_text)
    mysql_cursor.execute(query, values)
    mysql_connection.commit()

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
        print(f"Persona '{persona_id}' not found in persona_paths.")  # Debug statement
        return f"Persona '{persona_id}' not found in persona_paths."

    except FileNotFoundError:
        print(f"Persona file for '{persona_id}' not found.")  # Debug statement
        return f"Persona file for '{persona_id}' not found."

    except Exception as e:
        print(f"An error occurred while loading the persona: {str(e)}")  # Debug statement
        return f"An error occurred while loading the persona: {str(e)}"

# Function to generate a unique conversation ID
def conid_create():
    random_num = random.randint(0, 100000)
    conversation_id = hashlib.md5((str(random_num).encode())).hexdigest()
    query = "SELECT * FROM conversationlog WHERE conversation_id = %s"
    values = (conversation_id,)
    mysql_cursor.execute(query, values)
    result = mysql_cursor.fetchone()
    if result:
        print(f"Generated conversation_id '{conversation_id}' already exists. Generating a new one.")  # Debug statement
        return conid_create()
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
# Function to process the user's message
def process_user_message(user_id, user_message, conversation_id, persona_id):
    global msgcount

    # Add the user's message
    messages.append({"role": "user", "content": user_message})

    chat = openai.ChatCompletion.create(
        model=CHATGPT_MODEL, messages=messages
    )
    bot_answer = chat.choices[0].message.content
    messages[-1]["role"] = "user"
    messages.append({"role": "assistant", "content": bot_answer})

    msgcount = msgcount + 1
    if msgcount == 5:
        summarized_text = sum_50(messages)
        save_summarized_text(user_id, conversation_id, summarized_text)

    # Get persona-specific summarized texts and add them to the messages list
    try:
        persona_summarized_texts = get_summarized_texts(user_id, persona_id)

        for persona_summarized_text in persona_summarized_texts:
            messages.append({"role": "assistant", "content": persona_summarized_text})
    except:
        pass        

    return bot_answer


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_id = request.form['user_id']
        user_message = request.form['user_message']
        persona_id = request.form['persona_id']

        # Check if conversation_id is already in the session
        if 'conversation_id' in session:
            conversation_id = session['conversation_id']
        else:
            conversation_id = conid_create()
            session['conversation_id'] = conversation_id  # Store conversation_id in the session

        # Check if user_id is already in the session
        if 'user_id' in session:
            user_id = session['user_id']
        else:
            session['user_id'] = user_id  # Store user_id in the session

        # Initialize the system message based on persona
        initial_system_message = persona_select(persona_id)
        messages.append({"role": "system", "content": initial_system_message})

        bot_answer = process_user_message(user_id, user_message, conversation_id, persona_id)

        # Log the initial system message
        log_conversation(user_id, initial_system_message, user_message, bot_answer, conversation_id)

        # Store token in the session (assuming you want to keep it)
        token_value = token(user_id, conversation_id)
        session['token'] = token_value

        return render_template('index.html', user_id=user_id, user_message=user_message, bot_answer=bot_answer, token=token_value)

    return render_template('index.html', user_id=None, user_message=None)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8443, ssl_context="adhoc")
