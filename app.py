"""
豆瓣图书封面API服务
使用Selenium爬取豆瓣图书信息，优化资源使用
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import requests
import os

app = Flask(__name__)
CORS(app)

# 超时设置
REQUEST_TIMEOUT = 25


class DriverManager:
    """管理WebDriver的上下文管理器，确保用完即关闭"""

    @staticmethod
    def get_driver():
        """创建新的WebDriver实例"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--single-process')  # 单进程模式，减少内存使用
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        try:
            # 指定 Chrome 二进制文件路径
            options.binary_location = '/usr/bin/google-chrome'

            # 使用webdriver-manager自动管理ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(20)
            driver.set_script_timeout(10)
            return driver
        except Exception as e:
            print(f"创建WebDriver失败: {e}")
            return None


@app.route('/')
def home():
    """首页"""
    return jsonify({
        'service': '豆瓣图书封面API',
        'version': '1.0',
        'endpoints': {
            '/api/search': '搜索图书（支持ISBN和书名）',
            '/health': '健康检查'
        }
    })


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'healthy', 'service': 'Douban Scraper'})


def search_douban(query):
    """使用Selenium搜索豆瓣"""
    driver = None
    try:
        # 判断是ISBN还是书名
        is_isbn = query.replace('-', '').replace(' ', '').isdigit()

        driver = DriverManager.get_driver()
        if not driver:
            return None

        if is_isbn:
            url = f"https://book.douban.com/isbn/{query}"
        else:
            from urllib.parse import quote
            url = f"https://book.douban.com/subject_search?search_text={quote(query)}"

        driver.get(url)
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 如果是书名搜索，需要找到第一个结果
        if not is_isbn:
            link = soup.find('a', class_='title-text')
            if link and link.get('href'):
                driver.get(link['href'])
                time.sleep(2)
                soup = BeautifulSoup(driver.page_source, 'html.parser')

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

        return info

    except Exception as e:
        print(f"搜索错误: {e}")
        return None
    finally:
        # 确保关闭driver释放资源
        if driver:
            try:
                driver.quit()
            except:
                pass


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

        result = search_douban(query)

        if result and result['title']:
            return jsonify(result)
        else:
            return jsonify({'error': '未找到相关图书'}), 404

    except Exception as e:
        print(f"搜索错误: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
