"""
豆瓣图书封面API服务
基于 calibre-web-douban-api 插件改造
使用 requests + lxml 爬取豆瓣图书信息（轻量级方案）
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import re
import time
import random
from urllib.parse import urlparse, unquote
from lxml import etree
from functools import lru_cache
import os

app = Flask(__name__)
CORS(app)

# 配置（完全来自 calibre-web-douban-api 插件）
DOUBAN_SEARCH_URL = "https://www.douban.com/search"
DOUBAN_BASE = "https://book.douban.com/"
DOUBAN_BOOK_CAT = "1001"
DOUBAN_BOOK_CACHE_SIZE = 500
DOUBAN_CONCURRENCY_SIZE = 5
DOUBAN_BOOK_URL_PATTERN = re.compile(".*/subject/(\\d+)/?")
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3573.0 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate',
    'Referer': DOUBAN_BASE
}


# ==================== 插件中的 DoubanBookHtmlParser 类 ====================
class DoubanBookHtmlParser:
    def __init__(self):
        self.id_pattern = DOUBAN_BOOK_URL_PATTERN
        self.date_pattern = re.compile("(\\d{4})-(\\d+)")
        self.tag_pattern = re.compile("criteria = '(.+)'")

    def parse_book(self, url, book_content):
        """解析书籍详情，返回字典格式"""
        html = etree.HTML(book_content)

        # 使用插件中相同的 XPath 逻辑
        title = self.get_text(html.xpath("//span[@property='v:itemreviewed']"))

        # 获取 URL
        share_element = html.xpath("//a[@data-url]")
        if len(share_element):
            url = share_element[0].attrib['data-url']

        # 获取 ID
        id_match = self.id_pattern.match(url)
        book_id = id_match.group(1) if id_match else ""

        # 获取封面
        img_element = html.xpath("//a[@class='nbg']")
        cover = ''
        if len(img_element):
            cover = img_element[0].attrib['href']
            if not cover or cover.endswith('update_image'):
                cover = ''

        # 获取评分
        rating = self.get_rating(html.xpath("//strong[@property='v:average']"))

        # 获取作者、出版社等信息
        authors = []
        publisher = ""
        pubdate = ""
        isbn = ""

        elements = html.xpath("//span[@class='pl']")
        for element in elements:
            text = self.get_text(element)
            if text.startswith("作者") or text.startswith("译者"):
                authors.extend([self.get_text(author_element) for author_element in
                             filter(self.author_filter, element.findall("..//a"))])
            elif text.startswith("出版社"):
                publisher = self.get_tail(element)
            elif text.startswith("出版年"):
                pubdate = self.get_publish_date(self.get_tail(element))
            elif text.startswith("ISBN"):
                isbn = self.get_tail(element)

        return {
            'title': title,
            'author': authors,
            'publisher': publisher,
            'pubdate': pubdate,
            'isbn': isbn,
            'rating': str(rating),
            'cover_url': cover
        }

    def get_tags(self, book_content):
        tag_match = self.tag_pattern.findall(book_content)
        if len(tag_match):
            return [tag.replace('7:', '') for tag in
                    filter(lambda tag: tag and tag.startswith('7:'), tag_match[0].split('|'))]
        return []

    def get_publish_date(self, date_str):
        if date_str:
            date_match = self.date_pattern.fullmatch(date_str)
            if date_match:
                date_str = "{}-{}-1".format(date_match.group(1), date_match.group(2))
        return date_str

    def get_rating(self, rating_element):
        return float(self.get_text(rating_element, '0')) / 2

    def author_filter(self, a_element):
        a_href = a_element.attrib['href']
        return '/author' in a_href or '/search' in a_href

    def get_text(self, element, default_str=''):
        text = default_str
        if len(element) and element[0].text:
            text = element[0].text.strip()
        elif isinstance(element, etree._Element) and element.text:
            text = element.text.strip()
        return text if text else default_str

    def get_tail(self, element, default_str=''):
        text = default_str
        if isinstance(element, etree._Element) and element.tail:
            text = element.tail.strip()
            if not text:
                text = self.get_text(element.getnext(), default_str)
        return text if text else default_str


# ==================== 插件中的 DoubanBookLoader 类 ====================
class DoubanBookLoader:
    def __init__(self):
        self.book_parser = DoubanBookHtmlParser()

    @lru_cache(maxsize=DOUBAN_BOOK_CACHE_SIZE)
    def load_book(self, url):
        book = None
        self.random_sleep()
        start_time = time.time()
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if res.status_code in [200, 201]:
            print("下载书籍:{}成功,耗时{:.0f}ms".format(url, (time.time() - start_time) * 1000))
            book_detail_content = res.content
            book = self.book_parser.parse_book(url, book_detail_content.decode("utf8"))
        return book

    def random_sleep(self):
        random_sec = random.random() / 10
        print("Random sleep time {}s".format(random_sec))
        time.sleep(random_sec)


# ==================== 插件中的 DoubanBookSearcher 类 ====================
class DoubanBookSearcher:
    def __init__(self):
        self.book_loader = DoubanBookLoader()

    def calc_url(self, href):
        query = urlparse(href).query
        params = {item.split('=')[0]: item.split('=')[1] for item in query.split('&')}
        url = unquote(params['url'])
        if DOUBAN_BOOK_URL_PATTERN.match(url):
            return url

    def load_book_urls_new(self, query):
        url = DOUBAN_SEARCH_URL
        params = {"cat": DOUBAN_BOOK_CAT, "q": query}
        res = requests.get(url, params, headers=DEFAULT_HEADERS, timeout=10)
        book_urls = []
        if res.status_code in [200, 201]:
            html = etree.HTML(res.content)
            alist = html.xpath('//a[@class="nbg"]')
            for link in alist:
                href = link.attrib['href']
                parsed = self.calc_url(href)
                if parsed and len(book_urls) < DOUBAN_CONCURRENCY_SIZE:
                    book_urls.append(parsed)
        return book_urls

    def search_books(self, query):
        book_urls = self.load_book_urls_new(query)
        if not book_urls:
            return None
        # 返回第一个结果
        return self.book_loader.load_book(book_urls[0])


# ==================== Flask API 路由 ====================
@app.route('/')
def home():
    """首页"""
    return jsonify({
        'service': '豆瓣图书封面API',
        'version': '2.0',
        'method': 'requests + lxml (based on calibre-web-douban-api plugin)',
        'source': 'https://github.com/fugary/calibre-web-douban-api',
        'endpoints': {
            '/api/search': '搜索图书（支持ISBN和书名）',
            '/health': '健康检查'
        }
    })


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'healthy', 'service': 'Douban Scraper (Lightweight)'})


def search_douban(query):
    """使用插件的逻辑搜索豆瓣"""
    try:
        # 判断是ISBN还是书名
        is_isbn = query.replace('-', '').replace(' ', '').isdigit()

        if is_isbn:
            # ISBN 直接访问书籍页面
            url = f"{DOUBAN_BASE}isbn/{query}"
            searcher = DoubanBookSearcher()
            loader = DoubanBookLoader()
            result = loader.load_book(url)
            return result if result and result.get('title') else None
        else:
            # 书名搜索
            searcher = DoubanBookSearcher()
            result = searcher.search_books(query)
            return result if result and result.get('title') else None

    except Exception as e:
        print(f"搜索错误: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route('/api/search', methods=['GET', 'POST'])
def search_book():
    """
    搜索图书信息
    参数：
        - query: ISBN或书名
    返回：图书信息JSON
    """
    try:
        # 获取查询参数
        if request.method == 'POST':
            data = request.get_json()
            query = data.get('query', '')
        else:
            query = request.args.get('query', '')

        if not query:
            return jsonify({'error': '请提供query参数'}), 400

        print(f"搜索书籍: {query}")
        result = search_douban(query)

        if result and result.get('title'):
            return jsonify(result)
        else:
            return jsonify({'error': '未找到相关图书'}), 404

    except Exception as e:
        print(f"搜索错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
