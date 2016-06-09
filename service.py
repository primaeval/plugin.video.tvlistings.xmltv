import main
from xbmcswift2 import Plugin
plugin = Plugin()
monitor = xbmc.Monitor()
while not monitor.abortRequested():
    try:
        reload = plugin.get_setting('xml_reload_timer')
    except:
        reload = 'false'
    if (reload == 'true'):
        main.xml_channels()
    wait_time = 60*60
    if monitor.waitForAbort(wait_time):
        break
