import os
import requests
import time
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AIFallback:

    def __init__(self):

        self.url = os.getenv(
            "NINE_ROUTER_URL",
            "http://127.0.0.1:20128/v1/chat/completions"
        )

        self.api_key = os.getenv("NINE_ROUTER_API_KEY")

        models = os.getenv("AI_MODELS", "")

        self.models = [
            model.strip()
            for model in models.split(",")
            if model.strip()
        ]

        if not self.models:
            raise ValueError(
                "AI_MODELS belum dikonfigurasi di .env"
            )

        self.timeout = int(
            os.getenv("AI_TIMEOUT", "120")
        )

        self.cooldown = int(
            os.getenv("AI_COOLDOWN", "60")
        )

        # Model yang sementara dianggap bermasalah
        self.disabled_until = {}

    def _headers(self):

        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = (
                f"Bearer {self.api_key}"
            )

        return headers

    def _is_temporarily_unavailable(
        self,
        status_code,
        error_text
    ):

        error_lower = error_text.lower()

        # HTTP status yang biasanya berarti
        # quota/rate-limit/provider sedang bermasalah
        if status_code in [402, 429, 500, 502, 503, 504]:
            return True

        keywords = [
            "rate limit",
            "rate_limit",
            "quota",
            "quota exceeded",
            "credit",
            "credits",
            "limit exceeded",
            "too many requests",
            "temporarily unavailable",
            "insufficient balance",
            "paid model"
        ]

        return any(
            keyword in error_lower
            for keyword in keywords
        )

    def _is_disabled(self, model):

        until = self.disabled_until.get(model, 0)

        return time.time() < until

    def _disable_model(self, model):

        self.disabled_until[model] = (
            time.time() + self.cooldown
        )

        logger.warning(
            "Model %s dinonaktifkan sementara selama %s detik",
            model,
            self.cooldown
        )

    def chat(self, message):

        errors = []

        for model in self.models:

            if self._is_disabled(model):

                logger.info(
                    "Skip model %s karena masih cooldown",
                    model
                )

                continue

            logger.info(
                "Mencoba model: %s",
                model
            )

            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "stream": False
            }

            try:

                response = requests.post(
                    self.url,
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout
                )

                # Berhasil
                if response.status_code == 200:

                    data = response.json()

                    choices = data.get(
                        "choices",
                        []
                    )

                    if not choices:
                        raise RuntimeError(
                            "Response tidak memiliki choices"
                        )

                    content = choices[0].get(
                        "message",
                        {}
                    ).get(
                        "content"
                    )

                    if not content:
                        raise RuntimeError(
                            "Response AI kosong"
                        )

                    logger.info(
                        "Model berhasil: %s",
                        model
                    )

                    return {
                        "model": model,
                        "content": content
                    }

                error_text = response.text

                logger.warning(
                    "Model %s gagal: HTTP %s - %s",
                    model,
                    response.status_code,
                    error_text[:500]
                )

                if self._is_temporarily_unavailable(
                    response.status_code,
                    error_text
                ):

                    self._disable_model(model)

                    errors.append(
                        f"{model}: HTTP "
                        f"{response.status_code}"
                    )

                    continue

                # Error lain
                errors.append(
                    f"{model}: HTTP "
                    f"{response.status_code}"
                )

            except requests.Timeout:

                logger.warning(
                    "Timeout pada model %s",
                    model
                )

                self._disable_model(model)

                errors.append(
                    f"{model}: timeout"
                )

            except requests.RequestException as e:

                logger.warning(
                    "Request error pada model %s: %s",
                    model,
                    e
                )

                self._disable_model(model)

                errors.append(
                    f"{model}: {e}"
                )

            except Exception as e:

                logger.exception(
                    "Unexpected error pada %s",
                    model
                )

                errors.append(
                    f"{model}: {e}"
                )

        raise RuntimeError(
            "Semua model gagal.\n"
            + "\n".join(errors)
        )
