from app.services.fallback import AIFallback


ai = AIFallback()

question = "Jelaskan apa itu Python secara singkat."

try:

    result = ai.chat(question)

    print("\n======================")
    print("MODEL :", result["model"])
    print("======================")
    print(result["content"])

except Exception as e:

    print("\n======================")
    print("SEMUA MODEL GAGAL")
    print("======================")
    print(e)

