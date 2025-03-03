import re
from typing import List
from datetime import datetime

from src.exceptions import ParseContentError
from .schemas import SpecificationsRequest


patterns_map = {
    "invoice_number": r"viewModel\.InvoiceNumber\('([^']+)'\)",
    "token": r"viewModel\.Token\('([^']+)'\)",
    "bill_datetime": r'<span id="sdcDateTimeLabel">\s*([\d\.]+ \d{2}:\d{2}:\d{2})\s*</span>',
    "bill_meta_info": r"============ ФИСКАЛНИ РАЧУН ============\r\n(.*?)\r\n-------------ПРОМЕТ ПРОДАЈА-------------"
}


def parse_content(pattern: str, content: bytes):
    match = re.search(pattern, content.decode("utf-8"), re.S)
    if match:
        return match.group(1)
    else:
        raise ParseContentError(f"pattern {pattern} not found")


def get_specifications_request(content: bytes) -> SpecificationsRequest:
    try:
        invoice_number = parse_content(patterns_map["invoice_number"], content)
    except ParseContentError:
        raise ParseContentError(f"pattern 'invoice_number' not found")
    try:
        token = parse_content(patterns_map["token"], content)
    except ParseContentError:
        raise ParseContentError(f"pattern 'token' not found")

    return SpecificationsRequest(invoiceNumber=invoice_number, token=token)


def get_dt(content: bytes) -> datetime:
    try:
        dt = parse_content(patterns_map["bill_datetime"], content)
    except ParseContentError:
        raise ParseContentError(f"pattern 'bill_datetime' not found")

    return datetime.strptime(dt, '%d.%m.%Y. %H:%M:%S')


def get_meta_info(content: bytes) -> List[str]:
    try:
        meta_info = parse_content(patterns_map["bill_meta_info"], content)
    except ParseContentError:
        raise ParseContentError(f"pattern 'bill_meta_info' not found")

    return [_.strip() for _ in meta_info.split("\r\n")]