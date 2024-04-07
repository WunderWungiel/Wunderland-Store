import os
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, SubElement
from urllib.parse import quote

from flask import request
import psycopg2
import psycopg2.extras

from .config import config
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
    message.text = """Changelog for AppList 1.0 Build 298:
*Minor fixes for app changelog display and version selection


Changelog for AppList 1.0 Build 297:
*Added pull to refresh
*Improved successful installation detection
*Minor bug fixes


Changelog for AppList 1.0 Build 293:
*Fixed Czech language code for displaying apps/descriptions in that language


Changelog for AppList 1.0 Build 292:
*Added support for localized app descriptions


Changelog for AppList 1.0 Build 291:
*Fixed minor bugs related with updating and installing unsigned apps


Changelog for AppList 1.0 Build 290:
*Fixed displaying 'Now opening Nokia Store' note for apps that are not downloaded through the Nokia Store


Changelog for AppList 1.0 Build 289:
*Added Greek translation (thanks to Michael)
(this is more a release to give a note, that I'm still there ;) )


Changelog for AppList 1.0 Build 288:
*Optimized language functions and translated categories
*Added Education category
*Fixed search bar in dark layout
*Added message when search fails or no results found
*Links open in your system's default browser
*Fixed bug which caused AAS feed to load when it was disabled in the Settings
*Added Spanish translation (thanks to asturcon3)
*Updated translations


Changelog for AppList 1.0 Build 285:
*Improved explanation of what unsigned apps are
*Edited installation error note when installing an unsigned app failed
*Added Russian and Ukrainian translation (thanks to Alexey)
*Added Portuguese translation (thanks to Dan)
*Fixed not displaying changelog in the AppList Update page
*Minor improvements


Changelog for AppList 1.0 Build 281:
*Added displaying app size to Detail Page
*Added logic to check if enough space is available on a drive of your phone to download an app
*Added option to view full changelog history (right bottom icon > About AppList)
*Pressing Enter on Search page starts search
*Fixed not loading Hungarian translation
*Added French translation (thanks to Erwan)
*Updated Hungarian translation


Changelog for AppList 1.0 Build 275:
*Added Hungarian and Italian language files (sorry, forgot :) )


Changelog for AppList 1.0 Build 274:
Homescreen widget:
*Fixed launching AppList from the widget icon (thanks to huellif)
*Fixed negative new apps count

App:
*Added Hungarian and Italian UI translation (thanks to dankoi and Bruno)
*Fixed updating apps in the Nokia Store
*Added unsigned flag to requests to display apps that are only released as unsigned
*Fixed wrong update count in the bubble & widget
*Added further languages and updated ISO codes for languages (you may need to re-check your language settings)"""
    url = Element("url")
    root.append(message)
    root.append(url)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)

def applist_to_ovistore(categoryId):
    categories = {
        0: ("all", "apps"),
        1: (2, "apps"),
        2: (3, "apps"),
        3: (4, "apps"),
        5: (5, "apps"),
        6: (6, "apps"),
        7: (7, "apps"),
        8: (8, "apps"),
        10: (9, "apps"),
        12: (10, "apps"),
        13: (1, "apps")
    }

    return categories.get(categoryId)

def ovistore_to_applist(categoryId, content_type):
    categories_apps = {
        "all" : 0,
        2: 1,
        3: 2,
        4: 3,
        5: 5,
        6: 6,
        7: 7,
        8: 8,
        9: 10,
        10: 12,
        1: 13
    }

    return categories_apps.get(categoryId)

def format_results(results, content_type, widget=False):

    if not results:
        results = []

    root = Element("applist")
    minversion = Element("minversion")
    minversion.text = "1.0.298"
    root.append(minversion)

    for row in results:

        app = Element("app")

        if widget:
            
            id = SubElement(app, "id")
            id.text = str(row['id'])
            uid = SubElement(app, "uid")
            uid.text = "0xA1331003"
            uidstore = SubElement(app, "uidstore")
            uidunsigned = SubElement(app, "uidunsigned")
            version = SubElement(app, "version")
            version.text = row['version'] #
            versionstore = SubElement(app, "versionstore")
            versionunsigned = SubElement(app, "unsigned")
            versiondate = SubElement(app, "version")
            versiondate.text = "2024-03-30 20:54" #
            versiondatestore = SubElement(app, "versiondatestore")
            versiondateunsigned = SubElement(app, "versiondateunsigned")

        else:

            id = SubElement(app, "id")
            id.text = str(row['id'])
            name = SubElement(app, "name")
            name.text = row['title']
            uid = SubElement(app, "uid")
            uid.text = "0xA1331003" #
            uidstore = SubElement(app, "uidstore")
            uidunsigned = SubElement(app, "uidunsigned")
            icon = SubElement(app, "icon")
            icon.text = "http://ovi.wunderwungiel.pl/static/store/" + os.path.join(content_type, row['img'])
            version = SubElement(app, "version")
            version.text = row['version']
            versionstore = SubElement(app, "versionstore")
            versionunsigned = SubElement(app, "unsigned")
            versiondate = SubElement(app, "version")
            versiondate.text = "2024-03-30 20:54"
            versiondatestore = SubElement(app, "versiondatestore")
            versiondateunsigned = SubElement(app, "versiondateunsigned")
            category = SubElement(app, "category")
            category.text = str(ovistore_to_applist(row['category'], "apps"))
            language = SubElement(app, "language")
            language.text = "EN"
            os_el = SubElement(app, "os")
            os_el.text = "5.2,5.3,5.4,5.5"
            developer = SubElement(app, "developer")
            developer.text = row['publisher']
            mail = SubElement(app, "mail")
            website = SubElement(app, "website")
            twitter = SubElement(app, "twitter")
            facebook = SubElement(app, "facebook")
            donation = SubElement(app, "donation")
            price = SubElement(app, "price")
            price.text = "0.00"
            description = SubElement(app, "description")
            description.text = row['description'].strip().replace("<br>", "\n").replace("<br />", "\n").replace("<br/>", "\n")
            tags = SubElement(app, "tags")
            changelog = SubElement(app, "changelog")
            unsignednote = SubElement(app, "unsignednote")
            download = SubElement(app, "download")
            download.text = "http://" + quote(f"ovi.wunderwungiel.pl/static/files/{row['file']}") #
            downloadsize = SubElement(app, "downloadsize")
            downloadsize.text = "0" #
            downloadstore = SubElement(app, "downloadstore")
            downloadunsigned = SubElement(app, "downloadunsigned")
            downloadunsignedsize = SubElement(app, "downloadunsignedsize")

        root.append(app)

    ET.indent(root)

    return ET.tostring(root, encoding='unicode', short_empty_elements=False)

def get_content(id=None, category=None, start=None, latest=None, count=None, search=None, widget=None, content_type=None):

    platformId = "s60"
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if id:
        if id.isdigit():
            try:
                id = int(id)
            except:
                id = None
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
        new_category, content_type = applist_to_ovistore(category)
    else:
        new_category = None

    if latest:
        latest = True if latest == "true" else False
    if widget:
        widget = True if widget == "true" else False

    query = f"SELECT * FROM {content_type}"
    args = []
    where = False

    if new_category is not None and new_category != "all":
        query += " WHERE category=%s"
        args.append(new_category)
        where = True
    if platformId != "all":
        if not where:
            query += " WHERE"
            where = True
        else:
            query += " AND"
        query += " platform=%s"
        args.append(platformId)
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
    if latest and count:
        query += " ORDER BY id DESC LIMIT %s"
        args.append(count)
    else:
        query += " ORDER BY title"

    args = tuple(args)
    cursor.execute(query, args)
    results = cursor.fetchall()
    cursor.close()

    results_xml = format_results(results, content_type, widget)
    return results_xml
