"""
PoC for distributing DNS queries
================================

"""
from __future__ import print_function
from collections import deque
import random
import sys
import time
import threading


MIN_DNS_SERVERS = 40
INCREASE_PERCENT = 0.1
HALVE_AMOUNT = 3


class Prober(threading.Thread):
    def __init__(self, dns_host):
        # invoke Thread.__init__
        super(Prober, self).__init__()
        self.dns_host = dns_host

    def run(self):
        # this simulates how long the DNS query will take; substitute with the
        # actual DNS query command then save the output to a database
        _will_take = random.random() * 10
        time.sleep(_will_take)


def main():
    # this is the starting value - give it enough time to add all threads to
    # the queue
    sleep_interval = random.random() * 10

    d = deque()
    ql = deque()
    # initialize the queue
    for i in range(MIN_DNS_SERVERS):
        t = Prober('host1.example.com')
        t.start()
        d.append(t)

    ql.append(len(d))

    # initial value
    previous_len = len(d)
    running = True
    while running:
        try:
            # go through the queue and remove the threads that are done
            for el in range(len(d)):
                _t = d.popleft()
                if _t.is_alive():
                    # put it back and continue
                    d.append(_t)
                else:
                    # thread was done - we remove it from the queue
                    pass
            # print "Deque has length {}".format(len(d))

            # calculate how fast the queue has been growing
            delta = len(d) - previous_len
            rate = delta / sleep_interval
            # print(rate)
            ql.append(len(d))

            if rate > 2:
                # the queue is filling up too fast: increase sleep time it by 10%
                sleep_interval += (sleep_interval * INCREASE_PERCENT)
                print('+', end="")
            elif len(d) < MIN_DNS_SERVERS or rate < 0.5:
                # the queue is emptying too fast: drastically reduce sleep time
                sleep_interval /= HALVE_AMOUNT
                print('-', end="")
            else:
                # queue is neither empyting too fast nor filling up too fast -
                # we're OK
                print('.', end="")
                # pass

            # add new probers, taking the hostnames from a list
            t = Prober('another_host')
            t.start()
            d.append(t)

            time.sleep(sleep_interval)

        except KeyboardInterrupt:
            print("\nPlease wait for all threads to finish...")
            running = False
        finally:
            sys.stdout.flush()

    with open('data.txt', 'w') as f:
        for i, el in enumerate(ql):
            f.write('{} {}\n'.format(i, el))


if __name__ == '__main__':
    print("+: increase sleep time by {}%\n-:decrease sleep time by {}\n.: no change\n".format(INCREASE_PERCENT, HALVE_AMOUNT))
    main()
