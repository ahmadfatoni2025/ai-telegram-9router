from app.services.nine_router import NineRouter


router = NineRouter()

question = "Jelaskan apa itu Python dalam 2 kalimat."

try:
    answer = router.chat(question)

    print("\n===== AI =====")
    print(answer)

except Exception as e:
    print("\n===== ERROR =====")
    print(type(e).__name__, e)

