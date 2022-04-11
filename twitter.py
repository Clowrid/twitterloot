import os
import time
import tweepy
import re
from dotenv import load_dotenv
from datetime import datetime
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import requests
requests.packages.urllib3.disable_warnings() 

load_dotenv()
########### Using InfluxDB to store processed tweets ##################

listTweetID = []
token = os.getenv("INFLUX_TOKEN")
org = os.getenv("INFLUX_ORG")
bucket = os.getenv("INFLUX_BUCKET")

client = InfluxDBClient(url=os.getenv("INFLUX_URL"), token=token, org=org,verify_ssl=False)
write_api = client.write_api(write_options=SYNCHRONOUS)

query = """from(bucket: "clowrid's bucket")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "tweet")
  |> filter(fn: (r) => r["_field"] == "id")"""
tables = client.query_api().query(query, org=org)
for table in tables:
    for record in table.records:
        listTweetID.append(str(int(record.get_value())))

################# Using tweeter API #################
auth = tweepy.OAuthHandler(os.getenv('CONSUMER_KEY'), os.getenv('CONSUMER_SECRET'))
auth.set_access_token(os.getenv('ACCESS_TOKEN'), os.getenv('ACCESS_SECRET'))
api = tweepy.API(auth,wait_on_rate_limit=True)


regex = r"(^|[^@\w])@(\w{1,30})"
newtweetcounter, oldtweetcounter, ignorecounter = 0, 0, 0
ignoreList =  os.getenv('IGNORE').split(",")

searchwordlist =  os.getenv('SEARCH_WORDS').split(",")
for searchword in searchwordlist:
    for tweet in tweepy.Cursor(api.search, q=searchword,
                            lang="fr", result_type='popular', count=int(os.getenv('SEARCH_ITEM_NUMBER')),
                            tweet_mode='extended').items(int(os.getenv('SEARCH_ITEM_NUMBER'))):

        if tweet.user.screen_name in ignoreList:
            continue

        if str(int(tweet.id_str)) in listTweetID:
            if int(os.getenv('DEBUG')) == 1:
                print("tweet already processed : ",int(tweet.id_str))
            oldtweetcounter += 1
            continue
        elif (tweet.in_reply_to_status_id is not None) or hasattr(tweet, 'retweeted_status'):
            if int(os.getenv('DEBUG')) == 1:
                print("tweet is a reply/RT : ",int(tweet.id_str))
            ignorecounter += 1
            continue

        else:
            tweetId = str(int(tweet.id_str))
            print("tweet en cours: ",tweetId)
            listTweetID.append(tweetId)
            data = 'tweet,host=tweeter id="'+tweetId+'"'
            write_api.write(bucket, org, data)
            matches = re.findall(regex, tweet.full_text)
            newtweetcounter += 1
            for match in matches:
                if int(os.getenv('DEBUG')) == 1:
                    print("Follow @%s" % (match[1]))
                try:
                    api.create_friendship(match[1])
                except Exception as e:
                    print(e)
                    pass

            try:
                api.create_favorite(tweet.id)
                if (tweet.full_text.lower().find('tag') != -1 or tweet.full_text.lower().find('identifie') != -1  or tweet.full_text.lower().find('mentionne') != -1 or tweet.full_text.lower().find('ami') != -1 or tweet.full_text.lower().find('comment') != -1):
                    api.update_status(status = os.getenv('TAG_TEXT'), in_reply_to_status_id = tweet.id , auto_populate_reply_metadata=True)
            except Exception as e:
                print(e)
                pass

            try:
                api.create_friendship(tweet.user.screen_name)
            except Exception as e:
                print(e)
                pass

            try:
                tweet.retweet()
            except Exception as e:
                print(e)
                pass
            time.sleep(os.getenv('WAITING_TIME_BETWEEN_TWITTER_REQUESTS'))

    if int(os.getenv('DEBUG')) == 1:
        print('[',searchword,']','Subscribed to',newtweetcounter,'new contests.',oldtweetcounter,'were ignored (already subscribed)',ignorecounter,'were ignored (reply or RT)')

################# RT alternatives topics to hide competition RT #################
itemlist =  os.getenv('ALTERNATIVE_TOPICS').split(",")
for item in itemlist:
    for tweet in tweepy.Cursor(api.search, q=item,
                           lang="fr", result_type='popular', count=int(os.getenv('ALTERNATIVE_ITEM_NUMBER')),
                           tweet_mode='extended').items(int(os.getenv('ALTERNATIVE_ITEM_NUMBER'))):
        if str(int(tweet.id_str)) in listTweetID:
            continue
        tweetId = str(int(tweet.id_str))
        listTweetID.append(tweetId)
        data = 'tweet,host=tweeter id="'+tweetId+'"'
        write_api.write(bucket, org, data)
        try:
            tweet.retweet()
        except Exception as e:
            print(e)
            pass
        time.sleep(5)

client.close()