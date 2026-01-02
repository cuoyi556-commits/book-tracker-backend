"""
豆瓣图书封面API服务
部署在Railway.app上，为前端提供豆瓣图书封面查询
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import io
import base64
import requests

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局WebDriver实例
driver = None


def get_driver():
    """获取或创建WebDriver实例"""
    global driver
    if driver is None:
        options = Options()
        options.add_argument('--headless')  # 无头模式
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # Railway环境特殊配置
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')

        driver = webdriver.Chrome(options=options)
    return driver


@app.route('/')
def home():
    """首页"""
    return jsonify({
        'service': '豆瓣图书封面API',
        'version': '1.0',
        'endpoints': {
            '/api/search': '搜索图书（支持ISBN和书名）',
            '/api/cover/<isbn>': '获取图书封面图片',
            '/health': '健康检查'
        }
    })


@app.route('/health')
def health():
    """健康检查"""
    try:
        # 测试WebDriver是否正常
        d = get_driver()
        return jsonify({'status': 'healthy', 'driver': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


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

        # 判断是ISBN还是书名
        is_isbn = query.replace('-', '').replace(' ', '').isdigit()

        d = get_driver()

        if is_isbn:
            # ISBN查询
            url = f"https://book.douban.com/isbn/{query}"
        else:
            # 书名搜索
            from urllib.parse import quote
            url = f"https://book.douban.com/subject_search?search_text={quote(query)}"

        d.get(url)
        time.sleep(2)

        # 解析页面
        soup = BeautifulSoup(d.page_source, 'html.parser')

        # 如果是书名搜索，需要找到第一个结果
        if not is_isbn:
            link = soup.find('a', class_='title-text')
            if link and link.get('href'):
                d.get(link['href'])
                time.sleep(2)
                soup = BeautifulSoup(d.page_source, 'html.parser')

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
        title_elem = soup.find('h1')
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

        return jsonify(info)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cover/<path:isbn>')
def get_cover(isbn):
    """
    获取图书封面图片（Base64格式）
    用于直接在HTML中显示
    """
    try:
        d = get_driver()
        url = f"https://book.douban.com/isbn/{isbn}"
        d.get(url)
        time.sleep(2)

        soup = BeautifulSoup(d.page_source, 'html.parser')
        cover_elem = soup.find('a', class_='nbg')

        if not cover_elem:
            return jsonify({'error': '未找到封面'}), 404

        img = cover_elem.find('img')
        if not img:
            return jsonify({'error': '未找到封面'}), 404

        cover_url = img.get('data-src') or img.get('src')
        if not cover_url:
            return jsonify({'error': '未找到封面URL'}), 404

        # 转换为大图
        cover_url = cover_url.replace('/spic/', '/lpic/')
        cover_url = cover_url.replace('/mpic/', '/lpic/')

        # 下载图片
        cookies = {cookie['name']: cookie['value'] for cookie in d.get_cookies()}

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': url
        }

        response = requests.get(cover_url, headers=headers, cookies=cookies, timeout=10)

        if response.status_code != 200 or len(response.content) < 5000:
            return jsonify({'error': '图片下载失败'}), 404

        # 返回图片
        return send_file(
            io.BytesIO(response.content),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name=f'{isbn}.jpg'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cover-base64/<path:isbn>')
def get_cover_base64(isbn):
    """
    获取图书封面图片（Base64格式）
    返回JSON格式的Base64编码图片
    """
    try:
        d = get_driver()
        url = f"https://book.douban.com/isbn/{isbn}"
        d.get(url)
        time.sleep(2)

        soup = BeautifulSoup(d.page_source, 'html.parser')
        cover_elem = soup.find('a', class_='nbg')

        if not cover_elem:
            return jsonify({'error': '未找到封面'}), 404

        img = cover_elem.find('img')
        if not img:
            return jsonify({'error': '未找到封面'}), 404

        cover_url = img.get('data-src') or img.get('src')
        if not cover_url:
            return jsonify({'error': '未找到封面URL'}), 404

        # 转换为大图
        cover_url = cover_url.replace('/spic/', '/lpic/')
        cover_url = cover_url.replace('/mpic/', '/lpic/')

        # 下载图片
        cookies = {cookie['name']: cookie['value'] for cookie in d.get_cookies()}

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': url
        }

        response = requests.get(cover_url, headers=headers, cookies=cookies, timeout=10)

        if response.status_code != 200 or len(response.content) < 5000:
            return jsonify({'error': '图片下载失败'}), 404

        # 转换为Base64
        base64_data = base64.b64encode(response.content).decode('utf-8')

        return jsonify({
            'isbn': isbn,
            'format': 'jpeg',
            'data': base64_data,
            'url': cover_url
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    try:
        # Railway使用PORT环境变量
        port = int(__import__('os').environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    finally:
        # 清理
        if driver:
            driver.quit()
