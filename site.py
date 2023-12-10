# // Imports
from flask import redirect
import requests # // Send API requests
import flask # // Web app/web server. This is letting me do the oauth token and callback with spotify
import urllib.parse # // Still not 100% sure
import dotenv # // Securely storing our API keys
import os # // Needed to access the API keys
import datetime # // Used to track user first login time and track removal time
import mySpotifyModules as sMod
from waitress import serve
#TODO #4 Update requirements.txt
#TODO #11 Misc optimisations 


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
loginAttempts = 0 # TODO make sure this doesnt sync between users logging in
@app.route("/") # // Homepage
def index():
    global loginAttempts
    loginAttempts = 0 # Set login attempts back to - 
    return flask.render_template("index.html") # // VERY basic HTML

@app.route('/login') # // Login page, sends you to spotify link after getting all the shit needed
def login():
    return flask.redirect(sMod.spotifyUserAuth()) # Redirect user to spotify auth page

@app.route('/callback') # // Assuming everyhing above is working, this should be where the redirect goes 
def callback():
    global loginAttempts # This feels janky
    if 'code' in flask.request.args: # Failure detection.
        tokenResponse = sMod.spotifyUserToken(flask.request.args['code'])
        if tokenResponse == 403: # User who tried to login does not have permission to use this app.  Add them in the spotify dev panel.
             return "You are not authorised to use this app. Please contact the creator" #TODO #14 Make this a page that explains the error a bit more
        elif tokenResponse == 555:
            if loginAttempts < 5:
                loginAttempts +=1
                return flask.redirect('/login')
            else:
                return "You have exceeded the maximum number of login attempts.  Please try again later"
        else: # This data should always be the code we need, maybe it should check if its 200?
            print("Login auth passed") #// Debug
    
            query = "INSERT OR IGNORE INTO users VALUES(:id, :display_name, :access_token, :refresh_token, :date, :date)" # Create SQL Query
            sMod.accessDB(query,tokenResponse,True)
            print(tokenResponse["id"]) # // Debug
            sMod.scanLiked(tokenResponse["id"]) # // Scan user
    else: # // Failed login, send back to auth page
        if loginAttempts < 5:
            loginAttempts +=1
            return flask.redirect('/login')
        else:
            return "You have exceeded the maximum number of login attempts.  Please try again later"
    logdb = sMod.getLogs()
    return flask.render_template("logs.html", logdb=logdb)



@app.route('/logs') # // Log page
def logs():
    return flask.render_template("logs.html", logdb=sMod.getLogs())



    
if __name__ == '__main__': 
    serve(app, host ="0.0.0.0", port=8888)
    
    