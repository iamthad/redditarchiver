redditarchiver
==============

redditarchiver, a tool for archiving reddit JSON data and linked files

redditarchiver will download data of a desired listing (or listings) associated with a reddit account.

According to the [reddit API](https://www.reddit.com/dev/api#GET_user_{username}_{where}https://www.reddit.com/dev/api#GET_user_{username}_{where}), it is possible to get the following listings:
- overview
- submitted
- comments
- liked
- hidden
- saved
- gilded

To use redditarchiver, copy users.json.template to users.json in ~/.redditarchiver and fill out the appropriate information. Alternatively, run redditarchiver --username your\_username. In this case, only  'liked' and 'saved' will be archived.

On the first run, redditarchiver will download everything from the specified listings that reddit allows it to (around 1000 items at maximum). On subsequent runs, it will only download newer items.

By default, redditarchiver will only download the JSON data. To enable preliminary support for downloading imgur images, run with --process. This will make a list of the appropriate URLs, download them with wget (if present), and, if present, use jdberry's [tag tool](https://github.com/jdberry/tag) to add OS X Mavericks tags to each file with the subreddit name in which they were found.
