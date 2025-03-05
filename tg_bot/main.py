from datetime import datetime
from typing import List, Optional, Dict, Any
from io import BytesIO

import httpx
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

from src.analytics.schemas import CompanyTotal, ItemTotal, GetAnalyticsResponse
from src.bill.schemas import UploadBillRequest, UploadBillResponse, GetBillResponse
from src.suf_purs.schemas import SpecificationItem
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
    def format_top_items_section(title: str, items: List[CompanyTotal | ItemTotal | SpecificationItem], numbers=None):
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
    def format_bill_response(bill: GetBillResponse) -> str:
        name_section = f"🏪 <b>{bill.seller_info.company}</b>"
        total = 0.0
        if len(bill.items) > 0:
            total = sum([_.total for _ in bill.items])
        total_section = f"🧾 <b>Total</b> — {int(total)} <b>RSD</b>"
        dt_section = f"⌚ <b>Time</b> — {bill.dt.strftime('%d-%m-%Y %H:%M')}"
        category_section = f"📌 <b>Category</b> — {bill.category}"

        items = sorted(bill.items, key=lambda x: x.total, reverse=True)
        items_section = MessageFormatter.format_top_items_section(title="items", items=items)

        qr_url = f'👉 <a href="{str(bill.qr_url)}">račun</a>'

        return "\n".join([name_section, total_section, dt_section, category_section, qr_url, "", *items_section])


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


    async def get_bill(self, bill_id: str) -> GetBillResponse:
        params = {"bill_id": bill_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/bill/one", params=params)
            response.raise_for_status()
            return GetBillResponse.model_validate(response.json())


    async def upload_bill(self, bill_upload: UploadBillRequest, user_name: str) -> UploadBillResponse:
        params = {"user_name": user_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/bill/upload", params=params, json=bill_upload.model_dump(mode="json"))
            response.raise_for_status()
            return UploadBillResponse.model_validate(response.json())


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
            bill = await self.api_client.get_bill(bill_id)
            msg = MessageFormatter.format_bill_response(bill)

            keyboard = [[InlineKeyboardButton("Change category", callback_data=f"changeCategory__{bill_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)
        except httpx.HTTPError as e:
            if hasattr(e, "response") and hasattr(e.response, "json"):
                error_key = e.response.json().get('detail')
                msg = ErrorMessages.get_error_message(error_key)
            else:
                msg = f"An error occurred: {str(e)}"
            await update.message.reply_text(msg, parse_mode="HTML")
        except Exception as e:
            msg = f"An error occurred: {str(e)}"
            await update.message.reply_text(msg, parse_mode="HTML")
        # finally:
        #     await update.message.reply_text(msg, parse_mode="HTML")


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


    async def handle_button(self, update: Update, context: CallbackContext) -> None:
        query = update.callback_query
        await query.answer()
        action, sub_action, bill_id = query.data.split("_")
        if action == "changeCategory":
            keyboard = [
                [InlineKeyboardButton("🛒 Grocery", callback_data=f"setCategory_Grocery_{bill_id}")],
                [InlineKeyboardButton("🍽️ Food & Drinks", callback_data=f"setCategory_Food & Drinks_{bill_id}")],
                [InlineKeyboardButton("👗 Fashion & Clothing", callback_data=f"setCategory_Fashion & Clothing_{bill_id}")],
                [InlineKeyboardButton("🏠 Home & Decor", callback_data=f"setCategory_Home & Decor_{bill_id}")],
                [InlineKeyboardButton("🚗 Automobiles", callback_data=f"setCategory_Automobiles_{bill_id}")],
                [InlineKeyboardButton("🌍 Travel & Tourism", callback_data=f"setCategory_Travel & Tourism_{bill_id}")],
                [InlineKeyboardButton("🚀 Other", callback_data=f"setCategory_Other_{bill_id}")],
                [InlineKeyboardButton("🚫 Cancel", callback_data=f"cancelCategory__{bill_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Choose category", reply_markup=reply_markup)
        elif action == "setCategory":
            bill = await self.api_client.get_bill(bill_id)

            upload_bill_request = bill.model_dump()
            upload_bill_request["category"] = sub_action
            upload_bill_request = UploadBillRequest(**upload_bill_request)
            upserted_bill = await self.api_client.upload_bill(upload_bill_request, bill.user_name)
            bill = await self.api_client.get_bill(bill_id)
            msg = MessageFormatter.format_bill_response(bill)
            await query.message.edit_text(msg, parse_mode="HTML")
        elif action == "cancelCategory":
            await query.message.edit_text("Category change canceled")


def main():
    handler = TelegramHandler()
    app = Application.builder().token(Config.TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", handler.start))
    app.add_handler(MessageHandler(filters.PHOTO, handler.handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_message))
    app.add_handler(CallbackQueryHandler(handler.handle_button))

    app.run_polling()


if __name__ == "__main__":
    print("Starting bot...")
    main()
