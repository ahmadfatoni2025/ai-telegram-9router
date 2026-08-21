import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv()

NINE_ROUTER_URL = os.getenv(
    "NINE_ROUTER_URL"
)

NINE_ROUTER_API_KEY = os.getenv(
    "NINE_ROUTER_API_KEY"
)

MODELS = [
    os.getenv("FUSION_MODEL_1"),
    os.getenv("FUSION_MODEL_2"),
    os.getenv("FUSION_MODEL_3"),
]

SYNTHESIS_MODEL = os.getenv(
    "SYNTHESIS_MODEL"
)


def call_model(model, user_message):

    payload = {
        "model": model,

        "messages": [
            {
                "role": "system",
                "content": (
                    "Jawab pertanyaan pengguna "
                    "secara akurat dan teknis. "
                    "Berikan solusi terbaik."
                )
            },
            {
                "role": "user",
                "content": user_message
            }
        ],

        "stream": False
    }

    response = requests.post(
        NINE_ROUTER_URL,

        headers={
            "Authorization":
                f"Bearer {NINE_ROUTER_API_KEY}",

            "Content-Type":
                "application/json"
        },

        json=payload,

        timeout=180
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]


def ask_fusion(user_message):

    models = [
        model for model in [
            os.getenv("FUSION_MODEL_1", "ag/gemini-3.6-flash-low"),
            os.getenv("FUSION_MODEL_2", "ag/gemini-3.6-flash-medium"),
            os.getenv("FUSION_MODEL_3", "ag/gemini-3.7-flash-low"),
        ] if model
    ]

    synthesis_model = os.getenv(
        "SYNTHESIS_MODEL",
        "ag/gemini-3.6-flash-low"
    )

    results = {}
    valid_answers = {}

    # Jalankan beberapa model secara paralel
    with ThreadPoolExecutor(
        max_workers=max(len(models), 1)
    ) as executor:

        futures = {
            executor.submit(
                call_model,
                model,
                user_message
            ): model

            for model in models
            if model
        }

        for future in as_completed(futures):

            model = futures[future]

            try:

                ans = future.result()
                results[model] = ans
                valid_answers[model] = ans

            except Exception as error:

                results[model] = (
                    f"Model gagal: {error}"
                )

    if not valid_answers:
        raise RuntimeError("Semua model Fusion AI gagal mendapatkan respon.")

    # Jika hanya 1 model berhasil, langsung kembalikan hasilnya
    if len(valid_answers) == 1:
        return list(valid_answers.values())[0]

    # Gabungkan hasil
    collected = []

    for model, answer in results.items():

        collected.append(
            f"""
=== HASIL {model} ===

{answer}
"""
        )

    combined = "\n".join(collected)

    # Prompt synthesis
    synthesis_prompt = f"""
Kamu adalah AI synthesizer.

Pengguna memberikan pertanyaan:

{user_message}

Beberapa AI telah memberikan jawaban:

{combined}

Tugas kamu:

1. Bandingkan semua jawaban.
2. Cari informasi yang benar.
3. Identifikasi kesalahan.
4. Gabungkan insight terbaik.
5. Jangan sekadar menyalin satu jawaban.
6. Buat satu jawaban final yang akurat.
7. Jika ada perbedaan pendapat, tentukan
   solusi yang paling masuk akal.
8. Jawab dalam bahasa Indonesia.
9. Jangan menyebut proses internal
   atau nama model kecuali diperlukan.
"""

    try:
        final_answer = call_model(
            synthesis_model,
            synthesis_prompt
        )
        return final_answer
    except Exception as error:
        # Fallback jika model synthesis gagal: gunakan jawaban pertama yang berhasil
        return list(valid_answers.values())[0]

