import contextlib
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest
from unittest.mock import patch

import download_speed


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hits = 0
        cls.payload = b'x' * 150_000

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.hits += 1
                if self.path == '/error':
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Length', str(len(cls.payload)))
                self.end_headers()
                self.wfile.write(cls.payload[:100])
                self.wfile.flush()
                time.sleep(0.01)
                self.wfile.write(cls.payload[100:])

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_downloads_ten_complete_responses_and_calculates_metrics(self):
        before = self.hits
        ticks = [value for i in range(10) for value in (i * 3.0, i * 3.0 + 2)]
        with patch.object(download_speed.time, 'perf_counter', side_effect=ticks):
            result = download_speed.measure(self.url, 5)
        self.assertEqual(self.hits - before, 10)
        self.assertEqual(result.total_bytes, len(self.payload) * 10)
        self.assertEqual(result.average_seconds, 2)
        self.assertAlmostEqual(result.mib_per_second, 1_500_000 / 20 / 1024**2)

    def test_http_error_returns_failure_without_summary(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = download_speed.main([self.url + '/error'])
        self.assertEqual(code, 1)
        self.assertIn('404', errors.getvalue())
        self.assertNotIn('MiB/s', output.getvalue())

    def test_rejects_non_http_url(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            download_speed.main(['file:///tmp/example'])
        self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
