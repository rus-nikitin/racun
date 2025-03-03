from datetime import datetime
from typing import List, Optional, Dict, Any
from io import BytesIO

import httpx
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

from src.analytics.schemas import CompanyTotal, ItemTotal, GetAnalyticsResponse
from src.pipeline.schemas import ProcessingImageResponse
from tg_bot.config import settings


class Config:
    TOKEN = settings.token
    API_BASE_URL = f"http://{settings.host}:{settings.port}{settings.api_prefix}"
    REQUEST_TIMEOUT = settings.request_timeout  # seconds


# Error mapping
class ErrorMessages:
    ERROR_MAP = {
        "Failed to decode QR code: QRCodeDecodeError": "Can't decode QR code",
        "File already exists in the database.": "Image already received",
        "Invalid QR URL": "Invalid QR URL",
        "default": "Unknown error occurred"
    }

    @classmethod
    def get_error_message(cls, error_key: str) -> str:
        return cls.ERROR_MAP.get(error_key, cls.ERROR_MAP["default"])


# Keyboard layouts
class KeyboardLayouts:
    MAIN_MENU = ReplyKeyboardMarkup([
        ["📅 Day", "📆 Month"],
        ["📊 Year", "💰 Total"]
    ], resize_keyboard=True)


# Message formatters
class MessageFormatter:
    @staticmethod
    def format_top_items_section(title: str, items: List[CompanyTotal | ItemTotal], numbers=None):
        if numbers is None:
            numbers = ["1️⃣", "2️⃣", "3️⃣"]

        return [
            f"🔥 <b>Top {title} out of {len(items)}</b>",
            *[
                f"{number} <b>{item.name} — {int(item.total)}</b> <b>RSD</b>"
                for item, number in zip(items[:len(numbers)], numbers)
            ]
        ]


    @staticmethod
    def format_bill_response(data: GetAnalyticsResponse, dt: datetime) -> str:
        name_section = f"🏪 <b>{data.companies[0].name}</b>"
        total_section = f"🧾 <b>Total</b> — {int(data.total)} <b>RSD</b>"
        dt_section = f"⌚ <b>Time</b> — {dt.strftime('%d-%m-%Y %H:%M')}"

        items = sorted(data.items, key=lambda x: x.total, reverse=True)
        items_section = MessageFormatter.format_top_items_section(title="items", items=items)

        return "\n".join([name_section, "", total_section, "", dt_section, "", *items_section])


    @staticmethod
    def format_analytics_response(data: GetAnalyticsResponse) -> str:
        total_section = f"🧾 <b>Total</b> — {int(data.total)} <b>RSD</b>"

        companies = sorted(data.companies, key=lambda x: x.total, reverse=True)
        companies_section = MessageFormatter.format_top_items_section(title="companies", items=companies)

        items = sorted(data.items, key=lambda x: x.total, reverse=True)
        items_section = MessageFormatter.format_top_items_section(title="items", items=items)

        return "\n".join([total_section, "", *companies_section, "", *items_section])


# API Client
class APIClient:
    def __init__(self):
        self.base_url = Config.API_BASE_URL
        self.timeout = httpx.Timeout(Config.REQUEST_TIMEOUT)


    async def process_image(self, image_bytes: BytesIO, username: str) -> ProcessingImageResponse:
        files = {"image": ("image.jpg", image_bytes, "image/jpeg")}
        params = {"user_name": username}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/pipeline/processing",
                files=files,
                params=params
            )
            response.raise_for_status()
            return ProcessingImageResponse.model_validate(response.json())


    async def get_bill_details(self, bill_id: str) -> GetAnalyticsResponse:
        params = {"bill_id": bill_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/analytics", params=params)
            response.raise_for_status()
            return GetAnalyticsResponse.model_validate(response.json())


    async def get_analytics(self, username: str, from_dt: Optional[str] = None) -> GetAnalyticsResponse:
        params = {"user_name": username}
        if from_dt is not None:
            params["from_dt"] = from_dt

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/analytics", params=params)
            response.raise_for_status()
            return GetAnalyticsResponse.model_validate(response.json())


# Handler class
class TelegramHandler:
    def __init__(self):
        self.api_client = APIClient()


    @staticmethod
    async def start(update: Update, context: CallbackContext) -> None:
        await update.message.reply_text(
            "Choose an option:",
            reply_markup=KeyboardLayouts.MAIN_MENU
        )


    async def handle_image(self, update: Update, context: CallbackContext) -> None:
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = BytesIO(await file.download_as_bytearray())
            username = update.message.from_user.username or "unknown"

            data = await self.api_client.process_image(file_bytes, username)
            bill_id = data.bill_id
            dt = data.dt
            data = await self.api_client.get_bill_details(bill_id)
            msg = MessageFormatter.format_bill_response(data, dt)
        except httpx.HTTPError as e:
            if hasattr(e, "response") and hasattr(e.response, "json"):
                error_key = e.response.json().get('detail')
                msg = ErrorMessages.get_error_message(error_key)
            else:
                msg = f"An error occurred: {str(e)}"
        except Exception as e:
            msg = f"An error occurred: {str(e)}"
        finally:
            await update.message.reply_text(msg, parse_mode="HTML")


    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        text = update.message.text.lower()
        datetime_now = datetime.now()

        from_dt = None
        if "day" in text:
            from_dt = datetime_now.strftime('%Y-%m-%d')
        elif "month" in text:
            from_dt = datetime(year=datetime_now.year, month=datetime_now.month, day=1).strftime('%Y-%m-%d')
        elif "year" in text:
            from_dt = datetime(year=datetime_now.year, month=1, day=1).strftime('%Y-%m-%d')
        elif "total" not in text:
            await update.message.reply_text("Unknown command. Please use the keyboard buttons.")
            return

        try:
            username = update.message.from_user.username or "unknown"
            data = await self.api_client.get_analytics(username, from_dt)
            msg = MessageFormatter.format_analytics_response(data)
            await update.message.reply_text(msg, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}")


def main():
    handler = TelegramHandler()
    app = Application.builder().token(Config.TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", handler.start))
    app.add_handler(MessageHandler(filters.PHOTO, handler.handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_message))

    app.run_polling()


if __name__ == "__main__":
    print("Starting bot...")
    main()
