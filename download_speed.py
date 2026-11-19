"""Measure download throughput using ten sequential HTTP GET requests."""

import argparse
from dataclasses import dataclass
import http.client
import math
import sys
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class Result:
    total_bytes: int
    total_seconds: float

    @property
    def average_seconds(self):
        return self.total_seconds / REQUEST_COUNT

    @property
    def mib_per_second(self):
        return self.total_bytes / self.total_seconds / 1024**2


def measure(url, timeout):
    total_bytes = 0
    total_seconds = 0.0
    for _ in range(REQUEST_COUNT):
        request = Request(url, headers={'Accept-Encoding': 'identity'})
        started = time.perf_counter()
        with urlopen(request, timeout=timeout) as response:
            received = 0
            while chunk := response.read(CHUNK_SIZE):
                received += len(chunk)
            expected = response.headers.get('Content-Length')
            if expected is not None and received != int(expected):
                raise OSError('Incomplete response body')
        total_seconds += time.perf_counter() - started
        total_bytes += received
    return Result(total_bytes, total_seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', help='HTTP or HTTPS URL to download ten times')
    parser.add_argument('--timeout', type=float, default=30,
                        help='Socket operation timeout in seconds (default: 30)')
    args = parser.parse_args(argv)
    try:
        address = urlsplit(args.url)
        valid_url = address.scheme in ('http', 'https') and address.hostname
    except ValueError:
        valid_url = False
    if not valid_url:
        parser.error('URL must use http:// or https:// and include a hostname')
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be a positive finite number')
    try:
        result = measure(args.url, args.timeout)
    except (URLError, OSError, http.client.HTTPException, ValueError) as error:
        print(f'Download failed: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted.', file=sys.stderr)
        return 130
    print(f'Requests: {REQUEST_COUNT}')
    print(f'Average request time: {result.average_seconds:.3f} s')
    print(f'Total downloaded: {result.total_bytes} bytes '
          f'({result.total_bytes / 1024**2:.3f} MiB)')
    print(f'Download speed: {result.mib_per_second:.3f} MiB/s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
