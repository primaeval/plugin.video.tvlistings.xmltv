from xbmcswift2 import Plugin
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import re

import requests

from datetime import datetime,timedelta
import time
import urllib
import HTMLParser
import xbmcplugin


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
            
            
def xml_channels():
    if plugin.get_setting('xml_reload') == 'true':
        plugin.set_setting('xml_reload','false')
    else:
        path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
        stat = xbmcvfs.Stat(path)
        modified = str(stat.st_mtime())
        last_modified = plugin.get_setting('xmltv_last_modified')
        if last_modified == modified:
            return
        plugin.set_setting('xmltv_last_modified', modified)
        
    channels = plugin.get_storage('channels')
    items = []
    for channel in channels:
        channel = urllib.quote_plus(channel.encode("utf8"))
        programmes = plugin.get_storage(channel)
        programmes.clear()
    channels.clear()
        
    xbmcvfs.mkdir('special://userdata/addon_data/plugin.video.tvlistings.xmltv')
    if not xbmcvfs.exists('special://userdata/addon_data/plugin.video.tvlistings.xmltv/myaddons.ini'):
        f = xbmcvfs.File('special://userdata/addon_data/plugin.video.tvlistings.xmltv/myaddons.ini','w')
        f.close()

    file_name = 'special://userdata/addon_data/plugin.video.tvlistings.xmltv/template.ini'
    f = xbmcvfs.File(file_name,'w')
    write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next channel reload.\n\n[plugin.video.all]\n"
    f.write(write_str.encode("utf8"))

    import xml.etree.ElementTree as ET
    xml_f = xbmcvfs.File(plugin.get_setting('xmltv_file'))
    xml = xml_f.read()
    tree = ET.fromstring(xml)
    order = 0
    for channel in tree.findall(".//channel"):
        id = channel.attrib['id']
        display_name = channel.find('display-name').text
        try:
            icon = channel.find('icon').attrib['src']
        except:
            icon = ''
        channels[id] = '|'.join((display_name,icon,"%06d" % order))
        write_str = "%s=\n" % (id)
        f.write(write_str.encode("utf8"))
        order = order + 1
        
    for programme in tree.findall(".//programme"):
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
            desc = programme.find('desc').text
        except:
            desc = ''
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
        
        channel = urllib.quote_plus(channel.encode("utf8"))
        programmes = plugin.get_storage(channel)
        total_seconds = time.mktime(start.timetuple())
        programmes[total_seconds] = '|'.join((title,sub_title,date,series,episode,categories,desc))

        
        
@plugin.route('/channels')
def channels():  
    channels = plugin.get_storage('channels')
    items = []
    for channel_id in channels:
        (channel_name,img_url,order) = channels[channel_id].split('|')

        label = "[COLOR yellow][B]%s[/B][/COLOR]" % (channel_name)
            
        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))
        item['info'] = {'sorttitle' : order}
        
        items.append(item)

    plugin.set_view_mode(51)

    sorted_items = sorted(items, key=lambda item: item['info']['sorttitle'])
    return sorted_items  
    
@plugin.route('/now_next')
def now_next():  
    channels = plugin.get_storage('channels')
    now = datetime.now()
    total_seconds = time.mktime(now.timetuple())
    items = []

    for channel_id in channels:
        (channel_name,img_url,order) = channels[channel_id].split('|')
        channel = urllib.quote_plus(channel_id.encode("utf8"))
        programmes = plugin.get_storage(channel)
        times = sorted(programmes)
        max = len(times)
        less = [i for i in times if i < total_seconds]
        index = len(less) - 1
        if index < 0:
            continue
        now = times[index]
        now_programme = programmes[now]
        now = datetime.fromtimestamp(now)
        now = "%02d:%02d" % (now.hour,now.minute)
        (now_title,sub_title,date,season,episode,categories,plot) = now_programme.split('|')
        
        next = ''
        next_title = ''
        if index+1 < max: 
            next = times[index + 1]
            next_programme = programmes[next]
            next = datetime.fromtimestamp(next)                
            next = "%02d:%02d" % (next.hour,next.minute)                
            (next_title,sub_title,date,season,episode,categories,plot) = next_programme.split('|')
        
        after = ''
        after_title = ''
        if (index+2) < max:
            after = times[index + 2]
            after_programme = programmes[after]
            after = datetime.fromtimestamp(after)
            after = "%02d:%02d" % (after.hour,after.minute)
            (after_title,sub_title,date,season,episode,categories,plot) = after_programme.split('|')

        
        if  plugin.get_setting('show_channel_name') == 'true':
            label = "[COLOR yellow][B]%s[/B][/COLOR] %s [COLOR orange][B]%s[/B][/COLOR] %s [COLOR white][B]%s[/B][/COLOR] %s [COLOR grey][B]%s[/B][/COLOR]" % \
            (channel_name,now,now_title,next,next_title,after,after_title)
        else:
            label = "%s [COLOR orange][B]%s[/B][/COLOR] %s [COLOR white][B]%s[/B][/COLOR] %s [COLOR grey][B]%s[/B][/COLOR]" % \
            (now,now_title,next,next_title,after,after_title)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))
        item['info'] = {'sorttitle' : order}
        
        items.append(item)

    plugin.set_view_mode(51)
    #plugin.set_content('episodes')
    sorted_items = sorted(items, key=lambda item: item['info']['sorttitle'])
    return sorted_items  
    
@plugin.route('/listing/<channel_id>/<channel_name>')
def listing(channel_id,channel_name):  
    programmes = plugin.get_storage(urllib.quote_plus(channel_id))
    items = []
    last_day = ''
    for total_seconds in sorted(programmes):
        dt = datetime.fromtimestamp(total_seconds)
        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR red][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,'is_playable':True,'path':plugin.url_for('listing', channel_id=channel_id, channel_name=channel_name)})            
            
        (title,sub_title,date,season,episode,categories,plot) = programmes[total_seconds].split('|')
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

    plugin.set_view_mode(51)
    plugin.set_content('episodes')
    return items  
    
@plugin.route('/search/<programme_name>')
def search(programme_name):
    channels = plugin.get_storage('channels')
    programme_name_lower = programme_name.encode("utf8").lower()
    items = []
    for channel_id in channels:
        (channel_name,img_url,order) = channels[channel_id].split('|')
        programmes = plugin.get_storage(urllib.quote_plus(channel_id.encode("utf8")))
        for total_seconds in programmes:
            (title,sub_title,date,season,episode,categories,plot) = programmes[total_seconds].split('|')
            title_lower = title.encode("utf8").lower()
            match = re.search(programme_name_lower,title_lower)
            if match:
                dt = datetime.fromtimestamp(total_seconds)
                if not season:
                    season = '0'
                if not episode:
                    episode = '0'
                if date:
                    title = "%s (%s)" % (title,date)
                if sub_title:
                    plot = "[B]%s[/B]: %s" % (sub_title,plot)
                ttime = "%02d/%02d/%04d %02d:%02d" % (dt.day,dt.month,dt.year,dt.hour,dt.minute)

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
    plugin.set_view_mode(51)
    plugin.set_content('episodes')
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
    