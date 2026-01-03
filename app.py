"""
豆瓣图书封面API服务
使用 requests + BeautifulSoup 爬取豆瓣图书信息（轻量级方案）
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
from urllib.parse import quote, unquote

app = Flask(__name__)
CORS(app)

# 配置
DOUBAN_SEARCH_URL = "https://www.douban.com/search"
DOUBAN_BASE = "https://book.douban.com/"
DOUBAN_BOOK_CAT = "1001"
DOUBAN_BOOK_URL_PATTERN = re.compile(".*/subject/(\\d+)/?")

# 请求头
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': DOUBAN_BASE,
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}


def random_sleep():
    """随机延迟，避免频繁请求"""
    time.sleep(random.uniform(0.1, 0.5))


def search_douban(query):
    """使用 requests 搜索豆瓣"""
    try:
        # 判断是ISBN还是书名
        is_isbn = query.replace('-', '').replace(' ', '').isdigit()

        if is_isbn:
            # ISBN 直接访问书籍页面
            url = f"{DOUBAN_BASE}isbn/{query}"
            return load_book_info(url)
        else:
            # 书名搜索
            return search_books_by_name(query)

    except Exception as e:
        print(f"搜索错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def search_books_by_name(query):
    """通过书名搜索"""
    try:
        # 搜索
        params = {"cat": DOUBAN_BOOK_CAT, "q": query}
        response = requests.get(DOUBAN_SEARCH_URL, params=params, headers=DEFAULT_HEADERS, timeout=10)

        if response.status_code not in [200, 201]:
            print(f"搜索失败: status={response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # 找到第一个搜索结果
        link = soup.find('a', class_='title-text')
        if not link or not link.get('href'):
            print("未找到搜索结果")
            return None

        # 获取书籍详情URL
        book_url = link['href']
        print(f"找到书籍: {book_url}")

        # 加载书籍详情
        return load_book_info(book_url)

    except Exception as e:
        print(f"书名搜索错误: {e}")
        return None


def load_book_info(url):
    """加载书籍详情"""
    try:
        random_sleep()

        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)

        if response.status_code not in [200, 201]:
            print(f"加载书籍失败: status={response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # 提取图书信息
        info = {
            'title': '',
            'author': [],
            'publisher': '',
            'pubdate': '',
            'isbn': '',
            'rating': '',
            'cover_url': ''
        }

        # 书名
        title_elem = soup.find('span', property='v:itemreviewed')
        if title_elem:
            info['title'] = title_elem.get_text().strip()

        # 作者
        author_elem = soup.find('span', string=lambda text: text and '作者:' in text)
        if author_elem:
            author_links = author_elem.find_all_next_siblings('a')
            info['author'] = [a.get_text().strip() for a in author_links if a.get_text().strip()]

        # 出版社
        pub_elem = soup.find('span', string=lambda text: text and '出版社:' in text)
        if pub_elem:
            info['publisher'] = pub_elem.next_sibling.strip() if pub_elem.next_sibling else ''

        # 出版日期
        date_elem = soup.find('span', string=lambda text: text and '出版年:' in text)
        if date_elem:
            info['pubdate'] = date_elem.next_sibling.strip() if date_elem.next_sibling else ''

        # ISBN
        isbn_elem = soup.find('span', string=lambda text: text and 'ISBN:' in text)
        if isbn_elem:
            info['isbn'] = isbn_elem.next_sibling.strip() if isbn_elem.next_sibling else ''

        # 评分
        rating_elem = soup.find('strong', class_='ll rating_num')
        if rating_elem:
            info['rating'] = rating_elem.get_text().strip()

        # 封面图片
        cover_elem = soup.find('a', class_='nbg')
        if cover_elem:
            img = cover_elem.find('img')
            if img:
                cover_url = img.get('data-src') or img.get('src')
                if cover_url:
                    # 转换为大图URL
                    cover_url = cover_url.replace('/spic/', '/lpic/')
                    cover_url = cover_url.replace('/mpic/', '/lpic/')
                    info['cover_url'] = cover_url

        print(f"成功获取书籍信息: {info['title']}")
        return info

    except Exception as e:
        print(f"加载书籍详情错误: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route('/')
def home():
    """首页"""
    return jsonify({
        'service': '豆瓣图书封面API',
        'version': '2.0',
        'method': 'requests (lightweight)',
        'endpoints': {
            '/api/search': '搜索图书（支持ISBN和书名）',
            '/health': '健康检查'
        }
    })


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'healthy', 'service': 'Douban Scraper (Lightweight)'})


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

        if result and result['title']:
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
