"""
PoC for distributing DNS queries
================================

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
import dns.query
import dns.resolver

INCREASE_PERCENT = 0.1
MAX_DOMAIN_LEN = 3

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
        # this simulates how long the DNS query will take; substitute with the
        # actual DNS query command

        ###
        # remove from here
        #
        # using a normal distribution to simulate real work
        # _will_take = abs(random.gauss(0, 1) * 5)
        # time.sleep(_will_take)
        #
        # to here
        ###
        # resolve.nameservers = [item.address for item in resolve.query(
        #   self.dns_server)]
        resolver = dns.resolver.Resolver()
        try:
            log.debug("Resolving {} with nameserver {}".format(
                self.target, self.dns_server))
            resolver.nameservers = self.dns_server
            answer = resolver.query(self.target)
            for data in answer:
                print('{} | {}'.format(self.target, data))
        except dns.resolver.NXDOMAIN:
            print("nope: {}".format(self.target))
        except Exception as e:
            print("Exception in thread {} when querying {}: {}".format(
                self.name, self.target, e))
        # then append the result to some form of storage
        # res.append("{} done in {}s".format(self.target, _will_take))


def subdomain_gen():
    """A generator that.. generates all subdomains from the given alphabet"""
    for i in range(MAX_DOMAIN_LEN):
        for p in itertools.permutations(ALPHABET, i + 1):
            yield ''.join(p)


def subdomain_fromlist(the_list):
    """A generator that yields the content from a file"""
    with open(the_list) as f:
        for line in f.readlines():
            yield line.replace('\n', '')


def fill(d, amount, dom, sub, nsvrs):
    for i in range(amount):
        # calls next() on the generator to get the next iteration (or next
        # subdomain)
        t = Prober(random.choice(nsvrs), '{}.{}'.format(sub.next(), dom))
        t.start()
        d.append(t)


def main(dom, max_running_threads, outfile, overwrite, infile, nsvrs):
    if os.path.exists(outfile):
        if overwrite is False:
            raise SystemExit(
                "Specified file {} exists and overwrite "
                "option (-f) not set".format(outfile))
        else:
            print("Overwriting output file {}".format(outfile))
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
        sub = subdomain_gen()
    else:
        if not os.path.exists(infile):
            raise SystemExit("{} not found".format(infile))
        sub = subdomain_fromlist(infile)

    try:

        # fill the queue ip to max for now
        #    nsvrs = dns.resolver.query(dom, 'NS')
        # ns = str(nsvrs[random.randint(0, len(nsvrs)-1)])[:-1]
        fill(d, max_running_threads, dom, sub, nsvrs)
        print("Press CTRL-C to gracefully stop")
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
            print("\nAaaand we're done!")
            running = False
        finally:
            sys.stdout.flush()

    print("\nPlease wait for all threads to finish...")
    # waiting for all threads to finish, popping them one by one and join()
    # each...
    for el in range(len(d)):
        t = d.popleft()
        t.join()
    with open(outfile, 'w') as f:
        for r in res:
            f.write('{}\n'.format(r))
    print("Results written into file {}".format(outfile))


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
    parser.add_argument('-d', '--debug', action='store_true')
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("Debug logging enabled")

    nsvrs = dns.resolver.query(args.domain, 'NS')
    _nsvrs = list()
    for ns in nsvrs:
        _nsvrs.append(socket.gethostbyname(str(ns)[:-1]))
    log.debug('Using name servers: {}'.format(_nsvrs))
    main(
        args.domain,
        args.max_running_threads,
        args.savefile,
        args.force_overwrite,
        args.use_list, _nsvrs)
