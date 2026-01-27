from GoogleNews import GoogleNews
import pandas as pd
from datetime import timedelta, datetime
from google.oauth2 import service_account
import gspread
from dateutil import parser
from bs4 import BeautifulSoup
from time import sleep
from requests import get
import random

google_sheet_name = "寵物新聞"
start_date = (datetime.now() - timedelta(days=90)).date()
end_date = datetime.now().date()

keyword_list = ['"毛怪樂園"']

# replace " with ' for google sheet name
google_sheet_name_list = [keyword.replace('"', "") for keyword in keyword_list]


SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = r"credentials.json"
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)


def gsheet():
    client = gspread.authorize(credentials, client_factory=gspread.client.BackoffClient)

    workbook = client.open_by_key("1lsPW8u2zBmxIQiEHiKtJ2g6vajXN3k7Go-38quDuQY0")

    return workbook


def get_useragent():
    return random.choice(_useragent_list)


_useragent_list = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0",
]


def _req(term, results, lang, start, proxies, timeout):
    resp = get(
        url="https://www.google.com/search",
        headers={"User-Agent": get_useragent()},
        params={
            "q": term,
            "num": results + 2,  # Prevents multiple requests
            "hl": lang,
            "start": start,
        },
        proxies=proxies,
        timeout=timeout,
    )
    # print(term)
    resp.raise_for_status()
    return resp


class SearchResult:
    def __init__(self, url, title, description):
        self.url = url
        self.title = title
        self.description = description

    def __repr__(self):
        return f"SearchResult(url={self.url}, title={self.title}, description={self.description})"


def search(term, num_results=10, lang="en", proxy=None, advanced=False, sleep_interval=0, timeout=5):
    """Search the Google search engine"""

    # escaped_term = urllib.parse.quote_plus(term) # make 'site:xxx.xxx.xxx ' works.
    # print(escaped_term)
    # Proxy
    proxies = None
    if proxy:
        if proxy.startswith("https"):
            proxies = {"https": proxy}
        else:
            proxies = {"http": proxy}

    # Fetch
    start = 0
    while start < num_results:
        # Send request
        resp = _req(term, num_results - start, lang, start, proxies, timeout)

        # Parse
        soup = BeautifulSoup(resp.text, "html.parser")
        # print(soup)
        # return soup
        cannot_find = soup.find_all("b", string=term)
        if len(cannot_find) > 0:
            start += 1
            continue
        # print('here')
        # print(list(cannot_find))

        result_block = soup.find_all("div", attrs={"class": "g"})
        if len(result_block) == 0:
            start += 1
        for result in result_block:
            # Find link, title, description
            link = result.find("a", href=True)
            title = result.find("h3")
            description_box = result.find("div", {"style": "-webkit-line-clamp:2"})
            if description_box:
                description = description_box.text
                if link and title and description:
                    start += 1
                    if advanced:
                        yield SearchResult(link["href"], title.text, description)
                    else:
                        yield link["href"]
        sleep(sleep_interval)

        if start == 0:
            return []  # test_google_crawler.search("Google", advanced=True)


def collect_news(term, start_date, end_date):
    googlenews = GoogleNews(lang="zh-Hant", region="TW")
    result_df = pd.DataFrame()
    while start_date < end_date:
        start_str = start_date.strftime("%Y-%m-%d")
        before_str = (start_date + timedelta(days=3)).strftime("%Y-%m-%d")
        print(term + " after:" + start_str + " before:" + before_str)
        old_count = len(googlenews.results())
        googlenews.get_news(term + " after:" + start_str + " before:" + before_str)

        if old_count + 100 == len(googlenews.results()):
            print("too many news")
            start_date += timedelta(days=1)
            continue
        print(start_date, len(googlenews.results()))
        start_date += timedelta(days=3)
        tmp_result_def = pd.DataFrame(googlenews.results())
        tmp_result_def = tmp_result_def.drop_duplicates()

        for k, v in tmp_result_def.iterrows():
            str_date = v["date"]

            if "天前" in str_date:
                day = int(str_date.replace(" 天前", ""))
                tmp_result_def.loc[k, "date"] = (datetime.now() - timedelta(days=day)).strftime("%Y-%m-%d")
            elif "小時前" in str_date:
                hour = int(str_date.replace(" 小時前", ""))
                tmp_result_def.loc[k, "date"] = (datetime.now() - timedelta(hours=hour)).strftime("%Y-%m-%d")
            elif "分鐘前" in str_date:
                minute = int(str_date.replace(" 分鐘前", ""))
                tmp_result_def.loc[k, "date"] = (datetime.now() - timedelta(minutes=minute)).strftime("%Y-%m-%d")
            elif "昨天" in str_date:
                tmp_result_def.loc[k, "date"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                str_date = str_date.replace("年", "-").replace("月", "-").replace("日", "")

                tmp_result_def.loc[k, "date"] = parser.parse(str_date).strftime("%Y-%m-%d")
        tmp_result_def["keyword"] = term
        tmp_result_def["site"] = "google news"
        result_df = pd.concat([result_df, tmp_result_def])
    return result_df


def collect_ptt(term, start_date, end_date):
    result_list = []
    while start_date < end_date:
        # Set the date and period
        # google_news.start_date = (start_date.year, start_date.month, start_date.day)
        # google_news.period = '1d'  # Period of 1 day
        old_count = len(result_list)
        start_str = start_date.strftime("%Y-%m-%d")
        # end_str = end_date.strftime('%y-%m-%d')
        before_str = (start_date + timedelta(days=7)).strftime("%Y-%m-%d")
        # Get the news results
        print(term + " site:ptt.cc after:" + start_str + " before:" + before_str)
        result = search(
            term + " site:ptt.cc after:" + start_str + " before:" + before_str,
            lang="zh-Hant",
            advanced=True,
            num_results=10,
        )
        result_list.extend(list(result))
        if old_count + 100 == len(result_list):
            print("too many news")
            start_date += timedelta(days=1)
            continue
        # result_list.extend(results)
        # analyze the results, append them to a list, do whatever you need to do
        print(start_date, len(result_list))
        # Increment the start date by 1 day
        sleep(1)
        start_date += timedelta(days=7)
    test_list = []
    for item in result_list:
        test_list.append({"link": item.url, "title": item.title, "description": item.description})
    test_df = pd.DataFrame(test_list)
    for k, v in test_df.iterrows():
        str_date = v["description"].split("—")[0]

        if "天前" in str_date:
            day = int(str_date.replace(" 天前", ""))
            v["description"] = v["description"].replace(str_date, "")
            test_df.loc[k, "date"] = (datetime.now() - timedelta(days=day)).strftime("%Y-%m-%d")
        elif "小時前" in str_date:
            hour = int(str_date.replace(" 小時前", ""))
            v["description"] = v["description"].replace(str_date, "")
            test_df.loc[k, "date"] = (datetime.now() - timedelta(hours=hour)).strftime("%Y-%m-%d")
        elif "分鐘前" in str_date:
            minute = int(str_date.replace(" 分鐘前", ""))
            v["description"] = v["description"].replace(str_date, "")
            test_df.loc[k, "date"] = (datetime.now() - timedelta(minutes=minute)).strftime("%Y-%m-%d")
        elif "昨天" in str_date:
            v["description"] = v["description"].replace(str_date, "")
            test_df.loc[k, "date"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            v["description"] = v["description"].replace(str_date, "")
            str_date = str_date.replace("年", "-").replace("月", "-").replace("日", "")

            test_df.loc[k, "date"] = parser.parse(str_date).strftime("%Y-%m-%d")

    test_df["keyword"] = term
    test_df["site"] = "ptt"
    return test_df


# test_df["date"] =test_df["description"].str.split(" ")


def main():
    wb = gsheet()
    for keyword in keyword_list:
        source_sheet = wb.worksheet("每日爬")
        old_news_info = pd.DataFrame(source_sheet.get_values("A:K"))
        if len(old_news_info) > 0:
            old_news_info.columns = old_news_info.iloc[0]
            old_news_info = old_news_info[1:]

        result = collect_news(keyword, start_date, end_date)
        if "title" in result.columns:
            result = result[result["title"].str.contains(keyword.replace('"', ""))].drop_duplicates()

        result_ptt = collect_ptt(keyword, start_date, end_date)
        # result_dcard = collect_dcard(keyword, start_date, end_date)  # New Dcard search

        cleanning_df = pd.concat([result, result_ptt, old_news_info])
        cleanning_df = cleanning_df.reset_index(drop=True).drop_duplicates(["title", "description", "site"])
        cleanning_df = cleanning_df.fillna("")
        cleanning_df["date"] = pd.to_datetime(cleanning_df["date"])
        cleanning_df.sort_values(by=["date"], inplace=True, ascending=False)
        cleanning_df["date"] = cleanning_df["date"].dt.strftime("%Y-%m-%d")
        source_sheet.clear()
        source_sheet = wb.worksheet("每日爬")
        source_sheet.update([cleanning_df.columns.values.tolist()] + cleanning_df.values.tolist())


if __name__ == "__main__":
    main()
