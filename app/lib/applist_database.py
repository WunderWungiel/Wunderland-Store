"""AppList database backend"""

import os
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement
from urllib.parse import quote

from flask import request
import psycopg2
import psycopg2.extras

from . import conn


def version():
    root = Element("xml")
    message = Element("message")
    message.text = "Changelog for AppList 1.0 Build 298: *Minor fixes for app changelog display and version selection"
    url = Element("url")
    url.text = "http://repo.applist.schumi1331.de/AppList.sis"
    root.append(message)
    root.append(url)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)


def changelog():
    root = Element("xml")
    message = Element("message")
    message.text = """Changelog for Wunderland Store 1.0 Build 1:
* Using AppList as base app
* Supports: apps, icons, downloading"""
    url = Element("url")
    root.append(message)
    root.append(url)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)


# !!! Replace right side and comments with YOUR categories' IDs!
def applist_to_wunderland(category_id):
    categories = {
        0: ("all", "apps"),  # All apps
        1: (2, "apps"),  # Weather & GPS
        2: (3, "apps"),  # Office
        3: (4, "apps"),  # Camera, photos, videos
        4: (11, "apps"),  # Emulator
        5: (5, "apps"),  # File manager & cloud
        6: (1, "themes"),  # Themes
        7: (7, "apps"),  # Internet
        8: (8, "apps"),  # Music
        10: (9, "apps"),  # Social
        11: (12, "apps"),  # Extras
        12: (10, "apps"),  # Tools
        13: (1, "apps"),  # Other apps
        20: ("all", "games"),  # All games
        21: (2, "games"),  # Action
        22: (3, "games"),  # Adventure
        23: (6, "games"),  # Puzzles & cards
        24: (5, "games"),  # Strategy (represented as Tactic in AppList)
        25: (4, "games"),  #  Sports (represented as Extra in AppList)
        26: (1, "games")  # Other games

    }

    return categories.get(category_id)


# !!! Replace left side and comments with YOUR categories' IDs!
def wunderland_to_applist(category_id, content_type):
    categories = {
        "apps": {
            "all": 0,  # All apps
            2: 1,  # Weather & GPS
            3: 2,  # Camera, photos, videos
            4: 3,  # Emulator
            5: 5,  # File manager & cloud
            7: 7,  # Internet
            8: 8,  # Music
            9: 10,  # Social
            10: 12,  # Tools
            11: 4,  # Emulator
            12: 11,  # Extras
            1: 13  # Other apps
        },
        "games": {
            "all": 20,  # All games
            2: 21,  # Action
            3: 22,  # Adventure
            6: 23,  # Puzzles & cards
            5: 24,  # Strategy (represented as Tactic in AppList)
            4: 25,  # Sports (represented as Extra in AppList)
            1: 26  # Other games
        },
        "themes": {
            1: 6  # Themes
        }
    }

    return categories.get(content_type).get(category_id)


def format_results(results, content_type, widget=False):

    if not results:
        results = []

    root = Element("applist")
    minversion = Element("minversion")
    minversion.text = "1.0.298"
    root.append(minversion)

    for row in results:

        if content_type:
            c = content_type
        else:
            c = row['content_type']
        prefix = c.rstrip("s")

        row = {k: v.strip() if isinstance(v, str) else v for (k, v) in row.items()}

        app = Element("app")

        if widget:
            
            id = SubElement(app, "id")
            id.text = str(row['id'])
            uid = SubElement(app, "uid")
            if row['uid']:
                uid.text = row['uid']
            uidstore = SubElement(app, "uidstore")
            uidunsigned = SubElement(app, "uidunsigned")
            version = SubElement(app, "version")
            version.text = row['version']
            versionstore = SubElement(app, "versionstore")
            versionunsigned = SubElement(app, "unsigned")
            versiondate = SubElement(app, "version")
            versiondate.text = "2024-03-30 20:54"
            versiondatestore = SubElement(app, "versiondatestore")
            versiondateunsigned = SubElement(app, "versiondateunsigned")

        else:

            id = SubElement(app, "id")
            id.text = str(row['id'])
            name = SubElement(app, "name")
            name.text = row['title']
            uid = SubElement(app, "uid")
            if row['uid']:
                uid.text = row['uid']
            uidstore = SubElement(app, "uidstore")
            uidunsigned = SubElement(app, "uidunsigned")
            icon = SubElement(app, "icon")
            icon.text = f"http://{request.host}/static/content/icons/" + os.path.join(c, row['img'])
            version = SubElement(app, "version")
            version.text = row['version']
            versionstore = SubElement(app, "versionstore")
            versionunsigned = SubElement(app, "unsigned")
            versiondate = SubElement(app, "version")
            versiondate.text = "2024-03-30 20:54"
            versiondatestore = SubElement(app, "versiondatestore")
            versiondateunsigned = SubElement(app, "versiondateunsigned")
            category = SubElement(app, "category")
            category.text = str(wunderland_to_applist(row['category'], c))
            language = SubElement(app, "language")
            language.text = "EN"
            
            os_el = SubElement(app, "os")
            os_el.text = "5.2,5.3,5.4,5.5"
            developer = SubElement(app, "developer")
            developer.text = row['publisher']
            mail = SubElement(app, "mail")
            website = SubElement(app, "website")
            website.text = f"http://{request.host}/{prefix}/{row['id']}"
            twitter = SubElement(app, "twitter")
            facebook = SubElement(app, "facebook")
            if row['addon_file']:
                facebook.text = f"http://{request.host}/static/content/files/{row['addon_file']}"
            donation = SubElement(app, "donation")
            price = SubElement(app, "price")
            price.text = "0.00"
            description = SubElement(app, "description")
            if row['description']:

                row['description'].strip()
                description.text = row['description']

            if row['addon_message']:
                description.text += f"\n\nExtra file: {row['addon_message']}"
            image1 = SubElement(app, "image1")
            image2 = SubElement(app, "image2")
            image3 = SubElement(app, "image3")
            image4 = SubElement(app, "image4")
            image5 = SubElement(app, "image5")
            if row['image1']:
                image1.text = f"http://{request.host}/static/content/screenshots/{c}/{row['image1']}"
            if row['image2']:
                image2.text = f"http://{request.host}/static/content/screenshots/{c}/{row['image2']}"
            if row['image3']:
                image3.text = f"http://{request.host}/static/content/screenshots/{c}/{row['image3']}"
            if row['image4']:
                image4.text = f"http://{request.host}/static/content/screenshots/{c}/{row['image4']}"
            tags = SubElement(app, "tags")
            changelog = SubElement(app, "changelog")
            unsignednote = SubElement(app, "unsignednote")
            download = SubElement(app, "download")
            download.text = "http://" + quote(f"{request.host}/static/content/files/{row['file']}")
            downloadsize = SubElement(app, "downloadsize")
            downloadsize.text = "0"
            downloadstore = SubElement(app, "downloadstore")
            downloadunsigned = SubElement(app, "downloadunsigned")
            downloadunsignedsize = SubElement(app, "downloadunsignedsize")

        root.append(app)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)


def get_content(id=None, category=None, start=None, latest=None, count=None, search=None, widget=None, content_type=None):

    platformIds = ("s60", "symbian3")
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if id:
        if id.isdigit():
            id = int(id)
            ids = None
        else:
            try:
                ids = [int(id) for id in id.split(",")]
            except:
                ids = None
            id = None
    else:
        id, ids = None, None
    
    start = int(start) if start else None
    count = int(count) if count else None
    
    if category:
        category = int(category)
        new_category, content_type = applist_to_wunderland(category)
    else:
        new_category = None

    if latest:
        latest = True if latest == "true" else False
    if widget:
        widget = True if widget == "true" else False

    # base_query = f"SELECT * FROM {content_type}"
    # conditions = {}
    # if new_category is not None and new_category != "all":
        

    query = f"SELECT * FROM {content_type}"
    args = []
    where = False

    if new_category is not None and new_category != "all":
        query += " WHERE category=%s"
        args.append(new_category)
        where = True
    if platformIds:
        if not where:
            query += " WHERE"
            where = True
        else:
            query += " AND"
        query += " ("
        for platformId in platformIds:
            query += "platform=%s OR "
            args.append(platformId)
        query += "platform IS NULL)"
    if id or ids:
        if not where:
            query += " WHERE"
            where = True
        else:
            query += " AND"
        if id:
            query += " id=%s"
            args.append(id)
        elif ids:
            query += " ("
            for i, id in enumerate(ids):
                if i != len(ids)-1:
                    query += "id=%s OR "
                else:
                    query += "id=%s)"
                args.append(id)
    if start:
        if not where:
            query += " WHERE"
            where = True
        else:
            query += " AND"
        query += " id > %s"
        args.append(start)
    if search:
        if not where:
            query += " WHERE"
            where = True
        else:
            query += " AND"
        query += " title iLIKE %s"
        args.append(f"%{search}%")
    
    if not where:
        query += " WHERE"
        where = True
    else:
        query += " AND"
    query += " visible=true"

    if search:
        
        all_results = []

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, tuple(args))
        results = cursor.fetchall()
        cursor.close()
        for i, result in enumerate(results):
            results[i]["content_type"] = "apps"
        all_results += results

        query = query.replace("FROM apps", "FROM games", 1)

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, tuple(args))
        results = cursor.fetchall()
        cursor.close()
        for i, result in enumerate(results):
            results[i]["content_type"] = "games"
        all_results += results

        query = query.replace("FROM games", "FROM themes", 1)

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, tuple(args))
        results = cursor.fetchall()
        cursor.close()
        for i, result in enumerate(results):
            results[i]["content_type"] = "themes"
        all_results += results

        results_xml = format_results(all_results, None, widget)

        return results_xml

    if latest and count:
        query += " ORDER BY id DESC LIMIT %s"
        args.append(count)
    else:
        query += " ORDER BY id DESC"

    cursor.execute(query, args)
    results = cursor.fetchall()
    cursor.close()

    results_xml = format_results(results, content_type, widget)
    return results_xml
