from app.services.telegram import create_bot


def main():

    bot = create_bot()

    print(
        "Telegram Fusion AI berjalan..."
    )

    bot.run_polling()


if __name__ == "__main__":
    main()