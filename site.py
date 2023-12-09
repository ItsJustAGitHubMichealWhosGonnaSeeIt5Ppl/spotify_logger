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
from waitress import serve
#TODO #4 Update requirements.txt

# // Constants and variables we'll need alot
dotenv.load_dotenv() # // Loading variables
CLIENT_ID = os.getenv("CLIENT_ID") # // Loading variables
CLIENT_SECRET = os.getenv("CLIENT_SECRET") # // Loading variables
TOKEN_URL = 'https://accounts.spotify.com/api/token' # // Token request URL, send user code here :)
AUTH_URL = 'https://accounts.spotify.com/authorize?' # // User auth page, send users here and get data from the callback
REDIRECT_URI = os.getenv("REDIRECT_URI") # // Local callback, should contain users code which is used to get the token above
API_URL = 'https://api.spotify.com/v1' # // Base URL for all API calls to spotify
## \\ All above are Constants (variable that cannot be changed). To create, use ALL_CAPS_WITH_UNDERSCORES

# // Setup Flask
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
    return flask.redirect(userAuth) # // This redirects to the output of the command above. In this case, spotify uses the callback address to send the info we need


@app.route('/callback') # // Assuming everyhing above is working, this should be where the redirect goes 
def callback():
    if 'code' in flask.request.args: # // Look for "code", send to spotify if we find it
        tokenRequestData = { # // Send the below info to spotify to get our token for requests. 
            'code': flask.request.args['code'], # // We just extract the token here
            'grant_type':'authorization_code', # // We want an authorisation code
            'redirect_uri': REDIRECT_URI, # // Not used, but they want it
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        }
        
        tokenRequest = requests.post(TOKEN_URL, data = tokenRequestData) # // Send request to spotify for actual token
        if tokenRequest.status_code == 403: # This error appears if the spotify account that was attempting to authorise has not been invited
            return "Unauthorised (Your user is not authorised to use this Spotify)"
        if tokenRequest.status_code == 200: # Confirm valid input
            unixTime = int(str(datetime.datetime.now(datetime.timezone.utc).timestamp())[:10]) # Get time
            print("Login auth passed") #// Debug
             # Format response as a dictionary
            header = {'Authorization': 'Bearer ' +  tokenRequest.json()['access_token']} # // Properly formatted header so spotify won't be angry
            userProfileRequest = requests.get(API_URL + '/me', headers = header) # // Try to get users friendly name and Spotify ID for database
            
            if userProfileRequest.status_code != 200: return flask.redirect('/login') # Retry login if it fails. TODO #7 Add a limit to retries
            # ONLY RUNS IF TRUE
            userProfileResponse = userProfileRequest.json() # Reformat user data 
            tokenResponse = tokenRequest.json() # Reformat token data
            tokenResponse.update({ # Add ID, name, and date to to the user response table                  
                "date": unixTime,
                "display_name": userProfileResponse['display_name'],
                "id": userProfileResponse['id']
            })
            query = "INSERT OR IGNORE INTO users VALUES(:id, :display_name, :access_token, :refresh_token, :date, :date)"
            sMod.accessDB(query,tokenResponse,True)
            print(userProfileResponse["id"]) # // Debug
            sMod.scanLiked(userProfileResponse["id"]) # // Scan user
        else: # // Failed login, send back to auth page
            return flask.redirect('/login') 
    else: # // Failed login, send back to auth page
        return flask.redirect('/login')
    logdb = sMod.getLogs()
    return flask.render_template("logs.html", logdb=logdb)



@app.route('/logs') # // Log page
def logs():
    return flask.render_template("logs.html", logdb=sMod.getLogs())



    
if __name__ == '__main__':  # DEEEEEEEEEEEEEEEEEEEEEBUG
    serve(app, host ="0.0.0.0", port=8888)
    
    