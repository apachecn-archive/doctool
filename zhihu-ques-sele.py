import re
import sys
import time
import traceback
from os import path
from pyquery import PyQuery as pq
from EpubCrawler.util import request_retry
from EpubCrawler.img import process_img
from EpubCrawler.config import config as cralwer_config
from datetime import datetime
from GenEpub import gen_epub
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

cralwer_config['optiMode'] = 'thres'
cralwer_config['imgSrc'] = ['data-original', 'src']
DIR = path.dirname(path.abspath(__file__))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36'

def d(name):
    return path.join(DIR, name)

def fname_escape(name):
    return name.replace('\\', '＼') \
               .replace('/', '／') \
               .replace(':', '：') \
               .replace('*', '＊') \
               .replace('?', '？') \
               .replace('"', '＂') \
               .replace('<', '＜') \
               .replace('>', '＞') \
               .replace('|', '｜')
    
    
# 滚动到底
def scroll_to_bottom(driver):
    driver.execute_script('''
        document.documentElement.scrollTop = 100000000
    ''')
    
# 判断是否到底
def if_reach_bottom(driver):
    return driver.execute_script('''
        return document.querySelector('.QuestionAnswers-answerButton') != null
    ''')    
    
# 获取最后一个 AID
def get_last_aid(driver):
    return driver.execute_script('''
        var ansLi = document.querySelectorAll('.AnswerItem')
        return (ansLi.length == 0)? '': ansLi[ansLi.length - 1].getAttribute('name')
    ''')   

# 获取 AID 数量
def get_aid_count(driver):
    return driver.execute_script('''
        var ansLi = document.querySelectorAll('.AnswerItem')
        return ansLi.length
    ''')  
    
# 获取回答数量
def get_ans_count(driver):
    return driver.execute_script('''
        var el = document.querySelector('h4.List-headerText')
        if (!el) return 0
        var text = el.innerText.replace(',', '')
        var m = /\d+/.exec(text)
        if (!m) return 0
        return Number.parseInt(m[0])
    ''')  
    
# 获取整个页面 HTML
def get_html(driver):
    return driver.execute_script('''
        return document.documentElement.outerHTML
    ''')    
    
# 获取文章列表
def get_articles(html, qid):
    rt = pq(html)
    rt.remove('noscript, .GifPlayer-icon, a svg')
    title = '知乎问答：' + fname_escape(rt('h1.QuestionHeader-title').eq(0).text())
    co = f'''
        <blockquote>来源：<a href='https://www.zhihu.com/question/{qid}'>https://www.zhihu.com/question/{qid}</a></blockquote>
    '''
    articles = [{'title': title, 'content': co}]
    el_ansLi = rt('.AnswerItem')
    for i in range(len(el_ansLi)):
        el = el_ansLi.eq(i)
        el_au = el.find('.UserLink-link')
        au_name = (el_au.text() or '匿名用户').strip()
        au_url = el_au.attr('href') or ''
        el_time = el.find('.ContentItem-time>a')
        co_url = el_time.attr('href')
        vote = el.find('.VoteButton--up').attr('aria-label').strip()[3:]
        upd_time = el_time.text().strip()[4:]
        co = el.find('.RichText').html()
        co = f'''
            <blockquote>
                <p>作者：<a href='{au_url}'>{au_name}</a></p>
                <p>赞同数：{vote}</p>
                <p>编辑于：<a href='{co_url}'>{upd_time}</a></p>
            </blockquote>
            {co}
        '''
        articles.append({'title': au_name, 'content': co})
    return articles

def main():
    qid = sys.argv[1]
    url = f'https://www.zhihu.com/question/{qid}'
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_argument(f'--user-agent={UA}')
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)
    driver.set_script_timeout(1000)
    # StealthJS
    stealth = open(d('stealth.min.js')).read()
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": stealth
    })
    driver.get(url)
    # 关闭登录对话框
    driver.execute_script('''
        var cls_btn = document.querySelector('.Modal-closeButton')
        if (cls_btn) cls_btn.click()
    ''')
    ansCnt = get_ans_count(driver)
    # 如果没有到底就一直滚动
    while not if_reach_bottom(driver):
        try:
            cnt = get_aid_count(driver)
            print(f'reach bottom: false, count: {cnt}/{ansCnt}')
            scroll_to_bottom(driver)
            # time.sleep(1)
        except:
            traceback.print_exc()
    
    html = get_html(driver)
    # time.sleep(3600)
    driver.close()
    articles = get_articles(html, qid)
    imgs = {}
    
    for art in articles:
        art['content'] = process_img(
            art['content'], imgs, 
            img_prefix='../Images/',
            page_url=url,
        )
        
    gen_epub(articles, imgs)
    
if __name__ == '__main__': main()
