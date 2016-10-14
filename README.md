A parallelised domain name prober
=================================

This script is a PoC for a parallelised domain name prober. It creates a
queue of threads and tasks each one to probe a sub-domain of the given
root domain. At every iteration step each dead thread is removed and the
queue is replenished as necessary.

Please note that no DNS query is actually performed: all that each
thread does is wait a (normally distributed) amount of time and report
on itself. You'll have to write your own code for that.

The key thing is that the iteration frequency is dynamically adapted to
the depletion speed, i.e. the faster the threads complete the sooner new
ones will be added until an equilibrium is reached. It tries to stay
reasonably close to the maximum value set.

Usage:

    python dns-queue example.com 10 out.txt

Press ctrl-c to stop - it will wait for the last threads to finish and
write all results to `out.txt`.
