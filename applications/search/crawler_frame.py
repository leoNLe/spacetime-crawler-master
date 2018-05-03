import logging
from datamodel.search.LeoleJpadill3_datamodel import LeoleJpadill3Link, OneLeoleJpadill3UnProcessedLink
from spacetime.client.IApplication import IApplication
from spacetime.client.declarations import Producer, GetterSetter, Getter
from lxml import html,etree
import re, os
from time import time
from uuid import uuid4
import  requests
from bs4 import BeautifulSoup

from urlparse import urlparse, urljoin, parse_qs
from uuid import uuid4

logger = logging.getLogger(__name__)
LOG_HEADER = "[CRAWLER]"

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


frequency = {}
most_out_link = ["temp", -1]


def check_most_out_link(url, out_link_count):
    if most_out_link[1] < out_link_count:
        most_out_link[0] = url;
        most_out_link[1] = out_link_count
        print("most out changed ", most_out_link[0], " ", out_link_count)


def get_main_URL_from_raw(rawDataObj):
    if rawDataObj.is_redirected:
        url = rawDataObj.final_url
    else:
        url = rawDataObj.url
    return url


def get_tag_url_from_main(url):
    html = requests.get(url)
    soup = BeautifulSoup(html.content, "lxml")

    return soup('a')


def extract_next_links(rawDataObj):
    outputLinks = []
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

    # TODO writer to file
    # TODO add analytics

    url = get_main_URL_from_raw(rawDataObj)
    tag = get_tag_url_from_main(url)
    out_link_count = 0

    for a in tag:
        href = a.get('href', 'none')
        if not href.startswith('http'):
            href = urljoin(rawDataObj.url, href)
        # TODO parsed url

        if (href not in outputLinks) and is_valid(href):
            out_link_count += 1
            outputLinks.append(href)

    check_most_out_link(url, out_link_count)

    return outputLinks



def is_valid(url):
    '''
    Function returns True or False based on whether the url has to be
    downloaded or not.
    Robot rules and duplication rules are checked separately.
    This is a great place to filter out crawler traps.
    '''
    parsed = urlparse(url)
    if parsed.scheme not in set(["http", "https"]):
        return False
    try:
        return ".ics.uci.edu" in parsed.hostname \
            and not re.match(".*\.(css|js|bmp|gif|jpe?g|ico" + "|png|tiff?|mid|mp2|mp3|mp4"\
            + "|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf" \
            + "|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso|epub|dll|cnf|tgz|sha1" \
            + "|thmx|mso|arff|rtf|jar|csv"\
            + "|rm|smil|wmv|swf|wma|zip|rar|gz|pdf)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        return False

