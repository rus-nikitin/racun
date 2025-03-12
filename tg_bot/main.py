from datetime import datetime
from typing import List, Optional, Dict, Any
from io import BytesIO

import httpx
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

from src.analytics.schemas import CompanyTotal, ItemTotal, GetAnalyticsResponse, ByCategoriesResponse
from src.bill.schemas import UploadBillRequest, UploadBillResponse, GetBillResponse
from src.suf_purs.schemas import SpecificationItem
from src.pipeline.schemas import ProcessingImageResponse
from src.cost.schemas import CostItem, CostSellerInfo, CostCreate, CostUpdate, CostDocument
from tg_bot.config import settings
from tg_bot.service import parse_line


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


class KeyboardLayouts:
    MAIN_MENU = ReplyKeyboardMarkup([
        ["Statistics", "Uploads"],
        ["Help", "Settings"]
    ], resize_keyboard=True)

    categories = [
        "🛒 Grocery",
        "🍽️ Food & Drinks",
        "👗 Fashion & Clothing",
        "🏠 Home & Decor",
        "🚗 Automobiles",
        "🌍 Travel & Tourism",
        "🚀 Other",
        "🚫 Cancel"
    ]

    categories_map = {_.split(" ", 1)[1]: _ for _ in categories}

    @staticmethod
    def get_category_keyboard(handle: str, for_item: str) -> List:
        """
        handle | category | for_item
        setCategory_Grocery_forCost_67c99e7414606964687e7c26
        setCategory_Grocery_forBill_67c956c76f72582f61c62ef0
        """
        keyboard = []
        for category in KeyboardLayouts.categories:
            parts =  category.split()
            category_str = " ".join(parts[1:])  # w/o emoji
            keyboard.append([InlineKeyboardButton(category, callback_data=f"{handle}_{category_str}_{for_item}")])

        return keyboard


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
    def format_cost_response(cost: CostDocument) -> str:
        company_section = f"🏪 <b>{cost.seller_info.company}</b>"
        total = 0.0
        if len(cost.items) > 0:
            total = sum([_.total for _ in cost.items])
        total_section = f"🧾 <b>Total</b> — {int(total)} <b>RSD</b>"
        dt_section = f"⌚ <b>Date</b> — {cost.dt.strftime('%d-%m-%Y')}"
        category_section = f"📌 <b>Category</b> — {cost.category}"

        return "\n".join([company_section, total_section, dt_section, category_section])


    @staticmethod
    def format_analytics_response(data: GetAnalyticsResponse) -> str:
        total_section = f"🧾 <b>Total</b> — {int(data.total)} <b>RSD</b>"

        companies = sorted(data.companies, key=lambda x: x.total, reverse=True)
        companies_section = MessageFormatter.format_top_items_section(title="companies", items=companies)

        items = sorted(data.items, key=lambda x: x.total, reverse=True)
        items_section = MessageFormatter.format_top_items_section(title="items", items=items)

        return "\n".join([total_section, "", *companies_section, "", *items_section])

    @staticmethod
    def format_analytics_by_categories(data: ByCategoriesResponse, period: str, from_dt: str | None) -> str:
        total_s = f"<b>{int(data.total):,} RSD</b>"
        period_map = {
            "today": f"Costs {total_s} for today ({datetime.strptime(from_dt, '%Y-%m-%d').strftime('%-d %B %a') if from_dt else ''})",
            "currentMonth": f"Costs {total_s} in the current month ({datetime.strptime(from_dt, '%Y-%m-%d').strftime('%B')  if from_dt else ''})",
            "currentYear": f"Costs {total_s} in the current year ({datetime.strptime(from_dt, '%Y-%m-%d').strftime('%Y')  if from_dt else ''})",
            "allTime": f"Costs {total_s} for all time"
        }
        header_section = period_map[period]
        categories_section = []
        for category in data.categories:
            s = f"<b>{int(category.total):,} ({int(1e2*category.total/data.total)}%)</b> — {KeyboardLayouts.categories_map.get(category.category, '')}"
            categories_section.append(s)

        return "\n".join([header_section, "", *categories_section])

    @staticmethod
    def format_analytics_by_bills(data: GetAnalyticsResponse, period: str, from_dt: str | None) -> str:
        total_s = f"<b>{int(data.total):,} RSD</b>"
        period_map = {
            "today": f"Costs {total_s} for today ({datetime.strptime(from_dt, '%Y-%m-%d').strftime('%-d %B %a') if from_dt else ''})",
            "currentMonth": f"Costs {total_s} in the current month ({datetime.strptime(from_dt, '%Y-%m-%d').strftime('%B')  if from_dt else ''})",
            "currentYear": f"Costs {total_s} in the current year ({datetime.strptime(from_dt, '%Y-%m-%d').strftime('%Y')  if from_dt else ''})",
            "allTime": f"Costs {total_s} for all time"
        }
        header_section = period_map[period]

        companies = sorted(data.companies, key=lambda x: x.total, reverse=True)
        companies_section = [f"🔥 <b>Top companies out of {len(companies)}</b>"]
        for company in companies[:5]:
            s = f"<b>{int(company.total):,} ({int(1e2*company.total/data.total)}%)</b> — {company.name}"
            companies_section.append(s)

        items = sorted(data.items, key=lambda x: x.total, reverse=True)
        items_section = [f"🔥 <b>Top items out of {len(items)}</b>"]
        for item in items[:5]:
            s = f"<b>{int(item.total):,} ({int(1e2 * item.total / data.total)}%)</b> — {item.name}"
            items_section.append(s)

        return "\n".join([header_section, "", *companies_section, "", *items_section])


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


    async def delete_bill(self, bill_id: str, user_name: str) -> int:
        params = {"bill_id": bill_id, "user_name": user_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(f"{self.base_url}/bill/one", params=params)
            response.raise_for_status()
            return response.json()

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

    async def get_cost(self, cost_id: str) -> CostDocument:
        params = {"cost_id": cost_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/cost/one", params=params)
            response.raise_for_status()
            return CostDocument.model_validate(response.json())

    async def delete_cost(self, cost_id: str, user_name: str) -> int:
        params = {"cost_id": cost_id, "user_name": user_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(f"{self.base_url}/cost/one", params=params)
            response.raise_for_status()
            return response.json()

    async def upload_cost(self, cost_upload: CostCreate | CostUpdate, user_name: str) -> CostDocument:
        params = {"user_name": user_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/cost/upload", params=params, json=cost_upload.model_dump(mode="json"))
            response.raise_for_status()
            return CostDocument.model_validate(response.json())


    async def get_analytics(self, username: str, from_dt: Optional[str] = None) -> GetAnalyticsResponse:
        params = {"user_name": username}
        if from_dt is not None:
            params["from_dt"] = from_dt

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/analytics", params=params)
            response.raise_for_status()
            return GetAnalyticsResponse.model_validate(response.json())

    async def get_analytics_by_categories(self, username: str, from_dt: Optional[str] = None) -> ByCategoriesResponse:
        params = {"user_name": username}
        if from_dt is not None:
            params["from_dt"] = from_dt

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/analytics/by-categories", params=params)
            response.raise_for_status()
            return ByCategoriesResponse.model_validate(response.json())


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

            keyboard = [
                [InlineKeyboardButton("Change category", callback_data=f"changeCategory_forBill_{bill_id}")],
                [InlineKeyboardButton("Remove record", callback_data=f"removeRecord_forBill_{bill_id}")]
            ]

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


    async def handle_period_text(self, update: Update, context: CallbackContext) -> None:
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

    async def handle_message_statistics(self, update: Update, context: CallbackContext) -> None:
        keyboard = [
            [InlineKeyboardButton("By Categories", callback_data=f"statistics_byCategories")],
            [InlineKeyboardButton("By Bills", callback_data=f"statistics_byBills")],
            [InlineKeyboardButton("Cancel", callback_data=f"statistics_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return await update.message.reply_text("Select an option", parse_mode="HTML", reply_markup=reply_markup)

    async def handle_statistics_ByCategories(self, update: Update, context: CallbackContext):
        """
        query.data :
            statistics_byCategories_today
            statistics_byCategories_currentMonth
        """
        # query.from_user.username
        query = update.callback_query
        period = query.data.split("_")[-1]

        datetime_now = datetime.now()
        from_dt = None
        if period == "today":
            from_dt = datetime_now.strftime('%Y-%m-%d')
        elif period == "currentMonth":
            from_dt = datetime(year=datetime_now.year, month=datetime_now.month, day=1).strftime('%Y-%m-%d')
        elif period == "currentYear":
            from_dt = datetime(year=datetime_now.year, month=1, day=1).strftime('%Y-%m-%d')

        by_categories_data = await self.api_client.get_analytics_by_categories(query.from_user.username, from_dt)

        msg = MessageFormatter.format_analytics_by_categories(by_categories_data, period, from_dt)
        return await query.message.edit_text(msg, parse_mode="HTML")

    async def handle_statistics_ByBills(self, update: Update, context: CallbackContext):
        """
        query.data :
            statistics_byCategories_today
            statistics_byCategories_currentMonth
        """
        # query.from_user.username
        query = update.callback_query
        period = query.data.split("_")[-1]

        datetime_now = datetime.now()
        from_dt = None
        if period == "today":
            from_dt = datetime_now.strftime('%Y-%m-%d')
        elif period == "currentMonth":
            from_dt = datetime(year=datetime_now.year, month=datetime_now.month, day=1).strftime('%Y-%m-%d')
        elif period == "currentYear":
            from_dt = datetime(year=datetime_now.year, month=1, day=1).strftime('%Y-%m-%d')

        data = await self.api_client.get_analytics(query.from_user.username, from_dt)
        msg = MessageFormatter.format_analytics_by_bills(data, period, from_dt)
        return await query.message.edit_text(msg, parse_mode="HTML")


    async def handle_statistics(self, update: Update, context: CallbackContext):
        """
        query.data :
            statistics_cancel
            statistics_byCategories
            statistics_byBills
            statistics_byCategories_today
            statistics_byCategories_currentMonth
            statistics_byBills_previousMonth
            statistics_byBills_currentYear
            statistics_byBills_cancel
        """
        query = update.callback_query
        _ = query.data.split("_")

        if _[-1] == "cancel":
            return await query.message.edit_text("Canceled", parse_mode="HTML")

        if len(_) == 2:  # statistics_byCategories | statistics_byBills
            handle = "_".join(_)
            keyboard = [
                [InlineKeyboardButton("Today", callback_data=f"{handle}_today")],
                [InlineKeyboardButton("Current Month", callback_data=f"{handle}_currentMonth")],
                # [InlineKeyboardButton("Previous Month", callback_data=f"{handle}_previousMonth")],
                [InlineKeyboardButton("Current Year", callback_data=f"{handle}_currentYear")],
                [InlineKeyboardButton("All time", callback_data=f"{handle}_allTime")],
                [InlineKeyboardButton("Cancel", callback_data=f"{handle}_cancel")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            return await query.message.edit_text("Select a period", parse_mode="HTML", reply_markup=reply_markup)

        handle, option, period = _
        if option == "byCategories":
            return await self.handle_statistics_ByCategories(update, context)
        elif option == "byBills":
            return await self.handle_statistics_ByBills(update, context)


    async def handle_message_uploads(self, update: Update, context: CallbackContext) -> None:
        # TODO
        await update.message.reply_text("In development", parse_mode="HTML")

    async def handle_message_help(self, update: Update, context: CallbackContext) -> None:
        # TODO
        await update.message.reply_text("In development", parse_mode="HTML")

    async def handle_message_settings(self, update: Update, context: CallbackContext) -> None:
        # TODO
        await update.message.reply_text("In development", parse_mode="HTML")

    async def handle_message_unknown(self, update: Update, context: CallbackContext) -> None:
        return await update.message.reply_text("Unknown command")

    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        text = update.message.text.lower()

        handlers = {
            "statistics": self.handle_message_statistics,
            "uploads": self.handle_message_uploads,
            "help": self.handle_message_help,
            "settings": self.handle_message_settings,
        }
        handler_function = handlers.get(text)
        if handler_function:
            return await handler_function(update, context)

        username = update.message.from_user.username or "unknown"
        total, company, date = parse_line(text)
        if type(total) is not float:
            await update.message.reply_text("Unknown command")
            return
        if company is None:
            company = ""
        if date is not None:
            try:
                dt = datetime.strptime(date, '%d-%m-%Y')
            except ValueError:
                await update.message.reply_text("The date is in an incorrect format")
                return
        else:
            dt = datetime.now()
        cost = CostCreate(dt=dt, items=[CostItem(name="", total=total)], seller_info=CostSellerInfo(company=company))
        document = await self.api_client.upload_cost(cost, username)
        msg = MessageFormatter.format_cost_response(document)
        cost_id = document.cost_id
        keyboard = [
            [InlineKeyboardButton("Change category", callback_data=f"changeCategory_forCost_{cost_id}")],
            [InlineKeyboardButton("Remove record", callback_data=f"removeRecord_forCost_{cost_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

    async def handle_changeCategory(self, update: Update, context: CallbackContext):
        query = update.callback_query
        _, for_item = query.data.split("_", 1)

        keyboard = KeyboardLayouts.get_category_keyboard(handle="setCategory", for_item=for_item)
        reply_markup = InlineKeyboardMarkup(keyboard)
        return await query.message.edit_text(f"Choose category", reply_markup=reply_markup)

    @staticmethod
    async def edit_cost_details(update: Update, context: CallbackContext, cost_document):
        query = update.callback_query

        formatted_message = MessageFormatter.format_cost_response(cost_document)
        cost_id = cost_document.cost_id
        keyboard = [
            [InlineKeyboardButton("Change category", callback_data=f"changeCategory_forCost_{cost_id}")],
            [InlineKeyboardButton("Remove record", callback_data=f"removeRecord_forCost_{cost_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return await query.message.edit_text(formatted_message, parse_mode="HTML", reply_markup=reply_markup)

    @staticmethod
    async def edit_bill_details(update: Update, context: CallbackContext, bill_document, bill_id):
        query = update.callback_query

        formatted_message = MessageFormatter.format_bill_response(bill_document)
        keyboard = [
            [InlineKeyboardButton("Change category", callback_data=f"changeCategory_forBill_{bill_id}")],
            [InlineKeyboardButton("Remove record", callback_data=f"removeRecord_forBill_{bill_id}")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        return await query.message.edit_text(formatted_message, parse_mode="HTML", reply_markup=reply_markup)

    async def handle_setCategory_forCost(self, update: Update, context: CallbackContext):
        query = update.callback_query
        handle, category, item_type, item_id = query.data.split("_")

        document = await self.api_client.get_cost(item_id)
        if category == "Cancel":
            return await TelegramHandler.edit_cost_details(update, context, document)

        cost_data = document.model_dump()
        cost_data["category"] = category
        cost = CostUpdate(**cost_data)

        updated_cost_document = await self.api_client.upload_cost(cost, document.user_name)
        return await TelegramHandler.edit_cost_details(update, context, updated_cost_document)

    async def handle_setCategory_forBill(self, update: Update, context: CallbackContext):
        query = update.callback_query
        handle, category, item_type, item_id = query.data.split("_")

        document = await self.api_client.get_bill(item_id)
        if category == "Cancel":
            return await TelegramHandler.edit_bill_details(update, context, document, item_id)

        bill_data = document.model_dump()
        bill_data["category"] = category
        bill = UploadBillRequest(**bill_data)
        await self.api_client.upload_bill(bill, document.user_name)
        document = await self.api_client.get_bill(item_id)

        return await TelegramHandler.edit_bill_details(update, context, document, item_id)

    async def handle_setCategory(self, update: Update, context: CallbackContext):
        action_handlers = {
            "forCost": self.handle_setCategory_forCost,
            "forBill": self.handle_setCategory_forBill,
        }

        query = update.callback_query
        handle, category, item_type, item_id = query.data.split("_")
        handler_function = action_handlers.get(item_type)
        return await handler_function(update, context)

    async def handle_removeRecord(self, update: Update, context: CallbackContext):
        query = update.callback_query
        handle, item_type, item_id = query.data.split("_")

        text_html = query.message.text_html
        if item_type == "forBill":
            deleted_count = await self.api_client.delete_bill(item_id, query.from_user.username)
        elif item_type == "forCost":
            deleted_count = await self.api_client.delete_cost(item_id, query.from_user.username)

        return await query.message.edit_text("Removed\n"+text_html, parse_mode="HTML")

    async def handle_button(self, update: Update, context: CallbackContext):
        action_handlers = {
            "changeCategory": self.handle_changeCategory,
            "setCategory": self.handle_setCategory,
            "removeRecord": self.handle_removeRecord,
            "statistics": self.handle_statistics,
        }

        query = update.callback_query
        await query.answer()
        handler, *_ = query.data.split("_", 1)
        handler_function = action_handlers.get(handler)
        return await handler_function(update, context)


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
