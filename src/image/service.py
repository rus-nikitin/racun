import time
import functools

import numpy as np
import cv2
# from pyzbar import pyzbar

from logging import getLogger
from src.exceptions import QRCodeDecodeError

from qreader import QReader


log = getLogger(__name__)


def measure_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            log.info(f"Function {func.__name__} executed in {1e3 * (time.time() - start_time):.2f} ms.")

    return wrapper


# @measure_time
# def process_qr_url(image_bytes: bytes) -> str:
#     arr = np.frombuffer(image_bytes, np.uint8)
#
#     image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
#
#     decoded_objects = pyzbar.decode(image)
# 
#     for obj in decoded_objects:
#         if obj.type == 'QRCODE':
#             return obj.data.decode("utf-8")
#
#     raise QRCodeDecodeError("QRCodeDecodeError")


@measure_time
def process_qr_url_1(image_bytes: bytes):
    arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    qreader = QReader()

    decoded_text = qreader.detect_and_decode(image=image)

    first = next((x for x in decoded_text if x is not None), None)
    if first is not None:
        return first
    else:
        raise QRCodeDecodeError("QRCodeDecodeError")


if __name__ == "__main__":
    from pathlib import Path
    from typing import Callable, List


    def process(
            filename: str,
            image_bytes: bytes,
            fn: Callable,
            qr: List[str],
            success: List[str],
            errors: List[str]
    ):
        try:
            qr.append(fn(image_bytes))
            success.append(filename)
        except QRCodeDecodeError:
            errors.append(filename)


    # # zxing
    # import zxing
    # folder_path = Path('../../images')
    # for filename_path in folder_path.iterdir():
    #     if filename_path.suffix not in {".jpeg"}:
    #         continue
    #     reader = zxing.BarCodeReader()
    #     barcode = reader.decode(str(filename_path), try_harder=True)
    #     if barcode.raw is not None:
    #         print(barcode.path)

    filenames = []
    funcs = [
        {
            "fn": process_qr_url,
            "success": [],
            "errors": [],
            "qr": []
        },
        {
            "fn": process_qr_url_1,
            "success": [],
            "errors": [],
            "qr": []
        },
    ]

    folder_path = Path('../../images')
    for filename_path in folder_path.iterdir():
        if filename_path.suffix not in {".jpeg"}:
            continue


        with open(filename_path, "rb") as f:
            image_bytes = f.read()


        filename = filename_path.name
        filenames.append(filename)

        for func in funcs:
            process(filename, image_bytes, **func)


    import json
    for _ in funcs:
        del _["fn"]
    # with open("data.json", "w", encoding="utf-8") as f:
    #     json.dump(funcs, f, indent=4, ensure_ascii=False)

    # sorted(set(funcs[1]['success']) - set(funcs[0]['success']))
