import datetime
import pytz


def now(timezone="UTC"):
    return datetime.datetime.now(pytz.timezone(timezone))


def current_year_month():
    return now().strftime("%Y%m")


def date_to_str(date, format="%Y-%m-%d"):
    return date.strftime(format)


def str_to_date(str_date, format="%Y-%m-%d"):
    return datetime.datetime.strptime(str_date, format).date()


def current_month_range():
    today = now().date()
    start = today.replace(day=1)
    days_of_month = [date_to_str(start + datetime.timedelta(days=x)) for x in range((today - start).days + 1)]
    return days_of_month


def create_ascii_table(headers, table_data):
    table = []
    table.append("+")
    for header in headers:
        table.append("-" * header + "-" + "+")
    table.append("\n")

    for row in table_data:
        table.append("|")
        for i, cell in enumerate(row):
            if len(cell) < headers[i]:
                cell = " " * (headers[i] - len(cell)) + cell
            table.append("" + cell + " |")
        table.append("\n")
        table.append("+")
        for header in headers:
            table.append("-" * header + "-" + "+")
        table.append("\n")

    return "".join(table)


def user_data_to_ascii_table(user_date_list):
    table_data = [["date", "tokens", "times"]]
    headers = [16, 15, 15]
    for user_data in user_date_list:
        table_data.append([
            user_data['date'],
            str(user_data['tokens']),
            str(user_data['process_time']),
        ])
    return create_ascii_table(headers, table_data)
