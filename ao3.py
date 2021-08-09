import requests
from pyquery import PyQuery as pq
from datetime import datetime, timedelta
import sys, re, os, json
import subprocess as subp
from os import path
import tempfile
import uuid
import time

host = 'archiveofourown.org'

pr = {
    # 'http': 'https://localhost:1080',
    # 'https': 'https://localhost:1080',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
}

def request_retry(method, url, retry=10, **kw):
    kw.setdefault('timeout', 10)
    for i in range(retry):
        try:
            return requests.request(method, url, **kw)
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            print(f'{url} retry {i}')
            if i == retry - 1: raise e

get_retry = lambda *args, **kwargs: \
    request_retry('GET', *args, **kwargs)


def get_article(html):
    root = pq(html)
    title = root('h2.title').text().strip()
    root('h2.title').remove()
    co = root('div.preface').html() + '\n' + \
         str(root('dl.meta')) + '\n' + \
         root('div.userstuff').html()
    return {
        'title': title,
        'content': co,
    }
    
def safe_mkdir(dir):
    try:
        os.mkdir(dir)
    except:
        pass
        
def safe_rmdir(dir):
    try:
        os.rmdir(dir)
    except:
        pass

def get_ids(html):
    root = pq(html)
    el_links = root.find('h4 a:first-of-type')
    return [
        pq(l).attr('href').split('/')[-1]
        for l in el_links
    ]

def batch(fname):
    
    ids = open(fname).read().split('\n')
    ids = list(filter(None, map(lambda x: x.strip(), ids)))
    
    name = path.basename(fname)
    name = re.sub(r'\.\w+$', '', name)
    ofname = f'out/{name}.epub'
    if path.exists(ofname):
        print(f'{ofname} 已存在')
        return
    safe_mkdir('out')
        
    articles = [{'title': name, 'content': ''}]
    i = 1
    while i < len(ids):
        id = ids[i]
        print(f'id: {id}')
        url = f'https://{host}/works/{id}?view_adult=true'
        r = get_retry(
            url, 
            headers=headers, 
            proxies=pr,
            timeout=8,
        )
        if r.status_code == 429:
            print('HTTP 429')
            time.sleep(10)
            continue
        html = r.text
        art = get_article(html)
        articles.append(art)
        i += 1
        
    gen_epub(articles, None, ofname)
    

def fetch(fname, st=None, ed=None, pg=1):
    now = datetime.now()
    st = now if st is None \
         else datetime.strptime(st, '%Y%m%d')
    ed = now if ed is None \
         else datetime.strptime(ed,'%Y%m%d')
    ed += timedelta(1)
    days_st = (now - ed).days
    days_ed = (now - st).days
    print(f'days start: {days_st}, days end: {days_ed}')
    f = open(fname, 'a')
    
    i = pg
    while True:
        print(f'page: {i}')
        url = f'https://{host}/works/search?utf8=%E2%9C%93&commit=Search&page={i}&work_search%5Brevised_at%5D={days_st}-{days_ed}+days&work_search%5Blanguage_id%5D=zh&work_search%5Bsort_direction%5D=desc&work_search%5Bsort_column%5D=revised_at'
        
        r = get_retry(
            url, 
            headers=headers, 
            proxies=pr,
            timeout=8,
        )
        if r.status_code == 429:
            print('HTTP 429')
            time.sleep(10)
            continue
        html = r.text
        ids = get_ids(html)
        if len(ids) == 0: break
        for id in ids:
            print(f'id: {id}')
            f.write(id + '\n')
            f.flush()
        
        i += 1
        
    f.close()

def gen_epub(articles, imgs, p):   
    imgs = imgs or {}

    dir = path.join(tempfile.gettempdir(), uuid.uuid4().hex) 
    safe_mkdir(dir)
    img_dir = path.join(dir, 'img')
    safe_mkdir(img_dir)
    
    for fname, img in imgs.items():
        fname = path.join(img_dir, fname)
        with open(fname, 'wb') as f:
            f.write(img)
    
    fname = path.join(dir, 'articles.json')
    with open(fname, 'w') as f:
        f.write(json.dumps(articles))
    
    args = f'gen-epub "{fname}" -i "{img_dir}" -p "{p}"'
    subp.Popen(args, shell=True).communicate()
    safe_rmdir(dir)

def main():
    op = sys.argv[1]
    if op == 'fetch':
        fetch(
            sys.argv[2],
            sys.argv[3] if len(sys.argv) > 3 else None,
            sys.argv[4] if len(sys.argv) > 4 else None,
            int(sys.argv[5]) if len(sys.argv) > 5 else 1,
        )
    elif op == 'batch':
        batch(sys.argv[2])
        
if __name__ == '__main__': main()
