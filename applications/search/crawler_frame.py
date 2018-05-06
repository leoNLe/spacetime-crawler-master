import logging
from datamodel.search.LeoleJpadill3_datamodel import LeoleJpadill3Link, OneLeoleJpadill3UnProcessedLink
from spacetime.client.IApplication import IApplication
from spacetime.client.declarations import Producer, GetterSetter, Getter
from lxml import html, etree
import re, os
from time import time
from uuid import uuid4
import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError
import robotparser

from urlparse import urlparse, urljoin, parse_qs
import signal
import sys

logger = logging.getLogger(__name__)
LOG_HEADER = "[CRAWLER]"
frequency = {}
most_out_link = ["temp", -1]
last_time_write = 0
parsed = urlparse('www.website.com')

@Producer(LeoleJpadill3Link)
@GetterSetter(OneLeoleJpadill3UnProcessedLink)
class CrawlerFrame(IApplication):
    app_id = "LeoleJpadill3"

    def __init__(self, frame):
        self.app_id = "LeoleJpadill3"
        self.frame = frame

    def initialize(self):
        self.count = 0
        links = self.frame.get_new(OneLeoleJpadill3UnProcessedLink)
        if len(links) > 0:
            print "Resuming from the previous state."
            self.download_links(links)
        else:
            # l = LeoleJpadill3Link("http://ganglia.ics.uci.edu/")
            l = LeoleJpadill3Link("http://www.ics.uci.edu/")

            print l.full_url
            self.frame.add(l)

    def update(self):
        unprocessed_links = self.frame.get_new(OneLeoleJpadill3UnProcessedLink)
        if unprocessed_links:
            self.download_links(unprocessed_links)

    def download_links(self, unprocessed_links):
        for link in unprocessed_links:
            print "Got a link to download:", link.full_url
            downloaded = link.download()
            links = extract_next_links(downloaded)
            for l in links:
                if is_valid(l):
                    self.frame.add(LeoleJpadill3Link(l))

    def shutdown(self):
        print (
            "Time time spent this session: ",
            time() - self.starttime, " seconds.")


def to_load():
    global frequency
    try:
        frequency_in_file = open("/Users/leole/Documents/GitHub/"
                                 "spacetime-crawler-master/spacetime-crawler-master/frequency.txt", "r")
        for line in frequency_in_file:
            subdomain, time = line.split(' ')
            frequency[subdomain] = time
    except IOError:
        print("no file to load")
    frequency_in_file.close()
    try:
        in_most_out_links = open("/Users/leole/Documents/GitHub/spacetime-crawler-master/"
                                "spacetime-crawler-master/most_out.txt", "r")
        for line in in_most_out_links:
            site, outlink = line.split(' ')
            most_out_link[0] = site
            most_out_link[1] = outlink
    except IOError:
        return False;
    in_most_out_links.close()


def to_write():
    out_frequency = open("/Users/leole/Documents/GitHub/spacetime-crawler-master/spacetime-crawler-master/frequency.txt", "w")
    out_most_out_links = open("/Users/leole/Documents/GitHub/spacetime-crawler-master/spacetime-crawler-master/most_out.txt", "w")

    for row in frequency:
        print >> out_frequency, row + " " + str(frequency[row])

    out = str(most_out_link[0]) + " " + str(most_out_link[1])
    out_most_out_links.write(out)

    out_frequency.close()
    out_most_out_links.close()


def check_most_out_link(url, out_link_count):
    if most_out_link[1] < out_link_count:
        most_out_link[0] = url
        most_out_link[1] = out_link_count


def get_main_URL_from_raw(rawDataObj):
    if rawDataObj.is_redirected:
        url = rawDataObj.final_url
    else:
        url = rawDataObj.url
    return url


def get_tag_url_from_main(url):
    website_data = requests.get(url)
    soup = BeautifulSoup(website_data.content, "lxml")

    # return only the anchor tags
    return soup('a')


def extract_next_links(rawDataObj):
    outputLinks = []
    global last_time_write
    global parsed
    '''
    rawDataObj is an object of type UrlResponse declared at L20-30
    datamodel/search/server_datamodel.py
    the return of this function should be a list of urls in their absolute form
    Validation of link via is_valid function is done later (see line 42).
    It is not required to remove duplicates that have already been downloaded. 
    The frontier takes care of that.

    Suggested library: lxml
    1. Keep track of the subdomains that it visited, 
            and count how many different URLs it has processed from each of those subdomains.
    2.  Find the page with the most out links (of all pages 
        given to your crawler). Out Links are the number of links that are present on a particular webpage.
    3. Any additional things you may find interesting to keep track of, such as, 
        invalid links, crawler traps encountered, and so on. But this is not mandatory.
    '''

    # load when file first start
    if not frequency:
        to_load()

    url = get_main_URL_from_raw(rawDataObj)
    tag = get_tag_url_from_main(url)
    out_link_count = 0

    for ref in tag:
        href = ref.get('href', 'none')
        if not href.startswith('http'):
            href = urljoin(rawDataObj.url, href)

        if (href not in outputLinks) and is_valid(href):
            out_link_count += 1
            outputLinks.append(href)
            href_parsed = urlparse(href)
            if parsed.netloc in frequency:
                frequency[href_parsed.netloc] = 1 + int(frequency[href_parsed.netloc])
            else:
                frequency[parsed.netloc] = 1

    check_most_out_link(url, out_link_count)

    if last_time_write == 10:
        to_write()
        last_time_write = 0
    else:
        last_time_write = last_time_write + 1

    return outputLinks


def check_url(url):
    if len(url) >= 30:
        return False
    else:
        return True


def is_valid(url):
    '''
    Function returns True or False based on whether the url has to be
    downloaded or not.
    Robot rules and duplication rules are checked separately.
    This is a great place to filter out crawler traps.
    '''
    global parsed
    parsed = urlparse(url)
    if parsed.scheme not in set(["http", "https"]):
        return False

    # remove calendar
    if "calendar" in parsed.netloc:
        return False

    # if length of url is too long probably a trap
    if not check_url(parsed.query):
        return False

    # check if url is no 404 by only checking only getting the header of the url
    # should be last b/c it is quite expensive
    try:
        request = requests.head(url)
        if request.status_code != 200:
            return False
    except ConnectionError:
        return False

    try:
        return ".ics.uci.edu" in parsed.hostname \
               and not re.match(".*\.(css|js|bmp|gif|jpe?g|ico" + "|png|tiff?|mid|mp2|mp3|mp4" \
                                + "|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf" \
                                + "|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso|epub|dll|cnf|tgz|sha1" \
                                + "|thmx|mso|arff|rtf|jar|csv" \
                                + "|rm|smil|wmv|swf|wma|zip|rar|gz|pdf)$", parsed.path.lower())
    except TypeError:
        print ("TypeError for ", parsed)
        return False
