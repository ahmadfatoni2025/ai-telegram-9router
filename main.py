import os
import time
import logging
import requests

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

app = FastAPI()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

NINE_ROUTER_API_KEY = os.getenv("NINE_ROUTER_API_KEY")

NINE_ROUTER_URL = os.getenv(
    "NINE_ROUTER_URL",
    "http://127.0.0.1:20128/v1/chat/completions"
)

# Model fallback.
#
# Urutan model akan dicoba dari kiri ke kanan.
AI_MODELS = [
    model.strip()
    for model in os.getenv(
        "AI_MODELS",
        "ag/gemini-3.6-flash-low,"
        "ag/gemini-3.6-flash-medium,"
        "ag/gemini-3.7-flash-low,"
        "groq/llama-3.3-70b-versatile,"
        "groq/qwen/qwen3-32b"
    ).split(",")
    if model.strip()
]

AI_TIMEOUT = int(
    os.getenv("AI_TIMEOUT", "120")
)

AI_COOLDOWN = int(
    os.getenv("AI_COOLDOWN", "60")
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("whatsapp-ai")


# ============================================================
# MODEL STATE
# ============================================================

# Menyimpan model yang sedang cooldown.
#
# Contoh:
#
# {
#     "ag/gemini-3.6-flash-low": 1787275200
# }
#
# Artinya model tidak digunakan sampai timestamp tersebut.

model_cooldown = {}


# ============================================================
# WEBHOOK VERIFICATION
# ============================================================

@app.get("/webhook")
async def verify_webhook(request: Request):

    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:

        logger.info("WhatsApp webhook berhasil diverifikasi.")

        return PlainTextResponse(challenge)

    logger.warning("WhatsApp webhook verification gagal.")

    return PlainTextResponse(
        "Verification failed",
        status_code=403
    )


# ============================================================
# WHATSAPP WEBHOOK
# ============================================================

@app.post("/webhook")
async def receive_message(request: Request):

    data = await request.json()

    logger.info("Incoming WhatsApp:")
    logger.info(data)

    try:

        message = (
            data["entry"][0]
            ["changes"][0]
            ["value"]
            ["messages"][0]
        )

        sender = message["from"]

        # Untuk sementara hanya menerima pesan text.
        if message.get("type") != "text":

            logger.info(
                "Pesan bukan text, diabaikan."
            )

            return {"status": "ignored"}

        text = message["text"]["body"]

        logger.info(
            "From: %s",
            sender
        )

        logger.info(
            "Message: %s",
            text
        )

        # ====================================================
        # AI FALLBACK
        # ====================================================

        result = ask_ai(text)

        answer = result["content"]
        model_used = result["model"]

        logger.info(
            "AI berhasil menggunakan model: %s",
            model_used
        )

        # ====================================================
        # SEND WHATSAPP
        # ====================================================

        send_whatsapp_message(
            sender,
            answer
        )

    except (KeyError, IndexError, TypeError) as error:

        # Event WhatsApp tertentu memang tidak mempunyai
        # struktur messages.
        logger.info(
            "Webhook bukan pesan WhatsApp: %s",
            error
        )

    except Exception as error:

        logger.exception(
            "Error saat memproses WhatsApp: %s",
            error
        )

    return {"status": "ok"}


# ============================================================
# AI FALLBACK
# ============================================================

def ask_ai(question):

    models = [
        "ag/gemini-3.6-flash-low",
        "ag/gemini-3.6-flash-medium",
        "ag/gemini-3.6-flash-high",
        "gemini/gemini-3.6-flash",
        "ag/gemini-3.5-flash-low",
        "groq/llama-3.3-70b-versatile",
    ]

    for model in models:

        print("=" * 60)
        print(f"Trying model: {model}")

        try:

            response = requests.post(
                NINE_ROUTER_URL,

                headers={
                    "Authorization": f"Bearer {NINE_ROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },

                json={
                    "model": model,

                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Kamu adalah AI Assistant "
                                "yang berkomunikasi melalui WhatsApp. "
                                "Jawab dalam bahasa Indonesia. "
                                "Berikan jawaban yang jelas dan membantu."
                            )
                        },
                        {
                            "role": "user",
                            "content": question
                        }
                    ],

                    "stream": False
                },

                timeout=120
            )

            print(f"HTTP status: {response.status_code}")
            print(f"Response: {response.text[:500]}")

            # Berhasil
            if response.status_code == 200:

                data = response.json()

                try:
                    answer = data["choices"][0]["message"]["content"]

                    if answer:
                        print(f"SUCCESS: {model}")
                        return answer

                except (KeyError, IndexError, TypeError):
                    print(f"Invalid response from {model}")
                    continue

            # Limit / credits habis
            elif response.status_code in [402, 429]:

                print(
                    f"LIMIT/CREDITS HABIS: {model}"
                )

                continue

            # Server/model error
            elif response.status_code >= 500:

                print(
                    f"SERVER ERROR: {model}"
                )

                continue

            # Model tidak tersedia
            elif response.status_code == 404:

                print(
                    f"MODEL/ENDPOINT NOT FOUND: {model}"
                )

                continue

            else:

                print(
                    f"ERROR {response.status_code}: {model}"
                )

                continue

        except requests.exceptions.Timeout:

            print(
                f"TIMEOUT: {model}"
            )

            continue

        except requests.exceptions.RequestException as e:

            print(
                f"REQUEST ERROR: {model}"
            )

            print(e)

            continue

    return (
        "Maaf, semua model AI yang tersedia "
        "sedang tidak dapat digunakan. "
        "Silakan coba lagi beberapa saat."
    )

    errors = []

    logger.info(
        "Pertanyaan AI: %s",
        question
    )

    for model in AI_MODELS:

        # ----------------------------------------------------
        # CEK COOLDOWN
        # ----------------------------------------------------

        if is_model_on_cooldown(model):

            remaining = int(
                model_cooldown[model] - time.time()
            )

            logger.info(
                "SKIP %s - cooldown %ss lagi",
                model,
                max(remaining, 0)
            )

            continue

        logger.info(
            "Mencoba model: %s",
            model
        )

        try:

            response = requests.post(

                NINE_ROUTER_URL,

                headers={
                    "Authorization": (
                        f"Bearer {NINE_ROUTER_API_KEY}"
                    ),
                    "Content-Type": "application/json"
                },

                json={

                    "model": model,

                    "messages": [

                        {
                            "role": "system",
                            "content": (
                                "Kamu adalah AI Assistant "
                                "yang berkomunikasi melalui "
                                "WhatsApp. "
                                "Jawab dalam bahasa Indonesia. "
                                "Berikan jawaban yang jelas, "
                                "akurat, dan tidak bertele-tele."
                            )
                        },

                        {
                            "role": "user",
                            "content": question
                        }

                    ],

                    "stream": False

                },

                timeout=AI_TIMEOUT
            )

            # =================================================
            # BERHASIL
            # =================================================

            if response.status_code == 200:

                data = response.json()

                choices = data.get(
                    "choices",
                    []
                )

                if not choices:

                    raise RuntimeError(
                        "Response AI tidak memiliki choices."
                    )

                message = choices[0].get(
                    "message",
                    {}
                )

                content = message.get(
                    "content"
                )

                if not content:

                    raise RuntimeError(
                        "Response AI tidak memiliki content."
                    )

                return {
                    "model": model,
                    "content": content
                }

            # =================================================
            # ERROR
            # =================================================

            error_text = response.text

            logger.warning(
                "Model %s gagal. HTTP %s",
                model,
                response.status_code
            )

            logger.warning(
                "Response: %s",
                error_text[:1000]
            )

            # -------------------------------------------------
            # QUOTA / CREDIT / RATE LIMIT
            # -------------------------------------------------

            if is_quota_error(
                response.status_code,
                error_text
            ):

                cooldown_model(model)

                errors.append(
                    f"{model}: "
                    f"quota/limit HTTP "
                    f"{response.status_code}"
                )

                continue

            # -------------------------------------------------
            # SERVER ERROR
            # -------------------------------------------------

            if response.status_code in [
                500,
                502,
                503,
                504
            ]:

                cooldown_model(model)

                errors.append(
                    f"{model}: server error "
                    f"HTTP {response.status_code}"
                )

                continue

            # -------------------------------------------------
            # ERROR LAIN
            # -------------------------------------------------

            errors.append(
                f"{model}: HTTP "
                f"{response.status_code}"
            )

            # Jangan langsung mematikan seluruh sistem.
            # Coba model berikutnya.
            continue

        # =====================================================
        # TIMEOUT
        # =====================================================

        except requests.Timeout:

            logger.warning(
                "Model %s timeout.",
                model
            )

            cooldown_model(model)

            errors.append(
                f"{model}: timeout"
            )

            continue

        # =====================================================
        # REQUEST ERROR
        # =====================================================

        except requests.RequestException as error:

            logger.warning(
                "Request error pada %s: %s",
                model,
                error
            )

            cooldown_model(model)

            errors.append(
                f"{model}: request error"
            )

            continue

        # =====================================================
        # ERROR LAIN
        # =====================================================

        except Exception as error:

            logger.exception(
                "Error pada model %s",
                model
            )

            errors.append(
                f"{model}: {error}"
            )

            continue

    # =========================================================
    # SEMUA MODEL GAGAL
    # =========================================================

    logger.error(
        "Semua model AI gagal."
    )

    raise RuntimeError(
        "Semua model AI tidak tersedia.\n"
        + "\n".join(errors)
    )


# ============================================================
# DETECT QUOTA / LIMIT ERROR
# ============================================================

def is_quota_error(
    status_code,
    error_text
):

    error_lower = error_text.lower()

    # HTTP status umum untuk limit/quota
    if status_code in [
        402,  # Payment / credits
        429   # Rate limit
    ]:
        return True

    keywords = [

        "quota",

        "quota exceeded",

        "rate limit",

        "rate_limit",

        "too many requests",

        "limit exceeded",

        "credits",

        "credit",

        "paid model",

        "credits required",

        "insufficient balance",

        "insufficient credits",

        "usage limit",

        "token limit",

        "capacity"

    ]

    for keyword in keywords:

        if keyword in error_lower:
            return True

    return False


# ============================================================
# COOLDOWN
# ============================================================

def cooldown_model(model):

    until = time.time() + AI_COOLDOWN

    model_cooldown[model] = until

    logger.warning(
        "Model %s masuk cooldown selama %ss.",
        model,
        AI_COOLDOWN
    )


def is_model_on_cooldown(model):

    until = model_cooldown.get(
        model,
        0
    )

    if time.time() >= until:

        # Hapus status cooldown
        # kalau sudah selesai.
        model_cooldown.pop(
            model,
            None
        )

        return False

    return True


# ============================================================
# WHATSAPP SEND MESSAGE
# ============================================================

def send_whatsapp_message(
    to,
    message
):

    url = (
        "https://graph.facebook.com/v23.0/"
        f"{PHONE_NUMBER_ID}/messages"
    )

    headers = {

        "Authorization": (
            f"Bearer {WHATSAPP_TOKEN}"
        ),

        "Content-Type": (
            "application/json"
        )

    }

    payload = {

        "messaging_product": "whatsapp",

        "to": to,

        "type": "text",

        "text": {
            "body": message
        }

    }

    response = requests.post(

        url,

        headers=headers,

        json=payload,

        timeout=30

    )

    logger.info(
        "WhatsApp response: %s",
        response.text
    )

    response.raise_for_status()