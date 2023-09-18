import openai
import pinecone

# Step 1: Set up OpenAI and Pinecone with your API keys
openai.api_key = "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"
pinecone_api_key = '5c903a3b-5b76-40e5-bbdc-dfa0e627cfc2'
pinecone_index_name = "test-index"

# Step 2: Initialize a Pinecone client
pinecone.init(api_key=pinecone_api_key)

# Step 3: Get user input
user_input = input("Enter a message: ")

# Step 4: Generate embeddings using OpenAI for the user input
response = openai.Embedding.create(
    engine="text-embedding-ada-002",
    input=user_input
    )

user_embedding = response['data'][0]['embedding']

# Step 5: Store the user's embedding in Pinecone
index = pinecone.Index(index_name=pinecone_index_name)

# Create a list with the user's embedding
user_data = [{"id": "user", "vector": user_embedding}]

# Upload the user's data to Pinecone
index.upsert(items=user_data)

# Wait for the data to be indexed (optional)
index.wait_operations()

# Close the Pinecone index when done
index.close()

print("User data uploaded and indexed successfully!")
