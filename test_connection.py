import ollama

# Gaz's server IP
GAZ_IP = 'http://172.18.254.36:11434'
client = ollama.Client(host=GAZ_IP)

print("Pinging Gaz's AI server across the network...")

try:
    response = client.chat(model='llama3.2', messages=[
        {'role': 'user', 'content': 'Say "Backend Online" in two words.'}
    ])
    print("\nSUCCESS! Response from Gaz's PC:", response['message']['content'])
except Exception as e:
    print("\nConnection failed. Make sure Gaz's 'ollama serve' window is still open and the IP is correct.")
    print("Error details:", e)