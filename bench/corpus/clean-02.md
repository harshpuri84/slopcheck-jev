Retries now stop after four attempts and write the payload to a dead-letter queue.

The old policy retried forever, which turned one bad upstream response into 40,000
requests over a weekend.

The queue drains by hand. Nobody has built a replay tool yet.
