from xbmcswift2 import Plugin
from xbmcswift2 import actions
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
import shutil
from rpc import RPC
from types import *

plugin = Plugin()
big_list_view = False

def log2(v):
    xbmc.log(repr(v))

def log(v):
    xbmc.log(re.sub(',',',\n',repr(v)))

def get_icon_path(icon_name):
    addon_path = xbmcaddon.Addon().getAddonInfo("path")
    return os.path.join(addon_path, 'resources', 'img', icon_name+".png")


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

def get_tvdb_id(name):
    tvdb_url = "http://thetvdb.com//api/GetSeries.php?seriesname=%s" % name
    try:
        r = requests.get(tvdb_url)
    except:
        return ''
    tvdb_html = r.text
    tvdb_id = ''
    tvdb_match = re.search(r'<seriesid>(.*?)</seriesid>', tvdb_html, flags=(re.DOTALL | re.MULTILINE))
    if tvdb_match:
        tvdb_id = tvdb_match.group(1)
    return tvdb_id

@plugin.route('/clear_addon_paths')
def clear_addon_paths():
    conn = get_conn()
    conn.execute('UPDATE channels SET path=NULL, play_method=NULL')
    conn.execute('DROP TABLE IF EXISTS addon_paths')
    conn.commit()
    create_database_tables()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Clear Addon Paths")


@plugin.route('/clear_channels')
def clear_channels():
    conn = get_conn()
    conn.execute('UPDATE channels SET path=NULL, play_method=NULL')
    conn.execute('DROP TABLE IF EXISTS addons')
    conn.commit()
    create_database_tables()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Clear Channels")


@plugin.route('/export_channels')
def export_channels():
    file_name = 'special://profile/addon_data/plugin.video.tvlistings.xmltv/plugin.video.tvlistings.xmltv.ini'
    f = xbmcvfs.File(file_name,'w')
    write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next channel export.\n\n[plugin.video.tvlistings.xmltv]\n"
    f.write(write_str.encode("utf8"))

    items = []

    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT id,path FROM channels')
    for row in c:
        channel_id = row['id']
        path = row['path']
        if not path:
            path = ''
        write_str = "%s=%s\n" % (channel_id,path)
        f.write(write_str.encode("utf8"))

    c.execute('SELECT DISTINCT addon FROM addons')
    addons = [row["addon"] for row in c]

    for addon in addons:
        write_str = "[%s]\n" % (addon)
        f.write(write_str.encode("utf8"))
        c.execute('SELECT name,path FROM addons WHERE addon=?', [addon])
        for row in c:
            channel_name = row['name']
            path = row['path']
            if not path:
                path = ''
            write_str = "%s=%s\n" % (channel_name,path)
            f.write(write_str.encode("utf8"))
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Export Channels")
    c.close()
    return items


@plugin.route('/channel_list')
def channel_list():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM channels')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        path = row['path']
        method = row["play_method"]
        if method == "not_playable":
            is_playable = False
        else:
            is_playable = True
        if path:
            label = "[COLOR yellow][B]%s[/B][/COLOR]" % (channel_name)
            item = {'label':label,'icon':img_url,'thumbnail':img_url}
            item['path'] = path
            item['is_playable'] = is_playable
            url = plugin.url_for('channel_play', channel_id=channel_id.encode("utf8"),channel_play=False)
            item['context_menu'] = [('[COLOR yellow]Edit Channel[/COLOR]', actions.update_view(url))]
            items.append(item)
    c.close()
    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items


@plugin.route('/channel_remap')
def channel_remap():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    c.execute('SELECT addon, path FROM addons')
    addons = dict([[row["path"], row["addon"]] for row in c])

    c.execute('SELECT * FROM channels')
    items = []
    for row in c:
        channel_id = row['id']
        channel_name = row['name']
        img_url = row['icon']
        path = row['path']
        if path in addons:
            addon = addons[path]
            addon_name = remove_formatting(xbmcaddon.Addon(addon).getAddonInfo('name'))
            addon_icon = xbmcaddon.Addon(addon).getAddonInfo('icon')
            addon_label = " [COLOR green][B]%s[/B][/COLOR]" % addon_name
            img_url = addon_icon
        else:
            addon_label = ""

        if path:
            label = "[COLOR red][B]%s[/B][/COLOR]%s" % (channel_name,addon_label)
        else:
            label = "[COLOR yellow][B]%s[/B][/COLOR]%s" % (channel_name,addon_label)
        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('channel_remap_all', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), channel_play=True)
        items.append(item)
    c.close()
    sorted_items = sorted(items, key=lambda item: remove_formatting(item['label']))
    return sorted_items


@plugin.route('/channel_remap_addons/<channel_id>/<channel_name>')
def channel_remap_addons(channel_id,channel_name):
    global big_list_view
    big_list_view = True
    items = []

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT DISTINCT addon FROM addons')
    addons = [row["addon"] for row in c]
    icon = ''
    item = {
    'label': '[COLOR red][B]%s[/B][/COLOR]' % ("Search Addons"),
    'path': plugin.url_for(channel_remap_search, channel_id=channel_id,channel_name=channel_name),
    'thumbnail': get_icon_path('search'),
    'is_playable': False,
    }

    for addon_id in sorted(addons):
        try:
            addon = xbmcaddon.Addon(addon_id)
            if addon:
                icon = addon.getAddonInfo('icon')
                item = {
                'label': '[COLOR green][B]%s[/B][/COLOR]' % (remove_formatting(addon.getAddonInfo('name'))),
                'path': plugin.url_for(channel_remap_streams, addon_id=addon_id,channel_id=channel_id,channel_name=channel_name),
                'thumbnail': icon,
                'icon': icon,
                'is_playable': False,
                }
                items.append(item)
        except:
            pass
    return items


@plugin.route('/search_addons/<channel_name>')
def search_addons(channel_name):
    global big_list_view
    big_list_view = True
    if channel_name == 'none':
        dialog = xbmcgui.Dialog()
        channel_name = dialog.input('Search for channel?', type=xbmcgui.INPUT_ALPHANUM)
    if not channel_name:
        return

    items = []
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM addons WHERE LOWER(name) LIKE LOWER(?) ORDER BY addon, name", ['%'+channel_name.decode("utf8")+'%'])
    for row in c:
        addon_id = row["addon"]
        stream_name = row["name"]
        path = row["path"]
        icon = row["icon"]
        try:
            addon = xbmcaddon.Addon(addon_id)
        except:
            continue
        icon = addon.getAddonInfo('icon')
        addon_name = remove_formatting(addon.getAddonInfo('name'))
        label = '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR]' % (stream_name, addon_name)
        log(addon_id)
        item = {
        'label': label,
        'path': plugin.url_for('stream_play', addon_id=addon_id, stream_name=stream_name.encode("utf8"),path=path),
        'thumbnail': icon,
        'icon': icon,
        'is_playable': False,
        }
        items.append(item)

    return items


@plugin.route('/channel_remap_search/<channel_id>/<channel_name>')
def channel_remap_search(channel_id,channel_name):
    dialog = xbmcgui.Dialog()
    channel_name = dialog.input('Search for channel?', type=xbmcgui.INPUT_ALPHANUM)
    if not channel_name:
        return
    return channel_remap_all(channel_id,channel_name)


@plugin.route('/channel_remap_all/<channel_id>/<channel_name>/<channel_play>')
def channel_remap_all(channel_id,channel_name,channel_play):
    global big_list_view
    big_list_view = True

    items = []

    img_url = get_icon_path('search')
    label = "[COLOR yellow][B]%s[/B][/COLOR] [COLOR blue][B]%s[/B][/COLOR]" % (channel_name, 'All Streams')
    item = {'label':label,'icon':img_url,'thumbnail':img_url}
    item['path'] = plugin.url_for('channel_remap_addons', channel_id=channel_id, channel_name=channel_name)
    items.append(item)
    label = "[COLOR yellow][B]%s[/B][/COLOR] [COLOR white][B]%s[/B][/COLOR]" % (channel_name, 'Reset Channel')
    item = {'label':label,'icon':img_url,'thumbnail':img_url}
    item['path'] = plugin.url_for('reset_channel', channel_id=channel_id)
    items.append(item)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM channels WHERE id=?", [channel_id.decode("utf8")])
    row = c.fetchone()
    channel_path = row["path"]
    channel_icon = row["icon"]
    c.execute("SELECT * FROM addons WHERE LOWER(name) LIKE LOWER(?) ORDER BY addon, name", ['%'+channel_name.decode("utf8")+'%'])

    for row in c:
        addon_id = row["addon"]
        stream_name = row["name"]
        path = row["path"]
        icon = row["icon"]
        try:
            addon = xbmcaddon.Addon(addon_id)
        except:
            continue
        icon = addon.getAddonInfo('icon')
        addon_name = remove_formatting(addon.getAddonInfo('name'))
        if channel_path == path:
            label = '[COLOR yellow][B]%s[/B][/COLOR] [COLOR red][B]%s[/B][/COLOR]' % (stream_name, addon_name)
        else:
            label = '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR]' % (stream_name, addon_name)
        item = {
        'label': label,
        'path': plugin.url_for(channel_remap_stream, addon_id=addon_id, channel_id=channel_id, channel_name=channel_name, stream_name=stream_name.encode("utf8")),
        'thumbnail': icon,
        'icon': icon,
        'is_playable': False,
        }
        url = plugin.url_for('stream_play', addon_id=addon_id, stream_name=stream_name.encode("utf8"),path=path)
        item['context_menu'] = [('[COLOR yellow]Edit Shortcut[/COLOR]', actions.update_view(url))]
        items.append(item)

    log(channel_play)
    if channel_play == "True":
        if channel_path:
            item = {'label':"[COLOR yellow]%s[/COLOR] [COLOR red]%s[/COLOR]" % (channel_name,'Play Method'),
            'path': plugin.url_for('channel_play', channel_id=channel_id,channel_play=False),
            'thumbnail':channel_icon,
            'is_playable':False}
            #items.append(item)

    return items


@plugin.route('/channel_remap_streams/<addon_id>/<channel_id>/<channel_name>')
def channel_remap_streams(addon_id,channel_id,channel_name):
    global big_list_view
    big_list_view = True
    addon = xbmcaddon.Addon(addon_id)
    addon_name = remove_formatting(addon.getAddonInfo('name'))
    if addon:
        icon = addon.getAddonInfo('icon')
    else:
        icon = ''
    items = []

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT * FROM channels WHERE id=?", [channel_id.decode("utf8")])
    row = c.fetchone()
    channel_path = row["path"]

    c.execute('SELECT * FROM addons WHERE addon=?', [addon_id])
    streams = dict([row["path"],[row["name"], row["icon"]]] for row in c)

    for path in sorted(streams):
        (stream_name,icon) = streams[path]
        if channel_path == path:
            label = '[COLOR yellow][B]%s[/B][/COLOR] [COLOR red][B]%s[/B][/COLOR]' % (stream_name, addon_name)
        else:
            label = '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR]' % (stream_name, addon_name)

        item = {
        'label': label,
        'path': plugin.url_for(channel_remap_stream, addon_id=addon_id, channel_id=channel_id, channel_name=channel_name, stream_name=stream_name.encode("utf8")),
        'thumbnail': icon,
        'icon': icon,
        'is_playable': False,
        }
        url = plugin.url_for('stream_play', addon_id=addon_id, stream_name=stream_name.encode("utf8"),path=path)
        item['context_menu'] = [('[COLOR yellow]xEdit Channel[/COLOR]', actions.update_view(url))]
        items.append(item)

    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items


@plugin.route('/rename_shortcut/<addon_id>/<stream_name>/<path>')
def rename_shortcut(addon_id,stream_name,path):
    dialog = xbmcgui.Dialog()
    new_stream_name = dialog.input('Enter new Shortcut Name', stream_name, type=xbmcgui.INPUT_ALPHANUM)
    if not new_stream_name:
        return
    path = urllib.unquote(path)
    conn = get_conn()
    conn.execute('UPDATE addons SET name=? WHERE path=? AND addon=?', [new_stream_name,path,addon_id])
    conn.commit()


@plugin.route('/reset_channel/<channel_id>')
def reset_channel(channel_id):
    conn = get_conn()
    conn.execute('UPDATE channels SET path=NULL WHERE id=?', [channel_id.decode("utf8")])
    conn.commit()


@plugin.route('/channel_remap_stream/<addon_id>/<channel_id>/<channel_name>/<stream_name>')
def channel_remap_stream(addon_id,channel_id,channel_name,stream_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT path, play_method, icon FROM addons WHERE addon=? AND name=?', [addon_id, stream_name.decode("utf8")])
    row = c.fetchone()
    path = row["path"]
    icon = row["icon"]
    method = row["play_method"]
    if icon:
        c.execute('UPDATE channels SET path=?, play_method=?, icon=? WHERE id=?', [path,method,icon,channel_id.decode("utf8")])
    else:
        c.execute('UPDATE channels SET path=?, play_method=? WHERE id=?', [path,method,channel_id.decode("utf8")])
    conn.commit()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/select_channel/<channel_id>/<channel_name>')
def select_channel(channel_id,channel_name):
    global big_list_view
    big_list_view = True
    items = []
    for channel in sorted(channels):
        if channel == channel_name:
            label = "[COLOR red][B]%s[/B][/COLOR]" % (channel)
        else:
            label = "[COLOR yellow][B]%s[/B][/COLOR]" % (channel)
        img_url = ''
        item = {'label':label,'icon':img_url,'thumbnail':img_url,'is_playable': False}
        item['path'] = plugin.url_for('choose_channel', channel_id=channel_name.encode("utf8"), channel=channel.encode("utf8"),
        path=urllib.quote(channels[channel],safe=''))
        items.append(item)
    return items





@plugin.route('/play_channel/<channel_id>/<title>/<start>')
def play_channel(channel_id,title,start):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM channels WHERE id=?", [channel_id.decode("utf8")])
    row = c.fetchone()
    channel_path = row["path"]
    method = row["play_method"]
    plugin.set_setting('playing_channel',channel_id)
    plugin.set_setting('playing_title',title)
    plugin.set_setting('playing_start',start)
    if method == "not_playable":
        xbmc.executebuiltin('Container.Update("%s")' % channel_path)
    else:
        xbmc.executebuiltin('PlayMedia(%s)' % channel_path)


@plugin.route('/stop_playing/<channel_id>/<title>/<start>')
def stop_playing(channel_id,title,start):
    if plugin.get_setting('playing_channel') != channel_id:
        return
    elif plugin.get_setting('playing_start') != start:
        return
    plugin.set_setting('playing_channel','')
    plugin.set_setting('playing_title','')
    plugin.set_setting('playing_start','')
    xbmc.executebuiltin('PlayerControl(Stop)')


def get_conn():
    profilePath = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
    if not os.path.exists(profilePath):
        os.makedirs(profilePath)
    databasePath = os.path.join(profilePath, 'source.db')

    conn = sqlite3.connect(databasePath, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn


@plugin.route('/clear_reminders')
def clear_reminders():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM remind')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            title = row['title']
            xbmc.executebuiltin('CancelAlarm(%s,False)' % (channel_id+title+str(start)))

        c.execute('SELECT * FROM watch')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            title = row['title']
            xbmc.executebuiltin('CancelAlarm(%s-start,False)' % (channel_id+title+str(start)))
            xbmc.executebuiltin('CancelAlarm(%s-stop,False)' % (channel_id+title+str(start)))
    except:
        pass

    c.execute('DELETE FROM remind')
    c.execute('DELETE FROM watch')
    conn.commit()
    conn.close()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Clear Reminders")

@plugin.route('/refresh_reminders')
def refresh_reminders():
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute('SELECT * FROM remind')
        for row in c:
            start = row['start']
            t = datetime.fromtimestamp(float(start)) - datetime.now()
            timeToNotification = ((t.days * 86400) + t.seconds) / 60
            icon = ''
            description = "%s: %s" % (row['channel'],row['title'])
            xbmc.executebuiltin('AlarmClock(%s,Notification(%s,%s,10000,%s),%d)' %
                (row['channel']+row['title']+str(start), row['title'], description, icon, timeToNotification - int(plugin.get_setting('remind_before'))))

        c.execute('SELECT * FROM watch')
        for row in c:
            channel_id = row['channel']
            start = row['start']
            stop = row['stop']
            title = row['title']
            t = datetime.fromtimestamp(float(start)) - datetime.now()
            timeToNotification = ((t.days * 86400) + t.seconds) / 60
            command = 'AlarmClock(%s-start,PlayMedia(plugin://plugin.video.tvlistings.xmltv/play_channel/%s/%s/%s),%d,False)' % (
            channel_id+title+str(start), channel_id, title, start, timeToNotification - int(plugin.get_setting('remind_before')))
            xbmc.executebuiltin(command.encode("utf8"))
            if plugin.get_setting('watch_and_stop') == 'true':
                t = datetime.fromtimestamp(float(stop)) - datetime.now()
                timeToNotification = ((t.days * 86400) + t.seconds) / 60
                command = 'AlarmClock(%s-stop,PlayMedia(plugin://plugin.video.tvlistings.xmltv/stop_playing/%s/%s/%s),%d,True)' % (
                channel_id+title+str(start), channel_id, title, start, timeToNotification + int(plugin.get_setting('remind_after')))
                xbmc.executebuiltin(command.encode("utf8"))

        conn.commit()
        conn.close()
    except:
        pass
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Refresh Reminders")


@plugin.route('/remind/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def remind(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)
    xbmc.executebuiltin('AlarmClock(%s,Notification(%s,%s,10000,%s),%d)' %
        (channel_id+title+str(start), title, description, icon, timeToNotification - int(plugin.get_setting('remind_before'))))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    row = c.fetchone()
    c.execute("INSERT OR REPLACE INTO remind(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [row['channel'] ,row['title'] , row['sub_title'] , row['start'] , row['stop'], row['date'], row['description'] , row['series'] , row['episode'] , row['categories']])
    conn.commit()
    conn.close()
    #dialog = xbmcgui.Dialog()
    #dialog.notification("TV Listings (xmltv)","Done: Remind")
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/watch/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def watch(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    xbmc.executebuiltin('AlarmClock(%s-start,PlayMedia(plugin://plugin.video.tvlistings.xmltv/play_channel/%s/%s/%s),%d,False)' %
        (channel_id+title+str(start), channel_id, title, start, timeToNotification - int(plugin.get_setting('remind_before'))))

    #TODO check for overlapping times
    if plugin.get_setting('watch_and_stop') == 'true':
        t = datetime.fromtimestamp(float(stop)) - datetime.now()
        timeToNotification = ((t.days * 86400) + t.seconds) / 60
        xbmc.executebuiltin('AlarmClock(%s-stop,PlayMedia(plugin://plugin.video.tvlistings.xmltv/stop_playing/%s/%s/%s),%d,True)' %
            (channel_id+title+str(start), channel_id, title, start, timeToNotification + int(plugin.get_setting('remind_after'))))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    row = c.fetchone()
    c.execute("INSERT OR REPLACE INTO watch(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    [row['channel'] ,row['title'] , row['sub_title'] , row['start'] , row['stop'], row['date'], row['description'] , row['series'] , row['episode'] , row['categories']])
    conn.commit()
    conn.close()
    #dialog = xbmcgui.Dialog()
    #dialog.notification("TV Listings (xmltv)","Done: Watch")
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/cancel_remind/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def cancel_remind(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)
    xbmc.executebuiltin('CancelAlarm(%s,False)' % (channel_id+title+str(start)))

    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM remind WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])

    conn.commit()
    conn.close()
    #dialog = xbmcgui.Dialog()
    #dialog.notification("TV Listings (xmltv)","Done: Cancel Remind")
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/cancel_watch/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def cancel_watch(channel_id,channel_name,title,season,episode,start,stop):
    t = datetime.fromtimestamp(float(start)) - datetime.now()
    timeToNotification = ((t.days * 86400) + t.seconds) / 60
    icon = ''
    description = "%s: %s" % (channel_name,title)

    xbmc.executebuiltin('CancelAlarm(%s-start,False)' % (channel_id+title+str(start)))
    xbmc.executebuiltin('CancelAlarm(%s-stop,False)' % (channel_id+title+str(start)))

    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM watch WHERE channel=? AND start=?', [channel_id.decode("utf8"),start])
    conn.commit()
    conn.close()
    #dialog = xbmcgui.Dialog()
    #dialog.notification("TV Listings (xmltv)","Done: Cancel Watch")
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/play/<channel_id>/<channel_name>/<title>/<season>/<episode>/<start>/<stop>')
def play(channel_id,channel_name,title,season,episode,start,stop):
    global big_list_view
    big_list_view = True
    channel_items = channel(channel_id,channel_name)
    items = []
    tvdb_id = ''
    if int(season) > 0 and int(episode) > 0:
        tvdb_id = get_tvdb_id(title)
    try:
        addon = xbmcaddon.Addon('plugin.video.meta')
        meta_icon = addon.getAddonInfo('icon')
    except:
        meta_icon = ""
    if tvdb_id:
        if meta_icon:
            if season and episode:
                meta_url = "plugin://plugin.video.meta/tv/play/%s/%s/%s/%s" % (tvdb_id,season,episode,'select')
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]S%sE%s[/B][/COLOR] [COLOR green][B]Meta episode[/B][/COLOR]' % (title,season,episode),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': True,
                 })
            if season:
                meta_url = "plugin://plugin.video.meta/tv/tvdb/%s/%s" % (tvdb_id,season)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]S%s[/B][/COLOR] [COLOR green][B]Meta season[/B][/COLOR]' % (title,season),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
            meta_url = "plugin://plugin.video.meta/tv/tvdb/%s" % (tvdb_id)
            items.append({
            'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta TV search[/B][/COLOR]' % (title),
            'path': meta_url,
            'thumbnail': meta_icon,
            'icon': meta_icon,
            'is_playable': False,
             })
        try:
            addon = xbmcaddon.Addon('plugin.video.sickrage')
            sick_icon =  addon.getAddonInfo('icon')
            if addon:
                items.append({
                'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR yellow][B]SickRage[/B][/COLOR]' % (title),
                'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                'thumbnail': sick_icon,
                'icon': sick_icon,
                })
        except:
            pass
    else:
        match = re.search(r'(.*?)\(([0-9]*)\)$',title)
        if match:
            movie = match.group(1)
            year =  match.group(2) #TODO: Meta doesn't support year yet
            if meta_icon:
                meta_url = "plugin://plugin.video.meta/movies/search_term/%s/1" % (movie)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta movie[/B][/COLOR]' % (title),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
            try:
                addon = xbmcaddon.Addon('plugin.video.couchpotato_manager')
                couch_icon =  addon.getAddonInfo('icon')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR yellow][B]CouchPotato[/B][/COLOR]' % (title),
                    'path':"plugin://plugin.video.couchpotato_manager/movies/add/?title=%s" % (title),
                    'thumbnail': couch_icon,
                    'icon': couch_icon,
                    })
            except:
                pass
        else:
            if meta_icon:
                meta_url = "plugin://plugin.video.meta/tv/search_term/%s/1" % (title)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta TV search[/B][/COLOR]' % (title),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
                meta_url = "plugin://plugin.video.meta/movies/search_term/%s/1" % (title)
                items.append({
                'label': '[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]Meta movie search[/B][/COLOR]' % (title),
                'path': meta_url,
                'thumbnail': meta_icon,
                'icon': meta_icon,
                'is_playable': False,
                 })
            try:
                addon = xbmcaddon.Addon('plugin.video.sickrage')
                sick_icon =  addon.getAddonInfo('icon')
                if addon:
                    items.append({
                    'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR yellow][B]SickRage[/B][/COLOR]' % (title),
                    'path':"plugin://plugin.video.sickrage?action=addshow&&show_name=%s" % (title),
                    'thumbnail': sick_icon,
                    'icon': sick_icon,
                    })
            except:
                pass

    try:
        addon = xbmcaddon.Addon('plugin.program.super.favourites')
        sf_icon =  addon.getAddonInfo('icon')
        if addon:
            items.append({
            'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR green][B]iSearch[/B][/COLOR]' % (title),
            'path':"plugin://plugin.program.super.favourites?mode=0&keyword=%s" % (urllib.quote_plus(title)),
            'thumbnail': sf_icon,
            'icon': sf_icon,
            })
    except:
        pass

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    remind = [row['start'] for row in c]
    log(remind)
    log(start)
    c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    watch = [row['start'] for row in c]

    clock_icon = get_icon_path('alarm')
    if not int(start) in remind:
        items.append({
        'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]Remind[/B][/COLOR]' % (title),
        'path':plugin.url_for('remind', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
        'thumbnail': clock_icon,
        'icon': clock_icon,
        })
    else:
        items.append({
        'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR red][B]Cancel Remind[/B][/COLOR]' % (title),
        'path':plugin.url_for('cancel_remind', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
        'thumbnail': clock_icon,
        'icon': clock_icon,
        })

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT path FROM channels WHERE id=?', [channel_id.decode("utf8")])
    row = c.fetchone()
    path = row["path"]
    if path:
        if not int(start) in watch:
            items.append({
            'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR blue][B]Watch[/B][/COLOR]' % (title),
            'path':plugin.url_for('watch', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
            'thumbnail': clock_icon,
            'icon': clock_icon,
            })
        else:
            items.append({
            'label':'[COLOR orange][B]%s[/B][/COLOR] [COLOR blue][B]Cancel Watch[/B][/COLOR]' % (title),
            'path':plugin.url_for('cancel_watch', channel_id=channel_id, channel_name=channel_name,title=title, season=season, episode=episode, start=start, stop=stop),
            'thumbnail': clock_icon,
            'icon': clock_icon,
            })

    items.extend(channel_items)
    return items


@plugin.route('/activate_channel/<addon_id>/<channel_name>')
def activate_channel(addon_id,channel_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addons WHERE addon=? AND name=?', [addon_id,channel_name])
    row = c.fetchone()
    link = row["path"]
    icon = row["icon"]

    xbmc.executebuiltin('Container.Update("%s")' % link)


@plugin.route('/channel/<channel_id>/<channel_name>')
def channel(channel_id,channel_name):
    global big_list_view
    big_list_view = True

    items = []

    addon = xbmcaddon.Addon()
    addon_icon = addon.getAddonInfo('icon')
    addon_name = remove_formatting(addon.getAddonInfo('name'))

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM channels WHERE id=?', [channel_id.decode("utf8")])
    row = c.fetchone()
    path = row["path"]
    icon = row["icon"]
    method = row["play_method"]

    if method == "not_playable":
        is_playable = False
        method_label = "(Default Method)"
    else:
        is_playable = True
        method_label = "(Alternative Method)"
    if path:
        c.execute('SELECT addon FROM addons WHERE path=?', [path])
        row = c.fetchone()
        addon = row["addon"]
        addon = xbmcaddon.Addon(addon)
        addon_icon = addon.getAddonInfo('icon')
        addon_name = remove_formatting(addon.getAddonInfo('name'))
        label = "[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B] [COLOR white][B]Play[/B][/COLOR] [COLOR grey][B]%s[/B][/COLOR]" % (
        channel_name,addon_name, method_label)
        item = {'label':label,'thumbnail':addon_icon}
        item['path'] = path
        item['is_playable'] = is_playable
        edit_url = plugin.url_for('channel_play', channel_id=channel_id.encode("utf8"),channel_play=False)
        choose_url = plugin.url_for('channel_remap_all', channel_id=channel_id, channel_name=channel_name, channel_play=True)
        item['context_menu'] = [('[COLOR yellow]Play Method[/COLOR]', actions.update_view(edit_url)),
        ('[COLOR green]Default Shortcut[/COLOR]', actions.update_view(choose_url))]
        items.append(item)
    else:
        label = "[COLOR yellow][B]%s[/B][/COLOR] [COLOR white][B]Choose Player[/B][/COLOR]" % (channel_name)
        item = {'label':label,'icon':icon,'thumbnail':get_icon_path('search')}
        item['path'] = plugin.url_for('channel_remap_all', channel_id=channel_id, channel_name=channel_name, channel_play=True)
        items.append(item)

    return items


@plugin.route('/addon_streams')
def addon_streams():
    global big_list_view
    big_list_view = True
    items = []

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT DISTINCT addon FROM addons')
    addons = [row["addon"] for row in c]

    icon = ''
    item = {
    'label': '[COLOR red][B]%s[/B][/COLOR]' % ("Search Addons"),
    'path': plugin.url_for(search_addons, channel_name='none'),
    'thumbnail': get_icon_path('search'),
    'is_playable': False,
    }

    items.append(item)
    for addon_id in sorted(addons):
        try:
            addon = xbmcaddon.Addon(addon_id)
            if addon:
                icon = addon.getAddonInfo('icon')
                item = {
                'label': '[COLOR green][B]%s[/B][/COLOR]' % (remove_formatting(addon.getAddonInfo('name'))),
                'path': plugin.url_for(streams, addon_id=addon_id),
                'thumbnail': icon,
                'icon': icon,
                'is_playable': False,
                }
                items.append(item)
        except:
            pass
    return items


@plugin.route('/addon_streams_to_channels/<addon_id>')
def addon_streams_to_channels(addon_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addons WHERE addon=?', [addon_id])
    channels = dict((row['name'], (row['path'], row["play_method"], row['icon'])) for row in c)

    for channel_name in channels:
        (path, method, icon) = channels[channel_name]
        channel_name = re.sub(r'\(.*?\)$','',channel_name).strip()
        if icon:
            c.execute('UPDATE channels SET path=?, play_method=?, icon=? WHERE name=?', [path, method, icon, channel_name])
        else:
            c.execute('UPDATE channels SET path=?, play_method=? WHERE name=?', [path, method, channel_name])

    conn.commit()
    conn.close()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Addon Shortcuts to Default Shortcuts")

@plugin.route('/streams/<addon_id>')
def streams(addon_id):
    global big_list_view
    big_list_view = True
    addon = xbmcaddon.Addon(addon_id)
    if addon:
        icon = addon.getAddonInfo('icon')
    else:
        icon = ''
    items = []

    item = {'label':'[COLOR red][B]Use All as Default Shortcuts[/B][/COLOR]',
        'path':plugin.url_for('addon_streams_to_channels', addon_id=addon_id),
        'thumbnail':icon,
        'is_playable':False}
    items.append(item)

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addons WHERE addon=?', [addon_id])
    streams = dict([row["path"],[row["name"], row["icon"]]] for row in c)

    for path in sorted(streams):
        (stream_name,icon) = streams[path]
        item = {
        'label': '[COLOR yellow][B]%s[/B][/COLOR]' % (stream_name),
        'path': plugin.url_for(stream_play, addon_id=addon_id, stream_name=stream_name.encode("utf8"),path=path),
        'thumbnail': icon,
        'icon': icon,
        'is_playable': False,
        }
        items.append(item)

    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items



@plugin.route('/channel_play/<channel_id>/<channel_play>')
def channel_play(channel_id,channel_play):
    global big_list_view
    big_list_view = True
    items = []
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM channels WHERE id=?', [channel_id.decode("utf8")])
    row = c.fetchone()
    channel_name = row["name"]
    path = row["path"]
    icon = row["icon"]
    method = row["play_method"]
    if method == "not_playable":
        default_color = "grey"
        alternative_color = "red"
        is_playable = False
    else:
        default_color = "red"
        alternative_color = "grey"
        is_playable = True

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT addon FROM addons WHERE path=?', [path])
    row = c.fetchone()
    addon = row["addon"]
    addon_name = remove_formatting(xbmcaddon.Addon(addon).getAddonInfo('name'))
    addon_icon = xbmcaddon.Addon(addon).getAddonInfo('icon')

    item = {
    'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR] [COLOR %s][B]%s[/B][/COLOR]' % (
    channel_name, addon_name, default_color,'Default Play'),
    'path': path,
    'thumbnail': addon_icon,
    'is_playable': True,
    }
    url = plugin.url_for(set_channel_method, channel_id=channel_id, method='playable')
    item['context_menu'] = [('[COLOR yellow]Set Default[/COLOR]', actions.update_view(url))]
    items.append(item)
    item = {
    'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR] [COLOR %s][B]%s[/B][/COLOR]' % (
    channel_name, addon_name, alternative_color,'Alternative Play'),
    'path': path,
    'thumbnail': addon_icon,
    'is_playable': False,
    }
    url = plugin.url_for(set_channel_method, channel_id=channel_id, method='not_playable')
    item['context_menu'] = [('[COLOR yellow]Set Alternative[/COLOR]', actions.update_view(url))]
    items.append(item)

    return items

@plugin.route('/set_channel_method/<channel_id>/<method>')
def set_channel_method(channel_id,method):
    conn = get_conn()
    conn.execute('UPDATE channels SET play_method=? WHERE id=?', [method,channel_id.decode("utf8")])
    conn.commit()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/set_addon_method/<addon_id>/<stream_name>/<method>')
def set_addon_method(addon_id,stream_name,method):
    conn = get_conn()
    conn.execute('UPDATE addons SET play_method=? WHERE addon=? AND name=?', [method, addon_id, stream_name.decode("utf8")])
    conn.commit()
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/stream_play/<addon_id>/<stream_name>/<path>')
def stream_play(addon_id,stream_name,path):
    global big_list_view
    big_list_view = True
    addon = xbmcaddon.Addon(addon_id)
    if addon:
        addon_icon = addon.getAddonInfo('icon')
        addon_name = remove_formatting(addon.getAddonInfo('name'))
    else:
        icon = ''
    items = []
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addons WHERE addon=? AND path=?', [addon_id,path])
    row = c.fetchone()
    icon = row["icon"]
    method = row["play_method"]

    if method == "not_playable":
        default_color = "grey"
        alternative_color = "red"
        is_playable = False
    else:
        default_color = "red"
        alternative_color = "grey"
        is_playable = True

    item = {
    'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR] [COLOR %s][B]%s[/B][/COLOR]' % (stream_name, addon_name, default_color,'Default Play'),
    'path': path,
    'thumbnail': addon_icon,
    'is_playable': True,
    }
    url = plugin.url_for(set_addon_method, addon_id=addon_id, stream_name=stream_name, method='playable')
    item['context_menu'] = [('[COLOR yellow]Set Default[/COLOR]', actions.update_view(url))]
    items.append(item)
    item = {
    'label': '[COLOR yellow][B]%s[/B][/COLOR] [COLOR green][B]%s[/B][/COLOR] [COLOR %s][B]%s[/B][/COLOR]' % (stream_name, addon_name, alternative_color,'Alternative Play'),
    'path': path,
    'thumbnail': addon_icon,
    'is_playable': False,
    }
    url = plugin.url_for(set_addon_method, addon_id=addon_id, stream_name=stream_name, method='not_playable')
    item['context_menu'] = [('[COLOR yellow]Set Alternative[/COLOR]', actions.update_view(url))]
    items.append(item)

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

    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row

    items = []

    if plugin.get_setting('ini_type') == '1':
        url = plugin.get_setting('ini_url')
        r = requests.get(url)
        file_name = 'special://profile/addon_data/plugin.video.tvlistings.xmltv/addons.ini'
        xmltv_f = xbmcvfs.File(file_name,'w')
        xml = r.content
        xmltv_f.write(xml)
        xmltv_f.seek(0,0)
        #NOTE not xmltv_f.close()
        ini_file = file_name
        dt = datetime.now()
        now = int(time.mktime(dt.timetuple()))
        plugin.set_setting("ini_url_last",str(now))
    else:
        ini_file = plugin.get_setting('ini_file')
        path = xbmc.translatePath(plugin.get_setting('ini_file'))
        stat = xbmcvfs.Stat(path)
        modified = str(stat.st_mtime())
        plugin.set_setting('ini_last_modified',modified)

    try:
        if plugin.get_setting('ini_type') == '1':
            f = xmltv_f
        else:
            f = xbmcvfs.File(ini_file)
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
                        icon = ''
                        play_method = ''
                        conn.execute("INSERT OR IGNORE INTO addons(addon, name, path, play_method, icon) VALUES(?, ?, ?, ?, ?)", [addon, name, url, play_method, icon])
    except:
        pass
    conn.commit()
    conn.close()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Load ini File")


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

def create_database_tables():
    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS addon_paths(addon TEXT, name TEXT, path TEXT, play_method TEXT, PRIMARY KEY (path))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS addons(addon TEXT, name TEXT, path TEXT, play_method TEXT, icon TEXT, PRIMARY KEY (addon, name, path))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS channels(id TEXT, name TEXT, path TEXT, play_method TEXT, icon TEXT, PRIMARY KEY (id))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS programmes(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS remind(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.execute(
    'CREATE TABLE IF NOT EXISTS watch(channel TEXT, title TEXT, sub_title TEXT, start INTEGER, stop INTEGER, date INTEGER, description TEXT, series INTEGER, episode INTEGER, categories TEXT, PRIMARY KEY(channel, start))')
    conn.commit()
    conn.close()



def xml_channels():
    try:
        updating = plugin.get_setting('xmltv_updating')
    except:
        updating = 'false'
        plugin.set_setting('xmltv_updating', updating)
    if updating == 'true':
        return
    xmltv_type = plugin.get_setting('xmltv_type')
    if plugin.get_setting('xml_reload') == 'true':
        plugin.set_setting('xml_reload','false')
    else:
        try:
            xmltv_type_last = plugin.get_setting('xmltv_type_last')
        except:
            xmltv_type_last = xmltv_type
            plugin.set_setting('xmltv_type_last', xmltv_type)
        if xmltv_type == xmltv_type_last:
            if plugin.get_setting('xmltv_type') == '0': # File
                if plugin.get_setting('xml_reload_modified') == 'true':
                    path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
                    stat = xbmcvfs.Stat(path)
                    modified = str(stat.st_mtime())
                    last_modified = plugin.get_setting('xmltv_last_modified')
                    if last_modified == modified:
                        return
                    else:
                        pass
                else:
                    return
            else:
                dt = datetime.now()
                now_seconds = int(time.mktime(dt.timetuple()))
                try:
                    xmltv_url_last = int(plugin.get_setting("xmltv_url_last"))
                except:
                    xmltv_url_last = 0
                if xmltv_url_last + 24*3600 < now_seconds:
                    pass
                else:
                    return
        else:
            pass

    xbmc.log("XMLTV UPDATE")
    plugin.set_setting('xmltv_type_last',xmltv_type)

    dialog = xbmcgui.Dialog()

    xbmcvfs.mkdir('special://profile/addon_data/plugin.video.tvlistings.xmltv')


    conn = get_conn()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    conn.execute('DROP TABLE IF EXISTS programmes')
    create_database_tables()
    c = conn.cursor()
    c.execute('SELECT id FROM channels')
    old_channel_ids = [row["id"] for row in c]


    dialog.notification("TV Listings (xmltv)","downloading xmltv file")
    if plugin.get_setting('xmltv_type') == '1':
        url = plugin.get_setting('xmltv_url')
        r = requests.get(url)
        file_name = 'special://profile/addon_data/plugin.video.tvlistings.xmltv/xmltv.xml'
        xmltv_f = xbmcvfs.File(file_name,'w')
        xml = r.content
        xmltv_f.write(xml)
        xmltv_f.close()
        xmltv_file = file_name
        dt = datetime.now()
        now = int(time.mktime(dt.timetuple()))
        plugin.set_setting("xmltv_url_last",str(now))
    else:
        xmltv_file = plugin.get_setting('xmltv_file')
        path = xbmc.translatePath(plugin.get_setting('xmltv_file'))
        stat = xbmcvfs.Stat(path)
        modified = str(stat.st_mtime())
        plugin.set_setting('xmltv_last_modified',modified)

    dialog.notification("TV Listings (xmltv)","finished downloading xmltv file")

    xml_f = FileWrapper(xmltv_file)
    if xml_f.size == 0:
        return
    context = ET.iterparse(xml_f, events=("start", "end"))
    context = iter(context)
    event, root = context.next()
    last = datetime.now()
    new_channel_ids = []
    for event, elem in context:
        if event == "end":
            now = datetime.now()
            if elem.tag == "channel":
                id = elem.attrib['id']
                new_channel_ids.append(id)
                display_name = elem.find('display-name').text
                try:
                    icon = elem.find('icon').attrib['src']
                except:
                    icon = ''
                    if plugin.get_setting('logo_type') == 0:
                        path = plugin.get_setting('logo_folder')
                        if path:
                            icon = os.path.join(path,display_name,".png")
                    else:
                        path = plugin.get_setting('logo_url')
                        if path:
                            icon = "%s/%s.png" % (path,display_name)

                conn.execute("INSERT OR IGNORE INTO channels(id, name, path, play_method, icon) VALUES(?, ?, ?, ?, ?)", [id, display_name, '', '', icon])
                if (now - last).seconds > 0.5:
                    dialog.notification("TV Listings (xmltv)","loading channels: "+display_name)
                    last = now

            elif elem.tag == "programme":
                programme = elem
                start = programme.attrib['start']
                start = xml2utc(start)
                start = utc2local(start)
                stop = programme.attrib['stop']
                stop = xml2utc(stop)
                stop = utc2local(stop)
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
                total_seconds = time.mktime(stop.timetuple())
                stop = int(total_seconds)
                conn.execute("INSERT OR IGNORE INTO programmes(channel ,title , sub_title , start , stop, date, description , series , episode , categories) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [channel ,title , sub_title , start , stop, date, description , series , episode , categories])
                if (now - last).seconds > 0.5:
                    dialog.notification("TV Listings (xmltv)","loading programmes: "+channel)
                    last = now
            root.clear()

    remove_channel_ids = set(old_channel_ids) - set(new_channel_ids)
    for id in remove_channel_ids:
        conn.execute('DELETE FROM channels WHERE id=?', [id])
    conn.commit()
    conn.close()
    plugin.set_setting('xmltv_updating', 'false')
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Load xmltv File")


@plugin.route('/channels')
def channels():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    if plugin.get_setting('hide_unmapped') == 'false':
        c.execute('SELECT * FROM channels')
    else:
        c.execute('SELECT * FROM channels WHERE path IS NOT ""')
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

    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items


@plugin.route('/now_next_time/<seconds>')
def now_next_time(seconds):
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()

    if plugin.get_setting('hide_unmapped') == 'false':
        c.execute('SELECT * FROM channels')
    else:
        c.execute('SELECT * FROM channels WHERE path IS NOT ""')
    channels = [(row['id'], row['name'], row['icon']) for row in c]

    now = datetime.fromtimestamp(float(seconds))
    total_seconds = time.mktime(now.timetuple())

    items = []
    for (channel_id, channel_name, img_url) in channels:
        c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id])
        remind = [row['start'] for row in c]
        c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id])
        watch = [row['start'] for row in c]
        c.execute('SELECT start FROM programmes WHERE channel=? ORDER BY start', [channel_id])
        programmes = [row['start'] for row in c]

        times = sorted(programmes)
        max = len(times)
        less = [i for i in times if i <= total_seconds]
        index = len(less) - 1
        if index < 0:
            continue
        now_start = times[index]

        c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,now_start])
        now = datetime.fromtimestamp(now_start)
        now = "%02d:%02d" % (now.hour,now.minute)
        row = c.fetchone()
        now_title = row['title']
        now_stop = row['stop']
        if now_stop < total_seconds:
            now_title = "[I]%s[/I]" % now_title
        else:
            now_title = "[B]%s[/B]" % now_title

        if now_start in watch:
            now_title_format = "[COLOR blue]%s[/COLOR]" % now_title
        elif now_start in remind:
            now_title_format = "[COLOR red]%s[/COLOR]" % now_title
        else:
            now_title_format = "[COLOR orange]%s[/COLOR]" % now_title

        next = ''
        next_title = ''
        if index+1 < max:
            next_start = times[index + 1]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,next_start])
            next = datetime.fromtimestamp(next_start)
            next = "%02d:%02d" % (next.hour,next.minute)
            next_title = c.fetchone()['title']

        if next_start in watch:
            next_title_format = "[COLOR blue][B]%s[/B][/COLOR]" % next_title
        elif next_start in remind:
            next_title_format = "[COLOR red][B]%s[/B][/COLOR]" % next_title
        else:
            next_title_format = "[COLOR white][B]%s[/B][/COLOR]" % next_title

        after = ''
        after_title = ''
        if (index+2) < max:
            after_start = times[index + 2]
            c.execute('SELECT * FROM programmes WHERE channel=? AND start=?', [channel_id,after_start])
            after = datetime.fromtimestamp(after_start)
            after = "%02d:%02d" % (after.hour,after.minute)
            after_title = c.fetchone()['title']

        if after_start in watch:
            after_title_format = "[COLOR blue][B]%s[/B][/COLOR]" % after_title
        elif after_start in remind:
            after_title_format = "[COLOR red][B]%s[/B][/COLOR]" % after_title
        else:
            after_title_format = "[COLOR grey][B]%s[/B][/COLOR]" % after_title

        if  plugin.get_setting('show_channel_name') == 'true':
            label = "[COLOR yellow][B]%s[/B][/COLOR] %s %s %s %s %s %s" % \
            (channel_name,now,now_title_format,next,next_title_format,after,after_title_format)
        else:
            label = "%s %s %s %s %s %s" % \
            (now,now_title_format,next,next_title_format,after,after_title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['path'] = plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))

        items.append(item)

    if plugin.get_setting('sort_now') == 'true':
        sorted_items = sorted(items, key=lambda item: item['label'])
        return sorted_items
    else:
        return items


@plugin.route('/hourly')
def hourly():
    global big_list_view
    big_list_view = True
    items = []

    dt = datetime.now()
    dt = dt.replace(hour=0, minute=0, second=0)

    for day in ("Today","Tomorrow"):
        label = "[COLOR red][B]%s[/B][/COLOR]" % (day)
        items.append({'label':label,'path':plugin.url_for('hourly'),'thumbnail':get_icon_path('calendar')})
        for hour in range(0,24):
            label = "[COLOR blue][B]%02d:00[/B][/COLOR]" % (hour)
            total_seconds = str(time.mktime(dt.timetuple()))
            items.append({'label':label,'path':plugin.url_for('now_next_time',seconds=total_seconds),'thumbnail':get_icon_path('clock')})
            dt = dt + timedelta(hours=1)

    return items


@plugin.route('/prime')
def prime():
    prime = plugin.get_setting('prime')
    dt = datetime.now()
    dt = dt.replace(hour=int(prime), minute=0, second=0)
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds)
    return items


@plugin.route('/now_next')
def now_next():
    dt = datetime.now()
    total_seconds = str(time.mktime(dt.timetuple()))
    items = now_next_time(total_seconds)
    return items


@plugin.route('/listing/<channel_id>/<channel_name>')
def listing(channel_id,channel_name):
    global big_list_view
    big_list_view = True

    calendar_icon = get_icon_path('calendar')

    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)
    c.execute('SELECT * FROM remind WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    remind = [row['start'] for row in c]
    c.execute('SELECT * FROM watch WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    watch = [row['start'] for row in c]
    c.execute('SELECT * FROM programmes WHERE channel=? ORDER BY start', [channel_id.decode("utf8")])
    items = channel(channel_id,channel_name)
    last_day = ''
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        now = datetime.now()
        dt = datetime.fromtimestamp(start)
        dt_stop = datetime.fromtimestamp(stop)
        mode = 'future'
        if dt < now:
            mode = 'past'
            if dt_stop > now:
                mode = 'present'

        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR white][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,
            'is_playable':True,
            'thumbnail': calendar_icon,
            'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        if mode == "present":
            ttime = "[COLOR white][B]%02d:%02d[/B][/COLOR]" % (dt.hour,dt.minute)
        else:
            ttime = "%02d:%02d" % (dt.hour,dt.minute)

        if start in watch:
            title_format = "[COLOR blue][B]%s[/B][/COLOR]" % title
        elif start in remind:
            title_format = "[COLOR red][B]%s[/B][/COLOR]" % title
        else:
            if mode == 'past':
                title_format = "[COLOR grey][B]%s[/B][/COLOR]" % title
            else:
                title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title

        if mode == 'past':
            channel_format = "[COLOR grey]%s[/COLOR]" % channel_name
        else:
            channel_format = "[COLOR yellow][B]%s[/B][/COLOR]" % channel_name

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s %s" % (channel_format,ttime,title_format,plot)
            else:
                label = "%s %s %s" % (channel_format,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        items.append(item)
    c.close()

    return items


@plugin.route('/search/<programme_name>')
def search(programme_name):
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)
    calendar_icon = get_icon_path('calendar')
    c.execute('SELECT * FROM remind ORDER BY channel, start')
    remind = {}
    for row in c:
        if not row['channel'] in remind:
            remind[row['channel']] = []
        remind[row['channel']].append(row['start'])
    c.execute('SELECT * FROM watch ORDER BY channel, start')
    watch = {}
    for row in c:
        if not row['channel'] in watch:
            watch[row['channel']] = []
        watch[row['channel']].append(row['start'])

    c.execute("SELECT * FROM programmes WHERE LOWER(title) LIKE LOWER(?) ORDER BY start, channel", ['%'+programme_name.decode("utf8")+'%'])
    last_day = ''
    items = []
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        now = datetime.now()
        dt = datetime.fromtimestamp(start)
        dt_stop = datetime.fromtimestamp(stop)
        mode = 'future'
        if dt < now:
            mode = 'past'
            if dt_stop > now:
                mode = 'present'

        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR white][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,
            'is_playable':True,
            'thumbnail': calendar_icon,
            'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        if mode == "present":
            ttime = "[COLOR white][B]%02d:%02d[/B][/COLOR]" % (dt.hour,dt.minute)
        else:
            ttime = "%02d:%02d" % (dt.hour,dt.minute)

        if mode == 'past':
            title_format = "[COLOR grey][B]%s[/B][/COLOR]" % title
        else:
            title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title
        if channel_id in remind:
            if start in remind[channel_id]:
                title_format = "[COLOR red][B]%s[/B][/COLOR]" % title
        if channel_id in watch:
            if start in watch[channel_id]:
                title_format = "[COLOR blue][B]%s[/B][/COLOR]" % title

        if mode == 'past':
            channel_format = "[COLOR grey]%s[/COLOR]" % channel_name
        else:
            channel_format = "[COLOR yellow][B]%s[/B][/COLOR]" % channel_name

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s %s" % (channel_format,ttime,title_format,plot)
            else:
                label = "%s %s %s" % (channel_format,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)


        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        items.append(item)
    c.close()
    return items


@plugin.route('/reminders')
def reminders():
    global big_list_view
    big_list_view = True
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT *, name FROM channels')
    channels = dict((row['id'], (row['name'], row['icon'])) for row in c)
    calendar_icon = get_icon_path('calendar')
    c.execute('SELECT * FROM remind ORDER BY channel, start')
    remind = {}
    for row in c:
        if not row['channel'] in remind:
            remind[row['channel']] = []
        remind[row['channel']].append(row['start'])
    c.execute('SELECT * FROM watch ORDER BY channel, start')
    watch = {}
    for row in c:
        if not row['channel'] in watch:
            watch[row['channel']] = []
        watch[row['channel']].append(row['start'])

    c.execute('SELECT * FROM remind UNION SELECT * FROM watch ORDER BY start, channel')
    last_day = ''
    items = []
    for row in c:
        channel_id = row['channel']
        (channel_name, img_url) = channels[channel_id]
        title = row['title']
        sub_title = row['sub_title']
        start = row['start']
        stop = row['stop']
        date = row['date']
        plot = row['description']
        season = row['series']
        episode = row['episode']
        categories = row['categories']

        now = datetime.now()
        dt = datetime.fromtimestamp(start)
        dt_stop = datetime.fromtimestamp(stop)
        mode = 'future'
        if dt < now:
            mode = 'past'
            if dt_stop > now:
                mode = 'present'

        day = dt.day
        if day != last_day:
            last_day = day
            label = "[COLOR white][B]%s[/B][/COLOR]" % (dt.strftime("%A %d/%m/%y"))
            items.append({'label':label,
            'is_playable':True,
            'thumbnail': calendar_icon,
            'path':plugin.url_for('listing', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"))})

        if not season:
            season = '0'
        if not episode:
            episode = '0'
        if date:
            title = "%s (%s)" % (title,date)
        if sub_title:
            plot = "[B]%s[/B]: %s" % (sub_title,plot)
        if mode == "present":
            ttime = "[COLOR white][B]%02d:%02d[/B][/COLOR]" % (dt.hour,dt.minute)
        else:
            ttime = "%02d:%02d" % (dt.hour,dt.minute)

        if mode == 'past':
            title_format = "[COLOR grey][B]%s[/B][/COLOR]" % title
        else:
            title_format = "[COLOR orange][B]%s[/B][/COLOR]" % title
        if channel_id in remind:
            if start in remind[channel_id]:
                if mode == 'past':
                    title_format = "[COLOR red]%s[/COLOR]" % title
                else:
                    title_format = "[COLOR red][B]%s[/B][/COLOR]" % title
        if channel_id in watch:
            if start in watch[channel_id]:
                if mode == 'past':
                    title_format = "[COLOR blue]%s[/COLOR]" % title
                else:
                    title_format = "[COLOR blue][B]%s[/B][/COLOR]" % title

        if mode == 'past':
            channel_format = "[COLOR grey]%s[/COLOR]" % channel_name
        else:
            channel_format = "[COLOR yellow][B]%s[/B][/COLOR]" % channel_name

        if  plugin.get_setting('show_channel_name') == 'true':
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s %s" % (channel_format,ttime,title_format,plot)
            else:
                label = "%s %s %s" % (channel_format,ttime,title_format)
        else:
            if plugin.get_setting('show_plot') == 'true':
                label = "%s %s %s" % (ttime,title_format,plot)
            else:
                label = "%s %s" % (ttime,title_format)

        item = {'label':label,'icon':img_url,'thumbnail':img_url}
        item['info'] = {'plot':plot, 'season':int(season), 'episode':int(episode), 'genre':categories}
        item['path'] = plugin.url_for('play', channel_id=channel_id.encode("utf8"), channel_name=channel_name.encode("utf8"), title=title.encode("utf8"), season=season, episode=episode, start=start, stop=stop)
        items.append(item)
    c.close()
    return items


@plugin.route('/search_dialog')
def search_dialog():
    dialog = xbmcgui.Dialog()
    name = dialog.input('Search for programme', type=xbmcgui.INPUT_ALPHANUM)
    if name:
        return search(name)


@plugin.route('/nuke')
def nuke():
    TARGETFOLDER = xbmc.translatePath(
        'special://profile/addon_data/plugin.video.tvlistings.xmltv'
        )
    dialog = xbmcgui.Dialog()
    ok = dialog.ok('TV Listings (xmltv)', '[COLOR red][B]Delete Everything in addon_data Folder?![/B][/COLOR]')
    if not ok:
        return
    if os.path.exists( TARGETFOLDER ):
            shutil.rmtree( TARGETFOLDER , ignore_errors=True)

    dialog.notification("TV Listings (xmltv)","Done: Everything Deleted!")

def urlencode_path(path):
    from urlparse import urlparse, parse_qs, urlunparse
    path = path.encode("utf8")
    o = urlparse(path)
    query = parse_qs(o.query)
    path = urlunparse([o.scheme, o.netloc, o.path, o.params, urllib.urlencode(query, True), o.fragment])
    return path


@plugin.route('/browse_addons')
def browse_addons():
    global big_list_view
    big_list_view = True
    try:
        response = RPC.addons.get_addons(type="xbmc.addon.video",properties=["thumbnail"])
    except:
         return

    addons = response["addons"]
    ids = [a["addonid"] for a in addons]
    thumbnails = dict([[f["addonid"], f["thumbnail"]] for f in addons])
    items = []
    for id in ids:
        path = "plugin://%s" % id
        path = urlencode_path(path)
        addon = xbmcaddon.Addon(id)
        name = remove_formatting(addon.getAddonInfo('name'))
        name = remove_formatting(name)
        item = {'label':'[COLOR green][B]%s[/B][/COLOR]' % name,
        'path':plugin.url_for('browse_path', addon=id, path=path),
        'thumbnail':thumbnails[id]}
        items.append(item)

    sorted_items = sorted(items, key=lambda item: item['label'])
    return sorted_items


@plugin.route('/browse_path/<addon>/<path>')
def browse_path(addon,path):
    global big_list_view
    big_list_view = True

    addon_icon = xbmcaddon.Addon(addon).getAddonInfo('icon')

    try:
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    except:
         return

    files = response["files"]

    dirs = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "directory"])
    links = dict([[f["file"], f["label"]] for f in files if f["filetype"] == "file"])
    thumbnails = dict([[f["file"], f["thumbnail"]] for f in files])

    top_items = []
    item = {'label':'[COLOR red][B]Add Folder to Addon Shortcuts[/B][/COLOR]',
    'path':plugin.url_for('add_addon_channels', addon=addon, path=path, addon_name=False, method="playable"),
    'thumbnail':addon_icon,
    'is_playable':False}
    top_items.append(item)
    item = {'label':'[COLOR green][B]Add Folder to Addon Shortcuts with Alternative Play Method[/B][/COLOR]',
    'path':plugin.url_for('add_addon_channels', addon=addon, path=path, addon_name=False, method="not_playable"),
    'thumbnail':addon_icon,
    'is_playable':False}
    top_items.append(item)

    items = []

    for dir in sorted(dirs):
        log(dir)
        path = dirs[dir]
        dir = remove_formatting(dir)
        item = {'label':dir,
        'path':plugin.url_for('browse_path', addon=addon, path=path),
        'thumbnail':addon_icon,
        'is_playable':False}
        items.append(item)
    for path in sorted(links):
        label = links[path]
        label = remove_formatting(label)
        icon = thumbnails[path]
        item = {'label':label.encode("utf8"),
        'path':plugin.url_for('activate_play', label=label.encode("utf8"), path=path, icon=icon),
        'is_playable':False,
        'thumbnail':icon}
        items.append(item)

    sorted_items = sorted(items, key=lambda item: item['label'])
    items = top_items + sorted_items
    return items


@plugin.route('/reload_addon_paths')
def reload_addon_paths():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM addon_paths')
    addon_paths = [(row["addon"],row["path"],row["name"],row["play_method"]) for row in c]
    for addon_path in addon_paths:
        add_addon_channels(addon_path[0],addon_path[1],addon_path[2],addon_path[3])
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Addon Paths Refreshed")



@plugin.route('/add_addon_channels/<addon>/<path>/<addon_name>/<method>')
def add_addon_channels(addon,path,addon_name,method):
    try:
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    except:
         return

    files = response["files"]
    labels = dict([[f["file"], f["label"]] for f in files if f["filetype"] == "file"])
    thumbnails = dict([[f["file"], f["thumbnail"]] for f in files])

    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO addon_paths(addon, name, path, play_method) VALUES(?, ?, ?, ?)", [addon, addon_name, path, method])

    for file in sorted(labels):
        label = labels[file]
        label = re.sub('\[.*?\]','',label)
        icon = thumbnails[file]
        conn.execute("INSERT OR REPLACE INTO addons(addon, name, path, play_method, icon) VALUES(?, ?, ?, ?, ?)", [addon, label, file, method, icon])

    conn.commit()
    conn.close()
    dialog = xbmcgui.Dialog()
    dialog.notification("TV Listings (xmltv)","Done: Addon Path Added")


@plugin.route('/add_defaults/<addon>/<path>/<addon_name>')
def add_defaults(addon,path,addon_name):
    try:
        response = RPC.files.get_directory(media="video", directory=path, properties=["thumbnail"])
    except:
         return
    links = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "file"])
    addon = remove_formatting(xbmcaddon.Addon(addon))
    name = addon.getAddonInfo('name')

    for link in sorted(links):
        if addon_name == "True":
            title = "%s [COLOR green]%s[/COLOR]" % (link,name)
        else:
            title = link


@plugin.route('/activate_play/<label>/<path>/<icon>')
def activate_play(label,path,icon):
    global big_list_view
    big_list_view = True
    items = []
    item = {'label':"[COLOR yellow][B]%s[/B][/COLOR] - [COLOR green][B]Play[/B][/COLOR]" % label,'path':path,'is_playable':True, 'thumbnail':icon }
    items.append(item)
    item = {'label':"[COLOR yellow][B]%s[/B][/COLOR] - [COLOR green][B]Alternative Play[/B][/COLOR]" % label,'path':path,'is_playable':False, 'thumbnail':icon }
    items.append(item)
    return items


@plugin.route('/activate_link/<link>')
def activate_link(link):
    xbmc.executebuiltin('Container.Update("%s")' % link)


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
        'label': '[COLOR red][B]Channel Listings[/B][/COLOR]',
        'path': plugin.url_for('channels'),
    },
    {
        'label': '[COLOR yellow][B]Search Programmes[/B][/COLOR]',
        'path': plugin.url_for('search_dialog'),
    },
    {
        'label': '[COLOR blue][B]Reminders[/B][/COLOR]',
        'path': plugin.url_for('reminders'),
    },
    {
        'label': '[COLOR yellow]Channel Player[/COLOR]',
        'path': plugin.url_for('channel_list'),
    },
    {
        'label': '[COLOR red]Default Shortcuts[/COLOR]',
        'path': plugin.url_for('channel_remap'),
    },
    {
        'label': '[COLOR green]Addon Shortcuts[/COLOR]',
        'path': plugin.url_for('addon_streams'),
    },
    {
        'label': '[COLOR grey]Addon Browser[/COLOR]',
        'path': plugin.url_for('browse_addons'),
    },
    ]
    return items


if __name__ == '__main__':
    create_database_tables()
    xml_channels()
    store_channels()
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)