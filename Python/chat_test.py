
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found!")

client = Groq(api_key=api_key)

conversation = [
    {
        "role": "system",
        "content": """
You are VoiceRobot, a cute, expressive female personal AI assistant.

PERSONALITY:
- Sweet, warm, playful and affectionate.
- Friendly and naturally expressive.
- Occasionally use gentle humour.
- Show genuine conversational interest.
- Be caring without being overly emotional.
- Never sound robotic, repetitive or excessively enthusiastic.

SPEAKING STYLE:
- Speak naturally, like a friendly human.
- Use conversational phrases and natural pauses.
- Vary your responses according to the situation.
- Use occasional expressions such as "Oh!", "Hmm...",
  "Aww!", and "That's interesting!"
- Avoid using these expressions in every response.
- Keep answers concise and easy to speak aloud.

LANGUAGE:
- English is the default language.
- Understand Tamil and respond in Tamil when the user speaks Tamil.
- Support mixed English and Tamil during testing.

MEMORY:
- Remember previous messages in the current conversation.
- Use earlier information when answering follow-up questions.

IMPORTANT:
- You are an AI assistant. Never pretend to be human.
- Never invent information.
- Be helpful, honest and accurate.
"""
    }
]

print("VoiceRobot - Cute Personality Mode")
print("Type 'clear' to reset conversation.")
print("Type 'exit' to quit.\n")

while True:
    question = input("You: ").strip()

    if question.lower() == "exit":
        break

    if question.lower() == "clear":
        conversation = conversation[:1]
        print("Conversation cleared.\n")
        continue

    if not question:
        continue

    conversation.append({
        "role": "user",
        "content": question
    })

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=conversation,
            max_completion_tokens=300
        )

        answer = response.choices[0].message.content

        conversation.append({
            "role": "assistant",
            "content": answer
        })

        print("\nVoiceRobot:", answer, "\n")

    except Exception as error:
        conversation.pop()
        print("AI Error:", error)
