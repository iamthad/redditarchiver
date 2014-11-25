# redditarchiver 0.02, a tool for archiving reddit JSON data and linked files
# Copyright (C) 2014 Thadeus J. Fleming
#
# redditarchiver is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# redditarchiver is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with redditarchiver.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import print_function, with_statement
import json
import praw
import os
import sys
import argparse
import urlparse
import re
import subprocess32
import requests
import time
import shutil

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fresh-start',action='store_true', help='Ignore any previous data and get everything again.')
    parser.add_argument('--reprocess',action='store_true', help='Run the whole JSON file through the processing function again. This is handy when additional processing functionality has been added.')
    parser.add_argument('--no-save',dest='save', action='store_false', help="Don't save the resulting data or latest ID.")
    parser.add_argument('--process',dest='process', action='store_true', help="Process the results, downloading imgur links with wget and tagging them with the tag utility.")
    parser.add_argument('-d', '--directory', help="Where to put the archived files", default='~/Archive')
    parser.add_argument('-u', '--username', help="Which username to use. Overrides users.json")
    args = parser.parse_args()

    user_agent = "redditarchiver 0.02 by iamthad https://github.com/iamthad/redditarchiver"
    r = praw.Reddit(user_agent = user_agent)
    r.config.store_json_result = True

    fresh_start = args.fresh_start
    process = args.process
    reprocess = args.reprocess
    save = args.save

    archiveDir = os.path.expanduser(args.directory)

    # redditarchiver folder
    raDir = os.path.expanduser('~/.redditarchiver')
    # Check if redditarchiver folder exists
    if not os.path.isdir(raDir):
        os.mkdir(raDir)
    if args.username:
        users = [{'username':args.username, 'toArchive': ['liked','saved']}]
    else:
        usersFn = os.path.join(raDir,'users.json')
        if os.path.exists(usersFn):
            with open(usersFn) as usersFile:
                users = json.load(usersFile)
        else:
            print('Create a JSON file at', usersFn, 'with user information, or run with the --username argument. See users.json.template for an example')

    if process or reprocess:
        urlsFn = os.path.join(archiveDir,'urls.txt')
        tagsFn = os.path.join(archiveDir,'tags.txt')
        if os.path.exists(urlsFn):
            os.remove(urlsFn)
        if os.path.exists(tagsFn):
            os.remove(tagsFn)
    for user in users:
        print(user['username'])
        r.login(username=user['username'],password=(user['password'] if 'password' in user else None))
        me = r.user

        userDir = os.path.join(raDir,user['username'])
        if not os.path.isdir(userDir):
            os.mkdir(userDir)

        for ttype in user['toArchive']:
            newestID = get_newest_id(ttype, userDir) if not fresh_start else []
            things = get_things(ttype, me, userDir, newestID)
            if process and not reprocess:
                make_temp_files(things, archiveDir, urlsFn, tagsFn)
            things = (load_old_things(ttype, things, userDir) if not fresh_start else things)
            if reprocess:
                make_temp_files(things, archiveDir, urlsFn, tagsFn)
            if save:
                save_things(ttype, things, userDir)
    if process or reprocess:
        if os.path.exists(urlsFn) and os.path.exists(tagsFn):
            shutil.copy2('mktags.sh',archiveDir)
            run_commands(archiveDir,raDir)

def get_newest_id(ttype, userDir):
    newestIdFn = os.path.join(userDir,ttype+'-newest.txt')
    if os.path.exists(newestIdFn):
        print("Found " + ttype + "-newest")
        with open(newestIdFn) as newest:
            newestID = newest.read()
    else:
        print("First time for", ttype)
        if os.path.exists(thingJSONFn):
            print("No " + ttype + "-newest, but " + ttype +".json exists! Aborting!")
            raise Exception
        else:
            newestID = None
    return newestID


def get_things(ttype, me, userDir, newestID):

    print("Getting", ttype)

    thingJSONFn = os.path.join(userDir,ttype+'.json')

    things = []

    newthings = praw.internal._get_redditor_listing(ttype)(me,params=({'before':newestID} if newestID else {}),limit=None)
    nnew = 0
    try:
        for thing in newthings:
            things.append(thing.json_dict)
            nnew = nnew + 1
        print("Got", nnew, "new", ttype)
    except TypeError:
        print("Got 1 new", ttype)
        things.append(newthings.json_dict)
        nnew = 1
    return things

def load_old_things(ttype, things, userDir):
    thingJSONFn = os.path.join(userDir,ttype+'.json')
    if os.path.exists(thingJSONFn):
        with open(thingJSONFn) as thingsfile:
            try:
                things.extend(json.load(thingsfile))
            except Exception as e:
                print('Something went wrong', e, file=sys.stderr)
    return things

def save_things(ttype, things, userDir):
    if len(things) > 0:
        newestIdFn = os.path.join(userDir,ttype+'-newest.txt')
        thingJSONFn = os.path.join(userDir,ttype+'.json')
        newestID = things[0]['name']

        with open(newestIdFn,'w') as newest:
            newest.write(newestID)

        with open(thingJSONFn,'w') as thingsfile:
            json.dump(things,thingsfile)

def make_temp_files(things,archiveDir,urlsFn,tagsFn):
    # from RES
    imgurHashReStr = r"^https?:\/\/(?:i\.|m\.|edge\.|www\.)*imgur\.com\/(?!gallery)(?!removalrequest)(?!random)(?!memegen)([\w]{5,7}(?:[&,][\w]{5,7})*)(?:#\d+)?[sbtmlh]?(\.(?:jpe?g|gif|png|gifv))?(\?.*)?$"
    imgurHashRe = re.compile(imgurHashReStr)
    nThings = len(things)
    nImgurThings = 0
    print('Processing', nThings, 'things.')
    contentTypeDict = {"image/jpeg": ".jpg", "image/gif": ".mp4", "image/png": ".png"}

    with open(urlsFn,'a') as urlsFile, open(tagsFn,'a') as tagsFile:
        for thing in things:
            if 'url' in thing:
            # Can only process non-album imgur links for now
                url = thing['url']
                subreddit = (thing['subreddit'] if 'subreddit' in thing else '')
                parsed = urlparse.urlparse(url)
                if parsed.netloc.find('imgur') > -1:
                    match = imgurHashRe.search(url)
                    if match:
                        groups = match.groups()
                        headerReq = requests.head('http://i.imgur.com/' + groups[0] + '.jpg')
                        if 'content-type' in headerReq.headers:
                            contentType = headerReq.headers['content-type']
                            if contentType in contentTypeDict:
                                properURL = 'http://i.imgur.com/' + groups[0] + contentTypeDict[contentType]
                                print(properURL,file=urlsFile)
                                print(subreddit, 'i.imgur.com/*' + groups[0] + "*", file=tagsFile)
                                nImgurThings = nImgurThings + 1
                            else:
                                print("Error, content-type not found", contentType, file=sys.stderr) 
                        time.sleep(1)
    print('Used imgur logic for', nImgurThings, 'things.')
    

def run_commands(archiveDir,raDir):
    subprocess32.check_call('wget -xN -w 2 -i urls.txt', cwd=archiveDir, shell=True)
    subprocess32.check_call(os.path.join(archiveDir,'mktags.sh')+' tags.txt', cwd=archiveDir, shell=True)




if __name__ == "__main__":
    main()
