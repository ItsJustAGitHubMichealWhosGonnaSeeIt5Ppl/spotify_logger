


# // Trying to move all functions here for clarity
from requests import get, post
import urllib.parse # Will be used once all functions  are moved over
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
REDIRECT_URI = os.getenv("REDIRECT_URI") # // Local callback, should contain users code which is used to get the token above
API_URL = 'https://api.spotify.com/v1' # // Base URL for all API calls to spotify

""" Ideally, none of the spotify requests should have loops for now.
Do loops on the site."""

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
            query = "UPDATE users SET tokenRefreshedDate = ?, token = ? WHERE userID = ?"
            data = (currentUnixTime, newToken, userID)
            accessDB(query,data,True)
            return newToken
        else: attempts+=1
        

#TODO #9 Choose repeat time, only scan if last scan was more than 5 minutes ago
def scanLiked(scanUser): # // Scan users liked tracks manually.  Input userID (would normally run every _ minutes)
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute("SELECT token, tokenRefresh, tokenRefreshedDate, userID FROM users WHERE userID=?",(scanUser,)) # // Should probably have some validation somewhere
    userInfo = cursor.fetchone() # //Output from SQL request above as tuple 
    if scanUser not in userInfo: # // Check for valid input #TODO Does not work if there is no data returned
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
                "actionDate": likedDateUnix,
                "userID": userInfo[3], # // Allows for better insertion into the logger
                "latestAction": "yes",
                "actionType": "added",
                "uID": trackInfo["id"][:7] + str(likedDateUnix) + userInfo[3][:7] # Creates a UID for the track
                }
            uidList.append(trackInfo["id"][:7] + str(likedDateUnix) + userInfo[3][:7])
        # // Make sure we're not still in the loop
    uidList = tuple(uidList) 
    cursor.execute(f""" SELECT * FROM trackLog WHERE UID NOT IN {uidList} AND userID=? AND actionType='added' AND latestAction='yes'""",(userInfo[3],)) 
    removedTracks = cursor.fetchall()
    cursor.execute(f""" UPDATE OR IGNORE trackLog SET latestAction='no' WHERE userID=? AND actionType='added' AND latestAction='yes' AND UID NOT IN {uidList}""",(userInfo[3],))
    for track in removedTracks: # Add log iteem for removed tracks
        newUID = track[0]+ 'r' # Add R to UID to indicate its been removed
        cursor.execute(f"INSERT OR IGNORE INTO trackLog VALUES(?, ?, ?, ?, 'removed', 'yes')",(newUID,track[1],track[2],currentUnixTime,))
    for x in userTracksData: # // Iterate through and attempt to update each track to both the log and song list
        cursor.execute("INSERT OR IGNORE INTO spotifyTracks VALUES(:trackID, :trackURL, :previewURL, :track, :album, :artist)", userTracksData[x]) # // Add tracks to the main track DB. 
        cursor.execute("INSERT OR IGNORE INTO trackLog VALUES(:uID, :trackID, :userID, :actionDate, :actionType, :latestAction)", userTracksData[x]) #// Only add songs where tags don't match
    database.commit()
def addUser(userInfo): # // Attempt to add user
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute("INSERT OR IGNORE INTO users VALUES(:userID, :name, :token, :tokenRefresh, :tokenRefreshedDate, :addedDate)", userInfo)
    database.commit()

# TODO #13 Replace likeddate and unliked date with actionDate and add a new action for all actions
def getLogs(userID="all"): # Get logs for all users or a specific user(if specified) #TODO #8 Multiple users cause this to mark all songs as removed
    database = sqlite3.connect("spotifyBackup.db")
    logDB= {}
    cursor = database.cursor() 
    if userID != "all": # // Check if user ID is blank TODO, #5 add failure detection
        cursor.execute(""" SELECT * FROM trackLog WHERE userID=? ORDER BY actionDate DESC""",(userID,))
    else:
        cursor.execute(""" SELECT * FROM trackLog ORDER BY actionDate DESC""",)
    trackLog = cursor.fetchall()
    for action in trackLog:
        """ Action is a tuple, the indexes are
        0 UID
        1 trackID
        2 userID
        3 actionDate
        4 actionType - Can be added or removed, maybe it should be true or false, IDK
        5 latestAction - Yes or no, i dont think we'll use this?
        """
        # Get user friendly name and track info
        cursor.execute("SELECT name FROM users WHERE userID=?",(action[2],))
        name = cursor.fetchone()
        cursor.execute("SELECT track, trackURL, artist FROM spotifyTracks WHERE trackID=?",(action[1],))
        artistInfo = cursor.fetchone()
        """ Artist info returns a tuble 
        0 Track name
        1 Track URL
        2 Artist
        """
        dateRel = datetime.datetime.now() - datetime.datetime.fromtimestamp(action[3])
        logDB[action[0]] = { # Formatted data for web
                "name": name[0],
                "trackName": artistInfo[0],
                "artistName": artistInfo[2],
                "trackURL": artistInfo[1],
                "trackID": action[1],
                "action": action[4],
                "actionDateRel": dateRel,
                "actionUnix": action[3],
                "userID": action[2]
            }
    return logDB
    

def drasticMeasures(): # Delete the entire trackLog DB
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute("DELETE FROM trackLog")
    database.commit()
    return print("trackLog has been wiped")    


def scheduledScan(): # Scans all users
    database = sqlite3.connect("spotifyBackup.db")
    cursor = database.cursor()
    cursor.execute("Select userID FROM users")
    users = cursor.fetchall()
    for user in users:
        scanLiked(user[0])
   
# Welcome to the spotify section
def spotifyUserAuth():
    # scope = 'user-read-private user-library-read playlist-modify-private playlist-modify-public' # // permissions required to get user saved tracks and user acct info
    params = { # Request to be sent to spotify
    'response_type': 'code', # // Spotify said I had to put this here
    'client_id': CLIENT_ID,
    'redirect_uri': REDIRECT_URI,
    'scope': 'user-read-private user-library-read playlist-modify-private playlist-modify-public', # // permissions required to get user saved tracks and user acct info
    'show_dialog': 'False' # // This makes me login each time so I can get a new auth code. Good for debugging and since I have to restart this all the time
    }
    return f"{AUTH_URL}{urllib.parse.urlencode(params)}" # return formatted spotify authorisation string

def spotifyUserToken(userCode): # Request spotify token with user details.
    tokenRequestData = { # // Send the below info to spotify to get our token for requests. 
            'code': userCode, # // We just extract the token here
            'grant_type':'authorization_code', # // We want an authorisation code
            'redirect_uri': REDIRECT_URI, # // Not used, but they want it
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        }
    tokenRequest = post(TOKEN_URL, data = tokenRequestData) # // Send request to spotify for actual token
    if tokenRequest.status_code == 403: # This error appears if the spotify account that was attempting to authorise has not been invited
        return 403 # In this case we will use this to mean unauthorised
    elif tokenRequest.status_code == 200: # Confirm valid input, get additional required info
        
        header = {'Authorization': 'Bearer ' + tokenRequest.json()['access_token']} 
        profileRequest = get(API_URL + '/me', headers = header) # Get profile friendly name and ID
        if profileRequest.status_code == 200:
            return { # Relevant details for return call                  
                    "date": int(str(datetime.datetime.now(datetime.timezone.utc).timestamp())[:10]),
                    "display_name": profileRequest.json()['display_name'],
                    "id": profileRequest.json()['id'],
                    "access_token": tokenRequest.json()['access_token'],
                    "refresh_token": tokenRequest.json()['refresh_token'],
                }
        return 555 # This will catch other errors, if more specific codes are found, add them above