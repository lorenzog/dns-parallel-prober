A domain name generator
=======================

This script is a PoC for a parallelised domain name brute forcer. It
creates a queue and fills it with threads, each of them tasked with one
sub-domain. At every iteration it removes dead threads from the queue
and replenishes it as necessary.

It adapts the iteration frequency to the depletion speed, i.e. the
faster the threads complete the sooner new ones will be added. It tries
to stay reasonably close to the maximum value set.

Usage:

    ./dns-queue example.com 10 out.txt

Press ctrl-c to stop - it will wait for the last threads to finish and
write all results to a file.

Please note that no DNS query is performed: all that each thread does is
wait a (normally distributed) amount of time and report on itself.
