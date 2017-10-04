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
    raise SystemExit("Module 'dnspython' not found. Are you in the virtualenv? See README.md for quickstart instructions.")

INCREASE_PERCENT = 0.1
DEFAULT_MAX_SUBDOMAIN_LEN = 3
DEFAULT_DNS_TIMEOUT = 5
# for checking whether the DNS is a wildcard DNS...
RANDOM_SUBDOMAINS = 5
RANDOM_SUBDOMAINS_LENGTH = 6

# valid domain names allow ASCII letters, digits and hyphen (and are case
# insensitive)
# however see
# http://stackoverflow.com/questions/7111881/what-are-the-allowed-characters-in-a-sub-domain
# and https://en.wikipedia.org/wiki/Domain_name#Internationalized_domain_names
ALPHABET = ''.join([
    string.ascii_lowercase,
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


# global object to collect results
res = deque()


class Prober(threading.Thread):
    def __init__(self, dns_server, target, dns_timeout, results_collector):
        # invoke Thread.__init__
        super(Prober, self).__init__()
        self.target = target
        self.dns_server = dns_server
        self.dns_timeout = dns_timeout
        # used for storing the results
        if results_collector is None:
            # use the global object
            self.res = res
        else:
            self.res = results_collector

    def run(self):
        resolver = dns.resolver.Resolver()
        resolver.timeout = self.dns_timeout
        try:
            log.debug("{}: Resolving {} with nameserver {}".format(
                self.name, self.target, self.dns_server))
            # it's a list
            resolver.nameservers = [self.dns_server, ]
            answer = resolver.query(self.target)
            for data in answer:
                out = '{} | {}'.format(self.target, data)
                self.res.append(out)
                # don't log to console, use file.
                # log.info(out)
        except dns.exception.Timeout as e:
            # we want to know if the DNS server is barfing
            log.warn("{}: {}".format(self.target, e))
        except dns.exception.DNSException as e:
            log.debug("Error in thread {} when querying {}: {}".format(
                self.name, self.target, e))


def random_subdomain():
    """A generator that returns random subdomains, used for checking
    wildcard DNS"""
    for i in range(RANDOM_SUBDOMAINS):
        _random_subdomain = ''
        for j in range(RANDOM_SUBDOMAINS_LENGTH):
            _random_subdomain += random.choice(ALPHABET)
        yield _random_subdomain


def subdomain_gen(max_subdomain_len):
    """A generator that.. generates all permutations of subdomains from the given alphabet"""
    for i in range(max_subdomain_len):
        for p in itertools.permutations(ALPHABET, i + 1):
            yield ''.join(p)


def subdomain_fromlist(the_list):
    # XXX this could be optimised by reading chunks from the file to avoid
    # disk access every new subdomain, but if network access is slower than
    # disk access then we should be OK.
    """A generator that returns the content from a file without loading it all in memory"""
    with open(the_list) as f:
        for line in f.readlines():
            yield line.replace('\n', '')


# fills the queue with new threads
# XXX IMPORTANT -- When this function is used to check for wildcard DNSs then
# 'amount' must be at least as big as the number of subdomains, otherwise the
# remaining will be left out. Reason: there's no replenishing of the queue when
# doing wildcard dns checks.
def fill(d, amount, dom, sub, nsvrs, dns_timeout, results_collector=None):
    for i in range(amount):
        # calls next() on the generator to get the next target
        _target = '{}.{}'.format(sub.next(), dom)
        t = Prober(
            # pick a dns server
            random.choice(nsvrs),
            _target,
            dns_timeout,
            results_collector)
        t.start()
        d.append(t)


def do_check_wildcard_dns(dom, nsvrs, dns_timeout):
    print("[+] Checking wildcard DNS...")
    # a wildcard DNS returns the same IP for every possible query of a non-existing domain
    wildcard_checklist = deque()
    wildcard_results = deque()
    try:
        # XXX the second parameter must be at least as big as the number of random subdomains;
        # as there's no replenishing of the queue here, if it's less than RANDOM_SUBDOMAINS then
        # some will be left out.
        fill(
            wildcard_checklist,
            RANDOM_SUBDOMAINS,
            dom,
            random_subdomain(),
            nsvrs,
            dns_timeout,
            wildcard_results)
        # wait for the probes to finish
        for el in range(len(wildcard_checklist)):
            t = wildcard_checklist.popleft()
            t.join()
    except KeyboardInterrupt as e:
        raise SystemExit(e)

    # TODO: parse results, stop if they all have a positive hit
    # for now we simply count the number of hits
    if len(wildcard_results) == RANDOM_SUBDOMAINS:
        raise SystemExit(
            "{} random subdomains returned a hit; "
            "It is likely this is a wildcard DNS server. Use the -w option to skip this check.".format(
                RANDOM_SUBDOMAINS))


# TODO a 'dry-run' that prints but does not execute.
#
# DEBUG code left-over
# this simulates how long the DNS query will take; substitute with the
# actual DNS query command
# using a normal distribution to simulate real work
# _will_take = abs(random.gauss(0, 1) * 5)
# time.sleep(_will_take)

def main(dom, max_running_threads, outfile, overwrite, infile, use_nameserver, max_subdomain_len, dns_timeout, no_check_wildcard_dns):

    #
    ###
    # output management
    #
    print("[+] Output destination: '{}'".format(outfile))
    if os.path.exists(outfile):
        if overwrite is False:
            raise SystemExit(
                "Specified file '{}' exists and overwrite "
                "option (-f) not set".format(outfile))
        else:
            print("[+] Output destination will be overwritten.")
    # print(
    #     "-: queue ckeck interval increased by {}%\n.: "
    #     "no change\n".format(INCREASE_PERCENT))

    #
    ###
    #

    print("[+] Press CTRL-C to gracefully stop...")

    #
    ###
    # finding DNS servers
    #

    nsvrs = list()
    if use_nameserver:
        print("[+] Using user-supplied name servers...")
        _nsvrs = use_nameserver
    else:
        try:
            print("[+] Finding authoritative name servers for domain...")
            _nsvrs = dns.resolver.query(args.domain, 'NS')
        except dns.exception as e:
            raise SystemExit(e)
        except KeyboardInterrupt as e:
            raise SystemExit(e)
    for ns in _nsvrs:
        log.debug('ns: {}'.format(ns))
        nsvrs.append(socket.gethostbyname(str(ns)))
    log.debug('Using name servers: {}'.format(nsvrs))

    #
    ###
    # check for wildcard DNS
    #

    # hate double negatives
    check_wildcard_dns = not no_check_wildcard_dns
    if check_wildcard_dns:
        do_check_wildcard_dns(dom, nsvrs, dns_timeout)

    #
    ###
    # Begin

    # this is the starting value - it will adjust it according to depletion
    # rate
    sleep_time = 0.5

    # the main queue containing all threads
    d = deque()

    if infile is None:
        # use the inbuilt subdomain generator
        sub = subdomain_gen(max_subdomain_len)
        print("[+] Will search for subdomains made of all possible {}-characters permutations".format(max_subdomain_len))
    else:
        if not os.path.exists(infile):
            raise SystemExit("{} not found".format(infile))
        sub = subdomain_fromlist(infile)
        print("[+] Will search for subdomains contained in '{}'".format(infile))

    # pre-loading of queue
    print("[+] DNS probing starting...")
    try:
        # fill the queue ip to max for now
        #    nsvrs = dns.resolver.query(dom, 'NS')
        # ns = str(nsvrs[random.randint(0, len(nsvrs)-1)])[:-1]
        fill(d, max_running_threads, dom, sub, nsvrs, dns_timeout)
        running = True
    except StopIteration:
        running = False
    except KeyboardInterrupt:
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

            fill(d, delta, dom, sub, nsvrs, dns_timeout)
            previous_len = len(d)

        except KeyboardInterrupt:
            print("\n[+] DNS probing stopped.")
            running = False
        except StopIteration:
            print("\n[+] DNS probing done.")
            running = False
        finally:
            sys.stdout.flush()

    print("[+] Waiting for all threads to finish...")
    # waiting for all threads to finish, popping them one by one and join()
    # each...
    for el in range(len(d)):
        t = d.popleft()
        t.join()
    print("[+] Saving results to {}...".format(outfile))
    with open(outfile, 'w') as f:
        for r in res:
            f.write('{}\n'.format(r))
    print("[+] Done.")


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
    parser.add_argument(
        "-l", "--max-subdomain-len", type=int, default=DEFAULT_MAX_SUBDOMAIN_LEN,
        help="Maximum length of the subdomain for bruteforcing. Default: {}".format(DEFAULT_MAX_SUBDOMAIN_LEN))
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-n', '--use-nameserver', action='append', help="Use this DNS server. Can be repeated multiple times and a random one will be picked each time")
    parser.add_argument(
        '-t', '--dns-timeout', default=DEFAULT_DNS_TIMEOUT,
        help="How long to wait for a DNS response. Default: {}s".format(DEFAULT_DNS_TIMEOUT))
    parser.add_argument(
        '-w', '--no-check-wildcard-dns', action='store_true', default=False,
        help="Skip the check for wildcard DNS")
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("Debug logging enabled")

    main(
        args.domain,
        args.max_running_threads,
        args.savefile,
        args.force_overwrite,
        args.use_list,
        args.use_nameserver,
        args.max_subdomain_len,
        args.dns_timeout,
        args.no_check_wildcard_dns,
    )
