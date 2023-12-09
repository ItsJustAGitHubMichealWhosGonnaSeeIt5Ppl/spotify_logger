# // Trying to move all functions here for clarity
from requests import get, post
import urllib.parse # Will be used once all functionsa are moved over
import dotenv # // Securely storing our API keys
import os # // Needed to access the API keys
import datetime # // Used to track user first login time and track removal time
import sqlite3 # // Used for information collection and storage

# // Constants and variables needed often
dotenv.load_dotenv() # // Loading .env variables
CLIENT_ID = os.getenv("CLIENT_ID") 
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_URL = 'https://accounts.spotify.com/api/token' # // Token request URL, send user code here :)
AUTH_URL = 'https://accounts.spotify.com/authorize?' # // User auth page, send users here and get data from the callback
REDIRECT_URI = 'http://localhost:8888/callback' # // Local callback, should contain users code which is used to get the token above
API_URL = 'https://api.spotify.com/v1' # // Base URL for all API calls to spotify




currentUnixTime = int(str(datetime.datetime.now(datetime.timezone.utc).timestamp())[:10])

def accessDB(query,data,commit=False): # // Execute SQL queries here 
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute(query,data)
    if commit == True: database.commit() # Save changes


def tokenRefresher(refershToken,userID):
    attempts = 0
    while attempts < 5: # Try to refresh token up to 5 rimes
        tokenRefreshData = { # Create refresh token request
                'grant_type':'refresh_token', # // Per documentation, this has to be refresh token
                'refresh_token': refershToken,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
            }
        refreshTokenRequest = post(TOKEN_URL, data = tokenRefreshData) # // Token refresher
        if refreshTokenRequest.status_code == 200: # // Confirm Token request was successful
            refreshTokenRequest = refreshTokenRequest.json() # // Reformat response
            newToken = refreshTokenRequest["access_token"]
            newExpiration = currentUnixTime
            query = "UPDATE users SET tokenRefreshedDate = ?, token = ? WHERE userID = ?"
            data = (currentUnixTime, newToken, userID)
            accessDB(query,data,True)
            return newToken
        else: attempts+=1

def scanLiked(scanUser): # // Scan users liked tracks manually.  Input userID (would normally run every _ minutes)#
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute("SELECT token, tokenRefresh, tokenRefreshedDate, userID FROM users WHERE userID=?",(scanUser,)) # // Should probably have some validation somewhere
    userInfo = cursor.fetchone() # //Output from SQL request above as tuple 
    if scanUser not in userInfo: # // Check for valid input
        return print("No user found")

    if userInfo[2] + 3000 < currentUnixTime: # Check if token is more than 1 hour old (technically a bit less just to be safe in case it runs slow
        token = tokenRefresher(userInfo[1],userInfo[3])
    else: 
        token = userInfo[0]
    header = {'Authorization': 'Bearer ' +  str(token)} # // Header for API requests
    
    # // data needed for the while loop below
    totalTracks = 1 # // placeholder
    trackOffset = 0 # // placeholder / used to iterate through chunks of 50 tracks
    userTracksData = {}
    uidList=[]
    
    while trackOffset < totalTracks:
        print(f"doing tracks starting at{trackOffset}, total tracks = {totalTracks}")
        trackRequest = get(API_URL + "/me/tracks?limit=50&offset=" + str(trackOffset), headers = header) # // Pull first 50 tracks # // Add server busy detection [500]
        if trackRequest.status_code != 200: continue 
        trackRequest = trackRequest.json()
        totalTracks = int(trackRequest["total"])
        trackOffset = int(trackRequest["offset"]) + 50 # // Add 50 to offset (loading the next page)
        for x in trackRequest["items"]: # // Iterate through the tracks that were just loaded
            trackInfo = x["track"] # Drops into track level for easier access.
            likedDateUnix = int(datetime.datetime.fromisoformat(x["added_at"].replace("Z", "")).timestamp()) # // This would work if I was on python 3.11 / That was a lie. Removing the Z works though
            userTracksData[trackInfo['id']] = { # // Create dictionary item for each track using ID as its UID
                "trackID": trackInfo["id"], 
                "trackURL": trackInfo["external_urls"]["spotify"],
                "previewURL": trackInfo['preview_url'],
                "track": trackInfo["name"],
                "album": trackInfo["album"]["name"],
                "artist": trackInfo["artists"][0]["name"],
                "likedDate": likedDateUnix,
                "userID": userInfo[3], # // Allows for better insertion into the logger
                "null": "",
                "added": "added",
                "uID": trackInfo["id"][:7] + str(likedDateUnix) + userInfo[3][:7], # // Creates all track UIDs
                "currentDate": int(str(datetime.datetime.now(datetime.timezone.utc).timestamp())[:10]),
                }
            uidList.append(trackInfo["id"][:7] + str(likedDateUnix) + userInfo[3][:7])
        # // Make sure we're not still in the loop ;)
    for x in userTracksData: # // Iterate through and attempt to update each track to both the log and song list
        cursor.execute("INSERT OR IGNORE INTO spotifyTracks VALUES(:trackID, :trackURL, :previewURL, :track, :album, :artist)", userTracksData[x]) # // Add tracks to the main track DB. 
        cursor.execute("INSERT OR IGNORE INTO trackLog VALUES(:uID, :trackID, :userID, :likedDate, :null, :likedDate, :added)", userTracksData[x]) #// Only add songs where tags don't match
    database.commit()
    uidList = tuple(uidList)
    cursor.execute(f"UPDATE trackLog SET unlikedDate = ?, actionDate = ?, actionType = 'removed' WHERE UID NOT IN {uidList} AND actionType = 'added'", (currentUnixTime, currentUnixTime,)) # This should kind of work
    database.commit()


def addUser(userInfo): # // Attempt to add user
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute("INSERT OR IGNORE INTO users VALUES(:userID, :name, :token, :tokenRefresh, :tokenRefreshedDate, :addedDate)", userInfo)
    database.commit()


def getLogs(userID=""): # Get logs for all users or a specific user(if specified)
    database = sqlite3.connect("spotifyBackup.db")
    logDB= {}
    cursor = database.cursor() 
    if userID == "": # // Check if user ID is blank TODO, add failure detection
        cursor.execute(""" SELECT * FROM trackLog ORDER BY actionDate DESC""",)
    trackLog = cursor.fetchall()
    for action in trackLog:
        """ Action is a tuple, the indexes are
        0 UID
        1 trackID
        2 userID
        3 likedDate
        4 unlikedDate (This can be blank!!)
        5 actionDate - This is what should be pulled from 99.9% of the time
        6 actionType - Can be added or removed, maybe it should be true or false, IDK
        """
        cursor.execute("SELECT name FROM users WHERE userID=?",(action[2],))
        name = cursor.fetchone()
        cursor.execute("SELECT track, trackURL, artist FROM spotifyTracks WHERE trackID=?",(action[1],))
        artistInfo = cursor.fetchone()
        """ Artist info returns a tuble 
        0 Track name
        1 Track URL
        2 Artist
        """
        date = datetime.datetime.fromtimestamp(action[5])
        dateAdded = datetime.datetime.fromtimestamp(action[3])
        logDB[action[0]] = { # Formatted data for web
                "Name": name[0],
                "trackName": artistInfo[0],
                "artistName": artistInfo[2],
                "trackURL": artistInfo[1],
                "trackID": action[1],
                "action": action[6],
                "actionDate": str(date),
                "actionUnix": action[5]
            }
        if action[6] == "removed": # // Add liked song entry for now removed songs TODO sort this
            logDB["add"+action[0]] = { # Formatted data for webpage
                "Name": name[0],
                "trackName": artistInfo[0],
                "artistName": artistInfo[2],
                "trackURL": artistInfo[1],
                "trackID": action[1],
                "action": "added",
                "actionDate": str(dateAdded),
                "actionUnix": action[3]
            }
    return logDB
    

def drasticMeasures(): # Delete the entire trackLog DB
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute("DELETE FROM trackLog")
    database.commit()
# getLogs() #// DEBUG ONLY