from datetime import datetime
import math

from flask import Blueprint, request, redirect, render_template

from . import database as db

news = Blueprint("news", __name__, template_folder="templates")

@news.route("/feed.xml")
def _feed():

    now = datetime.now()
    now_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    news = db.get_news()

    xml = f'''<?xml version="1.0" encoding="windows-1252"?>
<rssversion="2.0">
    <channel>
        <title>Wunderland Store</title>
        <description>News, content and programs for retro devices.</description>
        <link>http://ovi.wunderwungiel.pl/</link>
        <lastBuildDate>{now_str}</lastBuildDate>'''
    
    for content in news:
        xml += f'''
        <item>
            <title>{content['title']}</title>
            <link>http://{request.host}/news/{content['id']}</link>
            <description></description>
            <pubDate>{content['date']}</pubDate>
            <guid>http://{request.host}/news/{content['id']}</guid>
        </item>'''

    xml += '''
    </channel>
</rss>'''

    return xml

@news.route("/news/<int:news_id>")
def _news(news_id):

    content = db.get_news(news_id=news_id)[0]

    return render_template("textpage.html", title=content['title'], content=content['content'], share=True)

@news.route("/")
def __root():
    return redirect("/home/")

@news.route("/home")
def _root():

    news = db.get_news()
    if not news:
        return render_template("index.html", news=[], next_page=None, previous_page=None)
    
    pageId = request.args.get('pageId')

    if not pageId:
        pageId = 1
    else:
        pageId = int(pageId)
    
    if (pageId * 10) > math.ceil(len(news) / 10) * 10:
        if pageId != 1:
            return redirect(f"/home/?pageId=1")
    else:
        if ((pageId + 1) * 10) < math.ceil(len(news) / 10) * 10:
            if pageId != 1:
                next_page = pageId + 1
            else:
                next_page = None
            if pageId != math.ceil(len(news) / 10):
                previous_page = pageId - 1
            else:
                previous_page = None
        else:
            next_page = None
            previous_page = None
    
    first_index = pageId - 1
    last_index = first_index + 10

    news_to_show = news[first_index:last_index]
    
    return render_template("index.html", news=news_to_show, next_page=next_page, previous_page=previous_page)