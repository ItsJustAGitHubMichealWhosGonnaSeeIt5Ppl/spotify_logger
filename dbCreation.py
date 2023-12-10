
# // SQLite might be referred to as SQL in comments. \\
# // SQL keywords are not cAsE SenSiTive but any values will be
## Misc SQLite notes
# .cursor() is how you send data to SQL/how you interact with it
# .commit() saves your changes
# if NOT EXISTS should avoid accidentally duplicating data

import sqlite3
import datetime
from zlib import DEF_BUF_SIZE


database = sqlite3.connect("spotifyBackup.db") # // Open DB (creates it if it doesnt exist) // Note this is created in the project root. In this case not in SpotifyBackupTool, it was Understanding APIs

cursor = database.cursor() # // Sets cursor variable to the database 
# // Both tables are now only created if they do not already exist
# // Create the user table (if it doesnt already exist)
cursor.execute("""CREATE TABLE if NOT EXISTS users(
               userID TEXT PRIMARY KEY,
               name TEXT,
               token TEXT,
               tokenRefresh TEXT,
               tokenRefreshedDate INT,
               addedDate INT
)""")
## // Table explainer \\ ##
# userID = Spotify user ID
# name = Spotify Display Name
# token = users authorisation token
# tokenRefresh = users refresh token (send this in to get a new token)
# tokenRefreshedDate = UNIX timestamp when the token was last refreshed
# addedDate = UNIX timestamp when the user authorised. Used to limit how much information is shown in the log I guess? If we have the info already im not sure it actually matters

# // Track table. Stores song name, artist, album, etc.  Avoids calling the API too often and then having spotify tell me to stop and then making me sad
cursor.execute("""CREATE TABLE if NOT EXISTS spotifyTracks(
               trackID TEXT PRIMARY KEY,
               trackURL TEXT,
               previewURL TEXT,
               track TEXT,
               album TEXT,
               artist TEXT)""")
## // Table explainer \\ ##
# trackID = Spotify track ID
# trackURL = Spotify track URL
# previewURL = Spotify preview URL
# track = Track name 
# artist = Self explainatory 
# album = Self explainatory 

#// Logs users liked tracks (current and previous)
cursor.execute("""CREATE TABLE if NOT EXISTS trackLog(
               UID TEXT PRIMARY KEY,
               trackID TEXT,
               userID TEXT,
               actionDate INT,
               actionType TEXT,
               latestAction TEXT,
               FOREIGN KEY(userID) REFERENCES users(userID),
               FOREIGN KEY(trackID) REFERENCES spotifyTracks(trackID)
)""")
## // Table explainer \\ ## 
# UID = Allows each item to be tracked individually
# trackID = Spotify track ID from spotifyTrack table. Reduces unneeded API calls
# userID = userID from the users table
# actionDate = either the liked date or the unliked date
# actionType = added or removed
# latestAction yes or no depending on if the song has already been removed

## This is just for testing
unixTime = str(datetime.datetime.now(datetime.timezone.utc).timestamp())[:10] # Current time in unix
humanTime = datetime.datetime.utcfromtimestamp(float(unixTime))
print(unixTime) #// This wil break in 2286, I think we're ok for now though
print(humanTime.strftime("%x %X")) # // Human time

