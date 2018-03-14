# TraktToSonarr
Synchronize shows from Trakt in Sonarr

This Python 3 script will allow you to sync Trakt into your Sonarr installation.

For this to work, you will need to create an API in Trakt using this link : https://trakt.tv/oauth/applications/new
ont the ClientId, the Secret ID and the App ID, you can find the last one on your App page it's the last number in the URL
ex : https://trakt.tv/oauth/applications/xxxxxx  with xxxxx your App ID

other thing you might need :
create a list for your shows, you can use the watchlist, but once you'll have seen all of a show or season, it is removed from the watchlist, this is how Trakt manage it.
you also can create another list for the shows you want to be created in sonarr but not searched, I use this for show on Netflix, that way I can see them in the Sonarr calendar, but they're not downloaded.


This script use Pyton 3.6


the python librairy you will need to run the script :
trakt.py
--> pip install trakt.py
tvdbsimple
--> pip install tvdbsimple

the first run will create the config file, you will have to edit it to put all Trakt ID, Sonarr URL...
