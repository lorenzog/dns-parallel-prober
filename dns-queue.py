#!/usr/bin/env python
"""
DNS Parallel Prober
===================

Given a domain name, probes its subdomains either by brute-force or from a list.

See `README.md` for more information and usage.

"""
from __future__ import print_function
import argparse
from collections import deque
import itertools
import logging
import os
import random
import socket
import string
import sys
import time
import threading
try:
    import dns.query
    import dns.resolver
except ImportError:
    # pip install dnspython
    raise SystemExit("Module dnspython not found. Are you in the virtualenv? See README.md for quickstart instructions.")

INCREASE_PERCENT = 0.1
DEFAULT_MAX_SUBDOMAIN_LEN = 3

# valid domain names allow ASCII letters, digits and hyphen (and are case
# insensitive)
# however see
# http://stackoverflow.com/questions/7111881/what-are-the-allowed-characters-in-a-sub-domain
# and https://en.wikipedia.org/wiki/Domain_name#Internationalized_domain_names
ALPHABET = ''.join([
    string.lowercase,
    string.digits,
    # technically domains shouldn't start or end with a -
    '-',
    # add here unicode characters sets
])

log = logging.getLogger(__name__)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter())
log.addHandler(sh)
log.setLevel(logging.INFO)


res = deque()
# ns = []
# resolve = dns.resolver.Resolver()


class Prober(threading.Thread):
    def __init__(self, dns_server, target):
        # invoke Thread.__init__
        super(Prober, self).__init__()
        self.target = target
        self.dns_server = dns_server

    def run(self):
        resolver = dns.resolver.Resolver()
        try:
            log.debug("{}: Resolving {} with nameserver {}".format(
                self.name, self.target, self.dns_server))
            # it's a list
            resolver.nameservers = [self.dns_server, ]
            answer = resolver.query(self.target)
            for data in answer:
                out = '{} | {}'.format(self.target, data)
                res.append(out)
                log.info(out)
        except dns.exception.DNSException as e:
            log.debug("Error in thread {} when querying {}: {}".format(
                self.name, self.target, e))


def subdomain_gen(max_subdomain_len):
    """A generator that.. generates all subdomains from the given alphabet"""
    for i in range(max_subdomain_len):
        for p in itertools.permutations(ALPHABET, i + 1):
            yield ''.join(p)


def subdomain_fromlist(the_list):
    # XXX this could be optimised by reading chunks from the file to avoid
    # disk access every new subdomain, but if network access is slower than
    # disk access then we should be OK.
    """A generator that yields the content from a file"""
    with open(the_list) as f:
        for line in f.readlines():
            yield line.replace('\n', '')


# fills the queue with new threads
def fill(d, amount, dom, sub, nsvrs):
    for i in range(amount):
        # calls next() on the generator to get the next iteration (or next
        # subdomain)
        t = Prober(random.choice(nsvrs), '{}.{}'.format(sub.next(), dom))
        t.start()
        d.append(t)


def main(dom, max_running_threads, outfile, overwrite, infile, nsvrs, max_subdomain_len):
    if os.path.exists(outfile):
        if overwrite is False:
            raise SystemExit(
                "Specified file {} exists and overwrite "
                "option (-f) not set".format(outfile))
        else:
            log.info("Overwriting output file {}".format(outfile))
    # print(
    #     "-: queue ckeck interval increased by {}%\n.: "
    #     "no change\n".format(INCREASE_PERCENT))

    # this is the starting value - it will adjust it according to depletion
    # rate
    sleep_time = 0.5

    # the main queue containing all threads
    d = deque()

    if infile is None:
        # the subdomain generator
        sub = subdomain_gen(max_subdomain_len)
    else:
        if not os.path.exists(infile):
            raise SystemExit("{} not found".format(infile))
        sub = subdomain_fromlist(infile)

    try:

        # fill the queue ip to max for now
        #    nsvrs = dns.resolver.query(dom, 'NS')
        # ns = str(nsvrs[random.randint(0, len(nsvrs)-1)])[:-1]
        fill(d, max_running_threads, dom, sub, nsvrs)
        log.info("Press CTRL-C to gracefully stop")
        running = True
    except StopIteration:
        running = False

    previous_len = len(d)
    while running:
        try:
            time.sleep(sleep_time)
            # go through the queue and remove the threads that are done
            for el in range(len(d)):
                _t = d.popleft()
                if _t.is_alive():
                    # put it back in the queue until next iteration
                    d.append(_t)

            # calculate how fast the queue has been changing
            delta = previous_len - len(d)
            rate = delta / sleep_time
            # print('\tq: {}\tdelta: {}\trate: {}\t{}s'.format(
            #     len(d), delta, rate, sleep_time))

            if rate > 0 and delta > max_running_threads / 10:
                sleep_time -= (sleep_time * INCREASE_PERCENT)
                # print('+', end="")
            else:
                sleep_time += (sleep_time * INCREASE_PERCENT)
                # print('.', end="")

            fill(d, delta, dom, sub, nsvrs)
            previous_len = len(d)

        except KeyboardInterrupt:
            running = False
        except StopIteration:
            log.info("\nAaaand we're done!")
            running = False
        finally:
            sys.stdout.flush()

    log.info("\nPlease wait for all threads to finish...")
    # waiting for all threads to finish, popping them one by one and join()
    # each...
    for el in range(len(d)):
        t = d.popleft()
        t.join()
    with open(outfile, 'w') as f:
        for r in res:
            f.write('{}\n'.format(r))
    log.info("Results written into file {}".format(outfile))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    parser.add_argument("max_running_threads", type=int)
    parser.add_argument("savefile", default="out.txt")
    parser.add_argument(
        "-f", "--force-overwrite", default=False,
        action='store_true')
    parser.add_argument(
        "-i", "--use-list", help="Reads the list from a file",
        default=None)
    parser.add_argument("-l", "--max-subdomain-len", default=DEFAULT_MAX_SUBDOMAIN_LEN,
        help="Maximum length of the subdomain for bruteforcing. Default: {}".format(DEFAULT_MAX_SUBDOMAIN_LEN))
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-n', '--use-nameserver', action='append')
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("Debug logging enabled")

    _nsvrs = list()
    if args.use_nameserver:
        nsvrs = args.use_nameserver
    else:
        nsvrs = dns.resolver.query(args.domain, 'NS')

    for ns in nsvrs:
        log.debug('ns: {}'.format(ns))
        _nsvrs.append(socket.gethostbyname(str(ns)))

    log.debug('Using name servers: {}'.format(_nsvrs))
    main(
        args.domain,
        args.max_running_threads,
        args.savefile,
        args.force_overwrite,
        args.use_list,
        _nsvrs,
        args.max_subdomain_len,
        )
