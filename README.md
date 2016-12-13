A parallelised domain name prober
=================================

This script is a PoC for a parallelised domain name prober. It creates a
queue of threads and tasks each one to probe a sub-domain of the given
root domain. At every iteration step each dead thread is removed and the
queue is replenished as necessary.

**PLEASE NOTE** this script actually does start probing DNS servers so use
at your own risk. You are likely to get blacklisted and/or saturate your
bandwidth. Whatever you do, it's your responsibility to make sure you
have approval for it.

The key thing is that the iteration frequency is dynamically adapted to
the depletion speed, i.e. the faster the threads complete the sooner new
ones will be added until an equilibrium is reached. It tries to stay
reasonably close to the maximum value set.

Usage:

    python dns-queue example.com 100 out.txt

If you want to read the subdomains frmo a list, do:

    python dns-queue example.com 100 out.txt -i subdomains.txt

Press ctrl-c to stop - it will wait for the last threads to finish and
write all results to `out.txt`.
