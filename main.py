from xbmcswift2 import Plugin
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import re

import requests

from datetime import datetime,timedelta
import time
import urllib
import HTMLParser
import xbmcplugin
import xml.etree.ElementTree as ET
import sqlite3
import os

plugin = Plugin()

def log2(v):
    xbmc.log(repr(v))

def log(v):
    xbmc.log(re.sub(',',',\n',repr(v)))
    
def get_tvdb_id(name):
    tvdb_url = "http://thetvdb.com//api/GetSeries.php?seriesname=%s" % name
    r = requests.get(tvdb_url)
    tvdb_html = r.text
    tvdb_id = ''
    tvdb_match = re.search(r'<seriesid>(.*?)</seriesid>', tvdb_html, flags=(re.DOTALL | re.MULTILINE))
    if tvdb_match:
        tvdb_id = tvdb_match.group(1)
    return tvdb_id

  
    
@plugin.route('/play/<channel_id>/<channel_name>/<title>/<season>/<episode>')
def play(channel_id,channel_name,title,season,episode):
    channel_items = channel(channel_id,channel_name)
    items = []
    tvdb_id = ''
    if int(season) > 0 and int(episode) > 0:
        tvdb_id = get_tvdb_id(title)
    if tvdb_id:
        if season and episode:
            meta_url = "plugin://plugin.video.meta/tv/play/%s/%s/%s/%s" % (tvdb_id,season,episode,'select')
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]S%sE%s[/B][/COLOR] [COLOR green][B]Meta episode[/B][/COLOR]' % (title,season,episode),
            'path': meta_url,
            'is_playable': True,
             })
        if season:
            meta_url = "plugin://plugin.video.meta/tv/tvdb/%s/%s" % (tvdb_id,season)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]S%s[/B][/COLOR] [COLOR green][B]Meta season[/B][/COLOR]' % (title,season),
            'path': meta_url,
            'is_playable': False,
             })         
        meta_url = "plugin://plugin.video.meta/tv/tvdb/%s" % (tvdb_id)
        items.append({
        'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta[/B][/COLOR]' % (title),
        'path': meta_url,
        'is_playable': False,
         })
        try:
            addon = xbmcaddon.Addon('plugin.video.sickrage')
            if addon:
                items.append({
                'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]SickRage[/B][/COLOR]' % (title), 
                'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                })
        except:
            pass
    else:
        match = re.search(r'(.*?)\(([0-9]*)\)$',title)
        if match:
            movie = match.group(1)
            year =  match.group(2) #TODO: Meta doesn't support year yet
            meta_url = "plugin://plugin.video.meta/movies/search_term/%s/1" % (movie)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta[/B][/COLOR]' % (title),
            'path': meta_url,
            'is_playable': False,
             }) 
            try:
                addon = xbmcaddon.Addon('plugin.video.couchpotato_manager')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]CouchPotato[/B][/COLOR]' % (title), 
                    'path':"plugin://plugin.video.couchpotato_manager/movies/add/?title=%s" % (title)
                    })
            except:
                pass
        else:
            meta_url = "plugin://plugin.video.meta/tv/search_term/%s/1" % (title)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta search[/B][/COLOR]' % (title),
            'path': meta_url,
            'is_playable': False,
             }) 
            try:
                addon = xbmcaddon.Addon('plugin.video.sickrage')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]SickRage[/B][/COLOR]' % (title), 
                    'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                    })
            except:
                pass
   
    items.extend(channel_items)
    return items

    
@plugin.route('/channel/<channel_id>/<channel_name>')
def channel(channel_id,channel_name):
    
    addons = plugin.get_storage('addons')
    items = []
    for addon in addons:
        channels = plugin.get_storage(addon)
        if not channel_id in channels:
            continue
        path = channels[channel_id]
        try:
            addon = xbmcaddon.Addon(addon)
            if addon:
                item = {
                'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR]' % (re.sub('_',' ',channel_name),addon.getAddonInfo('name')),
                'path': path,
                'is_playable': True,
                }
                items.append(item)
        except:
            pass

    return items

def utc2local (utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset
    
    
def local_time(ttime,year,month,day):
    match = re.search(r'(.{1,2}):(.{2}) {0,1}(.{2})',ttime)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3)
        if ampm == "pm":
            if hour < 12:
                hour = hour + 12
                hour = hour % 24
        else:
            if hour == 12:
                hour = 0

        utc_dt = datetime(int(year),int(month),int(day),hour,minute,0)
        loc_dt = utc2local(utc_dt)
        ttime = "%02d:%02d" % (loc_dt.hour,loc_dt.minute)
    return ttime



 
def get_url(url):
    headers = {'user-agent': 'Mozilla/5.0 (BB10; Touch) AppleWebKit/537.10+ (KHTML, like Gecko) Version/10.0.9.2372 Mobile Safari/537.10+'}
    try:
        r = requests.get(url,headers=headers)
        html = HTMLParser.HTMLParser().unescape(r.content.decode('utf-8'))
        return html
    except:
        return ''


def store_channels():
    if plugin.get_setting('ini_reload') == 'true':
        plugin.set_setting('ini_reload','false')
    else:
        return
        
    addons = plugin.get_storage('addons')
    items = []
    for addon in addons:
        channels = plugin.get_storage(addon)
        channels.clear()
    addons.clear()

    ini_files = [plugin.get_setting('ini_file1'),plugin.get_setting('ini_file2')]
    
    for ini in ini_files:
        try:
            f = xbmcvfs.File(ini)
            items = f.read().splitlines()
            f.close()
            addon = 'nothing'
            for item in items:
                if item.startswith('['):
                    addon = item.strip('[] \t')
                elif item.startswith('#'):
                    pass
                else:
                    name_url = item.split('=',1)
                    if len(name_url) == 2:
                        name = name_url[0]
                        url = name_url[1]
                        if url:
                            channels = plugin.get_storage(addon)
                            channels[name] = url
                            addons = plugin.get_storage('addons')
                            addons[addon] = addon
        except:
            pass



def xml2utc(xml):
    match = re.search(r'([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2}) ([+-])([0-9]{2})([0-9]{2})',xml)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        second = int(match.group(6))
        sign = match.group(7)
        hours = int(match.group(8))
        minutes = int(match.group(9))
        dt = datetime(year,month,day,hour,minute,second)
        td = timedelta(hours=hours,minutes=minutes)
        if sign == '+':
            dt = dt - td
        else:
            dt = dt + td
        return dt
    return ''

class FileWrapper(object):
    def __init__(self, filename):
        self.vfsfile = xbmcvfs.File(filename)
        self.size = self.vfsfile.size()
        self.bytesRead = 0

    def close(self):
        self.vfsfile.close()

    def read(self, byteCount):
        self.bytesRead += byteCount
        return self.vfsfile.read(byteCount)

    def tell(self):
        return self.bytesRead


def get_conn():    
    profilePath = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
    if not os.path.exists(profilePath):
        os.makedirs(profilePath)
    databasePath = os.path.join(profilePath, 'source.db')    
    
    conn = sqlite3.connect(databasePath, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row        
    return conn
        
def xml_channels():
    if plugin.get_setting('xml_reload') == 'true':
        plugin.set_setting('xml_reload','false')
    else:
        try:
            xmltv_type = plugin.get_setting('xmltv_type')
            xmltv_type_last = plugin.get_setting('xmltv_type_last')
            if xmltv_type == xmltv_type_last:
                if plugin.get_setting('xmltv_type') == '0':
                    path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
                    stat = xbmcvfs.Stat(path)
                    modified = str(stat.st_mtime())
                    last_modified = plugin.get_setting('xmltv_last_modified')
                    if last_modified == modified:
                        return
                    plugin.set_setting('xmltv_last_modified', modified)
                else:
                    dt = datetime.now()
                    now = int(time.mktime(dt.timetuple()))
                    try:
                        last = plugin.get_setting("xmltv_url_last")
                        last = int(last) if last else 0
                        hours = int(plugin.get_setting("xmltv_hours"))
                        next = last + 3600*hours
                        if now < next:
                            return
                        else:
                            plugin.set_setting("xmltv_url_last",str(now))
                    except:
                        plugin.set_setting("xmltv_url_last",str(now))
            #TODO check logic for reloading xmltv files
            plugin.set_setting('xmltv_type_last',xmltv_type)
        except:
            plugin.set_setting('xmltv_type_last',xmltv_type)


    xbmcvfs.mkdir('special://userdata/addon_data/plugin.video.tvlistings.xmltv')
    if not xbmcvfs.exists('special://userdata/addon_data/plugin.video.tvlistings.xmltv/myaddons.ini'):
        f = xbmcvfs.File('special://userdata/addon_data/plugin.video.tvlistings.xmltv/myaddons.ini','w')
        f.close()

    file_name = 'special://userdata/addon_data/plugin.video.tvlistings.xmltv/template.ini'
    f = xbmcvfs.File(file_name,'w')
    write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next channel reload.\n\n[plugin.video.all]\n"
    f.write(write_str.encode("utf8"))

    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    conn.execute('DROP TABLE IF EXISTS channels')
    conn.execute('DROP TABLE IF EXISTS programmes')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS channels(id TEXT, name TEXT, icon TEXT, PRIMARY KEY (id))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS programmes(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')

    if plugin.get_setting('xmltv_type') == '1':
        url = plugin.get_setting('xmltv_url')
        r = requests.get(url)
        file_name = 'special://userdata/addon_data/plugin.video.tvlistings.xmltv/xmltv.xml'
        xmltv_f = xbmcvfs.File(file_name,'w')
        xml = r.content
        xmltv_f.write(xml)
        xmltv_f.close()
        xmltv_file = file_name
    else:
        xmltv_file = plugin.get_setting('xmltv_file')
    
    xml_f = FileWrapper(xmltv_file)
    if xml_f.size == 0:
        return
    context = ET.iterparse(xml_f, events=("start", "end"))
    context = iter(context)
    event, root = context.next()
    for event, elem in context:
        if event == "end":

            if elem.tag == "channel":
                id = elem.attrib['id']
                display_name = elem.find('display-name').text
                try:
                    icon = elem.find('icon').attrib['src']
                except:
                    icon = ''
                write_str = "%s=\n" % (id)
                f.write(write_str.encode("utf8"))
                conn.execute("INSERT OR IGNORE INTO channels(id, name, icon) VALUES(?, ?, ?)", [id, display_name, icon])

            elif elem.tag == "programme":
                programme = elem
                start = programme.attrib['start']
                start = xml2utc(start)
                start = utc2local(start)
                channel = programme.attrib['channel']
                title = programme.find('title').text
                match = re.search(r'(.*?)"}.*?\(\?\)$',title) #BUG in webgrab
                if match:
                    title = match.group(1)
                try:
                    sub_title = programme.find('sub-title').text
                except:
                    sub_title = ''
                try:
                    date = programme.find('date').text
                except:
                    date = ''
                try:
                    description = programme.find('desc').text
                except:
                    description = ''
                try:
                    episode_num = programme.find('episode-num').text
                except:
                    episode_num = ''
                series = 0
                episode = 0
                match = re.search(r'(.*?)\.(.*?)[\./]',episode_num)
                if match:
                    try:
                        series = int(match.group(1)) + 1
                        episode = int(match.group(2)) + 1
                    except:
                        pass
                series = str(series)
                episode = str(episode)
                categories = ''
                for category in programme.findall('category'):
                    categories = ','.join((categories,category.text)).strip(',')

                total_seconds = time.mktime(start.timetuple())
                start = int(total_seconds)
                conn.execute("INSERT OR IGNORE INTO programmes(channel ,title , sub_title , start , date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", [channel ,title , sub_title , start , date, description , series , episode , categories])
            root.clear()

    conn.commit()
    conn.close()


@plugin.route('/channels')
def channels():  
    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT * FROM channels')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        label = "[COLOR yellow][B]%s[/B][/COLOR]" % (channel_name)
        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))
        items.append(item)
    c.close()

    plugin.set_view_mode(51)
    return items

@plugin.route('/now_next_time/<seconds>')
def now_next_time(seconds):  
    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT *, name FROM channels')
    channels = [(row['id'], row['name'], row['icon']) for row in c]

    now = datetime.fromtimestamp(float(seconds))
    total_seconds = time.mktime(now.timetuple())

    items = []
    for (channel_id, channel_name, img_url) in channels:

        c.execute('SELECT start FROM programmes WHERE channel=?', [channel_id])
        programmes = [row['start'] for row in c]
        
        times = sorted(programmes)
        max = len(times)
        less = [i for i in times if i <= total_seconds]
        index = len(less) - 1
        if index < 0:
            continue
        now = times[index]

        c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,now])
        now = datetime.fromtimestamp(now)
        now = "%02d:%02d" % (now.hour,now.minute)
        now_title = c.fetchone()['title']

        next = ''
        next_title = ''
        if index+1 < max: 
            next = times[index + 1]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,next])
            next = datetime.fromtimestamp(next)                
            next = "%02d:%02d" % (next.hour,next.minute)                
            next_title = c.fetchone()['title']

        after = ''
        after_title = ''
        if (index+2) < max:
            after = times[index + 2]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,after])
            after = datetime.fromtimestamp(after)
            after = "%02d:%02d" % (after.hour,after.minute)
            after_title = c.fetchone()['title']

        if  plugin.get_setting('show_channel_name') == 'true':
            label = "[COLOR yellow][B]%s[/B][/COLOR] %s [COLOR orange][B]%s[/B][/COLOR] %s [COLOR white][B]%s[/B][/COLOR] %s [COLOR grey][B]%s[/B][/COLOR]" % \
            (channel_name,now,now_title,next,next_title,after,after_title)
        else:
            label = "%s [COLOR orange][B]%s[/B][/COLOR] %s [COLOR white][B]%s[/B][/COLOR] %s [COLOR grey][B]%s[/B][/COLOR]" % \
            (now,now_title,next,next_title,after,after_title)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))

        items.append(item)

    #plugin.set_view_mode(51)
    #plugin.set_content('episodes')

    return items

@plugin.route('/hourly')
def hourly():  
    items = []

    dt = datetime.now()
    dt = dt.replace(hour=0, minute=0, second=0)

    for day in ("Today","Tomorrow"):
        label = "[COLOR red][B]%s[/B][/COLOR]" % (day)
        items.append({'label':label,'path':plugin.url_for('hourly')})
        for hour in range(0,24):
            label = "[COLOR blue][B]%02d:00[/B][/COLOR]" % (hour)
            total_seconds = str(time.mktime(dt.timetuple()))
            items.append({'label':label,'path':plugin.url_for('now_next_time',seconds=total_seconds)})
            dt = dt + timedelta(hours=1)

    return items


@plugin.route('/prime')
def prime():  
    prime = plugin.get_setting('prime')
    dt = datetime.now()
    dt = dt.replace(hour=int(prime), minute=0, second=0)
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds)

    plugin.set_view_mode(51)
    #plugin.set_content('episodes')
    #sorted_items = sorted(items, key=lambda item: item['info']['sorttitle'])
    #return sorted_items  
    return items


@plugin.route('/now_next')
def now_next():  
    dt = datetime.now()
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds)

    plugin.set_view_mode(51)
    #plugin.set_content('episodes')
    return items

@plugin.route('/listing/<channel_id>/<channel_name>')
def listing(channel_id,channel_name):  
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM programmes WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    items = []
    last_day = ''
    for row in c:

        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']
        
        dt = datetime.fromtimestamp(start)
        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR red][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,'is_playable':True,'path':plugin.url_for('listing', channel_id=channel_id, channel_name=channel_name)}) 
            
        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        ttime = "%02d:%02d" % (dt.hour,dt.minute)
        channel_name_u = unicode(channel_name,'utf-8')
        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s [COLOR orange][B]%s[/B][/COLOR] %s" % (channel_name_u,ttime,title,plot)
            else:
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s [COLOR orange][B]%s[/B][/COLOR]" % (channel_name_u,ttime,title)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s [COLOR orange][B]%s[/B][/COLOR] %s" % (ttime,title,plot)
            else:
                label = "%s [COLOR orange][B]%s[/B][/COLOR]" % (ttime,title)

        img_url = ''
        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id, channel_name=channel_name, title=title.encode("utf8"), season=season, episode=episode)
        items.append(item)
    c.close()

    return items  


@plugin.route('/search/<programme_name>')
def search(programme_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)
    c.execute("SELECT * FROM programmes WHERE LOWER(title) LIKE LOWER(?) ORDER BY start, channel", ['%'+programme_name+'%'])
    last_day = ''
    items = []
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']
        
        dt = datetime.fromtimestamp(start)
        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR red][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,'is_playable':True,'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))}) 
            
        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        ttime = "%02d:%02d" % (dt.hour,dt.minute)

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s [COLOR orange][B]%s[/B][/COLOR] %s" % (channel_name,ttime,title,plot)
            else:
                label = "[COLOR yellow][B]%s[/B][/COLOR] %s [COLOR orange][B]%s[/B][/COLOR]" % (channel_name,ttime,title)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s [COLOR orange][B]%s[/B][/COLOR] %s" % (ttime,title,plot)
            else:
                label = "%s [COLOR orange][B]%s[/B][/COLOR]" % (ttime,title)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode)
        items.append(item)
    c.close()
    return items



@plugin.route('/search_dialog')
def search_dialog():
    dialog = xbmcgui.Dialog()
    name = dialog.input('Search for programme', type=xbmcgui.INPUT_ALPHANUM)
    if name:
        return search(name)


@plugin.route('/')
def index():
    items = [  
    {
        'label': '[COLOR green][B]Now Next[/B][/COLOR]',
        'path': plugin.url_for('now_next'),
    },
    {
        'label': '[COLOR blue][B]Hourly[/B][/COLOR]',
        'path': plugin.url_for('hourly'),
    },
    {
        'label': '[COLOR orange][B]Prime Time[/B][/COLOR]',
        'path': plugin.url_for('prime'),
    },
    {
        'label': '[COLOR red][B]Listings[/B][/COLOR]',
        'path': plugin.url_for('channels'),
    },
    {
        'label': '[COLOR yellow][B]Search[/B][/COLOR]',
        'path': plugin.url_for('search_dialog'),
    },
    ]
    return items
    
if __name__ == '__main__':
    xml_channels()
    store_channels()
    plugin.run()
    