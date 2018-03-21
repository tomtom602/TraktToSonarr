#!/usr/local/bin/python3.6
# -*-coding:UTF-8 -*

import requests
import json
from slugify import slugify
import logging
import re

from trakt import Trakt 
from trakt.objects import Show, Season
import io
from six.moves import input
import os.path
from pprint import pprint
from datetime import datetime
import configparser

import tvdbsimple as tvdb

import pytz

utc=pytz.UTC

tvdb.KEYS.API_KEY = '01AA0A9B59C5074A'
tvdbImgs = 'https://www.thetvdb.com/banners/'


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Application(object):
  def __init__(self):
    self.authorization = None

    Trakt.on('oauth.token_refreshed', self.on_token_refreshed)
  
  def run(self):
    self.loadParameters()
    
    # Configure Trakt
    Trakt.configuration.defaults.app(
        id = self.TraktAppID
    )

    Trakt.configuration.defaults.client(
        id=self.TraktID,
        secret=self.TraktSecret
    )  
  
    self.authenticate()
    
    if not self.authorization:
      print('Authentication required')
      exit(1)
      
    with Trakt.configuration.oauth.from_response(self.authorization, refresh=True):
      r=requests.get(self.sonarrUrl + '/api/series?apikey='+self.sonarr_apikey)
      self.sonnarLib = r.json()

      reponse = Trakt['users/*/lists/*'].get(self.TraktUser, self.TraktWatchList)
      
      self.seasonsExceptions = [x for x in reponse.items() if isinstance(x, Season)]
 
      showList = [x for x in reponse.items() if isinstance(x, Show)]
      
      self.watched = {}

      #list of shows watched
      Trakt['sync/watched'].shows(self.watched, exceptions=True)
      
      
      #list of show to ignore (not monitor)
      self.Ignored = None
      if self.TraktIgnoreList:
        IgnoredTmp = Trakt['users/*/lists/*'].get(self.TraktUser, self.TraktIgnoreList).items()
        self.Ignored = [x for x in IgnoredTmp if isinstance(x, Show)]
            
      for item in showList:
        # if str(type(item)) == 'Show':
          self.TraktID = self.getTraktID(item)

          show = Trakt['shows'].get(self.TraktID, extended='full')
          
          # if self.getTvdbId(show) == '257655':
            # print('show :')
            # pprint(vars(show))
                
            
          sonarr = self.checkShowInSonarr(show)
        
          if sonarr is None:
            self.addShow(show)
          else:
            self.updateShow(show, sonarr)

  
  def authenticate(self):
    if os.path.isfile('traktToken.txt'):
      with open('traktToken.txt', 'r') as f:
        self.authorization = json.load(f)
        return True
    

    print('Navigate to: %s' % Trakt['oauth/pin'].url())

    code = input('Authorization code:')
    if not code:
        return False
    
    self.authorization = Trakt['oauth'].token_exchange(code, 'urn:ietf:wg:oauth:2.0:oob')
    print(self.authorization)
    if not self.authorization:
        return False

    with io.open('traktToken.txt', 'w', encoding='utf-8') as f:
      f.write(json.dumps(self.authorization, ensure_ascii=False))
    
    return True


  def on_token_refreshed(self, response):
    # OAuth token refreshed, save token for future calls
    self.authorization = response

    print('Token refreshed - authorization: %r' % self.authorization)    
    
  def loadParameters(self):
    config=configparser.ConfigParser()
    configFile = '/home/pi/script/syncTrakt.conf'
    
    if not os.path.exists(configFile):
      self.initConfigFile(config, configFile)
 
    
    config.read('/home/pi/script/syncTrakt.conf')
    
    self.quality=int(config.get('Sonarr', 'quality'))
    self.rootDirectory=config.get('Sonarr', 'rootDirectory')
    self.sonarr_apikey=config.get('Sonarr', 'sonarr_apikey')
    self.sonarrUrl=config.get('Sonarr', 'sonarrUrl')
    self.MonitorSpecials=config.get('Sonarr', 'MonitorSpecials').lower()=='true'

    self.TraktAppID = config.get('Trakt', 'TraktAppID')
    self.TraktID = config.get('Trakt', 'TraktID')
    self.TraktSecret = config.get('Trakt', 'TraktSecret')
    self.TraktUser = config.get('Trakt', 'user')    
    self.TraktWatchList = config.get('Trakt', 'TraktWatchList')
    self.TraktIgnoreList = config.get('Trakt', 'ignoreList')
    
    self.checkConfig()
    
    
  def checkConfig(self):
    messages = []
    if self.quality == 0:
      messages.append('quality not defined')
      
    if not os.path.exists(self.rootDirectory):
      messages.append('root directory does\'nt exists')
      
    if not self.sonarr_apikey:
      messages.append('Sonarr API key must be defined')
    
    if not self.TraktAppID:
      messages.append('Trakt Application ID must be defined')
      
    if not self.TraktID:
      messages.append('Trakt Client ID must be defined')

    if not self.TraktSecret:
      messages.append('Trakt Secret ID must be defined')      
    
    if not self.TraktWatchList:
      messages.append('Trakt watchlist must be specified')
    
    if self.TraktIgnoreList and not self.TraktUser:
      messages.append('Trakt User must be defined if you want to use the ignore list functionnality')            
    
    if len(messages) > 0:
      print('Problem(s) in configuration file :')
      for m in messages:
        print(m)
        
      exit(1)
      
    
  def initConfigFile(self, config, configFile):
    config.add_section('Sonarr')
    config.set('Sonarr', 'quality', 1)
    config.get('Sonarr', 'rootDirectory', '/home/pi')
    config.get('Sonarr', 'sonarr_apikey', '')
    config.get('Sonarr', 'sonarrUrl', 'http://127.0.0.1:8989')
    config.get('Sonarr', 'MonitorSpecials', 'False')

    config.add_section('Trakt')
    config.get('Trakt', 'TraktAppID', '')
    config.get('Trakt', 'TraktID', '')
    config.get('Trakt', 'TraktSecret', '')
    config.get('Trakt', 'user', '')    
    config.get('Trakt', 'TraktWatchList', '')
    config.get('Trakt', 'ignoreList', '')
    
    config.write(open(configFile, 'w')) 

    print('Configuration file initialized, please complete it before running the script again')
    exit(1)
  
    
  def getTvbdPoster(self, show):
    showId = self.getTvdbId(show)
    TvdbShow = tvdb.Series(78804)
  
    posters = TvdbShow.Images.poster()
    if not posters:
      imgs = []
    else:
      imgs = []
      for poster in posters:
        img = poster['fileName']
        imgs.append({'coverType' : 'poster', 'url' : tvdbImgs + img})
    
    return imgs


  def getTvdbId(self, show):
    keys = show.keys
    for key, id in keys:
      if key == 'tvdb':
        return id
      
  def getTraktID(self, show):
    keys = show.keys
    for key, id in keys:
      if key == 'trakt':
        return id  

  def getSlug(self, show):
    keys = show.keys
    for key, id in keys:
      if key == 'slug':
        return id


  def compareTitles(self, title1, title2):
    temp = re.search('^(.*)\s(\(?\d{4}\)?)$', title1)
    if(not temp):
      t1 = title1
    else:
      t1 = temp.group(1)
   
    temp = re.search('^(.*)\s(\(?\d{4}\)?)$', title2)  
    if(not temp):
      t2 = title2
    else:
      t2 = temp.group(1)
   
    if t1 == t2:
      return True
    else:
      return False

  def checkShowInSonarr(self, show):    
    for sonarrShow in self.sonnarLib:
        #pprint(sonarrShow)
        if str(sonarrShow['tvdbId']) == self.getTvdbId(show):        
          return sonarrShow            
                    
        if self.compareTitles(sonarrShow['title'], show.title):
          return sonarrShow
		
  def getSonnarrEpisodes(self, showId, seasonNumber):
    r=requests.get(self.sonarrUrl + '/api/episode?seriesId='+str(showId)+'&apikey='+self.sonarr_apikey)
    Episodes=r.json()
    
    SeasonEpisodes = [x for x in Episodes if x['seasonNumber'] == seasonNumber]    
    
    return SeasonEpisodes

  def ChangerSonarrEpisodeMonitoring(self, episode, monitor):
    if episode['monitored'] != monitor:
      episode['monitored'] = monitor
      r=requests.put(self.sonarrUrl + '/api/episode?id='+str(episode['id'])+'&apikey='+self.sonarr_apikey, data=json.dumps(episode))

      if r.status_code != 202:          
        logging.error('error updating '+show['name'])
        logging.error(r.text)


      

  def addShow(self, show):
    if self.getTvdbId(show) == None:
      logging.error('Cant\'t add show '+show.title+' : No TvdbId')
      return None


    if show.status =='canceled' or show.status =='ended':
        monitor=False
    else:
        monitor=True
		
    i=1
    tvdbId= self.getTvdbId(show)    
    watchedShowTab = [y for (x,y) in self.watched.items() if self.isSelectedShow(x, tvdbId)]
  
    watchedShow = None
    if watchedShowTab:
      watchedShow = watchedShowTab[0]
  	
#    print(show)
    neverSeen=not watchedShow
    seasons=[]
    traktId = self.getTraktID(show)
    traktSeasons = Trakt['shows'].seasons(traktId)
    if traktSeasons:
      for season in traktSeasons:
        seasons.append({'seasonNumber': season.keys[0], 'monitored': self.isToWatchedSeason(traktId, season, watchedShow)})
    
    monitored = True    
    if self.Ignored and len([x for x in self.Ignored if self.getTvdbId(x) == tvdbId]) > 0:
      monitored = False
    
        
    payload={'tvdbId':self.getTvdbId(show), 'title': show.title, 'qualityProfileId': self.quality, 'titleSlug': self.getSlug(show), 'images': self.getTvbdPoster(show), 'seasons': seasons, 'rootFolderPath': self.rootDirectory, 'seansonFolder': False,  'monitored' : monitored}
    
    if not neverSeen:
       payload.update({'addOptions' : {'ignoreEpisodesWithFiles': True}})
    r=requests.post(self.sonarrUrl + '/api/series?apikey='+self.sonarr_apikey, data=json.dumps(payload))
    if r.status_code == 201:
      logging.info('show added to Sonarr : '+show.title)
       
      result = r.json()
         
      #Update episodes for monitored seasons
      for season in seasons:
        if season['monitored']:
          self.UpdateEpisodes(result['id'], season['seasonNumber'], watchedShow)    
       
    else:
       logging.error('error adding '+show.title)
       logging.error(r.text)


  def isSelectedShow(self, key, id):
    if key[1] == id:
      return True
    else:
      return False
       
       
  def isToWatchedSeason(self, traktId, season, watched):
      
    # check if season is followed
    seasonFollowed = [x for x in self.seasonsExceptions if x.keys[0] == season.keys[0] and self.getTraktID(x.show) == traktId]  
    if len(seasonFollowed) > 0:
      return True
    
    if season.keys[0]==0:      
      if not self.MonitorSpecials:
        return False
  
    episodes= Trakt['shows'].season(traktId, season.keys[0])
  
    #finding season in watched
    watchedSeason = None
    if watched != None:
      watchedSeasonTab=[y for x,y in watched.seasons.items() if x==season.keys[0]]
      if watchedSeasonTab:
        watchedSeason=watchedSeasonTab[0]
      
    episodesCount = 0
    if episodes != None:
      episodesCount=len(episodes)
        
    episodesWatched=0
    if watchedSeason != None:
      episodesWatched= len(watchedSeason.episodes.values())
    
    
    #par défaut on suit toutes les saisons
    if episodesCount == episodesWatched:
      return False
    else:
      return True
       
  
  def UpdateEpisodes(self, sonarrId, seasonNumber, watched):
    
    Episodes = self.getSonnarrEpisodes(sonarrId, seasonNumber)
    
    #finding season in watched
    watchedSeason = None    
    if watched != None:
      watchedSeasonTab=[y for x,y in watched.seasons.items() if x==seasonNumber]
      if watchedSeasonTab:
        watchedSeason=watchedSeasonTab[0]

 
    episodesWatched=0
    if watchedSeason != None:
      episodesWatched= len(watchedSeason.episodes.values())
    
    # the season has never been watched --> set all episodes as monitored
    if watched == None or watchedSeason == None:
      for episode in Episodes:
        self.ChangerSonarrEpisodeMonitoring(episode, True)
  
  
    if episodesWatched > 0:
      watchedepisodes = [y for (x,y) in watchedSeason.episodes.items()]
      for episode in Episodes:
        monitored = len([x for x in watchedepisodes if x.keys[0][1] == episode['episodeNumber']]) == 0
        self.ChangerSonarrEpisodeMonitoring(episode, monitored)
       
  def updateShow(self, show, sonarr):
    if show.status =='canceled' or show.status =='ended':
        sonarr['monitored']=False
    else:
        sonarr['monitored']=True

    tvdbId= self.getTvdbId(show)    
    watchedShowTab = [y for (x,y) in self.watched.items() if self.isSelectedShow(x, tvdbId)]
    
    watchedShow = None
    if watchedShowTab:
      watchedShow = watchedShowTab[0]
    

    i=1
    seasons=[]    
    traktId = self.getTraktID(show)
    traktSeasons = Trakt['shows'].seasons(traktId)
    for season in traktSeasons:
      seasons.append({'seasonNumber': season.keys[0], 'monitored': self.isToWatchedSeason(traktId, season, watchedShow)})
  
    sonarr['seasons']=seasons
  
    monitored = True
    if self.Ignored and len([x for x in self.Ignored if self.getTvdbId(x) == tvdbId]) > 0:
      monitored = False
  
    sonarr['monitored']=monitored
  
    r=requests.put(self.sonarrUrl + '/api/series?apikey='+self.sonarr_apikey, data=json.dumps(sonarr))
    if r.status_code == 202:
       logging.info('show updated to Sonarr : '+show.title)
    else:      
       logging.error('error updating '+show.title)
       logging.error(r.text)
       
    #Update episids for monitored seasons
    for season in seasons:
      if season['monitored']:
        self.UpdateEpisodes(sonarr['id'], season['seasonNumber'], watchedShow)
	  
       
if __name__ == '__main__':
    # Start application
    app = Application()
    app.run()
