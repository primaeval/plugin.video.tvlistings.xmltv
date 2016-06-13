import sys
import xbmc, xbmcgui
import urllib

if __name__ == '__main__':
    filename = sys.listitem.getfilename()
    label = sys.listitem.getLabel()
    icon = xbmc.getInfoLabel( "ListItem.Icon" )
    runScript = "PlayMedia(plugin://plugin.video.tvlistings.xmltv/remove_channel/%s/%s/%s)" % ( urllib.quote( label , safe=''),urllib.quote( filename , safe=''), urllib.quote( icon , safe=''))
    xbmc.executebuiltin( "%s" %( runScript ) )
    runScript = "PlayMedia(plugin://plugin.video.tvlistings.xmltv/add_channel/%s/%s/%s/True)" % ( urllib.quote( label , safe=''),urllib.quote( filename , safe=''), urllib.quote( icon , safe=''))
    xbmc.executebuiltin( "%s" %( runScript ) )