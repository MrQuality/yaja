# Physical spikes

A spike resolves one uncertain external behavior before implementation depends
on it. Write it in standard-library Python, with the hypothesis in its docstring,
the exact service/version and prerequisites, bounded timeouts, raw observable
output, nonzero failure status, and a clear cleanup procedure. Do not substitute
fixtures or mock servers for a physical target. Add lasting knowledge to docs.

Run `python scripts/setup_env.py --start`, then `python spikes/active_spike.py`.
The active hypothesis is that the real local NATS server advertises JetStream,
accepts CONNECT/PING, returns PONG, and serves a JetStream account-info request.
The script uses a random private inbox and auto-unsubscribes after one reply.
It writes no stream or application data; closing the socket completes cleanup.
Connection and read deadlines are 3 seconds, with bounded frame counts and sizes.

Success reports JSON with the observed server ID/version and response type. This
proves handshake/account API reachability, not durable message storage or delivery.
The hook executes it fresh from the Git index and does not trust cached markers.
For future database, CDC, or search work, introduce a new concrete physical spike
and add its acceptance checks to scripts/verify.py before claiming the boundary.
