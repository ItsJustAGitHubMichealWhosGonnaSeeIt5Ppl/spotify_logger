## Just check the notion page


# // Imports
from flask import redirect
import requests # // Send API requests
import flask # // Web app/web server. This is letting me do the oauth token and callback with spotify
import urllib.parse # // Still not 100% sure
import dotenv # // Securely storing our API keys
import os # // Needed to access the API keys
import datetime # // Used to track user first login time and track removal time
import sqlite3 # // Used for information collection and storage
import mySpotifyModules as sMod

# // Constants and variables we'll need alot
dotenv.load_dotenv() # // Loading variables
CLIENT_ID = os.getenv("CLIENT_ID") # // Loading variables
CLIENT_SECRET = os.getenv("CLIENT_SECRET") # // Loading variables
TOKEN_URL = 'https://accounts.spotify.com/api/token' # // Token request URL, send user code here :)
AUTH_URL = 'https://accounts.spotify.com/authorize?' # // User auth page, send users here and get data from the callback
REDIRECT_URI = 'http://localhost:8888/callback' # // Local callback, should contain users code which is used to get the token above
API_URL = 'https://api.spotify.com/v1' # // Base URL for all API calls to spotify
## \\ All above are Constants (variable that cannot be changed). To create, use ALL_CAPS_WITH_UNDERSCORES

# // Setup SQLite
app = flask.Flask(__name__) 

@app.route("/") # // Homepage
def index(): 
    return flask.render_template("index.html") # // VERY basic HTML

@app.route('/login') # // Login page, sends you to spotify link after getting all the shit needed
def login():
    # scope = 'user-read-private user-library-read playlist-modify-private playlist-modify-public' # // permissions required to get user saved tracks and user acct info
    params = { # Request to be sent to spotify
    'response_type': 'code', # // Spotify said I had to put this here
    'client_id': CLIENT_ID,
    'redirect_uri': REDIRECT_URI,
    'scope': 'user-read-private user-library-read playlist-modify-private playlist-modify-public', # // permissions required to get user saved tracks and user acct info
    'show_dialog': 'False' # // This makes me login each time so I can get a new auth code. Good for debugging and since I have to restart this all the time
    }
    userAuth = f"{AUTH_URL}{urllib.parse.urlencode(params)}" # // This encodes params in a nice url format. (see example belo) 
    # // params becomes "response_type=code&client_id=576e6294677d45b59bfa9ebb49a2c8f0&redirect_uri=http%3A%2F%2Flocalhost%3A8888%2Fcallback&" etc.
    return flask.redirect(userAuth) # // This redirects to the output of the command above. In this case, spotify uses the callback address to send the info we need


@app.route('/callback') # // Assuming everyhing above is working, this should be where the redirect goes 
def callback():
    # /global token # // Make token global, this probably isn't needed long term but I like working in the command line for now.
    if 'code' in flask.request.args: # // Look for "code", send to spotify if we find it
        userTokenRequestData = { # // Send the below info to spotify to get our token for requests. 
            'code': flask.request.args['code'], # // We just extract the token here
            'grant_type':'authorization_code', # // We want an authorisation code
            'redirect_uri': REDIRECT_URI, # // Not used, but they want it
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        }
        userTokenResponse = requests.post(TOKEN_URL, data = userTokenRequestData) # // Send request to spotify for actual token
        if userTokenResponse.status_code == 200:
            print("Login stage 2 complete") #// Debug
            unixTime = int(str(datetime.datetime.now(datetime.timezone.utc).timestamp())[:10]) # // Get the current time (will be important later)
            userTokenResponse = userTokenResponse.json() # Format response as a dictionary
            header = {'Authorization': 'Bearer ' +  userTokenResponse['access_token']} # // Properly formatted header so spotify won't be angry

            userProfileRequest = requests.get(API_URL + '/me', headers = header).json() # // Try to get users friendly name and Spotify ID for database
            
            userInformation = { # // Reformat data from request / TODO: #1 Add a check to make sure the data is good (response code is probably fine) / TODO Try inputting this right into the SQLite request without creating a new dictionary
                "userID": userProfileRequest["id"],
                "name": userProfileRequest["display_name"],
                "token": userTokenResponse['access_token'],
                "tokenRefresh":userTokenResponse['refresh_token'],
                "tokenRefreshedDate": unixTime,
                "addedDate":unixTime,
            }
            print(userProfileRequest["id"]) # // Debug
            # // REMEMBER TO UNCOMMENT THESE
            sMod.addUser(userInformation) # // Attempt to add user
            sMod.scanLiked(userProfileRequest["id"]) # // Scan user
        else: # // Failed login, send back to auth page
            return flask.redirect('/login') 
    else: # // Failed login, send back to auth page
        return flask.redirect('/login')
    logdb = sMod.getLogs()
    return flask.render_template("logs.html", logdb=logdb)



@app.route('/logs') # // Log page
def logs():
    return flask.render_template("logs.html", logdb=sMod.getLogs())




    
if __name__ == '__main__':  # Runs only if you run the script directly
    app.run(port=8888)
    
    