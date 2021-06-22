import logging
import re
import time
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Any, Dict, List

import isodate
import requests
from bs4 import BeautifulSoup

logging.root.setLevel(logging.INFO)


def get_direct_child_from_soup(parent: BeautifulSoup):
    return "".join(parent.find_all(text=True, recursive=False)).strip()


def get_pt_time_in_seconds(time_str: Any) -> int:
    return int(isodate.parse_duration(time_str).total_seconds())


def get_time_in_seconds(time_str: Any) -> int:
    if time_str is not None:
        time_num = re.search(r"\d+", time_str)[0] if re.search(r"\d+", time_str) else 0
        return int(
            float(time_num) * 3600
            if "h" in time_str or "시" in time_str
            else float(time_num) * 60
        )
    return 0


def get_korean_from_string(string: str) -> List[Any]:
    if string is not None:
        return re.findall(r"[가-힣]+", string)
    return [None]


def get_numbers_from_string(string: str) -> List[Any]:
    if string is not None:
        return re.findall(r"[-+]?\d*\.\d+|\d+", string)
    return [1]


def get_letters_from_string(string: str) -> List[Any]:
    if string is not None:
        return re.findall(r"[가-힣]+|[a-zA-Z]+", string)
    return [None]


def get_response_content_list(url_list, headers: Dict = None) -> List[Dict]:
    response_list = list()
    processes = list()

    for i in range(0, len(url_list), 10):
        url_sublist = url_list[i : i + 10]
        parent_conn, child_conn = Pipe()
        response_list.append(parent_conn)
        process = Process(
            target=get_response_content_sublist, args=(url_sublist, child_conn, headers)
        )
        processes.append(process)

    for process in processes:
        process.start()

    total_response_list = list()
    for response_sublist in response_list:
        total_response_list.extend(response_sublist.recv())

    for process in processes:
        process.join()

    return total_response_list


def get_response_content_sublist(
    url_sublist: List[str], child_conn: Connection, headers: Dict = None
) -> None:
    response_list = list()
    for url in url_sublist:
        try:
            response = requests.get(url, headers=headers)
            time.sleep(0)
            response_list.append({"url": url, "response_content": response.content})
            logging.info(f"Got response content from {url}")
        except Exception as e:
            logging.error(e)
            pass
    child_conn.send(response_list)
    child_conn.close()
