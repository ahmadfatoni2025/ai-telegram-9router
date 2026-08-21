import json
import os
import requests

from dotenv import load_dotenv

from app.services.file_tools import (
    list_files,
    read_file,
    write_file,
    edit_file,
    delete_file,
    download_file,
)


load_dotenv()


NINE_ROUTER_URL = os.getenv(
    "NINE_ROUTER_URL",
    "http://127.0.0.1:20128/v1/chat/completions",
)

NINE_ROUTER_API_KEY = os.getenv(
    "NINE_ROUTER_API_KEY"
)

AI_MODEL = os.getenv(
    "AI_MODEL",
    "ag/gemini-3.6-flash-low"
)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Melihat daftar file dan folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relatif atau absolut folder."
                    }
                }
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Membaca isi file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relatif atau absolut file."
                    }
                },
                "required": ["path"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Membuat atau menulis ulang file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relatif atau absolut file."
                    },
                    "content": {
                        "type": "string"
                    }
                },
                "required": [
                    "path",
                    "content"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Mengganti satu bagian teks dalam file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relatif atau absolut file."
                    },
                    "old_text": {
                        "type": "string"
                    },
                    "new_text": {
                        "type": "string"
                    }
                },
                "required": [
                    "path",
                    "old_text",
                    "new_text"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Menghapus sebuah file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relatif atau absolut file."
                    }
                },
                "required": ["path"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "download_file",
            "description": "Mendownload file dari URL luar dan menyimpannya ke path lokal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL sumber file yang akan didownload."
                    },
                    "path": {
                        "type": "string",
                        "description": "Path tujuan penyimpanan lokal."
                    }
                },
                "required": [
                    "url",
                    "path"
                ]
            }
        }
    }
]


def execute_tool(name, arguments):

    if name == "list_files":
        return list_files(
            arguments.get("path", ".")
        )

    if name == "read_file":
        return read_file(
            arguments["path"]
        )

    if name == "write_file":
        return write_file(
            arguments["path"],
            arguments["content"]
        )

    if name == "edit_file":
        return edit_file(
            arguments["path"],
            arguments["old_text"],
            arguments["new_text"]
        )

    if name == "delete_file":
        return delete_file(
            arguments["path"]
        )

    if name == "download_file":
        return download_file(
            arguments["url"],
            arguments["path"]
        )

    return f"Tool tidak dikenal: {name}"


def _post_ai(model, messages, tools=None):
    """Helper: kirim request ke Nine Router dengan model tertentu."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    response = requests.post(
        NINE_ROUTER_URL,
        headers={
            "Authorization": f"Bearer {NINE_ROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=120
    )
    response.raise_for_status()
    return response.json()


# Model fallback untuk ask_ai (tools agent)
# Hanya model yang mendukung tool_calls
AGENT_MODELS = [
    os.getenv("AI_MODEL", "ag/gemini-3.6-flash-low"),
    "ag/gemini-3.6-flash-medium",
    "ag/gemini-3.7-flash-low",
    "ag/gemini-3.5-flash-low",
    "chatApp",
]


def ask_ai(user_message):

    messages = [
        {
            "role": "system",
            "content": """
Kamu adalah AI assistant yang dapat mengelola file (CRUD) serta mendownload file dari luar.

Kamu memiliki tools untuk:
- melihat daftar file/folder (list_files)
- membaca file (read_file)
- membuat/menulis file (write_file)
- mengedit file (edit_file)
- menghapus file (delete_file)
- mendownload file dari URL luar (download_file)

Gunakan tools jika pengguna meminta operasi terhadap file atau mengunduh file dari luar.
Jangan mengarang isi file yang belum dibaca. Jika ingin mengedit file, baca file terlebih dahulu.
"""
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    last_error = None

    for model in AGENT_MODELS:

        try:

            data = _post_ai(model, messages, tools=TOOLS)
            message = data["choices"][0]["message"]

            tool_calls = message.get("tool_calls")

            if not tool_calls:
                return message.get(
                    "content",
                    "AI tidak memberikan response."
                )

            # Jalankan semua tool
            tool_messages = list(messages)
            tool_messages.append(message)

            for tool_call in tool_calls:
                function = tool_call["function"]
                name = function["name"]
                arguments = json.loads(function["arguments"])
                result = execute_tool(name, arguments)

                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result
                })

            # Minta AI menjelaskan hasil tool (tanpa tools di sini)
            data2 = _post_ai(model, tool_messages)
            return data2["choices"][0]["message"]["content"]

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            last_error = e
            if status in (429, 404, 500, 502, 503):
                # Rate limit atau model tidak tersedia, coba model berikutnya
                continue
            raise

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f"Semua model AI Agent gagal. Error terakhir: {last_error}"
    )

