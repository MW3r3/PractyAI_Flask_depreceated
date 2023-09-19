import hashlib
import random

import mysql.connector
import openai
from flask import Flask, render_template, request
from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType,
    Collection, utility
)

from config import MYSQL_CONFIG, OPENAI_API_KEY

app = Flask(__name__)

mysql_connection = mysql.connector.connect(**MYSQL_CONFIG)
mysql_cursor = mysql_connection.cursor()

openai.api_key = OPENAI_API_KEY

messages = []

connections.connect("default", host="localhost", port="19530")

fields = [
    FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="embeddings", dtype=DataType.FLOAT_VECTOR, dim=1536)
]
schema = CollectionSchema(fields, "vdb for PractyAI")
vdb = Collection("practyai_vdb", schema)
index_params = {
  "metric_type":"L2",
  "index_type":"IVF_FLAT",
  "params":{"nlist":1024}
}
vdb.create_index(
  field_name="embeddings",
  index_params=index_params
)

vdb.load()

def insert_to_vdb(embedding):
    global vdb
    entities = [
        [embedding]
    ]
    insert_result = vdb.insert(entities)
    print("successfully inserted into vector database")
    return insert_result


def query_vector_from_vdb(embedding):
    search_params = {"metric_type": "L2", "params": {"nprobe": 20}}
    results = vdb.search(
        data=[embedding],
        anns_field="embeddings",
        param=search_params,
        limit=20,
        expr=None,
        consistency_level="Strong"
    )
    message_ids = results[0].ids
    return message_ids


def fetch_and_process_messages(message_ids):
    global messages

    for message_id in message_ids:
        result = get_message_from_sql(message_id)
        if result is not None:
            user_message, bot_answer = result
            messages.append({"role": "user", "content": user_message})
            messages.append({"role": "assistant", "content": bot_answer})
            print(f"Fetched and added message with ID {message_id} to messages list.")
        else:
            print(f"Message with ID {message_id} not found in the database.")


def get_embedding_from_openai(message):
    response = openai.Embedding.create(
        engine="text-embedding-ada-002",
        input=message
    )
    print("successfully fetched embedding from OpenAI")
    embedding_list = response['data'][0]['embedding']
    embedding_float_list = []
    for double_value in embedding_list:
        float_value = float(double_value)  # Convert each double value to float
        embedding_float_list.append(float_value)  # Append the float value to the new list
    return embedding_float_list


def process_user_message(user_id, user_message, persona_text, conversation_id):
    global messages
    str(persona_text)
#    system_message = {"role": "system", "content": persona_text}
#    messages.append(system_message)
    messages.append({"role": "user", "content": user_message})
    chat = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.5,
        max_tokens=100,
    )
    bot_answer = chat.choices[0].message.content
    messages.append({"role": "assistant", "content": bot_answer})
    print("successfully fetched bot_answer from OpenAI")
    log_conversation(user_id, user_message, bot_answer, conversation_id, persona_text)

    return bot_answer


def log_conversation(user_id, user_message, bot_answer, conversation_id, persona_text):
    query = "INSERT INTO conversation_log (user_id, system_message, user_message, bot_answer, conversation_id) " \
            "VALUES (%s, %s, %s, %s, %s)"
    values = (int(user_id), str(persona_text), str(user_message), str(bot_answer), str(conversation_id))
    mysql_cursor.execute(query, values)
    mysql_connection.commit()
    print("Conversation logged successfully.")


def get_message_from_sql(message_id):
    query = "SELECT user_message, bot_answer FROM conversation_log WHERE message_id = %s"
    values = (message_id,)
    mysql_cursor.execute(query, values)
    result = mysql_cursor.fetchone()
    if result:
        return result[0], result[1]
    else:
        print("Can't find message with specified id")


def create_token():
    random_num = random.randint(0, 100000)
    token = hashlib.md5((str(random_num).encode())).hexdigest()
    query = "SELECT * FROM tokens WHERE token = %s"
    values = (token,)
    mysql_cursor.execute(query, values)
    result = mysql_cursor.fetchone()
    if result:
        return create_token()
    else:
        return token


def create_conversation_id():
    rng = random.randint(0, 100000)
    conversation_id = hashlib.md5((str(rng).encode())).hexdigest()
    query = "SELECT * FROM conversation_log WHERE conversation_id = %s"
    values = (conversation_id,)
    mysql_cursor.execute(query, values)
    result = mysql_cursor.fetchone()
    if result:
        print(
            f"Generated conversation_id '{conversation_id}' already exists. Generating a new one.")
        return create_conversation_id()
    else:
        return conversation_id


def select_persona(persona_id):
    query = "SELECT persona_text FROM personas WHERE persona_id = %s"
    values = (persona_id,)
    mysql_cursor.execute(query, values)
    persona_text = mysql_cursor.fetchone()
    return persona_text


def get_spellcheck_from_openai(user_message):
    response = openai.Completion.create(
        engine="text-curie-001",
        prompt=("Check and fix the grammar of following sentence:" + user_message),
        temperature=0.1,
    )
    fixed_user_message = response['choices'][0]['text']
    return fixed_user_message


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_id = request.form['user_id']
        user_message = request.form['user_message']
        persona_id = request.form['persona_id']
        conversation_id = create_conversation_id()
        create_token()
        persona_text = select_persona(persona_id)
        embedding = get_embedding_from_openai(user_message)
        insert_to_vdb(embedding)
        message_ids = query_vector_from_vdb(embedding)

        fetch_and_process_messages(message_ids)

        bot_answer = process_user_message(user_id, user_message, persona_text, conversation_id)

        return render_template('index.html', user_id=user_id, user_message=user_message,
                               bot_answer=bot_answer, conversation_id=conversation_id)
    else:
        return render_template('index.html', user_id=None, user_message=None, persona_id=None)


if __name__ == "__main__":
    app.run(debug=True)
