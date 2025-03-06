import re


def custom_str_to_float(s):
    s = s.strip().replace(" ", "").replace('"', "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")  # "100.120,00" → "100120.00"
        else:
            s = s.replace(",", "")  # "100,120.00" → "100120.00"
    else:
        s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None


def parse_line(line: str):
    parts = line.split()

    total = custom_str_to_float(parts[0])
    date = None

    if len(parts) >= 3 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[-1]):
        date = parts[-1]
        company = " ".join(parts[1:-1])  # Всё между total и date — это company
    else:
        company = " ".join(parts[1:])  # Всё после total — это company

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", company) and date is None:
        company, date = date, company

    if company == "":
        company = None

    return total, company, date



if __name__ == "__main__":
    assert custom_str_to_float("10") == 10.0
    assert custom_str_to_float("10.00") == 10.0
    assert custom_str_to_float("10,11") == 10.11
    assert custom_str_to_float("100.120,00") == 100_120.0
    assert custom_str_to_float("100,120.00") == 100_120.0

    assert parse_line("20") == (20.0, None, None)
    assert parse_line("20 yettel") == (20.0, 'yettel', None)
    assert parse_line("20 yettel 2025-03-01") == (20.0, 'yettel', '2025-03-01')
    assert parse_line("20 crna ovca") == (20.0, 'crna ovca', None)
    assert parse_line("20 crna ovca 2025-03-01") == (20.0, 'crna ovca', '2025-03-01')
    assert parse_line("200 beer 2024-12-26") == (200.0, 'beer', '2024-12-26')
    assert parse_line("200 2024-12-26") == (200.0, None, '2024-12-26')
